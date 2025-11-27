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
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils import parse_composition_static
from calculations.phase_equilibrium_calculator import PhaseEquilibriumCalculator
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

        # 合金成分
        input_layout.addWidget(QLabel("合金成分:"), row, 0, Qt.AlignRight)
        self.sp_composition_input = QLineEdit("Fe0.70C0.03Si0.27")
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

        # 添加说明标签
        note_label = QLabel("注: 平衡相数由算法自动确定")
        note_label.setStyleSheet("color: #666; font-style: italic; font-size: 10pt;")
        input_layout.addWidget(note_label, row, 0, 1, 2, Qt.AlignCenter)
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

        # 结果文本（增加高度以显示完整的相律验证）
        results_group = QGroupBox("计算结果")
        results_layout = QVBoxLayout(results_group)

        self.sp_results_text = QTextEdit()
        self.sp_results_text.setReadOnly(True)
        self.sp_results_text.setMinimumHeight(350)  # 从200增加到350，确保相律验证可见
        self.sp_results_text.setMaximumHeight(450)  # 设置最大高度
        results_layout.addWidget(self.sp_results_text)

        layout.addWidget(results_group)

        # 结果表格（增加高度）
        table_group = QGroupBox("相平衡详细信息")
        table_layout = QVBoxLayout(table_group)

        self.sp_results_table = QTableWidget()
        self.sp_results_table.setColumnCount(5)
        self.sp_results_table.setHorizontalHeaderLabels([
            "相名称", "相分数 (%)", "元素", "摩尔分数", "质量分数"
        ])
        self.sp_results_table.setMinimumHeight(300)  # 增加最小高度

        # 设置列宽以优化显示
        self.sp_results_table.setColumnWidth(0, 120)  # 相名称
        self.sp_results_table.setColumnWidth(1, 120)  # 相分数 (%)
        self.sp_results_table.setColumnWidth(2, 80)   # 元素
        self.sp_results_table.setColumnWidth(3, 120)  # 摩尔分数
        self.sp_results_table.setColumnWidth(4, 120)  # 质量分数

        # 设置表格样式
        self.sp_results_table.setAlternatingRowColors(True)  # 交替行颜色
        self.sp_results_table.horizontalHeader().setStretchLastSection(True)  # 最后一列拉伸

        table_layout.addWidget(self.sp_results_table)

        layout.addWidget(table_group)

        # 饼图（增加高度）
        chart_group = QGroupBox("相分数可视化")
        chart_layout = QVBoxLayout(chart_group)

        self.sp_canvas = MplCanvas(self, width=8, height=6, dpi=100)  # 从6x4增加到8x6
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

        # 合金成分
        input_layout.addWidget(QLabel("合金成分:"), row, 0, Qt.AlignRight)
        self.tv_composition_input = QLineEdit("Fe0.70C0.03Si0.27")
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

        # 基础合金成分
        input_layout.addWidget(QLabel("基础合金:"), row, 0, Qt.AlignRight)
        self.cv_base_composition_input = QLineEdit("Fe0.97Si0.03")
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
            self.sp_progress_bar.setRange(0, 0)  # 不确定进度
            self.sp_calculate_button.setEnabled(False)

            # 创建计算线程
            self.calc_thread = CalculationThread(
                self.calculator.calculate_phase_equilibrium_gui_compatible,
                composition, temperature, extrap_func,
                extrap_model_name, activity_model
            )

            # 连接信号
            self.calc_thread.finished.connect(self.on_single_point_calculation_finished)
            self.calc_thread.error.connect(self.on_calculation_error)

            # 启动线程
            self.calc_thread.start()

        except ValueError as e:
            QMessageBox.warning(self, "输入错误", f"输入参数无效:\n{str(e)}")
            self.sp_progress_bar.setVisible(False)
            self.sp_calculate_button.setEnabled(True)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            QMessageBox.critical(
                self, "计算错误",
                f"启动计算失败:\n{str(e)}\n\n详细信息:\n{error_details}"
            )
            self.sp_progress_bar.setVisible(False)
            self.sp_calculate_button.setEnabled(True)

    def on_single_point_calculation_finished(self, result):
        """单点计算完成回调"""
        try:
            # 隐藏进度条
            self.sp_progress_bar.setVisible(False)
            self.sp_calculate_button.setEnabled(True)

            # 调试：检查返回类型
            if not isinstance(result, dict):
                QMessageBox.critical(
                    self, "计算错误",
                    f"计算器返回了错误的数据类型: {type(result).__name__}\n"
                    f"期望: dict\n"
                    f"这可能是由于代码缓存问题导致。请重启应用程序。"
                )
                return

            # 显示结果
            self.display_single_point_results(result)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            QMessageBox.critical(
                self, "显示错误",
                f"显示结果时发生错误:\n{str(e)}\n\n详细信息:\n{error_details}"
            )
            self.sp_progress_bar.setVisible(False)
            self.sp_calculate_button.setEnabled(True)

    def on_calculation_error(self, error_msg):
        """计算错误回调"""
        QMessageBox.critical(self, "计算错误", f"计算过程中发生错误:\n{error_msg}")
        self.sp_progress_bar.setVisible(False)
        self.sp_calculate_button.setEnabled(True)
        if hasattr(self, 'tv_progress_bar'):
            self.tv_progress_bar.setVisible(False)
            self.tv_calculate_button.setEnabled(True)
        if hasattr(self, 'cv_progress_bar'):
            self.cv_progress_bar.setVisible(False)
            self.cv_calculate_button.setEnabled(True)

    def display_single_point_results(self, result):
        """显示单点计算结果"""
        # 类型检查
        if not isinstance(result, dict):
            QMessageBox.critical(
                self, "数据错误",
                f"计算结果格式错误：期望字典类型，实际得到 {type(result).__name__} 类型。\n"
                f"请重启应用程序并重试。"
            )
            return

        # 显示文本结果
        text = f"=== 相平衡计算结果（递归相分离算法）===\n\n"
        text += f"状态: {result.get('status', 'unknown')}\n"
        text += f"温度: {result.get('temperature', 0):.2f} K\n"
        text += f"总组成: {result.get('total_composition', {})}\n"
        text += f"消息: {result.get('message', '')}\n\n"

        if 'phases' in result and result['phases']:
            # 计算组分数和相数
            total_comp = result.get('total_composition', {})
            num_components = len(total_comp)  # 组分数 C

            # 统计独立相数（相同名称的相只算一次）
            unique_phases = set(phase.name for phase in result['phases'])
            num_phases = len(unique_phases)  # 相数 P

            text += f"自动确定的平衡相数: {num_phases}\n"
            text += f"组分数 (C): {num_components}\n"

            # Gibbs相律验证 (给定温度和压力，F = C - P)
            degrees_of_freedom = num_components - num_phases
            text += f"\n--- Gibbs相律验证 ---\n"
            text += f"自由度 (F) = C - P = {num_components} - {num_phases} = {degrees_of_freedom}\n"

            if degrees_of_freedom >= 0:
                text += f"✓ 满足Gibbs相律 (F ≥ 0)\n"
                if degrees_of_freedom == 0:
                    text += f"  → 无变式系统：温度和组成完全确定相平衡\n"
                elif degrees_of_freedom == 1:
                    text += f"  → 单变式系统：可改变温度或一个组分含量\n"
                else:
                    text += f"  → 多变式系统：可改变 {degrees_of_freedom} 个变量\n"
            else:
                text += f"⚠ 警告：F < 0，可能存在计算问题或相数过多\n"

            text += f"\n详细相信息:\n"
            for i, phase in enumerate(result['phases'], 1):
                text += f"\n相 {i}: {phase.name}\n"
                text += f"  相分数: {phase.fraction:.4f} ({phase.fraction*100:.2f}%)\n"
                text += f"  组成: {phase.composition}\n"

        self.sp_results_text.setPlainText(text)

        # 填充表格
        self.fill_single_point_table(result)

        # 绘制饼图
        self.plot_single_point_chart(result)

    def fill_single_point_table(self, result):
        """填充单点计算表格"""
        self.sp_results_table.setRowCount(0)

        if not isinstance(result, dict):
            return

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
                # 元素
                self.sp_results_table.setItem(row, 2, QTableWidgetItem(elem))
                # 摩尔分数
                self.sp_results_table.setItem(row, 3, QTableWidgetItem(f"{mole_frac:.6f}"))
                # 质量分数
                self.sp_results_table.setItem(row, 4, QTableWidgetItem(f"{mass_frac:.6f}"))

                row += 1

        # 不再需要自动调整列宽，因为我们已经手动设置了固定列宽
        # self.sp_results_table.resizeColumnsToContents()

    def plot_single_point_chart(self, result):
        """绘制单点计算饼图"""
        self.sp_canvas.axes.clear()

        if not isinstance(result, dict):
            self.sp_canvas.draw()
            return

        if 'phases' not in result or not result['phases']:
            self.sp_canvas.draw()
            return

        # 提取相名称和分数
        labels = [phase.name for phase in result['phases']]
        fractions = [phase.fraction for phase in result['phases']]

        # 定义更丰富的颜色方案
        color_scheme = {
            'LIQUID': '#FF6B6B',
            'BCC_A2': '#4ECDC4',
            'FCC_A1': '#45B7D1',
            'HCP_A3': '#FFA07A',
            'GRAPHITE': '#95E1D3',
            'DIAMOND_A4': '#F38181',
        }
        colors = [color_scheme.get(label, '#CCCCCC') for label in labels]

        # 突出显示最大的相
        max_index = fractions.index(max(fractions))
        explode = [0.05 if i == max_index else 0 for i in range(len(labels))]

        # 绘制饼图
        wedges, texts, autotexts = self.sp_canvas.axes.pie(
            fractions,
            labels=labels,
            autopct='%1.1f%%',
            startangle=90,
            colors=colors,
            explode=explode,
            shadow=True,
            textprops={'fontsize': 11, 'weight': 'bold'},
            wedgeprops={'edgecolor': 'white', 'linewidth': 2}
        )

        # 优化百分比文字样式
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(10)
            autotext.set_weight('bold')

        # 设置标题
        self.sp_canvas.axes.set_title(
            f'相分数分布 (T={result.get("temperature", 0):.0f}K)',
            fontsize=14,
            weight='bold',
            pad=20
        )

        # 确保饼图是圆形
        self.sp_canvas.axes.axis('equal')

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

            # 保存组成用于显示
            self.tv_current_composition = composition

            # 创建计算线程
            self.calc_thread = CalculationThread(
                self.calculator.calculate_phase_equilibrium_vs_temperature,
                composition, T_min, T_max, n_points,
                extrap_func, extrap_model_name, activity_model,
                progress_callback=self.update_tv_progress
            )

            # 连接信号
            self.calc_thread.finished.connect(self.on_temperature_variation_finished)
            self.calc_thread.error.connect(self.on_calculation_error)

            # 启动线程
            self.calc_thread.start()

        except ValueError as e:
            QMessageBox.warning(self, "输入错误", f"输入参数无效:\n{str(e)}")
            self.tv_progress_bar.setVisible(False)
            self.tv_calculate_button.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "计算错误", f"启动计算失败:\n{str(e)}")
            self.tv_progress_bar.setVisible(False)
            self.tv_calculate_button.setEnabled(True)

    def on_temperature_variation_finished(self, result):
        """温度变化计算完成回调"""
        self.tv_progress_bar.setVisible(False)
        self.tv_calculate_button.setEnabled(True)
        self.display_temperature_variation_results(result, self.tv_current_composition)

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

            # 保存基础组成用于显示
            self.cv_current_base_composition = base_composition

            # 创建计算线程
            self.calc_thread = CalculationThread(
                self.calculator.calculate_phase_equilibrium_vs_composition,
                base_composition, variable_element, x_min, x_max, temperature,
                n_points, extrap_func, extrap_model_name, activity_model,
                progress_callback=self.update_cv_progress
            )

            # 连接信号
            self.calc_thread.finished.connect(self.on_composition_variation_finished)
            self.calc_thread.error.connect(self.on_calculation_error)

            # 启动线程
            self.calc_thread.start()

        except ValueError as e:
            QMessageBox.warning(self, "输入错误", f"输入参数无效:\n{str(e)}")
            self.cv_progress_bar.setVisible(False)
            self.cv_calculate_button.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "计算错误", f"启动计算失败:\n{str(e)}")
            self.cv_progress_bar.setVisible(False)
            self.cv_calculate_button.setEnabled(True)

    def on_composition_variation_finished(self, result):
        """组分变化计算完成回调"""
        self.cv_progress_bar.setVisible(False)
        self.cv_calculate_button.setEnabled(True)
        self.display_composition_variation_results(result, self.cv_current_base_composition)

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
