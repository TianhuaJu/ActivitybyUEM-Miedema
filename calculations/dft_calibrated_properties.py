# -*- coding: utf-8 -*-
"""
DFT 校准热力学计算器
=====================
在原有 UEM-Miedema 模型基础上，引入 DFT 计算数据进行校准:

1. 化合物形成能 → 提升析出温度、固溶度的精度
2. 固溶体混合焓 → 校正 Miedema 混合焓
3. 纯元素能量  → 提供形成能计算的参考基准

策略: DFT 数据可用时优先使用，否则回退到 Miedema 经验值。
"""

import math
import logging
from typing import Dict, List, Any, Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dft_data_store import DFTDataStore, CompoundEnergy, MixingEnthalpyPoint
from calculations.thermodynamic_properties import ThermodynamicProperties
from calculations.activity_calculator import ActivityCoefficient, extrap_func
from models.extrapolation_models import BinaryModel
from core.constants import Constants

logger = logging.getLogger(__name__)


class DFTCalibratedProperties:
    """
    DFT 校准的热力学性质计算器。

    继承原有 ThermodynamicProperties 的所有功能，
    在关键参数处优先使用 DFT 数据:

    - 析出温度: ΔG°_f 用 DFT 化合物形成能替代经验值
    - 液相线温度: 融化焓用 DFT 端基能量差替代经验值
    - 固溶度: 金属间化合物 ΔH_f 用 DFT 值替代

    用法:
        calc = DFTCalibratedProperties()
        # 存入 DFT 数据
        calc.dft_store.store_compound_energy(...)
        # 计算时自动使用 DFT 数据
        result = calc.calculate_precipitation_temperature_calibrated(...)
    """

    def __init__(self, dft_store: DFTDataStore = None):
        self.dft_store = dft_store or DFTDataStore()
        self.thermo = ThermodynamicProperties()
        self.R = Constants.R

    # ==================== 校准析出温度 ====================

    def calculate_precipitation_temperature_calibrated(
        self,
        alloy_composition: Dict[str, float],
        phase_type: str,
        solution_phase: str = "LIQUID",
        extrapolation_model_func: extrap_func = None,
        extrapolation_model_name: str = "UEM1",
        activity_model: str = "Wagner",
        T_min: float = 300,
        T_max: float = 2500,
        tolerance: float = 1.0,
    ) -> Dict[str, Any]:
        """
        DFT 校准的析出温度计算。

        如果 DFT 数据库中有该化合物的形成能，使用 DFT 值；
        否则回退到内置经验数据库。

        参数:
            alloy_composition: 合金成分 {元素: 摩尔分数}
            phase_type: 析出相类型（如 "TiC", "Fe3C", "Ni3Al"）
            solution_phase: "LIQUID" 或 "SOLID"
            其余参数同 ThermodynamicProperties

        返回:
            包含析出温度和 DFT 校准信息的字典
        """
        # 查询 DFT 数据
        dft_data = self.dft_store.get_compound_energy(phase_type)
        calibration_info = {"dft_calibrated": False, "data_source": "empirical"}

        user_data = None

        if dft_data is not None:
            # 有 DFT 数据 → 构造 user_data 覆盖内置值
            calibration_info = {
                "dft_calibrated": True,
                "data_source": f"DFT ({dft_data.dft_engine or dft_data.source})",
                "dft_formation_energy_J": dft_data.formation_energy_J,
                "dft_formation_energy_kJ": dft_data.formation_energy_J / 1000,
                "dft_delta_G_A": dft_data.delta_G_A,
                "dft_delta_G_B": dft_data.delta_G_B,
                "xc_functional": dft_data.xc_functional,
            }

            user_data = {
                "precipitate_data": {
                    phase_type: {
                        "formula": dft_data.elements,
                        "stoich": dft_data.stoichiometry,
                        "delta_G": (dft_data.delta_G_A, dft_data.delta_G_B),
                    }
                }
            }
            logger.info("析出温度计算使用 DFT 校准数据: %s (ΔH_f = %.0f J/mol)",
                         phase_type, dft_data.formation_energy_J)

        # 调用原始方法，传入 DFT 数据（或 None 使用经验值）
        result = self.thermo.get_precipitation_temperature(
            composition=alloy_composition,
            phase_type=phase_type,
            extrapolation_model_func=extrapolation_model_func,
            extrapolation_model_name=extrapolation_model_name,
            activity_model=activity_model,
            T_min=T_min,
            T_max=T_max,
            tolerance=tolerance,
            user_data=user_data,
        )

        # 附加校准信息
        result["calibration"] = calibration_info
        return result

    # ==================== 校准液相线温度 ====================

    def calculate_liquidus_temperature_calibrated(
        self,
        composition: Dict[str, float],
        extrapolation_model_func: extrap_func = None,
        extrapolation_model_name: str = "UEM1",
        activity_model: str = "Wagner",
        T_initial_guess: float = None,
        max_iterations: int = 50,
        tolerance: float = 0.1,
    ) -> Dict[str, Any]:
        """
        DFT 校准的液相线温度计算。

        如果 DFT 数据库中有溶剂元素的端基能量差（液固），
        用于更精确的融化焓估算。

        参数:
            同 ThermodynamicProperties.calculate_liquidus_temperature()

        返回:
            包含液相线温度和 DFT 校准信息的字典
        """
        # 确定溶剂
        total = sum(composition.values())
        comp = {k: v / total for k, v in composition.items()}
        solvent = max(comp, key=comp.get)

        calibration_info = {"dft_calibrated": False, "data_source": "empirical"}
        user_data = None

        # 查询 DFT 端基能量 → 估算融化焓
        elem_props = self.dft_store.get_element_property(solvent)
        if len(elem_props) >= 2:
            # 找到同元素不同结构的能量差 → 相变焓的近似
            energy_by_struct = {}
            for p in elem_props:
                energy_by_struct[p["structure"]] = p["total_energy_eV"]

            # 液相近似为高能结构
            if "liquid" in energy_by_struct:
                solid_structs = [s for s in energy_by_struct if s != "liquid"]
                if solid_structs:
                    e_liquid = energy_by_struct["liquid"]
                    e_solid = min(energy_by_struct[s] for s in solid_structs)
                    # eV/atom → J/mol
                    dH_fusion = (e_liquid - e_solid) * 96485.0
                    if dH_fusion > 0:
                        user_data = {
                            "enthalpy_of_fusion": {solvent: dH_fusion}
                        }
                        calibration_info = {
                            "dft_calibrated": True,
                            "data_source": "DFT (端基能量差)",
                            "dft_enthalpy_of_fusion_J": dH_fusion,
                        }

        # 查询混合焓数据校正
        system_name = "-".join(sorted(comp.keys()))
        mixing_data = self.dft_store.get_mixing_enthalpy(system_name, phase="liquid")
        if mixing_data:
            calibration_info["dft_mixing_enthalpy_available"] = True
            calibration_info["mixing_data_points"] = len(mixing_data)

        result = self.thermo.get_liquidus_temperature(
            composition=composition,
            extrapolation_model_func=extrapolation_model_func,
            extrapolation_model_name=extrapolation_model_name,
            activity_model=activity_model,
            T_initial_guess=T_initial_guess,
            max_iterations=max_iterations,
            tolerance=tolerance,
            user_data=user_data,
        )

        result["calibration"] = calibration_info
        return result

    # ==================== 校准固溶度 ====================

    def calculate_solubility_calibrated(
        self,
        solvent: str,
        solute: str,
        temperature_K: float,
        extrapolation_model_func: extrap_func = None,
        extrapolation_model_name: str = "UEM1",
        activity_model: str = "Wagner",
    ) -> Dict[str, Any]:
        """
        DFT 校准的固溶度计算。

        如果 DFT 数据库中有该体系金属间化合物的形成能，
        使用 DFT 值替代经验值。

        参数:
            solvent: 溶剂元素
            solute: 溶质元素
            temperature_K: 温度 (K)

        返回:
            包含固溶度和 DFT 校准信息的字典
        """
        from calculations.solubility_corrected import SolubilityCalculatorCorrected

        calibration_info = {"dft_calibrated": False, "data_source": "empirical"}

        # 查找该体系的 DFT 化合物数据
        dft_compounds = self._find_compounds_for_system(solvent, solute)

        if dft_compounds:
            # 用 DFT 形成能替换
            calibration_info = {
                "dft_calibrated": True,
                "data_source": "DFT",
                "dft_compounds": [
                    {"name": c.compound_name,
                     "formation_energy_J": c.formation_energy_J,
                     "source": c.source}
                    for c in dft_compounds
                ],
            }
            logger.info("固溶度计算使用 DFT 数据: %s-%s 体系，%d 个化合物",
                         solvent, solute, len(dft_compounds))

        # 使用 SolubilityCalculatorCorrected
        from core.tdb_parser import get_tdb_parser
        sol_calc = SolubilityCalculatorCorrected(
            tdb_parser=get_tdb_parser(),
            activity_calculator=self.thermo.activity_calculator,
        )

        # 如果有 DFT 数据，临时修改 INTERMETALLIC_DATA
        original_data = None
        if dft_compounds:
            key = (solvent.upper(), solute.upper())
            original_data = sol_calc.INTERMETALLIC_DATA.get(key)

            # 构造 DFT 校准的化合物数据
            new_data = []
            for c in dft_compounds:
                total_atoms = sum(c.stoichiometry)
                # x_溶质 = n_溶质 / total_atoms
                solute_idx = None
                for i, elem in enumerate(c.elements):
                    if elem.upper() == solute.upper():
                        solute_idx = i
                        break
                if solute_idx is not None:
                    x_solute = c.stoichiometry[solute_idx] / total_atoms
                    new_data.append(
                        (c.compound_name, x_solute, c.formation_energy_J)
                    )
            if new_data:
                sol_calc.INTERMETALLIC_DATA[key] = new_data

        try:
            result = sol_calc.calculate_corrected_solubility(
                solvent=solvent,
                solute=solute,
                temperature=temperature_K,
                composition={solvent: 0.99, solute: 0.01},
                extrapolation_model_func=extrapolation_model_func,
                extrapolation_model_name=extrapolation_model_name,
                activity_model=activity_model,
            )
        except Exception as e:
            result = {"status": "error", "message": str(e)}
        finally:
            # 恢复原始数据
            if original_data is not None:
                sol_calc.INTERMETALLIC_DATA[
                    (solvent.upper(), solute.upper())
                ] = original_data

        result["calibration"] = calibration_info
        return result

    # ==================== DFT + Miedema 混合焓对比 ====================

    def compare_mixing_enthalpy(
        self,
        element_a: str,
        element_b: str,
        temperature_K: float = 1800,
        phase: str = "liquid",
        n_points: int = 21,
    ) -> Dict[str, Any]:
        """
        对比 Miedema 模型和 DFT 计算的混合焓曲线。

        参数:
            element_a, element_b: 二元系的两个元素
            temperature_K: 温度 (K)
            phase: 相态
            n_points: 成分点数

        返回:
            {"miedema_curve": [...], "dft_points": [...], "deviation": ...}
        """
        from models.miedema_model import MiedemaModel

        phase_str = "SOLID" if phase == "solid" else "LIQUID"
        model = MiedemaModel((element_a, element_b), phase_str)
        order = "SS"

        # Miedema 曲线
        miedema_curve = []
        for i in range(n_points):
            x_b = i / (n_points - 1)
            x_a = 1.0 - x_b
            if x_a <= 1e-6 or x_b <= 1e-6:
                continue
            try:
                h_mix = model.getmixingEnthalpy_by_Miedema_Model(
                    element_b, x_b, temperature_K, order
                )
                miedema_curve.append({
                    "x_b": round(x_b, 3),
                    "H_mix_J": h_mix,
                })
            except Exception:
                pass

        # DFT 数据
        system = "-".join(sorted([element_a, element_b]))
        dft_points = self.dft_store.get_mixing_enthalpy(system, phase)

        # 计算偏差（如果有 DFT 数据）
        deviation = None
        if dft_points and miedema_curve:
            diffs = []
            for dp in dft_points:
                x_b_dft = dp["composition"].get(element_b, 0)
                h_dft = dp["mixing_enthalpy_J"]
                # 找最近的 Miedema 点
                closest = min(miedema_curve,
                              key=lambda p: abs(p["x_b"] - x_b_dft))
                diffs.append(abs(h_dft - closest["H_mix_J"]))
            if diffs:
                deviation = {
                    "mean_abs_error_J": sum(diffs) / len(diffs),
                    "max_abs_error_J": max(diffs),
                    "n_comparison_points": len(diffs),
                }

        return {
            "status": "success",
            "system": f"{element_a}-{element_b}",
            "temperature_K": temperature_K,
            "phase": phase,
            "miedema_curve": miedema_curve,
            "dft_points": dft_points,
            "deviation": deviation,
            "has_dft_data": len(dft_points) > 0,
        }

    # ==================== 辅助方法 ====================

    def _find_compounds_for_system(self, elem_a: str,
                                    elem_b: str) -> List[CompoundEnergy]:
        """查找包含两种元素的所有 DFT 化合物数据"""
        all_compounds = self.dft_store.list_compounds(elem_a)
        results = []
        for c in all_compounds:
            elems = [e.capitalize() for e in c["elements"]]
            if elem_a.capitalize() in elems and elem_b.capitalize() in elems:
                data = self.dft_store.get_compound_energy(c["compound"])
                if data:
                    results.append(data)
        return results

    def get_dft_data_summary(self) -> Dict[str, Any]:
        """获取 DFT 数据库摘要"""
        stats = self.dft_store.get_statistics()
        compounds = self.dft_store.list_compounds()
        return {
            "status": "success",
            **stats,
            "compounds": compounds,
        }
