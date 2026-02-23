# -*- coding: utf-8 -*-
"""
HPCJobManager - HPC 远程作业生命周期管理
==========================================
将 DFTEngine（输入生成/输出解析）、HPCConnection（SSH/SFTP）、
AsyncTaskQueue（本地任务持久化）整合为一个完整的远程计算工作流:

    生成输入 → 上传 → 提交作业 → 轮询状态 → 下载结果 → 解析输出

用户通过 LLM 自然语言触发，全程异步，可中断恢复。
"""

import logging
import os
import posixpath
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from extensions.engines.dft_engine import DFTEngine, DFTTaskType
from extensions.hpc_connection import HPCConnection, HPCProfile
from extensions.async_task import AsyncTaskQueue, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class JobRecord:
    """远程作业记录（扩展 AsyncTaskQueue 的 TaskInfo）"""
    task_id: str                          # 本地 AsyncTaskQueue 任务 ID
    hpc_job_id: str = ""                  # 远程调度器作业 ID
    cluster_name: str = ""                # 目标集群
    engine_name: str = ""                 # DFT 引擎名
    task_type: str = ""                   # 计算类型
    remote_dir: str = ""                  # 远程工作目录
    output_files: List[str] = field(default_factory=list)  # 待下载的输出文件


class HPCJobManager:
    """
    HPC 远程作业管理器 — 完整的 DFT 远程计算工作流引擎。

    整合三大组件:
    - DFTEngine:     输入文件生成 + 输出解析
    - HPCConnection: SSH 连接 + 文件传输 + 作业提交
    - AsyncTaskQueue: 本地任务持久化 + 状态追踪

    工作流:
    1. submit_job(): 生成输入 → SFTP 上传 → sbatch 提交 → 返回 task_id
    2. 后台线程自动轮询远程作业状态
    3. check_job(): 查询当前状态和进度
    4. get_results(): 作业完成后下载 + 解析结果
    5. cancel_job(): 取消远程作业
    """

    # 轮询间隔（秒）
    _POLL_INTERVAL_INITIAL = 30      # 初始 30 秒
    _POLL_INTERVAL_MAX = 300         # 最长 5 分钟
    _POLL_BACKOFF_FACTOR = 1.5       # 退避因子

    def __init__(self,
                 engines: Dict[str, DFTEngine],
                 hpc_connection: HPCConnection = None,
                 task_queue: AsyncTaskQueue = None):
        """
        参数:
            engines: {引擎名: DFTEngine实例} 的字典（来自 DFTAdapter）
            hpc_connection: HPC 连接管理器（None 则新建）
            task_queue: 异步任务队列（None 则新建）
        """
        self._engines = engines
        self._hpc = hpc_connection or HPCConnection()
        self._queue = task_queue or AsyncTaskQueue()
        self._jobs: Dict[str, JobRecord] = {}     # task_id → JobRecord
        self._poll_threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    @property
    def hpc(self) -> HPCConnection:
        """暴露 HPCConnection 供外部使用"""
        return self._hpc

    # ==================== 主要工作流 ====================

    def submit_job(self,
                   engine_name: str,
                   task_type: str,
                   structure: Dict[str, Any],
                   params: Dict[str, Any],
                   cluster_name: str = None,
                   n_cores: int = None,
                   walltime: str = None,
                   queue: str = None,
                   job_name: str = None) -> Dict[str, Any]:
        """
        提交 DFT 计算到远程 HPC。

        完整流程: 生成输入 → 连接集群 → 上传文件 → 提交作业 → 启动轮询

        参数:
            engine_name: DFT 引擎名称 ("vasp"/"qe"/"abinit"/"cp2k"/"gpaw")
            task_type: 计算类型 ("single_point"/"optimize"/"dos"/...)
            structure: 原子结构描述
            params: 计算参数
            cluster_name: 目标集群（None 则使用默认）
            n_cores: 并行核心数
            walltime: 最长运行时间
            queue: 队列名
            job_name: 作业名

        返回:
            {"status": "success"/"error", "task_id": str, ...}
        """
        # --- 1. 校验引擎 ---
        engine = self._engines.get(engine_name)
        if not engine:
            available = ", ".join(self._engines.keys())
            return {"status": "error",
                    "message": f"未知 DFT 引擎: {engine_name}。可用: {available}"}

        try:
            tt = DFTTaskType(task_type)
        except ValueError:
            return {"status": "error",
                    "message": f"未知计算类型: {task_type}"}

        if not engine.supports(tt):
            cap = engine.get_capability()
            return {"status": "error",
                    "message": f"{cap.display_name} 不支持 {task_type}"}

        # --- 2. 解析集群配置 ---
        if not cluster_name:
            cluster_name = self._hpc.get_default_cluster()
        if not cluster_name:
            return {"status": "error",
                    "message": "未配置 HPC 集群。请先使用 configure_hpc 添加集群配置。"
                               "需要提供: 主机名、用户名、SSH密钥路径等"}

        profile = self._hpc.get_profile(cluster_name)
        if not profile:
            return {"status": "error",
                    "message": f"未找到集群配置: {cluster_name}"}

        n_cores = n_cores or profile.default_cores
        walltime = walltime or profile.default_walltime
        queue = queue or profile.default_queue
        job_name = job_name or f"dft_{engine_name}_{task_type}"

        # --- 3. 生成输入文件 ---
        try:
            input_files = engine.generate_input(tt, structure, params)
        except Exception as e:
            return {"status": "error",
                    "message": f"生成输入文件失败: {e}"}

        # --- 4. 生成提交脚本 ---
        run_cmd = engine.get_run_command(tt, n_cores)
        submit_script = engine.get_submit_script(
            tt, run_cmd, job_name, n_cores, walltime, queue,
            profile.scheduler
        )

        # --- 5. 连接集群 ---
        conn_result = self._hpc.connect(cluster_name)
        if conn_result["status"] != "success":
            return conn_result

        # --- 6. 创建远程工作目录 ---
        work_base = self._hpc._expand_remote_path(
            profile.work_dir, profile
        )
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        remote_dir = posixpath.join(
            work_base,
            f"{engine_name}_{task_type}_{timestamp}"
        )

        # --- 7. 上传输入文件 ---
        all_files = dict(input_files.files)
        all_files["submit.sh"] = submit_script

        upload_result = self._hpc.upload_files(
            cluster_name, all_files, remote_dir
        )
        if upload_result["status"] != "success":
            return upload_result

        # --- 8. 提交作业 ---
        submit_result = self._hpc.submit_job(
            cluster_name, remote_dir, submit_script
        )
        if submit_result["status"] != "success":
            return submit_result

        hpc_job_id = submit_result["job_id"]

        # --- 9. 记录到本地任务队列 ---
        task_id = self._queue.submit(
            plugin_name="dft",
            tool_name=f"{engine_name}__{task_type}",
            arguments={
                "engine": engine_name,
                "task_type": task_type,
                "cluster": cluster_name,
                "remote_dir": remote_dir,
                "hpc_job_id": hpc_job_id,
            },
        )

        # 更新为 RUNNING
        task_info = self._queue._tasks.get(task_id)
        if task_info:
            task_info.status = TaskStatus.RUNNING
            task_info.started_at = time.time()
            task_info.message = f"作业已提交到 {profile.host} (job {hpc_job_id})"
            self._queue._save_task(task_info)

        # 确定需要下载的输出文件
        output_files = self._get_output_filenames(engine_name, task_type)

        job = JobRecord(
            task_id=task_id,
            hpc_job_id=hpc_job_id,
            cluster_name=cluster_name,
            engine_name=engine_name,
            task_type=task_type,
            remote_dir=remote_dir,
            output_files=output_files,
        )
        with self._lock:
            self._jobs[task_id] = job

        # --- 10. 启动后台轮询线程 ---
        self._start_poll_thread(task_id)

        cap = engine.get_capability()
        est = engine.estimate_time(tt, len(structure.get("elements", [])), params)

        return {
            "status": "success",
            "task_id": task_id,
            "hpc_job_id": hpc_job_id,
            "cluster": cluster_name,
            "engine": cap.display_name,
            "task_type": task_type,
            "remote_dir": remote_dir,
            "uploaded_files": list(all_files.keys()),
            "estimated_time": est,
            "message": f"作业已提交到 {profile.host}，作业ID: {hpc_job_id}。"
                       f"使用 check_job(task_id='{task_id}') 查询进度",
        }

    def check_job(self, task_id: str) -> Dict[str, Any]:
        """
        查询作业状态（本地 + 远程）。

        参数:
            task_id: 本地任务 ID

        返回:
            包含本地状态、远程状态、进度信息的字典
        """
        # 本地状态
        local = self._queue.poll(task_id)
        if local.get("status") == "error":
            return local

        job = self._jobs.get(task_id)
        if not job:
            return {
                "status": "success",
                **local,
                "note": "仅有本地记录，无远程作业信息",
            }

        # 实时查询远程状态
        remote = self._hpc.check_job(job.cluster_name, job.hpc_job_id)

        return {
            "status": "success",
            "task_id": task_id,
            "hpc_job_id": job.hpc_job_id,
            "cluster": job.cluster_name,
            "engine": job.engine_name,
            "task_type": job.task_type,
            "remote_dir": job.remote_dir,
            "local_status": local.get("status", "unknown"),
            "remote_status": remote.get("job_status", "unknown"),
            "progress": local.get("progress", 0),
            "message": local.get("message", ""),
        }

    def get_results(self, task_id: str,
                    force_download: bool = False) -> Dict[str, Any]:
        """
        获取已完成作业的结果。

        如果作业已完成但结果未下载，自动下载并解析。

        参数:
            task_id: 本地任务 ID
            force_download: 强制重新下载
        """
        # 检查本地是否已有结果
        if not force_download:
            local_result = self._queue.get_result(task_id)
            if local_result.get("status") == "success" and "total_energy_eV" in local_result:
                return local_result

        job = self._jobs.get(task_id)
        if not job:
            return {"status": "error",
                    "message": f"未找到作业记录: {task_id}"}

        # 下载输出文件
        downloaded = self._hpc.download_files(
            job.cluster_name, job.remote_dir, job.output_files
        )
        if not downloaded:
            return {"status": "error",
                    "message": "未能下载任何输出文件。作业可能尚未完成或输出文件不存在"}

        # 用对应引擎解析
        engine = self._engines.get(job.engine_name)
        if not engine:
            return {
                "status": "success",
                "raw_files": {k: v[:1000] for k, v in downloaded.items()},
                "message": "已下载文件但未找到对应引擎进行解析",
            }

        try:
            tt = DFTTaskType(job.task_type)
            parsed = engine.parse_output(tt, downloaded)
            result = {
                "status": "success",
                "engine": job.engine_name,
                "task_type": job.task_type,
                "cluster": job.cluster_name,
                **parsed.to_dict(),
            }

            # 更新本地任务结果
            task_info = self._queue._tasks.get(task_id)
            if task_info:
                task_info.status = TaskStatus.COMPLETED
                task_info.result = result
                task_info.progress = 1.0
                task_info.completed_at = time.time()
                task_info.message = "计算完成，结果已解析"
                self._queue._save_task(task_info)

            return result

        except Exception as e:
            return {"status": "error",
                    "message": f"解析输出文件失败: {e}",
                    "downloaded_files": list(downloaded.keys())}

    def cancel_job(self, task_id: str) -> Dict[str, Any]:
        """取消远程作业"""
        job = self._jobs.get(task_id)
        if not job:
            return self._queue.cancel(task_id)

        # 停止轮询线程
        stop_event = self._stop_events.get(task_id)
        if stop_event:
            stop_event.set()

        # 取消远程作业
        cancel_result = self._hpc.cancel_job(
            job.cluster_name, job.hpc_job_id
        )

        # 更新本地状态
        self._queue.cancel(task_id)

        return {
            "status": "success",
            "task_id": task_id,
            "hpc_job_id": job.hpc_job_id,
            "message": f"作业 {job.hpc_job_id} 已取消",
            "remote_cancel": cancel_result,
        }

    def list_jobs(self, status: str = None) -> List[Dict[str, Any]]:
        """列出所有作业"""
        ts = TaskStatus(status) if status else None
        tasks = self._queue.list_tasks(status=ts)

        # 附加远程信息
        for t in tasks:
            job = self._jobs.get(t["task_id"])
            if job:
                t["hpc_job_id"] = job.hpc_job_id
                t["cluster"] = job.cluster_name
                t["engine"] = job.engine_name
                t["remote_dir"] = job.remote_dir
        return tasks

    # ==================== 后台轮询 ====================

    def _start_poll_thread(self, task_id: str) -> None:
        """启动后台轮询线程"""
        stop_event = threading.Event()
        self._stop_events[task_id] = stop_event

        thread = threading.Thread(
            target=self._poll_loop,
            args=(task_id, stop_event),
            daemon=True,
            name=f"hpc_poll_{task_id}",
        )
        self._poll_threads[task_id] = thread
        thread.start()

    def _poll_loop(self, task_id: str, stop_event: threading.Event) -> None:
        """后台轮询远程作业状态"""
        interval = self._POLL_INTERVAL_INITIAL
        job = self._jobs.get(task_id)
        if not job:
            return

        while not stop_event.is_set():
            stop_event.wait(interval)
            if stop_event.is_set():
                break

            try:
                remote = self._hpc.check_job(
                    job.cluster_name, job.hpc_job_id
                )
                remote_status = remote.get("job_status", "unknown")

                # 更新本地进度
                task_info = self._queue._tasks.get(task_id)
                if not task_info:
                    break

                if remote_status == "pending":
                    task_info.message = f"作业排队中 (job {job.hpc_job_id})"
                    task_info.progress = 0.05
                elif remote_status == "running":
                    task_info.message = f"作业运行中 (job {job.hpc_job_id})"
                    # 逐步增加进度（粗略估算）
                    task_info.progress = min(0.9, task_info.progress + 0.05)
                elif remote_status in ("completed", "failed", "cancelled"):
                    # 作业已终结
                    if remote_status == "completed":
                        task_info.message = "远程计算已完成，正在下载结果..."
                        task_info.progress = 0.95
                        self._queue._save_task(task_info)

                        # 自动下载并解析
                        self.get_results(task_id, force_download=True)
                    elif remote_status == "failed":
                        task_info.status = TaskStatus.FAILED
                        task_info.error = "远程作业执行失败"
                        task_info.completed_at = time.time()
                        task_info.message = f"作业失败 (job {job.hpc_job_id})"
                    else:
                        task_info.status = TaskStatus.CANCELLED
                        task_info.completed_at = time.time()
                        task_info.message = f"作业已被取消 (job {job.hpc_job_id})"

                    self._queue._save_task(task_info)
                    break

                self._queue._save_task(task_info)

            except Exception as e:
                logger.warning("轮询作业 %s 失败: %s", task_id, e)

            # 退避增长轮询间隔
            interval = min(interval * self._POLL_BACKOFF_FACTOR,
                           self._POLL_INTERVAL_MAX)

        # 清理
        self._poll_threads.pop(task_id, None)
        self._stop_events.pop(task_id, None)

    # ==================== 辅助方法 ====================

    def _get_output_filenames(self, engine_name: str,
                              task_type: str) -> List[str]:
        """获取各引擎的输出文件名列表"""
        output_map = {
            "vasp": ["OUTCAR", "CONTCAR", "OSZICAR", "vasprun.xml"],
            "qe": ["pw.out"],
            "abinit": ["output.abo"],
            "cp2k": ["output.out"],
            "gpaw": ["gpaw.txt", "result.gpw"],
        }

        # DOS/Band 额外输出
        extra = {
            ("vasp", "dos"): ["DOSCAR"],
            ("vasp", "band"): ["EIGENVAL", "KPOINTS"],
            ("qe", "dos"): ["pwscf.dos"],
            ("qe", "band"): ["pwscf.bands.dat"],
            ("abinit", "dos"): ["*_DOS"],
        }

        files = output_map.get(engine_name, ["output"])
        files = list(files)
        key = (engine_name, task_type)
        if key in extra:
            files.extend(extra[key])

        return files

    def shutdown(self) -> None:
        """停止所有轮询线程和连接"""
        for event in self._stop_events.values():
            event.set()
        for thread in self._poll_threads.values():
            thread.join(timeout=5)
        self._hpc.disconnect_all()
        self._queue.shutdown()
