import numpy as np
from typing import Dict, List, Optional, Tuple
import copy
from dataclasses import dataclass, field
from calculations.phase_diagram import PhaseDiagramCalculator


@dataclass
class PhaseInfo:
    """相信息数据类"""
    name: str  # 相名称
    composition: Dict[str, float] = field(default_factory=dict)  # 相组成（摩尔分数）
    absolute_moles: float = 0.0  # 该相的绝对摩尔数（用于计算相分数）
    gibbs_energy: float = 0.0  # 摩尔吉布斯能量 (J/mol)
    fraction: float = 0.0  # 相分数


class PhaseEquilibriumCalculator(PhaseDiagramCalculator):
    """
    基于溶解度约束和稳定性迭代调整的多相平衡计算器。

    算法逻辑：
    1. 确定溶剂（含量最多的元素）
    2. 计算各溶质在溶剂相中的最大溶解度
    3. 构建饱和组成（每个溶质不超过溶解度）
    4. 判断饱和组成是否稳定
    5. 如果不稳定，逐步减少影响最大的溶质，直至稳定
    6. 得到第一相的组成和分数
    7. 计算剩余组成，重复以上步骤
    """
    
    def __init__(self):
        super().__init__()
    
    def calculate_phase_equilibrium(self,
                                     alloy_composition: Dict[str, float],
                                     temperature: float,
                                     extrapolation_model_func=None,
                                     extrapolation_model_name='UEM1',
                                     activity_model='Wagner',
                                     min_phase_fraction: float = 1e-4,
                                     max_iterations: int = 10,
                                     adjustment_factor: float = 0.95) -> List[Dict]:
        """
        计算特定合金组成下的多相平衡。
        
        改进的算法流程：
        1. 计算溶质在溶剂中的溶解度
        2. 构建不超过溶解度的饱和组成
        3. 检查饱和组成的稳定性
        4. 若不稳定，逐步减少最不稳定元素的含量
        5. 得到稳定相后，剩余组分继续迭代

        参数:
            adjustment_factor: 调整系数，每次减少不稳定元素含量时的乘数（默认0.95）
        
        返回:
            List[Dict]: 包含各稳定相信息的列表
        """
        
        print(f"\n{'='*60}")
        print(f"开始多相平衡计算（改进算法）")
        print(f"初始合金组成: {self._format_comp(alloy_composition)}")
        print(f"温度: {temperature} K")
        print(f"{'='*60}\n")
        
        results = []
        current_comp = alloy_composition.copy()
        remaining_moles = 1.0
        
        # 记录每个元素的绝对摩尔量
        current_moles_dict = {k: v * remaining_moles for k, v in current_comp.items()}
        
        for iteration in range(max_iterations):
            print(f"{'─'*60}")
            print(f"迭代 {iteration + 1}:")
            print(f"当前剩余成分: {self._format_comp(current_comp)}")
            print(f"剩余摩尔分数: {remaining_moles:.6f}\n")
            
            # 归一化当前成分
            total_current = sum(current_comp.values())
            if total_current <= 1e-9:
                print("剩余物质几乎为零，计算结束")
                break
            current_comp = {k: v / total_current for k, v in current_comp.items()}
            
            # 确定溶剂（含量最多的元素）
            solvent = max(current_comp.items(), key=lambda x: x[1])[0]
            print(f"  溶剂元素: {solvent} (含量: {current_comp[solvent]:.4f})")
            
            # 寻找能量最低的相作为基体相
            matrix_phase = self._find_lowest_energy_phase(current_comp, temperature)
            print(f"  基体相: {matrix_phase}\n")
            
            # 计算各溶质在该相中的溶解度限
            solubility_limits = self._calculate_solubility_limits(
                solvent=solvent,
                current_comp=current_comp,
                matrix_phase=matrix_phase,
                temperature=temperature,
                extrapolation_func=extrapolation_model_func,
                model_params=(extrapolation_model_name, activity_model)
            )
            
            # 构建初始饱和组成（不超过溶解度）
            saturated_comp = self._build_saturated_composition(
                current_comp=current_comp,
                solvent=solvent,
                solubility_limits=solubility_limits
            )
            
            print(f"  初始饱和组成: {self._format_comp(saturated_comp)}")
            
            # 迭代调整组成直至稳定
            stable_comp = self._adjust_to_stability(
                initial_comp=saturated_comp,
                solvent=solvent,
                matrix_phase=matrix_phase,
                temperature=temperature,
                extrapolation_func=extrapolation_model_func,
                model_params=(extrapolation_model_name, activity_model),
                adjustment_factor=adjustment_factor
            )
            
            print(f"  稳定相组成: {self._format_comp(stable_comp)}\n")
            
            # 根据物质守恒计算该相的摩尔数
            phase_moles, limiting_element = self._calculate_phase_moles(
                current_moles_dict,
                stable_comp
            )
            
            print(f"  相摩尔分数: {phase_moles:.6f} (受限于: {limiting_element})")
            
            # 检查相分数是否过小
            if phase_moles < min_phase_fraction:
                print(f"  ⚠ 相分数 {phase_moles:.4e} 小于阈值 {min_phase_fraction}")
                print(f"  → 将剩余物质归入最后一相\n")
                results.append({
                    'phase_name': "Residual_Phase",
                    'composition': current_comp,
                    'mole_fraction': remaining_moles,
                    'type': 'Residue',
                    'note': 'Below minimum phase fraction threshold'
                })
                break
            
            # 记录该相
            results.append({
                'phase_name': matrix_phase,
                'composition': stable_comp,
                'mole_fraction': phase_moles,
                'type': 'Matrix' if iteration == 0 else 'Precipitate'
            })
            
            # 计算剩余组成
            new_moles_dict = {}
            for el in current_moles_dict:
                n_consumed = phase_moles * stable_comp.get(el, 0.0)
                n_remaining = current_moles_dict[el] - n_consumed
                n_remaining = max(0.0, n_remaining)
                new_moles_dict[el] = n_remaining
            
            # 更新剩余物质
            current_moles_dict = new_moles_dict
            remaining_moles = sum(current_moles_dict.values())
            
            print(f"  剩余摩尔分数: {remaining_moles:.6f}\n")
            
            # 检查是否还有剩余物质
            if remaining_moles < 1e-6:
                print("所有物质已完全分配，计算结束")
                break
            
            # 重新归一化得到新的组成
            current_comp = {k: v / remaining_moles for k, v in current_moles_dict.items()}
            current_moles_dict = new_moles_dict
        
        # 输出最终结果摘要
        print(f"{'='*60}")
        print(f"相平衡计算完成")
        print(f"共形成 {len(results)} 个相:\n")
        total_fraction = 0.0
        for i, phase in enumerate(results, 1):
            frac = phase['mole_fraction']
            total_fraction += frac
            print(f"{i}. {phase['phase_name']}: {frac:.6f} ({frac*100:.2f}%)")
            print(f"   组成: {self._format_comp(phase['composition'])}")
        print(f"\n总摩尔分数: {total_fraction:.6f}")
        print(f"{'='*60}\n")

        # 转换为PhaseInfo对象列表
        phase_info_list = []
        for phase in results:
            phase_info = PhaseInfo(
                name=phase['phase_name'],
                composition=phase['composition'],
                absolute_moles=phase['mole_fraction'],  # 使用mole_fraction作为absolute_moles
                gibbs_energy=0.0,  # 当前算法未计算吉布斯能量
                fraction=phase['mole_fraction']
            )
            phase_info_list.append(phase_info)

        # 计算总吉布斯能量（简化为0）
        total_gibbs = 0.0

        # 包装成字典格式返回，兼容GUI
        return {
            'status': 'success',
            'temperature': temperature,
            'total_composition': alloy_composition,
            'phases': phase_info_list,
            'total_gibbs_energy': total_gibbs,
            'message': f'成功计算出 {len(results)} 个平衡相',
            'calculation_log': []  # 当前算法使用print输出，未收集日志
        }
    
    def _calculate_solubility_limits(self, solvent, current_comp, matrix_phase, 
                                     temperature, extrapolation_func, model_params):
        """
        计算各溶质在溶剂相中的溶解度限。
        
        参数:
            solvent: 溶剂元素
            current_comp: 当前合金组成
            matrix_phase: 基体相名称
            temperature: 温度
            extrapolation_func: 外推函数
            model_params: (模型名称, 活度模型)
            
        返回:
            solubility_limits: {溶质: 溶解度} 字典
        """
        extrap_name, act_model = model_params
        solubility_limits = {}
        
        solutes = [k for k in current_comp.keys() if k != solvent]
        
        print(f"  计算溶解度限:")
        
        for solute in solutes:
            proxy_base = {solvent: 1.0}
            
            try:
                res = self.calculate_solubility(
                    base_alloy_composition=proxy_base,
                    solute_element=solute,
                    solution_phase='SOLID' if 'LIQUID' not in matrix_phase else 'LIQUID',
                    temperature=temperature,
                    extrapolation_func=extrapolation_func,
                    extrapolation_model_name=extrap_name,
                    activity_model=act_model
                )
                
                limit = res.get('solubility_mole_fraction', 1.0)
                if limit is None or limit > 1.0:
                    limit = 1.0
                    
                solubility_limits[solute] = limit
                print(f"    {solute}: {limit:.6f}")
                
            except Exception as e:
                print(f"    {solute}: 计算失败，假设完全互溶")
                solubility_limits[solute] = 1.0
        
        print()
        return solubility_limits
    
    def _build_saturated_composition(self, current_comp, solvent, solubility_limits):
        """
        构建饱和组成：每个溶质不超过其溶解度限。
        
        参数:
            current_comp: 当前组成
            solvent: 溶剂元素
            solubility_limits: 溶解度限字典
            
        返回:
            saturated_comp: 饱和组成
        """
        saturated_comp = {}
        sum_solutes = 0.0
        
        solutes = [k for k in current_comp.keys() if k != solvent]
        
        for solute in solutes:
            current_x = current_comp[solute]
            limit_x = solubility_limits.get(solute, 1.0)
            
            # 取较小值：不超过溶解度
            sat_x = min(current_x, limit_x)
            saturated_comp[solute] = sat_x
            sum_solutes += sat_x
        
        # 溶剂占剩余部分
        saturated_comp[solvent] = max(0.0, 1.0 - sum_solutes)
        
        return saturated_comp
    
    def _adjust_to_stability(self, initial_comp, solvent, matrix_phase, temperature,
                            extrapolation_func, model_params, adjustment_factor=0.95):
        """
        迭代调整组成直至稳定。
        
        如果组成不稳定，找到影响最大的溶质（化学势偏离最大的），
        减少其含量，直至组成稳定。
        
        参数:
            initial_comp: 初始组成
            solvent: 溶剂元素
            matrix_phase: 基体相
            temperature: 温度
            extrapolation_func: 外推函数
            model_params: (模型名称, 活度模型)
            adjustment_factor: 调整因子（每次乘以此值减少含量）
            
        返回:
            stable_comp: 稳定的组成
        """
        extrap_name, act_model = model_params
        max_adjust_iterations = 30
        
        current_comp = initial_comp.copy()
        
        print(f"  调整组成至稳定:")
        
        for i in range(max_adjust_iterations):
            # 归一化
            total = sum(current_comp.values())
            current_comp = {k: v / total for k, v in current_comp.items()}
            
            # 检查稳定性
            is_stable, issues = self._check_alloy_full_stability(
                composition=current_comp,
                temperature=temperature,
                tdb_phase=matrix_phase,
                extrapolation_func=extrapolation_func,
                extrapolation_model_name=extrap_name,
                activity_model=act_model
            )
            
            if is_stable:
                print(f"    → 第 {i+1} 次调整后稳定\n")
                return current_comp
            
            # 找到最不稳定的元素
            most_unstable, max_deviation = self._find_most_unstable_element(issues)
            
            if most_unstable is None or most_unstable == solvent:
                print(f"    → 无法进一步调整，返回当前组成\n")
                return current_comp
            
            # 减少该元素的含量
            old_x = current_comp[most_unstable]
            current_comp[most_unstable] *= adjustment_factor
            new_x = current_comp[most_unstable]
            
            print(f"    第 {i+1} 次: 减少 {most_unstable} ({old_x:.6f} → {new_x:.6f}), Δμ={max_deviation:.1f}")
        
        print(f"    ⚠ 达到最大调整次数，返回当前组成\n")
        return current_comp
    
    def _find_most_unstable_element(self, stability_issues):
        """
        从稳定性问题列表中找到最不稳定的元素。
        
        参数:
            stability_issues: 稳定性问题列表，格式如：
                ['组分不稳定: AL 在 FCC_A1 中的化学势过高 (Δμ=4789.4)，倾向以纯态析出']
        
        返回:
            (element, deviation): 最不稳定的元素和化学势偏离值
        """
        max_deviation = 0.0
        most_unstable = None
        
        for issue in stability_issues:
            # 解析问题描述，提取元素和化学势偏离
            # 格式: "组分不稳定: AL 在 FCC_A1 中的化学势过高 (Δμ=4789.4)，倾向以纯态析出"
            try:
                if '组分不稳定:' in issue and 'Δμ=' in issue:
                    # 提取元素名
                    parts = issue.split()
                    element = parts[1]  # "AL"
                    
                    # 提取Δμ值
                    mu_part = issue.split('Δμ=')[1].split(')')[0]
                    deviation = abs(float(mu_part))
                    
                    if deviation > max_deviation:
                        max_deviation = deviation
                        most_unstable = element
            except:
                continue
        
        return most_unstable, max_deviation
    
    def _calculate_phase_moles(self, current_moles_dict, saturated_comp):
        """
        根据物质守恒计算该相能形成的最大摩尔数。
        
        参数:
            current_moles_dict: 当前剩余的各元素摩尔量
            saturated_comp: 相的组成
            
        返回:
            (phase_moles, limiting_element)
        """
        max_moles = float('inf')
        limiting_element = None
        
        for element, x_element in saturated_comp.items():
            if x_element < 1e-12:
                continue
                
            n_available = current_moles_dict.get(element, 0.0)
            possible_moles = n_available / x_element
            
            if possible_moles < max_moles:
                max_moles = possible_moles
                limiting_element = element
        
        return max_moles, limiting_element
    
    def _find_lowest_energy_phase(self, composition, temperature):
        """
        找到吉布斯自由能最低的相作为基体。
        
        参数:
            composition: 合金组成
            temperature: 温度
            
        返回:
            phase_name: 能量最低的相名称
        """
        solvent = max(composition.items(), key=lambda x: x[1])[0]
        phases = [p for p in self.tdb_parser.get_element_phases(solvent) 
                 if p != 'GAS']
        
        best_phase = 'FCC_A1'  # 默认相
        min_g = float('inf')
        
        for phase in phases:
            try:
                g_pure = self.tdb_parser.get_gibbs_energy(solvent, phase, temperature)
                
                if g_pure is not None and g_pure < min_g:
                    min_g = g_pure
                    best_phase = phase
                    
            except Exception as e:
                continue
        
        return best_phase
    
    def _format_comp(self, comp):
        """格式化输出组成"""
        return ", ".join([f"{k}:{v:.4f}" for k, v in comp.items() if v > 1e-4])

    def calculate_phase_equilibrium_vs_temperature(self,
                                                   total_composition: Dict[str, float],
                                                   T_min: float,
                                                   T_max: float,
                                                   n_points: int = 50,
                                                   extrapolation_model_func = None,
                                                   extrapolation_model_name: str = 'UEM1',
                                                   activity_model: str = 'Wagner',
                                                   progress_callback = None) -> Dict:
        """
        计算相平衡随温度的变化

        参数:
            total_composition: 总组成
            T_min: 最低温度 (K)
            T_max: 最高温度 (K)
            n_points: 温度点数
            extrapolation_model_func: 外推模型函数
            extrapolation_model_name: 外推模型名称
            activity_model: 活度模型
            progress_callback: 进度回调函数 callback(current, total)

        返回:
            {
                'status': 'success',
                'temperatures': [温度列表],
                'phase_fractions': {相名: [分数列表]},
                'results': [每个温度的完整结果]
            }
        """
        import numpy as np

        temperatures = np.linspace(T_min, T_max, n_points)
        results = []
        phase_fractions = {}

        for i, T in enumerate(temperatures):
            if progress_callback:
                progress_callback(i + 1, n_points)

            try:
                result = self.calculate_phase_equilibrium(
                    total_composition, T,
                    extrapolation_model_func, extrapolation_model_name, activity_model
                )

                results.append(result)

                # 记录相分数
                if result['status'] == 'success' and result['phases']:
                    for phase_info in result['phases']:
                        if phase_info.name not in phase_fractions:
                            phase_fractions[phase_info.name] = []
                        phase_fractions[phase_info.name].append(phase_info.fraction)

            except Exception as e:
                print(f"温度 {T:.1f} K 计算失败: {str(e)}")
                results.append({
                    'status': 'error',
                    'message': str(e),
                    'phases': []
                })

        return {
            'status': 'success',
            'temperatures': temperatures.tolist(),
            'phase_fractions': phase_fractions,
            'results': results
        }

    def calculate_phase_equilibrium_vs_composition(self,
                                                   base_composition: Dict[str, float],
                                                   variable_element: str,
                                                   x_min: float,
                                                   x_max: float,
                                                   temperature: float,
                                                   n_points: int = 50,
                                                   extrapolation_model_func = None,
                                                   extrapolation_model_name: str = 'UEM1',
                                                   activity_model: str = 'Wagner',
                                                   progress_callback = None) -> Dict:
        """
        计算相平衡随组分的变化

        参数:
            base_composition: 基础组成（不包括变化元素）
            variable_element: 变化的元素
            x_min: 最小摩尔分数
            x_max: 最大摩尔分数
            temperature: 温度 (K)
            n_points: 组分点数
            extrapolation_model_func: 外推模型函数
            extrapolation_model_name: 外推模型名称
            activity_model: 活度模型
            progress_callback: 进度回调函数 callback(current, total)

        返回:
            {
                'status': 'success',
                'compositions': [组分列表],
                'variable_element': 变化元素,
                'temperature': 温度,
                'phase_fractions': {相名: [分数列表]},
                'results': [每个组分的完整结果]
            }
        """
        import numpy as np

        variable_element = variable_element.upper()
        compositions = np.linspace(x_min, x_max, n_points)
        results = []
        phase_fractions = {}

        # 归一化基础组成
        base_total = sum(base_composition.values())
        base_norm = {k.upper(): v/base_total for k, v in base_composition.items()
                     if k.upper() != variable_element}

        for i, x_var in enumerate(compositions):
            if progress_callback:
                progress_callback(i + 1, n_points)

            try:
                # 构建当前组成
                remaining = 1.0 - x_var
                current_comp = {variable_element: x_var}

                for elem, frac in base_norm.items():
                    current_comp[elem] = frac * remaining

                # 归一化
                total = sum(current_comp.values())
                current_comp = {k: v/total for k, v in current_comp.items()}

                result = self.calculate_phase_equilibrium(
                    current_comp, temperature,
                    extrapolation_model_func, extrapolation_model_name, activity_model
                )

                results.append(result)

                # 记录相分数
                if result['status'] == 'success' and result['phases']:
                    for phase_info in result['phases']:
                        if phase_info.name not in phase_fractions:
                            phase_fractions[phase_info.name] = []
                        phase_fractions[phase_info.name].append(phase_info.fraction)

            except Exception as e:
                print(f"组分 {x_var:.3f} 计算失败: {str(e)}")
                results.append({
                    'status': 'error',
                    'message': str(e),
                    'phases': []
                })

        return {
            'status': 'success',
            'compositions': compositions.tolist(),
            'variable_element': variable_element,
            'temperature': temperature,
            'phase_fractions': phase_fractions,
            'results': results
        }



# =============================================================================
# 使用示例
# =============================================================================
if __name__ == '__main__':
    # 1. 初始化计算器
    calculator = PhaseEquilibriumCalculator()
    from models.extrapolation_models import BinaryModel
    
    extrapolation_model_func = BinaryModel().UEM1
    
    # 2. 定义合金和温度
    my_alloy = {'AL': 0.70, 'FE': 0.14, 'MG': 0.16}
    T_calc = 400  # K

    # 3. 运行计算
    results = calculator.calculate_phase_equilibrium(
        my_alloy, 
        T_calc,
        extrapolation_model_func=extrapolation_model_func,
        adjustment_factor=0.95  # 每次调整时减少5%
    )

    # 4. 打印结果
    print("\n最终结果:")
    for i, phase in enumerate(results, 1):
        print(f"\n相 {i}: {phase['phase_name']}")
        print(f"  摩尔分数: {phase['mole_fraction']:.6f} ({phase['mole_fraction']*100:.2f}%)")
        print(f"  组成: {phase['composition']}")