"""
Phase Diagram Calculator
========================
(V3.1 - 修复了二元50/50 KeyError bug)
(使用 V3 ThermoProperties (PyCalphad 后端))

依赖于:
- ThermodynamicProperties 类 (用于获取 G°, ln(γ))
- SciPy (用于求解非线性方程组)

作者: Claude
日期: 2025-11-08
"""

import math
from typing import Dict, Optional, Tuple, List
import sys
import os
from scipy.optimize import root, brentq

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (重要) 确保导入的是 V3 版本的基类
from calculations.thermodynamic_properties import ThermodynamicProperties
from pycalphad import variables as v # 导入 pycalphad 变量


class PhaseDiagramCalculator(ThermodynamicProperties):
    """
    通过继承 ThermodynamicProperties 类，
    实现液相线和固相线的计算。
    """

    def __init__(self):
        super().__init__()

    @staticmethod
    def _check_bounds(x, epsilon=1e-9):
        if x < epsilon: return epsilon
        if x > 1.0 - epsilon: return 1.0 - epsilon
        return x

    # ================================================================
    # =================== 统一的公共接口 (已修正) ===================
    # ================================================================

    def calculate_liquidus(self,
                           composition: Dict[str, float],
                           solid_phase_map: Dict[str, str],
                           extrapolation_model: str = 'UEM1',
                           activity_model: str = 'Wagner'
                           ) -> dict:
        """
        (V3.1 修正) 统一的液相线计算接口。
        自动根据组元数量选择二元或多元求解器。
        """
        
        n_components = len(composition)
        
        if n_components <= 0:
            raise ValueError("成分字典不能为空")
            
        if n_components == 1:
            print("(Info) 检测到纯物质，计算熔点...")
            elem = list(composition.keys())[0]
            solid_phase = solid_phase_map.get(elem)
            if solid_phase is None: raise ValueError(f"solid_phase_map 中未定义 {elem} 的固相")
            T_melt = self.calculate_pure_melting_point(elem, solid_phase)
            if T_melt is None: raise RuntimeError(f"无法计算纯 {elem} 的熔点")
            return {"status": "success", "T_liquidus": T_melt, "liquid_composition": composition, "solid_composition_eq": composition}

        elif n_components == 2:
            print("(Info) 检测到二元系统，调用二元求解器...")
            
            # --- (BUG 修复) ---
            # 修复了 50/50 成分时 min/max 返回相同键的 bug
            components = sorted(composition.keys()) # 确定一个顺序, e.g., ['CR', 'FE']
            comp_A = max(composition.items(), key=lambda item: item[1])[0] # 找到真正的溶剂
            # 确保 comp_B 是另一个元素
            comp_B = components[0] if components[1] == comp_A else components[1]
            # --- (BUG 修复结束) ---

            x_B_liq = composition[comp_B]
            solid_A = solid_phase_map[comp_A]
            solid_B = solid_phase_map[comp_B]
            
            T_melt_A = self.calculate_pure_melting_point(comp_A, solid_A)
            T_melt_B = self.calculate_pure_melting_point(comp_B, solid_B)
            
            if T_melt_A is None or T_melt_B is None:
                raise ValueError(f"无法计算 {comp_A} 或 {comp_B} 的熔点以生成猜测值")

            T_guess = (1 - x_B_liq) * T_melt_A + x_B_liq * T_melt_B + 10
            
            # (修正) 确保在调用 _auto_generate_solute_guess 后能正确找到 comp_B
            guess_dict = self._auto_generate_solute_guess(composition, default_k=0.8)
            if comp_B not in guess_dict:
                 comp_A_solute = min(composition.items(), key=lambda item: item[1])[0]
                 guess_dict = self._auto_generate_solute_guess(composition, default_k=0.8)
                 x_S_guess = guess_dict[comp_A_solute] # 这是一个临时的、不完美的回退
            else:
                x_S_guess = guess_dict[comp_B]
            
            return self.calculate_liquidus_temp(
                x_B_overall=x_B_liq,
                comp_A=comp_A, comp_B=comp_B,
                solid_phase_A=solid_A, solid_phase_B=solid_B,
                T_guess=T_guess, x_S_guess=x_S_guess,
                extrapolation_model=extrapolation_model, activity_model=activity_model
            )

        else: # n_components > 2
            print("(Info) 检测到多元系统，调用健壮版多元求解器...")
            return self.calculate_liquidus_temp_robust(
                liquid_composition=composition,
                solid_phase_map=solid_phase_map,
                extrapolation_model=extrapolation_model,
                activity_model=activity_model
            )

    def calculate_solidus(self,
                           composition: Dict[str, float],
                           solid_phase_map: Dict[str, str],
                           extrapolation_model: str = 'UEM1',
                           activity_model: str = 'Wagner'
                           ) -> dict:
        """
        (V3.1 修正) 统一的固相线计算接口。
        """
        n_components = len(composition)
        
        if n_components <= 0:
            raise ValueError("成分字典不能为空")
        if n_components == 1:
            return self.calculate_liquidus(composition, solid_phase_map, extrapolation_model, activity_model)

        elif n_components == 2:
            print("(Info) 检测到二元系统，调用二元求解器...")
            
            # --- (BUG 修复) ---
            components = sorted(composition.keys())
            comp_A = max(composition.items(), key=lambda item: item[1])[0]
            comp_B = components[0] if components[1] == comp_A else components[1]
            # --- (BUG 修复结束) ---
            
            x_B_sol = composition[comp_B]
            solid_A = solid_phase_map[comp_A]
            solid_B = solid_phase_map[comp_B]
            
            T_melt_A = self.calculate_pure_melting_point(comp_A, solid_A)
            T_melt_B = self.calculate_pure_melting_point(comp_B, solid_B)
            
            if T_melt_A is None or T_melt_B is None:
                raise ValueError(f"无法计算 {comp_A} 或 {comp_B} 的熔点以生成猜测值")

            T_guess = (1 - x_B_sol) * T_melt_A + x_B_sol * T_melt_B - 10
            
            # (修正)
            guess_dict = self._auto_generate_solute_guess(composition, default_k=1.2)
            if comp_B not in guess_dict:
                 comp_A_solute = min(composition.items(), key=lambda item: item[1])[0]
                 guess_dict = self._auto_generate_solute_guess(composition, default_k=1.2)
                 x_L_guess = guess_dict[comp_A_solute]
            else:
                x_L_guess = guess_dict[comp_B]
            
            return self.calculate_solidus_temp(
                x_B_overall=x_B_sol,
                comp_A=comp_A, comp_B=comp_B,
                solid_phase_A=solid_A, solid_phase_B=solid_B,
                T_guess=T_guess, x_L_guess=x_L_guess,
                extrapolation_model=extrapolation_model, activity_model=activity_model
            )

        else: # n_components > 2
            print("(Info) 检测到多元系统，调用健壮版多元求解器...")
            return self.calculate_solidus_temp_robust(
                solid_composition=composition,
                solid_phase_map=solid_phase_map,
                extrapolation_model=extrapolation_model,
                activity_model=activity_model
            )

    # ================================================================
    # =================== 内部辅助函数 ===================
    # ================================================================

    # --- (已重写：使用父类的 _get_pure_property) ---
    def calculate_pure_melting_point(self,
                                     element: str,
                                     solid_phase: Optional[str] = None,
                                     T_min: float = 300.0,
                                     T_max: float = 6000.0) -> Optional[float]:
        """
        从TDB数据计算纯元素的熔点。
        """
        if solid_phase is None:
            # (已重写) 使用 pycalphad DB 对象
            try:
                solid_phase = self.dbf.elements.get(element.upper()).reference_phase
                if solid_phase is None:
                    print(f"错误: 无法在 TDB 中找到 {element} 的参考固相。")
                    return None
            except Exception as e:
                print(f"错误: 调用 TDB.elements.get({element}) 失败: {e}")
                return None
        
        def _gibbs_difference(T: float) -> float:
            # (已重写) 使用父类的 _get_pure_property (它调用 pycalphad)
            g_liq = self._get_pure_property(element, 'LIQUID', T, 101325, 'G')
            g_solid = self._get_pure_property(element, solid_phase, T, 101325, 'G')
            if g_liq is None or g_solid is None:
                raise ValueError(f"无法在 T={T}K 时获取 {element} 的 Gibbs 能量。")
            return g_liq - g_solid

        try:
            g_diff_min = _gibbs_difference(T_min)
            g_diff_max = _gibbs_difference(T_max)
            if g_diff_min * g_diff_max >= 0:
                # print(f"错误: 无法包围 {element} 的熔点。 G_diff({T_min}K)={g_diff_min:.2f}, G_diff({T_max}K)={g_diff_max:.2f}")
                return None
            T_melt = brentq(_gibbs_difference, T_min, T_max, xtol=0.1)
            return T_melt
        except Exception as e:
            # print(f"计算 {element} 熔点时出错: {e}")
            return None

    # --- (已重写：使用父类的 G° 和 ln(gamma) 函数) ---
    def _get_chemical_potential(self,
                               composition: Dict[str, float],
                               component: str,
                               temperature: float,
                               tdb_phase: str, # 'LIQUID', 'BCC_A2', etc.
                               extrapolation_model: str,
                               activity_model: str) -> Optional[float]:
        """
        计算化学势的内部辅助函数。
        """
        # 1. (已重写) 使用父类的 _get_pure_property
        mu_0 = self._get_pure_property(component, tdb_phase, temperature, 101325, 'G')
        if mu_0 is None: return None

        # 2. (正确) 使用父类的 calculate_ln_activity_coefficient
        activity_phase_state = 'liquid' if tdb_phase == 'LIQUID' else 'solid'
        ln_gamma = self.calculate_ln_activity_coefficient(
            composition, component, temperature, activity_phase_state,
            None, extrapolation_model, activity_model
        )
        if ln_gamma is None: return None
        
        # 3.
        x_i = self._check_bounds(composition.get(component, 0.0))
        mu = mu_0 + self.R * temperature * (math.log(x_i) + ln_gamma)
        return mu

    def _auto_generate_solute_guess(self,
                                    composition: Dict[str, float],
                                    default_k: float = 0.8) -> Dict[str, float]:
        """
        自动为固相/液相求解器生成溶质成分的初始猜测值。
        """
        DEFAULT_K_RULES = {'C': 0.05, 'N': 0.05, 'B': 0.05, 'H': 0.01, 'O': 0.01, 'DEFAULT_SUBSTITUTIONAL': default_k}
        if not composition: return {}
        try:
            solvent = max(composition.items(), key=lambda item: item[1])[0]
        except ValueError:
            return {}
        solutes = [c for c in composition.keys() if c != solvent]
        solute_guess = {}
        for solute in solutes:
            x_l = composition[solute]; k = DEFAULT_K_RULES.get(solute, DEFAULT_K_RULES['DEFAULT_SUBSTITUTIONAL']); x_s_guess = k * x_l
            solute_guess[solute] = self._check_bounds(x_s_guess)
        return solute_guess

    # ================================================================
    # =================== 内部求解器 (二元) ===================
    # ================================================================
    
    def calculate_liquidus_temp(self, x_B_overall: float, comp_A: str, comp_B: str, solid_phase_A: str, solid_phase_B: str, T_guess: float, x_S_guess: float, extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> dict:
        x_L = self._check_bounds(x_B_overall)
        def _residuals(unknowns):
            T, x_S_calc = unknowns; x_S = self._check_bounds(x_S_calc)
            comp_dict_L = {comp_A: 1.0 - x_L, comp_B: x_L}; comp_dict_S = {comp_A: 1.0 - x_S, comp_B: x_S}
            mu_A_L = self._get_chemical_potential(comp_dict_L, comp_A, T, 'LIQUID', extrapolation_model, activity_model)
            mu_A_S = self._get_chemical_potential(comp_dict_S, comp_A, T, solid_phase_A, extrapolation_model, activity_model)
            mu_B_L = self._get_chemical_potential(comp_dict_L, comp_B, T, 'LIQUID', extrapolation_model, activity_model)
            mu_B_S = self._get_chemical_potential(comp_dict_S, comp_B, T, solid_phase_B, extrapolation_model, activity_model)
            if any(v is None for v in [mu_A_L, mu_A_S, mu_B_L, mu_B_S]): return [1e10, 1e10]
            return [mu_A_L - mu_A_S, mu_B_L - mu_B_S]
        sol = root(_residuals, [T_guess, x_S_guess], method='lm')
        if not sol.success: raise RuntimeError(f"二元液相线求解失败 (x_L={x_B_overall}): {sol.message}")
        return {"status": "success", "T_liquidus": sol.x[0], "liquid_composition": {comp_A: 1.0-x_L, comp_B: x_L}, "solid_composition_eq": {comp_A: 1.0-sol.x[1], comp_B: sol.x[1]}}

    def calculate_solidus_temp(self, x_B_overall: float, comp_A: str, comp_B: str, solid_phase_A: str, solid_phase_B: str, T_guess: float, x_L_guess: float, extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> dict:
        x_S = self._check_bounds(x_B_overall);
        def _residuals(unknowns):
            T, x_L_calc = unknowns; x_L = self._check_bounds(x_L_calc)
            comp_dict_L = {comp_A: 1.0 - x_L, comp_B: x_L}; comp_dict_S = {comp_A: 1.0 - x_S, comp_B: x_S}
            mu_A_L = self._get_chemical_potential(comp_dict_L, comp_A, T, 'LIQUID', extrapolation_model, activity_model)
            mu_A_S = self._get_chemical_potential(comp_dict_S, comp_A, T, solid_phase_A, extrapolation_model, activity_model)
            mu_B_L = self._get_chemical_potential(comp_dict_L, comp_B, T, 'LIQUID', extrapolation_model, activity_model)
            mu_B_S = self._get_chemical_potential(comp_dict_S, comp_B, T, solid_phase_B, extrapolation_model, activity_model)
            if any(v is None for v in [mu_A_L, mu_A_S, mu_B_L, mu_B_S]): return [1e10, 1e10]
            return [mu_A_L - mu_A_S, mu_B_L - mu_B_S]
        sol = root(_residuals, [T_guess, x_L_guess], method='lm')
        if not sol.success: raise RuntimeError(f"二元固相线求解失败 (x_S={x_B_overall}): {sol.message}")
        return {"status": "success", "T_solidus": sol.x[0], "solid_composition": {comp_A: 1.0-x_S, comp_B: x_S}, "liquid_composition_eq": {comp_A: 1.0-sol.x[1], comp_B: sol.x[1]}}


    # ================================================================
    # =================== 内部求解器 (多元) ===================
    # ================================================================
    
    def calculate_liquidus_temp_robust(self,
                                       liquid_composition: Dict[str, float],
                                       solid_phase_map: Dict[str, str],
                                       extrapolation_model: str = 'UEM1',
                                       activity_model: str = 'Wagner'
                                       ) -> dict:
        """
        (内部) 健壮地计算多元液相线温度。
        """
        solvent = max(liquid_composition.items(), key=lambda x: x[1])[0]
        solutes = [c for c in liquid_composition.keys() if c != solvent]
        T_guess = 1750.0
        try:
            T_melt_solvent = self.calculate_pure_melting_point(solvent, solid_phase_map.get(solvent))
            if T_melt_solvent:
                T_weighted = T_melt_solvent * liquid_composition[solvent]
                missing_tm = False
                for solute in solutes:
                    T_melt_solute = self.calculate_pure_melting_point(solute, solid_phase_map.get(solute))
                    if T_melt_solute: T_weighted += T_melt_solute * liquid_composition[solute]
                    else: missing_tm = True; T_weighted += T_melt_solvent * liquid_composition[solute]
                T_guess = T_weighted - 50
                if not missing_tm: print(f"  (Info) 使用加权平均 T_guess: {T_guess:.1f} K")
                else: print(f"  (Info) 缺少部分纯元素熔点，使用近似 T_guess: {T_guess:.1f} K")
            else: print(f"  (Warning) 无法计算溶剂 {solvent} 熔点，使用默认 T_guess: {T_guess:.1f} K")
        except Exception: print(f"  (Warning) T_guess 自动计算失败，使用默认 T_guess: {T_guess:.1f} K")
        guess_strategies = [
            self._auto_generate_solute_guess(liquid_composition, default_k=0.8),
            {s: liquid_composition[s] for s in solutes}, # k=1.0
            self._auto_generate_solute_guess(liquid_composition, default_k=0.1),
            self._auto_generate_solute_guess(liquid_composition, default_k=0.01)
        ]
        last_exception = None
        for i, solid_guess in enumerate(guess_strategies):
            # print(f"  (Info) Solver: 尝试策略 #{i+1} (T_guess={T_guess:.1f}K, X_S_guess={solid_guess})...")
            try:
                result = self.calculate_liquidus_temp_multicomponent(
                    liquid_composition, solid_phase_map, T_guess, solid_guess,
                    extrapolation_model, activity_model
                )
                T_result = result['T_liquidus']
                if 300 < T_result < 6000: return result
                else: last_exception = RuntimeError(f"Converged to non-physical T={T_result:.1f}K")
            except Exception as e: last_exception = e
        raise RuntimeError(f"所有求解器策略均未能找到 {liquid_composition} 的有效液相线温度。 最后错误: {last_exception}")

    def calculate_solidus_temp_robust(self,
                                      solid_composition: Dict[str, float],
                                      solid_phase_map: Dict[str, str],
                                      extrapolation_model: str = 'UEM1',
                                      activity_model: str = 'Wagner'
                                      ) -> dict:
        """
        (内部) 健壮地计算多元固相线温度。
        """
        solvent = max(solid_composition.items(), key=lambda x: x[1])[0]
        solutes = [c for c in solid_composition.keys() if c != solvent]
        T_guess = 1700.0
        try:
            T_melt_solvent = self.calculate_pure_melting_point(solvent, solid_phase_map[solvent])
            if T_melt_solvent:
                T_weighted = T_melt_solvent * solid_composition[solvent]
                for solute in solutes:
                    T_melt_solute = self.calculate_pure_melting_point(solute, solid_phase_map.get(solute))
                    T_weighted += (T_melt_solute or T_melt_solvent) * solid_composition[solute]
                T_guess = T_weighted - 100
                print(f"  (Info) 使用加权平均 T_guess: {T_guess:.1f} K")
            else: print(f"  (Warning) 无法计算溶剂 {solvent} 熔点，使用默认 T_guess: {T_guess:.1f} K")
        except Exception: print(f"  (Warning) T_guess 自动计算失败，使用默认 T_guess: {T_guess:.1f} K")
        guess_strategies = [
            self._auto_generate_solute_guess(solid_composition, default_k=0.8 / 1.0),
            {s: solid_composition[s] for s in solutes},
            self._auto_generate_solute_guess(solid_composition, default_k=1.2 / 1.0),
        ]
        last_exception = None
        for i, liquid_guess in enumerate(guess_strategies):
            try:
                result = self.calculate_solidus_temp_multicomponent(
                    solid_composition, solid_phase_map, T_guess, liquid_guess,
                    extrapolation_model, activity_model
                )
                T_result = result['T_solidus']
                if 300 < T_result < 6000: return result
                else: last_exception = RuntimeError(f"Converged to non-physical T={T_result:.1f}K")
            except Exception as e: last_exception = e
        raise RuntimeError(f"所有求解器策略均未能找到 {solid_composition} 的有效固相线温度。 最后错误: {last_exception}")

    def calculate_liquidus_temp_multicomponent(self, liquid_composition: Dict[str, float], solid_phase_map: Dict[str, str], T_guess: float, solid_solute_comp_guess: Dict[str, float], extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> dict:
        solvent = max(liquid_composition.items(), key=lambda x: x[1])[0]; solutes = [c for c in liquid_composition.keys() if c != solvent]; all_components = [solvent] + solutes
        X_L = {c: self._check_bounds(x) for c, x in liquid_composition.items()}
        def _residuals(unknowns):
            T = unknowns[0]; X_S_solutes = {solute: self._check_bounds(unknowns[i+1]) for i, solute in enumerate(solutes)}; x_s_solvent = 1.0 - sum(X_S_solutes.values()); X_S = {solvent: self._check_bounds(x_s_solvent), **X_S_solutes}
            residuals = []
            for comp in all_components:
                solid_phase = solid_phase_map.get(comp);
                if solid_phase is None: raise ValueError(f"solid_phase_map 中未定义组分 {comp} 的固相")
                mu_L = self._get_chemical_potential(X_L, comp, T, 'LIQUID', extrapolation_model, activity_model)
                mu_S = self._get_chemical_potential(X_S, comp, T, solid_phase, extrapolation_model, activity_model)
                if mu_L is None or mu_S is None: return [1e10] * len(all_components)
                residuals.append(mu_L - mu_S)
            return residuals
        initial_guesses = [T_guess] + [solid_solute_comp_guess.get(s, 0.0) for s in solutes]
        sol = root(_residuals, initial_guesses, method='lm')
        if not sol.success: raise RuntimeError(f"多元液相线求解失败: {sol.message}")
        T_liquidus = sol.x[0]; final_solid_solutes = {solute: sol.x[i+1] for i, solute in enumerate(solutes)}; final_solid_solvent = 1.0 - sum(final_solid_solutes.values()); final_solid_comp = {solvent: final_solid_solvent, **final_solid_solutes}
        return {"status": "success", "T_liquidus": T_liquidus, "liquid_composition": liquid_composition, "solid_composition_eq": final_solid_comp}


# 测试代码
if __name__ == "__main__":
    
    pd_calc = PhaseDiagramCalculator()
    
    # ================================================================
    # =================== 1. 二元测试 (Fe-Cr) ===================
    # ================================================================
    
    print("\n" + "=" * 70)
    print("Binary Liquidus/Solidus Calculation Test (Fe-Cr)")
    print("=" * 70)
    
    binary_comp = {'FE': 0.5, 'CR': 0.5}
    binary_solid_map = {'FE': 'BCC_A2', 'CR': 'BCC_A2'}
    
    try:
        liquidus_result = pd_calc.calculate_liquidus(
            composition=binary_comp,
            solid_phase_map=binary_solid_map
        )
        print(f"\n--- [Unified] 液相线 (凝固点) @ {binary_comp} ---")
        print(f"  T_liquidus: {liquidus_result['T_liquidus']:.2f} K")
        print("  Equilibrium Solid Composition:")
        for comp, x in liquidus_result['solid_composition_eq'].items():
            print(f"    x_{comp:<4}: {x:.6f}")
    except Exception as e:
        print(f"计算 Fe-Cr 液相线失败: {e}")

    try:
        solidus_result = pd_calc.calculate_solidus(
            composition=binary_comp,
            solid_phase_map=binary_solid_map
        )
        print(f"\n--- [Unified] 固相线 (熔点) @ {binary_comp} ---")
        print(f"  T_solidus: {solidus_result['T_solidus']:.2f} K")
        print("  Equilibrium Liquid Composition:")
        for comp, x in solidus_result['liquid_composition_eq'].items():
            print(f"    x_{comp:<4}: {x:.6f}")
    except Exception as e:
        print(f"计算 Fe-Cr 固相线失败: {e}")
        
    print("=" * 70)
    
    # ================================================================
    # =================== 2. 多元测试 (Fe-C-Si) ===================
    # ================================================================
    
    print("\n" + "=" * 70)
    print("Multicomponent Liquidus Calculation Test (Fe-C-Si)")
    print("=" * 70)

    liq_comp = {
        'FE': 0.95,
        'C': 0.02,
        'SI': 0.03
    }
    
    # (重要)
    # 假设1: 液相 <-> 铁素体(Fe,Si) + 石墨(C)
    # (这是物理上不正确的模型，但我们将用它来测试求解器)
    solid_map_graphite = {
        'FE': 'BCC_A2',
        'C': 'GRAPHITE', # 纯碳的参考固相
        'SI': 'BCC_A2'   # Si 溶解在 BCC_A2 中
    }
    
    # 假设2: 液相 <-> 奥氏体(Fe,C,Si) 固溶体
    solid_map_austenite = {
        'FE': 'FCC_A1',
        'C': 'FCC_A1',   # C 溶解在 FCC_A1 中
        'SI': 'FCC_A1'   # Si 溶解在 FCC_A1 中
    }
    
    try:
        print("\n--- 尝试计算: Liquid <-> BCC_A2(Fe,Si) + GRAPHITE(C) ---")
        multi_liq_result = pd_calc.calculate_liquidus(
            composition=liq_comp,
            solid_phase_map=solid_map_graphite # 使用假设 1
        )
        
        print(f"\n--- [Unified] 多元液相线 (凝固点) @ {liq_comp} ---")
        print(f"  T_liquidus: {multi_liq_result['T_liquidus']:.2f} K")
        print("  Equilibrium Solid Composition:")
        for comp, x in multi_liq_result['solid_composition_eq'].items():
            print(f"    x_{comp:<4}: {x:.6f}")
            
    except Exception as e:
        print(f"计算 Fe-C-Si 液相线 (BCC+Graphite) 失败: {e}")
    
    try:
        print("\n--- 尝试计算: Liquid <-> FCC_A1(Fe,C,Si) 固溶体 ---")
        multi_liq_result_fcc = pd_calc.calculate_liquidus(
            composition=liq_comp,
            solid_phase_map=solid_map_austenite # 使用假设 2
        )
        
        print(f"\n--- [Unified] 多元液相线 (凝固点) @ {liq_comp} ---")
        print(f"  T_liquidus (FCC): {multi_liq_result_fcc['T_liquidus']:.2f} K")
        print("  Equilibrium Solid Composition (FCC):")
        for comp, x in multi_liq_result_fcc['solid_composition_eq'].items():
            print(f"    x_{comp:<4}: {x:.6f}")
            
    except Exception as e:
        print(f"计算 Fe-C-Si 液相线 (FCC) 失败: {e}")
        
    print("=" * 70)