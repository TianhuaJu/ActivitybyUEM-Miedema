"""
Solubility Widget
==================
溶解度计算与可视化GUI组件

功能:
- 计算溶质在合金中的溶解度
- 绘制溶解度随基础合金成分变化的曲线
- 支持液相和固相溶解度计算

"""
import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton,
                             QSplitter, QFrame, QGroupBox, QTextEdit,
                             QMessageBox, QRadioButton, QButtonGroup, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils import parse_composition_static
from calculations.phase_diagram import PhaseDiagram


class SolubilityWorker(QThread):
    """溶解度计算工作线程"""

    # 定义信号
    progress_updated = pyqtSignal(int, int)  # (current, total)
    calculation_finished = pyqtSignal(dict)  # 完成信号，传递结果字典
    error_occurred = pyqtSignal(str)  # 错误信号

    def __init__(self, calc_type, params, phase_calc):
        """
        初始化工作线程

        Args:
            calc_type: 计算类型 ('single', 'curve', 'temperature')
            params: 计算参数字典
            phase_calc: PhaseDiagram 计算对象
        """
        super().__init__()
        self.calc_type = calc_type
        self.params = params
        self.phase_calc = phase_calc
        self._is_cancelled = False

    def cancel(self):
        """取消计算"""
        self._is_cancelled = True

    def run(self):
        """执行计算任务"""
        try:
            if self.calc_type == 'single':
                self._run_single_calculation()
            elif self.calc_type == 'curve':
                self._run_curve_calculation()
            elif self.calc_type == 'temperature':
                self._run_temperature_calculation()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _run_single_calculation(self):
        """执行单点溶解度计算"""
        result = self.phase_calc.calculate_solubility(
            base_alloy_composition=self.params['base_composition'],
            solute_element=self.params['solute'],
            solution_phase=self.params['tdb_solution_phase'],
            
            temperature=self.params['temperature'],
            extrapolation_func=self.params['extrap_func'],
            extrapolation_model_name=self.params['extrap_model_name'],
            activity_model=self.params['activity_model']
        )

        # 发送完成信号
        self.calculation_finished.emit({
            'type': 'single',
            'result': result,
            'params': self.params
        })

    def _run_curve_calculation(self):
        """执行浓度曲线计算（使用全局进程池 - 避免重复创建进程）"""
        import numpy as np
        from calculations.parallel_solubility import compute_concentration_point
        from calculations.global_process_pool import get_global_process_pool
        import threading

        x_values = np.linspace(
            self.params['x_min'],
            self.params['x_max'],
            self.params['n_points']
        )

        # 初始化结果列表
        n_points = len(x_values)
        solubility_values = [0.0] * n_points
        ideal_solubility_values = [0.0] * n_points
        results_list = [None] * n_points
        ideal_results_list = [None] * n_points

        completed_count = [0]
        lock = threading.Lock()
        all_done = threading.Event()

        # 准备参数
        task_params = []
        for i, x_val in enumerate(x_values):
            param_dict = {
                'x_var': float(x_val),
                'index': i,
                'fixed_base_norm': dict(self.params['fixed_base_norm']),
                'variable_comp': str(self.params['variable_comp']),
                'solute': str(self.params['solute']),
                'tdb_solution_phase': str(self.params['tdb_solution_phase']),
                'temperature': float(self.params['temperature']),
                'extrap_model_name': str(self.params['extrap_model_name']),
                'activity_model': str(self.params['activity_model'])
            }
            task_params.append(param_dict)

        # 回调函数
        def task_done_callback(future):
            if self._is_cancelled:
                return

            try:
                index, sol_value, ideal_sol_value, result, ideal_result = future.result()

                with lock:
                    solubility_values[index] = sol_value
                    ideal_solubility_values[index] = ideal_sol_value
                    results_list[index] = result
                    ideal_results_list[index] = ideal_result
                    completed_count[0] += 1
                    current = completed_count[0]

                self.progress_updated.emit(current, n_points)

                if current >= n_points:
                    all_done.set()

            except Exception as e:
                print(f"Task error: {e}")
                with lock:
                    completed_count[0] += 1
                    current = completed_count[0]
                self.progress_updated.emit(current, n_points)
                if current >= n_points:
                    all_done.set()

        # 使用全局进程池（复用，不重新创建！）
        pool = get_global_process_pool()

        # 提交所有任务
        for params in task_params:
            if self._is_cancelled:
                return
            future = pool.submit(compute_concentration_point, params)
            future.add_done_callback(task_done_callback)

        # 等待完成
        all_done.wait()

        # 发送完成信号
        self.calculation_finished.emit({
            'type': 'curve',
            'x_values': x_values,
            'solubility_values': solubility_values,
            'ideal_solubility_values': ideal_solubility_values,
            'results_list': results_list,
            'ideal_results_list': ideal_results_list,
            'params': self.params
        })

    def _run_temperature_calculation(self):
        """执行温度曲线计算（使用全局进程池 - 避免重复创建进程）"""
        import numpy as np
        from calculations.parallel_solubility import compute_temperature_point
        from calculations.global_process_pool import get_global_process_pool
        import threading

        t_values = np.linspace(
            self.params['t_start'],
            self.params['t_end'],
            self.params['n_points']
        )

        # 初始化结果列表
        n_points = len(t_values)
        solubility_values = [0.0] * n_points
        ideal_solubility_values = [0.0] * n_points
        results_list = [None] * n_points
        ideal_results_list = [None] * n_points

        completed_count = [0]
        lock = threading.Lock()
        all_done = threading.Event()

        # 准备参数
        task_params = []
        for i, t_val in enumerate(t_values):
            param_dict = {
                't_curr': float(t_val),
                'index': i,
                'base_composition': dict(self.params['base_composition']),
                'solute': str(self.params['solute']),
                'tdb_solution_phase': str(self.params['tdb_solution_phase']),
                'extrap_model_name': str(self.params['extrap_model_name']),
                'activity_model': str(self.params['activity_model'])
            }
            task_params.append(param_dict)

        # 回调函数
        def task_done_callback(future):
            if self._is_cancelled:
                return

            try:
                index, sol_value, ideal_sol_value, result, ideal_result = future.result()

                with lock:
                    solubility_values[index] = sol_value
                    ideal_solubility_values[index] = ideal_sol_value
                    results_list[index] = result
                    ideal_results_list[index] = ideal_result
                    completed_count[0] += 1
                    current = completed_count[0]

                self.progress_updated.emit(current, n_points)

                if current >= n_points:
                    all_done.set()

            except Exception as e:
                print(f"Task error: {e}")
                with lock:
                    completed_count[0] += 1
                    current = completed_count[0]
                self.progress_updated.emit(current, n_points)
                if current >= n_points:
                    all_done.set()

        # 使用全局进程池（复用，不重新创建！）
        pool = get_global_process_pool()

        # 提交所有任务
        for params in task_params:
            if self._is_cancelled:
                return
            future = pool.submit(compute_temperature_point, params)
            future.add_done_callback(task_done_callback)

        # 等待完成
        all_done.wait()

        # 发送完成信号
        self.calculation_finished.emit({
            'type': 'temperature',
            't_values': t_values,
            'solubility_values': solubility_values,
            'ideal_solubility_values': ideal_solubility_values,
            'results_list': results_list,
            'ideal_results_list': ideal_results_list,
            'params': self.params
        })


class MplCanvas(FigureCanvas):
    """Matplotlib画布类"""

    def __init__(self, parent=None, width=7, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)


class SolubilityWidget(QWidget):
    """溶解度计算与可视化组件"""

    def __init__(self):
        super().__init__()

        self.phase_calc = PhaseDiagram()
        self.calculation_count = 0  # 计算批次计数器
        self.worker = None  # 工作线程
        self.setup_ui()

    @staticmethod
    def simplify_phase_name(phase_name):
        """
        简化相名称显示
        例如: FCC_A1 -> FCC, BCC_A2 -> BCC, HCP_A3 -> HCP

        Args:
            phase_name: 原始相名称

        Returns:
            简化后的相名称
        """
        if not phase_name or phase_name == 'Unknown':
            return phase_name

        # 常见相名称简化规则
        simplification_rules = {
            'FCC_A1': 'FCC',
            'BCC_A2': 'BCC',
            'HCP_A3': 'HCP',
            'LIQUID': 'LIQUID',
            'GRAPHITE': 'GRAPHITE',
            'DIAMOND': 'DIAMOND',
        }

        # 直接匹配
        if phase_name in simplification_rules:
            return simplification_rules[phase_name]

        # 通用规则：如果包含下划线，去掉下划线及之后的部分
        # 例如：CEMENTITE_D011 -> CEMENTITE
        if '_' in phase_name:
            return phase_name.split('_')[0]

        # 没有匹配规则，返回原名称
        return phase_name

    @staticmethod
    def truncate_text(text, max_length=30):
        """
        截断文本，超过最大长度时添加省略号

        Args:
            text: 要截断的文本
            max_length: 最大长度（默认30字符）

        Returns:
            截断后的文本
        """
        if not text:
            return text
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."

    @staticmethod
    def format_alloy_composition(composition_dict):
        """
        格式化合金成分为显示字符串，包含每个元素的摩尔分数
        例如: {'Fe': 0.95, 'Si': 0.05} -> 'Fe0.95Si0.05'

        Args:
            composition_dict: 成分字典 {元素: 摩尔分数}

        Returns:
            格式化的成分字符串
        """
        if not composition_dict:
            return ""

        # 按元素符号排序，确保显示一致性
        sorted_items = sorted(composition_dict.items(), key=lambda x: x[0])

        # 格式化为 Element0.xx 的形式
        parts = []
        for elem, fraction in sorted_items:
            # 根据数值大小选择合适的小数位数
            if fraction >= 0.1:
                parts.append(f"{elem}{fraction:.2f}")
            elif fraction >= 0.01:
                parts.append(f"{elem}{fraction:.3f}")
            else:
                parts.append(f"{elem}{fraction:.4f}")

        return "".join(parts)

    def setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout(self)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧输入面板
        left_widget = self.create_input_panel()

        # 右侧结果面板
        right_widget = self.create_results_panel()

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 800])

    def create_input_panel(self):
        """创建输入面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 计算模式选择
        mode_group = QGroupBox("计算模式")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_button_group = QButtonGroup()

        self.mode_single = QRadioButton("单点溶解度计算")
        self.mode_curve = QRadioButton("溶解度-浓度曲线")
        self.mode_temp_curve = QRadioButton("溶解度-温度曲线")

        self.mode_button_group.addButton(self.mode_single, 1)
        self.mode_button_group.addButton(self.mode_curve, 2)
        self.mode_button_group.addButton(self.mode_temp_curve, 3)

        self.mode_single.setChecked(True)
        self.mode_single.toggled.connect(self.on_mode_changed)
        self.mode_curve.toggled.connect(self.on_mode_changed)
        self.mode_temp_curve.toggled.connect(self.on_mode_changed)

        mode_layout.addWidget(self.mode_single)
        mode_layout.addWidget(self.mode_curve)
        mode_layout.addWidget(self.mode_temp_curve)

        layout.addWidget(mode_group)

        # 模型参数分组
        model_group = QGroupBox("计算模型")
        model_layout = QGridLayout(model_group)
        model_layout.setSpacing(15)
        model_layout.setContentsMargins(20, 25, 20, 20)

        row = 0

        # 外推模型
        model_layout.addWidget(QLabel("外推模型:"), row, 0, Qt.AlignRight)
        self.extrap_model_combo = QComboBox()
        self.extrap_model_combo.addItems([
            "UEM1", "UEM2", "UEM2-Adv", "GSM",
            "Muggianu", "Toop-Muggianu", "Toop-Kohler"
        ])
        model_layout.addWidget(self.extrap_model_combo, row, 1)
        row += 1

        # 活度模型
        model_layout.addWidget(QLabel("活度模型:"), row, 0, Qt.AlignRight)
        self.activity_model_combo = QComboBox()
        self.activity_model_combo.addItems(["Wagner", "Darken", "Elliott"])
        model_layout.addWidget(self.activity_model_combo, row, 1)

        layout.addWidget(model_group)

        # 输入参数分组
        self.input_group = QGroupBox("输入参数")
        self.input_layout = QGridLayout(self.input_group)
        self.input_layout.setSpacing(15)
        self.input_layout.setContentsMargins(20, 25, 20, 20)

        self.create_input_fields()

        layout.addWidget(self.input_group)

        # 计算按钮
        button_layout = QHBoxLayout()
        self.calculate_button = QPushButton("计算")
        self.calculate_button.setMinimumHeight(40)
        self.calculate_button.clicked.connect(self.perform_calculation)
        button_layout.addWidget(self.calculate_button)

        self.cancel_button = QPushButton("取消计算")
        self.cancel_button.setMinimumHeight(40)
        self.cancel_button.clicked.connect(self.cancel_calculation)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)

        self.export_button = QPushButton("导出结果")
        self.export_button.setMinimumHeight(40)
        self.export_button.clicked.connect(self.export_results)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)

        self.clear_button = QPushButton("清除历史")
        self.clear_button.setMinimumHeight(40)
        self.clear_button.clicked.connect(self.clear_history)
        button_layout.addWidget(self.clear_button)

        layout.addLayout(button_layout)
        layout.addStretch()

        return widget
    
    def create_input_fields (self):
        """创建输入字段 (调整顺序版)"""
        # 1. 清空现有字段
        while self.input_layout.count():
            item = self.input_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        row = 0
        
        # ==========================================
        # 第一部分：基础合金定义
        # ==========================================
        if self.mode_single.isChecked() or self.mode_temp_curve.isChecked():
            self.input_layout.addWidget(QLabel("基础合金:"), row, 0, Qt.AlignRight)
            self.base_alloy_input = QLineEdit("Fe0.7Si0.3")
            if self.mode_temp_curve.isChecked():
                self.base_alloy_input.setPlaceholderText("例如: Fe0.7Si0.3 (保持固定)")
            else:
                self.base_alloy_input.setPlaceholderText("例如: Fe0.7Si0.3")
            self.input_layout.addWidget(self.base_alloy_input, row, 1)
            row += 1
        
        elif self.mode_curve.isChecked():
            self.input_layout.addWidget(QLabel("固定基础成分:"), row, 0, Qt.AlignRight)
            self.fixed_base_input = QLineEdit("Fe")
            self.fixed_base_input.setPlaceholderText("例如: Fe (不变化)")
            self.input_layout.addWidget(self.fixed_base_input, row, 1)
            row += 1
        
        # ==========================================
        # 第二部分：基体状态
        # ==========================================
        solution_label = QLabel("基体状态:")
        solution_label.setToolTip("选择基础合金所处的物理状态。\n程序将自动判断该状态下的稳定性。")
        self.input_layout.addWidget(solution_label, row, 0, Qt.AlignRight)
        
        self.solution_phase_combo = QComboBox()
        self.solution_phase_combo.addItems(["液相", "固相"])
        self.solution_phase_combo.setToolTip("液相和固相均采用UEM-Miedema框架计算")
        self.input_layout.addWidget(self.solution_phase_combo, row, 1)
        row += 1
        
        # ==========================================
        # 第三部分：溶质与析出相
        # ==========================================
        self.input_layout.addWidget(QLabel("溶质元素:"), row, 0, Qt.AlignRight)
        self.solute_input = QLineEdit("C")
        self.solute_input.setPlaceholderText("例如: C")
        self.input_layout.addWidget(self.solute_input, row, 1)
        row += 1
        
        
        # ==========================================
        # 第四部分：模式特定的参数 (温度、范围、采样点)
        # ==========================================
        
        # --- 模式 C: 温度曲线 (您图片中的模式) ---
        # 顺序: 起始温度 -> 终止温度 -> 采样点数
        if self.mode_temp_curve.isChecked():
            self.input_layout.addWidget(QLabel("起始温度 (K):"), row, 0, Qt.AlignRight)
            self.t_start_input = QLineEdit("1000")
            self.input_layout.addWidget(self.t_start_input, row, 1)
            row += 1
            
            self.input_layout.addWidget(QLabel("终止温度 (K):"), row, 0, Qt.AlignRight)
            self.t_end_input = QLineEdit("1800")
            self.input_layout.addWidget(self.t_end_input, row, 1)
            row += 1
            
            self.input_layout.addWidget(QLabel("采样点数:"), row, 0, Qt.AlignRight)
            self.n_points_input = QLineEdit("20")
            self.input_layout.addWidget(self.n_points_input, row, 1)
        
        # --- 模式 A: 单点计算 ---
        elif self.mode_single.isChecked():
            self.input_layout.addWidget(QLabel("温度 (K):"), row, 0, Qt.AlignRight)
            self.temperature_input = QLineEdit("1500")
            self.input_layout.addWidget(self.temperature_input, row, 1)
        
        # --- 模式 B: 浓度曲线 ---
        elif self.mode_curve.isChecked():
            self.input_layout.addWidget(QLabel("变化组分:"), row, 0, Qt.AlignRight)
            self.variable_comp_input = QLineEdit("Si")
            self.input_layout.addWidget(self.variable_comp_input, row, 1)
            row += 1
            
            self.input_layout.addWidget(QLabel("变化范围 (X_min):"), row, 0, Qt.AlignRight)
            self.x_min_input = QLineEdit("0.0")
            self.input_layout.addWidget(self.x_min_input, row, 1)
            row += 1
            
            self.input_layout.addWidget(QLabel("变化范围 (X_max):"), row, 0, Qt.AlignRight)
            self.x_max_input = QLineEdit("0.5")
            self.input_layout.addWidget(self.x_max_input, row, 1)
            row += 1
            
            self.input_layout.addWidget(QLabel("温度 (K):"), row, 0, Qt.AlignRight)
            self.temperature_input = QLineEdit("1500")
            self.input_layout.addWidget(self.temperature_input, row, 1)
            row += 1
            
            self.input_layout.addWidget(QLabel("采样点数:"), row, 0, Qt.AlignRight)
            self.n_points_input = QLineEdit("20")
            self.input_layout.addWidget(self.n_points_input, row, 1)

    def on_mode_changed(self):
        """模式切换时更新输入字段"""
        self.create_input_fields()

    def _extract_phase_name(self, phase_text: str) -> str:
        """映射溶液相选择为内部相名称
        液相 -> LIQUID
        固相 -> SOLID
        """
        if phase_text == "液相":
            return "LIQUID"
        elif phase_text == "固相":
            return "SOLID"
        else:
            return phase_text.strip()

    def create_results_panel(self):
        """创建结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 结果文本
        results_group = QGroupBox("计算结果")
        results_layout = QVBoxLayout(results_group)

        # 添加进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        results_layout.addWidget(self.progress_bar)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(150)

        # 禁用自动换行，启用横向滚动条
        self.results_text.setLineWrapMode(QTextEdit.NoWrap)
        self.results_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 设置等宽字体以确保表格对齐
        from PyQt5.QtGui import QFont
        font = QFont("Courier New", 9)  # 等宽字体
        font.setStyleHint(QFont.Monospace)
        self.results_text.setFont(font)

        results_layout.addWidget(self.results_text)

        layout.addWidget(results_group)

        # 图表绘制区域
        chart_group = QGroupBox("溶解度可视化")
        chart_layout = QVBoxLayout(chart_group)

        self.chart_canvas = MplCanvas(self, width=7, height=5, dpi=100)
        chart_layout.addWidget(self.chart_canvas)

        layout.addWidget(chart_group)

        return widget

    def cancel_calculation(self):
        """取消当前计算"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.results_text.append("\n⚠️ 用户取消计算...\n")
            self.progress_bar.setVisible(False)
            self.calculate_button.setEnabled(True)
            self.cancel_button.setEnabled(False)

    def on_calculation_started(self):
        """计算开始时的UI状态更新"""
        self.calculate_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

    def on_calculation_finished(self):
        """计算完成时的UI状态更新"""
        self.calculate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.export_button.setEnabled(True)

    def on_progress_updated(self, current, total):
        """更新进度条"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def on_error_occurred(self, error_msg):
        """处理计算错误"""
        self.on_calculation_finished()
        QMessageBox.critical(self, "计算错误", f"计算过程中发生错误:\n{error_msg}")
        self.results_text.append(f"\n❌ 错误: {error_msg}\n")

    def perform_calculation(self):
        """执行计算（多线程版本）"""
        # 如果已有任务在运行，先取消
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "提示", "已有计算任务正在运行，请先取消或等待完成！")
            return

        try:
            if self.mode_single.isChecked():
                self.calculate_single_point()
            elif self.mode_curve.isChecked():
                self.calculate_solubility_curve()
            elif self.mode_temp_curve.isChecked():
                self.calculate_temperature_curve()

        except Exception as e:
            QMessageBox.critical(self, "参数错误", f"参数验证失败:\n{str(e)}")
            self.results_text.setText(f"错误: {str(e)}")

    def calculate_single_point(self):
        """计算单点溶解度（多线程版本）"""
        # 获取输入参数
        solute = self.solute_input.text().strip().upper()
        
        solution_phase = self._extract_phase_name(self.solution_phase_combo.currentText())
        temperature = float(self.temperature_input.text())
        base_alloy_str = self.base_alloy_input.text().strip()

        if not solute or not base_alloy_str:
            QMessageBox.warning(self, "输入错误", "请输入溶质元素和基础合金！")
            return

        base_composition = parse_composition_static(base_alloy_str)
        if not base_composition:
            QMessageBox.warning(self, "输入错误", "无法解析基础合金成分！")
            return

        # 转为大写
        base_composition = {k.upper(): v for k, v in base_composition.items()}

        # 获取模型参数
        extrap_model_name = self.extrap_model_combo.currentText()
        activity_model = self.activity_model_combo.currentText()

        # 将外推模型名称转换为函数对象
        from models.extrapolation_models import BinaryModel
        bm = BinaryModel()
        extrap_func_map = {
            'UEM1': bm.UEM1, 'UEM2': bm.UEM2, 'UEM2-Adv': bm.UEM2_Adv,
            'GSM': bm.GSM, 'Muggianu': bm.Muggianu, 'Toop-Kohler': bm.Toop_Kohler,
            'Toop-Muggianu': bm.Toop_Muggianu
        }
        extrap_func = extrap_func_map.get(extrap_model_name, bm.UEM1)

        # 准备参数
        params = {
            'base_composition': base_composition,
            'solute': solute,
            'tdb_solution_phase': solution_phase,
            
            'temperature': temperature,
            'extrap_func': extrap_func,
            'extrap_model_name': extrap_model_name,
            'activity_model': activity_model,
            'base_alloy_str': base_alloy_str,
            'solution_phase_display': self.solution_phase_combo.currentText()
        }

        # 创建并启动工作线程
        self.worker = SolubilityWorker('single', params, self.phase_calc)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.calculation_finished.connect(self.on_single_point_finished)
        self.worker.error_occurred.connect(self.on_error_occurred)

        self.on_calculation_started()
        self.results_text.append(f"\n🔄 正在计算单点溶解度...\n")
        self.worker.start()

    def on_single_point_finished(self, data):
        """处理单点计算完成"""
        self.on_calculation_finished()

        result = data['result']
        params = data['params']
        base_alloy_str = params['base_alloy_str']
        solute = params['solute']
        detected_precipitate = result.get('precipitating_phase', 'Auto-Detect')
        detected_solution_phase = result.get('solution_phase_name', 'Unknown')

        # 简化相名称用于显示
        detected_precipitate_simple = self.simplify_phase_name(detected_precipitate)
        detected_solution_phase_simple = self.simplify_phase_name(detected_solution_phase)

        temperature = params['temperature']
        solution_phase = params['tdb_solution_phase']
        base_composition = params['base_composition']

        # 增加计算批次计数
        self.calculation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        phase_state_str = result.get('phase_state', solution_phase)
        base_stability = result.get('base_stability', 'Unknown')
        detected_solvent = result.get('solvent_element', 'Unknown')

        # 显示结果
        text_output = "\n" + "=" * 70 + "\n"
        text_output += f"【计算批次 #{self.calculation_count}】 {timestamp}\n"
        text_output += "溶解度计算结果\n"
        text_output += "=" * 70 + "\n\n"

        text_output += f"基础合金: {base_alloy_str}\n"
        text_output += f"  -> 自动识别溶剂: {detected_solvent}\n"
        text_output += f"  -> 基础合金状态: {base_stability} " + (
            "(⚠️ 不稳定)" if base_stability == "Unstable" else "(✅ 稳定)") + "\n"
        text_output += f"溶质元素: {solute}\n"
        text_output += f"  -> 溶解于相: {detected_solution_phase_simple}\n"
        text_output += f"  -> 析出相(平衡): {detected_precipitate_simple}\n"
        text_output += f"温度: {temperature:.2f} K ({temperature - 273.15:.2f} °C)\n"
        
        # 显示警告（特别是基础合金不稳定的警告）
        error_detail = result.get('error_detail', '')
        if error_detail:
            text_output += f"⚠️  主要错误: {error_detail}\n"
        warnings = result.get('warnings', [])
        if warnings:
            text_output += "\n⚠️  警告信息:\n"
            for warning in warnings:
                text_output += f"  • {warning}\n"
            text_output += "\n"
        
        if result['status'] == 'success':
            solubility = result['solubility_mole_fraction']
            
            relative_addition = result.get('relative_addition', 0)
            base_dilution = result.get('base_alloy_dilution', 0)
            # ... [原有的结果显示代码] ...
            text_output += f"✓ 溶解度 (X_{solute}): {solubility:.6e}\n"

            
            text_output += f"✓ 溶解度 (摩尔%): {solubility*100:.4f}%\n"
            text_output += f"✓ 相对添加量: {relative_addition:.4f} (溶质/基础合金 摩尔比)\n"
            text_output += f"  → 含义: 每 1 摩尔基础合金可添加 {relative_addition:.4f} 摩尔 {solute}\n"
            text_output += f"✓ 基础合金稀释度: {base_dilution*100:.2f}%\n\n"

            # 显示警告信息
            warnings = result.get('warnings', [])
            if warnings:
                text_output += "⚠️  合理性警告:\n"
                for warning in warnings:
                    text_output += f"  • {warning}\n"
                text_output += "\n"

            # 显示最终平衡合金的完整成分
            text_output += "说明：溶解度是指溶质在【最终平衡合金】中的摩尔分数\n"
            text_output += "-" * 70 + "\n"
            text_output += "最终平衡合金成分（总计=100%）：\n"
            if 'final_composition' in result:
                final_comp = result['final_composition']
                # 按含量从高到低排序
                sorted_comp = sorted(final_comp.items(), key=lambda x: x[1], reverse=True)
                for elem, mole_frac in sorted_comp:
                    text_output += f"  {elem}: {mole_frac:.6f} ({mole_frac*100:.4f}%)\n"
                # 验证总和
                total = sum(final_comp.values())
                text_output += f"  总计: {total:.6f} ({total*100:.2f}%)\n"
        elif result['status'] == 'fully_soluble':
            text_output += "结果: 完全溶解 (X ≈ 1.0)\n"
        elif result['status'] == 'insoluble':
            text_output += "结果: 几乎不溶 (X ≈ 0.0)\n"
        else:
            text_output += f"状态: {result['status']}\n"

        text_output += "=" * 70 + "\n"

        # 追加结果
        self.results_text.append(text_output)

        # 滚动到底部
        scrollbar = self.results_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # 绘制示意图
        self.chart_canvas.axes.clear()
        if result['status'] == 'success':
            solubility = result['solubility_mole_fraction']
            self.chart_canvas.axes.bar([solute], [solubility * 100], color='#3498db', width=0.5)

            # 构建基础合金成分描述（包含摩尔分数）
            base_alloy_desc = self.format_alloy_composition(base_composition)

            self.chart_canvas.axes.set_ylabel('溶解度 (摩尔%)', fontsize=11)

            # 标题：包含溶解相和析出相信息（使用简化名称）
            # 例如："C 在 Fe0.95Si0.05(BCC) 中的溶解度 | 析出相: GRAPHITE"
            title = f'{solute} 在 {base_alloy_desc}({detected_solution_phase_simple}) 中的溶解度\n析出相: {detected_precipitate_simple}'
            self.chart_canvas.axes.set_title(title, fontsize=11, fontweight='bold')
            self.chart_canvas.axes.grid(True, alpha=0.3, axis='y')
        self.chart_canvas.draw()
    
    def calculate_solubility_curve(self):
        """计算溶解度随浓度变化的曲线（多线程版本）"""
        # 获取输入参数
        solute = self.solute_input.text().strip().upper()
       
        solution_phase = self._extract_phase_name(self.solution_phase_combo.currentText())
        temperature = float(self.temperature_input.text())

        # 修改参数获取与解析逻辑
        fixed_base_str = self.fixed_base_input.text().strip()
        variable_comp = self.variable_comp_input.text().strip().upper()

        x_min = float(self.x_min_input.text())
        x_max = float(self.x_max_input.text())
        n_points = int(self.n_points_input.text())

        if not all([solute, fixed_base_str, variable_comp]):
            QMessageBox.warning(self, "输入错误", "请输入所有必需参数！")
            return

        # 解析固定基础合金成分
        fixed_base_map = parse_composition_static(fixed_base_str)
        if not fixed_base_map:
            QMessageBox.warning(self, "输入错误", f"无法解析固定基础成分: {fixed_base_str}")
            return

        # 归一化固定基础成分
        total_fixed = sum(fixed_base_map.values())
        fixed_base_norm = {k.upper(): v / total_fixed for k, v in fixed_base_map.items()}

        # 获取模型参数
        extrap_model_name = self.extrap_model_combo.currentText()
        activity_model = self.activity_model_combo.currentText()

        # 将外推模型名称转换为函数对象
        from models.extrapolation_models import BinaryModel
        bm = BinaryModel()
        extrap_func_map = {
            'UEM1': bm.UEM1, 'UEM2': bm.UEM2, 'UEM2-Adv': bm.UEM2_Adv,
            'GSM': bm.GSM, 'Muggianu': bm.Muggianu, 'Toop-Kohler': bm.Toop_Kohler,
            'Toop-Muggianu': bm.Toop_Muggianu
        }
        extrap_func = extrap_func_map.get(extrap_model_name, bm.UEM1)

        # 准备参数
        params = {
            'solute': solute,
            'tdb_solution_phase': solution_phase,
            
            'temperature': temperature,
            'extrap_func': extrap_func,
            'extrap_model_name': extrap_model_name,
            'activity_model': activity_model,
            'fixed_base_str': fixed_base_str,
            'fixed_base_norm': fixed_base_norm,
            'variable_comp': variable_comp,
            'x_min': x_min,
            'x_max': x_max,
            'n_points': n_points,
            'solution_phase_display': self.solution_phase_combo.currentText()
        }

        # 创建并启动工作线程
        self.worker = SolubilityWorker('curve', params, self.phase_calc)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.calculation_finished.connect(self.on_curve_finished)
        self.worker.error_occurred.connect(self.on_error_occurred)

        self.on_calculation_started()
        self.results_text.append(f"\n🔄 正在计算溶解度-浓度曲线 ({n_points} 个点)...\n")
        self.worker.start()

    def on_curve_finished(self, data):
        """处理浓度曲线计算完成"""
        self.on_calculation_finished()

        x_values = data['x_values']
        solubility_values = data['solubility_values']
        ideal_solubility_values = data['ideal_solubility_values']
        results_list = data['results_list']
        ideal_results_list = data['ideal_results_list']
        params = data['params']
        first_valid = next((r for r in results_list if r.get('status') == 'success'), {})
        detected_precipitate = first_valid.get('precipitating_phase', 'Auto-Detect')
        detected_solution_phase = first_valid.get('solution_phase_name', params.get('tdb_solution_phase', 'Unknown'))

        # 简化相名称用于显示
        detected_precipitate_simple = self.simplify_phase_name(detected_precipitate)
        detected_solution_phase_simple = self.simplify_phase_name(detected_solution_phase)

        solute = params['solute']
        solution_phase = params['tdb_solution_phase']

        temperature = params['temperature']
        extrap_model_name = params['extrap_model_name']
        activity_model = params['activity_model']
        fixed_base_str = params['fixed_base_str']
        fixed_base_norm = params['fixed_base_norm']
        variable_comp = params['variable_comp']
        n_points = params['n_points']
        x_min = params['x_min']
        x_max = params['x_max']

        # 格式化固定基础成分用于图表显示
        fixed_base_formatted = self.format_alloy_composition(fixed_base_norm)

        # 增加计算批次计数，结果文本输出
        self.calculation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


        # 显示结果
        text_output = "\n" + "=" * 70 + "\n"
        text_output += f"【计算批次 #{self.calculation_count}】 {timestamp}\n"
        text_output += "溶解度-浓度曲线计算结果\n"
        text_output += "=" * 70 + "\n\n"
        text_output += f"溶质元素: {solute}\n"
        text_output += f"固定基础: {fixed_base_str}\n"
        text_output += f"变化组分: {variable_comp} ({x_min:.3f} ~ {x_max:.3f})\n"
        text_output += f"  -> 溶解于相: {detected_solution_phase_simple}\n"
        text_output += f"析出相(平衡): {detected_precipitate_simple}\n"
        text_output += f"温度: {temperature:.2f} K ({temperature - 273.15:.2f} °C)\n"
        text_output += f"外推模型: {extrap_model_name}\n"
        text_output += f"活度模型: {activity_model}\n"
        text_output += f"采样点数: {n_points}\n\n"
        
        text_output += "说明：溶解度是指溶质在【最终平衡合金】中的摩尔分数\n"
        text_output += "      相对添加量 = 溶质摩尔数 / 基础合金摩尔数\n"
        text_output += "-" * 70 + "\n"

        
        # 统计警告数量
        warning_count = sum(1 for r in results_list if r.get('status') == 'success' and r.get('warnings'))
        if warning_count > 0:
            text_output += f"⚠️  {warning_count} 个数据点存在合理性警告，详见下表\n\n"
        
        # 【修改 1：更新表头】将 '警告' 改为 '状态/详情'
        text_output += f"{'X_' + variable_comp:<10} "
        text_output += f"{'X_' + solute + '(溶解度)':<16} "
        text_output += f"{'相对添加量':<12} "
        text_output += f"{'溶解相':<10} "
        text_output += f"{'状态/详情':<40}\n"  # 加宽一点以容纳错误信息
        text_output += "-" * 90 + "\n"

        for i, x_var in enumerate(x_values):
            result = results_list[i]
            sol = solubility_values[i]

            text_output += f"{x_var:<10.4f} "

            if sol is not None and result.get('status') == 'success':
                rel_add = result.get('relative_addition', 0)
                warnings = result.get('warnings', [])
                solution_phase_name = result.get('solution_phase_name', 'Unknown')
                solution_phase_simple = self.simplify_phase_name(solution_phase_name)

                text_output += f"{sol:<16.6e} "
                text_output += f"{rel_add:<12.4f} "
                text_output += f"{solution_phase_simple:<10} "

                if warnings:
                    # 只显示第一个警告的简短版本
                    first_warning = warnings[0]
                    if len(first_warning) > 28:
                        text_output += first_warning[:25] + "..."
                    else:
                        text_output += first_warning
                else:
                    text_output += "OK"  # 成功且无警告显示 OK

                text_output += "\n"
            elif sol is not None and result.get('status') == 'fully_soluble':
                # 完全互溶的情况
                solution_phase_name = result.get('solution_phase_name', 'Unknown')
                solution_phase_simple = self.simplify_phase_name(solution_phase_name)

                text_output += f"{'完全互溶':<16} "
                text_output += f"{'无上限':<12} "
                text_output += f"{solution_phase_simple:<10} "
                status_msg = self.truncate_text("可任意添加溶质", max_length=35)
                text_output += f"{status_msg}\n"
            else:
                # 【修改 2：处理失败情况，显示详细错误】
                error_detail = result.get('error_detail', '')
                status = result.get('status', 'Unknown')

                # 根据不同状态显示清晰的说明
                if error_detail:
                    display_msg = error_detail
                elif status == 'base_unstable':
                    display_msg = "基础合金不稳定，无法计算溶解度"
                elif status == 'insoluble':
                    display_msg = "溶质不溶"
                elif status == 'error':
                    display_msg = "计算错误"
                else:
                    display_msg = f"未知状态: {status}"

                # 截断长消息，保持表格紧凑
                display_msg = self.truncate_text(display_msg, max_length=35)

                text_output += f"{'0':<16} {'N/A':<12} {'N/A':<10} {display_msg}\n"
        
        text_output += "=" * 70 + "\n"
        # 如果存在高溶解度警告，添加额外说明
        high_solubility_points = [(x_values[i], solubility_values[i])
                                   for i, r in enumerate(results_list)
                                   if r.get('status') == 'success' and solubility_values[i] and solubility_values[i] > 0.5]
        if high_solubility_points:
            text_output += "\n📊 高溶解度数据点详细说明:\n"
            text_output += "-" * 70 + "\n"
            for x_var, sol in high_solubility_points[:3]:  # 最多显示3个
                idx = list(x_values).index(x_var)
                result = results_list[idx]
                final_comp = result.get('final_composition', {})
                if final_comp:
                    text_output += f"当 X_{variable_comp}={x_var:.3f} 时，X_{solute}={sol:.3f}:\n"
                    text_output += "  最终合金成分: "
                    comp_str = ", ".join([f"{k}({v*100:.1f}%)" for k, v in sorted(final_comp.items(), key=lambda x: x[1], reverse=True)])
                    text_output += comp_str + "\n"
            text_output += "-" * 70 + "\n"

        # 追加结果
        self.results_text.append(text_output)

        # 滚动到底部
        scrollbar = self.results_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # 绘制曲线
        self.chart_canvas.axes.clear()

        # 直接使用所有数据，不溶解=0%，完全互溶=100%
        if len(x_values) > 0:
            # 绘制实际溶解度曲线
            self.chart_canvas.axes.plot(x_values, [s*100 for s in solubility_values], 'b-o', linewidth=2, markersize=5,
                                        label=f'实际溶解度 ({extrap_model_name})')

            # 绘制理想溶解度曲线
            self.chart_canvas.axes.plot(x_values, [s*100 for s in ideal_solubility_values], 'r--s', linewidth=2,
                                        markersize=5, label='理想溶解度 (γ=1)')

            # 检测并标注相转变
            phase_transitions = []
            for i in range(len(results_list) - 1):
                if results_list[i].get('status') == 'success' and results_list[i+1].get('status') == 'success':
                    phase1 = results_list[i].get('solution_phase_name', '')
                    phase2 = results_list[i+1].get('solution_phase_name', '')
                    if phase1 and phase2 and phase1 != phase2:
                        # 相转变发生在两点之间
                        x_transition = (x_values[i] + x_values[i+1]) / 2
                        phase_transitions.append((x_transition, phase1, phase2))

            # 检测溶解相区域（连续相同的相）
            phase_regions = []
            current_phase = None
            region_start = None
            for i, result in enumerate(results_list):
                if result.get('status') == 'success':
                    phase = result.get('solution_phase_name', '')
                    if phase:
                        if phase != current_phase:
                            # 结束前一个区域
                            if current_phase is not None and region_start is not None:
                                phase_regions.append((region_start, x_values[i-1], current_phase))
                            # 开始新区域
                            current_phase = phase
                            region_start = x_values[i]
            # 添加最后一个区域
            if current_phase is not None and region_start is not None:
                phase_regions.append((region_start, x_values[-1], current_phase))

            # 在图表中标注相转变
            if phase_transitions:
                y_min, y_max = self.chart_canvas.axes.get_ylim()
                for x_trans, phase1, phase2 in phase_transitions:
                    # 绘制垂直虚线
                    self.chart_canvas.axes.axvline(x=x_trans, color='green', linestyle=':', linewidth=2, alpha=0.7)
                    # 添加文字标注
                    phase1_simple = self.simplify_phase_name(phase1)
                    phase2_simple = self.simplify_phase_name(phase2)
                    self.chart_canvas.axes.text(x_trans, y_max * 0.95,
                                               f'{phase1_simple}→{phase2_simple}',
                                               rotation=90, verticalalignment='top',
                                               fontsize=9, color='green', fontweight='bold')

            # 标注相区域
            if phase_regions:
                y_min, y_max = self.chart_canvas.axes.get_ylim()
                for x_start, x_end, phase in phase_regions:
                    phase_simple = self.simplify_phase_name(phase)
                    x_center = (x_start + x_end) / 2
                    # 在图表顶部标注相区域
                    self.chart_canvas.axes.text(x_center, y_max * 0.85,
                                               f'{phase_simple}相区',
                                               horizontalalignment='center',
                                               fontsize=10, color='blue', fontweight='bold',
                                               bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.3))

            # 构建更清晰的标签
            # X轴：变化组分的摩尔分数
            self.chart_canvas.axes.set_xlabel(f'{variable_comp} 含量 (摩尔分数)', fontsize=11)

            # Y轴：溶质的溶解度
            self.chart_canvas.axes.set_ylabel(f'{solute} 溶解度 (摩尔%)', fontsize=11)

            # 标题：使用化学式形式 (AmBn)_{1-x}C_x
            # 例如："C 在 (Fe0.95Si0.05)_{1-x}Cr_x(BCC) 中的溶解度 vs. Cr 含量"
            alloy_formula = f'({fixed_base_formatted})$_{{1-x}}${variable_comp}$_x$'
            title = f'{solute} 在 {alloy_formula}({detected_solution_phase_simple}) 中的溶解度 vs. {variable_comp} 含量\n析出相: {detected_precipitate_simple}'
            self.chart_canvas.axes.set_title(title, fontsize=12, fontweight='bold')

            self.chart_canvas.axes.grid(True, alpha=0.3)
            self.chart_canvas.axes.legend(loc='best', fontsize=10)

        self.chart_canvas.draw()
    
    def calculate_temperature_curve(self):
        """计算溶解度随温度变化的曲线（多线程版本）"""
        # 1. 获取参数
        solute = self.solute_input.text().strip().upper()
        
        solution_phase = self._extract_phase_name(self.solution_phase_combo.currentText())
        base_alloy_str = self.base_alloy_input.text().strip()

        t_start = float(self.t_start_input.text())
        t_end = float(self.t_end_input.text())
        n_points = int(self.n_points_input.text())

        if not all([solute, base_alloy_str]):
            QMessageBox.warning(self, "输入错误", "请输入所有必需参数！")
            return

        # 解析基础合金
        base_composition = parse_composition_static(base_alloy_str)
        if not base_composition:
            QMessageBox.warning(self, "输入错误", "无法解析基础合金成分！")
            return
        base_composition = {k.upper(): v for k, v in base_composition.items()}

        # 获取模型参数
        extrap_model_name = self.extrap_model_combo.currentText()
        activity_model = self.activity_model_combo.currentText()
        from models.extrapolation_models import BinaryModel
        bm = BinaryModel()
        extrap_func_map = {
            'UEM1': bm.UEM1, 'UEM2': bm.UEM2, 'UEM2-Adv': bm.UEM2_Adv,
            'GSM': bm.GSM, 'Muggianu': bm.Muggianu, 'Toop-Kohler': bm.Toop_Kohler,
            'Toop-Muggianu': bm.Toop_Muggianu
        }
        extrap_func = extrap_func_map.get(extrap_model_name, bm.UEM1)

        # 准备参数
        params = {
            'base_composition': base_composition,
            'solute': solute,
            'tdb_solution_phase': solution_phase,
            
            'extrap_func': extrap_func,
            'extrap_model_name': extrap_model_name,
            'activity_model': activity_model,
            't_start': t_start,
            't_end': t_end,
            'n_points': n_points,
            'base_alloy_str': base_alloy_str,
            'solution_phase_display': self.solution_phase_combo.currentText()
        }

        # 创建并启动工作线程
        self.worker = SolubilityWorker('temperature', params, self.phase_calc)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.calculation_finished.connect(self.on_temperature_finished)
        self.worker.error_occurred.connect(self.on_error_occurred)

        self.on_calculation_started()
        self.results_text.append(f"\n🔄 正在计算溶解度-温度曲线 ({n_points} 个点)...\n")
        self.worker.start()

    def on_temperature_finished(self, data):
        """处理温度曲线计算完成"""
        self.on_calculation_finished()

        t_values = data['t_values']
        solubility_values = data['solubility_values']
        ideal_solubility_values = data['ideal_solubility_values']
        results_list = data['results_list']
        ideal_results_list = data['ideal_results_list']
        params = data['params']

        solute = params['solute']
        solution_phase = params['tdb_solution_phase']
        base_composition = params['base_composition']

        extrap_model_name = params['extrap_model_name']
        base_alloy_str = params['base_alloy_str']
        t_start = params['t_start']
        t_end = params['t_end']

        # 结果文本输出
        self.calculation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 提取第一点的溶剂信息用于显示
        first_valid = next((r for r in results_list if r.get('status') == 'success'), {})
        detected_solvent = first_valid.get('solvent_element', 'Unknown')
        detected_precipitate = first_valid.get('precipitating_phase', 'Auto-Detect')
        detected_solution_phase = first_valid.get('solution_phase_name', solution_phase)

        # 简化相名称用于显示
        detected_precipitate_simple = self.simplify_phase_name(detected_precipitate)
        detected_solution_phase_simple = self.simplify_phase_name(detected_solution_phase)

        # 格式化基础合金成分用于图表显示
        base_alloy_formatted = self.format_alloy_composition(base_composition)

        text_output = "\n" + "=" * 70 + "\n"
        text_output += f"【计算批次 #{self.calculation_count}】 {timestamp}\n"
        text_output += "溶解度-温度曲线计算结果\n"
        text_output += "=" * 70 + "\n\n"
        text_output += f"溶质元素: {solute}\n"
        text_output += f"基础合金: {base_alloy_str}\n"
        text_output += f"  -> 自动识别溶剂: {detected_solvent}\n"
        text_output += f"  -> 溶解于相: {detected_solution_phase_simple}\n"
        text_output += f"温度范围: {t_start:.1f} K ~ {t_end:.1f} K\n"
        text_output += f"析出相(平衡): {detected_precipitate_simple}\n\n"

        text_output += "说明: 实际溶解度采用UEM-Miedema模型（考虑活度系数），理想溶解度假设活度系数=1\n"
        text_output += "-" * 95 + "\n"

        text_output += f"{'温度(K)':<10} {'温度(°C)':<10} {'实际溶解度':<18} {'理想溶解度':<18} {'溶解相':<10} {'状态/备注':<20}\n"
        text_output += "-" * 95 + "\n"

        for i, t_curr in enumerate(t_values):
            sol = solubility_values[i]
            sol_ideal = ideal_solubility_values[i]
            res = results_list[i]

            # 温度信息
            temp_k_str = f"{t_curr:<10.1f}"
            temp_c_str = f"{t_curr - 273.15:<10.1f}"

            # 判断计算是否成功
            if sol is not None and res.get('status') == 'success':
                # 成功计算出溶解度
                sol_str = f"{sol:.6e}"

                # 获取溶解相信息
                solution_phase_name = res.get('solution_phase_name', 'Unknown')
                solution_phase_simple = self.simplify_phase_name(solution_phase_name)

                # 理想溶解度
                if sol_ideal is not None:
                    sol_ideal_str = f"{sol_ideal:.6e}"
                    # 计算偏差系数
                    if sol_ideal > 1e-12:
                        deviation = sol / sol_ideal
                        status_str = f"γ偏差={deviation:.4f}"
                    else:
                        status_str = "OK"
                else:
                    sol_ideal_str = "N/A"
                    status_str = "理想计算失败"

                text_output += f"{temp_k_str} {temp_c_str} {sol_str:<18} {sol_ideal_str:<18} {solution_phase_simple:<10} {status_str:<20}\n"

            elif sol is not None and res.get('status') == 'fully_soluble':
                # 完全互溶的情况
                solution_phase_name = res.get('solution_phase_name', 'Unknown')
                solution_phase_simple = self.simplify_phase_name(solution_phase_name)

                # 理想溶解度
                if sol_ideal is not None:
                    sol_ideal_str = f"{sol_ideal:.6e}"
                else:
                    sol_ideal_str = "N/A"

                # 截断状态消息
                status_msg = self.truncate_text(f"溶解于{solution_phase_simple}", max_length=18)
                text_output += f"{temp_k_str} {temp_c_str} {'完全互溶':<18} {sol_ideal_str:<18} {solution_phase_simple:<10} {status_msg}\n"

            else:
                # 计算失败或不稳定，在曲线上显示为0
                sol_str = "0"

                # 理想溶解度（即使实际失败，理想可能成功）
                if sol_ideal is not None and sol_ideal > 0:
                    sol_ideal_str = f"{sol_ideal:.6e}"
                else:
                    sol_ideal_str = "0"

                # 获取详细错误信息
                error_detail = res.get('error_detail', '')
                status = res.get('status', 'Unknown')

                # 根据不同状态显示清晰的说明
                if error_detail:
                    display_msg = error_detail
                elif status == 'base_unstable':
                    display_msg = "基础合金不稳定，无法计算溶解度"
                elif status == 'insoluble':
                    display_msg = "溶质不溶"
                elif status == 'error':
                    display_msg = "计算错误"
                else:
                    display_msg = f"未知状态: {status}"

                # 截断长消息，保持表格紧凑
                display_msg = self.truncate_text(display_msg, max_length=18)

                text_output += f"{temp_k_str} {temp_c_str} {sol_str:<18} {sol_ideal_str:<18} {'N/A':<10} {display_msg}\n"
            
        self.results_text.append(text_output)
        scrollbar = self.results_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # 5. 绘制图表
        self.chart_canvas.axes.clear()

        # 直接使用所有数据，不溶解=0%，完全互溶=100%
        if len(t_values) > 0:
            # 绘制实际溶解度曲线
            self.chart_canvas.axes.plot(t_values, [s * 100 for s in solubility_values], 'b-o', linewidth=2, markersize=4,
                                        label=f'实际溶解度 ({extrap_model_name})')

            # 绘制理想溶解度曲线
            self.chart_canvas.axes.plot(t_values, [s * 100 for s in ideal_solubility_values], 'r--s', linewidth=2,
                                        markersize=4, label='理想溶解度 (γ=1)')

            # 检测并标注相转变
            phase_transitions = []
            for i in range(len(results_list) - 1):
                if results_list[i].get('status') == 'success' and results_list[i+1].get('status') == 'success':
                    phase1 = results_list[i].get('solution_phase_name', '')
                    phase2 = results_list[i+1].get('solution_phase_name', '')
                    if phase1 and phase2 and phase1 != phase2:
                        # 相转变发生在两点之间
                        t_transition = (t_values[i] + t_values[i+1]) / 2
                        phase_transitions.append((t_transition, phase1, phase2))

            # 检测溶解相区域（连续相同的相）
            phase_regions = []
            current_phase = None
            region_start = None
            for i, result in enumerate(results_list):
                if result.get('status') == 'success':
                    phase = result.get('solution_phase_name', '')
                    if phase:
                        if phase != current_phase:
                            # 结束前一个区域
                            if current_phase is not None and region_start is not None:
                                phase_regions.append((region_start, t_values[i-1], current_phase))
                            # 开始新区域
                            current_phase = phase
                            region_start = t_values[i]
            # 添加最后一个区域
            if current_phase is not None and region_start is not None:
                phase_regions.append((region_start, t_values[-1], current_phase))

            # 在图表中标注相转变
            if phase_transitions:
                y_min, y_max = self.chart_canvas.axes.get_ylim()
                for t_trans, phase1, phase2 in phase_transitions:
                    # 绘制垂直虚线
                    self.chart_canvas.axes.axvline(x=t_trans, color='green', linestyle=':', linewidth=2, alpha=0.7)
                    # 添加文字标注
                    phase1_simple = self.simplify_phase_name(phase1)
                    phase2_simple = self.simplify_phase_name(phase2)
                    self.chart_canvas.axes.text(t_trans, y_max * 0.95,
                                               f'{phase1_simple}→{phase2_simple}',
                                               rotation=90, verticalalignment='top',
                                               fontsize=9, color='green', fontweight='bold')

            # 标注相区域
            if phase_regions:
                y_min, y_max = self.chart_canvas.axes.get_ylim()
                for t_start, t_end, phase in phase_regions:
                    phase_simple = self.simplify_phase_name(phase)
                    t_center = (t_start + t_end) / 2
                    # 在图表顶部标注相区域
                    self.chart_canvas.axes.text(t_center, y_max * 0.85,
                                               f'{phase_simple}相区',
                                               horizontalalignment='center',
                                               fontsize=10, color='blue', fontweight='bold',
                                               bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.3))

            self.chart_canvas.axes.set_xlabel('温度 (K)', fontsize=11)
            self.chart_canvas.axes.set_ylabel(f'{solute} 溶解度 (摩尔%)', fontsize=11)

            # 使用检测到的溶液相名称（简化），并显示基础合金的组成比
            # 例如："C 在 Fe0.95Si0.05(BCC) 中的溶解度 vs. 温度"
            title = f'{solute} 在 {base_alloy_formatted}({detected_solution_phase_simple}) 中的溶解度 vs. 温度\n析出相: {detected_precipitate_simple}'
            self.chart_canvas.axes.set_title(title, fontsize=12, fontweight='bold')
            self.chart_canvas.axes.grid(True, alpha=0.3)
            self.chart_canvas.axes.legend(loc='best', fontsize=10)

            # 如果数据跨度大，可以考虑对数坐标，这里默认线性
            # self.chart_canvas.axes.set_yscale('log')

        self.chart_canvas.draw()

    def clear_history(self):
        """清除历史计算记录"""
        reply = QMessageBox.question(
            self,
            "确认清除",
            "确定要清除所有历史计算记录吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.results_text.clear()
            self.calculation_count = 0
            self.chart_canvas.axes.clear()
            self.chart_canvas.axes.set_title("溶解度")
            self.chart_canvas.axes.set_xlabel("成分")
            self.chart_canvas.axes.set_ylabel("溶解度 (摩尔%)")
            self.chart_canvas.axes.grid(True, alpha=0.3)
            self.chart_canvas.draw()

    def export_results(self):
        """导出结果"""
        try:
            results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'results')
            os.makedirs(results_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(results_dir, f"solubility_{timestamp}.txt")

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.results_text.toPlainText())

            QMessageBox.information(self, "导出成功", f"结果已保存到:\n{filename}")

        except Exception as e:
            QMessageBox.critical(self, "导出错误", f"导出失败:\n{str(e)}")


# 测试代码
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    widget = SolubilityWidget()
    widget.setWindowTitle("溶解度计算")
    widget.resize(1200, 800)
    widget.show()
    sys.exit(app.exec_())
