# 可扩展操作规划方案

## AlloyThermolCal Pro — 插件化架构与 DFT/MD 集成路线图

> 版本: 1.0
> 日期: 2026-02-14
> 状态: 初始设计

---

## 一、背景与目标

### 1.1 现状

AlloyThermolCal Pro 当前基于 UEM-Miedema 模型框架，提供即时同步计算（< 1 秒）。工具系统（`llm/tools.py`）通过硬编码的 `TOOL_SCHEMAS` + `ThermodynamicTools` 类注册，扩展需要修改源码。动态技能系统（`llm/skill_registry.py`）允许运行时创建工具，但受限于 30 秒超时和沙盒环境。

### 1.2 目标

构建**通用插件化架构**，使第三方计算引擎（DFT、分子动力学、CALPHAD、机器学习势等）可以：

1. **即插即用** — 放入 `extensions/` 目录即可被自动发现和注册
2. **统一接口** — 所有插件遵循相同的 `CalculationPlugin` 基类协议
3. **异步支持** — 长时间计算（DFT/MD）通过异步任务队列处理
4. **LLM 无缝集成** — 插件自动注册为 LLM 可调用工具
5. **GUI 自动适配** — 新插件自动出现在 AI 助手和工具菜单中

---

## 二、架构设计

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────┐
│                      GUI Layer (PyQt5)                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐  │
│  │ 现有 Tabs   │  │ 插件 Tabs  │  │  AI 助手 (ChatWidget)  │  │
│  │ (热力学等)  │  │ (DFT/MD等)│  │  + 异步任务面板        │  │
│  └──────┬─────┘  └─────┬──────┘  └────────┬───────────────┘  │
│         │              │                   │                  │
├─────────┴──────────────┴───────────────────┴──────────────────┤
│                     Tool Execution Layer                      │
│  ┌──────────────────┐  ┌──────────────────────────────────┐  │
│  │ ThermodynamicTools│  │  PluginRegistry (自动发现+注册)  │  │
│  │ (现有26个工具)    │  │  ├─ 同步插件 → 直接执行          │  │
│  │                  │  │  └─ 异步插件 → AsyncTaskQueue     │  │
│  └──────────────────┘  └──────────────────────────────────┘  │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                     Plugin Layer (新增)                        │
│  ┌──────────────────────────┐  ┌───────────┐ ┌────────────┐ │
│  │ DFT Adapter (统一入口)   │  │ MD        │ │ ML         │ │
│  │  ┌─────┐ ┌────┐ ┌─────┐ │  │ Adapter   │ │ Potential  │ │
│  │  │VASP │ │ QE │ │GPAW │ │  │ (LAMMPS)  │ │ Adapter    │ │
│  │  │     │ │    │ │     │ │  └─────┬─────┘ └─────┬──────┘ │
│  │  └──┬──┘ └─┬──┘ └──┬──┘ │        │             │        │
│  │     └──────┴───────┘    │        │             │        │
│  │  ┌──────┐ ┌──────┐      │        │             │        │
│  │  │ABINIT│ │ CP2K │      │        │             │        │
│  │  └──┬───┘ └──┬───┘      │        │             │        │
│  │     └────────┘          │        │             │        │
│  │    DFTEngine (策略接口)  │        │             │        │
│  └────────────┬─────────────┘        │             │        │
│               │                      │             │        │
│  ┌────────────┴──────────────────────┴─────────────┴───────┐│
│  │              CalculationPlugin (抽象基类)                  ││
│  │  - get_metadata()   返回插件元信息                        ││
│  │  - get_tools()      返回工具定义列表                      ││
│  │  - execute()        同步执行                              ││
│  │  - submit()         异步提交 (可选)                       ││
│  │  - poll()           轮询状态 (可选)                       ││
│  │  - cancel()         取消任务 (可选)                       ││
│  └──────────────────────────────────────────────────────────┘│
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                   Async Infrastructure (新增)                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              AsyncTaskQueue                              │ │
│  │  - submit_task(plugin, tool, args) → task_id            │ │
│  │  - poll_task(task_id) → TaskStatus                      │ │
│  │  - get_result(task_id) → Dict                           │ │
│  │  - cancel_task(task_id)                                 │ │
│  │  - list_tasks() → List[TaskInfo]                        │ │
│  │                                                         │ │
│  │  存储: SQLite (~/.alloyact/tasks.db)                    │ │
│  │  执行: ThreadPoolExecutor / ProcessPoolExecutor         │ │
│  └─────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### 2.2 新增目录结构

```
extensions/                          # 插件系统根目录
├── __init__.py                      # 包初始化 + 便捷导入
├── base.py                          # CalculationPlugin 抽象基类
├── registry.py                      # PluginRegistry 自动发现与注册
├── async_task.py                    # AsyncTaskQueue 异步任务队列
│
├── engines/                         # DFT 计算引擎抽象层（策略模式）
│   ├── __init__.py
│   ├── dft_engine.py               # DFTEngine 抽象基类 + 统一数据格式
│   ├── vasp_engine.py              # VASP 引擎（商业）
│   ├── qe_engine.py                # Quantum ESPRESSO 引擎（GPL）
│   ├── abinit_engine.py            # ABINIT 引擎（GPL）
│   ├── cp2k_engine.py              # CP2K 引擎（GPL，擅长大体系/AIMD）
│   └── gpaw_engine.py              # GPAW 引擎（GPL，Python原生）
│
├── adapters/                        # 插件适配器
│   ├── __init__.py
│   ├── dft_adapter.py              # 统一 DFT 适配器（调度所有引擎）
│   ├── ase_adapter.py              # ASE 轻量 DFT/MD (Phase 2)
│   └── lammps_adapter.py           # LAMMPS MD 远程提交 (Phase 3)
│
└── contrib/                         # 第三方插件目录（用户扩展）
    └── README.md                    # 开发指南
```

---

## 三、核心接口设计

### 3.1 CalculationPlugin 抽象基类

```python
# extensions/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class PluginType(Enum):
    """插件执行类型"""
    SYNC = "sync"        # 同步: < 30秒，直接返回结果
    ASYNC = "async"      # 异步: 提交→轮询→获取结果
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
    dependencies: List[str] = field(default_factory=list)  # 所需Python包
    external_programs: List[str] = field(default_factory=list)  # 所需外部程序
    category: str = "general"          # theory/dft/md/calphad/ml/general


@dataclass
class ToolSchema:
    """工具定义（JSON Schema 格式，与现有 TOOL_SCHEMAS 兼容）"""
    name: str                          # 工具名称 (snake_case)
    description: str                   # 中文描述
    parameters: Dict[str, Any]         # JSON Schema
    is_async: bool = False             # 是否异步工具
    timeout: int = 30                  # 超时秒数（同步工具）


class CalculationPlugin(ABC):
    """计算插件抽象基类 — 所有扩展引擎必须实现此接口"""

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
            arguments: 工具参数

        返回:
            {"status": "success"/"error", ...结果数据}
        """
        ...

    def check_availability(self) -> Dict[str, Any]:
        """
        检查插件运行环境是否满足。

        返回:
            {"available": bool, "missing_deps": [...], "missing_programs": [...]}
        """
        meta = self.get_metadata()
        missing_deps = []
        for dep in meta.dependencies:
            try:
                __import__(dep.split('[')[0])
            except ImportError:
                missing_deps.append(dep)

        missing_progs = []
        import shutil
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

        返回:
            task_id (字符串)

        默认实现: 抛出 NotImplementedError
        """
        raise NotImplementedError(f"插件 {self.get_metadata().name} 不支持异步执行")

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
```

### 3.2 PluginRegistry 自动发现

```python
# extensions/registry.py（核心逻辑）

class PluginRegistry:
    """插件注册表 — 自动发现、加载、管理计算插件"""

    def __init__(self, plugin_dirs: List[str] = None):
        self._plugins: Dict[str, CalculationPlugin] = {}
        self._plugin_dirs = plugin_dirs or [
            os.path.join(os.path.dirname(__file__), "adapters"),
            os.path.join(os.path.dirname(__file__), "contrib"),
        ]

    def discover(self) -> List[str]:
        """扫描插件目录，加载所有 CalculationPlugin 子类"""
        ...

    def register(self, plugin: CalculationPlugin) -> None:
        """手动注册插件"""
        ...

    def get_all_tool_definitions(self) -> List[ToolDefinition]:
        """将所有插件工具转换为 LLM ToolDefinition 格式"""
        ...

    def execute(self, plugin_name: str, tool_name: str,
                arguments: Dict[str, Any]) -> Dict[str, Any]:
        """统一执行入口：自动判断同步/异步"""
        ...
```

### 3.3 AsyncTaskQueue 异步任务队列

```python
# extensions/async_task.py（核心逻辑）

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class TaskInfo:
    task_id: str
    plugin_name: str
    tool_name: str
    arguments: Dict[str, Any]
    status: TaskStatus
    progress: float          # 0.0 ~ 1.0
    message: str
    created_at: float
    completed_at: Optional[float]
    result: Optional[Dict[str, Any]]

class AsyncTaskQueue:
    """异步任务队列 — 管理长时间运行的计算任务"""

    def __init__(self, db_path: str = None, max_workers: int = 4):
        self._db_path = db_path or "~/.alloyact/tasks.db"
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, TaskInfo] = {}

    def submit(self, plugin: CalculationPlugin,
               tool_name: str, arguments: Dict[str, Any]) -> str:
        """提交异步计算任务，返回 task_id"""
        ...

    def poll(self, task_id: str) -> TaskInfo:
        """查询任务状态"""
        ...

    def get_result(self, task_id: str) -> Dict[str, Any]:
        """获取完成任务的结果"""
        ...

    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        ...

    def list_tasks(self, status: TaskStatus = None) -> List[TaskInfo]:
        """列出任务"""
        ...
```

---

## 四、与现有系统的集成点

### 4.1 llm/tools.py 集成

```python
# ThermodynamicTools.__init__ 新增：
def __init__(self, ..., plugin_registry=None):
    self._plugin_registry = plugin_registry

# _get_all_tool_methods() 新增：
def _get_all_tool_methods(self):
    methods = { ... }  # 现有26个工具不变
    # 合并插件工具
    if self._plugin_registry:
        for name, func in self._plugin_registry.get_tool_methods().items():
            methods[name] = func
    return methods

# get_tool_definitions() 新增：
def get_tool_definitions(self):
    tools = [ ... ]  # 现有工具定义不变
    # 合并插件工具定义
    if self._plugin_registry:
        tools.extend(self._plugin_registry.get_all_tool_definitions())
    return tools
```

### 4.2 llm/chat_agent.py 集成

```python
# ChatAgent.__init__ 新增：
from extensions.registry import PluginRegistry

self.plugin_registry = PluginRegistry()
self.plugin_registry.discover()  # 自动发现插件

self.tools = ThermodynamicTools(
    ...,
    plugin_registry=self.plugin_registry
)

# SYSTEM_PROMPT 动态追加插件工具说明：
plugin_prompt = self.plugin_registry.format_tools_for_prompt()
session.add_message("system", SYSTEM_PROMPT + plugin_prompt)
```

### 4.3 异步工具的 LLM 交互模式

异步插件自动注册 3 个额外的 meta 工具：

| 工具名 | 功能 | 示例 |
|--------|------|------|
| `submit_async_task` | 提交异步任务 | `{"plugin": "vasp_dft", "tool": "single_point_energy", "args": {...}}` |
| `check_task_status` | 查询任务状态 | `{"task_id": "abc123"}` |
| `get_task_result` | 获取已完成的结果 | `{"task_id": "abc123"}` |

LLM 对话流程：
```
用户: "帮我算 Fe-C 体系的 DFT 能量"
AI:   → 调用 submit_async_task(plugin="vasp_dft", tool="single_point_energy", ...)
      ← {"task_id": "abc123", "estimated_time": "2h"}
AI:   "已提交 DFT 计算（任务 ID: abc123），预计 2 小时完成。稍后可以问我查看进度。"

用户: "之前的 DFT 任务完成了吗？"
AI:   → 调用 check_task_status(task_id="abc123")
      ← {"status": "completed", "progress": 1.0}
      → 调用 get_task_result(task_id="abc123")
      ← {"energy": -8.234, "forces": [...], ...}
AI:   "DFT 计算已完成。Fe-C 体系总能量为 -8.234 eV。"
```

### 4.4 GUI 集成

```python
# gui/Alloyact_GUI_Pro.py

# 在 setup_ui() 中，自动为每个有 GUI widget 的插件创建 Tab：
for plugin in self.plugin_registry.get_plugins():
    meta = plugin.get_metadata()
    widget = plugin.get_widget()  # 可选方法
    if widget:
        self.main_tabs.addTab(widget, meta.display_name)
```

---

## 五、实施路线图

### Phase 1: 插件基建（本次实施）

**目标**: 建立可扩展框架，不改变现有功能

| 任务 | 文件 | 说明 |
|------|------|------|
| 插件基类 | `extensions/base.py` | `CalculationPlugin`, `PluginMetadata`, `ToolSchema` |
| 插件注册表 | `extensions/registry.py` | 自动发现、加载、工具转换 |
| 异步队列 | `extensions/async_task.py` | `AsyncTaskQueue`, `TaskInfo`, SQLite 持久化 |
| 工具桥接 | `extensions/tool_bridge.py` | 插件工具→LLM ToolDefinition 转换 |
| 示例插件 | `extensions/adapters/ase_adapter.py` | ASE 适配器（存根） |
| 集成入口 | 修改 `llm/tools.py`, `llm/chat_agent.py` | 合并插件工具到现有系统 |

### Phase 2: ASE 轻量集成

**目标**: 通过 ASE 实现本地快速 DFT/MD

**前提**: `pip install ase`

| 工具 | 功能 | 预计耗时 |
|------|------|---------|
| `ase_optimize_structure` | 结构优化 (EMT/EAM) | < 10秒 |
| `ase_single_point` | 单点能量计算 | < 5秒 |
| `ase_md_nvt` | NVT 分子动力学 | < 30秒 |
| `ase_phonon` | 声子频率计算 | < 20秒 |
| `ase_eos` | 状态方程拟合 | < 15秒 |

### Phase 3: HPC 远程计算

**目标**: 远程提交 VASP/LAMMPS 到 HPC 集群

**新增依赖**: `paramiko` (SSH), `fabric` (remote execution)

| 组件 | 功能 |
|------|------|
| `VASPAdapter` | POSCAR/INCAR 自动生成 → SSH 提交 → OUTCAR 解析 |
| `LAMMPSAdapter` | .lmp 输入生成 → SSH 提交 → dump 解析 |
| `HPCConnector` | SSH 连接池、SLURM/PBS 作业管理 |
| `ResultParser` | VASP/LAMMPS 输出文件自动解析 |

### Phase 4: ML Potential 集成

**目标**: 机器学习势函数加速大规模模拟

| 框架 | 用途 |
|------|------|
| MACE / NequIP | 通用原子势 |
| CHGNet | 电荷感知势 |
| M3GNet | 材料通用势 |

---

## 六、开发一个新插件的步骤（面向开发者）

### 6.1 最简同步插件

```python
# extensions/contrib/my_calculator.py

from extensions.base import CalculationPlugin, PluginMetadata, ToolSchema, PluginType

class MyCalculatorPlugin(CalculationPlugin):
    """自定义计算插件示例"""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_calculator",
            display_name="我的计算器",
            version="1.0.0",
            description="自定义热力学计算插件",
            author="开发者",
            plugin_type=PluginType.SYNC,
            dependencies=[],          # 无额外依赖
        )

    def get_tools(self) -> list:
        return [
            ToolSchema(
                name="my_custom_calc",
                description="执行自定义计算",
                parameters={
                    "type": "object",
                    "properties": {
                        "x": {"type": "number", "description": "输入值"},
                    },
                    "required": ["x"]
                }
            )
        ]

    def execute(self, tool_name: str, arguments: dict) -> dict:
        if tool_name == "my_custom_calc":
            x = arguments["x"]
            return {"status": "success", "result": x ** 2}
        return {"status": "error", "message": f"未知工具: {tool_name}"}
```

放入 `extensions/contrib/` 目录后，重启应用即可在 AI 助手中使用。

### 6.2 异步插件（DFT 示例）

```python
# extensions/contrib/my_dft_plugin.py

class MyDFTPlugin(CalculationPlugin):

    def get_metadata(self):
        return PluginMetadata(
            name="my_dft",
            display_name="DFT 计算",
            version="0.1.0",
            description="远程 DFT 第一性原理计算",
            author="研究组",
            plugin_type=PluginType.ASYNC,
            dependencies=["paramiko"],
            external_programs=["vasp_std"],  # 需要 VASP
        )

    def get_tools(self):
        return [
            ToolSchema(
                name="dft_single_point",
                description="DFT 单点能量计算",
                parameters={...},
                is_async=True,
                timeout=7200,  # 2小时
            )
        ]

    def execute(self, tool_name, arguments):
        # 异步插件不实现 execute，通过 submit/poll/get_result
        raise NotImplementedError("此工具为异步工具，请使用 submit()")

    def submit(self, tool_name, arguments):
        # 1. 生成 VASP 输入文件
        # 2. SSH 上传到 HPC
        # 3. 提交 SLURM 作业
        # 4. 返回 task_id
        task_id = self._submit_to_hpc(tool_name, arguments)
        return task_id

    def poll(self, task_id):
        # SSH 检查作业状态
        status = self._check_slurm_status(task_id)
        return {"task_id": task_id, "status": status, "progress": 0.5}

    def get_result(self, task_id):
        # SSH 下载 OUTCAR，解析结果
        result = self._parse_vasp_output(task_id)
        return {"status": "success", **result}
```

---

## 七、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 第三方插件代码安全 | 恶意代码执行 | 沙盒执行 + 权限白名单 + 代码签名 |
| 异步任务积压 | 内存/线程耗尽 | 队列长度限制 + 优先级调度 + 超时清理 |
| HPC 连接不稳定 | 任务丢失 | SQLite 持久化 + 断线重连 + 状态恢复 |
| 依赖冲突 | 包版本不兼容 | 每个插件声明依赖 + 可选隔离环境 |
| 现有功能回归 | 引入bug | 插件系统与现有工具完全解耦，默认不加载任何插件 |

---

## 八、兼容性保证

1. **零侵入** — 不修改现有 26 个工具的任何逻辑
2. **渐进加载** — 插件目录为空时，系统行为与原来完全一致
3. **优雅降级** — 插件依赖缺失时自动跳过，不影响其他功能
4. **向后兼容** — 现有 SkillRegistry 动态技能系统保持不变
