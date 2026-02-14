# -*- coding: utf-8 -*-
"""
LAMMPS Adapter - LAMMPS 分子动力学适配器（存根）
==================================================
通过 SSH 连接 HPC 集群，提交 LAMMPS 分子动力学模拟任务。
此文件为架构存根，实际的 HPC 连接逻辑待 Phase 3 实现。

依赖: pip install paramiko
外部程序: lmp (HPC 端)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from extensions.base import (
    CalculationPlugin, PluginMetadata, PluginType, ToolSchema
)
from typing import Dict, List, Any


class LAMMPSAdapter(CalculationPlugin):
    """LAMMPS 分子动力学适配器（异步插件 — 存根实现）"""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="lammps_md",
            display_name="LAMMPS 分子动力学",
            version="0.0.1",
            description="通过 SSH 连接 HPC 集群提交 LAMMPS 分子动力学模拟，"
                        "支持 NVT/NPT 系综、热力学性质计算、扩散系数等",
            author="AlloyThermolCal Pro",
            plugin_type=PluginType.ASYNC,
            dependencies=["paramiko"],
            external_programs=[],
            category="md",
        )

    def get_tools(self) -> List[ToolSchema]:
        return [
            ToolSchema(
                name="md_thermodynamic",
                description="LAMMPS 热力学性质模拟（NPT 系综，计算平衡态热力学量）",
                parameters={
                    "type": "object",
                    "properties": {
                        "composition": {
                            "type": "object",
                            "description": "合金成分 {元素: 原子数}",
                            "additionalProperties": {"type": "integer"},
                        },
                        "temperature": {
                            "type": "number",
                            "description": "模拟温度 (K)",
                        },
                        "pressure": {
                            "type": "number",
                            "description": "模拟压力 (atm)",
                            "default": 1.0,
                        },
                        "potential": {
                            "type": "string",
                            "description": "势函数类型",
                            "enum": ["eam", "eam/alloy", "meam", "tersoff"],
                            "default": "eam/alloy",
                        },
                        "total_steps": {
                            "type": "integer",
                            "description": "总模拟步数",
                            "default": 100000,
                        },
                    },
                    "required": ["composition", "temperature"],
                },
                is_async=True,
                timeout=3600,
            ),
            ToolSchema(
                name="md_diffusion",
                description="LAMMPS 扩散系数计算（NVT + MSD 分析）",
                parameters={
                    "type": "object",
                    "properties": {
                        "composition": {
                            "type": "object",
                            "description": "合金成分 {元素: 原子数}",
                            "additionalProperties": {"type": "integer"},
                        },
                        "temperature": {
                            "type": "number",
                            "description": "模拟温度 (K)",
                        },
                        "total_steps": {
                            "type": "integer",
                            "description": "总模拟步数",
                            "default": 200000,
                        },
                    },
                    "required": ["composition", "temperature"],
                },
                is_async=True,
                timeout=7200,
            ),
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """异步插件不支持同步执行"""
        return {
            "status": "error",
            "message": "LAMMPS 模拟为异步任务，请使用 submit() 提交。"
                       "此功能待 Phase 3 实现 HPC 连接后可用。",
        }

    def submit(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        提交 LAMMPS 任务到 HPC 集群。

        TODO (Phase 3):
        1. 生成 LAMMPS 输入脚本 (.in)
        2. 选择并下载合适的势函数文件
        3. SSH 上传到 HPC 工作目录
        4. 提交 SLURM 作业
        5. 返回作业 ID
        """
        raise NotImplementedError(
            "LAMMPS HPC 连接尚未实现。请参考 docs/EXTENSIBILITY_PLAN.md Phase 3。"
        )

    def poll(self, task_id: str) -> Dict[str, Any]:
        """检查 SLURM 作业状态"""
        raise NotImplementedError("LAMMPS HPC 连接尚未实现")

    def get_result(self, task_id: str) -> Dict[str, Any]:
        """下载并解析 LAMMPS 输出"""
        raise NotImplementedError("LAMMPS HPC 连接尚未实现")

    def cancel(self, task_id: str) -> Dict[str, Any]:
        """取消 SLURM 作业"""
        raise NotImplementedError("LAMMPS HPC 连接尚未实现")
