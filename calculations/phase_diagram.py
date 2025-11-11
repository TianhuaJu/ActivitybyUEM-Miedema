"""
Phase Diagram Calculator
========================
计算二元及多元稀溶液的液相线 (Liquidus) 和固相线 (Solidus) 温度。

(V3.3 - [Gemini] 集成固溶体(SS)和纯固体(Pure)模型)
- 增加了 'solid_model_type' 参数 ('SOLID_SOLUTION' 或 'PURE_SOLID')
- 恢复 V3.1 的固溶体求解器
- 重构内部函数以支持模型切换

依赖于:
- ThermodynamicProperties 类 (用于获取 G°, ln(γ))
- SciPy (用于求解非线性方程组)

作者: Claude (修改: Gemini)
日期: 2025-11-09
"""

import math
from typing import Dict, Optional, Tuple, List
import sys
import os
from scipy.optimize import root, brentq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations.thermodynamic_properties import ThermodynamicProperties


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
    # =================== 统一的公共接口 (V3.3 调度器) ===================
    # ================================================================

    def calculate_liquidus(self,
                           composition: Dict[str, float],
                           solid_phase_map: Dict[str, str],
                           extrapolation_model: str = 'UEM1',
                           activity_model: str = 'Wagner',
                           solid_model_type: str = 'SOLID_SOLUTION'
                           ) -> dict:
        """
        (V3.3) 统一的液相线计算接口。
        自动根据组元数量和 'solid_model_type' 选择求解器。
        
        Args:
            composition (Dict): 液相成分
            solid_phase_map (Dict): 组分到固相名称的映射
            extrapolation_model (str): 活度系数外推模型
            activity_model (str): 活度系数模型 (如 'Wagner')
            solid_model_type (str): 固相模型:
                'SOLID_SOLUTION': 液相 <-> 固溶体 (V3.1 逻辑)
                'PURE_SOLID':     液相 <-> 纯固体 (V3.2 逻辑)
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
            
            # 两种模型的纯物质固相成分不同
            if solid_model_type == 'SOLID_SOLUTION':
                 solid_comp_eq = composition
            else: # 'PURE_SOLID'
                 solid_comp_eq = {elem: 1.0}
                 
            return {"status": "success", "T_liquidus": T_melt, "liquid_composition": composition, "solid_composition_eq": solid_comp_eq}

        elif n_components == 2:
            print(f"(Info) 检测到二元系统，使用 '{solid_model_type}' 模型...")
            
            components = sorted(composition.keys())
            comp_A = max(composition.items(), key=lambda item: item[1])[0]
            comp_B = components[0] if components[1] == comp_A else components[1]

            x_B_liq = composition[comp_B]
            solid_A = solid_phase_map[comp_A]
            solid_B = solid_phase_map[comp_B]
            
            T_melt_A = self.calculate_pure_melting_point(comp_A, solid_A)
            T_melt_B = self.calculate_pure_melting_point(comp_B, solid_B)
            
            if T_melt_A is None or T_melt_B is None:
                raise ValueError(f"无法计算 {comp_A} 或 {comp_B} 的熔点以生成猜测值")

            T_guess = (1 - x_B_liq) * T_melt_A + x_B_liq * T_melt_B + 10
            x_S_guess = self._auto_generate_solute_guess(composition, default_k=0.8)[comp_B]
            
            # --- 模型调度 ---
            if solid_model_type == 'SOLID_SOLUTION':
                solver_func = self._solve_liquidus_binary_ss
            elif solid_model_type == 'PURE_SOLID':
                solver_func = self._solve_liquidus_binary_pure
            else:
                raise ValueError(f"未知的 solid_model_type: {solid_model_type}")
            # --- 结束调度 ---

            return solver_func(
                x_B_overall=x_B_liq,
                comp_A=comp_A, comp_B=comp_B,
                solid_phase_A=solid_A, solid_phase_B=solid_B,
                T_guess=T_guess, x_S_guess=x_S_guess,
                extrapolation_model=extrapolation_model, activity_model=activity_model
            )

        else: # n_components > 2
            print(f"(Info) 检测到多元系统，使用 '{solid_model_type}' 健壮版求解器...")
            
            # --- 模型调度 ---
            if solid_model_type == 'SOLID_SOLUTION':
                robust_solver_func = self.calculate_liquidus_temp_robust_ss
            elif solid_model_type == 'PURE_SOLID':
                robust_solver_func = self.calculate_liquidus_temp_robust_pure
            else:
                raise ValueError(f"未知的 solid_model_type: {solid_model_type}")
            # --- 结束调度 ---
            
            return robust_solver_func(
                liquid_composition=composition,
                solid_phase_map=solid_phase_map,
                extrapolation_model=extrapolation_model,
                activity_model=activity_model
            )

    def calculate_solidus(self,
                           composition: Dict[str, float],
                           solid_phase_map: Dict[str, str],
                           extrapolation_model: str = 'UEM1',
                           activity_model: str = 'Wagner',
                           solid_model_type: str = 'SOLID_SOLUTION'
                           ) -> dict:
        """
        (V3.3) 统一的固相线计算接口。
        
        Args:
            composition (Dict): 固相成分
            ...
            solid_model_type (str): 'SOLID_SOLUTION' 或 'PURE_SOLID'
        """
        n_components = len(composition)
        
        if n_components <= 0:
            raise ValueError("成分字典不能为空")
        if n_components == 1:
            return self.calculate_liquidus(composition, solid_phase_map, extrapolation_model, activity_model, solid_model_type)

        elif n_components == 2:
            print(f"(Info) 检测到二元系统，使用 '{solid_model_type}' 模型...")
            
            components = sorted(composition.keys())
            comp_A = max(composition.items(), key=lambda item: item[1])[0]
            comp_B = components[0] if components[1] == comp_A else components[1]
            
            x_B_sol = composition[comp_B]
            solid_A = solid_phase_map[comp_A]
            solid_B = solid_phase_map[comp_B]
            
            T_melt_A = self.calculate_pure_melting_point(comp_A, solid_A)
            T_melt_B = self.calculate_pure_melting_point(comp_B, solid_B)
            
            if T_melt_A is None or T_melt_B is None:
                raise ValueError(f"无法计算 {comp_A} 或 {comp_B} 的熔点以生成猜测值")

            # 猜测值
            T_guess_ss = (1 - x_B_sol) * T_melt_A + x_B_sol * T_melt_B - 10
            T_guess_pure = min(T_melt_A, T_melt_B) - 50
            x_L_guess_dict = self._auto_generate_solute_guess(composition, default_k=1.2)
            x_L_guess = x_L_guess_dict[comp_B]

            # --- 模型调度 ---
            if solid_model_type == 'SOLID_SOLUTION':
                solver_func = self._solve_solidus_binary_ss
                T_guess = T_guess_ss
            elif solid_model_type == 'PURE_SOLID':
                solver_func = self._solve_solidus_binary_pure
                T_guess = T_guess_pure
            else:
                raise ValueError(f"未知的 solid_model_type: {solid_model_type}")
            # --- 结束调度 ---
            
            return solver_func(
                x_B_overall=x_B_sol,
                comp_A=comp_A, comp_B=comp_B,
                solid_phase_A=solid_A, solid_phase_B=solid_B,
                T_guess=T_guess, x_L_guess=x_L_guess,
                extrapolation_model=extrapolation_model, activity_model=activity_model
            )

        else: # n_components > 2
            print(f"(Info) 检测到多元系统，使用 '{solid_model_type}' 健壮版求解器...")

            # --- 模型调度 ---
            if solid_model_type == 'SOLID_SOLUTION':
                robust_solver_func = self.calculate_solidus_temp_robust_ss
            elif solid_model_type == 'PURE_SOLID':
                robust_solver_func = self.calculate_solidus_temp_robust_pure
            else:
                raise ValueError(f"未知的 solid_model_type: {solid_model_type}")
            # --- 结束调度 ---

            return robust_solver_func(
                solid_composition=composition,
                solid_phase_map=solid_phase_map,
                extrapolation_model=extrapolation_model,
                activity_model=activity_model
            )

    # ================================================================
    # =================== 内部辅助函数 ===================
    # ================================================================

    def calculate_pure_melting_point(self,
                                     element: str,
                                     solid_phase: Optional[str] = None,
                                     T_min: float = 300.0,
                                     T_max: float = 6000.0) -> Optional[float]:
        """
        从TDB数据计算纯元素的熔点。
        """
        if solid_phase is None:
            try:
                solid_phase = self.tdb_parser.get_reference_phase(element)
                if solid_phase is None:
                    print(f"错误: 无法在 TDB 中找到 {element} 的参考固相。")
                    return None
            except Exception as e:
                print(f"错误: 调用 get_reference_phase({element}) 失败: {e}")
                return None

        def _gibbs_difference(T: float) -> float:
            g_liq = self.tdb_parser.get_gibbs_energy(element, 'LIQUID', T)
            g_solid = self.tdb_parser.get_gibbs_energy(element, solid_phase, T)
            if g_liq is None or g_solid is None:
                raise ValueError(f"无法在 T={T}K 时获取 {element} 的 Gibbs 能量。")
            return g_liq - g_solid

        try:
            g_diff_min = _gibbs_difference(T_min)
            g_diff_max = _gibbs_difference(T_max)
            if g_diff_min * g_diff_max >= 0:
                return None
            T_melt = brentq(_gibbs_difference, T_min, T_max, xtol=0.1)
            return T_melt
        except Exception as e:
            return None

    def _get_chemical_potential(self,
                              composition: Dict[str, float],
                              component: str,
                              temperature: float,
                              tdb_phase: str, # 'LIQUID', 'BCC_A2', etc.
                              extrapolation_model: str,
                              activity_model: str) -> Optional[float]:
        """
        计算化学势的内部辅助函数 (V3.2 固溶体版本)。
        用于计算任何 *溶液相* (液相或固溶体) 的化学势。
        mu_i = G_i_0 + R*T*ln(x_i) + R*T*ln(gamma_i)

        关键修改：固相统一使用 phase_state='solid' 调用 UEM-Miedema 框架
        """
        # 1. 获取标准 Gibbs 能量
        mu_0 = self.tdb_parser.get_gibbs_energy(component, tdb_phase, temperature)
        if mu_0 is None:
            print(f"  (Warning) 无法获取 {component} 在 {tdb_phase} 相的标准 Gibbs 能量 @ {temperature}K")
            return None

        # 2. 确定相态：液相或固相（统一处理所有固相）
        activity_phase_state = 'liquid' if tdb_phase == 'LIQUID' else 'solid'

        # 3. 计算活度系数（使用 UEM-Miedema 框架，传入 phase_state）
        ln_gamma = self.calculate_ln_activity_coefficient(
            composition, component, temperature, activity_phase_state,
            None, extrapolation_model, activity_model
        )
        if ln_gamma is None:
            print(f"  (Warning) 无法计算 {component} 的活度系数 @ phase_state={activity_phase_state}")
            return None

        # 4. 计算化学势
        x_i = self._check_bounds(composition.get(component, 0.0))
        mu = mu_0 + self.R * temperature * (math.log(x_i) + ln_gamma)

        # 调试输出
        # print(f"  (Debug) μ_{component} @ {tdb_phase}({activity_phase_state}): G°={mu_0:.2f}, ln(γ)={ln_gamma:.4f}, x={x_i:.4e}, μ={mu:.2f}")

        return mu

    def _auto_generate_solute_guess(self,
                                    composition: Dict[str, float],
                                    default_k: float = 0.8) -> Dict[str, float]:
        """
        自动为固相/液相求解器生成溶质成分的初始猜测值。
        """
        DEFAULT_K_RULES = {
            'C': 0.05, 'N': 0.05, 'B': 0.05, 'H': 0.01, 'O': 0.01,
            'DEFAULT_SUBSTITUTIONAL': default_k
        }
        if not composition: return {}
        try:
            solvent = max(composition.items(), key=lambda item: item[1])[0]
        except ValueError:
            return {}
        solutes = [c for c in composition.keys() if c != solvent]
        solute_guess = {}
        for solute in solutes:
            x_l = composition[solute]
            k = DEFAULT_K_RULES.get(solute, DEFAULT_K_RULES['DEFAULT_SUBSTITUTIONAL'])
            x_s_guess = k * x_l
            solute_guess[solute] = self._check_bounds(x_s_guess)
        return solute_guess

    # ================================================================
    # ============ MODEL 1: SOLID SOLUTION (V3.1 Logic) ==============
    # ================================================================

    def _solve_liquidus_binary_ss(self, x_B_overall: float, comp_A: str, comp_B: str, solid_phase_A: str, solid_phase_B: str, T_guess: float, x_S_guess: float, extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> dict:
        """ (V3.1 Logic) 求解 L <-> SS (二元) 液相线 """
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
        if not sol.success: raise RuntimeError(f"二元液相线求解失败(SS Model) (x_L={x_B_overall}): {sol.message}")
        return {"status": "success", "T_liquidus": sol.x[0], "liquid_composition": {comp_A: 1.0-x_L, comp_B: x_L}, "solid_composition_eq": {comp_A: 1.0-sol.x[1], comp_B: sol.x[1]}}

    def _solve_solidus_binary_ss(self, x_B_overall: float, comp_A: str, comp_B: str, solid_phase_A: str, solid_phase_B: str, T_guess: float, x_L_guess: float, extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> dict:
        """ (V3.1 Logic) 求解 L <-> SS (二元) 固相线 """
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
        if not sol.success: raise RuntimeError(f"二元固相线求解失败(SS Model) (x_S={x_B_overall}): {sol.message}")
        return {"status": "success", "T_solidus": sol.x[0], "solid_composition": {comp_A: 1.0-x_S, comp_B: x_S}, "liquid_composition_eq": {comp_A: 1.0-sol.x[1], comp_B: sol.x[1]}}

    def calculate_liquidus_temp_robust_ss(self,
                                          liquid_composition: Dict[str, float],
                                          solid_phase_map: Dict[str, str],
                                          extrapolation_model: str = 'UEM1',
                                          activity_model: str = 'Wagner'
                                          ) -> dict:
        """ (V3.1 Logic) 健壮地计算多元液相线 (SS Model) """
        solvent = max(liquid_composition.items(), key=lambda x: x[1])[0]
        solutes = [c for c in liquid_composition.keys() if c != solvent]
        T_guess = 1750.0
        try:
            T_melt_solvent = self.calculate_pure_melting_point(solvent, solid_phase_map[solvent])
            if T_melt_solvent:
                T_weighted = T_melt_solvent * liquid_composition[solvent]
                missing_tm = False
                for solute in solutes:
                    T_melt_solute = self.calculate_pure_melting_point(solute, solid_phase_map.get(solute))
                    if T_melt_solute:
                        T_weighted += T_melt_solute * liquid_composition[solute]
                    else:
                        missing_tm = True
                        T_weighted += T_melt_solvent * liquid_composition[solute]
                T_guess = T_weighted - 50
                if not missing_tm:
                    print(f"  (Info-SS) 使用加权平均 T_guess: {T_guess:.1f} K")
                else:
                    print(f"  (Info-SS) 缺少部分纯元素熔点，使用近似 T_guess: {T_guess:.1f} K")
            else:
                 print(f"  (Warning-SS) 无法计算溶剂 {solvent} 熔点，使用默认 T_guess: {T_guess:.1f} K")
        except Exception:
             print(f"  (Warning-SS) T_guess 自动计算失败，使用默认 T_guess: {T_guess:.1f} K")
        
        guess_strategies = [
            self._auto_generate_solute_guess(liquid_composition, default_k=0.8),
            {s: liquid_composition[s] for s in solutes}, # k=1.0
            self._auto_generate_solute_guess(liquid_composition, default_k=0.1),
            self._auto_generate_solute_guess(liquid_composition, default_k=0.01)
        ]
        last_exception = None
        for i, solid_guess in enumerate(guess_strategies):
            try:
                result = self._solve_liquidus_multi_ss(
                    liquid_composition, solid_phase_map, T_guess, solid_guess,
                    extrapolation_model, activity_model
                )
                T_result = result['T_liquidus']
                if 300 < T_result < 6000:
                    return result
                else:
                    last_exception = RuntimeError(f"Converged to non-physical T={T_result:.1f}K")
            except Exception as e:
                last_exception = e
        raise RuntimeError(f"所有SS策略均未能找到 {liquid_composition} 的有效液相线温度。 最后错误: {last_exception}")

    def calculate_solidus_temp_robust_ss(self,
                                         solid_composition: Dict[str, float],
                                         solid_phase_map: Dict[str, str],
                                         extrapolation_model: str = 'UEM1',
                                         activity_model: str = 'Wagner'
                                         ) -> dict:
        """ (V3.1 Logic) 健壮地计算多元固相线 (SS Model) """
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
                print(f"  (Info-SS) 使用加权平均 T_guess: {T_guess:.1f} K")
            else:
                print(f"  (Warning-SS) 无法计算溶剂 {solvent} 熔点，使用默认 T_guess: {T_guess:.1f} K")
        except Exception:
            print(f"  (Warning-SS) T_guess 自动计算失败，使用默认 T_guess: {T_guess:.1f} K")
        
        guess_strategies = [
            self._auto_generate_solute_guess(solid_composition, default_k=0.8 / 1.0),
            {s: solid_composition[s] for s in solutes},
            self._auto_generate_solute_guess(solid_composition, default_k=1.2 / 1.0),
        ]
        last_exception = None
        for i, liquid_guess in enumerate(guess_strategies):
            try:
                result = self._solve_solidus_multi_ss(
                    solid_composition, solid_phase_map, T_guess, liquid_guess,
                    extrapolation_model, activity_model
                )
                T_result = result['T_solidus']
                if 300 < T_result < 6000:
                    return result
                else:
                    last_exception = RuntimeError(f"Converged to non-physical T={T_result:.1f}K")
            except Exception as e:
                last_exception = e
        raise RuntimeError(f"所有SS策略均未能找到 {solid_composition} 的有效固相线温度。 最后错误: {last_exception}")

    def _solve_liquidus_multi_ss(self, liquid_composition: Dict[str, float], solid_phase_map: Dict[str, str], T_guess: float, solid_solute_comp_guess: Dict[str, float], extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> dict:
        """ (V3.1 Logic) 求解 L <-> SS (多元) 液相线 """
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
        if not sol.success: raise RuntimeError(f"多元液相线求解失败(SS Model): {sol.message}")
        T_liquidus = sol.x[0]; final_solid_solutes = {solute: sol.x[i+1] for i, solute in enumerate(solutes)}; final_solid_solvent = 1.0 - sum(final_solid_solutes.values()); final_solid_comp = {solvent: final_solid_solvent, **final_solid_solutes}
        return {"status": "success", "T_liquidus": T_liquidus, "liquid_composition": liquid_composition, "solid_composition_eq": final_solid_comp}

    def _solve_solidus_multi_ss(self, solid_composition: Dict[str, float], solid_phase_map: Dict[str, str], T_guess: float, liquid_solute_comp_guess: Dict[str, float], extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> dict:
        """ (V3.1 Logic) 求解 L <-> SS (多元) 固相线 """
        solvent = max(solid_composition.items(), key=lambda x: x[1])[0]; solutes = [c for c in solid_composition.keys() if c != solvent]; all_components = [solvent] + solutes
        X_S = {c: self._check_bounds(x) for c, x in solid_composition.items()}
        def _residuals(unknowns):
            T = unknowns[0]; X_L_solutes = {solute: self._check_bounds(unknowns[i+1]) for i, solute in enumerate(solutes)}; x_l_solvent = 1.0 - sum(X_L_solutes.values()); X_L = {solvent: self._check_bounds(x_l_solvent), **X_L_solutes}
            residuals = []
            for comp in all_components:
                solid_phase = solid_phase_map.get(comp);
                if solid_phase is None: raise ValueError(f"solid_phase_map 中未定义组分 {comp} 的固相")
                mu_L = self._get_chemical_potential(X_L, comp, T, 'LIQUID', extrapolation_model, activity_model)
                mu_S = self._get_chemical_potential(X_S, comp, T, solid_phase, extrapolation_model, activity_model)
                if mu_L is None or mu_S is None: return [1e10] * len(all_components)
                residuals.append(mu_L - mu_S)
            return residuals
        initial_guesses = [T_guess] + [liquid_solute_comp_guess.get(s, 0.0) for s in solutes]
        sol = root(_residuals, initial_guesses, method='lm')
        if not sol.success: raise RuntimeError(f"多元固相线求解失败(SS Model): {sol.message}")
        T_solidus = sol.x[0]; final_liquid_solutes = {solute: sol.x[i+1] for i, solute in enumerate(solutes)}; final_liquid_solvent = 1.0 - sum(final_liquid_solutes.values()); final_liquid_comp = {solvent: final_liquid_solvent, **final_liquid_solutes}
        return {"status": "success", "T_solidus": T_solidus, "solid_composition": solid_composition, "liquid_composition_eq": final_liquid_comp}

    # ================================================================
    # ============ MODEL 2: PURE SOLID (V3.2 Logic) ==================
    # ================================================================

    def _solve_liquidus_binary_pure(self, x_B_overall: float, comp_A: str, comp_B: str, solid_phase_A: str, solid_phase_B: str, T_guess: float, x_S_guess: float, extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> dict:
        """ (V3.2 Logic) 求解 L <-> Pure (二元) 液相线 """
        x_L = self._check_bounds(x_B_overall)
        comp_dict_L = {comp_A: 1.0 - x_L, comp_B: x_L}

        def _resid_A(T: float) -> float:
            mu_A_L = self._get_chemical_potential(comp_dict_L, comp_A, T, 'LIQUID', extrapolation_model, activity_model)
            mu_A_S_pure = self.tdb_parser.get_gibbs_energy(comp_A, solid_phase_A, T)
            if mu_A_L is None or mu_A_S_pure is None: return 1e10
            return mu_A_L - mu_A_S_pure

        def _resid_B(T: float) -> float:
            mu_B_L = self._get_chemical_potential(comp_dict_L, comp_B, T, 'LIQUID', extrapolation_model, activity_model)
            mu_B_S_pure = self.tdb_parser.get_gibbs_energy(comp_B, solid_phase_B, T)
            if mu_B_L is None or mu_B_S_pure is None: return 1e10
            return mu_B_L - mu_B_S_pure

        T_melt_A = self.calculate_pure_melting_point(comp_A, solid_phase_A)
        T_melt_B = self.calculate_pure_melting_point(comp_B, solid_phase_B)
        
        T_min = min(T_melt_A, T_melt_B) - 500 if T_melt_A and T_melt_B else 300.0
        T_max = max(T_melt_A, T_melt_B) + 500 if T_melt_A and T_melt_B else 6000.0
        
        T_liq_A, T_liq_B = None, None
        try:
            if _resid_A(T_min) * _resid_A(T_max) < 0:
                T_liq_A = brentq(_resid_A, T_min, T_max, xtol=0.1)
        except Exception: pass
        
        try:
            if _resid_B(T_min) * _resid_B(T_max) < 0:
                T_liq_B = brentq(_resid_B, T_min, T_max, xtol=0.1)
        except Exception: pass

        T_liquidus, primary_phase_comp = None, None
        if T_liq_A is not None and T_liq_B is not None:
            T_liquidus = max(T_liq_A, T_liq_B)
            primary_phase_comp = comp_A if T_liq_A >= T_liq_B else comp_B
        elif T_liq_A is not None:
            T_liquidus = T_liq_A; primary_phase_comp = comp_A
        elif T_liq_B is not None:
            T_liquidus = T_liq_B; primary_phase_comp = comp_B
        else:
            raise RuntimeError(f"二元液相线求解失败(Pure Model) (x_L={x_B_overall}): 无法为任一组分包围熔点。")

        solid_comp_eq = {comp_A: 0.0, comp_B: 0.0}; solid_comp_eq[primary_phase_comp] = 1.0
        return {"status": "success", "T_liquidus": T_liquidus, "liquid_composition": comp_dict_L, "solid_composition_eq": solid_comp_eq}

    def _solve_solidus_binary_pure(self, x_B_overall: float, comp_A: str, comp_B: str, solid_phase_A: str, solid_phase_B: str, T_guess: float, x_L_guess: float, extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> dict:
        """ (V3.2 Logic) 求解 L <-> Pure_A + Pure_B (二元共晶) 固相线 """
        x_S_input_comp = {comp_A: 1.0 - x_B_overall, comp_B: x_B_overall}
        def _residuals(unknowns):
            T, x_L_calc = unknowns; x_L = self._check_bounds(x_L_calc)
            comp_dict_L = {comp_A: 1.0 - x_L, comp_B: x_L}
            mu_A_L = self._get_chemical_potential(comp_dict_L, comp_A, T, 'LIQUID', extrapolation_model, activity_model)
            mu_B_L = self._get_chemical_potential(comp_dict_L, comp_B, T, 'LIQUID', extrapolation_model, activity_model)
            mu_A_S_pure = self.tdb_parser.get_gibbs_energy(comp_A, solid_phase_A, T)
            mu_B_S_pure = self.tdb_parser.get_gibbs_energy(comp_B, solid_phase_B, T)
            if any(v is None for v in [mu_A_L, mu_A_S_pure, mu_B_L, mu_B_S_pure]): return [1e10, 1e10]
            return [mu_A_L - mu_A_S_pure, mu_B_L - mu_B_S_pure]
        
        sol = root(_residuals, [T_guess, x_L_guess], method='lm')
        if not sol.success: raise RuntimeError(f"二元固相线(共晶)求解失败(Pure Model) (x_S={x_B_overall}): {sol.message}")
        return {"status": "success", "T_solidus": sol.x[0], "solid_composition": x_S_input_comp, "liquid_composition_eq": {comp_A: 1.0-sol.x[1], comp_B: sol.x[1]}}

    def calculate_liquidus_temp_robust_pure(self,
                                            liquid_composition: Dict[str, float],
                                            solid_phase_map: Dict[str, str],
                                            extrapolation_model: str = 'UEM1',
                                            activity_model: str = 'Wagner'
                                            ) -> dict:
        """ (V3.2 Logic) 健壮地计算多元液相线 (Pure Model) """
        solvent = max(liquid_composition.items(), key=lambda x: x[1])[0]
        solutes = [c for c in liquid_composition.keys() if c != solvent]
        T_guess = 1750.0
        try:
            T_melt_solvent = self.calculate_pure_melting_point(solvent, solid_phase_map[solvent])
            if T_melt_solvent:
                T_weighted = T_melt_solvent * liquid_composition[solvent]
                missing_tm = False
                for solute in solutes:
                    T_melt_solute = self.calculate_pure_melting_point(solute, solid_phase_map.get(solute))
                    if T_melt_solute:
                        T_weighted += T_melt_solute * liquid_composition[solute]
                    else:
                        missing_tm = True
                        T_weighted += T_melt_solvent * liquid_composition[solute]
                T_guess = T_weighted - 50
                if not missing_tm:
                    print(f"  (Info-Pure) 使用加权平均 T_guess: {T_guess:.1f} K")
                else:
                    print(f"  (Info-Pure) 缺少部分纯元素熔点，使用近似 T_guess: {T_guess:.1f} K")
            else:
                 print(f"  (Warning-Pure) 无法计算溶剂 {solvent} 熔点，使用默认 T_guess: {T_guess:.1f} K")
        except Exception:
             print(f"  (Warning-Pure) T_guess 自动计算失败，使用默认 T_guess: {T_guess:.1f} K")
        
        solid_guess_placeholder = {} # Pure model 不需要
        try:
            result = self._solve_liquidus_multi_pure(
                liquid_composition, solid_phase_map, T_guess, solid_guess_placeholder,
                extrapolation_model, activity_model
            )
            T_result = result['T_liquidus']
            if 300 < T_result < 6000:
                return result
            else:
                raise RuntimeError(f"收敛到非物理温度 T={T_result:.1f}K")
        except Exception as e:
            raise RuntimeError(f"多元液相线求解器(Pure Model)未能找到 {liquid_composition} 的有效温度。 错误: {e}")

    def calculate_solidus_temp_robust_pure(self,
                                           solid_composition: Dict[str, float],
                                           solid_phase_map: Dict[str, str],
                                           extrapolation_model: str = 'UEM1',
                                           activity_model: str = 'Wagner'
                                           ) -> dict:
        """ (V3.2 Logic) 健壮地计算多元固相线 (Pure Model, 共晶) """
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
                T_guess = T_weighted - 150
                print(f"  (Info-Pure) 使用加权平均 T_guess: {T_guess:.1f} K")
            else:
                print(f"  (Warning-Pure) 无法计算溶剂 {solvent} 熔点，使用默认 T_guess: {T_guess:.1f} K")
        except Exception:
             print(f"  (Warning-Pure) T_guess 自动计算失败，使用默认 T_guess: {T_guess:.1f} K")
        
        guess_strategies = [
            self._auto_generate_solute_guess(solid_composition, default_k=1.2),
            {s: solid_composition[s] for s in solutes},
            self._auto_generate_solute_guess(solid_composition, default_k=2.0),
        ]
        last_exception = None
        for i, liquid_guess in enumerate(guess_strategies):
            try:
                result = self._solve_solidus_multi_pure(
                    solid_composition, solid_phase_map, T_guess, liquid_guess,
                    extrapolation_model, activity_model
                )
                T_result = result['T_solidus']
                if 300 < T_result < 6000:
                    return result
                else:
                    last_exception = RuntimeError(f"Converged to non-physical T={T_result:.1f}K")
            except Exception as e:
                last_exception = e
        raise RuntimeError(f"所有Pure策略均未能找到 {solid_composition} 的有效固相线(共晶)温度。 最后错误: {last_exception}")

    def _solve_liquidus_multi_pure(self, liquid_composition: Dict[str, float], solid_phase_map: Dict[str, str], T_guess: float, solid_solute_comp_guess: Dict[str, float], extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> dict:
        """ (V3.2 Logic) 求解 L <-> Pure (多元) 液相线 """
        all_components = list(liquid_composition.keys())
        X_L = {c: self._check_bounds(x) for c, x in liquid_composition.items()}
        T_liquidus_all_comps = []
        T_min_overall, T_max_overall = 300.0, 6000.0
        all_T_melts_found = True
        valid_T_melts = []

        for comp in all_components:
            solid_phase = solid_phase_map.get(comp)
            if solid_phase is None: raise ValueError(f"solid_phase_map 中未定义组分 {comp} 的固相")
            T_m = self.calculate_pure_melting_point(comp, solid_phase)
            if T_m is None: all_T_melts_found = False
            else: valid_T_melts.append(T_m)

        if all_T_melts_found and valid_T_melts:
            T_min_overall = min(valid_T_melts) - 500
            T_max_overall = max(valid_T_melts) + 500

        for comp in all_components:
            solid_phase = solid_phase_map[comp]
            def _resid_comp(T: float) -> float:
                mu_L = self._get_chemical_potential(X_L, comp, T, 'LIQUID', extrapolation_model, activity_model)
                mu_S_pure = self.tdb_parser.get_gibbs_energy(comp, solid_phase, T)
                if mu_L is None or mu_S_pure is None: return 1e10
                return mu_L - mu_S_pure
            try:
                if _resid_comp(T_min_overall) * _resid_comp(T_max_overall) < 0:
                    T_liq_comp = brentq(_resid_comp, T_min_overall, T_max_overall, xtol=0.1)
                    T_liquidus_all_comps.append((T_liq_comp, comp))
            except Exception: pass

        if not T_liquidus_all_comps:
             raise RuntimeError(f"多元液相线求解失败(Pure Model): 无法为任一组分包围熔点。")

        T_liquidus, primary_phase_comp = max(T_liquidus_all_comps, key=lambda item: item[0])
        final_solid_comp = {c: 0.0 for c in all_components}; final_solid_comp[primary_phase_comp] = 1.0
        return {"status": "success", "T_liquidus": T_liquidus, "liquid_composition": liquid_composition, "solid_composition_eq": final_solid_comp}

    def _solve_solidus_multi_pure(self, solid_composition: Dict[str, float], solid_phase_map: Dict[str, str], T_guess: float, liquid_solute_comp_guess: Dict[str, float], extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> dict:
        """ (V3.2 Logic) 求解 L <-> Pure_A + ... (多元共晶) 固相线 """
        solvent = max(solid_composition.items(), key=lambda x: x[1])[0]
        solutes = [c for c in solid_composition.keys() if c != solvent]
        all_components = [solvent] + solutes
        
        def _residuals(unknowns):
            T = unknowns[0]
            X_L_solutes = {solute: self._check_bounds(unknowns[i+1]) for i, solute in enumerate(solutes)}
            x_l_solvent = 1.0 - sum(X_L_solutes.values())
            X_L = {solvent: self._check_bounds(x_l_solvent), **X_L_solutes}
            residuals = []
            for comp in all_components:
                solid_phase = solid_phase_map.get(comp)
                if solid_phase is None: raise ValueError(f"solid_phase_map 中未定义组分 {comp} 的固相")
                mu_L = self._get_chemical_potential(X_L, comp, T, 'LIQUID', extrapolation_model, activity_model)
                mu_S_pure = self.tdb_parser.get_gibbs_energy(comp, solid_phase, T)
                if mu_L is None or mu_S_pure is None: return [1e10] * len(all_components)
                residuals.append(mu_L - mu_S_pure)
            return residuals

        initial_guesses = [T_guess] + [liquid_solute_comp_guess.get(s, 0.0) for s in solutes]
        sol = root(_residuals, initial_guesses, method='lm')
        if not sol.success: raise RuntimeError(f"多元固相线(共晶)求解失败(Pure Model): {sol.message}")
        
        T_solidus_eutectic = sol.x[0]
        final_liquid_solutes = {solute: sol.x[i+1] for i, solute in enumerate(solutes)}
        final_liquid_solvent = 1.0 - sum(final_liquid_solutes.values())
        final_liquid_comp_eutectic = {solvent: final_liquid_solvent, **final_liquid_solutes}
        
        return {"status": "success", "T_solidus": T_solidus_eutectic, "solid_composition": solid_composition, "liquid_composition_eq": final_liquid_comp_eutectic}
    
    # ================================================================
    # =================== 新增：溶解度计算器，液相中的溶解度 ===================
    # ================================================================
    def calculate_solubility (self,
                              base_alloy_composition: Dict[str, float],
                              solute_element: str,
                              solution_phase: str,
                              precipitating_phase: str,
                              temperature: float,
                              extrapolation_model: str = 'UEM1',
                              activity_model: str = 'Wagner',
                              min_solubility: float = 1e-9,
                              max_solubility: float = 0.999) -> dict:
        """
        (V4.2 - 新增) 计算指定溶质在多元溶液相中的溶解度极限。

        这适用于:
        1. 固溶体溶解度:
           e.g., C 在 BCC_A2(Fe,Si) 中的溶解度 (平衡相: GRAPHITE)
        2. 液相溶解度:
           e.g., C 在 LIQUID(Fe,Si) 中的溶解度 (平衡相: GRAPHITE)

        算法:
        求解 $X_i$ 使得 μ_i^Solution(T, X_Solution) = G^0_i,Precipitate(T)

        Args:
            base_alloy_composition (Dict): 基础合金（溶剂）的成分, e.g., {'FE': 0.7, 'SI': 0.3}
            solute_element (str): 待计算溶解度的溶质, e.g., 'C'
            solution_phase (str): 溶质溶解于的相, e.g., 'BCC_A2' 或 'LIQUID'
            precipitating_phase (str): 溶质析出时形成的纯固相, e.g., 'GRAPHITE'
            temperature (float): 固定的温度 (K)
            min_solubility (float): 求解器下限
            max_solubility (float): 求解器上限 (必须 < 1.0)

        Returns:
            dict: 求解结果
        """
        
        # 确定相态类型（液相或固相）
        phase_type = "液态" if solution_phase == "LIQUID" else "固态"
        phase_state = "liquid" if solution_phase == "LIQUID" else "solid"

        print(f"(Info) 开始计算 {solute_element} 在 {phase_type} {solution_phase} 相中的溶解度 @ {temperature}K...")
        print(f"       (基础合金: {base_alloy_composition})")
        print(f"       (析出相: {precipitating_phase})")
        print(f"       (相态: {phase_state}, 外推模型: {extrapolation_model}, 活度模型: {activity_model})")

        # 1. 归一化基础合金成分
        base_total = sum(base_alloy_composition.values())
        if base_total == 0:
            raise ValueError("基础合金成分不能为空")
        normalized_base_comp = {elem: x / base_total for elem, x in base_alloy_composition.items()}

        # 2. 获取析出相的纯固相 Gibbs 能量
        g_precipitate_pure = self.tdb_parser.get_gibbs_energy(solute_element, precipitating_phase, temperature)
        if g_precipitate_pure is None:
            raise RuntimeError(f"无法获取析出相 {solute_element} 在 {precipitating_phase} 相的纯 Gibbs 能量")

        print(f"       G°_{solute_element},{precipitating_phase} = {g_precipitate_pure:.2f} J/mol")
        
        # 3. 定义残差函数 f(x_solute) = mu_solution - g_precipitate
        def _solubility_residual (x_solute: float) -> float:
            """
            计算: μ_solute^Solution_Phase - G_solute^Precipitate_Phase
            """
            x_solute = self._check_bounds(x_solute, epsilon=min_solubility)
            
            # a. 根据 x_solute 重建当前的总成分
            total_solvent_fraction = 1.0 - x_solute
            current_solution_comp = {
                elem: x_base * total_solvent_fraction
                for elem, x_base in normalized_base_comp.items()
            }
            current_solution_comp[solute_element] = x_solute
            
            # b. 计算溶质在“溶液相”中的化学势
            #    (使用通用的 _get_chemical_potential 辅助函数)
            mu_in_solution = self._get_chemical_potential(
                    composition=current_solution_comp,
                    component=solute_element,
                    temperature=temperature,
                    tdb_phase=solution_phase,  # e.g., 'BCC_A2' 或 'LIQUID'
                    extrapolation_model=extrapolation_model,
                    activity_model=activity_model
            )
            
            if mu_in_solution is None:
                raise ValueError(f"无法在 T={temperature}K, x_{solute_element}={x_solute} 时计算化学势")
            
            # c. 返回差值
            return mu_in_solution - g_precipitate_pure
        
        # 4. 求解
        try:
            # 检查边界
            f_low = _solubility_residual(min_solubility)
            f_high = _solubility_residual(max_solubility)
            
            if f_low * f_high >= 0:
                if f_low < 0 and f_high < 0:
                    # 在 x=0.999 时 mu_liq 仍低于 g_sol_pure，表明完全溶解
                    print(f"  (Info) {solute_element} 在 {solution_phase} 中完全溶解。")
                    return {"status": "fully_soluble", "solubility": 1.0, "T": temperature}
                else:  # f_low > 0
                    # 在 x=1e-9 时 mu_liq 就已高于 g_sol_pure，表明几乎不溶
                    print(f"  (Info) {solute_element} 在 {solution_phase} 中几乎不溶。")
                    return {"status": "insoluble", "solubility": 0.0, "T": temperature}
            
            # 调用 brentq 求解
            solubility = brentq(_solubility_residual, min_solubility, max_solubility, xtol=1e-6)
            
            return {
                "status": "success",
                "T": temperature,
                "solute": solute_element,
                "solution_phase": solution_phase,
                "precipitating_phase": precipitating_phase,
                "solubility_mole_fraction": solubility,  # This is X_i
                "base_alloy": normalized_base_comp
            }
        except Exception as e:
            raise RuntimeError(f"计算 {solution_phase} 中 {solute_element} 的溶解度失败: {e}")
    # ================================================================
    # =================== 新增：溶解度计算器 ，固溶体中的溶解度===================
    # ================================================================
    
    
    
    
    def _get_default_solid_phase_map(self, composition: Dict[str, float]) -> Dict[str, str]:
        """
        为给定的成分生成默认的固相映射
        基于常见元素的标准固相
        """
        # 常见元素的默认固相
        default_phases = {
            'FE': 'BCC_A2',      # 铁素体 (α-Fe)
            'C': 'GRAPHITE',     # 石墨
            'CR': 'BCC_A2',      # Cr也是BCC
            'NI': 'FCC_A1',      # 镍（面心立方）
            'MN': 'CBCC_A12',    # 锰
            'SI': 'DIAMOND_A4',  # 硅（金刚石结构）
            'MO': 'BCC_A2',      # 钼
            'W': 'BCC_A2',       # 钨
            'CO': 'HCP_A3',      # 钴（密排六方）
            'CU': 'FCC_A1',      # 铜
            'AL': 'FCC_A1',      # 铝
            'TI': 'HCP_A3',      # 钛
            'V': 'BCC_A2',       # 钒
            'NB': 'BCC_A2',      # 铌
            'ZR': 'HCP_A3',      # 锆
        }

        solid_phase_map = {}
        for element in composition.keys():
            elem_upper = element.upper()
            if elem_upper in default_phases:
                solid_phase_map[elem_upper] = default_phases[elem_upper]
            else:
                # 未知元素默认使用BCC_A2
                solid_phase_map[elem_upper] = 'BCC_A2'
                print(f"Warning: 未知元素 {elem_upper}，默认使用 BCC_A2 作为固相")

        return solid_phase_map

    def calculate_liquidus_temperature(self,
                                      composition: Dict[str, float],
                                      extrapolation_model: str = 'UEM1',
                                      activity_model: str = 'Wagner',
                                      solid_model_type: str = 'PURE_SOLID') -> Optional[float]:
        """
        GUI兼容性方法：计算液相线温度（简化接口）

        Args:
            composition: 液相成分字典，如 {'Fe': 0.97, 'C': 0.03}
            extrapolation_model: 外推模型
            activity_model: 活度模型
            solid_model_type: 固相模型类型 ('SOLID_SOLUTION' 或 'PURE_SOLID')

        Returns:
            液相线温度 (K)，如果计算失败返回 None
        """
        try:
            # 统一转为大写符号（TDB数据库使用大写）
            composition_upper = {k.upper(): v for k, v in composition.items()}

            # 自动生成 solid_phase_map（使用大写符号）
            solid_phase_map = self._get_default_solid_phase_map(composition_upper)

            # 调用完整的 calculate_liquidus 方法
            result = self.calculate_liquidus(
                composition=composition_upper,
                solid_phase_map=solid_phase_map,
                extrapolation_model=extrapolation_model,
                activity_model=activity_model,
                solid_model_type=solid_model_type
            )

            if result['status'] == 'success':
                return result['T_liquidus']
            else:
                return None

        except Exception as e:
            print(f"Error calculating liquidus temperature: {e}")
            import traceback
            traceback.print_exc()
            return None

    def calculate_solidus_temperature(self,
                                     composition: Dict[str, float],
                                     extrapolation_model: str = 'UEM1',
                                     activity_model: str = 'Wagner',
                                     solid_model_type: str = 'PURE_SOLID') -> Optional[float]:
        """
        GUI兼容性方法：计算固相线温度（简化接口）

        Args:
            composition: 固相成分字典，如 {'Fe': 0.97, 'C': 0.03}
            extrapolation_model: 外推模型
            activity_model: 活度模型
            solid_model_type: 固相模型类型 ('SOLID_SOLUTION' 或 'PURE_SOLID')

        Returns:
            固相线温度 (K)，如果计算失败返回 None
        """
        try:
            # 统一转为大写符号（TDB数据库使用大写）
            composition_upper = {k.upper(): v for k, v in composition.items()}

            # 自动生成 solid_phase_map（使用大写符号）
            solid_phase_map = self._get_default_solid_phase_map(composition_upper)

            # 调用完整的 calculate_solidus 方法
            result = self.calculate_solidus(
                composition=composition_upper,
                solid_phase_map=solid_phase_map,
                extrapolation_model=extrapolation_model,
                activity_model=activity_model,
                solid_model_type=solid_model_type
            )

            if result['status'] == 'success':
                return result['T_solidus']
            else:
                return None

        except Exception as e:
            print(f"Error calculating solidus temperature: {e}")
            import traceback
            traceback.print_exc()
            return None

    def calculate_binary_phase_diagram(self,
                                       component_a: str,
                                       component_b: str,
                                       n_points: int = 20,
                                       extrapolation_model: str = 'UEM1',
                                       activity_model: str = 'Wagner',
                                       solid_model_type: str = 'PURE_SOLID',
                                       progress_callback=None) -> Dict[str, List]:
        """
        GUI兼容性方法：计算二元相图

        Args:
            component_a: 组分A
            component_b: 组分B
            n_points: 采样点数
            extrapolation_model: 外推模型
            activity_model: 活度模型
            solid_model_type: 固相模型类型
            progress_callback: 可选的进度回调函数 progress_callback(current, total)

        Returns:
            包含 'x_b', 'T_liquidus', 'T_solidus' 的字典
        """
        results = {
            'x_b': [],
            'T_liquidus': [],
            'T_solidus': []
        }

        import numpy as np
        x_b_values = np.linspace(0.0, 1.0, n_points)

        for i, x_b in enumerate(x_b_values):
            # 更新进度
            if progress_callback:
                progress_callback(i + 1, len(x_b_values))

            x_a = 1.0 - x_b
            composition = {
                component_a.upper(): x_a,
                component_b.upper(): x_b
            }

            # 过滤掉极小的值
            composition = {k: v for k, v in composition.items() if v > 1e-6}

            if len(composition) == 0:
                continue

            T_liq = self.calculate_liquidus_temperature(
                composition, extrapolation_model, activity_model, solid_model_type
            )
            T_sol = self.calculate_solidus_temperature(
                composition, extrapolation_model, activity_model, solid_model_type
            )

            results['x_b'].append(x_b)
            results['T_liquidus'].append(T_liq)
            results['T_solidus'].append(T_sol)

        return results

    def calculate_phase_diagram_curve(self,
                                      base_composition: Dict[str, float],
                                      variable_component: str,
                                      x_min: float = 0.0,
                                      x_max: float = 1.0,
                                      n_points: int = 20,
                                      extrapolation_model: str = 'UEM1',
                                      activity_model: str = 'Wagner',
                                      solid_model_type: str = 'PURE_SOLID',
                                      progress_callback=None) -> Dict[str, List]:
        """
        GUI兼容性方法：计算成分变化曲线

        保证基础成分的含量比例保持不变，变化组分含量变化，
        基础成分的总含量 = 1 - 变化组分的含量

        Args:
            base_composition: 基础成分（不含变化组分），如 {'Fe': 0.97}
            variable_component: 变化的组分，如 'C'
            x_min: 变化组分的最小摩尔分数
            x_max: 变化组分的最大摩尔分数
            n_points: 采样点数
            extrapolation_model: 外推模型
            activity_model: 活度模型
            solid_model_type: 固相模型类型
            progress_callback: 可选的进度回调函数 progress_callback(current, total)

        Returns:
            包含 'x', 'T_liquidus', 'T_solidus' 的字典
        """
        results = {
            'x': [],
            'T_liquidus': [],
            'T_solidus': []
        }

        # 转为大写并移除variable_component（如果存在）
        variable_component_upper = variable_component.upper()
        base_composition_upper = {}
        for comp, x_i in base_composition.items():
            comp_upper = comp.upper()
            if comp_upper != variable_component_upper:
                base_composition_upper[comp_upper] = x_i

        # 计算基础成分的总量（用于归一化）
        base_total = sum(base_composition_upper.values())
        if base_total <= 0:
            # 如果没有基础成分，只能计算纯变化组分
            base_composition_upper = {}

        import numpy as np
        x_values = np.linspace(x_min, x_max, n_points)

        for i, x_var in enumerate(x_values):
            # 更新进度
            if progress_callback:
                progress_callback(i + 1, len(x_values))

            # 计算当前成分
            current_comp = {variable_component_upper: x_var}
            remaining = 1.0 - x_var

            # 按初始比例分配基础成分
            if base_total > 0:
                for comp, x_i in base_composition_upper.items():
                    # x_i / base_total 是该组分在基础成分中的比例
                    # 乘以 remaining 得到在总成分中的摩尔分数
                    current_comp[comp] = (x_i / base_total) * remaining

            # 验证归一化（应该已经是1.0）
            total = sum(current_comp.values())
            if abs(total - 1.0) > 1e-6:
                # 如果有误差，重新归一化
                current_comp = {k: v/total for k, v in current_comp.items()}

            T_liq = self.calculate_liquidus_temperature(
                current_comp, extrapolation_model, activity_model, solid_model_type
            )
            T_sol = self.calculate_solidus_temperature(
                current_comp, extrapolation_model, activity_model, solid_model_type
            )

            results['x'].append(x_var)
            results['T_liquidus'].append(T_liq if T_liq else None)
            results['T_solidus'].append(T_sol if T_sol else None)

        return results


# 为GUI向后兼容性添加类别名
PhaseDiagram = PhaseDiagramCalculator

# ================================================================
# =================== 测试代码 ===================
# ================================================================
if __name__ == "__main__":
    
    pd_calc = PhaseDiagramCalculator()
    
    # ... (原有的 Fe-Cr 和 Fe-C-Si 液相线测试) ...
    
    # ================================================================
    # =================== 1. 二元测试 (Fe-Cr) ===================
    # ================================================================
    
    print("\n" + "=" * 70)
    print("Binary Pure Solid Test (Fe-Cr)")
    print("[V4.1 Note] 使用纯固体模型计算 (模拟共晶系统)")
    print("=" * 70)
    
    binary_comp = {'FE': 0.5, 'CR': 0.5}
    binary_solid_map = {'FE': 'BCC_A2', 'CR': 'BCC_A2'}
    
    try:
        liquidus_result = pd_calc.calculate_liquidus(
                composition=binary_comp,
                solid_phase_map=binary_solid_map,
                is_solid_solution=False  # (重要) 强制使用纯固相模型
        )
        print(f"\n--- [V4] 液相线 (凝固点) @ {binary_comp} ---")
        print(f"  T_liquidus: {liquidus_result['T_liquidus']:.2f} K")
        print(f"  (首先析出的组分: {liquidus_result['precipitating_component']})")
        print(f"  (析出相: {liquidus_result['primary_solid_phase']})")
        
        print("\n  所有组元的单独平衡温度:")
        for comp, temp in liquidus_result['component_equilibrium_temps'].items():
            print(f"    T({comp}): {temp:.2f} K")
    
    except Exception as e:
        print(f"计算 Fe-Cr 液相线 (纯固相模型) 失败: {e}")
    
    print("=" * 70)
    
    # ================================================================
    # =================== 2. 多元测试 (Fe-C-Si) ===================
    # ================================================================
    
    print("\n" + "=" * 70)
    print("Multicomponent Pure Solid Test (Fe-C-Si)")
    print("[V4.1 Note] 使用纯固体模型计算")
    print("=" * 70)
    
    liq_comp = {
        'FE': 0.95,
        'C': 0.02,
        'SI': 0.03
    }
    
    solid_map_pure = {
        'FE': 'BCC_A2',  # Fe 的 TDB 参考相
        'C': 'GRAPHITE',  # C 的 TDB 参考相
        'SI': 'DIAMOND_A4'  # Si 的 TDB 参考相
    }
    
    try:
        print(f"\n--- 尝试计算: Liquid <-> 纯固相 @ {liq_comp} ---")
        multi_liq_result = pd_calc.calculate_liquidus(
                composition=liq_comp,
                solid_phase_map=solid_map_pure,
                is_solid_solution=False  # (重要) 告诉求解器这是一个纯固相模型
        )
        
        print(f"\n--- [V4] 多元液相线 (凝固点) ---")
        print(f"  T_liquidus: {multi_liq_result['T_liquidus']:.2f} K")
        print(f"  (首先析出的组分: {multi_liq_result['precipitating_component']})")
        print(f"  (析出相: {multi_liq_result['primary_solid_phase']})")
        
        print("\n  所有组元的单独平衡温度:")
        for comp, temp in multi_liq_result['component_equilibrium_temps'].items():
            print(f"    T({comp}): {temp:.2f} K")
    
    except Exception as e:
        print(f"计算 Fe-C-Si 液相线 (纯固相模型) 失败: {e}")
    
    print("=" * 70)
    
    # ================================================================
    # =================== 3. 固溶体溶解度测试 (C in Fe) ===================
    # ================================================================
    
    print("\n" + "=" * 70)
    print("Solid Solution Solubility Test (C in pure FE)")
    print("=" * 70)
    
    # 我们要计算 C 在 纯Fe 中的溶解度
    # 基础合金 = 纯 FE
    base_comp_fe = {'FE': 1.0}
    solute_c = 'C'
    
    # 溶液相是 BCC_A2 (铁素体)
    solution_phase_bcc = 'BCC_A2'
    
    # 析出相是 GRAPHITE
    precipitating_phase_c = 'GRAPHITE'
    
    # 在 1000 K (铁素体区) 计算
    T_test_sol = 1000.0
    
    # TDB 映射
    solid_map_solubility = {
        'FE': 'BCC_A2',
        'C': 'BCC_A2'  # (重要) C 在 BCC_A2 中的 G°
    }
    
    try:
        solubility_result = pd_calc.calculate_solubility(
                base_alloy_composition=base_comp_fe,
                solute_element=solute_c,
                solution_phase=solution_phase_bcc,
                precipitating_phase=precipitating_phase_c,
                temperature=T_test_sol,
                solid_phase_map=solid_map_solubility  # (注意: 此参数目前仅用于 'calculate_pure_melting_point'，
                #  但在未来版本中可能用于 _get_chemical_potential)
        )
        
        print(f"\n--- [V4.2] 溶解度计算 @ {T_test_sol} K ---")
        print(f"  溶质: {solute_c}")
        print(f"  溶液相: {solution_phase_bcc}")
        print(f"  析出相: {precipitating_phase_c}")
        print(f"  基础合金: {base_comp_fe}")
        print(f"  状态: {solubility_result['status']}")
        print(f"  溶解度 (摩尔分数): {solubility_result['solubility_mole_fraction']:.6f}")
    
    except Exception as e:
        print(f"计算 C 在 Fe 中的溶解度失败: {e}")
    
    print("=" * 70)