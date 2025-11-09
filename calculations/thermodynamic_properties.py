"""
Thermodynamic Properties Calculator
====================================
(V3 - 使用 PyCalphad 作为 TDB 后端)

计算多组元合金的完整热力学性质
"""

import math
from typing import Dict, Optional, Tuple, List
import sys
import os

# --- (新增导入) ---
from pycalphad import Database, variables as v
from pycalphad import calculate
# --- (新增导入结束) ---

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- (移除 TDBParser) ---
# from core.tdb_parser import get_tdb_parser, TDBParser
# --- (移除结束) ---

from core.constants import Constants


class ThermodynamicProperties:
    """多组元合金热力学性质计算器"""

    def __init__(self):
        """初始化热力学性质计算器"""
        
        # --- (关键修改：使用 PyCalphad DB) ---
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tdb_path = os.path.join(current_dir, '..', 'database', 'data', 'unary50.tdb')
            tdb_path = os.path.normpath(tdb_path)
            if not os.path.exists(tdb_path):
                tdb_path = os.path.join(os.path.dirname(__file__), 'unary50.tdb')
                if not os.path.exists(tdb_path):
                     raise FileNotFoundError("无法在任何已知位置找到 unary50.tdb")
                     
            self.dbf = Database(tdb_path)
        except Exception as e:
            print(f"加载 TDB 数据库失败: {e}")
            raise
        # --- (修改结束) ---

        from calculations.activity_calculator import ActivityCoefficient
        from models.extrapolation_models import BinaryModel

        self.activity_calculator = ActivityCoefficient()
        self.binary_model = BinaryModel()
        self.R = Constants.R  # J/(mol*K)

    @staticmethod
    def _to_standard_symbol(symbol: str) -> str:
        """
        (关键修正)
        将TDB的大写符号 (例如 'FE') 转换为 Miedema 的标准符号 (例如 'Fe')。
        """
        if not symbol or len(symbol) == 0:
            return symbol
        return symbol.capitalize()

    # --- (新增辅助函数：PyCalphad G/H/S/Cp 计算器) ---
    def _get_pure_property(self, element: str, phase: str, T: float, P: float = 101325.0, output: str = 'G') -> Optional[float]:
        """
        (新增) 使用 pycalphad.calculate 获取纯物质的 G, H, S, Cp。
        """
        try:
            # 1. 检查所需相是否存在于 TDB 中
            if phase not in self.dbf.phases:
                # print(f"Warning: (pycalphad) 相 '{phase}' 不在 TDB 中。")
                if phase == "SER": # 'SER' 是一个请求，而不是一个真正的相
                     ref_phase = self.dbf.elements.get(element.upper()).reference_phase
                     if ref_phase is None:
                         # print(f"Warning: (pycalphad) 无法找到 {element} 的参考相")
                         return None
                     phase = ref_phase
                else:
                    return None
            
            # 2. 检查元素是否在 TDB 的该相中定义
            # (pycalphad 会在 calculate 中自动处理此问题)
            
            # 3. 组元列表
            comps = [element, 'VA'] # VA 是必须的
            
            # 4. 条件
            conds = {v.T: T, v.P: P, v.N: 1, v.X(element): 1.0}
            
            # 5. 调用 pycalphad
            result = calculate(self.dbf, comps, phase, **conds, output=output)
            
            value = float(result.values.item())
            
            # pycalphad 的 G, H 是相对于 SER=0@298K 的。这正是我们所需要的。
            return value
        except Exception as e:
            # 捕获 pycalphad 错误 (例如相未定义 'C' in 'BCC_A2')
            # print(f"pycalphad.calculate 失败 for {element}-{phase}-{output}: {e}")
            return None

    def calculate_activity(self,
                          composition: Dict[str, float],
                          component: str,
                          temperature: float,
                          phase_state: str = 'liquid',
                          solvent: str = None,
                          extrapolation_model: str = 'UEM1',
                          activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算组分的活度 a_i = γ_i * X_i
        """
        ln_gamma = self.calculate_ln_activity_coefficient(
            composition, component, temperature, phase_state,
            solvent, extrapolation_model, activity_model
        )
        if ln_gamma is None: return None
        gamma = math.exp(ln_gamma)
        x_i = composition.get(component, 0.0)
        activity = gamma * x_i
        return activity

    def calculate_ln_activity_coefficient(self,
                                         composition: Dict[str, float],
                                         component: str,
                                         temperature: float,
                                         phase_state: str = 'liquid',
                                         solvent: str = None,
                                         extrapolation_model: str = 'UEM1',
                                         activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算活度系数的对数 ln(γ_i)
        (已修正) 此函数将大写TDB符号(FE)转换为标准Miedema符号(Fe)。
        """
        # 1. 确定溶剂 (仍然使用大写符号)
        if solvent is None:
            if not composition: raise ValueError("Composition dictionary is empty")
            valid_components = {k: v for k, v in composition.items() if v > 0}
            if not valid_components: return 0.0
            solvent = max(valid_components.items(), key=lambda x: x[1])[0]
        # 2. 转换为标准符号
        try:
            comp_dict_std = {self._to_standard_symbol(k): v for k, v in composition.items()}
            component_std = self._to_standard_symbol(component)
            solvent_std = self._to_standard_symbol(solvent)
        except Exception as e:
            print(f"Error standardizing symbols: {e}"); return None
        
        self.activity_calculator._comp_dict = comp_dict_std.copy()
        from models.extrapolation_models import BinaryModel
        bm = BinaryModel(); extrap_func_map = {'UEM1': bm.UEM1, 'UEM2': bm.UEM2, 'UEM2-Adv': bm.UEM2_Adv, 'GSM': bm.GSM, 'Muggianu': bm.Muggianu, 'Toop-Kohler': bm.Toop_Kohler, 'Toop-Muggianu': bm.Toop_Muggianu}
        extrap_func = extrap_func_map.get(extrapolation_model, bm.UEM1)
        try:
            # 3. 使用标准符号 (Fe, C, Si) 调用
            ln_gamma = self.activity_calculator.get_ln_gamma(
                comp_dict=comp_dict_std, component_to_calculate=component_std, solvent=solvent_std,
                Tem=temperature, state=phase_state,
                extra_model=extrap_func, extra_model_name=extrapolation_model,
                activity_model=activity_model
            )
            return ln_gamma
        except Exception as e:
            print(f"Error calculating ln(γ) for {component} (as {component_std}): {e}"); return None

    def calculate_chemical_potential(self,
                                     composition: Dict[str, float],
                                     component: str,
                                     temperature: float,
                                     phase_state: str = 'liquid',
                                     solvent: str = None,
                                     extrapolation_model: str = 'UEM1',
                                     activity_model: str = 'Wagner') -> Optional[float]:
        """
        计算化学势 μ_i = G°_i(T) + RT ln(a_i)
        (已重写) 使用 pycalphad 获取 G°
        """
        phase_map = {'liquid': 'LIQUID', 'solid': 'SER'}
        tdb_phase = phase_map.get(phase_state.lower(), 'LIQUID')

        # 1. (已重写) 使用 pycalphad 获取 G°
        mu_0 = self._get_pure_property(component, tdb_phase, temperature, 101325, 'G')
        if mu_0 is None:
            print(f"Warning: Could not find G° for {component} in {tdb_phase} phase at T={temperature}K")
            return None

        # 2. (正确) 内部函数将处理转换
        activity = self.calculate_activity(
            composition, component, temperature, phase_state,
            solvent, extrapolation_model, activity_model
        )
        if activity is None or activity <= 0:
            return None

        # 3. 计算化学势
        mu = mu_0 + self.R * temperature * math.log(activity)
        return mu

    def calculate_molar_enthalpy(self,
                                 composition: Dict[str, float],
                                 temperature: float,
                                 phase_state: str = 'liquid',
                                 extrapolation_model: str = 'UEM1') -> Optional[float]:
        """
        计算合金的摩尔焓 H_alloy = Σ(X_i * H°_i) + H^E
        (已重写) 使用 pycalphad 获取 H°
        """
        H_ideal = 0.0
        phase_map = {'liquid': 'LIQUID', 'solid': 'SER'}
        tdb_phase = phase_map.get(phase_state.lower(), 'LIQUID')

        for component, x_i in composition.items():
            # 1. (已重写) 使用 pycalphad 获取 H°
            H_i = self._get_pure_property(component, tdb_phase, temperature, 101325, 'H')
            if H_i is None:
                print(f"Warning: Could not find H° for {component} in {tdb_phase}")
                return None
            H_ideal += x_i * H_i

        # 2. 过剩焓 H^E
        H_excess = self._calculate_excess_enthalpy(
            composition, temperature, phase_state, extrapolation_model
        )
        if H_excess is None:
            print("Warning: Could not calculate excess enthalpy, using ideal mixing only")
            H_excess = 0.0

        H_total = H_ideal + H_excess
        return H_total

    # ... (calculate_gibbs_energy, calculate_entropy, _calculate_excess_enthalpy,
    #      calculate_all_properties 和 if __name__ == "__main__" 块保持不变) ...
    def calculate_gibbs_energy(self, composition: Dict[str, float], temperature: float, phase_state: str = 'liquid', solvent: str = None, extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> Optional[float]:
        G_total = 0.0
        for component, x_i in composition.items():
            mu_i = self.calculate_chemical_potential(composition, component, temperature, phase_state, solvent, extrapolation_model, activity_model)
            if mu_i is None: return None
            G_total += x_i * mu_i
        return G_total

    def calculate_entropy(self, composition: Dict[str, float], temperature: float, phase_state: str = 'liquid', solvent: str = None, extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> Optional[float]:
        H = self.calculate_molar_enthalpy(composition, temperature, phase_state, extrapolation_model)
        G = self.calculate_gibbs_energy(composition, temperature, phase_state, solvent, extrapolation_model, activity_model)
        if H is None or G is None: return None
        if temperature == 0: return None
        S = (H - G) / temperature
        return S

    def _calculate_excess_enthalpy(self, composition: Dict[str, float], temperature: float, phase_state: str = 'liquid', extrapolation_model: str = 'UEM1') -> Optional[float]:
        try:
            comp_std = {self._to_standard_symbol(k): v for k, v in composition.items()}; components = list(comp_std.keys())
            n = len(components)
            if n == 1: return 0.0
            if n == 2:
                elem_a = components[0]; elem_b = components[1]; x_a = comp_std[elem_a]; x_b = comp_std[elem_b]
                self.binary_model.set_state(phase_state); self.binary_model.set_temperature(temperature)
                H_mix = self.binary_model.binary_model(elem_a, elem_b, x_a, x_b)
                return H_mix
            H_excess = 0.0
            for i in range(n):
                for j in range(i+1, n):
                    elem_i = components[i]; elem_j = components[j]; x_i = comp_std[elem_i]; x_j = comp_std[elem_j]
                    if x_i > 0 and x_j > 0:
                        self.binary_model.set_state(phase_state); self.binary_model.set_temperature(temperature)
                        x_sum = x_i + x_j
                        if x_sum == 0: continue
                        x_i_norm = x_i / x_sum; x_j_norm = x_j / x_sum
                        H_ij = self.binary_model.binary_model(elem_i, elem_j, x_i_norm, x_j_norm)
                        if H_ij is not None and math.isfinite(H_ij): H_excess += x_i * x_j * H_ij / x_sum
                        else: print(f"Warning: H_ij for {elem_i}-{elem_j} was None or infinite, skipping.")
            return H_excess
        except Exception as e:
            print(f"Error calculating excess enthalpy: {e}"); return None

    def calculate_all_properties(self, composition: Dict[str, float], temperature: float, phase_state: str = 'liquid', solvent: str = None, extrapolation_model: str = 'UEM1', activity_model: str = 'Wagner') -> Dict[str, Dict]:
        results = {'component_properties': {}, 'alloy_properties': {}}
        for component in composition.keys():
            comp_results = {}; ln_gamma = self.calculate_ln_activity_coefficient(composition, component, temperature, phase_state, solvent, extrapolation_model, activity_model)
            comp_results['ln_gamma'] = ln_gamma; comp_results['gamma'] = math.exp(ln_gamma) if ln_gamma is not None else None
            activity = self.calculate_activity(composition, component, temperature, phase_state, solvent, extrapolation_model, activity_model)
            comp_results['activity'] = activity
            mu = self.calculate_chemical_potential(composition, component, temperature, phase_state, solvent, extrapolation_model, activity_model)
            comp_results['mu'] = mu; comp_results['mole_fraction'] = composition[component]; results['component_properties'][component] = comp_results
        H = self.calculate_molar_enthalpy(composition, temperature, phase_state, extrapolation_model); results['alloy_properties']['H'] = H
        G = self.calculate_gibbs_energy(composition, temperature, phase_state, solvent, extrapolation_model, activity_model); results['alloy_properties']['G'] = G
        S = self.calculate_entropy(composition, temperature, phase_state, solvent, extrapolation_model, activity_model); results['alloy_properties']['S'] = S
        results['alloy_properties']['T'] = temperature; results['alloy_properties']['phase'] = phase_state
        return results

if __name__ == "__main__":
    print("=" * 70)
    print("Thermodynamic Properties Calculator Test (V3 - PyCalphad Backend)")
    print("=" * 70)
    thermo = ThermodynamicProperties()
    composition = {'FE': 0.70, 'C': 0.03, 'SI': 0.27}
    temperature = 1873.0; phase_state = 'liquid'
    print(f"\nAlloy Composition: {composition}"); print(f"Temperature: {temperature}K ({temperature-273.15:.1f}°C)"); print(f"Phase State: {phase_state}"); print("\n" + "=" * 70)
    results = thermo.calculate_all_properties(composition=composition, temperature=temperature, phase_state=phase_state, extrapolation_model='UEM1', activity_model='Wagner')
    print("\nComponent Properties:"); print("-" * 70); print(f"{'Component':<10} {'X_i':<10} {'ln(γ_i)':<12} {'γ_i':<12} {'a_i':<12} {'μ_i (kJ/mol)':<15}"); print("-" * 70)
    for comp, props in results['component_properties'].items():
        x_i = props['mole_fraction']; ln_gamma = props['ln_gamma']; gamma = props['gamma']; activity = props['activity']; mu = props['mu']
        ln_gamma_str = f"{ln_gamma:<12.4f}" if ln_gamma is not None else f"{'N/A':<12}"; gamma_str = f"{gamma:<12.4f}" if gamma is not None else f"{'N/A':<12}"; activity_str = f"{activity:<12.4f}" if activity is not None else f"{'N/A':<12}"; mu_str = f"{mu/1000:<15.2f}" if mu is not None else f"{'N/A':<15}"
        print(f"{comp:<10} {x_i:<10.4f} {ln_gamma_str} {gamma_str} {activity_str} {mu_str}")
    print("\n" + "=" * 70); print("Alloy Properties:"); print("-" * 70)
    alloy_props = results['alloy_properties']; H = alloy_props['H']; G = alloy_props['G']; S = alloy_props['S']
    if H is not None and math.isfinite(H): print(f"Molar Enthalpy (H):        {H/1000:.2f} kJ/mol")
    else: print(f"Molar Enthalpy (H):        N/A (Calculation failed)")
    if G is not None and math.isfinite(G): print(f"Gibbs Free Energy (G):     {G/1000:.2f} kJ/mol")
    else: print(f"Gibbs Free Energy (G):     N/A (Calculation failed)")
    if S is not None and math.isfinite(S): print(f"Molar Entropy (S):         {S:.4f} J/(mol*K)")
    else: print(f"Molar Entropy (S):         N/A (Calculation failed)")
    print("=" * 70)