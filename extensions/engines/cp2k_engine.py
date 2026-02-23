# -*- coding: utf-8 -*-
"""
CP2K 引擎
===========
开源混合高斯/平面波(GPW)DFT软件，擅长大体系和AIMD
https://www.cp2k.org/

输入文件: *.inp (块结构)
输出文件: *.out (标准输出)
"""

from extensions.engines.dft_engine import (
    DFTEngine, DFTTaskType, EngineCapability, InputFiles, ParsedResult
)
from typing import Dict, Any


class CP2KEngine(DFTEngine):
    """CP2K 计算引擎"""

    def get_capability(self) -> EngineCapability:
        return EngineCapability(
            engine_name="cp2k",
            display_name="CP2K",
            version="2024.x",
            description="开源混合高斯/平面波方法DFT软件，"
                        "擅长大体系（数千原子）和从头算分子动力学(AIMD)",
            supported_tasks=[
                DFTTaskType.SINGLE_POINT,
                DFTTaskType.OPTIMIZE,
                DFTTaskType.MD,
            ],
            executable="cp2k.psmp",
            license_type="GPL-2.0",
            website="https://www.cp2k.org/",
            file_format="Sectioned input (.inp)",
        )

    def generate_input(self, task_type: DFTTaskType,
                       structure: Dict[str, Any],
                       params: Dict[str, Any]) -> InputFiles:
        """生成 CP2K 输入文件"""
        elements = structure.get("elements", [])
        positions = structure.get("positions", [])
        cell = structure.get("cell", [[5, 0, 0], [0, 5, 0], [0, 0, 5]])
        unique_elems = list(dict.fromkeys(elements))

        run_type = {
            DFTTaskType.SINGLE_POINT: "ENERGY_FORCE",
            DFTTaskType.OPTIMIZE: "GEO_OPT",
            DFTTaskType.MD: "MD",
        }.get(task_type, "ENERGY_FORCE")

        cutoff = params.get("cutoff", 400)
        rel_cutoff = params.get("rel_cutoff", 60)
        xc_functional = params.get("xc_functional", "PBE")

        lines = [
            "&GLOBAL",
            "  PROJECT alloy_calc",
            f"  RUN_TYPE {run_type}",
            "  PRINT_LEVEL MEDIUM",
            "&END GLOBAL",
            "",
            "&FORCE_EVAL",
            "  METHOD Quickstep",
            "",
            "  &DFT",
            f"    BASIS_SET_FILE_NAME BASIS_MOLOPT",
            f"    POTENTIAL_FILE_NAME GTH_POTENTIALS",
            "",
            "    &QS",
            "      EPS_DEFAULT 1.0E-12",
            "    &END QS",
            "",
            "    &MGRID",
            f"      CUTOFF {cutoff}",
            f"      REL_CUTOFF {rel_cutoff}",
            "      NGRIDS 5",
            "    &END MGRID",
            "",
            "    &SCF",
            "      SCF_GUESS ATOMIC",
            f"      EPS_SCF {params.get('eps_scf', 1e-6)}",
            f"      MAX_SCF {params.get('max_scf', 200)}",
            "      &DIAGONALIZATION",
            "        ALGORITHM STANDARD",
            "      &END DIAGONALIZATION",
            "      &MIXING",
            "        METHOD BROYDEN_MIXING",
            f"        ALPHA {params.get('mixing_alpha', 0.4)}",
            "      &END MIXING",
            "    &END SCF",
            "",
            f"    &XC",
            f"      &XC_FUNCTIONAL {xc_functional}",
            f"      &END XC_FUNCTIONAL",
            f"    &END XC",
            "  &END DFT",
            "",
            "  &SUBSYS",
            "    &CELL",
        ]

        # 晶胞
        abc_labels = ["A", "B", "C"]
        for i, vec in enumerate(cell):
            lines.append(
                f"      {abc_labels[i]}  {vec[0]:.10f}  {vec[1]:.10f}  {vec[2]:.10f}"
            )
        lines.append("    &END CELL")
        lines.append("")

        # 原子坐标
        lines.append("    &COORD")
        for i, pos in enumerate(positions):
            lines.append(
                f"      {elements[i]}  {pos[0]:.10f}  {pos[1]:.10f}  {pos[2]:.10f}"
            )
        lines.append("    &END COORD")
        lines.append("")

        # 基组和赝势
        for elem in unique_elems:
            basis = params.get("basis_set", {}).get(elem, "DZVP-MOLOPT-SR-GTH")
            potential = params.get("potential", {}).get(elem, f"GTH-{xc_functional}")
            lines.extend([
                f"    &KIND {elem}",
                f"      BASIS_SET {basis}",
                f"      POTENTIAL {potential}",
                f"    &END KIND",
            ])

        lines.extend([
            "  &END SUBSYS",
            "&END FORCE_EVAL",
        ])

        # MD 参数
        if task_type == DFTTaskType.MD:
            temp = params.get("temperature", 300)
            nsteps = params.get("nstep", 1000)
            timestep = params.get("timestep", 0.5)
            lines.extend([
                "",
                "&MOTION",
                "  &MD",
                "    ENSEMBLE NVT",
                f"    STEPS {nsteps}",
                f"    TIMESTEP {timestep}",
                f"    TEMPERATURE {temp}",
                "    &THERMOSTAT",
                "      TYPE NOSE",
                f"      &NOSE",
                f"        TIMECON {params.get('timecon', 100)}",
                f"      &END NOSE",
                "    &END THERMOSTAT",
                "  &END MD",
                "&END MOTION",
            ])
        elif task_type == DFTTaskType.OPTIMIZE:
            lines.extend([
                "",
                "&MOTION",
                "  &GEO_OPT",
                f"    MAX_ITER {params.get('max_iter', 100)}",
                f"    MAX_FORCE {params.get('max_force', 1e-4)}",
                "    OPTIMIZER BFGS",
                "  &END GEO_OPT",
                "&END MOTION",
            ])

        files = {"input.inp": "\n".join(lines) + "\n"}

        return InputFiles(
            files=files,
            work_dir_name=f"cp2k_{task_type.value}",
            notes="基组文件 BASIS_MOLOPT 和赝势文件 GTH_POTENTIALS "
                  "需从 CP2K data 目录获取",
        )

    def parse_output(self, task_type: DFTTaskType,
                     output_files: Dict[str, str]) -> ParsedResult:
        """解析 CP2K 输出"""
        result = ParsedResult()
        output = output_files.get("output.out", "")
        if not output:
            return result

        ha_to_ev = 27.2114
        lines = output.strip().split("\n")

        for line in reversed(lines):
            if "ENERGY| Total FORCE_EVAL" in line:
                try:
                    energy_ha = float(line.split()[-1])
                    result.total_energy_eV = energy_ha * ha_to_ev
                except (ValueError, IndexError):
                    pass
                break

        for line in reversed(lines):
            if "SCF run converged" in line:
                result.converged = True
                break
        else:
            result.converged = False

        return result

    def get_run_command(self, task_type: DFTTaskType,
                       n_cores: int = 1) -> str:
        if n_cores > 1:
            return f"mpirun -np {n_cores} cp2k.psmp -i input.inp -o output.out"
        return "cp2k.sopt -i input.inp -o output.out"

    def estimate_time(self, task_type: DFTTaskType,
                      n_atoms: int,
                      params: Dict[str, Any]) -> Dict[str, Any]:
        """CP2K 线性标度，大体系相对快"""
        base = {
            DFTTaskType.SINGLE_POINT: 200,
            DFTTaskType.OPTIMIZE: 1200,
            DFTTaskType.MD: 3600,
        }.get(task_type, 1800)
        # CP2K 对大体系有优势，标度更接近线性
        scale = max(1, n_atoms / 8)
        return {"estimated_seconds": int(base * scale), "confidence": "low"}
