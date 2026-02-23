# -*- coding: utf-8 -*-
"""
CalculationPlugin 抽象基类
===========================
所有可扩展计算引擎（DFT、MD、CALPHAD、ML势等）的统一接口。

同步插件只需实现:  get_metadata(), get_tools(), execute()
异步插件还需实现:  submit(), poll(), get_result(), cancel()
"""

import logging
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class PluginType(Enum):
    """插件执行类型"""
    SYNC = "sync"        # 同步: < 30秒，直接返回结果
    ASYNC = "async"      # 异步: 提交 → 轮询 → 获取结果
    HYBRID = "hybrid"    # 混合: 部分工具同步，部分异步


@dataclass
class PluginMetadata:
    """插件元信息"""
    name: str                          # 唯一标识 (snake_case)
    display_name: str                  # 中文显示名
    version: str                       # 语义版本号
    description: str                   # 中文描述
    author: str                        # 作者
    plugin_type: PluginType            # 执行类型
    dependencies: List[str] = field(default_factory=list)
    external_programs: List[str] = field(default_factory=list)
    category: str = "general"          # theory/dft/md/calphad/ml/general


@dataclass
class ToolSchema:
    """
    工具定义 — 与现有 TOOL_SCHEMAS 兼容的 JSON Schema 格式。

    参数:
        name: 工具名称 (snake_case，全局唯一)
        description: 中文描述（供LLM理解用途）
        parameters: JSON Schema 格式的参数定义
        is_async: 是否为异步工具
        timeout: 同步工具的超时秒数
    """
    name: str
    description: str
    parameters: Dict[str, Any]
    is_async: bool = False
    timeout: int = 30


class CalculationPlugin(ABC):
    """
    计算插件抽象基类。

    所有扩展计算引擎必须继承此类并实现核心接口。
    放入 extensions/adapters/ 或 extensions/contrib/ 目录后，
    PluginRegistry 会自动发现并注册。
    """

    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """返回插件元信息"""
        ...

    @abstractmethod
    def get_tools(self) -> List[ToolSchema]:
        """返回此插件提供的所有工具定义"""
        ...

    @abstractmethod
    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        同步执行工具。

        参数:
            tool_name: 工具名称
            arguments: 工具参数字典

        返回:
            {"status": "success"/"error", ...结果数据}
        """
        ...

    @staticmethod
    def _auto_install(pip_name: str) -> bool:
        """尝试通过 pip 自动安装缺失的依赖包"""
        try:
            logger.info("[自动安装] 正在安装 %s ...", pip_name)
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pip_name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=120
            )
            logger.info("[自动安装] %s 安装完成", pip_name)
            return True
        except Exception as e:
            logger.warning("[自动安装] %s 安装失败: %s", pip_name, e)
            return False

    def check_availability(self, auto_install: bool = True) -> Dict[str, Any]:
        """
        检查插件运行环境是否满足（依赖包、外部程序）。
        若 auto_install=True，会自动尝试 pip install 缺失的 Python 依赖。

        返回:
            {"available": bool, "missing_deps": [...], "missing_programs": [...]}
        """
        meta = self.get_metadata()
        missing_deps = []
        for dep in meta.dependencies:
            pkg = dep.split("[")[0].split(">=")[0].split("==")[0].strip()
            try:
                __import__(pkg)
            except ImportError:
                if auto_install and self._auto_install(dep):
                    # 安装后重新验证
                    try:
                        __import__(pkg)
                        continue  # 安装成功，不加入 missing
                    except ImportError:
                        pass
                missing_deps.append(dep)

        missing_progs = []
        for prog in meta.external_programs:
            if not shutil.which(prog):
                missing_progs.append(prog)

        return {
            "available": len(missing_deps) == 0 and len(missing_progs) == 0,
            "missing_deps": missing_deps,
            "missing_programs": missing_progs,
        }

    # --- 异步接口（PluginType.ASYNC / HYBRID 必须实现） ---

    def submit(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        提交异步任务。

        参数:
            tool_name: 工具名称
            arguments: 工具参数

        返回:
            task_id 字符串
        """
        raise NotImplementedError(
            f"插件 {self.get_metadata().name} 不支持异步执行"
        )

    def poll(self, task_id: str) -> Dict[str, Any]:
        """
        轮询异步任务状态。

        返回:
            {"task_id": str, "status": "pending"/"running"/"completed"/"failed",
             "progress": 0.0~1.0, "message": str}
        """
        raise NotImplementedError

    def get_result(self, task_id: str) -> Dict[str, Any]:
        """获取已完成任务的结果"""
        raise NotImplementedError

    def cancel(self, task_id: str) -> Dict[str, Any]:
        """取消运行中的任务"""
        raise NotImplementedError

    # --- 可选：GUI 组件 ---

    def get_widget(self) -> Optional[Any]:
        """
        返回插件专用的 PyQt5 QWidget（可选）。
        返回 None 表示无专用界面，仅通过 AI 助手交互。
        """
        return None

    def __repr__(self) -> str:
        meta = self.get_metadata()
        return f"<{meta.display_name} v{meta.version} ({meta.plugin_type.value})>"
