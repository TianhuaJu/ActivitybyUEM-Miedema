# utils.py

from core.constants import Constants
from PyQt5.QtWidgets import QMessageBox # Consider removing or abstracting PyQt5

def entropy_judge(*elements: str) -> bool:
    """
    判断是否需要考虑过剩熵。

    Args:
        *elements: 一个或多个元素符号。

    Returns:
        bool: 如果根据规则需要考虑过剩熵，则返回 True，否则返回 False。
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