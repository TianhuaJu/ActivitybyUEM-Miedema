# -*- coding: utf-8 -*-
"""
用户数据输入对话框 (User Data Input Dialog)
============================================
当数据库中找不到所需数据时，弹出对话框让用户输入。
支持解析温度依赖的表达式字符串。

作者: Claude
日期: 2026-02-10
"""

import re
import math
from typing import Optional, Callable, Tuple, Dict, Any

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QGroupBox, QGridLayout, QTextEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class TemperatureDependentParser:
    """
    温度依赖字符串解析器

    支持解析以下格式的表达式：
    - 常数: "15000", "-191000"
    - 线性: "-191000 + 17*T", "100-5*T"
    - 多项式: "100 + 5*T - 0.001*T^2", "A + B*T + C*T^2"

    返回一个可调用函数 f(T) -> float
    """

    # 匹配数字（包括科学计数法）
    NUMBER_PATTERN = r'[+-]?\d+\.?\d*(?:[eE][+-]?\d+)?'

    @staticmethod
    def parse(expression: str) -> Tuple[bool, Callable[[float], float], str]:
        """
        解析温度依赖表达式

        参数:
        -----
        expression : str
            温度依赖表达式字符串

        返回:
        -----
        Tuple[bool, Callable, str]:
            - success: 是否解析成功
            - func: 可调用函数 f(T) -> float，失败时返回 None
            - message: 错误信息或解析后的表达式描述
        """
        if not expression or not expression.strip():
            return False, None, "表达式不能为空"

        expr = expression.strip()

        # 移除空格
        expr_clean = expr.replace(' ', '')

        # 尝试解析为纯数字
        try:
            value = float(expr_clean)
            return True, lambda T, v=value: v, f"常数: {value}"
        except ValueError:
            pass

        # 尝试解析为温度依赖表达式
        try:
            # 将表达式转换为可计算形式
            # 替换 T^2, T^3 等为 T**2, T**3
            calc_expr = re.sub(r'T\^(\d+)', r'T**\1', expr_clean)

            # 替换 *T 确保正确
            # 已经是正确格式

            # 测试表达式是否有效
            T = 1000.0  # 测试温度
            try:
                test_value = eval(calc_expr)
                if not isinstance(test_value, (int, float)):
                    return False, None, f"表达式结果不是数值: {type(test_value)}"
            except Exception as e:
                return False, None, f"表达式无效: {str(e)}"

            # 创建可调用函数
            def evaluator(T, expr=calc_expr):
                return eval(expr)

            return True, evaluator, f"表达式: {expr}"

        except Exception as e:
            return False, None, f"解析失败: {str(e)}"

    @staticmethod
    def evaluate_at_temperature(expression: str, T: float) -> Tuple[bool, float, str]:
        """
        在指定温度下计算表达式的值

        参数:
        -----
        expression : str
            温度依赖表达式
        T : float
            温度 (K)

        返回:
        -----
        Tuple[bool, float, str]:
            - success: 是否计算成功
            - value: 计算结果，失败时为 None
            - message: 错误信息或成功信息
        """
        success, func, msg = TemperatureDependentParser.parse(expression)

        if not success:
            return False, None, msg

        try:
            value = func(T)
            return True, value, f"T={T}K 时的值: {value}"
        except Exception as e:
            return False, None, f"计算失败: {str(e)}"


class UserDataInputDialog(QDialog):
    """
    用户数据输入对话框

    当数据库中找不到所需的热力学数据时，弹出此对话框让用户输入。
    支持输入常数或温度依赖表达式。
    """

    def __init__(
        self,
        parent=None,
        data_name: str = "数据",
        data_description: str = "",
        unit: str = "",
        example: str = "",
        allow_temperature_dependent: bool = True
    ):
        """
        初始化对话框

        参数:
        -----
        parent : QWidget
            父窗口
        data_name : str
            数据名称 (如 "熔化焓", "生成自由能")
        data_description : str
            数据描述
        unit : str
            单位 (如 "J/mol", "K")
        example : str
            示例输入
        allow_temperature_dependent : bool
            是否允许温度依赖表达式
        """
        super().__init__(parent)

        self.data_name = data_name
        self.data_description = data_description
        self.unit = unit
        self.allow_temperature_dependent = allow_temperature_dependent

        self._result_value = None
        self._result_func = None
        self._is_temperature_dependent = False

        self._setup_ui(example)

    def _setup_ui(self, example: str):
        """设置UI"""
        self.setWindowTitle(f"输入 {self.data_name}")
        self.setMinimumWidth(450)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 标题和说明
        title_label = QLabel(f"数据库中未找到 {self.data_name}")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #d9534f;")
        layout.addWidget(title_label)

        if self.data_description:
            desc_label = QLabel(self.data_description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #666;")
            layout.addWidget(desc_label)

        # 输入区域
        input_group = QGroupBox("请输入数据值")
        input_layout = QGridLayout(input_group)

        # 数据输入
        input_layout.addWidget(QLabel(f"{self.data_name}:"), 0, 0)

        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText(f"输入数值" + (f" ({self.unit})" if self.unit else ""))
        self.value_input.textChanged.connect(self._on_input_changed)
        input_layout.addWidget(self.value_input, 0, 1)

        if self.unit:
            input_layout.addWidget(QLabel(self.unit), 0, 2)

        # 格式说明
        if self.allow_temperature_dependent:
            format_label = QLabel(
                "支持以下格式:\n"
                "• 常数: 15000, -191000\n"
                "• 线性温度依赖: -191000 + 17*T\n"
                "• 多项式: 100 + 5*T - 0.001*T^2"
            )
        else:
            format_label = QLabel("请输入数值常数")

        format_label.setStyleSheet("color: #888; font-size: 11px;")
        input_layout.addWidget(format_label, 1, 0, 1, 3)

        # 示例
        if example:
            example_label = QLabel(f"示例: {example}")
            example_label.setStyleSheet("color: #5cb85c; font-style: italic;")
            input_layout.addWidget(example_label, 2, 0, 1, 3)

        layout.addWidget(input_group)

        # 验证结果显示
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("取消计算")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.ok_btn = QPushButton("确定")
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self._on_accept)
        self.ok_btn.setDefault(True)
        button_layout.addWidget(self.ok_btn)

        layout.addLayout(button_layout)

    def _on_input_changed(self, text: str):
        """输入变化时验证"""
        if not text.strip():
            self.validation_label.setText("")
            self.ok_btn.setEnabled(False)
            return

        success, func, msg = TemperatureDependentParser.parse(text)

        if success:
            # 测试计算
            try:
                test_T = 1000.0
                test_value = func(test_T)
                self.validation_label.setText(
                    f"✓ 有效 - {msg}\n"
                    f"  T=1000K 时的值: {test_value:.4g}"
                )
                self.validation_label.setStyleSheet("color: #5cb85c;")
                self.ok_btn.setEnabled(True)
                self._result_func = func
                self._is_temperature_dependent = 'T' in text
            except Exception as e:
                self.validation_label.setText(f"✗ 计算错误: {str(e)}")
                self.validation_label.setStyleSheet("color: #d9534f;")
                self.ok_btn.setEnabled(False)
        else:
            self.validation_label.setText(f"✗ {msg}")
            self.validation_label.setStyleSheet("color: #d9534f;")
            self.ok_btn.setEnabled(False)

    def _on_accept(self):
        """确定按钮点击"""
        text = self.value_input.text().strip()
        success, func, _ = TemperatureDependentParser.parse(text)

        if success:
            self._result_func = func
            self._is_temperature_dependent = 'T' in text.upper().replace(' ', '')
            self.accept()
        else:
            QMessageBox.warning(self, "输入错误", "请输入有效的数值或表达式")

    def get_result(self) -> Tuple[bool, Callable[[float], float], bool]:
        """
        获取输入结果

        返回:
        -----
        Tuple[bool, Callable, bool]:
            - success: 用户是否确认输入
            - func: 可调用函数 f(T) -> float
            - is_temperature_dependent: 是否是温度依赖表达式
        """
        if self.result() == QDialog.Accepted and self._result_func is not None:
            return True, self._result_func, self._is_temperature_dependent
        return False, None, False


class PrecipitateDataInputDialog(QDialog):
    """
    析出相数据输入对话框

    用于输入数据库中不存在的析出相热力学数据。
    """

    def __init__(
        self,
        parent=None,
        phase_name: str = "未知相"
    ):
        """
        初始化对话框

        参数:
        -----
        parent : QWidget
            父窗口
        phase_name : str
            析出相名称
        """
        super().__init__(parent)

        self.phase_name = phase_name
        self._result = None

        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle(f"输入析出相 {self.phase_name} 的数据")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 标题
        title_label = QLabel(f"数据库中未找到析出相 {self.phase_name} 的热力学数据")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #d9534f;")
        layout.addWidget(title_label)

        # 化学式输入
        formula_group = QGroupBox("化学式")
        formula_layout = QGridLayout(formula_group)

        formula_layout.addWidget(QLabel("元素A:"), 0, 0)
        self.elem_a_input = QLineEdit()
        self.elem_a_input.setPlaceholderText("如 Ti")
        formula_layout.addWidget(self.elem_a_input, 0, 1)

        formula_layout.addWidget(QLabel("化学计量数 m:"), 0, 2)
        self.stoich_m_input = QLineEdit()
        self.stoich_m_input.setPlaceholderText("如 1")
        formula_layout.addWidget(self.stoich_m_input, 0, 3)

        formula_layout.addWidget(QLabel("元素B:"), 1, 0)
        self.elem_b_input = QLineEdit()
        self.elem_b_input.setPlaceholderText("如 C")
        formula_layout.addWidget(self.elem_b_input, 1, 1)

        formula_layout.addWidget(QLabel("化学计量数 n:"), 1, 2)
        self.stoich_n_input = QLineEdit()
        self.stoich_n_input.setPlaceholderText("如 1")
        formula_layout.addWidget(self.stoich_n_input, 1, 3)

        layout.addWidget(formula_group)

        # 生成自由能输入
        gibbs_group = QGroupBox("生成自由能 ΔG° = A + B*T (J/mol)")
        gibbs_layout = QGridLayout(gibbs_group)

        gibbs_layout.addWidget(QLabel("常数项 A:"), 0, 0)
        self.gibbs_a_input = QLineEdit()
        self.gibbs_a_input.setPlaceholderText("如 -191000")
        gibbs_layout.addWidget(self.gibbs_a_input, 0, 1)
        gibbs_layout.addWidget(QLabel("J/mol"), 0, 2)

        gibbs_layout.addWidget(QLabel("温度系数 B:"), 1, 0)
        self.gibbs_b_input = QLineEdit()
        self.gibbs_b_input.setPlaceholderText("如 17.0")
        gibbs_layout.addWidget(self.gibbs_b_input, 1, 1)
        gibbs_layout.addWidget(QLabel("J/(mol·K)"), 1, 2)

        example_label = QLabel(
            "说明: ΔG° = A + B*T 是析出相的标准生成自由能\n"
            "示例 (TiC): A = -191000, B = 17.0"
        )
        example_label.setStyleSheet("color: #888; font-size: 11px;")
        gibbs_layout.addWidget(example_label, 2, 0, 1, 3)

        layout.addWidget(gibbs_group)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("取消计算")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self._on_accept)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    def _on_accept(self):
        """验证并接受输入"""
        try:
            elem_a = self.elem_a_input.text().strip().capitalize()
            elem_b = self.elem_b_input.text().strip().capitalize()
            stoich_m = int(self.stoich_m_input.text().strip())
            stoich_n = int(self.stoich_n_input.text().strip())
            gibbs_a = float(self.gibbs_a_input.text().strip())
            gibbs_b = float(self.gibbs_b_input.text().strip())

            if not elem_a or not elem_b:
                raise ValueError("元素符号不能为空")
            if stoich_m <= 0 or stoich_n <= 0:
                raise ValueError("化学计量数必须为正整数")

            self._result = {
                'formula': (elem_a, elem_b),
                'stoich': (stoich_m, stoich_n),
                'delta_G': (gibbs_a, gibbs_b)
            }
            self.accept()

        except ValueError as e:
            QMessageBox.warning(self, "输入错误", f"请检查输入: {str(e)}")

    def get_result(self) -> Tuple[bool, Optional[Dict]]:
        """
        获取输入结果

        返回:
        -----
        Tuple[bool, Dict]:
            - success: 用户是否确认输入
            - data: 析出相数据字典
        """
        if self.result() == QDialog.Accepted and self._result is not None:
            return True, self._result
        return False, None


# 便捷函数
def request_user_data(
    parent,
    data_name: str,
    data_description: str = "",
    unit: str = "",
    example: str = "",
    allow_temperature_dependent: bool = True
) -> Tuple[bool, Callable[[float], float]]:
    """
    请求用户输入数据的便捷函数

    参数:
    -----
    parent : QWidget
        父窗口
    data_name : str
        数据名称
    data_description : str
        数据描述
    unit : str
        单位
    example : str
        示例
    allow_temperature_dependent : bool
        是否允许温度依赖表达式

    返回:
    -----
    Tuple[bool, Callable]:
        - success: 用户是否确认输入
        - func: 可调用函数 f(T) -> float
    """
    dialog = UserDataInputDialog(
        parent=parent,
        data_name=data_name,
        data_description=data_description,
        unit=unit,
        example=example,
        allow_temperature_dependent=allow_temperature_dependent
    )

    dialog.exec_()
    success, func, _ = dialog.get_result()
    return success, func


def request_precipitate_data(
    parent,
    phase_name: str
) -> Tuple[bool, Optional[Dict]]:
    """
    请求用户输入析出相数据的便捷函数

    参数:
    -----
    parent : QWidget
        父窗口
    phase_name : str
        析出相名称

    返回:
    -----
    Tuple[bool, Dict]:
        - success: 用户是否确认输入
        - data: 析出相数据字典
    """
    dialog = PrecipitateDataInputDialog(
        parent=parent,
        phase_name=phase_name
    )

    dialog.exec_()
    return dialog.get_result()


class MissingDataHandler:
    """
    缺失数据处理器

    用于处理计算过程中遇到的缺失数据情况。
    当计算返回 'missing_data' 状态时，自动弹出对话框让用户输入数据。
    """

    def __init__(self, parent_widget):
        """
        初始化处理器

        参数:
        -----
        parent_widget : QWidget
            父窗口，用于显示对话框
        """
        self.parent = parent_widget
        self.user_data_cache = {}  # 缓存用户输入的数据

    def handle_missing_data(self, result: Dict) -> Tuple[bool, Dict]:
        """
        处理缺失数据

        参数:
        -----
        result : Dict
            计算返回的结果，包含 'missing_data' 字段

        返回:
        -----
        Tuple[bool, Dict]:
            - success: 是否成功获取所有缺失数据
            - user_data: 用户提供的数据字典
        """
        if result.get('status') != 'missing_data':
            return True, {}

        missing_list = result.get('missing_data', [])
        user_data = {}

        for item in missing_list:
            data_type = item.get('type')

            if data_type == 'melting_point':
                success, func = self._request_melting_point(item)
                if not success:
                    return False, None
                if 'melting_point' not in user_data:
                    user_data['melting_point'] = {}
                user_data['melting_point'][item['element']] = func(0)  # 熔点是常数

            elif data_type == 'enthalpy_of_fusion':
                success, func = self._request_enthalpy_of_fusion(item)
                if not success:
                    return False, None
                if 'enthalpy_of_fusion' not in user_data:
                    user_data['enthalpy_of_fusion'] = {}
                user_data['enthalpy_of_fusion'][item['element']] = func

            elif data_type == 'precipitate_data':
                success, data = self._request_precipitate_data(item)
                if not success:
                    return False, None
                if 'precipitate_data' not in user_data:
                    user_data['precipitate_data'] = {}
                user_data['precipitate_data'][item['phase_type']] = data

            else:
                # 未知类型，使用通用对话框
                success, func = request_user_data(
                    self.parent,
                    data_name=item.get('description', '未知数据'),
                    data_description=item.get('description', ''),
                    unit=item.get('unit', ''),
                    example=item.get('example', '')
                )
                if not success:
                    return False, None

        return True, user_data

    def _request_melting_point(self, item: Dict) -> Tuple[bool, Callable]:
        """请求熔点数据"""
        element = item.get('element', '未知')
        return request_user_data(
            self.parent,
            data_name=f"元素 {element} 的熔点",
            data_description=f"数据库中未找到元素 {element} 的熔点数据。请输入该元素的熔点温度。",
            unit="K",
            example=item.get('example', '1811 (Fe的熔点)'),
            allow_temperature_dependent=False  # 熔点是常数
        )

    def _request_enthalpy_of_fusion(self, item: Dict) -> Tuple[bool, Callable]:
        """请求熔化焓数据"""
        element = item.get('element', '未知')
        return request_user_data(
            self.parent,
            data_name=f"元素 {element} 的熔化焓 (ΔH_f)",
            data_description=f"数据库中未找到元素 {element} 的熔化焓数据。\n"
                           f"熔化焓是物质从固态变为液态所需的能量。",
            unit="J/mol",
            example=item.get('example', '13810 (Fe的熔化焓)'),
            allow_temperature_dependent=True
        )

    def _request_precipitate_data(self, item: Dict) -> Tuple[bool, Optional[Dict]]:
        """请求析出相数据"""
        phase_type = item.get('phase_type', '未知')
        return request_precipitate_data(self.parent, phase_type)

    def clear_cache(self):
        """清除缓存的用户数据"""
        self.user_data_cache = {}


def handle_calculation_with_missing_data(
    parent_widget,
    calc_func: Callable,
    max_retries: int = 3,
    **calc_kwargs
) -> Dict:
    """
    执行计算并处理缺失数据的便捷函数

    自动处理计算中的缺失数据情况：
    1. 执行计算
    2. 如果返回 'missing_data' 状态，弹出对话框让用户输入
    3. 使用用户数据重试计算
    4. 如果用户取消，返回取消状态

    参数:
    -----
    parent_widget : QWidget
        父窗口
    calc_func : Callable
        计算函数
    max_retries : int
        最大重试次数
    **calc_kwargs : dict
        传递给计算函数的参数

    返回:
    -----
    Dict: 计算结果或取消/错误状态
    """
    handler = MissingDataHandler(parent_widget)
    user_data = calc_kwargs.pop('user_data', None) or {}

    for retry in range(max_retries):
        # 执行计算
        result = calc_func(user_data=user_data, **calc_kwargs)

        if result.get('status') == 'missing_data':
            # 处理缺失数据
            success, new_user_data = handler.handle_missing_data(result)

            if not success:
                # 用户取消
                return {
                    'status': 'cancelled',
                    'message': '用户取消了数据输入',
                    'result': None
                }

            # 合并用户数据并重试
            for key, value in new_user_data.items():
                if key in user_data:
                    user_data[key].update(value)
                else:
                    user_data[key] = value

            continue

        # 计算完成（成功、警告或错误）
        return result

    # 达到最大重试次数
    return {
        'status': 'error',
        'message': f'达到最大重试次数 ({max_retries})，仍有缺失数据',
        'result': None
    }


# 测试代码
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 测试解析器
    print("=== 测试温度依赖解析器 ===")
    test_cases = [
        "15000",
        "-191000",
        "-191000 + 17*T",
        "100 - 5*T",
        "100 + 5*T - 0.001*T^2",
        "-338000+90*T",
        "invalid expression",
    ]

    for expr in test_cases:
        success, func, msg = TemperatureDependentParser.parse(expr)
        print(f"'{expr}': {msg}")
        if success:
            print(f"  T=1000K: {func(1000):.2f}")
            print(f"  T=1500K: {func(1500):.2f}")
        print()

    # 测试对话框
    print("=== 测试用户输入对话框 ===")
    success, func = request_user_data(
        None,
        data_name="熔化焓 (ΔH_f)",
        data_description="元素 Zr 的熔化焓数据不在数据库中",
        unit="J/mol",
        example="-191000 + 17*T"
    )

    if success:
        print(f"用户输入成功，T=1000K时的值: {func(1000)}")
    else:
        print("用户取消了输入")

    sys.exit(0)
