# utils.py
import re
from core.constants import Constants
def entropy_judge(*elements: str) -> bool:
    """
    判断是否需要考虑过剩熵。

    Args:
        *elements: 一个或多个元素符号。

    Returns:
        bool: 根据规则，如果需要考虑过剩熵，则返回 True，否则返回 False。
    """
    if not elements:
        # Avoid direct GUI calls in utility functions
        print("警告: entropy_judge 函数至少需要一个元素参数。")
        # QMessageBox.warning(None, "输入错误", "entropy_judge 函数至少需要一个元素参数。")
        return False

    s_set = set(elements)
    

    if "O" in s_set:
        other_elements = s_set - {"O"}
        return bool(other_elements.intersection(Constants.non_metal_list))
    elif "H" in s_set or "N" in s_set:
        
        return False
    else:
         
        return True


def parse_composition_static (alloy_str):
    """解析合金组成的静态方法
    返回合金的摩尔组成
    """
    comp_dict = {}
    pattern = r"([A-Z][a-z]?)(\d*\.?\d+|\d+)?"
    matches = re.findall(pattern, alloy_str)
    if not matches:
        print("错误：未匹配到任何元素。")
        return None
    
    first_element_processed = False
    total_moles = 0
    
    try:
        for i, (element, amount_str) in enumerate(matches):
            if i == 0:  # 第一个元素
                # 如果第一个元素后面没有数字，且后面还有其他元素，则其摩尔量默认为1
                # 或者如果显式指定了数字，则使用该数字
                if amount_str:
                    amount = float(amount_str)
                elif len(matches) > 1:  # 如果后面还有其他元素且第一个元素未指定数量
                    amount = 1.0
                else:  # 单个元素，无数量，也默认为1
                    amount = 1.0
            else:  # 非第一个元素
                amount = float(amount_str) if amount_str else 1.0
            
            if amount < 0:
                print(f"错误：元素 {element} 的量不能为负数。")
                return None
            comp_dict[element] = comp_dict.get(element, 0) + amount
            total_moles += amount
    
    except ValueError:
        print("错误：成分数量转换失败。")
        return None
    
    if not comp_dict:
        print("错误：未能解析出任何成分。")
        return None
    
    if abs(total_moles) < 1e-9:
        print("错误：总摩尔量过小。")
        return None
    
    # 将摩尔量转换为摩尔分数 (归一化)
    normalized_comp_dict = {}
    for element, moles in comp_dict.items():
        normalized_comp_dict[element] = moles / total_moles
    
    return normalized_comp_dict

# 请将此函数添加到 core/utils.py 的末尾



def get_canonical_alloy_name(alloy_composition) -> str:
    """
    从合金组成字符串或字典中，生成一个按字母排序的、规范的合金名称。
    例如: "Fe0.7Si0.1C0.2" -> "C-Fe-Si"

    Args:
        alloy_composition (str or dict): 合金组成字符串或已解析的字典。

    Returns:
        str: 规范化的合金名称，例如 "C-Fe-Si"。
    """
    elements = []
    if isinstance(alloy_composition, str):
        # 从字符串中提取所有元素符号
        elements = sorted(list(set(re.findall(r"([A-Z][a-z]?)", alloy_composition))))
    elif isinstance(alloy_composition, dict):
        # 从字典的键中获取所有元素
        elements = sorted(list(alloy_composition.keys()))

    return "-".join(elements)