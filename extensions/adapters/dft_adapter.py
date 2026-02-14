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
    """

    def __init__(self):
        self._engines: Dict[str, DFTEngine] = {}
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
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """同步执行 DFT 工具"""
        dispatch = {
            "list_engines": self._list_engines,
            "generate_input": self._generate_input,
            "parse_output": self._parse_output,
            "estimate_time": self._estimate_time,
            "generate_submit_script": self._generate_submit_script,
            "compare_engines": self._compare_engines,
        }
        handler = dispatch.get(tool_name)
        if not handler:
            return {"status": "error", "message": f"未知工具: {tool_name}"}
        try:
            return handler(**arguments)
        except Exception as e:
            return {"status": "error", "message": str(e)}

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
