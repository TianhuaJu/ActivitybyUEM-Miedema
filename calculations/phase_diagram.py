"""
Phase Diagram Calculator
========================
计算二元及多元稀溶液的液相线 (Liquidus) 和固相线 (Solidus) 温度。

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
from scipy.optimize import root

# 添加项目根目录到路径
# (假设此文件与 thermodynamic_properties.py 位于同一文件夹)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 从分离的文件中导入基类
from calculations.thermodynamic_properties import ThermodynamicProperties


class PhaseDiagramCalculator(ThermodynamicProperties):
    """
    通过继承 ThermodynamicProperties 类，
    实现液相线和固相线的计算。
    """

    def __init__(self):
        """
        初始化相图计算器。
        这将自动调用父类(ThermodynamicProperties)的 __init__，
        从而加载 TDB 解析器和活度计算器。
        """
        super().__init__()

    @staticmethod
    def _check_bounds(x, epsilon=1e-9):
        """防止 log(0) 或 log(1) 出现数值错误"""
        if x < epsilon:
            return epsilon
        if x > 1.0 - epsilon:
            return 1.0 - epsilon
        return x

    # ================================================================
    # =================== 内部辅助函数 ===================
    # ================================================================

    def _get_chemical_potential(self,
                               composition: Dict[str, float],
                               component: str,
                               temperature: float,
                               tdb_phase: str, # 'LIQUID', 'BCC_A2', etc.
                               extrapolation_model: str,
                               activity_model: str) -> Optional[float]:
        """
        (新增) 计算化学势的内部辅助函数。
        
        μ_i = G°_i(T) + RT*ln(x_i) + RT*ln(γ_i)
        
        这与父类中的 'calculate_chemical_potential' 不同，
        因为它需要一个显式的 tdb_phase (如 'BCC_A2')
        而不是一个通用的 'solid'。
        """
        
        # 1. 获取 G° (来自 TDB)
        # (使用父类的 tdb_parser)
        mu_0 = self.tdb_parser.get_gibbs_energy(component, tdb_phase, temperature)
        if mu_0 is None:
            print(f"Warning: _get_chemical_potential: Could not find G° for {component} in {tdb_phase}")
            return None

        # 2. 获取 ln(gamma) (来自 Miedema/UEM)
        # (使用父类的活度计算器)
        activity_phase_state = 'liquid' if tdb_phase == 'LIQUID' else 'solid'
        
        ln_gamma = self.calculate_ln_activity_coefficient(
            composition, component, temperature, activity_phase_state,
            None, extrapolation_model, activity_model # None = 自动检测溶剂
        )
        if ln_gamma is None:
            print(f"Warning: _get_chemical_potential: Could not get ln(gamma) for {component} in {tdb_phase}")
            return None
        
        # 3. 获取摩尔分数
        x_i = self._check_bounds(composition.get(component, 0.0))
        
        # 4. 计算化学势
        mu = mu_0 + self.R * temperature * (math.log(x_i) + ln_gamma)
        return mu

    # ================================================================
    # =================== (保留) 二元求解器 ===================
    # ================================================================

    def calculate_liquidus_temp(self,
                                x_B_overall: float,
                                comp_A: str,
                                comp_B: str,
                                solid_phase_A: str,
                                solid_phase_B: str,
                                T_guess: float,
                                x_S_guess: float,
                                extrapolation_model: str = 'UEM1',
                                activity_model: str = 'Wagner'
                                ) -> dict:
        """
        (二元) 计算给定液相组成 (x_B_overall) 时的液相线温度 (T_liq) 和
        与之平衡的固相组成 (x_S)。
        """
        
        x_L = self._check_bounds(x_B_overall)
        
        def _residuals(unknowns):
            T, x_S_calc = unknowns
            x_S = self._check_bounds(x_S_calc)
            
            comp_dict_L = {comp_A: 1.0 - x_L, comp_B: x_L}
            comp_dict_S = {comp_A: 1.0 - x_S, comp_B: x_S}
            
            mu_A_L = self._get_chemical_potential(comp_dict_L, comp_A, T, 'LIQUID', extrapolation_model, activity_model)
            mu_A_S = self._get_chemical_potential(comp_dict_S, comp_A, T, solid_phase_A, extrapolation_model, activity_model)
            mu_B_L = self._get_chemical_potential(comp_dict_L, comp_B, T, 'LIQUID', extrapolation_model, activity_model)
            mu_B_S = self._get_chemical_potential(comp_dict_S, comp_B, T, solid_phase_B, extrapolation_model, activity_model)
            
            if any(v is None for v in [mu_A_L, mu_A_S, mu_B_L, mu_B_S]):
                return [1e10, 1e10] # 无法计算，返回巨大残差

            return [mu_A_L - mu_A_S, mu_B_L - mu_B_S]

        sol = root(_residuals, [T_guess, x_S_guess], method='lm')
        
        if not sol.success:
            raise RuntimeError(f"二元液相线求解失败 (x_L={x_B_overall}): {sol.message}")

        return {
            "status": "success",
            "T_liquidus": sol.x[0],
            "x_L": x_B_overall,
            "x_S_equilibrium": sol.x[1]
        }


    def calculate_solidus_temp(self,
                               x_B_overall: float,
                               comp_A: str,
                               comp_B: str,
                               solid_phase_A: str,
                               solid_phase_B: str,
                               T_guess: float,
                               x_L_guess: float,
                               extrapolation_model: str = 'UEM1',
                               activity_model: str = 'Wagner'
                               ) -> dict:
        """
        (二元) 计算给定固相组成 (x_B_overall) 时的固相线温度 (T_sol) 和
        与之平衡的液相组成 (x_L)。
        """
        
        x_S = self._check_bounds(x_B_overall)
        
        def _residuals(unknowns):
            T, x_L_calc = unknowns
            x_L = self._check_bounds(x_L_calc)
            
            comp_dict_L = {comp_A: 1.0 - x_L, comp_B: x_L}
            comp_dict_S = {comp_A: 1.0 - x_S, comp_B: x_S}

            mu_A_L = self._get_chemical_potential(comp_dict_L, comp_A, T, 'LIQUID', extrapolation_model, activity_model)
            mu_A_S = self._get_chemical_potential(comp_dict_S, comp_A, T, solid_phase_A, extrapolation_model, activity_model)
            mu_B_L = self._get_chemical_potential(comp_dict_L, comp_B, T, 'LIQUID', extrapolation_model, activity_model)
            mu_B_S = self._get_chemical_potential(comp_dict_S, comp_B, T, solid_phase_B, extrapolation_model, activity_model)

            if any(v is None for v in [mu_A_L, mu_A_S, mu_B_L, mu_B_S]):
                return [1e10, 1e10] # 无法计算，返回巨大残差
                
            return [mu_A_L - mu_A_S, mu_B_L - mu_B_S]

        sol = root(_residuals, [T_guess, x_L_guess], method='lm')
        
        if not sol.success:
            raise RuntimeError(f"二元固相线求解失败 (x_S={x_B_overall}): {sol.message}")

        return {
            "status": "success",
            "T_solidus": sol.x[0],
            "x_S": x_B_overall,
            "x_L_equilibrium": sol.x[1]
        }

    # ================================================================
    # =================== 新增：多元求解器 ===================
    # ================================================================

    def calculate_liquidus_temp_multicomponent(self,
                                               liquid_composition: Dict[str, float],
                                               solid_phase_map: Dict[str, str],
                                               T_guess: float,
                                               solid_solute_comp_guess: Dict[str, float],
                                               extrapolation_model: str = 'UEM1',
                                               activity_model: str = 'Wagner'
                                               ) -> dict:
        """
        (多元) 计算给定液相组成时的液相线温度 (T_liq) 和
        与之平衡的固相组成 (X_S)。
        
        Args:
            liquid_composition (Dict): 固定的液相成分, e.g., {'FE': 0.95, 'C': 0.02, 'SI': 0.03}
            solid_phase_map (Dict): 每个组元在固相中的TDB相名称, e.g., {'FE': 'BCC_A2', 'C': 'GRAPHITE', 'SI': 'BCC_A2'}
            T_guess (float): 初始猜测温度
            solid_solute_comp_guess (Dict): 初始猜测固相中【溶质】的成分, e.g., {'C': 0.01, 'SI': 0.02}
            
        Returns:
            dict: 求解结果
        """
        
        # 1. 确定溶剂和溶质
        solvent = max(liquid_composition.items(), key=lambda x: x[1])[0]
        solutes = [c for c in liquid_composition.keys() if c != solvent]
        all_components = [solvent] + solutes
        
        X_L = {c: self._check_bounds(x) for c, x in liquid_composition.items()}
        
        def _residuals(unknowns):
            """
            求解 N 个方程 (N=组元数)
            未知数 (N个): [T, y_solute1, y_solute2, ..., y_solute(N-1)]
            """
            T = unknowns[0]
            
            # 2. 重建固相成分
            X_S_solutes = {solute: self._check_bounds(unknowns[i+1]) for i, solute in enumerate(solutes)}
            x_s_solvent = 1.0 - sum(X_S_solutes.values())
            X_S = {solvent: self._check_bounds(x_s_solvent), **X_S_solutes}
            
            residuals = []
            
            # 3. 建立 N 个化学势平衡方程
            for comp in all_components:
                solid_phase = solid_phase_map.get(comp)
                if solid_phase is None:
                    raise ValueError(f"solid_phase_map 中未定义组分 {comp} 的固相")
                    
                mu_L = self._get_chemical_potential(
                    X_L, comp, T, 'LIQUID', extrapolation_model, activity_model
                )
                mu_S = self._get_chemical_potential(
                    X_S, comp, T, solid_phase, extrapolation_model, activity_model
                )
                
                if mu_L is None or mu_S is None:
                    # TDB 或活度系数计算失败
                    return [1e10] * len(all_components)
                    
                residuals.append(mu_L - mu_S)
                
            return residuals

        # 4. 准备求解
        initial_guesses = [T_guess] + [solid_solute_comp_guess.get(s, 0.0) for s in solutes]
        
        sol = root(_residuals, initial_guesses, method='lm')
        
        if not sol.success:
            raise RuntimeError(f"多元液相线求解失败: {sol.message}")

        # 5. 解包结果
        T_liquidus = sol.x[0]
        final_solid_solutes = {solute: sol.x[i+1] for i, solute in enumerate(solutes)}
        final_solid_solvent = 1.0 - sum(final_solid_solutes.values())
        final_solid_comp = {solvent: final_solid_solvent, **final_solid_solutes}
        
        return {
            "status": "success",
            "T_liquidus": T_liquidus,
            "liquid_composition": liquid_composition,
            "solid_composition_eq": final_solid_comp
        }

    def calculate_solidus_temp_multicomponent(self,
                                              solid_composition: Dict[str, float],
                                              solid_phase_map: Dict[str, str],
                                              T_guess: float,
                                              liquid_solute_comp_guess: Dict[str, float],
                                              extrapolation_model: str = 'UEM1',
                                              activity_model: str = 'Wagner'
                                              ) -> dict:
        """
        (多元) 计算给定固相组成时的固相线温度 (T_sol) 和
        与之平衡的液相组成 (X_L)。
        
        Args:
            solid_composition (Dict): 固定的固相成分, e.g., {'FE': 0.95, 'C': 0.02, 'SI': 0.03}
            solid_phase_map (Dict): 每个组元在固相中的TDB相名称
            T_guess (float): 初始猜测温度
            liquid_solute_comp_guess (Dict): 初始猜测液相中【溶质】的成分, e.g., {'C': 0.03, 'SI': 0.04}
            
        Returns:
            dict: 求解结果
        """
        
        solvent = max(solid_composition.items(), key=lambda x: x[1])[0]
        solutes = [c for c in solid_composition.keys() if c != solvent]
        all_components = [solvent] + solutes
        
        X_S = {c: self._check_bounds(x) for c, x in solid_composition.items()}
        
        def _residuals(unknowns):
            # 未知数: [T, x_solute1, x_solute2, ...]
            T = unknowns[0]
            
            X_L_solutes = {solute: self._check_bounds(unknowns[i+1]) for i, solute in enumerate(solutes)}
            x_l_solvent = 1.0 - sum(X_L_solutes.values())
            X_L = {solvent: self._check_bounds(x_l_solvent), **X_L_solutes}
            
            residuals = []
            
            for comp in all_components:
                solid_phase = solid_phase_map.get(comp)
                if solid_phase is None:
                    raise ValueError(f"solid_phase_map 中未定义组分 {comp} 的固相")
                    
                mu_L = self._get_chemical_potential(
                    X_L, comp, T, 'LIQUID', extrapolation_model, activity_model
                )
                mu_S = self._get_chemical_potential(
                    X_S, comp, T, solid_phase, extrapolation_model, activity_model
                )
                
                if mu_L is None or mu_S is None:
                    return [1e10] * len(all_components)
                    
                residuals.append(mu_L - mu_S)
                
            return residuals

        initial_guesses = [T_guess] + [liquid_solute_comp_guess.get(s, 0.0) for s in solutes]
        
        sol = root(_residuals, initial_guesses, method='lm')
        
        if not sol.success:
            raise RuntimeError(f"多元固相线求解失败: {sol.message}")

        T_solidus = sol.x[0]
        final_liquid_solutes = {solute: sol.x[i+1] for i, solute in enumerate(solutes)}
        final_liquid_solvent = 1.0 - sum(final_liquid_solutes.values())
        final_liquid_comp = {solvent: final_liquid_solvent, **final_liquid_solutes}
        
        return {
            "status": "success",
            "T_solidus": T_solidus,
            "solid_composition": solid_composition,
            "liquid_composition_eq": final_liquid_comp
        }

    # ================================================================
    # =================== GUI兼容性包装方法 ===================
    # ================================================================

    def get_melting_point(self, element: str) -> Optional[float]:
        """
        获取元素的熔点（从TDB数据库）
        为GUI兼容性保留的简化接口
        """
        # 简化方法：查找G(liquid) = G(solid)的温度
        # 使用常见金属的熔点作为参考
        common_melting_points = {
            'FE': 1811.0,  # Fe
            'AL': 933.47,  # Al
            'CU': 1357.77, # Cu
            'NI': 1728.0,  # Ni
            'CR': 2180.0,  # Cr
            'MN': 1519.0,  # Mn
            'SI': 1687.0,  # Si
            'C': 3823.0,   # C (石墨升华)
        }
        return common_melting_points.get(element.upper())

    def calculate_liquidus_temperature(self,
                                      composition: Dict[str, float],
                                      extrapolation_model: str = 'UEM1',
                                      activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算合金的液相线温度（简化方法）
        使用加权平均熔点作为估计
        为GUI兼容性保留的接口
        """
        try:
            if not composition or sum(composition.values()) == 0:
                return None

            T_weighted_sum = 0.0
            x_sum = 0.0

            for component, x_i in composition.items():
                if x_i > 0:
                    T_melt = self.get_melting_point(component)
                    if T_melt is not None:
                        T_weighted_sum += x_i * T_melt
                        x_sum += x_i

            if x_sum == 0:
                return None

            return T_weighted_sum / x_sum

        except Exception as e:
            print(f"Error calculating liquidus temperature: {e}")
            return None

    def calculate_solidus_temperature(self,
                                     composition: Dict[str, float],
                                     extrapolation_model: str = 'UEM1',
                                     activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算合金的固相线温度（简化方法）
        使用最低熔点作为估计
        为GUI兼容性保留的接口
        """
        try:
            if not composition or sum(composition.values()) == 0:
                return None

            T_solidus = float('inf')
            threshold = 0.001

            for component, x_i in composition.items():
                if x_i > threshold:
                    T_melt = self.get_melting_point(component)
                    if T_melt is not None and T_melt < T_solidus:
                        T_solidus = T_melt

            if T_solidus == float('inf'):
                return None

            return T_solidus

        except Exception as e:
            print(f"Error calculating solidus temperature: {e}")
            return None

    def calculate_binary_phase_diagram(self,
                                       component_a: str,
                                       component_b: str,
                                       n_points: int = 20,
                                       extrapolation_model: str = 'UEM1',
                                       activity_model: str = 'Wagner') -> Dict[str, List]:
        """
        计算二元相图（简化方法）
        为GUI兼容性保留的接口
        """
        results = {
            'x_b': [],
            'T_liquidus': [],
            'T_solidus': []
        }

        import numpy as np
        x_b_values = np.linspace(0.0, 1.0, n_points)

        for x_b in x_b_values:
            x_a = 1.0 - x_b
            composition = {
                component_a: x_a,
                component_b: x_b
            }
            composition = {k: v for k, v in composition.items() if v > 1e-6}

            if len(composition) == 0:
                continue

            T_liq = self.calculate_liquidus_temperature(
                composition, extrapolation_model, activity_model
            )
            T_sol = self.calculate_solidus_temperature(
                composition, extrapolation_model, activity_model
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
                                      activity_model: str = 'Wagner') -> Dict[str, List]:
        """
        计算液相线/固相线随某组分浓度变化的曲线（简化方法）
        为GUI兼容性保留的接口
        """
        results = {
            'x': [],
            'T_liquidus': [],
            'T_solidus': []
        }

        base_total = sum(base_composition.values())
        if base_total <= 0:
            base_composition = {}

        import numpy as np
        x_values = np.linspace(x_min, x_max, n_points)

        for x_var in x_values:
            current_comp = {variable_component: x_var}
            remaining = 1.0 - x_var

            for comp, x_i in base_composition.items():
                if comp != variable_component:
                    if base_total > 0:
                        current_comp[comp] = x_i / base_total * remaining
                    else:
                        current_comp[comp] = 0.0

            total = sum(current_comp.values())
            if total > 0:
                current_comp = {k: v/total for k, v in current_comp.items()}

            T_liq = self.calculate_liquidus_temperature(
                current_comp, extrapolation_model, activity_model
            )
            T_sol = self.calculate_solidus_temperature(
                current_comp, extrapolation_model, activity_model
            )

            results['x'].append(x_var)
            results['T_liquidus'].append(T_liq if T_liq else None)
            results['T_solidus'].append(T_sol if T_sol else None)

        return results


# 为GUI向后兼容性添加类别名
PhaseDiagram = PhaseDiagramCalculator


# 测试代码
if __name__ == "__main__":
    
    # --- 实例化 ---
    pd_calc = PhaseDiagramCalculator()
    
    # ================================================================
    # =================== 1. 二元测试 (Fe-Cr) ===================
    # ================================================================
    
    print("\n" + "=" * 70)
    print("Binary Liquidus/Solidus Calculation Test (Fe-Cr)")
    print("=" * 70)
    
    COMP_A = 'FE'
    COMP_B = 'CR'
    SOLID_A = 'BCC_A2'
    SOLID_B = 'BCC_A2'
    alloy_comp_B = 0.5  # 50% Cr
    
    # 初始猜测值
    T_guess_liq = 1800.0
    x_S_guess = 0.5
    T_guess_sol = 1750.0
    x_L_guess = 0.5
    
    try:
        liquidus_result = pd_calc.calculate_liquidus_temp(
            alloy_comp_B, COMP_A, COMP_B, SOLID_A, SOLID_B,
            T_guess_liq, x_S_guess
        )
        print(f"\n--- 液相线 (凝固点) @ x_CR = {alloy_comp_B} ---")
        print(f"  T_liquidus: {liquidus_result['T_liquidus']:.2f} K")
        print(f"  Equilibrium x_S: {liquidus_result['x_S_equilibrium']:.4f}")

    except Exception as e:
        print(f"计算 Fe-Cr 液相线失败: {e}")

    try:
        solidus_result = pd_calc.calculate_solidus_temp(
            alloy_comp_B, COMP_A, COMP_B, SOLID_A, SOLID_B,
            T_guess_sol, x_L_guess
        )
        print(f"\n--- 固相线 (熔点) @ x_CR = {alloy_comp_B} ---")
        print(f"  T_solidus: {solidus_result['T_solidus']:.2f} K")
        print(f"  Equilibrium x_L: {solidus_result['x_L_equilibrium']:.4f}")
        
    except Exception as e:
        print(f"计算 Fe-Cr 固相线失败: {e}")
        
    print("=" * 70)
    
    # ================================================================
    # =================== 2. 多元测试 (Fe-C-Si) ===================
    # ================================================================
    
    print("\n" + "=" * 70)
    print("Multicomponent Liquidus Calculation Test (Fe-C-Si)")
    print("=" * 70)

    # 1. 定义液相成分
    liq_comp = {
        'FE': 0.95,
        'C': 0.02,
        'SI': 0.03
    }
    
    # 2. 定义固相映射 (Fe 和 Si 形成 BCC, C 析出为石墨)
    #    (注意：这是一个简化的假设，实际钢中 C 可能形成 奥氏体/铁素体)
    solid_map = {
        'FE': 'BCC_A2',
        'C': 'GRAPHITE',
        'SI': 'BCC_A2'  # 假设 Si 固溶在 BCC_A2 中
    }
    
    # 3. 初始猜测值
    T_liq_guess = 1750.0 # 纯铁熔点 1811 K, 溶质使其降低
    # 猜测平衡固相中的溶质含量
    solid_solute_guess = {
        'C': 0.001,
        'SI': 0.02
    }
    
    try:
        multi_liq_result = pd_calc.calculate_liquidus_temp_multicomponent(
            liquid_composition=liq_comp,
            solid_phase_map=solid_map,
            T_guess=T_liq_guess,
            solid_solute_comp_guess=solid_solute_guess
        )
        
        print(f"\n--- 多元液相线 (凝固点) @ {liq_comp} ---")
        print(f"  T_liquidus: {multi_liq_result['T_liquidus']:.2f} K")
        print("  Equilibrium Solid Composition:")
        for comp, x in multi_liq_result['solid_composition_eq'].items():
            print(f"    x_{comp:<4}: {x:.6f}")
            
    except Exception as e:
        print(f"计算 Fe-C-Si 液相线失败: {e}")
        
    print("=" * 70)