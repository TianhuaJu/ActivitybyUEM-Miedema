# -*- coding: utf-8 -*-
"""
Quantum ESPRESSO 引擎
=======================
开源平面波DFT软件
https://www.quantum-espresso.org/

输入文件: *.in (Fortran namelist 格式)
输出文件: *.out (标准输出)
"""

from extensions.engines.dft_engine import (
    DFTEngine, DFTTaskType, EngineCapability, InputFiles, ParsedResult
)
from typing import Dict, Any


class QEEngine(DFTEngine):
    """Quantum ESPRESSO 计算引擎"""

    def get_capability(self) -> EngineCapability:
        return EngineCapability(
            engine_name="qe",
            display_name="Quantum ESPRESSO",
            version="7.x",
            description="开源平面波赝势DFT软件，支持超软赝势和PAW，"
                        "模块化设计（pw.x/ph.x/pp.x等）",
            supported_tasks=[
                DFTTaskType.SINGLE_POINT,
                DFTTaskType.OPTIMIZE,
                DFTTaskType.DOS,
                DFTTaskType.BAND,
                DFTTaskType.PHONON,
                DFTTaskType.MD,
            ],
            executable="pw.x",
            license_type="GPL-2.0",
            website="https://www.quantum-espresso.org/",
            file_format="Fortran namelist (.in)",
        )

    def generate_input(self, task_type: DFTTaskType,
                       structure: Dict[str, Any],
                       params: Dict[str, Any]) -> InputFiles:
        """生成 Quantum ESPRESSO pw.x 输入文件"""
        elements = structure.get("elements", [])
        positions = structure.get("positions", [])
        cell = structure.get("cell", [[5, 0, 0], [0, 5, 0], [0, 0, 5]])
        unique_elems = list(dict.fromkeys(elements))

        ecutwfc = params.get("ecutwfc", params.get("encut", 400) / 13.6057)
        ecutrho = params.get("ecutrho", ecutwfc * 8)

        # 任务类型映射
        calc_map = {
            DFTTaskType.SINGLE_POINT: "scf",
            DFTTaskType.OPTIMIZE: "relax",
            DFTTaskType.DOS: "nscf",
            DFTTaskType.BAND: "bands",
            DFTTaskType.MD: "md",
        }
        calculation = calc_map.get(task_type, "scf")

        lines = []
        lines.append("&CONTROL")
        lines.append(f"  calculation = '{calculation}',")
        lines.append("  pseudo_dir = './pseudo/',")
        lines.append("  outdir = './tmp/',")
        lines.append("  prefix = 'alloy',")
        if task_type == DFTTaskType.OPTIMIZE:
            lines.append(f"  forc_conv_thr = {params.get('forc_conv_thr', 1e-3)},")
        lines.append("/")

        lines.append("&SYSTEM")
        lines.append(f"  ibrav = 0,")
        lines.append(f"  nat = {len(elements)},")
        lines.append(f"  ntyp = {len(unique_elems)},")
        lines.append(f"  ecutwfc = {ecutwfc:.1f},")
        lines.append(f"  ecutrho = {ecutrho:.1f},")
        lines.append(f"  occupations = '{params.get('occupations', 'smearing')}',")
        lines.append(f"  smearing = '{params.get('smearing', 'mv')}',")
        lines.append(f"  degauss = {params.get('degauss', 0.02)},")
        lines.append("/")

        lines.append("&ELECTRONS")
        lines.append(f"  conv_thr = {params.get('conv_thr', 1e-8)},")
        lines.append(f"  mixing_beta = {params.get('mixing_beta', 0.7)},")
        lines.append("/")

        if task_type == DFTTaskType.OPTIMIZE:
            lines.append("&IONS")
            lines.append(f"  ion_dynamics = '{params.get('ion_dynamics', 'bfgs')}',")
            lines.append("/")
        elif task_type == DFTTaskType.MD:
            lines.append("&IONS")
            lines.append("  ion_dynamics = 'verlet',")
            dt_au = params.get("dt", 20.0)
            lines.append(f"  dt = {dt_au},")
            lines.append(f"  nstep = {params.get('nstep', 100)},")
            lines.append(f"  tempw = {params.get('temperature', 300)},")
            lines.append("/")

        # ATOMIC_SPECIES (赝势文件名需用户配置)
        lines.append("ATOMIC_SPECIES")
        for elem in unique_elems:
            mass = params.get("masses", {}).get(elem, 1.0)
            lines.append(f"  {elem}  {mass}  {elem}.UPF")

        # CELL_PARAMETERS (angstrom)
        lines.append("CELL_PARAMETERS angstrom")
        for vec in cell:
            lines.append(f"  {vec[0]:.10f}  {vec[1]:.10f}  {vec[2]:.10f}")

        # ATOMIC_POSITIONS (angstrom)
        lines.append("ATOMIC_POSITIONS angstrom")
        for i, pos in enumerate(positions):
            lines.append(f"  {elements[i]}  {pos[0]:.10f}  {pos[1]:.10f}  {pos[2]:.10f}")

        # K_POINTS
        kpts = params.get("kpoints", "6 6 6")
        lines.append("K_POINTS automatic")
        lines.append(f"  {kpts}  0 0 0")

        pw_input = "\n".join(lines) + "\n"
        files = {"pw.in": pw_input}

        return InputFiles(
            files=files,
            work_dir_name=f"qe_{task_type.value}",
            notes="赝势文件（*.UPF）需放入 pseudo/ 目录，"
                  "可从 https://www.quantum-espresso.org/pseudopotentials 下载",
        )

    def parse_output(self, task_type: DFTTaskType,
                     output_files: Dict[str, str]) -> ParsedResult:
        """解析 QE pw.x 输出"""
        result = ParsedResult()
        output = output_files.get("pw.out", "")
        if not output:
            return result

        lines = output.strip().split("\n")

        # 解析总能量（Ry → eV）
        ry_to_ev = 13.6057
        for line in reversed(lines):
            if "!" in line and "total energy" in line:
                try:
                    energy_ry = float(line.split("=")[1].strip().split()[0])
                    result.total_energy_eV = energy_ry * ry_to_ev
                except (ValueError, IndexError):
                    pass
                break

        # 收敛检查
        for line in reversed(lines):
            if "convergence has been achieved" in line:
                result.converged = True
                break
        else:
            result.converged = False

        # 原子数
        for line in lines:
            if "number of atoms/cell" in line:
                try:
                    n_atoms = int(line.split("=")[1].strip())
                    if result.total_energy_eV is not None:
                        result.energy_per_atom_eV = result.total_energy_eV / n_atoms
                except (ValueError, IndexError):
                    pass
                break

        return result

    def get_run_command(self, task_type: DFTTaskType,
                       n_cores: int = 1) -> str:
        exe = "pw.x"
        if task_type == DFTTaskType.PHONON:
            exe = "ph.x"
        if n_cores > 1:
            return f"mpirun -np {n_cores} {exe} -in pw.in > pw.out"
        return f"{exe} -in pw.in > pw.out"

    def estimate_time(self, task_type: DFTTaskType,
                      n_atoms: int,
                      params: Dict[str, Any]) -> Dict[str, Any]:
        base = {
            DFTTaskType.SINGLE_POINT: 300,
            DFTTaskType.OPTIMIZE: 1800,
            DFTTaskType.DOS: 600,
            DFTTaskType.PHONON: 7200,
            DFTTaskType.MD: 7200,
        }.get(task_type, 3600)
        scale = max(1, n_atoms / 4)
        return {"estimated_seconds": int(base * scale), "confidence": "low"}
