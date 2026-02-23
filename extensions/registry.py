# -*- coding: utf-8 -*-
"""
PluginRegistry - 插件自动发现与注册
=====================================
扫描指定目录中的 CalculationPlugin 子类，自动加载并注册为 LLM 可调用工具。
"""

import importlib
import importlib.util
import logging
import os
import sys
import traceback
from typing import Dict, List, Any, Optional, Callable

from extensions.base import CalculationPlugin, PluginMetadata, PluginType, ToolSchema

logger = logging.getLogger(__name__)


class PluginRegistry:
    """插件注册表 — 自动发现、加载、管理计算插件"""

    def __init__(self, plugin_dirs: List[str] = None):
        """
        参数:
            plugin_dirs: 插件搜索目录列表。默认搜索 extensions/adapters/ 和 extensions/contrib/
        """
        _base = os.path.dirname(os.path.abspath(__file__))
        self._plugin_dirs = plugin_dirs or [
            os.path.join(_base, "adapters"),
            os.path.join(_base, "contrib"),
        ]
        self._plugins: Dict[str, CalculationPlugin] = {}
        self._availability: Dict[str, Dict[str, Any]] = {}

    # ==================== 发现与注册 ====================

    def discover(self) -> List[str]:
        """
        扫描所有插件目录，加载包含 CalculationPlugin 子类的 .py 文件。

        返回:
            成功加载的插件名称列表
        """
        loaded = []
        for d in self._plugin_dirs:
            if not os.path.isdir(d):
                continue
            for fname in sorted(os.listdir(d)):
                if not fname.endswith(".py") or fname.startswith("_"):
                    continue
                fpath = os.path.join(d, fname)
                try:
                    names = self._load_file(fpath)
                    loaded.extend(names)
                except Exception:
                    logger.warning("加载插件文件失败: %s\n%s",
                                   fpath, traceback.format_exc())
        return loaded

    def _load_file(self, filepath: str) -> List[str]:
        """从单个 .py 文件中加载所有 CalculationPlugin 子类"""
        module_name = f"_ext_{os.path.basename(filepath)[:-3]}"
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            return []

        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)

        loaded = []
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if (isinstance(obj, type)
                    and issubclass(obj, CalculationPlugin)
                    and obj is not CalculationPlugin):
                try:
                    plugin = obj()
                    self.register(plugin)
                    loaded.append(plugin.get_metadata().name)
                except Exception:
                    logger.warning("实例化插件 %s 失败:\n%s",
                                   attr_name, traceback.format_exc())
        return loaded

    def register(self, plugin: CalculationPlugin) -> None:
        """
        手动注册插件实例。

        参数:
            plugin: CalculationPlugin 子类实例
        """
        meta = plugin.get_metadata()
        name = meta.name

        if name in self._plugins:
            existing_ver = self._plugins[name].get_metadata().version
            logger.info("插件 %s 已存在 (v%s)，覆盖为 v%s",
                        name, existing_ver, meta.version)

        avail = plugin.check_availability()
        self._availability[name] = avail
        self._plugins[name] = plugin

        if avail["available"]:
            logger.info("插件已注册: %s v%s (%s)",
                        meta.display_name, meta.version, meta.plugin_type.value)
        else:
            logger.warning("插件 %s 依赖不满足 (deps=%s, progs=%s)，标记为不可用",
                           name, avail["missing_deps"], avail["missing_programs"])

    def unregister(self, name: str) -> bool:
        """注销插件"""
        if name in self._plugins:
            del self._plugins[name]
            self._availability.pop(name, None)
            return True
        return False

    # ==================== 查询接口 ====================

    def get_plugin(self, name: str) -> Optional[CalculationPlugin]:
        """按名称获取插件实例"""
        return self._plugins.get(name)

    def get_plugins(self) -> List[CalculationPlugin]:
        """获取所有已注册插件"""
        return list(self._plugins.values())

    def get_available_plugins(self) -> List[CalculationPlugin]:
        """获取所有依赖满足的可用插件"""
        return [
            p for name, p in self._plugins.items()
            if self._availability.get(name, {}).get("available", False)
        ]

    def list_plugins(self) -> List[Dict[str, Any]]:
        """列出所有插件的概要信息"""
        result = []
        for name, plugin in self._plugins.items():
            meta = plugin.get_metadata()
            avail = self._availability.get(name, {})
            result.append({
                "name": meta.name,
                "display_name": meta.display_name,
                "version": meta.version,
                "description": meta.description,
                "category": meta.category,
                "plugin_type": meta.plugin_type.value,
                "available": avail.get("available", False),
                "missing_deps": avail.get("missing_deps", []),
                "missing_programs": avail.get("missing_programs", []),
                "tool_count": len(plugin.get_tools()),
            })
        return result

    # ==================== 工具转换 ====================

    def get_all_tool_schemas(self) -> Dict[str, Dict[str, Any]]:
        """
        将所有可用插件的工具转换为 TOOL_SCHEMAS 兼容格式。

        返回:
            {"plugin_name.tool_name": JSON_Schema, ...}
        """
        schemas = {}
        for plugin in self.get_available_plugins():
            meta = plugin.get_metadata()
            for tool in plugin.get_tools():
                full_name = f"{meta.name}__{tool.name}"
                schemas[full_name] = tool.parameters
        return schemas

    def get_all_tool_descriptions(self) -> Dict[str, str]:
        """
        将所有可用插件的工具描述转换为 TOOL_DESCRIPTIONS 兼容格式。

        返回:
            {"plugin_name.tool_name": "中文描述", ...}
        """
        descs = {}
        for plugin in self.get_available_plugins():
            meta = plugin.get_metadata()
            for tool in plugin.get_tools():
                full_name = f"{meta.name}__{tool.name}"
                descs[full_name] = f"[{meta.display_name}] {tool.description}"
        return descs

    def get_tool_methods(self) -> Dict[str, Callable]:
        """
        生成工具名 → 可调用函数的映射。
        同步工具直接映射到 plugin.execute()；
        异步工具映射到 submit/poll/get_result 包装。

        返回:
            {"plugin_name__tool_name": callable, ...}
        """
        methods = {}
        for plugin in self.get_available_plugins():
            meta = plugin.get_metadata()
            for tool in plugin.get_tools():
                full_name = f"{meta.name}__{tool.name}"

                if tool.is_async:
                    # 异步工具：execute 返回提交信息
                    def _make_async(p=plugin, t=tool):
                        def _submit(**kwargs):
                            try:
                                task_id = p.submit(t.name, kwargs)
                                return {
                                    "status": "success",
                                    "message": f"异步任务已提交",
                                    "task_id": task_id,
                                    "plugin": p.get_metadata().name,
                                    "tool": t.name,
                                }
                            except NotImplementedError:
                                return {
                                    "status": "error",
                                    "message": "此工具不支持异步执行",
                                }
                            except Exception as e:
                                return {"status": "error", "message": str(e)}
                        return _submit
                    methods[full_name] = _make_async()
                else:
                    # 同步工具：直接调用 execute
                    def _make_sync(p=plugin, t=tool):
                        def _exec(**kwargs):
                            try:
                                return p.execute(t.name, kwargs)
                            except Exception as e:
                                return {"status": "error", "message": str(e)}
                        return _exec
                    methods[full_name] = _make_sync()

        return methods

    def get_all_tool_definitions(self) -> list:
        """
        将所有可用插件工具转换为 ToolDefinition 列表，
        可直接合并到 ThermodynamicTools.get_tool_definitions() 返回值中。
        """
        from llm.llm_backend import ToolDefinition

        definitions = []
        schemas = self.get_all_tool_schemas()
        descs = self.get_all_tool_descriptions()
        methods = self.get_tool_methods()

        for full_name in schemas:
            definitions.append(ToolDefinition(
                name=full_name,
                description=descs.get(full_name, ""),
                parameters=schemas[full_name],
                function=methods.get(full_name),
            ))
        return definitions

    # ==================== 执行入口 ====================

    def execute(self, full_tool_name: str,
                arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        统一执行入口。

        参数:
            full_tool_name: "plugin_name__tool_name" 格式
            arguments: 工具参数

        返回:
            {"status": "success"/"error", ...}
        """
        parts = full_tool_name.split("__", 1)
        if len(parts) != 2:
            return {"status": "error",
                    "message": f"无效的插件工具名: {full_tool_name}"}

        plugin_name, tool_name = parts
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            return {"status": "error",
                    "message": f"未找到插件: {plugin_name}"}

        avail = self._availability.get(plugin_name, {})
        if not avail.get("available", False):
            return {"status": "error",
                    "message": f"插件 {plugin_name} 不可用: "
                               f"缺少依赖 {avail.get('missing_deps', [])}"}

        # 判断同步/异步
        tool_schema = None
        for t in plugin.get_tools():
            if t.name == tool_name:
                tool_schema = t
                break
        if not tool_schema:
            return {"status": "error",
                    "message": f"插件 {plugin_name} 中无工具: {tool_name}"}

        if tool_schema.is_async:
            try:
                task_id = plugin.submit(tool_name, arguments)
                return {
                    "status": "success",
                    "message": "异步任务已提交",
                    "task_id": task_id,
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
        else:
            try:
                return plugin.execute(tool_name, arguments)
            except Exception as e:
                return {"status": "error", "message": str(e)}

    # ==================== Prompt 格式化 ====================

    def format_tools_for_prompt(self) -> str:
        """
        生成插件工具描述文本，追加到 SYSTEM_PROMPT 中供 LLM 理解。

        返回:
            可拼接到 system prompt 的文本段落
        """
        available = self.get_available_plugins()
        if not available:
            return ""

        lines = ["\n\n========== 扩展插件工具 =========="]
        for plugin in available:
            meta = plugin.get_metadata()
            lines.append(f"\n【{meta.display_name}】({meta.category}, "
                         f"{'异步' if meta.plugin_type == PluginType.ASYNC else '同步'})")
            for tool in plugin.get_tools():
                full_name = f"{meta.name}__{tool.name}"
                async_tag = " [异步]" if tool.is_async else ""
                lines.append(f"  - {full_name}: {tool.description}{async_tag}")

        return "\n".join(lines)
