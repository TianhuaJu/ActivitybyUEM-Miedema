"""
析出温度计算 Widget
====================
用于计算和可视化溶质析出温度的GUI组件

功能:
- 单点析出温度计算
- 析出温度-成分曲线
- 多溶质析出顺序分析
"""

import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton,
                             QSplitter, QGroupBox, QTextEdit,
                             QMessageBox, QRadioButton, QButtonGroup,
                             QProgressBar, QTableWidget, QTableWidgetItem,
                             QHeaderView, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from gui.widgets import AutoResizeTextEdit
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils import parse_composition_static
from calculations.precipitation_temperature import PrecipitationTemperatureCalculator


class PrecipitationWorker(QThread):
    """析出温度计算工作线程"""

    progress_updated = pyqtSignal(int, int)
    calculation_finished = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, calc_type, params, calculator):
        super().__init__()
        self.calc_type = calc_type
        self.params = params
        self.calculator = calculator
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self.calc_type == 'single':
                self._run_single_calculation()
            elif self.calc_type == 'curve':
                self._run_curve_calculation()
            elif self.calc_type == 'multi_solute':
                self._run_multi_solute_calculation()
            elif self.calc_type == 'manual_precipitate':
                self._run_manual_precipitate_calculation()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(str(e))

    def _run_single_calculation(self):
        """执行单点析出温度计算"""
        result = self.calculator.calculate_precipitation_temperature(
            alloy_composition=self.params['composition'],
            solute_element=self.params['solute'],
            solution_phase=self.params['solution_phase'],
            extrapolation_func=self.params['extrap_func'],
            extrapolation_model_name=self.params['extrap_model_name'],
            activity_model=self.params['activity_model']
        )

        self.calculation_finished.emit({
            'type': 'single',
            'result': result,
            'params': self.params
        })

    def _run_curve_calculation(self):
        """执行析出温度曲线计算"""
        def progress_callback(current, total):
            if self._is_cancelled:
                return
            self.progress_updated.emit(current, total)

        result = self.calculator.calculate_precipitation_curve(
            base_alloy_composition=self.params['base_composition'],
            solute_element=self.params['solute'],
            x_min=self.params['x_min'],
            x_max=self.params['x_max'],
            n_points=self.params['n_points'],
            solution_phase=self.params['solution_phase'],
            extrapolation_func=self.params['extrap_func'],
            extrapolation_model_name=self.params['extrap_model_name'],
            activity_model=self.params['activity_model'],
            progress_callback=progress_callback
        )

        self.calculation_finished.emit({
            'type': 'curve',
            'result': result,
            'params': self.params
        })

    def _run_multi_solute_calculation(self):
        """执行多溶质析出顺序计算"""
        result = self.calculator.calculate_multi_solute_precipitation(
            alloy_composition=self.params['composition'],
            solute_elements=self.params['solutes'],
            solution_phase=self.params['solution_phase'],
            extrapolation_func=self.params['extrap_func'],
            extrapolation_model_name=self.params['extrap_model_name'],
            activity_model=self.params['activity_model']
        )

        self.calculation_finished.emit({
            'type': 'multi_solute',
            'result': result,
            'params': self.params
        })

    def _run_manual_precipitate_calculation(self):
        """执行手动指定析出相的析出温度计算"""
        result = self.calculator.calculate_multi_precipitate_temperature(
            alloy_composition=self.params['composition'],
            precipitate_phases=self.params['precipitates'],
            solution_phase=self.params['solution_phase'],
            compound_gibbs_energies=self.params['gibbs_energies'],
            extrapolation_func=self.params['extrap_func'],
            extrapolation_model_name=self.params['extrap_model_name'],
            activity_model=self.params['activity_model']
        )

        self.calculation_finished.emit({
            'type': 'manual_precipitate',
            'result': result,
            'params': self.params
        })


class MplCanvas(FigureCanvas):
    """Matplotlib画布"""

    def __init__(self, parent=None, width=7, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)


class PrecipitationTemperatureWidget(QWidget):
    """析出温度计算与可视化组件"""

    def __init__(self):
        super().__init__()

        self.calculator = PrecipitationTemperatureCalculator()
        self.calculation_count = 0
        self.worker = None
        self.setup_ui()

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

        self.mode_single = QRadioButton("单点析出温度计算")
        self.mode_curve = QRadioButton("析出温度-成分曲线")
        self.mode_multi = QRadioButton("多溶质析出顺序")
        self.mode_manual = QRadioButton("手动指定析出相")

        self.mode_button_group.addButton(self.mode_single, 1)
        self.mode_button_group.addButton(self.mode_curve, 2)
        self.mode_button_group.addButton(self.mode_multi, 3)
        self.mode_button_group.addButton(self.mode_manual, 4)

        self.mode_single.setChecked(True)
        self.mode_single.toggled.connect(self.on_mode_changed)
        self.mode_curve.toggled.connect(self.on_mode_changed)
        self.mode_multi.toggled.connect(self.on_mode_changed)
        self.mode_manual.toggled.connect(self.on_mode_changed)

        mode_layout.addWidget(self.mode_single)
        mode_layout.addWidget(self.mode_curve)
        mode_layout.addWidget(self.mode_multi)
        mode_layout.addWidget(self.mode_manual)

        layout.addWidget(mode_group)

        # 模型参数
        model_group = QGroupBox("计算模型")
        model_layout = QGridLayout(model_group)
        model_layout.setSpacing(10)

        row = 0
        model_layout.addWidget(QLabel("外推模型:"), row, 0, Qt.AlignRight)
        self.extrap_model_combo = QComboBox()
        self.extrap_model_combo.addItems([
            "UEM1", "UEM1_A","UEM2", "UEM2-Adv", "GSM",
            "Muggianu", "Toop-Muggianu", "Toop-Kohler"
        ])
        model_layout.addWidget(self.extrap_model_combo, row, 1)
        row += 1

        model_layout.addWidget(QLabel("活度模型:"), row, 0, Qt.AlignRight)
        self.activity_model_combo = QComboBox()
        self.activity_model_combo.addItems(["Wagner", "Darken", "Elliott"])
        model_layout.addWidget(self.activity_model_combo, row, 1)

        layout.addWidget(model_group)

        # 输入参数分组
        self.input_group = QGroupBox("输入参数")
        self.input_layout = QGridLayout(self.input_group)
        self.input_layout.setSpacing(10)

        self.create_input_fields()

        layout.addWidget(self.input_group)

        # 按钮
        button_layout = QHBoxLayout()

        self.calculate_button = QPushButton("计算")
        self.calculate_button.setMinimumHeight(40)
        self.calculate_button.clicked.connect(self.perform_calculation)
        button_layout.addWidget(self.calculate_button)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.setMinimumHeight(40)
        self.cancel_button.clicked.connect(self.cancel_calculation)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)

        self.export_button = QPushButton("导出")
        self.export_button.setMinimumHeight(40)
        self.export_button.clicked.connect(self.export_results)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)

        layout.addLayout(button_layout)
        layout.addStretch()

        return widget

    def create_input_fields(self):
        """创建输入字段"""
        # 清空现有字段
        while self.input_layout.count():
            item = self.input_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        row = 0

        if self.mode_single.isChecked():
            # 单点计算（自动调整大小）
            self.input_layout.addWidget(QLabel("合金成分:"), row, 0, Qt.AlignRight)
            self.alloy_input = AutoResizeTextEdit(min_lines=1, max_lines=3)
            self.alloy_input.setText("Fe0.98C0.02")
            self.alloy_input.setPlaceholderText("例如: Fe0.98C0.02 或 Fe0.95C0.02Si0.03")
            self.input_layout.addWidget(self.alloy_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("溶质元素:"), row, 0, Qt.AlignRight)
            self.solute_input = QLineEdit("C")
            self.solute_input.setPlaceholderText("例如: C")
            self.input_layout.addWidget(self.solute_input, row, 1)
            row += 1

        elif self.mode_curve.isChecked():
            # 曲线计算（自动调整大小）
            self.input_layout.addWidget(QLabel("基础合金:"), row, 0, Qt.AlignRight)
            self.base_alloy_input = AutoResizeTextEdit(min_lines=1, max_lines=3)
            self.base_alloy_input.setText("Fe")
            self.base_alloy_input.setPlaceholderText("例如: Fe 或 Fe0.97Si0.03")
            self.input_layout.addWidget(self.base_alloy_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("溶质元素:"), row, 0, Qt.AlignRight)
            self.solute_input = QLineEdit("C")
            self.input_layout.addWidget(self.solute_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("X_min (摩尔分数):"), row, 0, Qt.AlignRight)
            self.x_min_input = QLineEdit("0.001")
            self.input_layout.addWidget(self.x_min_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("X_max (摩尔分数):"), row, 0, Qt.AlignRight)
            self.x_max_input = QLineEdit("0.05")
            self.input_layout.addWidget(self.x_max_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("采样点数:"), row, 0, Qt.AlignRight)
            self.n_points_input = QLineEdit("20")
            self.input_layout.addWidget(self.n_points_input, row, 1)
            row += 1

        elif self.mode_multi.isChecked():
            # 多溶质计算（自动调整大小）
            self.input_layout.addWidget(QLabel("合金成分:"), row, 0, Qt.AlignRight)
            self.alloy_input = AutoResizeTextEdit(min_lines=1, max_lines=3)
            self.alloy_input.setText("Fe0.92C0.02Mn0.03Si0.02N0.01")
            self.alloy_input.setPlaceholderText("多元合金成分")
            self.input_layout.addWidget(self.alloy_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("溶质列表:"), row, 0, Qt.AlignRight)
            self.solutes_input = QLineEdit("C, Mn, Si, N")
            self.solutes_input.setPlaceholderText("用逗号分隔，例如: C, Mn, Si")
            self.input_layout.addWidget(self.solutes_input, row, 1)
            row += 1

        elif self.mode_manual.isChecked():
            # 手动指定析出相计算
            self.input_layout.addWidget(QLabel("合金成分:"), row, 0, Qt.AlignRight)
            self.alloy_input = AutoResizeTextEdit(min_lines=1, max_lines=3)
            self.alloy_input.setText("Fe0.95C0.03Ti0.02")
            self.alloy_input.setPlaceholderText("例如: Fe0.95C0.03Ti0.02")
            self.input_layout.addWidget(self.alloy_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("析出相:"), row, 0, Qt.AlignRight)
            self.precipitate_input = AutoResizeTextEdit(min_lines=1, max_lines=2)
            self.precipitate_input.setText("Fe3C")
            self.precipitate_input.setPlaceholderText("化合物，如: Fe3C, TiC（多个用逗号分隔）")
            self.input_layout.addWidget(self.precipitate_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("吉布斯能(J/mol):"), row, 0, Qt.AlignRight)
            self.gibbs_input = QLineEdit("auto")
            self.gibbs_input.setPlaceholderText("auto表示自动估算，多个用逗号分隔")
            self.input_layout.addWidget(self.gibbs_input, row, 1)
            row += 1

        # 基体状态（所有模式通用）
        self.input_layout.addWidget(QLabel("基体状态:"), row, 0, Qt.AlignRight)
        self.phase_combo = QComboBox()
        self.phase_combo.addItems(["固相", "液相"])
        self.input_layout.addWidget(self.phase_combo, row, 1)

    def on_mode_changed(self):
        """模式改变时更新输入字段"""
        self.create_input_fields()

    def create_results_panel(self):
        """创建结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 结果文本
        results_group = QGroupBox("计算结果")
        results_layout = QVBoxLayout(results_group)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(180)
        self.results_text.setLineWrapMode(QTextEdit.NoWrap)

        font = QFont("Courier New", 9)
        font.setStyleHint(QFont.Monospace)
        self.results_text.setFont(font)

        results_layout.addWidget(self.results_text)
        layout.addWidget(results_group)

        # 图表
        chart_group = QGroupBox("析出温度可视化")
        chart_layout = QVBoxLayout(chart_group)

        self.chart_canvas = MplCanvas(self, width=7, height=5, dpi=100)
        chart_layout.addWidget(self.chart_canvas)

        layout.addWidget(chart_group)

        return widget

    def get_extrap_func(self):
        """获取外推函数"""
        from models.extrapolation_models import BinaryModel

        bm = BinaryModel()
        model_name = self.extrap_model_combo.currentText()

        func_map = {
            'UEM1': bm.UEM1, "UEM1_A":bm.UEM1_A,'UEM2': bm.UEM2, 'UEM2-Adv': bm.UEM2_Adv,
            'GSM': bm.GSM, 'Muggianu': bm.Muggianu,
            'Toop-Kohler': bm.Toop_Kohler, 'Toop-Muggianu': bm.Toop_Muggianu
        }

        return func_map.get(model_name, bm.UEM1)

    def perform_calculation(self):
        """执行计算"""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "提示", "计算正在进行中...")
            return

        try:
            if self.mode_single.isChecked():
                self.calculate_single_point()
            elif self.mode_curve.isChecked():
                self.calculate_curve()
            elif self.mode_multi.isChecked():
                self.calculate_multi_solute()
            elif self.mode_manual.isChecked():
                self.calculate_manual_precipitate()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"参数错误: {str(e)}")

    def calculate_single_point(self):
        """单点计算"""
        alloy_str = self.alloy_input.text().strip()
        solute = self.solute_input.text().strip().upper()

        composition = parse_composition_static(alloy_str)
        if not composition:
            QMessageBox.warning(self, "错误", "无法解析合金成分")
            return

        composition = {k.upper(): v for k, v in composition.items()}

        solution_phase = 'LIQUID' if self.phase_combo.currentText() == "液相" else 'SOLID'

        params = {
            'composition': composition,
            'solute': solute,
            'solution_phase': solution_phase,
            'extrap_func': self.get_extrap_func(),
            'extrap_model_name': self.extrap_model_combo.currentText(),
            'activity_model': self.activity_model_combo.currentText(),
            'alloy_str': alloy_str
        }

        self.worker = PrecipitationWorker('single', params, self.calculator)
        self.worker.calculation_finished.connect(self.on_single_finished)
        self.worker.error_occurred.connect(self.on_error)

        self.on_calculation_started()
        self.results_text.append("\n正在计算单点析出温度...\n")
        self.worker.start()

    def calculate_curve(self):
        """曲线计算"""
        base_str = self.base_alloy_input.text().strip()
        solute = self.solute_input.text().strip().upper()

        base_composition = parse_composition_static(base_str)
        if not base_composition:
            QMessageBox.warning(self, "错误", "无法解析基础合金成分")
            return

        base_composition = {k.upper(): v for k, v in base_composition.items()}

        x_min = float(self.x_min_input.text())
        x_max = float(self.x_max_input.text())
        n_points = int(self.n_points_input.text())

        solution_phase = 'LIQUID' if self.phase_combo.currentText() == "液相" else 'SOLID'

        params = {
            'base_composition': base_composition,
            'solute': solute,
            'x_min': x_min,
            'x_max': x_max,
            'n_points': n_points,
            'solution_phase': solution_phase,
            'extrap_func': self.get_extrap_func(),
            'extrap_model_name': self.extrap_model_combo.currentText(),
            'activity_model': self.activity_model_combo.currentText(),
            'base_str': base_str
        }

        self.worker = PrecipitationWorker('curve', params, self.calculator)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.calculation_finished.connect(self.on_curve_finished)
        self.worker.error_occurred.connect(self.on_error)

        self.on_calculation_started()
        self.results_text.append(f"\n正在计算析出温度曲线 ({n_points} 点)...\n")
        self.worker.start()

    def calculate_multi_solute(self):
        """多溶质计算"""
        alloy_str = self.alloy_input.text().strip()
        solutes_str = self.solutes_input.text().strip()

        composition = parse_composition_static(alloy_str)
        if not composition:
            QMessageBox.warning(self, "错误", "无法解析合金成分")
            return

        composition = {k.upper(): v for k, v in composition.items()}
        solutes = [s.strip().upper() for s in solutes_str.split(',')]

        solution_phase = 'LIQUID' if self.phase_combo.currentText() == "液相" else 'SOLID'

        params = {
            'composition': composition,
            'solutes': solutes,
            'solution_phase': solution_phase,
            'extrap_func': self.get_extrap_func(),
            'extrap_model_name': self.extrap_model_combo.currentText(),
            'activity_model': self.activity_model_combo.currentText(),
            'alloy_str': alloy_str
        }

        self.worker = PrecipitationWorker('multi_solute', params, self.calculator)
        self.worker.calculation_finished.connect(self.on_multi_finished)
        self.worker.error_occurred.connect(self.on_error)

        self.on_calculation_started()
        self.results_text.append("\n正在计算多溶质析出温度...\n")
        self.worker.start()

    def calculate_manual_precipitate(self):
        """手动指定析出相计算"""
        import re

        alloy_str = self.alloy_input.text().strip()
        precipitate_str = self.precipitate_input.text().strip()
        gibbs_str = self.gibbs_input.text().strip()

        composition = parse_composition_static(alloy_str)
        if not composition:
            QMessageBox.warning(self, "错误", "无法解析合金成分")
            return

        composition = {k.upper(): v for k, v in composition.items()}

        # 解析多个析出相（支持逗号或空格分隔）
        precipitates = [p.strip() for p in re.split(r'[,\s]+', precipitate_str) if p.strip()]
        if not precipitates:
            QMessageBox.warning(self, "错误", "请输入析出相")
            return

        # 解析多个吉布斯能
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
        while len(gibbs_energies) < len(precipitates):
            gibbs_energies.append(None)

        solution_phase = 'LIQUID' if self.phase_combo.currentText() == "液相" else 'SOLID'

        params = {
            'composition': composition,
            'precipitates': precipitates,
            'gibbs_energies': gibbs_energies,
            'solution_phase': solution_phase,
            'extrap_func': self.get_extrap_func(),
            'extrap_model_name': self.extrap_model_combo.currentText(),
            'activity_model': self.activity_model_combo.currentText(),
            'alloy_str': alloy_str
        }

        self.worker = PrecipitationWorker('manual_precipitate', params, self.calculator)
        self.worker.calculation_finished.connect(self.on_manual_finished)
        self.worker.error_occurred.connect(self.on_error)

        self.on_calculation_started()
        precip_list = ', '.join(precipitates)
        self.results_text.append(f"\n正在计算手动指定析出相 [{precip_list}] 的析出温度...\n")
        self.worker.start()

    def on_calculation_started(self):
        """计算开始"""
        self.calculate_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

    def on_calculation_finished(self):
        """计算完成"""
        self.calculate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.export_button.setEnabled(True)
        self.worker = None

    def on_progress_updated(self, current, total):
        """更新进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def on_error(self, error_msg):
        """处理错误"""
        self.on_calculation_finished()
        QMessageBox.critical(self, "计算错误", f"错误: {error_msg}")
        self.results_text.append(f"\n错误: {error_msg}\n")

    def cancel_calculation(self):
        """取消计算"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
            self.on_calculation_finished()
            self.results_text.append("\n计算已取消\n")

    def on_single_finished(self, data):
        """单点计算完成"""
        self.on_calculation_finished()

        result = data['result']
        params = data['params']

        self.calculation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        text = "\n" + "=" * 70 + "\n"
        text += f"【计算批次 #{self.calculation_count}】 {timestamp}\n"
        text += "析出温度计算结果\n"
        text += "=" * 70 + "\n\n"

        text += f"合金成分: {params['alloy_str']}\n"
        text += f"溶质元素: {params['solute']}\n"
        text += f"基体状态: {params['solution_phase']}\n"
        text += f"外推模型: {params['extrap_model_name']}\n"
        text += f"活度模型: {params['activity_model']}\n\n"

        if result['status'] == 'success':
            text += f"析出温度: {result['precipitation_temperature']:.1f} K\n"
            text += f"         ({result['precipitation_temperature_celsius']:.1f} C)\n"
            text += f"析出相: {result['precipitating_phase']}\n"
            text += f"溶液相: {result['solution_phase']}\n"

            if 'activity_coefficient_at_Tp' in result:
                text += f"\n析出温度处的活度系数: {result['activity_coefficient_at_Tp']:.4f}\n"
                text += f"析出温度处的活度: {result['activity_at_Tp']:.6f}\n"
        else:
            text += f"状态: {result['status']}\n"
            text += f"说明: {result.get('message', 'N/A')}\n"

        text += "=" * 70 + "\n"

        self.results_text.append(text)

        # 绘制示意图
        self.chart_canvas.axes.clear()
        if result['status'] == 'success':
            T_p = result['precipitation_temperature']
            solute = params['solute']

            # 绘制温度标尺
            T_range = np.linspace(300, 2000, 100)
            self.chart_canvas.axes.axhline(y=T_p, color='r', linestyle='--', linewidth=2,
                                          label=f'T_precip = {T_p:.1f} K')
            self.chart_canvas.axes.fill_between([0, 1], 300, T_p, alpha=0.3, color='blue',
                                               label='过饱和区 (析出)')
            self.chart_canvas.axes.fill_between([0, 1], T_p, 2000, alpha=0.3, color='green',
                                               label='欠饱和区 (溶解)')

            self.chart_canvas.axes.set_ylabel('温度 (K)')
            self.chart_canvas.axes.set_xlim(0, 1)
            self.chart_canvas.axes.set_ylim(300, min(T_p * 1.5, 2500))
            self.chart_canvas.axes.set_title(f'{solute} 在合金中的析出温度')
            self.chart_canvas.axes.legend(loc='best')
            self.chart_canvas.axes.grid(True, alpha=0.3)

            # 隐藏x轴刻度
            self.chart_canvas.axes.set_xticks([])

        self.chart_canvas.draw()

    def on_curve_finished(self, data):
        """曲线计算完成"""
        self.on_calculation_finished()

        result = data['result']
        params = data['params']

        self.calculation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        solute = params['solute']

        text = "\n" + "=" * 70 + "\n"
        text += f"【计算批次 #{self.calculation_count}】 {timestamp}\n"
        text += "析出温度-成分曲线计算结果\n"
        text += "=" * 70 + "\n\n"

        text += f"基础合金: {params['base_str']}\n"
        text += f"溶质元素: {solute}\n"
        text += f"成分范围: {params['x_min']:.4f} ~ {params['x_max']:.4f}\n"
        text += f"外推模型: {params['extrap_model_name']}\n\n"

        text += f"{'X_' + solute:<12} {'T_析出 (K)':<15} {'T_析出 (C)':<15} {'状态'}\n"
        text += "-" * 60 + "\n"

        for i in range(len(result['x_solute'])):
            x = result['x_solute'][i]
            T = result['T_precipitation'][i]
            T_c = result['T_precipitation_celsius'][i]
            status = result['status'][i]

            T_str = f"{T:.1f}" if T else "N/A"
            T_c_str = f"{T_c:.1f}" if T_c else "N/A"
            text += f"{x:<12.4f} {T_str:<15} {T_c_str:<15} {status}\n"

        text += "=" * 70 + "\n"

        self.results_text.append(text)

        # 绘制曲线
        self.chart_canvas.axes.clear()

        x_valid = []
        T_valid = []

        for i in range(len(result['x_solute'])):
            if result['T_precipitation'][i] is not None:
                x_valid.append(result['x_solute'][i])
                T_valid.append(result['T_precipitation'][i])

        if x_valid:
            self.chart_canvas.axes.plot(x_valid, T_valid, 'b-o', linewidth=2, markersize=6,
                                       label='析出温度曲线')

            # 填充区域
            x_arr = np.array(x_valid)
            T_arr = np.array(T_valid)

            self.chart_canvas.axes.fill_between(x_arr, 300, T_arr, alpha=0.2, color='blue',
                                               label='过饱和区')
            self.chart_canvas.axes.fill_between(x_arr, T_arr, max(T_arr)*1.2, alpha=0.2,
                                               color='green', label='欠饱和区')

            self.chart_canvas.axes.set_xlabel(f'X_{solute} (摩尔分数)')
            self.chart_canvas.axes.set_ylabel('析出温度 (K)')
            self.chart_canvas.axes.set_title(f'{solute} 的析出温度 vs. 成分')
            self.chart_canvas.axes.legend(loc='best')
            self.chart_canvas.axes.grid(True, alpha=0.3)

        self.chart_canvas.draw()

    def on_multi_finished(self, data):
        """多溶质计算完成"""
        self.on_calculation_finished()

        result = data['result']
        params = data['params']

        self.calculation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        text = "\n" + "=" * 70 + "\n"
        text += f"【计算批次 #{self.calculation_count}】 {timestamp}\n"
        text += "多溶质析出顺序分析\n"
        text += "=" * 70 + "\n\n"

        text += f"合金成分: {params['alloy_str']}\n"
        text += f"分析溶质: {', '.join(params['solutes'])}\n\n"

        if result.get('precipitation_sequence'):
            text += "析出顺序 (按温度从高到低):\n"
            text += "-" * 40 + "\n"

            for i, solute in enumerate(result['precipitation_sequence']):
                T = result['sorted_temperatures'][i]
                text += f"  {i+1}. {solute}: {T:.1f} K ({T-273.15:.1f} C)\n"

            text += "\n说明: 温度越高的溶质越先析出\n"
        else:
            text += "无法确定析出顺序\n"

        # 各溶质详细信息
        text += "\n详细结果:\n"
        text += "-" * 40 + "\n"

        for solute, detail in result['details'].items():
            text += f"\n{solute}:\n"
            text += f"  状态: {detail['status']}\n"
            if detail['status'] == 'success':
                text += f"  析出温度: {detail['precipitation_temperature']:.1f} K\n"
                text += f"  析出相: {detail['precipitating_phase']}\n"
            else:
                text += f"  说明: {detail.get('message', 'N/A')}\n"

        text += "\n" + "=" * 70 + "\n"

        self.results_text.append(text)

        # 绘制柱状图
        self.chart_canvas.axes.clear()

        if result.get('precipitation_sequence'):
            solutes = result['precipitation_sequence']
            temps = result['sorted_temperatures']

            colors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db', '#9b59b6']
            bar_colors = [colors[i % len(colors)] for i in range(len(solutes))]

            bars = self.chart_canvas.axes.bar(solutes, temps, color=bar_colors)

            # 添加数值标签
            for bar, temp in zip(bars, temps):
                height = bar.get_height()
                self.chart_canvas.axes.text(bar.get_x() + bar.get_width()/2., height,
                                           f'{temp:.0f}K',
                                           ha='center', va='bottom', fontsize=10)

            self.chart_canvas.axes.set_ylabel('析出温度 (K)')
            self.chart_canvas.axes.set_xlabel('溶质元素')
            self.chart_canvas.axes.set_title('各溶质析出温度对比 (按析出顺序排列)')
            self.chart_canvas.axes.grid(True, alpha=0.3, axis='y')

        self.chart_canvas.draw()

    def on_manual_finished(self, data):
        """手动指定析出相计算完成"""
        self.on_calculation_finished()

        result = data['result']
        params = data['params']

        self.calculation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        text = "\n" + "=" * 70 + "\n"
        text += f"【计算批次 #{self.calculation_count}】 {timestamp}\n"
        text += "手动指定析出相的析出温度计算\n"
        text += "=" * 70 + "\n\n"

        text += f"合金成分: {params['alloy_str']}\n"
        text += f"析出相: {', '.join(params['precipitates'])}\n"
        text += f"基体状态: {params['solution_phase']}\n"
        text += f"外推模型: {params['extrap_model_name']}\n"
        text += f"活度模型: {params['activity_model']}\n\n"

        if result.get('precipitation_sequence'):
            text += "析出顺序 (按温度从高到低):\n"
            text += "-" * 40 + "\n"

            for i, phase in enumerate(result['precipitation_sequence']):
                T = result['sorted_temperatures'][i]
                text += f"  {i+1}. {phase}: {T:.1f} K ({T-273.15:.1f} °C)\n"

            text += "\n说明: 温度越高的析出相越先析出\n"
        else:
            text += "无法确定析出顺序\n"

        # 各析出相详细信息
        text += "\n详细结果:\n"
        text += "-" * 40 + "\n"

        for phase, detail in result['details'].items():
            text += f"\n{phase}:\n"
            text += f"  状态: {detail['status']}\n"
            if detail['status'] == 'success':
                text += f"  析出温度: {detail['precipitation_temperature']:.1f} K\n"
                text += f"  析出温度: {detail['precipitation_temperature_celsius']:.1f} °C\n"
                text += f"  基体相: {detail.get('solution_phase', 'N/A')}\n"
                # 显示化合物组成
                if 'compound_composition' in detail:
                    comp_str = ", ".join([f"{k}:{v:.3f}" for k, v in detail['compound_composition'].items()])
                    text += f"  化合物组成: {comp_str}\n"
            else:
                text += f"  说明: {detail.get('message', 'N/A')}\n"

        text += "\n" + "=" * 70 + "\n"

        self.results_text.append(text)

        # 绘制柱状图
        self.chart_canvas.axes.clear()

        if result.get('precipitation_sequence'):
            phases = result['precipitation_sequence']
            temps = result['sorted_temperatures']

            colors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db', '#9b59b6']
            bar_colors = [colors[i % len(colors)] for i in range(len(phases))]

            bars = self.chart_canvas.axes.bar(phases, temps, color=bar_colors)

            # 添加数值标签
            for bar, temp in zip(bars, temps):
                height = bar.get_height()
                self.chart_canvas.axes.text(bar.get_x() + bar.get_width()/2., height,
                                           f'{temp:.0f}K\n({temp-273.15:.0f}°C)',
                                           ha='center', va='bottom', fontsize=9)

            self.chart_canvas.axes.set_ylabel('析出温度 (K)')
            self.chart_canvas.axes.set_xlabel('析出相')
            self.chart_canvas.axes.set_title('各析出相析出温度对比 (按析出顺序排列)')
            self.chart_canvas.axes.grid(True, alpha=0.3, axis='y')

        self.chart_canvas.draw()

    def export_results(self):
        """导出结果"""
        try:
            results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'results')
            os.makedirs(results_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(results_dir, f"precipitation_temp_{timestamp}.txt")

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.results_text.toPlainText())

            QMessageBox.information(self, "导出成功", f"结果已保存到:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "导出错误", f"导出失败:\n{str(e)}")


# 测试代码
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = PrecipitationTemperatureWidget()
    widget.setWindowTitle("析出温度计算 - UEM-Miedema")
    widget.resize(1200, 800)
    widget.show()
    sys.exit(app.exec_())
