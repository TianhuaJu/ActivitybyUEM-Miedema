# -*- coding: utf-8 -*-
"""
ASE Adapter - 原子模拟环境适配器
==================================
通过 ASE (Atomic Simulation Environment) 提供轻量级 DFT/MD 计算能力。
支持 EMT、EAM 等经验势的快速模拟，适合教学演示和快速筛选。

依赖: pip install ase
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from extensions.base import (
    CalculationPlugin, PluginMetadata, PluginType, ToolSchema
)
from typing import Dict, List, Any


class ASEAdapter(CalculationPlugin):
    """ASE 轻量原子模拟适配器（同步插件）"""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="ase_lite",
            display_name="ASE 原子模拟",
            version="0.1.0",
            description="基于 ASE 的轻量级原子模拟工具，支持 EMT 势的结构优化、"
                        "单点能量和简单分子动力学",
            author="AlloyThermolCal Pro",
            plugin_type=PluginType.SYNC,
            dependencies=["ase"],
            category="md",
        )

    def get_tools(self) -> List[ToolSchema]:
        return [
            ToolSchema(
                name="single_point_energy",
                description="使用 EMT 势计算金属体系的单点能量（支持 Al, Cu, Ag, Au, Ni, Pd, Pt）",
                parameters={
                    "type": "object",
                    "properties": {
                        "element": {
                            "type": "string",
                            "description": "元素符号，如 'Cu', 'Al'",
                        },
                        "structure": {
                            "type": "string",
                            "description": "晶体结构类型",
                            "enum": ["fcc", "bcc", "hcp"],
                            "default": "fcc",
                        },
                        "lattice_constant": {
                            "type": "number",
                            "description": "晶格常数 (Å)。若不提供则使用默认值",
                        },
                    },
                    "required": ["element"],
                },
                timeout=10,
            ),
            ToolSchema(
                name="optimize_structure",
                description="使用 EMT 势进行结构优化（弛豫），返回优化后的能量和晶格常数",
                parameters={
                    "type": "object",
                    "properties": {
                        "element": {
                            "type": "string",
                            "description": "元素符号",
                        },
                        "structure": {
                            "type": "string",
                            "enum": ["fcc", "bcc", "hcp"],
                            "default": "fcc",
                        },
                    },
                    "required": ["element"],
                },
                timeout=15,
            ),
            ToolSchema(
                name="equation_of_state",
                description="计算状态方程 (EOS)：在不同体积下计算能量，拟合 Birch-Murnaghan EOS，"
                            "得到平衡体积、体模量等",
                parameters={
                    "type": "object",
                    "properties": {
                        "element": {
                            "type": "string",
                            "description": "元素符号",
                        },
                        "structure": {
                            "type": "string",
                            "enum": ["fcc", "bcc", "hcp"],
                            "default": "fcc",
                        },
                        "num_points": {
                            "type": "integer",
                            "description": "拟合点数",
                            "default": 7,
                        },
                    },
                    "required": ["element"],
                },
                timeout=20,
            ),
            ToolSchema(
                name="md_nvt",
                description="NVT 系综分子动力学模拟（Langevin 恒温器），返回温度/能量随时间变化",
                parameters={
                    "type": "object",
                    "properties": {
                        "element": {
                            "type": "string",
                            "description": "元素符号",
                        },
                        "temperature": {
                            "type": "number",
                            "description": "目标温度 (K)",
                            "default": 300,
                        },
                        "steps": {
                            "type": "integer",
                            "description": "模拟步数",
                            "default": 100,
                        },
                        "timestep": {
                            "type": "number",
                            "description": "时间步长 (fs)",
                            "default": 1.0,
                        },
                        "supercell_size": {
                            "type": "integer",
                            "description": "超胞倍数 (NxNxN)",
                            "default": 3,
                        },
                    },
                    "required": ["element"],
                },
                timeout=30,
            ),
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行 ASE 计算"""
        dispatch = {
            "single_point_energy": self._single_point,
            "optimize_structure": self._optimize,
            "equation_of_state": self._eos,
            "md_nvt": self._md_nvt,
        }
        handler = dispatch.get(tool_name)
        if not handler:
            return {"status": "error", "message": f"未知工具: {tool_name}"}
        return handler(**arguments)

    # ==================== 工具实现 ====================

    def _single_point(self, element: str, structure: str = "fcc",
                      lattice_constant: float = None) -> Dict[str, Any]:
        """单点能量计算"""
        try:
            from ase.build import bulk
            from ase.calculators.emt import EMT
        except ImportError:
            return {"status": "error", "message": "请先安装 ASE: pip install ase"}

        kwargs = {"crystalstructure": structure}
        if lattice_constant:
            kwargs["a"] = lattice_constant

        try:
            atoms = bulk(element, **kwargs)
            atoms.calc = EMT()
            energy = atoms.get_potential_energy()
            forces = atoms.get_forces()
            max_force = float(max(abs(f) for row in forces for f in row))
        except Exception as e:
            return {"status": "error", "message": f"计算失败: {e}"}

        return {
            "status": "success",
            "element": element,
            "structure": structure,
            "energy_eV": round(energy, 6),
            "energy_per_atom_eV": round(energy / len(atoms), 6),
            "max_force_eV_A": round(max_force, 6),
            "n_atoms": len(atoms),
            "cell_A": [round(x, 4) for x in atoms.cell.lengths().tolist()],
        }

    def _optimize(self, element: str,
                  structure: str = "fcc") -> Dict[str, Any]:
        """结构优化"""
        try:
            from ase.build import bulk
            from ase.calculators.emt import EMT
            from ase.optimize import BFGS
            from ase.constraints import StrainFilter
        except ImportError:
            return {"status": "error", "message": "请先安装 ASE: pip install ase"}

        try:
            atoms = bulk(element, crystalstructure=structure)
            atoms.calc = EMT()
            initial_energy = atoms.get_potential_energy()

            sf = StrainFilter(atoms)
            opt = BFGS(sf, logfile=None)
            opt.run(fmax=0.01, steps=100)

            final_energy = atoms.get_potential_energy()
        except Exception as e:
            return {"status": "error", "message": f"优化失败: {e}"}

        return {
            "status": "success",
            "element": element,
            "structure": structure,
            "initial_energy_eV": round(initial_energy, 6),
            "final_energy_eV": round(final_energy, 6),
            "energy_per_atom_eV": round(final_energy / len(atoms), 6),
            "optimized_cell_A": [round(x, 4)
                                 for x in atoms.cell.lengths().tolist()],
            "converged": opt.converged(),
            "steps": opt.nsteps,
        }

    def _eos(self, element: str, structure: str = "fcc",
             num_points: int = 7) -> Dict[str, Any]:
        """状态方程拟合"""
        try:
            from ase.build import bulk
            from ase.calculators.emt import EMT
            from ase.eos import EquationOfState
            import numpy as np
        except ImportError:
            return {"status": "error",
                    "message": "请先安装 ASE 和 numpy: pip install ase numpy"}

        try:
            atoms = bulk(element, crystalstructure=structure)
            atoms.calc = EMT()
            cell = atoms.cell.copy()
            volumes = []
            energies = []

            for scale in np.linspace(0.90, 1.10, num_points):
                a = atoms.copy()
                a.set_cell(cell * scale, scale_atoms=True)
                a.calc = EMT()
                volumes.append(a.get_volume())
                energies.append(a.get_potential_energy())

            eos = EquationOfState(volumes, energies, eos="birchmurnaghan")
            v0, e0, B = eos.fit()
            B_GPa = B / 1.602176634e-19 * 1e-30 / 1e9  # eV/Å³ → GPa
        except Exception as e:
            return {"status": "error", "message": f"EOS 拟合失败: {e}"}

        return {
            "status": "success",
            "element": element,
            "structure": structure,
            "equilibrium_volume_A3": round(float(v0), 4),
            "equilibrium_energy_eV": round(float(e0), 6),
            "bulk_modulus_GPa": round(float(B_GPa), 2),
            "num_points": num_points,
            "volumes_A3": [round(v, 4) for v in volumes],
            "energies_eV": [round(e, 6) for e in energies],
        }

    def _md_nvt(self, element: str, temperature: float = 300,
                steps: int = 100, timestep: float = 1.0,
                supercell_size: int = 3) -> Dict[str, Any]:
        """NVT 分子动力学"""
        try:
            from ase.build import bulk
            from ase.calculators.emt import EMT
            from ase.md.langevin import Langevin
            from ase import units
            import numpy as np
        except ImportError:
            return {"status": "error",
                    "message": "请先安装 ASE 和 numpy: pip install ase numpy"}

        try:
            atoms = bulk(element, crystalstructure="fcc")
            atoms = atoms.repeat((supercell_size, supercell_size, supercell_size))
            atoms.calc = EMT()

            from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
            MaxwellBoltzmannDistribution(atoms, temperature_K=temperature)

            dyn = Langevin(
                atoms,
                timestep=timestep * units.fs,
                temperature_K=temperature,
                friction=0.01 / units.fs,
                logfile=None,
            )

            temps = []
            energies = []
            sample_interval = max(1, steps // 20)

            for i in range(steps):
                dyn.run(1)
                if i % sample_interval == 0:
                    ke = atoms.get_kinetic_energy()
                    pe = atoms.get_potential_energy()
                    t = 2 * ke / (3 * len(atoms) * units.kB)
                    temps.append(round(float(t), 1))
                    energies.append(round(float(ke + pe), 4))

        except Exception as e:
            return {"status": "error", "message": f"MD 模拟失败: {e}"}

        return {
            "status": "success",
            "element": element,
            "target_temperature_K": temperature,
            "n_atoms": len(atoms),
            "total_steps": steps,
            "timestep_fs": timestep,
            "total_time_ps": round(steps * timestep / 1000, 3),
            "avg_temperature_K": round(float(np.mean(temps)), 1),
            "std_temperature_K": round(float(np.std(temps)), 1),
            "final_energy_eV": energies[-1] if energies else None,
            "temperature_trajectory_K": temps,
            "energy_trajectory_eV": energies,
        }
