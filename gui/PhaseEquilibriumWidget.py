"""
Phase Equilibrium Widget
=========================
相平衡计算GUI组件

功能:
1. 计算给定合金组成在一定温度下的平衡相及其占比
2. 相平衡组成随温度的变化
3. 相平衡在指定温度下随组分的变化

作者: Claude
日期: 2025-11-23
"""

import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton,
                             QSplitter, QFrame, QGroupBox, QTextEdit,
                             QMessageBox, QTableWidget, QTableWidgetItem,
                             QProgressBar, QTabWidget, QDoubleSpinBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from gui.widgets import AutoResizeTextEdit
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils import parse_composition_static
from calculations.phase_equilibrium import PhaseEquilibriumCalculator, ManualPhaseEquilibriumCalculator
from models.extrapolation_models import BinaryModel


class CalculationThread(QThread):
    """计算线程"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, int)
    error = pyqtSignal(str)

    def __init__(self, calc_func, *args, **kwargs):
        super().__init__()
        self.calc_func = calc_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.calc_func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MplCanvas(FigureCanvas):
    """Matplotlib画布类"""

    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)


class PhaseEquilibriumWidget(QWidget):
    """相平衡计算组件"""

    def __init__(self):
        super().__init__()

        self.calculator = PhaseEquilibriumCalculator()
        self.manual_calculator = ManualPhaseEquilibriumCalculator()
        self.binary_model = BinaryModel()
        self.calc_thread = None
        self.current_results = None

        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout(self)

        # 创建主标签页
        self.main_tabs = QTabWidget()
        layout.addWidget(self.main_tabs)

        # 功能1: 单点平衡计算
        self.tab1 = self.create_single_point_tab()
        self.main_tabs.addTab(self.tab1, "平衡相计算")

        # 功能2: 温度变化分析
        self.tab2 = self.create_temperature_variation_tab()
        self.main_tabs.addTab(self.tab2, "温度变化分析")

        # 功能3: 组分变化分析
        self.tab3 = self.create_composition_variation_tab()
        self.main_tabs.addTab(self.tab3, "组分变化分析")

        # 功能4: 手动指定平衡相
        self.tab4 = self.create_manual_phase_tab()
        self.main_tabs.addTab(self.tab4, "手动指定平衡相")

    def create_single_point_tab(self):
        """创建单点平衡计算标签"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧输入面板
        left_widget = self.create_single_point_input_panel()

        # 右侧结果面板
        right_widget = self.create_single_point_results_panel()

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([350, 850])

        return widget

    def create_single_point_input_panel(self):
        """创建单点计算输入面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 输入参数分组
        input_group = QGroupBox("输入参数")
        input_layout = QGridLayout(input_group)
        input_layout.setSpacing(15)
        input_layout.setContentsMargins(20, 25, 20, 20)

        row = 0

        # 合金成分（自动调整大小）
        input_layout.addWidget(QLabel("合金成分:"), row, 0, Qt.AlignRight)
        self.sp_composition_input = AutoResizeTextEdit(min_lines=1, max_lines=3)
        self.sp_composition_input.setText("Fe0.70C0.03Si0.27")
        self.sp_composition_input.setPlaceholderText("例如: Fe0.7C0.03Si0.27")
        self.sp_composition_input.setToolTip("输入格式: 元素符号+摩尔分数")
        input_layout.addWidget(self.sp_composition_input, row, 1)
        row += 1

        # 温度
        input_layout.addWidget(QLabel("温度 (K):"), row, 0, Qt.AlignRight)
        self.sp_temperature_input = QLineEdit("1873")
        self.sp_temperature_input.setPlaceholderText("温度 (K)")
        input_layout.addWidget(self.sp_temperature_input, row, 1)
        row += 1

        # 外推模型
        input_layout.addWidget(QLabel("外推模型:"), row, 0, Qt.AlignRight)
        self.sp_extrap_model_combo = QComboBox()
        self.sp_extrap_model_combo.addItems([
            "UEM1", "UEM2", "UEM2-Adv", "GSM",
            "Muggianu", "Toop-Muggianu", "Toop-Kohler"
        ])
        input_layout.addWidget(self.sp_extrap_model_combo, row, 1)
        row += 1

        # 活度模型
        input_layout.addWidget(QLabel("活度模型:"), row, 0, Qt.AlignRight)
        self.sp_activity_model_combo = QComboBox()
        self.sp_activity_model_combo.addItems(["Wagner", "Darken", "Elliott"])
        input_layout.addWidget(self.sp_activity_model_combo, row, 1)
        row += 1

        layout.addWidget(input_group)

        # 计算按钮
        button_layout = QHBoxLayout()
        self.sp_calculate_button = QPushButton("计算")
        self.sp_calculate_button.setMinimumHeight(40)
        self.sp_calculate_button.clicked.connect(self.perform_single_point_calculation)
        button_layout.addWidget(self.sp_calculate_button)

        self.sp_clear_button = QPushButton("清除")
        self.sp_clear_button.setMinimumHeight(40)
        self.sp_clear_button.clicked.connect(self.clear_single_point_results)
        button_layout.addWidget(self.sp_clear_button)

        layout.addLayout(button_layout)
        layout.addStretch()

        return widget

    def create_single_point_results_panel(self):
        """创建单点计算结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 进度条
        self.sp_progress_bar = QProgressBar()
        self.sp_progress_bar.setVisible(False)
        self.sp_progress_bar.setRange(0, 0)
        layout.addWidget(self.sp_progress_bar)

        # 结果文本
        results_group = QGroupBox("计算结果")
        results_layout = QVBoxLayout(results_group)

        self.sp_results_text = QTextEdit()
        self.sp_results_text.setReadOnly(True)
        self.sp_results_text.setMinimumHeight(200)
        results_layout.addWidget(self.sp_results_text)

        layout.addWidget(results_group)

        # 结果表格
        table_group = QGroupBox("相平衡详细信息")
        table_layout = QVBoxLayout(table_group)

        self.sp_results_table = QTableWidget()
        self.sp_results_table.setColumnCount(6)
        self.sp_results_table.setHorizontalHeaderLabels([
            "相名称", "相分数 (%)", "吉布斯能 (J/mol)", "元素", "摩尔分数", "质量分数"
        ])
        table_layout.addWidget(self.sp_results_table)

        layout.addWidget(table_group)

        # 饼图
        chart_group = QGroupBox("相分数可视化")
        chart_layout = QVBoxLayout(chart_group)

        self.sp_canvas = MplCanvas(self, width=6, height=4, dpi=100)
        chart_layout.addWidget(self.sp_canvas)

        layout.addWidget(chart_group)

        return widget

    def create_temperature_variation_tab(self):
        """创建温度变化分析标签"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧输入面板
        left_widget = self.create_temp_var_input_panel()

        # 右侧结果面板
        right_widget = self.create_temp_var_results_panel()

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([350, 850])

        return widget

    def create_temp_var_input_panel(self):
        """创建温度变化输入面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 输入参数分组
        input_group = QGroupBox("输入参数")
        input_layout = QGridLayout(input_group)
        input_layout.setSpacing(15)
        input_layout.setContentsMargins(20, 25, 20, 20)

        row = 0

        # 合金成分（自动调整大小）
        input_layout.addWidget(QLabel("合金成分:"), row, 0, Qt.AlignRight)
        self.tv_composition_input = AutoResizeTextEdit(min_lines=1, max_lines=3)
        self.tv_composition_input.setText("Fe0.70C0.03Si0.27")
        self.tv_composition_input.setPlaceholderText("例如: Fe0.7C0.03Si0.27")
        input_layout.addWidget(self.tv_composition_input, row, 1)
        row += 1

        # 起始温度
        input_layout.addWidget(QLabel("起始温度 (K):"), row, 0, Qt.AlignRight)
        self.tv_t_min_input = QLineEdit("1273")
        input_layout.addWidget(self.tv_t_min_input, row, 1)
        row += 1

        # 终止温度
        input_layout.addWidget(QLabel("终止温度 (K):"), row, 0, Qt.AlignRight)
        self.tv_t_max_input = QLineEdit("2273")
        input_layout.addWidget(self.tv_t_max_input, row, 1)
        row += 1

        # 温度点数
        input_layout.addWidget(QLabel("温度点数:"), row, 0, Qt.AlignRight)
        self.tv_n_points_input = QLineEdit("50")
        input_layout.addWidget(self.tv_n_points_input, row, 1)
        row += 1

        # 外推模型
        input_layout.addWidget(QLabel("外推模型:"), row, 0, Qt.AlignRight)
        self.tv_extrap_model_combo = QComboBox()
        self.tv_extrap_model_combo.addItems([
            "UEM1", "UEM2", "UEM2-Adv", "GSM",
            "Muggianu", "Toop-Muggianu", "Toop-Kohler"
        ])
        input_layout.addWidget(self.tv_extrap_model_combo, row, 1)
        row += 1

        # 活度模型
        input_layout.addWidget(QLabel("活度模型:"), row, 0, Qt.AlignRight)
        self.tv_activity_model_combo = QComboBox()
        self.tv_activity_model_combo.addItems(["Wagner", "Darken", "Elliott"])
        input_layout.addWidget(self.tv_activity_model_combo, row, 1)
        row += 1

        layout.addWidget(input_group)

        # 计算按钮
        button_layout = QHBoxLayout()
        self.tv_calculate_button = QPushButton("计算")
        self.tv_calculate_button.setMinimumHeight(40)
        self.tv_calculate_button.clicked.connect(self.perform_temperature_variation_calculation)
        button_layout.addWidget(self.tv_calculate_button)

        self.tv_clear_button = QPushButton("清除")
        self.tv_clear_button.setMinimumHeight(40)
        self.tv_clear_button.clicked.connect(self.clear_temperature_variation_results)
        button_layout.addWidget(self.tv_clear_button)

        layout.addLayout(button_layout)
        layout.addStretch()

        return widget

    def create_temp_var_results_panel(self):
        """创建温度变化结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 进度条
        self.tv_progress_bar = QProgressBar()
        self.tv_progress_bar.setVisible(False)
        layout.addWidget(self.tv_progress_bar)

        # 结果文本
        results_group = QGroupBox("计算摘要")
        results_layout = QVBoxLayout(results_group)

        self.tv_results_text = QTextEdit()
        self.tv_results_text.setReadOnly(True)
        self.tv_results_text.setMaximumHeight(150)
        results_layout.addWidget(self.tv_results_text)

        layout.addWidget(results_group)

        # 图表
        chart_group = QGroupBox("相分数随温度变化")
        chart_layout = QVBoxLayout(chart_group)

        self.tv_canvas = MplCanvas(self, width=8, height=6, dpi=100)
        chart_layout.addWidget(self.tv_canvas)

        layout.addWidget(chart_group)

        return widget

    def create_composition_variation_tab(self):
        """创建组分变化分析标签"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧输入面板
        left_widget = self.create_comp_var_input_panel()

        # 右侧结果面板
        right_widget = self.create_comp_var_results_panel()

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([350, 850])

        return widget

    def create_comp_var_input_panel(self):
        """创建组分变化输入面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 输入参数分组
        input_group = QGroupBox("输入参数")
        input_layout = QGridLayout(input_group)
        input_layout.setSpacing(15)
        input_layout.setContentsMargins(20, 25, 20, 20)

        row = 0

        # 基础合金成分（自动调整大小）
        input_layout.addWidget(QLabel("基础合金:"), row, 0, Qt.AlignRight)
        self.cv_base_composition_input = AutoResizeTextEdit(min_lines=1, max_lines=3)
        self.cv_base_composition_input.setText("Fe0.97Si0.03")
        self.cv_base_composition_input.setPlaceholderText("例如: Fe0.97Si0.03")
        self.cv_base_composition_input.setToolTip("不含变化元素的基础组成")
        input_layout.addWidget(self.cv_base_composition_input, row, 1)
        row += 1

        # 变化元素
        input_layout.addWidget(QLabel("变化元素:"), row, 0, Qt.AlignRight)
        self.cv_variable_element_input = QLineEdit("C")
        self.cv_variable_element_input.setPlaceholderText("元素符号,如: C")
        input_layout.addWidget(self.cv_variable_element_input, row, 1)
        row += 1

        # 最小摩尔分数
        input_layout.addWidget(QLabel("最小摩尔分数:"), row, 0, Qt.AlignRight)
        self.cv_x_min_input = QLineEdit("0.0")
        input_layout.addWidget(self.cv_x_min_input, row, 1)
        row += 1

        # 最大摩尔分数
        input_layout.addWidget(QLabel("最大摩尔分数:"), row, 0, Qt.AlignRight)
        self.cv_x_max_input = QLineEdit("0.10")
        input_layout.addWidget(self.cv_x_max_input, row, 1)
        row += 1

        # 温度
        input_layout.addWidget(QLabel("温度 (K):"), row, 0, Qt.AlignRight)
        self.cv_temperature_input = QLineEdit("1873")
        input_layout.addWidget(self.cv_temperature_input, row, 1)
        row += 1

        # 组分点数
        input_layout.addWidget(QLabel("组分点数:"), row, 0, Qt.AlignRight)
        self.cv_n_points_input = QLineEdit("50")
        input_layout.addWidget(self.cv_n_points_input, row, 1)
        row += 1

        # 外推模型
        input_layout.addWidget(QLabel("外推模型:"), row, 0, Qt.AlignRight)
        self.cv_extrap_model_combo = QComboBox()
        self.cv_extrap_model_combo.addItems([
            "UEM1", "UEM2", "UEM2-Adv", "GSM",
            "Muggianu", "Toop-Muggianu", "Toop-Kohler"
        ])
        input_layout.addWidget(self.cv_extrap_model_combo, row, 1)
        row += 1

        # 活度模型
        input_layout.addWidget(QLabel("活度模型:"), row, 0, Qt.AlignRight)
        self.cv_activity_model_combo = QComboBox()
        self.cv_activity_model_combo.addItems(["Wagner", "Darken", "Elliott"])
        input_layout.addWidget(self.cv_activity_model_combo, row, 1)
        row += 1

        layout.addWidget(input_group)

        # 计算按钮
        button_layout = QHBoxLayout()
        self.cv_calculate_button = QPushButton("计算")
        self.cv_calculate_button.setMinimumHeight(40)
        self.cv_calculate_button.clicked.connect(self.perform_composition_variation_calculation)
        button_layout.addWidget(self.cv_calculate_button)

        self.cv_clear_button = QPushButton("清除")
        self.cv_clear_button.setMinimumHeight(40)
        self.cv_clear_button.clicked.connect(self.clear_composition_variation_results)
        button_layout.addWidget(self.cv_clear_button)

        layout.addLayout(button_layout)
        layout.addStretch()

        return widget

    def create_comp_var_results_panel(self):
        """创建组分变化结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 进度条
        self.cv_progress_bar = QProgressBar()
        self.cv_progress_bar.setVisible(False)
        layout.addWidget(self.cv_progress_bar)

        # 结果文本
        results_group = QGroupBox("计算摘要")
        results_layout = QVBoxLayout(results_group)

        self.cv_results_text = QTextEdit()
        self.cv_results_text.setReadOnly(True)
        self.cv_results_text.setMaximumHeight(150)
        results_layout.addWidget(self.cv_results_text)

        layout.addWidget(results_group)

        # 图表
        chart_group = QGroupBox("相分数随组分变化")
        chart_layout = QVBoxLayout(chart_group)

        self.cv_canvas = MplCanvas(self, width=8, height=6, dpi=100)
        chart_layout.addWidget(self.cv_canvas)

        layout.addWidget(chart_group)

        return widget

    # ========== 功能1: 单点平衡计算 ==========

    def perform_single_point_calculation(self):
        """执行单点平衡计算"""
        try:
            # 解析输入
            comp_str = self.sp_composition_input.text().strip()
            if not comp_str:
                QMessageBox.warning(self, "输入错误", "请输入合金成分！")
                return

            composition = parse_composition_static(comp_str)
            temperature = float(self.sp_temperature_input.text())
            extrap_model_name = self.sp_extrap_model_combo.currentText()
            activity_model = self.sp_activity_model_combo.currentText()

            # 获取外推模型函数
            extrap_func = getattr(self.binary_model, extrap_model_name)

            # 显示进度
            self.sp_progress_bar.setVisible(True)
            self.sp_calculate_button.setEnabled(False)

            # 执行计算（平衡相数由热力学自动判断）
            result = self.calculator.calculate_phase_equilibrium_at_temperature(
                composition, temperature, extrap_func,
                extrap_model_name, activity_model
            )

            # 显示结果
            self.display_single_point_results(result)

        except ValueError as e:
            QMessageBox.warning(self, "输入错误", f"输入参数无效:\n{str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "计算错误", f"计算过程中发生错误:\n{str(e)}")
        finally:
            self.sp_progress_bar.setVisible(False)
            self.sp_calculate_button.setEnabled(True)

    def display_single_point_results(self, result):
        """显示单点计算结果"""
        # 显示文本结果
        text = f"=== 相平衡计算结果 ===\n\n"
        text += f"状态: {result.get('status', 'unknown')}\n"
        text += f"温度: {result.get('temperature', 0):.2f} K\n"
        text += f"总组成: {result.get('total_composition', {})}\n"
        text += f"总吉布斯自由能: {result.get('total_gibbs_energy', 0):.2f} J/mol\n"
        text += f"消息: {result.get('message', '')}\n"

        # 显示Gibbs相律验证信息
        gibbs_info = result.get('gibbs_phase_rule')
        if gibbs_info:
            text += f"\n--- Gibbs相律验证 ---\n"
            text += f"组分数 C = {gibbs_info['num_components']}\n"
            text += f"相数 P = {gibbs_info['num_phases']}\n"
            text += f"自由度 F = C - P = {gibbs_info['degrees_of_freedom']}\n"
            text += f"最大允许相数 = {gibbs_info['max_phases_allowed']}\n"
            if gibbs_info['is_valid']:
                text += f"验证结果: 符合Gibbs相律\n"
            else:
                text += f"验证结果: 违反Gibbs相律（相数过多）\n"

        if 'phases' in result and result['phases']:
            text += f"\n平衡相数: {len(result['phases'])}\n\n"

            for i, phase in enumerate(result['phases'], 1):
                text += f"相 {i}: {phase.name}\n"
                text += f"  相分数: {phase.fraction:.4f} ({phase.fraction*100:.2f}%)\n"
                text += f"  吉布斯能: {phase.gibbs_energy:.2f} J/mol\n"
                text += f"  组成: {phase.composition}\n\n"

        self.sp_results_text.setPlainText(text)

        # 填充表格
        self.fill_single_point_table(result)

        # 绘制饼图
        self.plot_single_point_chart(result)

    def fill_single_point_table(self, result):
        """填充单点计算表格"""
        self.sp_results_table.setRowCount(0)

        if 'phases' not in result or not result['phases']:
            return

        row = 0
        for phase in result['phases']:
            # 计算该相中各元素的质量分数
            total_mass = 0
            elem_masses = {}

            # 获取元素原子质量 (简化处理,使用近似值)
            atomic_masses = {
                'FE': 55.845, 'C': 12.011, 'SI': 28.085, 'MN': 54.938,
                'CR': 51.996, 'NI': 58.693, 'MO': 95.94, 'CU': 63.546,
                'AL': 26.982, 'TI': 47.867, 'V': 50.942, 'W': 183.84,
                'CO': 58.933, 'N': 14.007, 'P': 30.974, 'S': 32.065
            }

            for elem, mole_frac in phase.composition.items():
                atomic_mass = atomic_masses.get(elem.upper(), 50.0)  # 默认值50
                mass = mole_frac * atomic_mass
                elem_masses[elem] = mass
                total_mass += mass

            # 为每个元素添加一行
            for elem, mole_frac in phase.composition.items():
                self.sp_results_table.insertRow(row)

                mass_frac = elem_masses[elem] / total_mass if total_mass > 0 else 0

                # 相名称
                self.sp_results_table.setItem(row, 0, QTableWidgetItem(phase.name))
                # 相分数
                self.sp_results_table.setItem(row, 1, QTableWidgetItem(f"{phase.fraction*100:.2f}"))
                # 吉布斯能
                self.sp_results_table.setItem(row, 2, QTableWidgetItem(f"{phase.gibbs_energy:.2f}"))
                # 元素
                self.sp_results_table.setItem(row, 3, QTableWidgetItem(elem))
                # 摩尔分数
                self.sp_results_table.setItem(row, 4, QTableWidgetItem(f"{mole_frac:.6f}"))
                # 质量分数
                self.sp_results_table.setItem(row, 5, QTableWidgetItem(f"{mass_frac:.6f}"))

                row += 1

        self.sp_results_table.resizeColumnsToContents()

    def plot_single_point_chart(self, result):
        """绘制单点计算饼图"""
        self.sp_canvas.axes.clear()

        if 'phases' not in result or not result['phases']:
            self.sp_canvas.draw()
            return

        # 提取相名称和分数
        labels = [phase.name for phase in result['phases']]
        fractions = [phase.fraction for phase in result['phases']]

        # 定义颜色
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8']

        # 绘制饼图
        self.sp_canvas.axes.pie(
            fractions, labels=labels, autopct='%1.1f%%',
            startangle=90, colors=colors[:len(labels)]
        )
        self.sp_canvas.axes.set_title(
            f'相分数分布 (T={result.get("temperature", 0):.0f}K)'
        )

        self.sp_canvas.draw()

    def clear_single_point_results(self):
        """清除单点计算结果"""
        self.sp_results_text.clear()
        self.sp_results_table.setRowCount(0)
        self.sp_canvas.axes.clear()
        self.sp_canvas.draw()

    # ========== 功能2: 温度变化分析 ==========

    def perform_temperature_variation_calculation(self):
        """执行温度变化计算"""
        try:
            # 解析输入
            comp_str = self.tv_composition_input.text().strip()
            if not comp_str:
                QMessageBox.warning(self, "输入错误", "请输入合金成分！")
                return

            composition = parse_composition_static(comp_str)
            T_min = float(self.tv_t_min_input.text())
            T_max = float(self.tv_t_max_input.text())
            n_points = int(self.tv_n_points_input.text())
            extrap_model_name = self.tv_extrap_model_combo.currentText()
            activity_model = self.tv_activity_model_combo.currentText()

            # 获取外推模型函数
            extrap_func = getattr(self.binary_model, extrap_model_name)

            # 显示进度
            self.tv_progress_bar.setVisible(True)
            self.tv_progress_bar.setRange(0, n_points)
            self.tv_calculate_button.setEnabled(False)

            # 执行计算
            result = self.calculator.calculate_phase_equilibrium_vs_temperature(
                composition, T_min, T_max, n_points,
                extrap_func, extrap_model_name, activity_model,
                progress_callback=self.update_tv_progress
            )

            # 显示结果
            self.display_temperature_variation_results(result, composition)

        except ValueError as e:
            QMessageBox.warning(self, "输入错误", f"输入参数无效:\n{str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "计算错误", f"计算过程中发生错误:\n{str(e)}")
        finally:
            self.tv_progress_bar.setVisible(False)
            self.tv_calculate_button.setEnabled(True)

    def update_tv_progress(self, current, total):
        """更新温度变化进度条"""
        self.tv_progress_bar.setValue(current)

    def display_temperature_variation_results(self, result, composition):
        """显示温度变化结果"""
        # 显示文本摘要
        text = f"=== 相平衡随温度变化分析 ===\n\n"
        text += f"合金组成: {composition}\n"
        text += f"温度范围: {min(result['temperatures']):.0f} - {max(result['temperatures']):.0f} K\n"
        text += f"计算点数: {len(result['temperatures'])}\n"
        text += f"发现相: {', '.join(result['phase_fractions'].keys())}\n\n"

        self.tv_results_text.setPlainText(text)

        # 绘制图表
        self.plot_temperature_variation_chart(result)

    def plot_temperature_variation_chart(self, result):
        """绘制温度变化图表"""
        self.tv_canvas.axes.clear()

        temperatures = result['temperatures']
        phase_fractions = result['phase_fractions']

        # 定义颜色映射
        color_map = {
            'LIQUID': '#FF6B6B',
            'BCC_A2': '#4ECDC4',
            'FCC_A1': '#45B7D1',
            'HCP_A3': '#FFA07A'
        }

        # 绘制堆叠区域图
        bottom = np.zeros(len(temperatures))

        for phase_name, fractions in phase_fractions.items():
            if len(fractions) > 0 and max(fractions) > 0.001:
                color = color_map.get(phase_name, '#CCCCCC')
                self.tv_canvas.axes.fill_between(
                    temperatures, bottom, bottom + fractions,
                    label=phase_name, alpha=0.7, color=color
                )
                bottom = bottom + np.array(fractions)

        self.tv_canvas.axes.set_xlabel('温度 (K)', fontsize=12)
        self.tv_canvas.axes.set_ylabel('相分数', fontsize=12)
        self.tv_canvas.axes.set_title('相分数随温度变化', fontsize=14, fontweight='bold')
        self.tv_canvas.axes.legend(loc='best')
        self.tv_canvas.axes.grid(True, alpha=0.3)
        self.tv_canvas.axes.set_ylim([0, 1])

        self.tv_canvas.fig.tight_layout()
        self.tv_canvas.draw()

    def clear_temperature_variation_results(self):
        """清除温度变化结果"""
        self.tv_results_text.clear()
        self.tv_canvas.axes.clear()
        self.tv_canvas.draw()

    # ========== 功能3: 组分变化分析 ==========

    def perform_composition_variation_calculation(self):
        """执行组分变化计算"""
        try:
            # 解析输入
            base_comp_str = self.cv_base_composition_input.text().strip()
            if not base_comp_str:
                QMessageBox.warning(self, "输入错误", "请输入基础合金成分！")
                return

            base_composition = parse_composition_static(base_comp_str)
            variable_element = self.cv_variable_element_input.text().strip()
            if not variable_element:
                QMessageBox.warning(self, "输入错误", "请输入变化元素！")
                return

            x_min = float(self.cv_x_min_input.text())
            x_max = float(self.cv_x_max_input.text())
            temperature = float(self.cv_temperature_input.text())
            n_points = int(self.cv_n_points_input.text())
            extrap_model_name = self.cv_extrap_model_combo.currentText()
            activity_model = self.cv_activity_model_combo.currentText()

            # 获取外推模型函数
            extrap_func = getattr(self.binary_model, extrap_model_name)

            # 显示进度
            self.cv_progress_bar.setVisible(True)
            self.cv_progress_bar.setRange(0, n_points)
            self.cv_calculate_button.setEnabled(False)

            # 执行计算
            result = self.calculator.calculate_phase_equilibrium_vs_composition(
                base_composition, variable_element, x_min, x_max, temperature,
                n_points, extrap_func, extrap_model_name, activity_model,
                progress_callback=self.update_cv_progress
            )

            # 显示结果
            self.display_composition_variation_results(result, base_composition)

        except ValueError as e:
            QMessageBox.warning(self, "输入错误", f"输入参数无效:\n{str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "计算错误", f"计算过程中发生错误:\n{str(e)}")
        finally:
            self.cv_progress_bar.setVisible(False)
            self.cv_calculate_button.setEnabled(True)

    def update_cv_progress(self, current, total):
        """更新组分变化进度条"""
        self.cv_progress_bar.setValue(current)

    def display_composition_variation_results(self, result, base_composition):
        """显示组分变化结果"""
        # 显示文本摘要
        text = f"=== 相平衡随组分变化分析 ===\n\n"
        text += f"基础合金: {base_composition}\n"
        text += f"变化元素: {result['variable_element']}\n"
        text += f"温度: {result['temperature']:.0f} K\n"
        text += f"组分范围: {min(result['compositions']):.4f} - {max(result['compositions']):.4f}\n"
        text += f"计算点数: {len(result['compositions'])}\n"
        text += f"发现相: {', '.join(result['phase_fractions'].keys())}\n\n"

        self.cv_results_text.setPlainText(text)

        # 绘制图表
        self.plot_composition_variation_chart(result)

    def plot_composition_variation_chart(self, result):
        """绘制组分变化图表"""
        self.cv_canvas.axes.clear()

        compositions = result['compositions']
        phase_fractions = result['phase_fractions']
        variable_element = result['variable_element']

        # 定义颜色映射
        color_map = {
            'LIQUID': '#FF6B6B',
            'BCC_A2': '#4ECDC4',
            'FCC_A1': '#45B7D1',
            'HCP_A3': '#FFA07A'
        }

        # 绘制堆叠区域图
        bottom = np.zeros(len(compositions))

        for phase_name, fractions in phase_fractions.items():
            if len(fractions) > 0 and max(fractions) > 0.001:
                color = color_map.get(phase_name, '#CCCCCC')
                self.cv_canvas.axes.fill_between(
                    compositions, bottom, bottom + fractions,
                    label=phase_name, alpha=0.7, color=color
                )
                bottom = bottom + np.array(fractions)

        self.cv_canvas.axes.set_xlabel(f'{variable_element} 摩尔分数', fontsize=12)
        self.cv_canvas.axes.set_ylabel('相分数', fontsize=12)
        self.cv_canvas.axes.set_title(
            f'相分数随 {variable_element} 含量变化 (T={result["temperature"]:.0f}K)',
            fontsize=14, fontweight='bold'
        )
        self.cv_canvas.axes.legend(loc='best')
        self.cv_canvas.axes.grid(True, alpha=0.3)
        self.cv_canvas.axes.set_ylim([0, 1])

        self.cv_canvas.fig.tight_layout()
        self.cv_canvas.draw()

    def clear_composition_variation_results(self):
        """清除组分变化结果"""
        self.cv_results_text.clear()
        self.cv_canvas.axes.clear()
        self.cv_canvas.draw()

    # ========== 功能4: 手动指定平衡相 ==========

    def create_manual_phase_tab(self):
        """创建手动指定平衡相标签"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧输入面板
        left_widget = self.create_manual_phase_input_panel()

        # 右侧结果面板
        right_widget = self.create_manual_phase_results_panel()

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 800])

        return widget

    def create_manual_phase_input_panel(self):
        """创建手动指定平衡相输入面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 输入参数分组
        input_group = QGroupBox("输入参数")
        input_layout = QGridLayout(input_group)
        input_layout.setSpacing(15)
        input_layout.setContentsMargins(20, 25, 20, 20)

        row = 0

        # 合金成分（自动调整大小）
        input_layout.addWidget(QLabel("合金成分:"), row, 0, Qt.AlignRight)
        self.mp_composition_input = AutoResizeTextEdit(min_lines=1, max_lines=3)
        self.mp_composition_input.setText("Fe0.95C0.03Si0.02")
        self.mp_composition_input.setPlaceholderText("例如: Fe0.95C0.03Si0.02")
        self.mp_composition_input.setToolTip("输入格式: 元素符号+摩尔分数")
        input_layout.addWidget(self.mp_composition_input, row, 1)
        row += 1

        # 平衡相输入（支持多个，用逗号或空格分隔）
        input_layout.addWidget(QLabel("平衡相:"), row, 0, Qt.AlignRight | Qt.AlignTop)
        self.mp_phase_input = AutoResizeTextEdit(min_lines=1, max_lines=3)
        self.mp_phase_input.setText("Fe3C")
        self.mp_phase_input.setPlaceholderText("例如: Fe3C, TiC 或 Fe3C TiC (多个用逗号或空格分隔)")
        self.mp_phase_input.setToolTip(
            "支持多个平衡相输入，用逗号或空格分隔:\n"
            "- 化合物: Fe3C, TiC, Ni3Al, Cr23C6\n"
            "- 溶体相: LIQUID, BCC_A2, FCC_A1, HCP_A3\n"
            "例如: Fe3C, TiC 或 Fe3C TiC"
        )
        input_layout.addWidget(self.mp_phase_input, row, 1)
        row += 1

        # 化合物吉布斯能（可选，支持多个，与平衡相对应）
        input_layout.addWidget(QLabel("化合物吉布斯能:"), row, 0, Qt.AlignRight | Qt.AlignTop)
        self.mp_gibbs_input = AutoResizeTextEdit(min_lines=1, max_lines=3)
        self.mp_gibbs_input.setPlaceholderText("可选，多个用逗号分隔，如: -50000, -80000 (J/mol)")
        self.mp_gibbs_input.setToolTip(
            "仅对化合物有效。多个值用逗号分隔，顺序与平衡相对应。\n"
            "留空表示自动估算。部分留空用 'auto' 占位。\n"
            "例如: -50000, auto, -80000"
        )
        input_layout.addWidget(self.mp_gibbs_input, row, 1)
        row += 1

        # 温度
        input_layout.addWidget(QLabel("温度 (K):"), row, 0, Qt.AlignRight)
        self.mp_temperature_input = QLineEdit("1273")
        self.mp_temperature_input.setPlaceholderText("温度 (K)")
        input_layout.addWidget(self.mp_temperature_input, row, 1)
        row += 1

        # 外推模型
        input_layout.addWidget(QLabel("外推模型:"), row, 0, Qt.AlignRight)
        self.mp_extrap_model_combo = QComboBox()
        self.mp_extrap_model_combo.addItems([
            "UEM1", "UEM2", "UEM2-Adv", "GSM",
            "Muggianu", "Toop-Muggianu", "Toop-Kohler"
        ])
        input_layout.addWidget(self.mp_extrap_model_combo, row, 1)
        row += 1

        # 活度模型
        input_layout.addWidget(QLabel("活度模型:"), row, 0, Qt.AlignRight)
        self.mp_activity_model_combo = QComboBox()
        self.mp_activity_model_combo.addItems(["Wagner", "Darken", "Elliott"])
        input_layout.addWidget(self.mp_activity_model_combo, row, 1)
        row += 1

        layout.addWidget(input_group)

        # 常用化合物提示
        hint_group = QGroupBox("常用化合物参考")
        hint_layout = QVBoxLayout(hint_group)
        hint_text = QLabel(
            "碳化物: Fe3C, Cr23C6, Cr7C3, Mo2C, VC, TiC, WC, NbC, SiC\n"
            "氮化物: TiN, VN, AlN, CrN, Cr2N, Si3N4\n"
            "金属间化合物: Ni3Al, NiAl, Fe3Al, FeAl, TiAl, Ti3Al\n"
            "硅化物: FeSi, FeSi2, Fe3Si, Mg2Si\n"
            "Laves相: Fe2Nb, Fe2Mo, Fe2Ti, Fe2W\n"
            "溶体相: LIQUID, BCC_A2, FCC_A1, HCP_A3"
        )
        hint_text.setWordWrap(True)
        hint_text.setStyleSheet("color: gray; font-size: 11px;")
        hint_layout.addWidget(hint_text)
        layout.addWidget(hint_group)

        # 计算按钮
        button_layout = QHBoxLayout()
        self.mp_calculate_button = QPushButton("计算")
        self.mp_calculate_button.setMinimumHeight(40)
        self.mp_calculate_button.clicked.connect(self.perform_manual_phase_calculation)
        button_layout.addWidget(self.mp_calculate_button)

        self.mp_clear_button = QPushButton("清除")
        self.mp_clear_button.setMinimumHeight(40)
        self.mp_clear_button.clicked.connect(self.clear_manual_phase_results)
        button_layout.addWidget(self.mp_clear_button)

        layout.addLayout(button_layout)
        layout.addStretch()

        return widget

    def create_manual_phase_results_panel(self):
        """创建手动指定平衡相结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 进度条
        self.mp_progress_bar = QProgressBar()
        self.mp_progress_bar.setVisible(False)
        self.mp_progress_bar.setRange(0, 0)
        layout.addWidget(self.mp_progress_bar)

        # 结果文本
        results_group = QGroupBox("计算结果")
        results_layout = QVBoxLayout(results_group)

        self.mp_results_text = QTextEdit()
        self.mp_results_text.setReadOnly(True)
        self.mp_results_text.setMinimumHeight(180)
        results_layout.addWidget(self.mp_results_text)

        layout.addWidget(results_group)

        # 表格并排显示区域
        tables_layout = QHBoxLayout()

        # 左侧：平衡相详细信息表格
        table_group = QGroupBox("平衡相详细信息")
        table_layout = QVBoxLayout(table_group)

        self.mp_results_table = QTableWidget()
        self.mp_results_table.setColumnCount(5)
        self.mp_results_table.setHorizontalHeaderLabels([
            "相名称", "类型", "摩尔分数 (%)", "质量分数 (%)", "吉布斯能 (J/mol)"
        ])
        self.mp_results_table.setMinimumHeight(200)
        table_layout.addWidget(self.mp_results_table)

        tables_layout.addWidget(table_group)

        # 右侧：相组成详细表格
        comp_group = QGroupBox("相组成详细")
        comp_layout = QVBoxLayout(comp_group)

        self.mp_comp_table = QTableWidget()
        self.mp_comp_table.setColumnCount(4)
        self.mp_comp_table.setHorizontalHeaderLabels([
            "相名称", "元素", "摩尔分数", "质量分数"
        ])
        self.mp_comp_table.setMinimumHeight(200)
        comp_layout.addWidget(self.mp_comp_table)

        tables_layout.addWidget(comp_group)

        layout.addLayout(tables_layout)

        # 饼图
        chart_group = QGroupBox("相分数可视化")
        chart_layout = QVBoxLayout(chart_group)

        self.mp_canvas = MplCanvas(self, width=6, height=3.5, dpi=100)
        chart_layout.addWidget(self.mp_canvas)

        layout.addWidget(chart_group)

        return widget

    def perform_manual_phase_calculation(self):
        """执行手动指定平衡相计算（支持多个平衡相，按稳定性顺序析出）"""
        try:
            # 解析输入
            comp_str = self.mp_composition_input.text().strip()
            if not comp_str:
                QMessageBox.warning(self, "输入错误", "请输入合金成分！")
                return

            phase_str = self.mp_phase_input.text().strip()
            if not phase_str:
                QMessageBox.warning(self, "输入错误", "请输入平衡相！")
                return

            composition = parse_composition_static(comp_str)
            temperature = float(self.mp_temperature_input.text())
            extrap_model_name = self.mp_extrap_model_combo.currentText()
            activity_model = self.mp_activity_model_combo.currentText()

            # 解析多个平衡相（支持逗号或空格分隔）
            import re
            phases = [p.strip() for p in re.split(r'[,\s]+', phase_str) if p.strip()]
            if not phases:
                QMessageBox.warning(self, "输入错误", "请输入至少一个平衡相！")
                return

            # 解析多个吉布斯能（逗号分隔，'auto'或空表示自动）
            gibbs_str = self.mp_gibbs_input.text().strip()
            gibbs_energies = []
            if gibbs_str:
                gibbs_parts = [g.strip() for g in gibbs_str.split(',')]
                for g in gibbs_parts:
                    if g.lower() == 'auto' or g == '':
                        gibbs_energies.append(None)
                    else:
                        try:
                            gibbs_energies.append(float(g))
                        except ValueError:
                            gibbs_energies.append(None)
            # 补齐吉布斯能列表
            while len(gibbs_energies) < len(phases):
                gibbs_energies.append(None)

            # 获取外推模型函数
            extrap_func = getattr(self.binary_model, extrap_model_name)

            # 显示进度
            self.mp_progress_bar.setVisible(True)
            self.mp_calculate_button.setEnabled(False)

            # ========== 新的多相平衡计算逻辑 ==========
            # 归一化组成键为大写（解决大小写不匹配问题）
            composition_upper = {k.upper(): v for k, v in composition.items()}

            # 步骤1: 首先计算所有相的驱动力（使用原始组成）
            phase_stability_info = []
            for i, phase in enumerate(phases):
                gibbs_energy = gibbs_energies[i] if i < len(gibbs_energies) else None
                # 计算该相的驱动力
                driving_force = self._calculate_phase_driving_force(
                    composition_upper, phase, temperature, gibbs_energy,
                    extrap_func, extrap_model_name, activity_model
                )
                phase_stability_info.append({
                    'phase': phase,
                    'gibbs_energy': gibbs_energy,
                    'driving_force': driving_force,
                    'original_index': i
                })

            # 步骤2: 按稳定性排序（驱动力越正越稳定，优先析出）
            phase_stability_info.sort(key=lambda x: x['driving_force'], reverse=True)

            print(f"\n=== 相稳定性排序 ===")
            for info in phase_stability_info:
                stability = "可析出" if info['driving_force'] > 0 else "不析出"
                print(f"  {info['phase']}: 驱动力 = {info['driving_force']:.2f} J/mol ({stability})")

            # 步骤3: 按稳定性顺序依次析出，更新剩余组成
            all_results = []
            remaining_composition = composition_upper.copy()
            processed_phases = set()

            for info in phase_stability_info:
                phase = info['phase']
                gibbs_energy = info['gibbs_energy']

                # 检查剩余组成中是否还有足够的元素
                compound_comp = self._get_compound_composition(phase)
                if compound_comp:
                    # compound_comp 的键已经是大写，remaining_composition 也已归一化为大写
                    has_elements = all(
                        remaining_composition.get(el, 0) > 1e-10
                        for el in compound_comp
                    )
                    if not has_elements:
                        print(f"  {phase}: 剩余组成中缺少必要元素，跳过")
                        all_results.append({
                            'status': 'skipped',
                            'message': f'剩余组成中缺少形成 {phase} 所需元素',
                            'equilibrium_phase': {
                                'name': phase,
                                'type': 'compound',
                                'composition': compound_comp,
                                'mole_fraction': 0,
                                'mass_fraction': 0,
                                'gibbs_energy': gibbs_energy or 0,
                                'driving_force': info['driving_force'],
                                'is_stable': False
                            },
                            'matrix_phase': None
                        })
                        continue

                # 重新计算当前组成下的稳定性
                current_driving_force = self._calculate_phase_driving_force(
                    remaining_composition, phase, temperature, gibbs_energy,
                    extrap_func, extrap_model_name, activity_model
                )

                print(f"\n  计算 {phase} (当前驱动力: {current_driving_force:.2f} J/mol)")

                # 执行平衡计算
                result = self.manual_calculator.calculate_manual_equilibrium(
                    alloy_composition=remaining_composition,
                    equilibrium_phase=phase,
                    temperature=temperature,
                    compound_gibbs_energy=gibbs_energy,
                    extrapolation_func=extrap_func,
                    extrapolation_model_name=extrap_model_name,
                    activity_model=activity_model
                )

                # 添加原始驱动力信息（用于显示）
                if result.get('equilibrium_phase'):
                    result['equilibrium_phase']['original_driving_force'] = info['driving_force']

                all_results.append(result)
                processed_phases.add(phase)

                # 如果析出成功，更新剩余组成
                if result.get('status') == 'success':
                    matrix = result.get('matrix_phase')
                    if matrix and matrix.get('composition'):
                        # 考虑相分数来计算实际剩余组成
                        eq_phase = result.get('equilibrium_phase')
                        if eq_phase and eq_phase.get('mole_fraction', 0) > 0:
                            # 计算消耗后的剩余组成
                            phase_fraction = eq_phase['mole_fraction']
                            phase_comp = eq_phase.get('composition', {})

                            new_remaining = {}
                            for el, x in remaining_composition.items():
                                consumed = phase_fraction * phase_comp.get(el, 0)
                                new_remaining[el] = max(0, x - consumed)

                            # 归一化
                            total = sum(new_remaining.values())
                            if total > 1e-10:
                                remaining_composition = {k: v/total for k, v in new_remaining.items()}
                            else:
                                remaining_composition = {}

                            print(f"    析出 {phase}: {phase_fraction*100:.2f}%")
                            print(f"    剩余组成: {self._format_comp(remaining_composition)}")

            # 合并结果并显示
            combined_result = self._combine_phase_results(all_results, phases)
            self.display_manual_phase_results(combined_result, composition, phases, temperature)

        except ValueError as e:
            QMessageBox.warning(self, "输入错误", f"输入参数无效:\n{str(e)}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "计算错误", f"计算过程中发生错误:\n{str(e)}")
        finally:
            self.mp_progress_bar.setVisible(False)
            self.mp_calculate_button.setEnabled(True)

    def _calculate_phase_driving_force(self, composition, phase, temperature, gibbs_energy,
                                        extrap_func, extrap_model_name, activity_model):
        """
        计算相的热力学驱动力（ΔG > 0 表示可析出）

        注意：composition 的键应该已经归一化为大写
        """
        try:
            # 如果是溶体相，返回大正值（始终可以存在）
            if self.manual_calculator.is_solution_phase(phase):
                return 1000.0  # 溶体相始终稳定

            # 获取化合物组成（键为大写）
            compound_comp = self.manual_calculator.parse_compound_formula(phase)

            # 检查合金中是否含有所需元素
            # compound_comp 的键已经是大写，composition 的键也应该是大写
            for el in compound_comp:
                if el not in composition or composition[el] < 1e-10:
                    return float('-inf')  # 缺少元素，不可能形成（返回负无穷表示不稳定）

            # 估算吉布斯能
            if gibbs_energy is None:
                g_compound = self.manual_calculator._estimate_compound_gibbs_energy(
                    compound_comp, phase, temperature
                )
            else:
                g_compound = gibbs_energy

            # 调用稳定性检查方法计算驱动力
            is_stable, driving_force = self.manual_calculator._check_compound_stability(
                composition, compound_comp, phase, temperature,
                g_compound, extrap_func, extrap_model_name, activity_model
            )

            return driving_force

        except Exception as e:
            print(f"计算 {phase} 驱动力时出错: {e}")
            return float('-inf')  # 出错时返回负无穷（不稳定）

    def _get_compound_composition(self, phase):
        """获取化合物的组成"""
        try:
            if self.manual_calculator.is_solution_phase(phase):
                return None
            return self.manual_calculator.parse_compound_formula(phase)
        except:
            return None

    def _format_comp(self, comp):
        """格式化组成字符串"""
        if not comp:
            return "N/A"
        return ", ".join([f"{k}:{v:.4f}" for k, v in comp.items() if v > 1e-6])

    def _combine_phase_results(self, all_results, phases):
        """合并多个平衡相计算结果"""
        combined = {
            'status': 'success',
            'message': '',
            'equilibrium_phases': [],  # 多个平衡相
            'matrix_phase': None,
            'calculation_details': {}
        }

        stable_count = 0
        unstable_count = 0
        # 跳过的相不计入统计，也不显示在结果中

        # 创建一个从phase名称到原始索引的映射
        phase_to_index = {phase: i for i, phase in enumerate(phases)}

        for result in all_results:
            status = result.get('status')
            eq_phase = result.get('equilibrium_phase')

            # 获取相名称和对应的原始索引
            phase_name = eq_phase.get('name') if eq_phase else None
            original_index = phase_to_index.get(phase_name, -1) if phase_name else -1

            if status == 'success':
                # 相稳定且可以析出
                if eq_phase:
                    eq_phase['stability_status'] = 'stable'
                    combined['equilibrium_phases'].append(eq_phase)
                    stable_count += 1

                # 最后一个成功结果的基体相作为最终基体相
                if result.get('matrix_phase'):
                    combined['matrix_phase'] = result.get('matrix_phase')

                # 收集计算细节
                details = result.get('calculation_details', {})
                for key, value in details.items():
                    combined['calculation_details'][f"{phase_name}_{key}"] = value

            elif status == 'unstable':
                # 相热力学不稳定，不会析出
                unstable_count += 1
                if eq_phase:
                    eq_phase['stability_status'] = 'unstable'
                    combined['equilibrium_phases'].append(eq_phase)
                else:
                    combined['equilibrium_phases'].append({
                        'name': phase_name or f'Phase_{original_index}',
                        'type': 'compound',
                        'composition': {},
                        'mole_fraction': 0,
                        'mass_fraction': 0,
                        'gibbs_energy': 0,
                        'stability_status': 'unstable',
                        'is_stable': False,
                        'message': result.get('message', '热力学不稳定')
                    })

                # 关键修复：不稳定相不更新基体相分数
                # 只有当还没有任何成功的析出相时，才使用不稳定相的基体相作为初始值
                if combined['matrix_phase'] is None and result.get('matrix_phase'):
                    combined['matrix_phase'] = result.get('matrix_phase')

            elif status == 'skipped':
                # 因为元素被消耗而跳过的相，不在结果中显示
                # 只打印日志，不添加到 equilibrium_phases 列表
                print(f"  {phase_name}: 元素已被更稳定相消耗，跳过")
                pass

            else:
                # 其他错误，也不显示
                print(f"  {phase_name}: 计算出错 - {result.get('message', '未知错误')}")
                pass

        # 更新消息
        messages = []
        if stable_count > 0:
            messages.append(f'成功计算 {stable_count} 个平衡相')
        if unstable_count > 0:
            messages.append(f'{unstable_count} 个相热力学不稳定')

        if messages:
            combined['message'] = '，'.join(messages)
        else:
            combined['message'] = '基体相稳定，指定的析出相均不会析出'
            combined['matrix_stable'] = True  # 标记基体相稳定

        return combined

    def display_manual_phase_results(self, result, composition, phases, temperature):
        """显示手动指定平衡相计算结果（支持多个平衡相）"""
        # 显示文本结果
        phases_str = ', '.join(phases) if isinstance(phases, list) else phases
        text = f"=== 手动指定平衡相计算结果 ===\n\n"
        text += f"状态: {result.get('status', 'unknown')}\n"
        text += f"消息: {result.get('message', '')}\n"
        text += f"温度: {temperature:.2f} K\n"
        text += f"指定平衡相: {phases_str}\n"
        text += f"总合金组成: {composition}\n\n"

        # 多个平衡相
        eq_phases = result.get('equilibrium_phases', [])
        # 兼容旧格式（单个平衡相）
        if not eq_phases and result.get('equilibrium_phase'):
            eq_phases = [result.get('equilibrium_phase')]

        for i, eq_phase in enumerate(eq_phases, 1):
            if eq_phase:
                text += f"--- 平衡相 {i}: {eq_phase['name']} ---\n"
                text += f"相类型: {eq_phase['type']}\n"

                # 显示稳定性状态
                stability_status = eq_phase.get('stability_status', 'unknown')

                # 显示原始驱动力（初始组成下的稳定性）
                original_df = eq_phase.get('original_driving_force')
                current_df = eq_phase.get('driving_force')

                if stability_status == 'unstable':
                    text += f"⚠ 稳定性: 热力学不稳定，不会析出\n"
                    if current_df is not None:
                        text += f"驱动力: {current_df:.2f} J/mol (负值表示不析出)\n"
                    text += f"摩尔分数: 0.0000 (0.00%)\n\n"
                elif eq_phase.get('error'):
                    text += f"错误: {eq_phase['error']}\n\n"
                else:
                    if stability_status == 'stable':
                        text += f"✓ 稳定性: 热力学稳定，可以析出\n"
                        if original_df is not None:
                            text += f"初始驱动力: {original_df:.2f} J/mol (正值表示可析出)\n"
                        elif current_df is not None:
                            text += f"驱动力: {current_df:.2f} J/mol (正值表示可析出)\n"
                    text += f"摩尔分数: {eq_phase['mole_fraction']:.6f} ({eq_phase['mole_fraction']*100:.2f}%)\n"
                    text += f"质量分数: {eq_phase['mass_fraction']:.6f} ({eq_phase['mass_fraction']*100:.2f}%)\n"
                    text += f"吉布斯能: {eq_phase['gibbs_energy']:.2f} J/mol\n\n"

        # 基体相信息
        matrix_phase = result.get('matrix_phase')
        matrix_stable = result.get('matrix_stable', False)

        if matrix_stable and matrix_phase:
            # 基体相稳定，没有析出相
            text += f"--- 基体相信息 (稳定) ---\n"
            text += f"✓ 基体相稳定，所有指定析出相均不会析出\n"
            text += f"相名称: {matrix_phase.get('name', 'Matrix')}\n"
            text += f"摩尔分数: 1.0000 (100.00%)\n"
            text += f"组成: {composition}\n"
        elif matrix_phase and matrix_phase.get('composition'):
            text += f"--- 基体相信息 ---\n"
            text += f"相名称: {matrix_phase['name']}\n"
            text += f"摩尔分数: {matrix_phase['mole_fraction']:.6f} ({matrix_phase['mole_fraction']*100:.2f}%)\n"

        self.mp_results_text.setPlainText(text)

        # 填充结果表格
        self.fill_manual_phase_table(result)

        # 填充组成表格
        self.fill_manual_comp_table(result)

        # 绘制饼图
        self.plot_manual_phase_chart(result)

    def fill_manual_phase_table(self, result):
        """填充手动指定平衡相结果表格（支持多个平衡相）"""
        self.mp_results_table.setRowCount(0)

        row = 0

        # 多个平衡相
        eq_phases = result.get('equilibrium_phases', [])
        # 兼容旧格式
        if not eq_phases and result.get('equilibrium_phase'):
            eq_phases = [result.get('equilibrium_phase')]

        for eq_phase in eq_phases:
            if eq_phase:
                stability_status = eq_phase.get('stability_status', 'unknown')

                # 跳过错误的相
                if stability_status == 'error' or eq_phase.get('error'):
                    continue

                self.mp_results_table.insertRow(row)

                # 根据稳定性状态显示不同内容
                if stability_status == 'unstable':
                    # 不稳定相显示为0
                    self.mp_results_table.setItem(row, 0, QTableWidgetItem(f"{eq_phase['name']} (不稳定)"))
                    self.mp_results_table.setItem(row, 1, QTableWidgetItem(eq_phase['type']))
                    self.mp_results_table.setItem(row, 2, QTableWidgetItem("0.0000"))
                    self.mp_results_table.setItem(row, 3, QTableWidgetItem("0.0000"))
                    g_energy = eq_phase.get('gibbs_energy', 0)
                    self.mp_results_table.setItem(row, 4, QTableWidgetItem(f"{g_energy:.2f}" if g_energy else "-"))
                else:
                    # 稳定相正常显示
                    self.mp_results_table.setItem(row, 0, QTableWidgetItem(eq_phase['name']))
                    self.mp_results_table.setItem(row, 1, QTableWidgetItem(eq_phase['type']))
                    self.mp_results_table.setItem(row, 2, QTableWidgetItem(f"{eq_phase['mole_fraction']*100:.4f}"))
                    self.mp_results_table.setItem(row, 3, QTableWidgetItem(f"{eq_phase['mass_fraction']*100:.4f}"))
                    self.mp_results_table.setItem(row, 4, QTableWidgetItem(f"{eq_phase['gibbs_energy']:.2f}"))
                row += 1

        # 基体相信息
        matrix_phase = result.get('matrix_phase')
        matrix_stable = result.get('matrix_stable', False)

        if matrix_stable and matrix_phase:
            # 基体相稳定，100%基体
            self.mp_results_table.insertRow(row)
            self.mp_results_table.setItem(row, 0, QTableWidgetItem(f"{matrix_phase.get('name', 'Matrix')} (稳定)"))
            self.mp_results_table.setItem(row, 1, QTableWidgetItem("matrix"))
            self.mp_results_table.setItem(row, 2, QTableWidgetItem("100.0000"))
            self.mp_results_table.setItem(row, 3, QTableWidgetItem("100.0000"))
            self.mp_results_table.setItem(row, 4, QTableWidgetItem("-"))
            row += 1
        elif matrix_phase and matrix_phase.get('composition'):
            self.mp_results_table.insertRow(row)
            self.mp_results_table.setItem(row, 0, QTableWidgetItem(matrix_phase['name']))
            self.mp_results_table.setItem(row, 1, QTableWidgetItem("matrix"))
            self.mp_results_table.setItem(row, 2, QTableWidgetItem(f"{matrix_phase['mole_fraction']*100:.4f}"))
            self.mp_results_table.setItem(row, 3, QTableWidgetItem("-"))
            self.mp_results_table.setItem(row, 4, QTableWidgetItem("-"))
            row += 1

        self.mp_results_table.resizeColumnsToContents()

    def fill_manual_comp_table(self, result):
        """填充相组成详细表格（支持多个平衡相）"""
        self.mp_comp_table.setRowCount(0)

        # 原子质量
        atomic_masses = {
            'FE': 55.845, 'C': 12.011, 'SI': 28.085, 'MN': 54.938,
            'CR': 51.996, 'NI': 58.693, 'MO': 95.94, 'CU': 63.546,
            'AL': 26.982, 'TI': 47.867, 'V': 50.942, 'W': 183.84,
            'CO': 58.933, 'N': 14.007, 'P': 30.974, 'S': 32.065,
            'NB': 92.906, 'ZR': 91.224, 'B': 10.81, 'O': 15.999,
            'MG': 24.305, 'ZN': 65.38
        }

        row = 0

        # 多个平衡相组成
        eq_phases = result.get('equilibrium_phases', [])
        # 兼容旧格式
        if not eq_phases and result.get('equilibrium_phase'):
            eq_phases = [result.get('equilibrium_phase')]

        for eq_phase in eq_phases:
            # 跳过不稳定相和错误相（它们不会形成，不显示组成）
            stability_status = eq_phase.get('stability_status', 'unknown') if eq_phase else 'error'
            if stability_status in ['unstable', 'error'] or eq_phase.get('error'):
                continue

            if eq_phase and eq_phase.get('composition'):
                comp = eq_phase['composition']
                total_mass = sum(comp.get(el, 0) * atomic_masses.get(el.upper(), 50)
                               for el in comp)

                for elem, mole_frac in comp.items():
                    self.mp_comp_table.insertRow(row)
                    mass = mole_frac * atomic_masses.get(elem.upper(), 50)
                    mass_frac = mass / total_mass if total_mass > 0 else 0

                    self.mp_comp_table.setItem(row, 0, QTableWidgetItem(eq_phase['name']))
                    self.mp_comp_table.setItem(row, 1, QTableWidgetItem(elem))
                    self.mp_comp_table.setItem(row, 2, QTableWidgetItem(f"{mole_frac:.6f}"))
                    self.mp_comp_table.setItem(row, 3, QTableWidgetItem(f"{mass_frac:.6f}"))
                    row += 1

        # 基体相组成
        matrix_phase = result.get('matrix_phase')
        if matrix_phase and matrix_phase.get('composition'):
            comp = matrix_phase['composition']
            total_mass = sum(comp.get(el, 0) * atomic_masses.get(el.upper(), 50)
                           for el in comp)

            for elem, mole_frac in comp.items():
                if mole_frac < 1e-6:
                    continue
                self.mp_comp_table.insertRow(row)
                mass = mole_frac * atomic_masses.get(elem.upper(), 50)
                mass_frac = mass / total_mass if total_mass > 0 else 0

                self.mp_comp_table.setItem(row, 0, QTableWidgetItem(matrix_phase['name']))
                self.mp_comp_table.setItem(row, 1, QTableWidgetItem(elem))
                self.mp_comp_table.setItem(row, 2, QTableWidgetItem(f"{mole_frac:.6f}"))
                self.mp_comp_table.setItem(row, 3, QTableWidgetItem(f"{mass_frac:.6f}"))
                row += 1

        self.mp_comp_table.resizeColumnsToContents()

    def plot_manual_phase_chart(self, result):
        """绘制手动指定平衡相饼图（支持多个平衡相）"""
        self.mp_canvas.axes.clear()

        labels = []
        fractions = []

        # 多个平衡相
        eq_phases = result.get('equilibrium_phases', [])
        # 兼容旧格式
        if not eq_phases and result.get('equilibrium_phase'):
            eq_phases = [result.get('equilibrium_phase')]

        for eq_phase in eq_phases:
            # 跳过不稳定相和错误相（它们的mole_fraction为0）
            stability_status = eq_phase.get('stability_status', 'unknown') if eq_phase else 'error'
            if stability_status in ['unstable', 'error'] or eq_phase.get('error'):
                continue

            if eq_phase and eq_phase.get('mole_fraction', 0) > 0.001:
                labels.append(eq_phase['name'])
                fractions.append(eq_phase['mole_fraction'])

        # 基体相
        matrix_phase = result.get('matrix_phase')
        matrix_stable = result.get('matrix_stable', False)

        if matrix_stable and matrix_phase:
            # 基体相稳定，100%基体
            labels.append(f"{matrix_phase.get('name', 'Matrix')} (稳定)")
            fractions.append(1.0)
        elif matrix_phase and matrix_phase.get('mole_fraction', 0) > 0.001:
            labels.append(matrix_phase['name'])
            fractions.append(matrix_phase['mole_fraction'])

        if not labels or sum(fractions) < 0.001:
            self.mp_canvas.axes.text(0.5, 0.5, '无有效相分数数据\n(指定相可能热力学不稳定)',
                                     ha='center', va='center', fontsize=12)
            self.mp_canvas.draw()
            return

        # 定义颜色
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#95E1D3', '#F38181', '#AA96DA']

        # 绘制饼图
        self.mp_canvas.axes.pie(
            fractions, labels=labels, autopct='%1.2f%%',
            startangle=90, colors=colors[:len(labels)]
        )
        self.mp_canvas.axes.set_title('相分数分布', fontsize=14, fontweight='bold')

        self.mp_canvas.draw()

    def clear_manual_phase_results(self):
        """清除手动指定平衡相结果"""
        self.mp_results_text.clear()
        self.mp_results_table.setRowCount(0)
        self.mp_comp_table.setRowCount(0)
        self.mp_canvas.axes.clear()
        self.mp_canvas.draw()
