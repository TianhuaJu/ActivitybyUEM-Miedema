"""
并行溶解度计算模块
==================
支持多进程并行计算的独立函数

为了支持 ProcessPoolExecutor,所有函数都必须是模块级别的
（不能是类方法或嵌套函数）
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations.phase_diagram import PhaseDiagramCalculator
from models.extrapolation_models import BinaryModel


# 全局缓存计算器实例（每个进程一个）
_calculator_instance = None


def get_calculator():
    """获取计算器实例（进程级单例）"""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = PhaseDiagramCalculator()
    return _calculator_instance


def compute_concentration_point(params):
    """
    计算单个浓度点的溶解度（独立函数，支持多进程）

    Args:
        params: 包含所有计算参数的字典
            - x_var: 浓度值
            - index: 索引
            - fixed_base_norm: 固定基础成分
            - variable_comp: 变化组分
            - solute: 溶质元素
            - tdb_solution_phase: TDB溶液相
            - temperature: 温度
            - extrap_model_name: 外推模型名称
            - activity_model: 活度模型

    Returns:
        (index, sol_value, ideal_sol_value, result, ideal_result)
    """
    try:
        # 获取计算器
        phase_calc = get_calculator()

        # 获取外推函数
        bm = BinaryModel()
        extrap_func_map = {
            'UEM1': bm.UEM1, 'UEM2': bm.UEM2, 'UEM2-Adv': bm.UEM2_Adv,
            'GSM': bm.GSM, 'Muggianu': bm.Muggianu,
            'Toop-Kohler': bm.Toop_Kohler, 'Toop-Muggianu': bm.Toop_Muggianu
        }
        extrap_func = extrap_func_map.get(params['extrap_model_name'], bm.UEM1)

        # 构建基础合金成分
        x_var = params['x_var']
        x_fixed_fraction = 1.0 - x_var
        base_composition = {}

        for elem, frac in params['fixed_base_norm'].items():
            base_composition[elem] = frac * x_fixed_fraction

        variable_comp = params['variable_comp']
        base_composition[variable_comp] = base_composition.get(variable_comp, 0.0) + x_var

        # 实际溶解度计算
        result = phase_calc.calculate_solubility(
            base_alloy_composition=base_composition,
            solute_element=params['solute'],
            solution_phase=params['tdb_solution_phase'],
            temperature=params['temperature'],
            extrapolation_func=extrap_func,
            extrapolation_model_name=params['extrap_model_name'],
            activity_model=params['activity_model']
        )

        # 理想溶解度计算
        ideal_result = phase_calc.calculate_ideal_solubility(
            base_alloy_composition=base_composition,
            solute_element=params['solute'],
            solution_phase=params['tdb_solution_phase'],
            precipitating_phase="",
            temperature=params['temperature']
        )

        # 处理实际溶解度
        if result['status'] == 'success':
            sol_value = result['solubility_mole_fraction']
        elif result['status'] == 'fully_soluble':
            sol_value = 1.0
        elif result['status'] == 'insoluble':
            sol_value = 0.0
        else:
            sol_value = 0.0

        # 处理理想溶解度
        if ideal_result['status'] == 'success':
            ideal_sol_value = ideal_result['solubility_mole_fraction']
        elif ideal_result['status'] == 'fully_soluble':
            ideal_sol_value = 1.0
        elif ideal_result['status'] == 'insoluble':
            ideal_sol_value = 0.0
        else:
            ideal_sol_value = 0.0

        return (params['index'], sol_value, ideal_sol_value, result, ideal_result)

    except Exception as e:
        print(f"Error at X_{params['variable_comp']}={params['x_var']}: {e}")
        import traceback
        traceback.print_exc()
        error_result = {'status': 'error', 'message': str(e)}
        return (params['index'], 0.0, 0.0, error_result, error_result)


def compute_temperature_point(params):
    """
    计算单个温度点的溶解度（独立函数，支持多进程）

    Args:
        params: 包含所有计算参数的字典
            - t_curr: 温度值
            - index: 索引
            - base_composition: 基础合金成分
            - solute: 溶质元素
            - tdb_solution_phase: TDB溶液相
            - extrap_model_name: 外推模型名称
            - activity_model: 活度模型

    Returns:
        (index, sol_value, ideal_sol_value, result, ideal_result)
    """
    try:
        # 获取计算器
        phase_calc = get_calculator()

        # 获取外推函数
        bm = BinaryModel()
        extrap_func_map = {
            'UEM1': bm.UEM1, 'UEM2': bm.UEM2, 'UEM2-Adv': bm.UEM2_Adv,
            'GSM': bm.GSM, 'Muggianu': bm.Muggianu,
            'Toop-Kohler': bm.Toop_Kohler, 'Toop-Muggianu': bm.Toop_Muggianu
        }
        extrap_func = extrap_func_map.get(params['extrap_model_name'], bm.UEM1)

        # 实际溶解度计算
        result = phase_calc.calculate_solubility(
            base_alloy_composition=params['base_composition'],
            solute_element=params['solute'],
            solution_phase=params['tdb_solution_phase'],
            temperature=params['t_curr'],
            extrapolation_func=extrap_func,
            extrapolation_model_name=params['extrap_model_name'],
            activity_model=params['activity_model']
        )

        # 理想溶解度计算
        ideal_result = phase_calc.calculate_ideal_solubility(
            base_alloy_composition=params['base_composition'],
            solute_element=params['solute'],
            solution_phase=params['tdb_solution_phase'],
            precipitating_phase="",
            temperature=params['t_curr']
        )

        # 处理实际溶解度
        if result['status'] == 'success':
            sol_value = result['solubility_mole_fraction']
        elif result['status'] == 'fully_soluble':
            sol_value = 1.0
        elif result['status'] == 'insoluble':
            sol_value = 0.0
        else:
            sol_value = 0.0

        # 处理理想溶解度
        if ideal_result['status'] == 'success':
            ideal_sol_value = ideal_result['solubility_mole_fraction']
        elif ideal_result['status'] == 'fully_soluble':
            ideal_sol_value = 1.0
        elif ideal_result['status'] == 'insoluble':
            ideal_sol_value = 0.0
        else:
            ideal_sol_value = 0.0

        return (params['index'], sol_value, ideal_sol_value, result, ideal_result)

    except Exception as e:
        print(f"Error at T={params['t_curr']}: {e}")
        import traceback
        traceback.print_exc()
        error_result = {'status': 'error', 'message': str(e)}
        return (params['index'], 0.0, 0.0, error_result, error_result)
