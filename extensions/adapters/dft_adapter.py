# -*- coding: utf-8 -*-
"""
DFT Adapter - 统一 DFT 计算适配器
====================================
将多种 DFT 引擎（VASP、Quantum ESPRESSO、ABINIT、CP2K、GPAW）
统一封装为 CalculationPlugin，LLM 通过 engine 参数选择后端。

用法:
    用户: "用 QE 算一下 Fe-C 体系的单点能量"
    LLM:  → dft__single_point(engine="qe", composition={"Fe":3,"C":1}, ...)

    用户: "帮我生成 ABINIT 的输入文件"
    LLM:  → dft__generate_input(engine="abinit", ...)

    用户: "有哪些可用的 DFT 软件？"
    LLM:  → dft__list_engines()
"""

import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from extensions.base import (
    CalculationPlugin, PluginMetadata, PluginType, ToolSchema
)
from extensions.engines.dft_engine import DFTEngine, DFTTaskType, EngineCapability
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DFTAdapter(CalculationPlugin):
    """
    统一 DFT 计算适配器。

    自动发现并注册所有 DFTEngine 子类，通过 engine 参数灵活调度。
    用户无需关心具体是哪个软件，只需指定 engine="vasp"/"qe"/"abinit" 等。

    本地工具（同步）: 生成输入、解析输出、比较引擎等
    远程工具（异步）: 提交作业、监控状态、获取结果等
    """

    def __init__(self):
        self._engines: Dict[str, DFTEngine] = {}
        self._job_manager = None  # 延迟初始化
        self._discover_engines()

    def _discover_engines(self) -> None:
        """自动发现所有已实现的 DFTEngine 子类"""
        engines_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "engines"
        )
        if not os.path.isdir(engines_dir):
            return

        import importlib.util

        for fname in sorted(os.listdir(engines_dir)):
            if not fname.endswith("_engine.py") or fname.startswith("_"):
                continue
            if fname == "dft_engine.py":  # 跳过基类
                continue

            fpath = os.path.join(engines_dir, fname)
            mod_name = f"_dft_eng_{fname[:-3]}"
            try:
                spec = importlib.util.spec_from_file_location(mod_name, fpath)
                if spec is None or spec.loader is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                for attr_name in dir(mod):
                    obj = getattr(mod, attr_name)
                    if (isinstance(obj, type)
                            and issubclass(obj, DFTEngine)
                            and obj is not DFTEngine):
                        engine = obj()
                        cap = engine.get_capability()
                        self._engines[cap.engine_name] = engine
                        logger.info("DFT 引擎已加载: %s (%s)",
                                    cap.display_name, cap.engine_name)
            except Exception as e:
                logger.warning("加载 DFT 引擎 %s 失败: %s", fname, e)

    def _get_job_manager(self):
        """延迟初始化 HPCJobManager（避免无远程需求时的开销）"""
        if self._job_manager is None:
            try:
                from extensions.hpc_job_manager import HPCJobManager
                self._job_manager = HPCJobManager(engines=self._engines)
                logger.info("HPCJobManager 已初始化")
            except Exception as e:
                logger.warning("HPCJobManager 初始化失败: %s", e)
                return None
        return self._job_manager

    # ==================== CalculationPlugin 接口 ====================

    def get_metadata(self) -> PluginMetadata:
        engine_names = ", ".join(
            e.get_capability().display_name for e in self._engines.values()
        )
        return PluginMetadata(
            name="dft",
            display_name="DFT 第一性原理计算",
            version="0.2.0",
            description=f"统一 DFT 计算接口，支持多种后端引擎: {engine_names}。"
                        "通过 engine 参数选择 DFT 软件，支持输入生成、"
                        "任务提交、输出解析等全流程",
            author="AlloyThermolCal Pro",
            plugin_type=PluginType.HYBRID,
            dependencies=["paramiko"],  # 远程提交需要
            category="dft",
        )

    def check_availability(self) -> Dict[str, Any]:
        """DFT 适配器始终可用（只要有引擎就行）"""
        if not self._engines:
            return {
                "available": False,
                "missing_deps": [],
                "missing_programs": ["至少需要一个 DFT 引擎"],
            }
        return {
            "available": True,
            "missing_deps": [],
            "missing_programs": [],
        }

    def get_tools(self) -> List[ToolSchema]:
        engine_enum = list(self._engines.keys())
        if not engine_enum:
            engine_enum = ["vasp", "qe", "abinit", "cp2k", "gpaw"]

        return [
            # 1. 列出所有可用引擎
            ToolSchema(
                name="list_engines",
                description="列出所有可用的 DFT 计算引擎及其支持的任务类型",
                parameters={
                    "type": "object",
                    "properties": {},
                },
            ),

            # 2. 生成输入文件
            ToolSchema(
                name="generate_input",
                description="为指定 DFT 引擎生成输入文件。"
                            "返回文件内容，用户可直接复制到 HPC 上运行",
                parameters={
                    "type": "object",
                    "properties": {
                        "engine": {
                            "type": "string",
                            "description": "DFT 引擎名称",
                            "enum": engine_enum,
                        },
                        "task_type": {
                            "type": "string",
                            "description": "计算类型",
                            "enum": ["single_point", "optimize", "dos",
                                     "band", "phonon", "md"],
                        },
                        "composition": {
                            "type": "object",
                            "description": "合金成分 {元素: 原子数}",
                            "additionalProperties": {"type": "integer"},
                        },
                        "structure": {
                            "type": "string",
                            "description": "晶体结构类型",
                            "enum": ["fcc", "bcc", "hcp", "custom"],
                            "default": "fcc",
                        },
                        "lattice_constant": {
                            "type": "number",
                            "description": "晶格常数 (Å)",
                        },
                        "encut": {
                            "type": "number",
                            "description": "截断能 (eV)",
                            "default": 400,
                        },
                        "kpoints": {
                            "type": "string",
                            "description": "K 点网格，如 '6 6 6'",
                            "default": "6 6 6",
                        },
                        "xc_functional": {
                            "type": "string",
                            "description": "交换关联泛函",
                            "enum": ["PBE", "LDA", "PBEsol", "SCAN", "HSE06"],
                            "default": "PBE",
                        },
                        "extra_params": {
                            "type": "object",
                            "description": "引擎特有的额外参数",
                        },
                    },
                    "required": ["engine", "task_type", "composition"],
                },
            ),

            # 3. 解析输出文件
            ToolSchema(
                name="parse_output",
                description="解析 DFT 计算输出文件，提取能量、力、收敛性等结果",
                parameters={
                    "type": "object",
                    "properties": {
                        "engine": {
                            "type": "string",
                            "description": "DFT 引擎名称",
                            "enum": engine_enum,
                        },
                        "task_type": {
                            "type": "string",
                            "description": "计算类型",
                            "enum": ["single_point", "optimize", "dos", "band"],
                        },
                        "output_text": {
                            "type": "string",
                            "description": "输出文件内容（如 OUTCAR, pw.out 等）",
                        },
                        "output_filename": {
                            "type": "string",
                            "description": "输出文件名（用于自动识别格式）",
                            "default": "",
                        },
                    },
                    "required": ["engine", "task_type", "output_text"],
                },
            ),

            # 4. 估算计算时间
            ToolSchema(
                name="estimate_time",
                description="估算 DFT 计算大约需要多长时间",
                parameters={
                    "type": "object",
                    "properties": {
                        "engine": {
                            "type": "string",
                            "description": "DFT 引擎名称",
                            "enum": engine_enum,
                        },
                        "task_type": {
                            "type": "string",
                            "description": "计算类型",
                            "enum": ["single_point", "optimize", "dos",
                                     "band", "phonon", "md"],
                        },
                        "n_atoms": {
                            "type": "integer",
                            "description": "体系原子数",
                        },
                    },
                    "required": ["engine", "task_type", "n_atoms"],
                },
            ),

            # 5. 生成作业脚本
            ToolSchema(
                name="generate_submit_script",
                description="为指定 DFT 引擎生成 HPC 作业调度脚本（SLURM 或 PBS）",
                parameters={
                    "type": "object",
                    "properties": {
                        "engine": {
                            "type": "string",
                            "description": "DFT 引擎名称",
                            "enum": engine_enum,
                        },
                        "task_type": {
                            "type": "string",
                            "description": "计算类型",
                            "enum": ["single_point", "optimize", "dos",
                                     "band", "phonon", "md"],
                        },
                        "n_cores": {
                            "type": "integer",
                            "description": "并行核心数",
                            "default": 4,
                        },
                        "walltime": {
                            "type": "string",
                            "description": "最大运行时间",
                            "default": "24:00:00",
                        },
                        "job_name": {
                            "type": "string",
                            "description": "作业名称",
                            "default": "dft_job",
                        },
                        "queue": {
                            "type": "string",
                            "description": "队列/分区名称",
                            "default": "normal",
                        },
                        "scheduler": {
                            "type": "string",
                            "description": "调度器类型",
                            "enum": ["slurm", "pbs"],
                            "default": "slurm",
                        },
                    },
                    "required": ["engine", "task_type"],
                },
            ),

            # 6. 比较引擎
            ToolSchema(
                name="compare_engines",
                description="比较不同 DFT 引擎的特点、优劣和适用场景",
                parameters={
                    "type": "object",
                    "properties": {
                        "engines": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要比较的引擎名称列表",
                        },
                    },
                },
            ),

            # ========== 远程 HPC 工具 ==========

            # 7. 提交远程作业
            ToolSchema(
                name="submit_job",
                description="将 DFT 计算提交到远程 HPC 集群。"
                            "自动生成输入文件、上传、提交作业，返回任务ID用于跟踪",
                parameters={
                    "type": "object",
                    "properties": {
                        "engine": {
                            "type": "string",
                            "description": "DFT 引擎名称",
                            "enum": engine_enum,
                        },
                        "task_type": {
                            "type": "string",
                            "description": "计算类型",
                            "enum": ["single_point", "optimize", "dos",
                                     "band", "phonon", "md"],
                        },
                        "composition": {
                            "type": "object",
                            "description": "合金成分 {元素: 原子数}",
                            "additionalProperties": {"type": "integer"},
                        },
                        "structure": {
                            "type": "string",
                            "description": "晶体结构类型",
                            "enum": ["fcc", "bcc", "hcp"],
                            "default": "fcc",
                        },
                        "cluster": {
                            "type": "string",
                            "description": "目标 HPC 集群名称（留空使用默认集群）",
                        },
                        "encut": {
                            "type": "number",
                            "description": "截断能 (eV)",
                            "default": 400,
                        },
                        "kpoints": {
                            "type": "string",
                            "description": "K 点网格",
                            "default": "6 6 6",
                        },
                        "n_cores": {
                            "type": "integer",
                            "description": "并行核心数",
                        },
                        "walltime": {
                            "type": "string",
                            "description": "最长运行时间",
                        },
                        "queue": {
                            "type": "string",
                            "description": "队列名",
                        },
                    },
                    "required": ["engine", "task_type", "composition"],
                },
                is_async=True,
                timeout=86400,
            ),

            # 8. 查询作业状态
            ToolSchema(
                name="check_job",
                description="查询已提交的 DFT 作业的运行状态和进度",
                parameters={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "任务 ID（submit_job 返回的）",
                        },
                    },
                    "required": ["task_id"],
                },
            ),

            # 9. 获取计算结果
            ToolSchema(
                name="get_results",
                description="获取已完成的 DFT 计算结果。"
                            "自动从 HPC 下载输出文件并解析",
                parameters={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "任务 ID",
                        },
                        "force_download": {
                            "type": "boolean",
                            "description": "强制重新下载",
                            "default": False,
                        },
                    },
                    "required": ["task_id"],
                },
            ),

            # 10. 取消作业
            ToolSchema(
                name="cancel_job",
                description="取消正在运行或排队的 DFT 作业",
                parameters={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "任务 ID",
                        },
                    },
                    "required": ["task_id"],
                },
            ),

            # 11. 列出所有作业
            ToolSchema(
                name="list_jobs",
                description="列出所有已提交的 DFT 计算作业及其状态",
                parameters={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "按状态过滤",
                            "enum": ["pending", "running", "completed",
                                     "failed", "cancelled"],
                        },
                    },
                },
            ),

            # 12. 管理 HPC 集群配置
            ToolSchema(
                name="configure_hpc",
                description="配置 HPC 集群连接信息（主机、用户名、SSH密钥等）。"
                            "配置后即可向该集群提交 DFT 计算作业",
                parameters={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "操作类型",
                            "enum": ["list", "add", "remove", "test"],
                        },
                        "name": {
                            "type": "string",
                            "description": "集群配置名称（唯一标识）",
                        },
                        "host": {
                            "type": "string",
                            "description": "主机名或 IP 地址",
                        },
                        "username": {
                            "type": "string",
                            "description": "SSH 用户名",
                        },
                        "port": {
                            "type": "integer",
                            "description": "SSH 端口",
                            "default": 22,
                        },
                        "key_file": {
                            "type": "string",
                            "description": "SSH 私钥文件路径",
                            "default": "~/.ssh/id_rsa",
                        },
                        "work_dir": {
                            "type": "string",
                            "description": "远程工作目录",
                            "default": "~/dft_jobs",
                        },
                        "scheduler": {
                            "type": "string",
                            "description": "调度器类型",
                            "enum": ["slurm", "pbs"],
                            "default": "slurm",
                        },
                        "default_queue": {
                            "type": "string",
                            "description": "默认队列",
                            "default": "normal",
                        },
                        "default_cores": {
                            "type": "integer",
                            "description": "默认核心数",
                            "default": 4,
                        },
                        "module_loads": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "需要加载的 module（如 'intel/2023'）",
                        },
                    },
                    "required": ["action"],
                },
            ),
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """同步执行 DFT 工具"""
        # 本地工具
        local_dispatch = {
            "list_engines": self._list_engines,
            "generate_input": self._generate_input,
            "parse_output": self._parse_output,
            "estimate_time": self._estimate_time,
            "generate_submit_script": self._generate_submit_script,
            "compare_engines": self._compare_engines,
        }
        handler = local_dispatch.get(tool_name)
        if handler:
            try:
                return handler(**arguments)
            except Exception as e:
                return {"status": "error", "message": str(e)}

        # 远程 HPC 工具
        remote_dispatch = {
            "submit_job": self._submit_job,
            "check_job": self._check_job,
            "get_results": self._get_results,
            "cancel_job": self._cancel_job,
            "list_jobs": self._list_jobs,
            "configure_hpc": self._configure_hpc,
        }
        handler = remote_dispatch.get(tool_name)
        if handler:
            try:
                return handler(**arguments)
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "error", "message": f"未知工具: {tool_name}"}

    # ==================== 工具实现 ====================

    def _list_engines(self) -> Dict[str, Any]:
        """列出所有可用引擎"""
        engines_info = []
        for name, engine in self._engines.items():
            cap = engine.get_capability()
            engines_info.append({
                "name": cap.engine_name,
                "display_name": cap.display_name,
                "description": cap.description,
                "license": cap.license_type,
                "executable": cap.executable,
                "supported_tasks": [t.value for t in cap.supported_tasks],
                "python_bindings": cap.python_bindings,
                "website": cap.website,
            })
        return {
            "status": "success",
            "engine_count": len(engines_info),
            "engines": engines_info,
        }

    def _generate_input(self, engine: str, task_type: str,
                        composition: Dict[str, int],
                        structure: str = "fcc",
                        lattice_constant: float = None,
                        encut: float = 400,
                        kpoints: str = "6 6 6",
                        xc_functional: str = "PBE",
                        extra_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成 DFT 输入文件"""
        eng = self._engines.get(engine)
        if not eng:
            available = ", ".join(self._engines.keys())
            return {"status": "error",
                    "message": f"未知引擎: {engine}。可用引擎: {available}"}

        try:
            tt = DFTTaskType(task_type)
        except ValueError:
            return {"status": "error",
                    "message": f"未知任务类型: {task_type}。"
                               f"可选: {[t.value for t in DFTTaskType]}"}

        if not eng.supports(tt):
            cap = eng.get_capability()
            supported = [t.value for t in cap.supported_tasks]
            return {"status": "error",
                    "message": f"{cap.display_name} 不支持 {task_type}。"
                               f"支持的类型: {supported}"}

        # 构造结构
        struct = self._build_structure(composition, structure, lattice_constant)

        # 合并参数
        params = {
            "encut": encut,
            "kpoints": kpoints,
            "xc_functional": xc_functional,
        }
        if extra_params:
            params.update(extra_params)

        # 调用引擎生成输入
        input_files = eng.generate_input(tt, struct, params)

        return {
            "status": "success",
            "engine": engine,
            "engine_display_name": eng.get_capability().display_name,
            "task_type": task_type,
            "files": input_files.files,
            "work_dir": input_files.work_dir_name,
            "notes": input_files.notes,
            "file_count": len(input_files.files),
        }

    def _parse_output(self, engine: str, task_type: str,
                      output_text: str,
                      output_filename: str = "") -> Dict[str, Any]:
        """解析 DFT 输出"""
        eng = self._engines.get(engine)
        if not eng:
            return {"status": "error", "message": f"未知引擎: {engine}"}

        try:
            tt = DFTTaskType(task_type)
        except ValueError:
            return {"status": "error", "message": f"未知任务类型: {task_type}"}

        # 猜测文件名
        if not output_filename:
            default_names = {
                "vasp": "OUTCAR",
                "qe": "pw.out",
                "abinit": "output.abo",
                "cp2k": "output.out",
                "gpaw": "gpaw.txt",
            }
            output_filename = default_names.get(engine, "output")

        result = eng.parse_output(tt, {output_filename: output_text})

        return {
            "status": "success",
            "engine": engine,
            "task_type": task_type,
            **result.to_dict(),
        }

    def _estimate_time(self, engine: str, task_type: str,
                       n_atoms: int) -> Dict[str, Any]:
        """估算计算时间"""
        eng = self._engines.get(engine)
        if not eng:
            return {"status": "error", "message": f"未知引擎: {engine}"}

        try:
            tt = DFTTaskType(task_type)
        except ValueError:
            return {"status": "error", "message": f"未知任务类型: {task_type}"}

        est = eng.estimate_time(tt, n_atoms, {})
        seconds = est["estimated_seconds"]
        if seconds < 60:
            time_str = f"{seconds} 秒"
        elif seconds < 3600:
            time_str = f"{seconds // 60} 分钟"
        else:
            time_str = f"{seconds / 3600:.1f} 小时"

        return {
            "status": "success",
            "engine": engine,
            "task_type": task_type,
            "n_atoms": n_atoms,
            "estimated_time": time_str,
            "estimated_seconds": seconds,
            "confidence": est["confidence"],
        }

    def _generate_submit_script(self, engine: str, task_type: str,
                                n_cores: int = 4,
                                walltime: str = "24:00:00",
                                job_name: str = "dft_job",
                                queue: str = "normal",
                                scheduler: str = "slurm") -> Dict[str, Any]:
        """生成作业脚本"""
        eng = self._engines.get(engine)
        if not eng:
            return {"status": "error", "message": f"未知引擎: {engine}"}

        try:
            tt = DFTTaskType(task_type)
        except ValueError:
            return {"status": "error", "message": f"未知任务类型: {task_type}"}

        run_cmd = eng.get_run_command(tt, n_cores)
        script = eng.get_submit_script(
            tt, run_cmd, job_name, n_cores, walltime, queue, scheduler
        )

        return {
            "status": "success",
            "engine": engine,
            "scheduler": scheduler,
            "run_command": run_cmd,
            "script": script,
        }

    def _compare_engines(self, engines: List[str] = None) -> Dict[str, Any]:
        """比较 DFT 引擎"""
        if not engines:
            engines = list(self._engines.keys())

        comparison = []
        for name in engines:
            eng = self._engines.get(name)
            if not eng:
                continue
            cap = eng.get_capability()
            comparison.append({
                "name": cap.engine_name,
                "display_name": cap.display_name,
                "license": cap.license_type,
                "tasks": [t.value for t in cap.supported_tasks],
                "python_api": cap.python_bindings,
                "parallel": cap.parallel_support,
                "description": cap.description,
            })

        return {
            "status": "success",
            "comparison": comparison,
        }

    # ==================== 远程 HPC 工具实现 ====================

    def _submit_job(self, engine: str, task_type: str,
                    composition: Dict[str, int],
                    structure: str = "fcc",
                    cluster: str = None,
                    encut: float = 400,
                    kpoints: str = "6 6 6",
                    n_cores: int = None,
                    walltime: str = None,
                    queue: str = None,
                    **extra) -> Dict[str, Any]:
        """提交 DFT 计算到远程 HPC"""
        mgr = self._get_job_manager()
        if not mgr:
            return {"status": "error",
                    "message": "HPCJobManager 未就绪，请检查 extensions 模块"}

        struct = self._build_structure(composition, structure)
        params = {"encut": encut, "kpoints": kpoints}
        params.update(extra)

        return mgr.submit_job(
            engine_name=engine,
            task_type=task_type,
            structure=struct,
            params=params,
            cluster_name=cluster,
            n_cores=n_cores,
            walltime=walltime,
            queue=queue,
        )

    def _check_job(self, task_id: str) -> Dict[str, Any]:
        """查询作业状态"""
        mgr = self._get_job_manager()
        if not mgr:
            return {"status": "error", "message": "HPCJobManager 未就绪"}
        return mgr.check_job(task_id)

    def _get_results(self, task_id: str,
                     force_download: bool = False) -> Dict[str, Any]:
        """获取计算结果"""
        mgr = self._get_job_manager()
        if not mgr:
            return {"status": "error", "message": "HPCJobManager 未就绪"}
        return mgr.get_results(task_id, force_download)

    def _cancel_job(self, task_id: str) -> Dict[str, Any]:
        """取消作业"""
        mgr = self._get_job_manager()
        if not mgr:
            return {"status": "error", "message": "HPCJobManager 未就绪"}
        return mgr.cancel_job(task_id)

    def _list_jobs(self, status: str = None) -> Dict[str, Any]:
        """列出所有作业"""
        mgr = self._get_job_manager()
        if not mgr:
            return {"status": "error", "message": "HPCJobManager 未就绪"}
        jobs = mgr.list_jobs(status)
        return {
            "status": "success",
            "job_count": len(jobs),
            "jobs": jobs,
        }

    def _configure_hpc(self, action: str,
                       name: str = None,
                       host: str = None,
                       username: str = None,
                       port: int = 22,
                       key_file: str = "~/.ssh/id_rsa",
                       work_dir: str = "~/dft_jobs",
                       scheduler: str = "slurm",
                       default_queue: str = "normal",
                       default_cores: int = 4,
                       module_loads: List[str] = None,
                       **extra) -> Dict[str, Any]:
        """管理 HPC 集群配置"""
        mgr = self._get_job_manager()
        if not mgr:
            return {"status": "error", "message": "HPCJobManager 未就绪"}

        hpc = mgr.hpc

        if action == "list":
            profiles = hpc.list_profiles()
            default = hpc.get_default_cluster()
            if not profiles:
                return {
                    "status": "success",
                    "message": "尚未配置任何 HPC 集群。"
                               "使用 configure_hpc(action='add', name='...', "
                               "host='...', username='...') 添加配置",
                    "clusters": [],
                    "default_cluster": None,
                }
            return {
                "status": "success",
                "cluster_count": len(profiles),
                "clusters": profiles,
                "default_cluster": default,
            }

        elif action == "add":
            if not name or not host or not username:
                return {"status": "error",
                        "message": "添加集群需要: name（配置名）, host（主机名）, "
                                   "username（用户名）"}

            from extensions.hpc_connection import HPCProfile
            profile = HPCProfile(
                name=name,
                host=host,
                port=port,
                username=username,
                key_file=key_file,
                work_dir=work_dir,
                scheduler=scheduler,
                default_queue=default_queue,
                default_cores=default_cores,
                module_loads=module_loads or [],
            )
            hpc.add_profile(profile)
            return {
                "status": "success",
                "message": f"已添加集群配置: {name} ({username}@{host})",
                "profile": {
                    "name": name, "host": host, "username": username,
                    "scheduler": scheduler, "work_dir": work_dir,
                },
            }

        elif action == "remove":
            if not name:
                return {"status": "error", "message": "请指定要删除的集群名称"}
            if hpc.remove_profile(name):
                return {"status": "success",
                        "message": f"已删除集群配置: {name}"}
            return {"status": "error",
                    "message": f"未找到集群配置: {name}"}

        elif action == "test":
            if not name:
                return {"status": "error", "message": "请指定要测试的集群名称"}
            conn_result = hpc.connect(name)
            if conn_result["status"] != "success":
                return conn_result

            # 测试远程命令
            cmd_result = hpc.exec_command(name, "hostname && whoami && pwd")
            hpc.disconnect(name)

            return {
                "status": "success",
                "message": f"连接测试成功",
                "connection": conn_result["message"],
                "remote_info": cmd_result.get("stdout", "").strip(),
            }

        return {"status": "error", "message": f"未知操作: {action}"}

    # ==================== 辅助方法 ====================

    def _build_structure(self, composition: Dict[str, int],
                         structure_type: str = "fcc",
                         lattice_constant: float = None) -> Dict[str, Any]:
        """
        从成分描述构造原子结构。

        参数:
            composition: {元素: 原子数}，如 {"Fe": 3, "C": 1}
            structure_type: 晶体结构类型
            lattice_constant: 晶格常数 (Å)
        """
        # 默认晶格常数（来自实验值的近似）
        default_a = {
            "Fe": 2.87, "Al": 4.05, "Cu": 3.61, "Ni": 3.52,
            "Au": 4.08, "Ag": 4.09, "Pt": 3.92, "Pd": 3.89,
            "Ti": 2.95, "Cr": 2.91, "V": 3.02, "Mo": 3.15,
            "W": 3.16, "Co": 2.51, "Mn": 8.91,
        }

        elements = []
        for elem, count in composition.items():
            elements.extend([elem] * count)

        # 用主元素的晶格常数
        main_elem = max(composition, key=composition.get)
        a = lattice_constant or default_a.get(main_elem, 3.5)

        if structure_type == "fcc":
            # 常规 FCC 单胞（4 原子位置）
            base_positions = [
                [0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]
            ]
            cell = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        elif structure_type == "bcc":
            base_positions = [[0, 0, 0], [0.5, 0.5, 0.5]]
            cell = [[a, 0, 0], [0, a, 0], [0, 0, a]]
        elif structure_type == "hcp":
            c = a * 1.633
            base_positions = [
                [0, 0, 0],
                [1/3, 2/3, 0.5],
            ]
            cell = [
                [a, 0, 0],
                [-a / 2, a * 0.866, 0],
                [0, 0, c],
            ]
        else:
            # custom: 简单立方
            base_positions = [[0, 0, 0]]
            cell = [[a, 0, 0], [0, a, 0], [0, 0, a]]

        # 将分数坐标转为笛卡尔坐标
        n_total = len(elements)
        n_base = len(base_positions)

        # 如果原子数 > 基本位置数，需要扩胞
        positions = []
        if n_total <= n_base:
            for i in range(n_total):
                frac = base_positions[i]
                cart = [
                    frac[0] * cell[0][0] + frac[1] * cell[1][0] + frac[2] * cell[2][0],
                    frac[0] * cell[0][1] + frac[1] * cell[1][1] + frac[2] * cell[2][1],
                    frac[0] * cell[0][2] + frac[1] * cell[1][2] + frac[2] * cell[2][2],
                ]
                positions.append(cart)
        else:
            # 简易扩胞
            import math
            repeat = max(2, math.ceil((n_total / n_base) ** (1/3)))
            for ix in range(repeat):
                for iy in range(repeat):
                    for iz in range(repeat):
                        for frac in base_positions:
                            if len(positions) >= n_total:
                                break
                            cart = [
                                (frac[0] + ix) * cell[0][0] / repeat + (frac[1] + iy) * cell[1][0] / repeat + (frac[2] + iz) * cell[2][0] / repeat,
                                (frac[0] + ix) * cell[0][1] / repeat + (frac[1] + iy) * cell[1][1] / repeat + (frac[2] + iz) * cell[2][1] / repeat,
                                (frac[0] + ix) * cell[0][2] / repeat + (frac[1] + iy) * cell[1][2] / repeat + (frac[2] + iz) * cell[2][2] / repeat,
                            ]
                            positions.append(cart)
                        if len(positions) >= n_total:
                            break
                    if len(positions) >= n_total:
                        break
                if len(positions) >= n_total:
                    break
            positions = positions[:n_total]

        return {
            "elements": elements,
            "positions": positions,
            "cell": cell,
            "pbc": True,
        }
