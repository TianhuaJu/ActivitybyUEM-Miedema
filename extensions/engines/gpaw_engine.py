# -*- coding: utf-8 -*-
"""
GPAW 引擎
===========
基于 Python 的开源 DFT 软件，与 ASE 深度集成
https://wiki.fysik.dtu.dk/gpaw/

特点: 纯 Python 接口，可直接本地调用（无需 SSH）
输入: Python 脚本
输出: JSON / gpw 文件
"""

from extensions.engines.dft_engine import (
    DFTEngine, DFTTaskType, EngineCapability, InputFiles, ParsedResult
)
from typing import Dict, Any


class GPAWEngine(DFTEngine):
    """GPAW 计算引擎（支持本地 Python 直接调用）"""

    def get_capability(self) -> EngineCapability:
        return EngineCapability(
            engine_name="gpaw",
            display_name="GPAW",
            version="24.x",
            description="基于Python的开源DFT软件，采用PAW方法，"
                        "与ASE深度集成，支持实空间/平面波/LCAO三种模式，"
                        "可直接通过Python API本地调用",
            supported_tasks=[
                DFTTaskType.SINGLE_POINT,
                DFTTaskType.OPTIMIZE,
                DFTTaskType.DOS,
                DFTTaskType.BAND,
            ],
            executable="gpaw",
            license_type="GPL-3.0",
            website="https://wiki.fysik.dtu.dk/gpaw/",
            file_format="Python script",
            python_bindings=True,
        )

    def generate_input(self, task_type: DFTTaskType,
                       structure: Dict[str, Any],
                       params: Dict[str, Any]) -> InputFiles:
        """生成 GPAW Python 脚本"""
        elements = structure.get("elements", [])
        positions = structure.get("positions", [])
        cell = structure.get("cell", [[5, 0, 0], [0, 5, 0], [0, 0, 5]])

        mode = params.get("mode", "pw")
        encut = params.get("encut", 400)
        kpts_str = params.get("kpoints", "6 6 6")
        kpts = tuple(int(k) for k in kpts_str.split())
        xc = params.get("xc", "PBE")

        # 构建 Python 脚本
        script_lines = [
            "# GPAW 计算脚本 - AlloyThermolCal Pro 自动生成",
            "from ase import Atoms",
            "from gpaw import GPAW, PW",
        ]

        if task_type == DFTTaskType.OPTIMIZE:
            script_lines.append("from ase.optimize import BFGS")

        # 构造原子体系
        script_lines.extend([
            "",
            f"atoms = Atoms(",
            f"    symbols={elements!r},",
            f"    positions={positions!r},",
            f"    cell={cell!r},",
            f"    pbc=True,",
            f")",
            "",
        ])

        # 计算器设置
        if mode == "pw":
            script_lines.append(
                f"calc = GPAW(mode=PW({encut}), xc='{xc}', "
                f"kpts={kpts!r}, txt='gpaw.txt')"
            )
        elif mode == "lcao":
            basis = params.get("basis", "dzp")
            script_lines.append(
                f"calc = GPAW(mode='lcao', basis='{basis}', xc='{xc}', "
                f"kpts={kpts!r}, txt='gpaw.txt')"
            )
        else:
            h = params.get("h", 0.18)
            script_lines.append(
                f"calc = GPAW(mode='fd', h={h}, xc='{xc}', "
                f"kpts={kpts!r}, txt='gpaw.txt')"
            )

        script_lines.extend([
            "atoms.calc = calc",
            "",
        ])

        if task_type == DFTTaskType.SINGLE_POINT:
            script_lines.extend([
                "energy = atoms.get_potential_energy()",
                "forces = atoms.get_forces()",
                "print(f'Total energy: {energy:.6f} eV')",
                "print(f'Max force: {max(abs(f) for row in forces for f in row):.6f} eV/A')",
                "calc.write('result.gpw')",
            ])
        elif task_type == DFTTaskType.OPTIMIZE:
            fmax = params.get("fmax", 0.01)
            script_lines.extend([
                f"opt = BFGS(atoms, logfile='opt.log', trajectory='opt.traj')",
                f"opt.run(fmax={fmax})",
                "energy = atoms.get_potential_energy()",
                "print(f'Optimized energy: {energy:.6f} eV')",
                "calc.write('result.gpw')",
            ])
        elif task_type == DFTTaskType.DOS:
            script_lines.extend([
                "energy = atoms.get_potential_energy()",
                "dos = calc.get_dos()",
                "energies = dos.get_energies()",
                "weights = dos.get_weights()",
                "import numpy as np",
                "np.savetxt('dos.dat', np.column_stack([energies, weights]))",
                "print(f'Total energy: {energy:.6f} eV')",
                "calc.write('result.gpw')",
            ])

        files = {"gpaw_calc.py": "\n".join(script_lines) + "\n"}

        return InputFiles(
            files=files,
            work_dir_name=f"gpaw_{task_type.value}",
            notes="需安装 GPAW: pip install gpaw。"
                  "PAW datasets 需通过 gpaw install-data 安装",
        )

    def parse_output(self, task_type: DFTTaskType,
                     output_files: Dict[str, str]) -> ParsedResult:
        """解析 GPAW 输出"""
        result = ParsedResult()
        output = output_files.get("gpaw.txt", "")
        if not output:
            return result

        lines = output.strip().split("\n")

        for line in reversed(lines):
            if "Free energy:" in line or "Extrapolated:" in line:
                try:
                    result.total_energy_eV = float(line.split()[-1])
                except (ValueError, IndexError):
                    pass
                break

        for line in reversed(lines):
            if "Converged after" in line:
                result.converged = True
                try:
                    result.n_iterations = int(line.split("after")[1].split()[0])
                except (ValueError, IndexError):
                    pass
                break
        else:
            result.converged = False

        return result

    def get_run_command(self, task_type: DFTTaskType,
                       n_cores: int = 1) -> str:
        if n_cores > 1:
            return f"mpirun -np {n_cores} gpaw python gpaw_calc.py"
        return "gpaw python gpaw_calc.py"

    def estimate_time(self, task_type: DFTTaskType,
                      n_atoms: int,
                      params: Dict[str, Any]) -> Dict[str, Any]:
        mode = params.get("mode", "pw")
        base = {
            DFTTaskType.SINGLE_POINT: 200 if mode == "lcao" else 400,
            DFTTaskType.OPTIMIZE: 1200,
            DFTTaskType.DOS: 500,
            DFTTaskType.BAND: 800,
        }.get(task_type, 1800)
        scale = max(1, n_atoms / 4)
        return {"estimated_seconds": int(base * scale), "confidence": "low"}
