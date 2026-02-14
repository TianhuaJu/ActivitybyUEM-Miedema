# -*- coding: utf-8 -*-
"""
VASP Adapter - VASP DFT 远程计算适配器（存根）
================================================
通过 SSH 连接 HPC 集群，提交 VASP 计算任务，自动解析结果。
此文件为架构存根，实际的 HPC 连接逻辑待 Phase 3 实现。

依赖: pip install paramiko
外部程序: vasp_std (HPC 端)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from extensions.base import (
    CalculationPlugin, PluginMetadata, PluginType, ToolSchema
)
from typing import Dict, List, Any


class VASPAdapter(CalculationPlugin):
    """VASP DFT 远程计算适配器（异步插件 — 存根实现）"""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="vasp_dft",
            display_name="VASP DFT 计算",
            version="0.0.1",
            description="通过 SSH 连接 HPC 集群提交 VASP 第一性原理计算任务，"
                        "支持单点能量、结构优化、态密度、能带等计算",
            author="AlloyThermolCal Pro",
            plugin_type=PluginType.ASYNC,
            dependencies=["paramiko"],
            external_programs=[],  # vasp 在远程 HPC 上，本地不检查
            category="dft",
        )

    def get_tools(self) -> List[ToolSchema]:
        return [
            ToolSchema(
                name="dft_single_point",
                description="DFT 单点能量计算（VASP）",
                parameters={
                    "type": "object",
                    "properties": {
                        "composition": {
                            "type": "object",
                            "description": "合金成分 {元素: 原子数}",
                            "additionalProperties": {"type": "integer"},
                        },
                        "structure": {
                            "type": "string",
                            "description": "晶体结构类型",
                            "enum": ["fcc", "bcc", "hcp"],
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
                    },
                    "required": ["composition", "structure"],
                },
                is_async=True,
                timeout=7200,
            ),
            ToolSchema(
                name="dft_optimize",
                description="DFT 结构优化（VASP ISIF=3）",
                parameters={
                    "type": "object",
                    "properties": {
                        "composition": {
                            "type": "object",
                            "description": "合金成分 {元素: 原子数}",
                            "additionalProperties": {"type": "integer"},
                        },
                        "structure": {
                            "type": "string",
                            "enum": ["fcc", "bcc", "hcp"],
                        },
                    },
                    "required": ["composition", "structure"],
                },
                is_async=True,
                timeout=14400,
            ),
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """异步插件不支持同步执行"""
        return {
            "status": "error",
            "message": "VASP 计算为异步任务，请使用 submit() 提交。"
                       "此功能待 Phase 3 实现 HPC 连接后可用。",
        }

    def submit(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        提交 VASP 任务到 HPC 集群。

        TODO (Phase 3):
        1. 生成 POSCAR / INCAR / KPOINTS / POTCAR
        2. SSH 上传到 HPC 工作目录
        3. 提交 SLURM 作业 (sbatch)
        4. 返回作业 ID
        """
        raise NotImplementedError(
            "VASP HPC 连接尚未实现。请参考 docs/EXTENSIBILITY_PLAN.md Phase 3。"
        )

    def poll(self, task_id: str) -> Dict[str, Any]:
        """
        检查 SLURM 作业状态。

        TODO (Phase 3):
        1. SSH 执行 squeue -j <job_id>
        2. 解析作业状态
        3. 读取 OSZICAR 估算收敛进度
        """
        raise NotImplementedError("VASP HPC 连接尚未实现")

    def get_result(self, task_id: str) -> Dict[str, Any]:
        """
        下载并解析 VASP 输出。

        TODO (Phase 3):
        1. SSH 下载 OUTCAR / vasprun.xml
        2. 解析总能量、力、应力
        3. 返回结构化结果
        """
        raise NotImplementedError("VASP HPC 连接尚未实现")

    def cancel(self, task_id: str) -> Dict[str, Any]:
        """
        取消 SLURM 作业。

        TODO (Phase 3):
        1. SSH 执行 scancel <job_id>
        """
        raise NotImplementedError("VASP HPC 连接尚未实现")
