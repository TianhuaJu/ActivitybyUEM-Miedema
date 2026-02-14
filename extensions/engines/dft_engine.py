# -*- coding: utf-8 -*-
"""
DFTEngine 抽象基类
===================
所有 DFT 软件后端（VASP、Quantum ESPRESSO、ABINIT、CP2K、GPAW 等）
的统一接口。每个引擎只需关注：
  1. 输入文件怎么生成
  2. 输出文件怎么解析
  3. 用什么命令执行

DFTAdapter 负责调度、提交、轮询等通用逻辑。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional


class DFTTaskType(Enum):
    """DFT 计算任务类型"""
    SINGLE_POINT = "single_point"       # 单点能量
    OPTIMIZE = "optimize"               # 结构优化
    DOS = "dos"                         # 态密度
    BAND = "band"                       # 能带结构
    PHONON = "phonon"                   # 声子计算
    MD = "md"                           # 从头算分子动力学 (AIMD)
    NEB = "neb"                         # 过渡态搜索


@dataclass
class EngineCapability:
    """引擎能力描述"""
    engine_name: str                    # 引擎标识 (snake_case)
    display_name: str                   # 显示名称
    version: str                        # 版本号
    description: str                    # 中文描述
    supported_tasks: List[DFTTaskType]  # 支持的任务类型
    executable: str                     # 可执行命令 (如 "vasp_std", "pw.x")
    license_type: str = "open-source"   # 许可证类型
    website: str = ""                   # 官网
    file_format: str = ""               # 输入文件格式说明
    parallel_support: bool = True       # 是否支持 MPI 并行
    python_bindings: bool = False       # 是否有 Python 绑定（本地执行）


@dataclass
class InputFiles:
    """DFT 计算输入文件集合"""
    files: Dict[str, str]              # {文件名: 文件内容}
    work_dir_name: str = ""            # 建议的工作目录名
    notes: str = ""                    # 额外说明


@dataclass
class ParsedResult:
    """DFT 计算结果的统一格式"""
    total_energy_eV: Optional[float] = None
    energy_per_atom_eV: Optional[float] = None
    forces_eV_A: Optional[List[List[float]]] = None
    stress_GPa: Optional[List[float]] = None
    max_force_eV_A: Optional[float] = None
    converged: Optional[bool] = None
    n_iterations: Optional[int] = None
    band_gap_eV: Optional[float] = None
    magnetic_moment: Optional[float] = None
    lattice_vectors: Optional[List[List[float]]] = None
    positions: Optional[List[Dict[str, Any]]] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转为字典，去除 None 字段"""
        d = {}
        for k, v in self.__dict__.items():
            if v is not None and k != "extra":
                d[k] = v
        if self.extra:
            d.update(self.extra)
        return d


class DFTEngine(ABC):
    """
    DFT 计算引擎抽象基类。

    每种 DFT 软件实现一个子类，只需实现以下方法:
      - get_capability():  声明引擎能力
      - generate_input():  根据任务类型和参数生成输入文件
      - parse_output():    解析输出文件为统一格式
      - get_run_command(): 返回执行命令

    可选实现:
      - validate_params(): 校验参数合法性
      - estimate_time():   估算计算时间
      - get_submit_script(): 生成作业调度脚本
    """

    @abstractmethod
    def get_capability(self) -> EngineCapability:
        """返回引擎能力描述"""
        ...

    @abstractmethod
    def generate_input(self, task_type: DFTTaskType,
                       structure: Dict[str, Any],
                       params: Dict[str, Any]) -> InputFiles:
        """
        生成 DFT 计算输入文件。

        参数:
            task_type: 计算任务类型
            structure: 结构描述 {"elements": [...], "positions": [...],
                       "cell": [...], "pbc": bool}
            params: 计算参数 {"encut": 400, "kpoints": "6 6 6", ...}

        返回:
            InputFiles: 包含所有输入文件内容的对象
        """
        ...

    @abstractmethod
    def parse_output(self, task_type: DFTTaskType,
                     output_files: Dict[str, str]) -> ParsedResult:
        """
        解析 DFT 计算输出文件。

        参数:
            task_type: 计算任务类型
            output_files: {文件名: 文件内容} 的字典

        返回:
            ParsedResult: 统一格式的计算结果
        """
        ...

    @abstractmethod
    def get_run_command(self, task_type: DFTTaskType,
                       n_cores: int = 1) -> str:
        """
        返回执行命令。

        参数:
            task_type: 计算任务类型
            n_cores: 并行核心数

        返回:
            命令字符串，如 "mpirun -np 4 vasp_std"
        """
        ...

    def validate_params(self, task_type: DFTTaskType,
                        params: Dict[str, Any]) -> Dict[str, Any]:
        """
        校验并补全计算参数（可选）。

        返回:
            {"valid": bool, "params": {补全后的参数}, "warnings": [...]}
        """
        return {"valid": True, "params": params, "warnings": []}

    def estimate_time(self, task_type: DFTTaskType,
                      n_atoms: int,
                      params: Dict[str, Any]) -> Dict[str, Any]:
        """
        估算计算时间（可选）。

        返回:
            {"estimated_seconds": int, "confidence": "low"/"medium"/"high"}
        """
        return {"estimated_seconds": 3600, "confidence": "low"}

    def get_submit_script(self, task_type: DFTTaskType,
                          run_command: str,
                          job_name: str = "dft_job",
                          n_cores: int = 4,
                          walltime: str = "24:00:00",
                          queue: str = "normal",
                          scheduler: str = "slurm") -> str:
        """
        生成作业调度脚本（可选，默认生成 SLURM 脚本）。

        参数:
            scheduler: "slurm" 或 "pbs"
        """
        if scheduler == "slurm":
            return (
                f"#!/bin/bash\n"
                f"#SBATCH --job-name={job_name}\n"
                f"#SBATCH --ntasks={n_cores}\n"
                f"#SBATCH --time={walltime}\n"
                f"#SBATCH --partition={queue}\n"
                f"#SBATCH --output=%j.out\n"
                f"#SBATCH --error=%j.err\n\n"
                f"{run_command}\n"
            )
        elif scheduler == "pbs":
            return (
                f"#!/bin/bash\n"
                f"#PBS -N {job_name}\n"
                f"#PBS -l nodes=1:ppn={n_cores}\n"
                f"#PBS -l walltime={walltime}\n"
                f"#PBS -q {queue}\n"
                f"#PBS -o $PBS_JOBID.out\n"
                f"#PBS -e $PBS_JOBID.err\n\n"
                f"cd $PBS_O_WORKDIR\n"
                f"{run_command}\n"
            )
        return f"#!/bin/bash\n{run_command}\n"

    def supports(self, task_type: DFTTaskType) -> bool:
        """检查是否支持某种任务类型"""
        return task_type in self.get_capability().supported_tasks

    def __repr__(self) -> str:
        cap = self.get_capability()
        tasks = ", ".join(t.value for t in cap.supported_tasks)
        return f"<{cap.display_name} ({cap.executable}) [{tasks}]>"
