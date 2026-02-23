"""
修正版溶解度计算模块
====================
修正了原始 calculate_solubility 方法的核心问题：
原方法假设溶质析出为纯元素，但实际上应该与溶剂形成金属间化合物。

例如：Mn在Ti中的溶解度极限是由 α-Ti/TiMn₂ 平衡决定的，
而不是由 α-Ti/纯Mn 平衡决定的。

作者: Claude
日期: 2025
"""

import math
from typing import Dict, Optional, Tuple
from scipy.optimize import brentq

# 假设这些模块可以导入
# from models.miedema_model import MiedemaModel
# from core.tdb_parser import TDBParser


class SolubilityCalculatorCorrected:
    """
    修正版溶解度计算器
    考虑金属间化合物作为平衡第二相
    """
    
    # ============================================================
    # 常见二元系统的金属间化合物数据
    # 格式: (溶剂, 溶质): [(化合物名, x_溶质, ΔHf (J/mol))]
    # ============================================================
    INTERMETALLIC_DATA = {
        # Ti-Mn 系统 (TiMn₂ Laves相是最常见的平衡相)
        ('TI', 'MN'): [
            ('TiMn2', 0.667, -12000),   # TiMn₂, x_Mn = 2/3, ΔHf ≈ -12 kJ/mol
            ('TiMn', 0.500, -8000),     # TiMn, x_Mn = 1/2
        ],
        ('MN', 'TI'): [
            ('TiMn2', 0.333, -12000),   # 从Mn角度看
        ],
        
        # Ti-Fe 系统
        ('TI', 'FE'): [
            ('TiFe', 0.500, -20000),    # TiFe, ΔHf ≈ -20 kJ/mol
            ('TiFe2', 0.667, -18000),   # TiFe₂
        ],
        
        # Ti-Ni 系统
        ('TI', 'NI'): [
            ('TiNi', 0.500, -34000),    # TiNi, ΔHf ≈ -34 kJ/mol
            ('TiNi3', 0.750, -42000),   # TiNi₃
            ('Ti2Ni', 0.333, -26000),   # Ti₂Ni
        ],
        
        # Ti-Cu 系统
        ('TI', 'CU'): [
            ('TiCu', 0.500, -10000),
            ('Ti2Cu', 0.333, -12000),
        ],
        
        # Ti-Cr 系统
        ('TI', 'CR'): [
            ('TiCr2', 0.667, -8000),    # Laves相
        ],
        
        # Fe-C 系统 (渗碳体)
        ('FE', 'C'): [
            ('Fe3C', 0.25, 5000),       # 渗碳体 (亚稳相，正的形成焓)
        ],
        
        # Ni-Al 系统
        ('NI', 'AL'): [
            ('Ni3Al', 0.25, -42000),    # γ' 相
            ('NiAl', 0.50, -60000),     # β 相
        ],
        
        # Al-Cu 系统  
        ('AL', 'CU'): [
            ('Al2Cu', 0.333, -13000),   # θ 相
            ('AlCu', 0.500, -20000),
        ],
        
        # Al-Fe 系统
        ('AL', 'FE'): [
            ('Al3Fe', 0.25, -28000),
            ('Al5Fe2', 0.286, -30000),
        ],
    }
    
    def __init__(self, tdb_parser, activity_calculator, miedema_model=None):
        """
        初始化修正版溶解度计算器
        
        参数:
            tdb_parser: TDB解析器实例
            activity_calculator: 活度计算器实例
            miedema_model: Miedema模型实例（可选，用于估算未知化合物）
        """
        self.tdb_parser = tdb_parser
        self.activity_calculator = activity_calculator
        self.miedema_model = miedema_model
        self.R = 8.314  # J/(mol·K)
    
    def get_intermetallic_gibbs(self, 
                                 solvent: str, 
                                 solute: str, 
                                 temperature: float) -> Tuple[Optional[float], Optional[str], Optional[float]]:
        """
        获取最稳定金属间化合物的Gibbs能和溶质的化学势
        
        返回:
            (G_compound, compound_name, x_solute_in_compound)
            如果没有找到化合物数据，返回 (None, None, None)
        """
        key = (solvent.upper(), solute.upper())
        
        if key not in self.INTERMETALLIC_DATA:
            # 尝试使用Miedema模型估算
            return self._estimate_intermetallic_miedema(solvent, solute, temperature)
        
        compounds = self.INTERMETALLIC_DATA[key]
        
        # 获取纯组元的Gibbs能
        G_solvent_pure = self.tdb_parser.get_gibbs_energy(solvent, 'SER', temperature)
        G_solute_pure = self.tdb_parser.get_gibbs_energy(solute, 'SER', temperature)
        
        if G_solvent_pure is None or G_solute_pure is None:
            return None, None, None
        
        # 找出最稳定的化合物（Gibbs能最低）
        best_compound = None
        min_G = float('inf')
        best_x_solute = None
        
        for comp_name, x_solute, delta_Hf in compounds:
            x_solvent = 1.0 - x_solute
            
            # 假设形成熵可忽略或很小（对金属间化合物通常成立）
            # G_compound ≈ x_A*G°_A + x_B*G°_B + ΔHf
            G_compound = x_solvent * G_solvent_pure + x_solute * G_solute_pure + delta_Hf
            
            if G_compound < min_G:
                min_G = G_compound
                best_compound = comp_name
                best_x_solute = x_solute
        
        return min_G, best_compound, best_x_solute
    
    def _estimate_intermetallic_miedema(self, 
                                         solvent: str, 
                                         solute: str, 
                                         temperature: float) -> Tuple[Optional[float], Optional[str], Optional[float]]:
        """
        使用Miedema模型估算金属间化合物的Gibbs能
        """
        if self.miedema_model is None:
            return None, None, None
        
        try:
            # 尝试常见的化学计量比
            ratios = [(0.5, "1:1"), (0.333, "2:1"), (0.667, "1:2"), (0.25, "3:1"), (0.75, "1:3")]
            
            G_solvent = self.tdb_parser.get_gibbs_energy(solvent, 'SER', temperature)
            G_solute = self.tdb_parser.get_gibbs_energy(solute, 'SER', temperature)
            
            if G_solvent is None or G_solute is None:
                return None, None, None
            
            best_G = float('inf')
            best_name = None
            best_x = None
            
            for x_solute, ratio_name in ratios:
                x_solvent = 1.0 - x_solute
                
                # 使用Miedema模型计算金属间化合物的形成焓
                # 注意：需要设置 order_degree='IM' 来获取有序化合物的焓
                delta_H = self.miedema_model.getmixingEnthalpy_by_Miedema_Model(
                    solvent, x_solvent, temperature, order_degree='IM'
                )
                
                G_compound = x_solvent * G_solvent + x_solute * G_solute + delta_H
                
                if G_compound < best_G:
                    best_G = G_compound
                    best_name = f"{solvent}{ratio_name.split(':')[0]}{solute}{ratio_name.split(':')[1]}_Miedema"
                    best_x = x_solute
            
            return best_G, best_name, best_x
            
        except Exception as e:
            print(f"Miedema估算失败: {e}")
            return None, None, None
    
    def calculate_mu_solute_in_compound(self,
                                        G_compound: float,
                                        x_solute_in_compound: float,
                                        solvent: str,
                                        mu_solvent_in_matrix: float) -> float:
        """
        计算溶质在金属间化合物中的化学势
        
        对于化合物 A_{1-x}B_x，在与基体相平衡时：
        G_compound = (1-x)*μ_A + x*μ_B
        
        如果假设基体中溶剂的化学势 μ_A 已知（接近纯溶剂），则：
        μ_B = (G_compound - (1-x)*μ_A) / x
        
        参数:
            G_compound: 化合物的Gibbs能 (J/mol)
            x_solute_in_compound: 化合物中溶质的摩尔分数
            solvent: 溶剂元素
            mu_solvent_in_matrix: 溶剂在基体中的化学势
            
        返回:
            溶质在化合物中的化学势 (J/mol)
        """
        x_solvent = 1.0 - x_solute_in_compound
        
        # μ_solute = (G_compound - x_solvent * μ_solvent) / x_solute
        mu_solute = (G_compound - x_solvent * mu_solvent_in_matrix) / x_solute_in_compound
        
        return mu_solute
    
    def calculate_solubility_with_compound(self,
                                           base_alloy_composition: Dict[str, float],
                                           solute_element: str,
                                           solution_phase: str,
                                           temperature: float,
                                           extrapolation_func,
                                           extrapolation_model_name: str = 'UEM1',
                                           activity_model: str = 'Wagner',
                                           min_solubility: float = 1e-12,
                                           max_solubility: float = 0.5) -> dict:
        """
        修正版溶解度计算：考虑金属间化合物作为平衡第二相
        
        核心修正：
        原方法: μ_solute(in matrix) = G°_solute(pure)
        修正后: μ_solute(in matrix) = μ_solute(in intermetallic)
        
        参数:
            base_alloy_composition: 基础合金成分
            solute_element: 溶质元素
            solution_phase: 溶液相类型 ('LIQUID' 或 'SOLID')
            temperature: 温度 (K)
            extrapolation_func: 外推模型函数
            extrapolation_model_name: 外推模型名称
            activity_model: 活度模型
            min_solubility: 最小溶解度
            max_solubility: 最大溶解度（对于形成化合物的系统，通常不超过0.5）
            
        返回:
            包含溶解度和相关信息的字典
        """
        # ==================== 1. 预处理 ====================
        solute = solute_element.upper()
        
        total_base = sum(base_alloy_composition.values())
        if total_base <= 0:
            raise ValueError("基础合金成分不能为空")
        
        base_comp = {k.upper(): v / total_base for k, v in base_alloy_composition.items()}
        solvent = max(base_comp.items(), key=lambda x: x[1])[0]
        
        # 确定溶液相
        if solution_phase.upper() == 'LIQUID':
            tdb_solution_phase = 'LIQUID'
            phase_state = 'liquid'
        else:
            ref = self.tdb_parser.get_stable_phase(solvent, temperature)
            tdb_solution_phase = ref if ref else 'BCC_A2'
            phase_state = 'solid'
        
        # ==================== 2. 获取金属间化合物信息 ====================
        G_compound, compound_name, x_solute_compound = self.get_intermetallic_gibbs(
            solvent, solute, temperature
        )
        
        # 获取纯溶质的Gibbs能（作为备选）
        pure_solute_phase = self.tdb_parser.get_stable_phase(solute, temperature)
        G_pure_solute = self.tdb_parser.get_gibbs_energy(solute, pure_solute_phase, temperature)
        
        if G_compound is None:
            # 没有化合物数据，回退到原始方法（与纯溶质平衡）
            print(f"警告: 未找到 {solvent}-{solute} 系统的金属间化合物数据，使用纯{solute}作为平衡相")
            equilibrium_phase = f"Pure {solute} ({pure_solute_phase})"
            use_compound = False
        else:
            equilibrium_phase = compound_name
            use_compound = True
            print(f"使用金属间化合物 {compound_name} (x_{solute}={x_solute_compound:.3f}) 作为平衡相")
        
        # ==================== 3. 定义残差函数 ====================
        def residual(x_solute: float) -> float:
            x_solute = max(min(x_solute, max_solubility), min_solubility)
            remaining = 1.0 - x_solute
            
            # 构建当前合金成分
            current_comp = {el: base_comp[el] * remaining for el in base_comp}
            current_comp[solute] = x_solute
            
            # 计算溶质在基体中的化学势
            mu_solute_matrix = self._get_chemical_potential_internal(
                composition=current_comp,
                component=solute,
                temperature=temperature,
                tdb_phase=tdb_solution_phase,
                phase_state=phase_state,
                extrapolation_func=extrapolation_func,
                extrapolation_model_name=extrapolation_model_name,
                activity_model=activity_model
            )
            
            if mu_solute_matrix is None:
                return 1e20
            
            if use_compound:
                # 计算溶剂在基体中的化学势
                mu_solvent_matrix = self._get_chemical_potential_internal(
                    composition=current_comp,
                    component=solvent,
                    temperature=temperature,
                    tdb_phase=tdb_solution_phase,
                    phase_state=phase_state,
                    extrapolation_func=extrapolation_func,
                    extrapolation_model_name=extrapolation_model_name,
                    activity_model=activity_model
                )
                
                if mu_solvent_matrix is None:
                    return 1e20
                
                # 计算溶质在化合物中的化学势
                mu_solute_compound = self.calculate_mu_solute_in_compound(
                    G_compound, x_solute_compound, solvent, mu_solvent_matrix
                )
                
                # 平衡条件：μ_solute(matrix) = μ_solute(compound)
                return mu_solute_matrix - mu_solute_compound
            else:
                # 回退：与纯溶质平衡
                return mu_solute_matrix - G_pure_solute
        
        # ==================== 4. 求解 ====================
        f_low = residual(min_solubility)
        f_high = residual(max_solubility)
        
        if f_low > 0:
            solubility = 0.0
            status = "insoluble"
            message = "即使无限稀释也已过饱和"
        elif f_high < 0:
            solubility = max_solubility
            status = "high_solubility"
            message = f"溶解度超过{max_solubility*100:.1f}%，可能无限互溶或需要检查化合物数据"
        else:
            try:
                solubility = brentq(residual, min_solubility, max_solubility, xtol=1e-8)
                status = "success"
                message = "计算收敛"
            except ValueError as e:
                solubility = 0.0
                status = "numerical_failure"
                message = f"求解失败: {e}"
        
        # ==================== 5. 构建结果 ====================
        remaining = 1.0 - solubility
        final_comp = {el: base_comp[el] * remaining for el in base_comp}
        final_comp[solute] = solubility
        
        return {
            "status": status,
            "message": message,
            "T": temperature,
            "solute": solute,
            "solvent": solvent,
            "equilibrium_phase": equilibrium_phase,  # 新增：与什么相平衡
            "solution_phase": tdb_solution_phase,
            "solubility_mole_fraction": float(solubility),
            "solubility_weight_percent": None,  # 可后续计算
            "final_composition": final_comp,
            "used_intermetallic": use_compound,
            "intermetallic_name": compound_name if use_compound else None,
            "intermetallic_x_solute": x_solute_compound if use_compound else None,
        }
    
    def _get_chemical_potential_internal(self,
                                          composition: Dict[str, float],
                                          component: str,
                                          temperature: float,
                                          tdb_phase: str,
                                          phase_state: str,
                                          extrapolation_func,
                                          extrapolation_model_name: str,
                                          activity_model: str) -> Optional[float]:
        """
        内部方法：计算化学势
        μ_i = G°_i(phase) + RT*ln(a_i)
        """
        # 获取纯组元在该相的Gibbs能
        G_0 = self.tdb_parser.get_gibbs_energy(component, tdb_phase, temperature)
        if G_0 is None:
            # 尝试参考态
            G_0 = self.tdb_parser.get_gibbs_energy(component, 'SER', temperature)
        
        if G_0 is None:
            return None
        
        # 计算活度
        x_i = composition.get(component, 0.0)
        if x_i <= 0:
            return None
        
        # 转换为标准符号
        comp_std = {k.capitalize(): v for k, v in composition.items()}
        component_std = component.capitalize()
        solvent = max(composition.items(), key=lambda x: x[1])[0]
        solvent_std = solvent.capitalize()
        
        # 获取活度系数
        ln_gamma = self.activity_calculator.get_ln_gamma(
            comp_dict=comp_std,
            component_to_calculate=component_std,
            solvent=solvent_std,
            Tem=temperature,
            state=phase_state,
            extra_model=extrapolation_func,
            extrapolation_model_name=extrapolation_model_name,
            activity_model=activity_model
        )
        
        if ln_gamma is None:
            ln_gamma = 0.0  # 假设理想溶液
        
        # μ = G° + RT*ln(γ*x)
        activity = math.exp(ln_gamma) * x_i
        if activity <= 0:
            return None
        
        mu = G_0 + self.R * temperature * math.log(activity)
        return mu


# ============================================================
# 使用示例和测试
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("修正版溶解度计算器测试")
    print("=" * 70)
    
    # 这里需要实际的解析器和计算器实例
    # 以下是伪代码示例
    
    """
    from core.tdb_parser import get_tdb_parser
    from calculations.activity_calculator import ActivityCoefficient
    from models.miedema_model import MiedemaModel
    
    tdb = get_tdb_parser()
    act_calc = ActivityCoefficient()
    miedema = MiedemaModel(('Ti', 'Mn'), 'SOLID')
    
    calc = SolubilityCalculatorCorrected(tdb, act_calc, miedema)
    
    # 计算Mn在α-Ti中的溶解度
    result = calc.calculate_solubility_with_compound(
        base_alloy_composition={'Ti': 1.0},
        solute_element='Mn',
        solution_phase='SOLID',
        temperature=1000,  # K
        extrapolation_func=BinaryModel().UEM1,
        extrapolation_model_name='UEM1',
        activity_model='Wagner'
    )
    
    print(f"Mn在Ti中的溶解度: {result['solubility_mole_fraction']*100:.2f} at%")
    print(f"平衡相: {result['equilibrium_phase']}")
    """
    
    # 简单测试数据结构
    test_data = SolubilityCalculatorCorrected.INTERMETALLIC_DATA
    print("\n已收录的金属间化合物数据:")
    for key, compounds in test_data.items():
        print(f"  {key[0]}-{key[1]} 系统:")
        for name, x, dH in compounds:
            print(f"    {name}: x={x:.3f}, ΔHf={dH/1000:.1f} kJ/mol")
