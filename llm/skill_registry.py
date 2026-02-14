# -*- coding: utf-8 -*-
"""
Skill Registry - 动态技能注册表
================================
支持通过对话动态创建、注册和管理计算工具（技能）。
用户可以在对话中描述新的计算需求，AI生成代码并注册为可调用工具。
"""

import json
import os
import signal
import time
import math
import traceback
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict


# 技能代码中允许的安全内置函数
_SAFE_BUILTINS = {
    'abs', 'round', 'min', 'max', 'sum', 'len', 'range', 'enumerate',
    'zip', 'map', 'filter', 'sorted', 'reversed', 'list', 'dict', 'tuple',
    'set', 'int', 'float', 'str', 'bool', 'type', 'isinstance',
    'print', 'format', 'pow', 'divmod', 'any', 'all',
}

# 允许注入的安全模块
_SAFE_MODULES = {
    'math': math,
}

# 禁止出现的代码模式
_FORBIDDEN = [
    'import os', 'import sys', 'import subprocess', 'import shutil',
    '__import__', 'eval(', 'exec(', 'compile(',
    'open(', 'input(',
    'os.system', 'os.popen', 'subprocess',
    'globals(', 'locals(',
    '__builtins__', '__class__', '__subclasses__',
]

# 允许技能调用的内置工具白名单（纯计算/查询，无副作用）
_CALLABLE_TOOLS = {
    "calculate_liquidus_temperature",
    "calculate_precipitation_temperature",
    "calculate_activity",
    "calculate_activity_coefficient",
    "calculate_mixing_enthalpy",
    "calculate_gibbs_energy",
    "calculate_chemical_potential",
    "calculate_entropy",
    "calculate_all_properties",
    "calculate_melting_point_depression",
    "get_interaction_coefficient",
    "get_second_order_interaction_coefficient",
    "get_contribution_coefficients",
    "get_infinite_dilution_activity_coefficient",
    "get_element_properties",
    "screen_elements_liquidus_effect",
    "search_knowledge",
}


class ToolBridge:
    """工具桥接器 — 让动态技能安全地调用内置计算工具"""

    def __init__(self, tools_ref):
        """
        参数:
            tools_ref: ThermodynamicTools 实例
        """
        self._tools = tools_ref

    def call_tool(self, tool_name: str, **kwargs) -> dict:
        """
        调用内置计算工具。

        参数:
            tool_name: 工具名称（如 'calculate_activity'）
            **kwargs: 传给工具的参数

        返回:
            dict: 工具执行结果
        """
        if tool_name not in _CALLABLE_TOOLS:
            return {"status": "error",
                    "message": f"工具 '{tool_name}' 不在可调用白名单中"}
        try:
            result_json = self._tools.execute_tool(tool_name, kwargs)
            return json.loads(result_json)
        except (json.JSONDecodeError, Exception) as e:
            return {"status": "error",
                    "message": f"调用工具 '{tool_name}' 失败: {e}"}


@dataclass
class DynamicSkill:
    """动态技能定义"""
    name: str
    description: str
    code: str
    parameters: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    version: int = 1
    enabled: bool = True
    tags: List[str] = field(default_factory=list)


class SkillRegistry:
    """动态技能注册表 — 管理用户通过对话创建的自定义计算工具"""

    def __init__(self, storage_dir: str = None):
        """
        参数:
            storage_dir: 存储目录，默认 ~/.alloyact
        """
        self._dir = storage_dir or os.path.expanduser("~/.alloyact")
        self._file = os.path.join(self._dir, "skills.json")
        self._skills: Dict[str, DynamicSkill] = {}
        self._compiled: Dict[str, Callable] = {}
        self._bridge: Optional[ToolBridge] = None
        os.makedirs(self._dir, exist_ok=True)
        self._load()

    def bind_tools(self, tools_ref) -> None:
        """
        绑定内置工具引用，启用技能→工具桥接。

        参数:
            tools_ref: ThermodynamicTools 实例
        """
        self._bridge = ToolBridge(tools_ref)
        # 重新编译所有技能，注入 call_tool
        for name, skill in self._skills.items():
            if skill.enabled:
                try:
                    self._compiled[name] = self._compile(name, skill.code)
                except Exception:
                    skill.enabled = False

    def create_skill(self, name: str, description: str, code: str,
                     parameters: Dict[str, Any],
                     tags: List[str] = None) -> Dict[str, Any]:
        """
        创建并注册新技能。

        参数:
            name: 技能名称（英文 snake_case）
            description: 技能描述（中文）
            code: Python函数代码（必须定义一个与name同名的函数）
            parameters: JSON Schema 格式的参数定义
            tags: 标签列表

        返回:
            {status, message}
        """
        # 校验名称
        if not name.isidentifier():
            return {"status": "error",
                    "message": f"技能名称 '{name}' 不是合法的Python标识符"}
        if name.startswith("_"):
            return {"status": "error",
                    "message": "技能名称不能以下划线开头"}

        # 安全检查
        err = self._check_safety(code)
        if err:
            return {"status": "error", "message": f"代码安全检查失败: {err}"}

        # 编译
        try:
            func = self._compile(name, code)
        except Exception as e:
            return {"status": "error", "message": f"代码编译失败: {e}"}

        action = "更新" if name in self._skills else "创建"
        self._skills[name] = DynamicSkill(
            name=name, description=description, code=code,
            parameters=parameters, tags=tags or [],
        )
        self._compiled[name] = func
        self._save()

        return {
            "status": "success",
            "message": f"技能 '{name}' {action}成功，已注册为可调用工具。",
            "skill_name": name,
        }

    _EXEC_TIMEOUT = 30  # 技能执行超时秒数

    def execute_skill(self, name: str,
                      arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行动态技能（带超时保护）"""
        if name not in self._compiled:
            return {"status": "error", "message": f"技能 '{name}' 未注册"}
        skill = self._skills[name]
        if not skill.enabled:
            return {"status": "error", "message": f"技能 '{name}' 已禁用"}

        container = {"result": None, "error": None}

        def _run():
            try:
                container["result"] = self._compiled[name](**arguments)
            except Exception as e:
                container["error"] = str(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=self._EXEC_TIMEOUT)

        if t.is_alive():
            return {"status": "error",
                    "message": f"技能 '{name}' 执行超时 (>{self._EXEC_TIMEOUT}秒)"}
        if container["error"]:
            return {"status": "error",
                    "message": f"执行技能 '{name}' 出错: {container['error']}"}
        result = container["result"]
        if isinstance(result, dict):
            return result
        return {"status": "success", "result": result}

    def list_skills(self) -> List[Dict[str, Any]]:
        """列出所有已注册的技能"""
        return [
            {"name": s.name, "description": s.description,
             "enabled": s.enabled, "version": s.version,
             "tags": s.tags}
            for s in self._skills.values()
        ]

    def remove_skill(self, name: str) -> Dict[str, Any]:
        """删除技能"""
        if name not in self._skills:
            return {"status": "error", "message": f"技能 '{name}' 不存在"}
        del self._skills[name]
        self._compiled.pop(name, None)
        self._save()
        return {"status": "success", "message": f"技能 '{name}' 已删除"}

    def get_tool_definitions(self):
        """获取所有启用技能的工具定义"""
        from llm.llm_backend import ToolDefinition
        defs = []
        for name, skill in self._skills.items():
            if not skill.enabled or name not in self._compiled:
                continue
            # 用闭包捕获 name
            def _make_exec(n):
                return lambda **kw: self.execute_skill(n, kw)
            defs.append(ToolDefinition(
                name=f"skill_{name}",
                description=f"[自定义技能] {skill.description}",
                parameters=skill.parameters,
                function=_make_exec(name),
            ))
        return defs

    def get_skill_count(self) -> int:
        """获取已启用技能数量"""
        return sum(1 for s in self._skills.values() if s.enabled)

    # ---- 内部方法 ----

    def _check_safety(self, code: str) -> Optional[str]:
        """检查代码安全性"""
        code_lower = code.lower()
        for pat in _FORBIDDEN:
            if pat.lower() in code_lower:
                return f"禁止使用 '{pat}'"
        return None

    def _compile(self, name: str, code: str) -> Callable:
        """编译技能代码并返回可调用函数"""
        # 安全的执行环境
        safe_globals = {
            "__builtins__": {b: __builtins__[b] if isinstance(__builtins__, dict)
                            else getattr(__builtins__, b)
                            for b in _SAFE_BUILTINS
                            if (b in __builtins__ if isinstance(__builtins__, dict)
                                else hasattr(__builtins__, b))}
        }
        # 注入安全模块
        for mod_name, mod in _SAFE_MODULES.items():
            safe_globals[mod_name] = mod

        # 尝试注入 numpy
        try:
            import numpy as np
            safe_globals["np"] = np
            safe_globals["numpy"] = np
        except ImportError:
            pass

        # 尝试注入 scipy 子模块
        try:
            from scipy import optimize, interpolate
            safe_globals["scipy_optimize"] = optimize
            safe_globals["scipy_interpolate"] = interpolate
        except ImportError:
            pass

        # 安全的 import 函数：只允许已注入的模块
        _allowed_imports = dict(safe_globals)  # 当前环境的快照

        def _safe_import(name, *args, **kwargs):
            if name in _allowed_imports:
                return _allowed_imports[name]
            raise ImportError(f"模块 '{name}' 不可用。可用模块: math, np/numpy, scipy_optimize, scipy_interpolate")

        safe_globals["__builtins__"]["__import__"] = _safe_import

        # 注入工具桥接器：call_tool(tool_name, **kwargs) -> dict
        if self._bridge:
            safe_globals["call_tool"] = self._bridge.call_tool
        else:
            # 无桥接器时提供占位函数，返回错误信息
            def _no_bridge(tool_name: str, **kwargs):
                return {"status": "error",
                        "message": "工具桥接器未初始化，无法调用内置工具"}
            safe_globals["call_tool"] = _no_bridge

        # 注入可调用工具清单（技能代码可读取）
        safe_globals["AVAILABLE_TOOLS"] = sorted(_CALLABLE_TOOLS)

        exec(code, safe_globals)

        if name not in safe_globals:
            raise ValueError(f"代码中未定义名为 '{name}' 的函数")
        func = safe_globals[name]
        if not callable(func):
            raise ValueError(f"'{name}' 不是可调用对象")
        return func

    def _load(self):
        """从磁盘加载技能"""
        if not os.path.exists(self._file):
            return
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return
            for item in data:
                if not isinstance(item, dict) or "name" not in item:
                    continue
                try:
                    skill = DynamicSkill(**item)
                except (TypeError, ValueError):
                    continue
                self._skills[skill.name] = skill
                try:
                    self._compiled[skill.name] = self._compile(
                        skill.name, skill.code
                    )
                except Exception:
                    skill.enabled = False
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self):
        """保存技能到磁盘"""
        try:
            data = [asdict(s) for s in self._skills.values()]
            tmp = self._file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._file)
        except Exception:
            # 保存失败不影响运行
            pass
