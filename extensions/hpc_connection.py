# -*- coding: utf-8 -*-
"""
HPCConnection - HPC 远程连接管理器
=====================================
通过 SSH/SFTP 管理与远程 HPC 集群的连接。
支持多集群配置、连接复用、SSH 密钥认证、跳板机。

配置存储: ~/.alloyact/hpc_profiles.json

典型配置:
{
    "clusters": {
        "my_hpc": {
            "host": "login.hpc.example.edu",
            "port": 22,
            "username": "user01",
            "auth_method": "key",
            "key_file": "~/.ssh/id_rsa",
            "work_dir": "/home/user01/dft_jobs",
            "scheduler": "slurm",
            "default_queue": "normal",
            "default_cores": 24,
            "module_loads": ["intel/2023", "vasp/6.3"],
            "jump_host": null
        }
    },
    "default_cluster": "my_hpc"
}
"""

import json
import logging
import os
import posixpath
import time
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# 配置文件路径
_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".alloyact")
_PROFILES_FILE = os.path.join(_CONFIG_DIR, "hpc_profiles.json")


@dataclass
class HPCProfile:
    """HPC 集群连接配置"""
    name: str                              # 配置名称（唯一标识）
    host: str                              # 主机名或 IP
    port: int = 22                         # SSH 端口
    username: str = ""                     # 用户名
    auth_method: str = "key"               # 认证方式: "key" / "password" / "agent"
    key_file: str = "~/.ssh/id_rsa"        # SSH 私钥路径
    password: str = ""                     # 密码（不推荐，建议用密钥）
    work_dir: str = "~/dft_jobs"           # 远程工作目录
    scheduler: str = "slurm"              # 调度器: "slurm" / "pbs"
    default_queue: str = "normal"          # 默认队列
    default_cores: int = 4                 # 默认核心数
    default_walltime: str = "24:00:00"     # 默认运行时间
    module_loads: List[str] = field(default_factory=list)  # module load 命令
    jump_host: Optional[str] = None        # 跳板机（格式: user@host:port）
    env_vars: Dict[str, str] = field(default_factory=dict)  # 环境变量


class HPCConnection:
    """
    HPC 远程连接管理器。

    管理 SSH/SFTP 连接的生命周期，提供:
    - 连接建立与复用（带自动重连）
    - 文件上传/下载 (SFTP)
    - 远程命令执行
    - 多集群配置管理
    """

    def __init__(self):
        self._profiles: Dict[str, HPCProfile] = {}
        self._connections: Dict[str, Any] = {}  # name → paramiko.SSHClient
        self._lock = threading.Lock()
        self._load_profiles()

    # ==================== 配置管理 ====================

    def _load_profiles(self) -> None:
        """从配置文件加载集群配置"""
        if not os.path.isfile(_PROFILES_FILE):
            return
        try:
            with open(_PROFILES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, cfg in data.get("clusters", {}).items():
                cfg["name"] = name
                self._profiles[name] = HPCProfile(**cfg)
            logger.info("已加载 %d 个 HPC 集群配置", len(self._profiles))
        except Exception as e:
            logger.warning("加载 HPC 配置失败: %s", e)

    def _save_profiles(self) -> None:
        """保存集群配置到文件"""
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        data = {
            "clusters": {},
            "default_cluster": self.get_default_cluster(),
        }
        for name, profile in self._profiles.items():
            d = asdict(profile)
            d.pop("name", None)
            # 不保存密码到文件
            if d.get("auth_method") != "password":
                d.pop("password", None)
            data["clusters"][name] = d

        with open(_PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("HPC 配置已保存到 %s", _PROFILES_FILE)

    def add_profile(self, profile: HPCProfile) -> None:
        """添加或更新集群配置"""
        self._profiles[profile.name] = profile
        self._save_profiles()

    def remove_profile(self, name: str) -> bool:
        """删除集群配置"""
        if name in self._profiles:
            self.disconnect(name)
            del self._profiles[name]
            self._save_profiles()
            return True
        return False

    def get_profile(self, name: str) -> Optional[HPCProfile]:
        """获取集群配置"""
        return self._profiles.get(name)

    def list_profiles(self) -> List[Dict[str, Any]]:
        """列出所有集群配置"""
        result = []
        for name, p in self._profiles.items():
            connected = name in self._connections
            result.append({
                "name": p.name,
                "host": p.host,
                "username": p.username,
                "scheduler": p.scheduler,
                "work_dir": p.work_dir,
                "default_queue": p.default_queue,
                "default_cores": p.default_cores,
                "connected": connected,
            })
        return result

    def get_default_cluster(self) -> Optional[str]:
        """获取默认集群名"""
        if not self._profiles:
            return None
        try:
            with open(_PROFILES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("default_cluster")
        except Exception:
            return next(iter(self._profiles), None)

    # ==================== SSH 连接 ====================

    def connect(self, cluster_name: str) -> Dict[str, Any]:
        """
        建立到指定集群的 SSH 连接。

        参数:
            cluster_name: 集群配置名称

        返回:
            {"status": "success"/"error", "message": str}
        """
        profile = self._profiles.get(cluster_name)
        if not profile:
            return {"status": "error",
                    "message": f"未找到集群配置: {cluster_name}。"
                               f"可用: {list(self._profiles.keys())}"}

        # 已连接则复用
        if cluster_name in self._connections:
            client = self._connections[cluster_name]
            if self._is_alive(client):
                return {"status": "success",
                        "message": f"已连接到 {profile.host}（复用现有连接）"}
            else:
                self.disconnect(cluster_name)

        try:
            import paramiko

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": profile.host,
                "port": profile.port,
                "username": profile.username,
                "timeout": 30,
            }

            if profile.auth_method == "key":
                key_path = os.path.expanduser(profile.key_file)
                if os.path.isfile(key_path):
                    connect_kwargs["key_filename"] = key_path
                else:
                    return {"status": "error",
                            "message": f"SSH 密钥文件不存在: {key_path}"}
            elif profile.auth_method == "password":
                connect_kwargs["password"] = profile.password
            # auth_method == "agent" 不需要额外参数

            # 跳板机支持
            if profile.jump_host:
                sock = self._create_jump_channel(profile.jump_host)
                if sock:
                    connect_kwargs["sock"] = sock

            client.connect(**connect_kwargs)

            with self._lock:
                self._connections[cluster_name] = client

            # 确保远程工作目录存在
            work_dir = self._expand_remote_path(profile.work_dir, profile)
            self._exec_remote(cluster_name, f"mkdir -p {work_dir}")

            return {"status": "success",
                    "message": f"已连接到 {profile.username}@{profile.host}"}

        except ImportError:
            return {"status": "error",
                    "message": "需要安装 paramiko: pip install paramiko"}
        except Exception as e:
            return {"status": "error",
                    "message": f"SSH 连接失败: {e}"}

    def disconnect(self, cluster_name: str) -> None:
        """断开连接"""
        with self._lock:
            client = self._connections.pop(cluster_name, None)
        if client:
            try:
                client.close()
            except Exception:
                pass

    def disconnect_all(self) -> None:
        """断开所有连接"""
        names = list(self._connections.keys())
        for name in names:
            self.disconnect(name)

    def _is_alive(self, client) -> bool:
        """检查连接是否存活"""
        try:
            transport = client.get_transport()
            if transport is None or not transport.is_active():
                return False
            transport.send_ignore()
            return True
        except Exception:
            return False

    def _ensure_connected(self, cluster_name: str) -> Dict[str, Any]:
        """确保已连接，否则自动连接"""
        if cluster_name in self._connections:
            client = self._connections[cluster_name]
            if self._is_alive(client):
                return {"status": "success"}
            self.disconnect(cluster_name)
        return self.connect(cluster_name)

    def _create_jump_channel(self, jump_host_str: str):
        """创建跳板机通道"""
        try:
            import paramiko

            parts = jump_host_str.split("@")
            if len(parts) == 2:
                j_user = parts[0]
                host_port = parts[1]
            else:
                j_user = os.environ.get("USER", "")
                host_port = parts[0]

            hp = host_port.split(":")
            j_host = hp[0]
            j_port = int(hp[1]) if len(hp) > 1 else 22

            jump_client = paramiko.SSHClient()
            jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            jump_client.connect(j_host, port=j_port, username=j_user, timeout=30)

            transport = jump_client.get_transport()
            dest = (self._profiles.get(jump_host_str, HPCProfile(name="")).host, 22)
            local = ("127.0.0.1", 0)
            return transport.open_channel("direct-tcpip", dest, local)
        except Exception as e:
            logger.warning("跳板机连接失败: %s", e)
            return None

    # ==================== 远程命令执行 ====================

    def _exec_remote(self, cluster_name: str,
                     command: str,
                     timeout: int = 60) -> Tuple[int, str, str]:
        """
        执行远程命令。

        返回:
            (exit_code, stdout, stderr)
        """
        conn_result = self._ensure_connected(cluster_name)
        if conn_result["status"] != "success":
            raise ConnectionError(conn_result["message"])

        client = self._connections[cluster_name]
        profile = self._profiles[cluster_name]

        # 前置 module load 和环境变量
        prefix_cmds = []
        for mod in profile.module_loads:
            prefix_cmds.append(f"module load {mod}")
        for k, v in profile.env_vars.items():
            prefix_cmds.append(f"export {k}={v}")

        if prefix_cmds:
            full_cmd = " && ".join(prefix_cmds) + " && " + command
        else:
            full_cmd = command

        stdin, stdout, stderr = client.exec_command(full_cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return exit_code, out, err

    def exec_command(self, cluster_name: str, command: str,
                     timeout: int = 60) -> Dict[str, Any]:
        """
        执行远程命令（公开接口）。

        返回:
            {"status": "success"/"error", "exit_code": int,
             "stdout": str, "stderr": str}
        """
        try:
            code, out, err = self._exec_remote(cluster_name, command, timeout)
            return {
                "status": "success" if code == 0 else "error",
                "exit_code": code,
                "stdout": out,
                "stderr": err,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ==================== 文件传输 ====================

    def upload_files(self, cluster_name: str,
                     files: Dict[str, str],
                     remote_dir: str) -> Dict[str, Any]:
        """
        上传多个文件到远程目录。

        参数:
            cluster_name: 集群名
            files: {文件名: 文件内容} 字典
            remote_dir: 远程目标目录（绝对路径）

        返回:
            {"status": "success"/"error", "uploaded": [文件名列表]}
        """
        conn_result = self._ensure_connected(cluster_name)
        if conn_result["status"] != "success":
            return conn_result

        client = self._connections[cluster_name]

        try:
            sftp = client.open_sftp()

            # 确保远程目录存在
            self._sftp_makedirs(sftp, remote_dir)

            uploaded = []
            for filename, content in files.items():
                remote_path = posixpath.join(remote_dir, filename)
                # 确保父目录存在
                parent = posixpath.dirname(remote_path)
                if parent != remote_dir:
                    self._sftp_makedirs(sftp, parent)

                with sftp.open(remote_path, "w") as f:
                    f.write(content)
                uploaded.append(filename)

            sftp.close()
            return {
                "status": "success",
                "uploaded": uploaded,
                "remote_dir": remote_dir,
            }
        except Exception as e:
            return {"status": "error", "message": f"文件上传失败: {e}"}

    def download_file(self, cluster_name: str,
                      remote_path: str) -> Dict[str, Any]:
        """
        下载远程文件内容。

        返回:
            {"status": "success"/"error", "content": str, "filename": str}
        """
        conn_result = self._ensure_connected(cluster_name)
        if conn_result["status"] != "success":
            return conn_result

        client = self._connections[cluster_name]

        try:
            sftp = client.open_sftp()
            with sftp.open(remote_path, "r") as f:
                content = f.read().decode("utf-8", errors="replace")
            sftp.close()
            return {
                "status": "success",
                "content": content,
                "filename": posixpath.basename(remote_path),
            }
        except FileNotFoundError:
            return {"status": "error",
                    "message": f"远程文件不存在: {remote_path}"}
        except Exception as e:
            return {"status": "error", "message": f"文件下载失败: {e}"}

    def download_files(self, cluster_name: str,
                       remote_dir: str,
                       filenames: List[str]) -> Dict[str, str]:
        """
        批量下载文件。

        返回:
            {文件名: 文件内容} 字典（下载失败的文件不包含在内）
        """
        results = {}
        for fname in filenames:
            remote_path = posixpath.join(remote_dir, fname)
            r = self.download_file(cluster_name, remote_path)
            if r["status"] == "success":
                results[fname] = r["content"]
        return results

    def _sftp_makedirs(self, sftp, remote_dir: str) -> None:
        """递归创建远程目录"""
        parts = remote_dir.split("/")
        current = ""
        for part in parts:
            if not part:
                current = "/"
                continue
            current = posixpath.join(current, part) if current else f"/{part}"
            try:
                sftp.stat(current)
            except FileNotFoundError:
                try:
                    sftp.mkdir(current)
                except Exception:
                    pass

    # ==================== 作业调度 ====================

    def submit_job(self, cluster_name: str,
                   remote_dir: str,
                   script_content: str,
                   script_name: str = "submit.sh") -> Dict[str, Any]:
        """
        提交作业到调度器。

        参数:
            cluster_name: 集群名
            remote_dir: 作业工作目录
            script_content: 提交脚本内容
            script_name: 脚本文件名

        返回:
            {"status": "success"/"error", "job_id": str}
        """
        # 上传脚本
        upload_result = self.upload_files(
            cluster_name, {script_name: script_content}, remote_dir
        )
        if upload_result["status"] != "success":
            return upload_result

        profile = self._profiles[cluster_name]
        script_path = posixpath.join(remote_dir, script_name)

        if profile.scheduler == "slurm":
            submit_cmd = f"cd {remote_dir} && sbatch {script_path}"
        elif profile.scheduler == "pbs":
            submit_cmd = f"cd {remote_dir} && qsub {script_path}"
        else:
            return {"status": "error",
                    "message": f"不支持的调度器: {profile.scheduler}"}

        try:
            code, out, err = self._exec_remote(cluster_name, submit_cmd)
            if code != 0:
                return {"status": "error",
                        "message": f"提交作业失败: {err.strip() or out.strip()}"}

            # 解析 job_id
            job_id = self._parse_job_id(out, profile.scheduler)
            return {
                "status": "success",
                "job_id": job_id,
                "message": f"作业已提交到 {profile.host}",
            }
        except Exception as e:
            return {"status": "error", "message": f"提交作业失败: {e}"}

    def check_job(self, cluster_name: str,
                  job_id: str) -> Dict[str, Any]:
        """
        查询作业状态。

        返回:
            {"status": "success", "job_status": "pending"/"running"/"completed"/"failed",
             "job_id": str, ...}
        """
        profile = self._profiles.get(cluster_name)
        if not profile:
            return {"status": "error", "message": f"未找到集群: {cluster_name}"}

        try:
            if profile.scheduler == "slurm":
                code, out, err = self._exec_remote(
                    cluster_name,
                    f"squeue -j {job_id} -h -o '%T %M %l' 2>/dev/null; "
                    f"sacct -j {job_id} --format=State,ExitCode -n -P 2>/dev/null"
                )
            else:  # PBS
                code, out, err = self._exec_remote(
                    cluster_name,
                    f"qstat -f {job_id} 2>/dev/null"
                )

            job_status = self._parse_job_status(out, err, profile.scheduler)
            return {
                "status": "success",
                "job_id": job_id,
                "job_status": job_status,
                "raw_output": out.strip()[:500],
            }
        except Exception as e:
            return {"status": "error", "message": f"查询作业失败: {e}"}

    def cancel_job(self, cluster_name: str,
                   job_id: str) -> Dict[str, Any]:
        """取消远程作业"""
        profile = self._profiles.get(cluster_name)
        if not profile:
            return {"status": "error", "message": f"未找到集群: {cluster_name}"}

        try:
            if profile.scheduler == "slurm":
                cmd = f"scancel {job_id}"
            else:
                cmd = f"qdel {job_id}"

            code, out, err = self._exec_remote(cluster_name, cmd)
            if code == 0:
                return {"status": "success",
                        "message": f"作业 {job_id} 已取消"}
            return {"status": "error",
                    "message": f"取消失败: {err.strip() or out.strip()}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ==================== 解析辅助 ====================

    def _parse_job_id(self, submit_output: str, scheduler: str) -> str:
        """从提交输出中解析 job ID"""
        output = submit_output.strip()
        if scheduler == "slurm":
            # "Submitted batch job 123456"
            for part in output.split():
                if part.isdigit():
                    return part
            return output.split()[-1] if output else "unknown"
        else:  # PBS
            # "123456.pbs_server"
            return output.split(".")[0] if output else "unknown"

    def _parse_job_status(self, stdout: str, stderr: str,
                          scheduler: str) -> str:
        """解析作业状态"""
        out = stdout.strip()
        if not out:
            return "completed"  # 已不在队列中，可能已完成

        if scheduler == "slurm":
            # squeue 输出: PENDING/RUNNING/COMPLETING
            # sacct 输出: COMPLETED/FAILED/CANCELLED/TIMEOUT
            out_upper = out.upper()
            if "RUNNING" in out_upper:
                return "running"
            if "PENDING" in out_upper:
                return "pending"
            if "COMPLETING" in out_upper:
                return "running"
            if "COMPLETED" in out_upper:
                return "completed"
            if "FAILED" in out_upper or "TIMEOUT" in out_upper:
                return "failed"
            if "CANCELLED" in out_upper:
                return "cancelled"
            return "completed"
        else:  # PBS
            out_upper = out.upper()
            if "job_state = R" in out or "RUNNING" in out_upper:
                return "running"
            if "job_state = Q" in out or "QUEUED" in out_upper:
                return "pending"
            if "job_state = C" in out:
                return "completed"
            return "completed"

    def _expand_remote_path(self, path: str, profile: HPCProfile) -> str:
        """展开远程路径中的 ~"""
        if path.startswith("~"):
            return path.replace("~", f"/home/{profile.username}", 1)
        return path
