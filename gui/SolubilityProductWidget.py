"""
溶解度积计算 Widget
====================
基于Turkdogan经验公式的溶解度积计算与可视化GUI组件

功能:
- 溶解度积计算 (log Ksp)
- 析出温度计算 (基于溶解度积)
- 平衡溶解度计算
- 析出顺序分析
"""

import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton,
                             QSplitter, QGroupBox, QTextEdit,
                             QMessageBox, QRadioButton, QButtonGroup,
                             QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.solubility_product_database import (
    SOLUBILITY_PRODUCTS,
    get_solubility_product_data,
    calculate_log_solubility_product,
    calculate_precipitation_temperature_from_product,
    calculate_equilibrium_content,
    get_precipitation_sequence,
)


class SolubilityProductWorker(QThread):
    """溶解度积计算工作线程"""

    calculation_finished = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, calc_type, params):
        super().__init__()
        self.calc_type = calc_type
        self.params = params

    def run(self):
        try:
            if self.calc_type == 'ksp':
                self._run_ksp()
            elif self.calc_type == 'precip_temp':
                self._run_precip_temp()
            elif self.calc_type == 'equilibrium':
                self._run_equilibrium()
            elif self.calc_type == 'sequence':
                self._run_sequence()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(str(e))

    def _run_ksp(self):
        """计算溶解度积"""
        compound = self.params['compound']
        temperature = self.params['temperature']
        phase = self.params['phase']

        data = get_solubility_product_data(compound, phase)
        if data is None:
            self.error_occurred.emit(f"未找到 {compound} 在 {phase} 中的溶解度积数据")
            return

        log_ksp = calculate_log_solubility_product(compound, phase, temperature)
        if log_ksp is None:
            self.error_occurred.emit("溶解度积计算失败")
            return

        # 计算温度范围内的Ksp曲线
        t_min = data.get('T_min', temperature - 200)
        t_max = data.get('T_max', temperature + 200)
        temps = np.linspace(t_min, t_max, 100)
        log_ksps = [calculate_log_solubility_product(compound, phase, t) for t in temps]

        self.calculation_finished.emit({
            'type': 'ksp',
            'compound': compound,
            'phase': phase,
            'temperature': temperature,
            'log_ksp': log_ksp,
            'ksp': 10 ** log_ksp,
            'data': data,
            'curve_temps': temps.tolist(),
            'curve_log_ksps': log_ksps,
        })

    def _run_precip_temp(self):
        """计算析出温度"""
        compound = self.params['compound']
        metal_wt = self.params['metal_wt']
        nonmetal_wt = self.params['nonmetal_wt']
        phase = self.params['phase']

        data = get_solubility_product_data(compound, phase)
        if data is None:
            self.error_occurred.emit(f"未找到 {compound} 在 {phase} 中的溶解度积数据")
            return

        t_precip = calculate_precipitation_temperature_from_product(
            compound, phase, metal_wt, nonmetal_wt
        )
        if t_precip is None:
            self.error_occurred.emit("析出温度计算失败（含量过高或数据不可用）")
            return

        self.calculation_finished.emit({
            'type': 'precip_temp',
            'compound': compound,
            'phase': phase,
            'metal_wt': metal_wt,
            'nonmetal_wt': nonmetal_wt,
            't_precip_k': t_precip,
            't_precip_c': t_precip - 273.15,
            'data': data,
        })

    def _run_equilibrium(self):
        """计算平衡溶解度"""
        compound = self.params['compound']
        temperature = self.params['temperature']
        fixed_element = self.params['fixed_element']
        fixed_content = self.params['fixed_content']
        phase = self.params['phase']

        data = get_solubility_product_data(compound, phase)
        if data is None:
            self.error_occurred.emit(f"未找到 {compound} 在 {phase} 中的溶解度积数据")
            return

        eq_content = calculate_equilibrium_content(
            compound, phase, temperature, fixed_element, fixed_content
        )
        if eq_content is None:
            self.error_occurred.emit("平衡溶解度计算失败")
            return

        # 计算温度范围内的平衡含量曲线
        t_min = data.get('T_min', temperature - 200)
        t_max = data.get('T_max', temperature + 200)
        temps = np.linspace(t_min, t_max, 100)
        eq_contents = []
        for t in temps:
            c = calculate_equilibrium_content(compound, phase, t, fixed_element, fixed_content)
            eq_contents.append(c if c is not None else 0.0)

        self.calculation_finished.emit({
            'type': 'equilibrium',
            'compound': compound,
            'phase': phase,
            'temperature': temperature,
            'fixed_element': fixed_element,
            'fixed_content': fixed_content,
            'eq_content': eq_content,
            'data': data,
            'curve_temps': temps.tolist(),
            'curve_contents': eq_contents,
        })

    def _run_sequence(self):
        """计算析出顺序"""
        composition = self.params['composition']
        phase = self.params['phase']

        sequence = get_precipitation_sequence(composition, phase)
        if not sequence:
            self.error_occurred.emit("未能计算析出顺序，请检查成分中是否包含可析出的元素对")
            return

        self.calculation_finished.emit({
            'type': 'sequence',
            'phase': phase,
            'composition': composition,
            'sequence': sequence,
        })


class MplCanvas(FigureCanvas):
    """Matplotlib画布"""

    def __init__(self, parent=None, width=7, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)


class SolubilityProductWidget(QWidget):
    """溶解度积计算与可视化组件"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        left_widget = self._create_input_panel()
        right_widget = self._create_results_panel()

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([420, 800])

    def _create_input_panel(self):
        """创建输入面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 计算模式选择
        mode_group = QGroupBox("计算模式")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_button_group = QButtonGroup()

        self.mode_ksp = QRadioButton("溶解度积计算 — log(Ksp) vs 温度")
        self.mode_precip = QRadioButton("析出温度计算 — 由元素含量求 T")
        self.mode_equilibrium = QRadioButton("平衡溶解度计算 — 由温度求平衡含量")
        self.mode_sequence = QRadioButton("析出顺序分析 — 多化合物排序")

        self.mode_button_group.addButton(self.mode_ksp, 1)
        self.mode_button_group.addButton(self.mode_precip, 2)
        self.mode_button_group.addButton(self.mode_equilibrium, 3)
        self.mode_button_group.addButton(self.mode_sequence, 4)

        self.mode_ksp.setChecked(True)
        self.mode_ksp.toggled.connect(self._on_mode_changed)
        self.mode_precip.toggled.connect(self._on_mode_changed)
        self.mode_equilibrium.toggled.connect(self._on_mode_changed)
        self.mode_sequence.toggled.connect(self._on_mode_changed)

        mode_layout.addWidget(self.mode_ksp)
        mode_layout.addWidget(self.mode_precip)
        mode_layout.addWidget(self.mode_equilibrium)
        mode_layout.addWidget(self.mode_sequence)

        layout.addWidget(mode_group)

        # 输入参数
        self.input_group = QGroupBox("输入参数")
        self.input_layout = QGridLayout(self.input_group)
        self.input_layout.setSpacing(10)

        self._create_input_fields()

        layout.addWidget(self.input_group)

        # 化合物信息展示
        self.info_group = QGroupBox("化合物信息")
        info_layout = QVBoxLayout(self.info_group)
        self.info_label = QLabel("选择化合物和基体相后显示公式信息")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("""
            color: #444; font-size: 12px; padding: 4px;
            background: #fafafa; border-radius: 4px;
        """)
        info_layout.addWidget(self.info_label)
        layout.addWidget(self.info_group)

        # 按钮
        button_layout = QHBoxLayout()

        self.calculate_button = QPushButton("计算")
        self.calculate_button.setMinimumHeight(40)
        self.calculate_button.clicked.connect(self._perform_calculation)
        button_layout.addWidget(self.calculate_button)

        self.clear_button = QPushButton("清空结果")
        self.clear_button.setMinimumHeight(40)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; color: white;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        self.clear_button.clicked.connect(self._clear_results)
        button_layout.addWidget(self.clear_button)

        layout.addLayout(button_layout)
        layout.addStretch()

        return widget

    def _get_phase_key(self, phase_text: str) -> str:
        """将下拉框文本转换为相键"""
        phase_map = {
            '奥氏体 (AUSTENITE)': 'AUSTENITE',
            '铁素体 (FERRITE)': 'FERRITE',
            '液相 (LIQUID)': 'LIQUID',
        }
        return phase_map.get(phase_text, 'AUSTENITE')

    def _create_input_fields(self):
        """创建输入字段"""
        # 清空现有字段
        while self.input_layout.count():
            item = self.input_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        row = 0

        if self.mode_ksp.isChecked():
            self._build_phase_and_compound(row)
            row += 2

            self.input_layout.addWidget(QLabel("温度 (K):"), row, 0, Qt.AlignRight)
            self.temp_input = QLineEdit("1473")
            self.temp_input.setPlaceholderText("例如: 1473 (即1200°C)")
            self.input_layout.addWidget(self.temp_input, row, 1)

        elif self.mode_precip.isChecked():
            self._build_phase_and_compound(row)
            row += 2

            # 动态标签 — 根据化合物显示具体元素名
            self.metal_label = QLabel("金属元素含量 (wt%):")
            self.input_layout.addWidget(self.metal_label, row, 0, Qt.AlignRight)
            self.metal_input = QLineEdit("0.02")
            self.metal_input.setPlaceholderText("例如: 0.02")
            self.input_layout.addWidget(self.metal_input, row, 1)
            row += 1

            self.nonmetal_label = QLabel("非金属元素含量 (wt%):")
            self.input_layout.addWidget(self.nonmetal_label, row, 0, Qt.AlignRight)
            self.nonmetal_input = QLineEdit("0.005")
            self.nonmetal_input.setPlaceholderText("例如: 0.005")
            self.input_layout.addWidget(self.nonmetal_input, row, 1)

            # 初始化动态标签
            self._update_element_labels()

        elif self.mode_equilibrium.isChecked():
            self._build_phase_and_compound(row)
            row += 2

            self.input_layout.addWidget(QLabel("温度 (K):"), row, 0, Qt.AlignRight)
            self.temp_input = QLineEdit("1473")
            self.temp_input.setPlaceholderText("例如: 1473")
            self.input_layout.addWidget(self.temp_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("固定元素:"), row, 0, Qt.AlignRight)
            self.fixed_element_combo = QComboBox()
            # 动态选项 — 根据化合物显示实际元素名
            self._build_fixed_element_options()
            self.input_layout.addWidget(self.fixed_element_combo, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("固定元素含量 (wt%):"), row, 0, Qt.AlignRight)
            self.fixed_content_input = QLineEdit("0.02")
            self.fixed_content_input.setPlaceholderText("例如: 0.02")
            self.input_layout.addWidget(self.fixed_content_input, row, 1)

        elif self.mode_sequence.isChecked():
            self.input_layout.addWidget(QLabel("基体相:"), row, 0, Qt.AlignRight)
            self.phase_combo = QComboBox()
            self.phase_combo.addItems(['奥氏体 (AUSTENITE)', '铁素体 (FERRITE)', '液相 (LIQUID)'])
            self.input_layout.addWidget(self.phase_combo, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("成分 (wt%):"), row, 0, Qt.AlignRight | Qt.AlignTop)
            comp_widget = QWidget()
            comp_layout = QGridLayout(comp_widget)
            comp_layout.setContentsMargins(0, 0, 0, 0)
            comp_layout.setSpacing(6)

            self.comp_inputs = {}
            elements = ['TI', 'NB', 'V', 'AL', 'CR', 'MN', 'C', 'N', 'S']
            for i, el in enumerate(elements):
                r, c = divmod(i, 3)
                lbl = QLabel(f"{el}:")
                lbl.setStyleSheet("font-weight: bold;")
                comp_layout.addWidget(lbl, r, c * 2, Qt.AlignRight)
                inp = QLineEdit()
                inp.setPlaceholderText("0")
                inp.setMinimumWidth(90)
                comp_layout.addWidget(inp, r, c * 2 + 1)
                self.comp_inputs[el] = inp

            defaults = {'TI': '0.015', 'NB': '0.025', 'V': '0.05',
                        'C': '0.08', 'N': '0.008', 'AL': '0.03'}
            for el, val in defaults.items():
                if el in self.comp_inputs:
                    self.comp_inputs[el].setText(val)

            self.input_layout.addWidget(comp_widget, row, 1)

        # 更新化合物信息
        self._update_compound_info()

    def _build_phase_and_compound(self, start_row: int):
        """构建基体相和化合物下拉框（前三种模式共用）"""
        self.input_layout.addWidget(QLabel("基体相:"), start_row, 0, Qt.AlignRight)
        self.phase_combo = QComboBox()
        self.phase_combo.addItems(['奥氏体 (AUSTENITE)', '铁素体 (FERRITE)', '液相 (LIQUID)'])
        self.phase_combo.currentIndexChanged.connect(self._on_phase_changed)
        self.input_layout.addWidget(self.phase_combo, start_row, 1)

        self.input_layout.addWidget(QLabel("化合物:"), start_row + 1, 0, Qt.AlignRight)
        self.compound_combo = QComboBox()
        self._update_compound_list()
        self.compound_combo.currentIndexChanged.connect(self._on_compound_changed)
        self.input_layout.addWidget(self.compound_combo, start_row + 1, 1)

    def _on_mode_changed(self):
        """模式改变时更新输入字段"""
        self._create_input_fields()

    def _on_phase_changed(self):
        """相改变时更新化合物列表"""
        self._update_compound_list()
        self._on_compound_changed()

    def _on_compound_changed(self):
        """化合物改变时更新信息和动态标签"""
        self._update_compound_info()
        if self.mode_precip.isChecked():
            self._update_element_labels()
        elif self.mode_equilibrium.isChecked():
            self._build_fixed_element_options()

    def _update_compound_list(self):
        """更新化合物下拉列表"""
        if not hasattr(self, 'compound_combo') or not hasattr(self, 'phase_combo'):
            return
        phase_key = self._get_phase_key(self.phase_combo.currentText())
        compounds = list(SOLUBILITY_PRODUCTS.get(phase_key, {}).keys())
        self.compound_combo.blockSignals(True)
        self.compound_combo.clear()
        self.compound_combo.addItems(compounds)
        self.compound_combo.blockSignals(False)

    def _update_compound_info(self):
        """更新化合物信息展示"""
        if not hasattr(self, 'info_label'):
            return
        if self.mode_sequence.isChecked():
            self.info_group.setVisible(False)
            return

        self.info_group.setVisible(True)
        if not hasattr(self, 'compound_combo') or not hasattr(self, 'phase_combo'):
            return

        compound = self.compound_combo.currentText()
        phase = self._get_phase_key(self.phase_combo.currentText())
        data = get_solubility_product_data(compound, phase)

        if data is None:
            self.info_label.setText("未找到该化合物的数据")
            return

        n_str = f"^{data['n']}" if data['n'] != 1.0 else ""
        formula = f"log[%{data['metal']}][%{data['nonmetal']}]{n_str} = {data['A']} - {data['B']}/T"
        temp_range = f"{data['T_min']}~{data['T_max']} K ({data['T_min']-273.15:.0f}~{data['T_max']-273.15:.0f} °C)"
        ref = data.get('reference', 'N/A')
        notes = data.get('notes', '')

        info_text = (
            f"公式: {formula}\n"
            f"适用温度: {temp_range}\n"
            f"参考文献: {ref}"
        )
        if notes:
            info_text += f"\n备注: {notes}"

        self.info_label.setText(info_text)

    def _update_element_labels(self):
        """根据选中化合物更新金属/非金属标签"""
        if not hasattr(self, 'compound_combo') or not hasattr(self, 'phase_combo'):
            return
        if not hasattr(self, 'metal_label') or not hasattr(self, 'nonmetal_label'):
            return

        compound = self.compound_combo.currentText()
        phase = self._get_phase_key(self.phase_combo.currentText())
        data = get_solubility_product_data(compound, phase)

        if data:
            self.metal_label.setText(f"[{data['metal']}] 含量 (wt%):")
            self.nonmetal_label.setText(f"[{data['nonmetal']}] 含量 (wt%):")
        else:
            self.metal_label.setText("金属元素含量 (wt%):")
            self.nonmetal_label.setText("非金属元素含量 (wt%):")

    def _build_fixed_element_options(self):
        """根据选中化合物构建固定元素选项"""
        if not hasattr(self, 'fixed_element_combo'):
            return
        if not hasattr(self, 'compound_combo') or not hasattr(self, 'phase_combo'):
            return

        compound = self.compound_combo.currentText()
        phase = self._get_phase_key(self.phase_combo.currentText())
        data = get_solubility_product_data(compound, phase)

        self.fixed_element_combo.blockSignals(True)
        self.fixed_element_combo.clear()
        if data:
            self.fixed_element_combo.addItems([
                f"metal — 固定 [{data['metal']}] 含量",
                f"nonmetal — 固定 [{data['nonmetal']}] 含量",
            ])
        else:
            self.fixed_element_combo.addItems([
                'metal (金属元素)',
                'nonmetal (非金属元素)',
            ])
        self.fixed_element_combo.blockSignals(False)

    def _create_results_panel(self):
        """创建结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 结果文本
        results_group = QGroupBox("计算结果")
        results_layout = QVBoxLayout(results_group)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(180)
        self.results_text.setLineWrapMode(QTextEdit.NoWrap)

        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.results_text.setFont(font)

        results_layout.addWidget(self.results_text)
        layout.addWidget(results_group)

        # 图表
        chart_group = QGroupBox("可视化")
        chart_layout = QVBoxLayout(chart_group)

        self.chart_canvas = MplCanvas(self, width=7, height=5, dpi=100)
        chart_layout.addWidget(self.chart_canvas)

        layout.addWidget(chart_group)

        return widget

    def _clear_results(self):
        """清空计算结果和图表"""
        self.results_text.clear()
        self.chart_canvas.axes.clear()
        self.chart_canvas.draw()

    def _perform_calculation(self):
        """执行计算"""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "提示", "计算正在进行中...")
            return

        try:
            if self.mode_ksp.isChecked():
                self._calc_ksp()
            elif self.mode_precip.isChecked():
                self._calc_precip_temp()
            elif self.mode_equilibrium.isChecked():
                self._calc_equilibrium()
            elif self.mode_sequence.isChecked():
                self._calc_sequence()
        except ValueError as e:
            QMessageBox.critical(self, "输入错误", f"参数格式错误：{e}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算失败：{e}")

    def _calc_ksp(self):
        """溶解度积计算"""
        params = {
            'compound': self.compound_combo.currentText(),
            'temperature': float(self.temp_input.text()),
            'phase': self._get_phase_key(self.phase_combo.currentText()),
        }

        self.worker = SolubilityProductWorker('ksp', params)
        self.worker.calculation_finished.connect(self._on_calculation_finished)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _calc_precip_temp(self):
        """析出温度计算"""
        params = {
            'compound': self.compound_combo.currentText(),
            'metal_wt': float(self.metal_input.text()),
            'nonmetal_wt': float(self.nonmetal_input.text()),
            'phase': self._get_phase_key(self.phase_combo.currentText()),
        }

        self.worker = SolubilityProductWorker('precip_temp', params)
        self.worker.calculation_finished.connect(self._on_calculation_finished)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _calc_equilibrium(self):
        """平衡溶解度计算"""
        fixed_text = self.fixed_element_combo.currentText()
        fixed_element = 'metal' if fixed_text.startswith('metal') else 'nonmetal'

        params = {
            'compound': self.compound_combo.currentText(),
            'temperature': float(self.temp_input.text()),
            'fixed_element': fixed_element,
            'fixed_content': float(self.fixed_content_input.text()),
            'phase': self._get_phase_key(self.phase_combo.currentText()),
        }

        self.worker = SolubilityProductWorker('equilibrium', params)
        self.worker.calculation_finished.connect(self._on_calculation_finished)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _calc_sequence(self):
        """析出顺序分析"""
        composition = {}
        for el, inp in self.comp_inputs.items():
            text = inp.text().strip()
            if text:
                val = float(text)
                if val > 0:
                    composition[el] = val

        if not composition:
            QMessageBox.warning(self, "提示", "请至少输入一种元素的含量")
            return

        params = {
            'composition': composition,
            'phase': self._get_phase_key(self.phase_combo.currentText()),
        }

        self.worker = SolubilityProductWorker('sequence', params)
        self.worker.calculation_finished.connect(self._on_calculation_finished)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _on_error(self, msg: str):
        """计算错误处理"""
        QMessageBox.critical(self, "计算错误", msg)

    def _on_calculation_finished(self, result: dict):
        """计算完成处理"""
        calc_type = result['type']

        if calc_type == 'ksp':
            self._display_ksp_result(result)
        elif calc_type == 'precip_temp':
            self._display_precip_temp_result(result)
        elif calc_type == 'equilibrium':
            self._display_equilibrium_result(result)
        elif calc_type == 'sequence':
            self._display_sequence_result(result)

    def _display_ksp_result(self, result: dict):
        """显示溶解度积结果"""
        data = result['data']
        T = result['temperature']
        T_c = T - 273.15

        n_str = f"^{data['n']}" if data['n'] != 1.0 else ""
        text = (
            f"{'='*60}\n"
            f" 溶解度积计算结果\n"
            f"{'='*60}\n"
            f" 化合物: {result['compound']}\n"
            f" 基体相: {result['phase']}\n"
            f" 温度:   {T:.1f} K ({T_c:.1f} °C)\n"
            f"{'-'*60}\n"
            f" log(Ksp) = {result['log_ksp']:.4f}\n"
            f" Ksp      = {result['ksp']:.4e}\n"
            f"{'-'*60}\n"
            f" 经验公式: log[%{data['metal']}][%{data['nonmetal']}]{n_str}"
            f" = {data['A']} - {data['B']}/T\n"
            f" 适用温度: {data['T_min']}-{data['T_max']} K\n"
            f" 参考文献: {data.get('reference', 'N/A')}\n"
            f"{'='*60}\n"
        )
        self.results_text.setPlainText(text)

        # 绘制Ksp-温度曲线
        self.chart_canvas.axes.clear()
        temps_c = [t - 273.15 for t in result['curve_temps']]
        self.chart_canvas.axes.plot(temps_c, result['curve_log_ksps'], 'b-', linewidth=2)
        self.chart_canvas.axes.axvline(x=T_c, color='r', linestyle='--', alpha=0.7,
                                       label=f'T = {T_c:.0f}°C')
        self.chart_canvas.axes.axhline(y=result['log_ksp'], color='r', linestyle=':', alpha=0.5)
        self.chart_canvas.axes.plot(T_c, result['log_ksp'], 'ro', markersize=8)
        self.chart_canvas.axes.set_xlabel('温度 (°C)')
        self.chart_canvas.axes.set_ylabel(f'log Ksp ({result["compound"]})')
        self.chart_canvas.axes.set_title(f'{result["compound"]} 在 {result["phase"]} 中的溶解度积')
        self.chart_canvas.axes.legend()
        self.chart_canvas.axes.grid(True, alpha=0.3)
        self.chart_canvas.fig.tight_layout()
        self.chart_canvas.draw()

    def _display_precip_temp_result(self, result: dict):
        """显示析出温度结果"""
        data = result['data']
        n_str = f"^{data['n']}" if data['n'] != 1.0 else ""

        text = (
            f"{'='*60}\n"
            f" 析出温度计算结果（溶解度积法）\n"
            f"{'='*60}\n"
            f" 化合物:       {result['compound']}\n"
            f" 基体相:       {result['phase']}\n"
            f" [{data['metal']}] 含量:  {result['metal_wt']} wt%\n"
            f" [{data['nonmetal']}] 含量: {result['nonmetal_wt']} wt%\n"
            f"{'-'*60}\n"
            f" 析出温度 = {result['t_precip_k']:.1f} K ({result['t_precip_c']:.1f} °C)\n"
            f"{'-'*60}\n"
            f" 经验公式: log[%{data['metal']}][%{data['nonmetal']}]{n_str}"
            f" = {data['A']} - {data['B']}/T\n"
            f" T_precip = {data['B']} / ({data['A']} - log([%M][%X]{n_str}))\n"
            f" 参考文献: {data.get('reference', 'N/A')}\n"
            f"{'='*60}\n"
        )
        self.results_text.setPlainText(text)

        # 清空图表
        self.chart_canvas.axes.clear()
        self.chart_canvas.axes.text(
            0.5, 0.5,
            f"{result['compound']} 析出温度\n{result['t_precip_k']:.1f} K ({result['t_precip_c']:.1f} °C)",
            transform=self.chart_canvas.axes.transAxes,
            ha='center', va='center', fontsize=16, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.8)
        )
        self.chart_canvas.axes.set_axis_off()
        self.chart_canvas.fig.tight_layout()
        self.chart_canvas.draw()

    def _display_equilibrium_result(self, result: dict):
        """显示平衡溶解度结果"""
        data = result['data']
        T = result['temperature']
        T_c = T - 273.15

        if result['fixed_element'] == 'metal':
            fixed_el = data['metal']
            calc_el = data['nonmetal']
        else:
            fixed_el = data['nonmetal']
            calc_el = data['metal']

        text = (
            f"{'='*60}\n"
            f" 平衡溶解度计算结果\n"
            f"{'='*60}\n"
            f" 化合物: {result['compound']}\n"
            f" 基体相: {result['phase']}\n"
            f" 温度:   {T:.1f} K ({T_c:.1f} °C)\n"
            f" 固定:   [{fixed_el}] = {result['fixed_content']} wt%\n"
            f"{'-'*60}\n"
            f" [{calc_el}] 平衡含量 = {result['eq_content']:.6f} wt%\n"
        )
        if result['eq_content'] < 0.01:
            text += f"                  = {result['eq_content']*10000:.2f} ppm\n"
        text += (
            f"{'-'*60}\n"
            f" 参考文献: {data.get('reference', 'N/A')}\n"
            f"{'='*60}\n"
        )
        self.results_text.setPlainText(text)

        # 绘制平衡含量-温度曲线
        self.chart_canvas.axes.clear()
        temps_c = [t - 273.15 for t in result['curve_temps']]
        self.chart_canvas.axes.plot(temps_c, result['curve_contents'], 'b-', linewidth=2)
        self.chart_canvas.axes.axvline(x=T_c, color='r', linestyle='--', alpha=0.7)
        self.chart_canvas.axes.plot(T_c, result['eq_content'], 'ro', markersize=8,
                                    label=f'{T_c:.0f}°C: {result["eq_content"]:.4e} wt%')
        self.chart_canvas.axes.set_xlabel('温度 (°C)')
        self.chart_canvas.axes.set_ylabel(f'[{calc_el}] 平衡含量 (wt%)')
        self.chart_canvas.axes.set_title(
            f'{result["compound"]} 中 [{calc_el}] 的平衡含量 ([{fixed_el}]={result["fixed_content"]}wt%)')
        self.chart_canvas.axes.legend()
        self.chart_canvas.axes.grid(True, alpha=0.3)
        self.chart_canvas.fig.tight_layout()
        self.chart_canvas.draw()

    def _display_sequence_result(self, result: dict):
        """显示析出顺序结果"""
        sequence = result['sequence']
        comp = result['composition']

        text = (
            f"{'='*60}\n"
            f" 析出顺序分析结果\n"
            f"{'='*60}\n"
            f" 基体相: {result['phase']}\n"
            f" 成分 (wt%): {comp}\n"
            f"{'-'*60}\n"
            f" {'序号':<6}{'化合物':<10}{'析出温度(K)':<14}{'析出温度(°C)':<14}\n"
            f" {'-'*44}\n"
        )
        for i, (compound, t_k) in enumerate(sequence, 1):
            t_c = t_k - 273.15
            text += f" {i:<6}{compound:<10}{t_k:<14.1f}{t_c:<14.1f}\n"

        text += f"{'='*60}\n"
        self.results_text.setPlainText(text)

        # 绘制析出温度柱状图
        self.chart_canvas.axes.clear()
        compounds = [s[0] for s in sequence]
        temps_c = [s[1] - 273.15 for s in sequence]
        colors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#3498db',
                  '#9b59b6', '#1abc9c', '#34495e', '#95a5a6']
        bar_colors = [colors[i % len(colors)] for i in range(len(compounds))]

        bars = self.chart_canvas.axes.bar(compounds, temps_c, color=bar_colors, edgecolor='white')

        for bar, tc in zip(bars, temps_c):
            self.chart_canvas.axes.text(
                bar.get_x() + bar.get_width() / 2., bar.get_height() + 5,
                f'{tc:.0f}°C', ha='center', va='bottom', fontsize=9, fontweight='bold'
            )

        self.chart_canvas.axes.set_xlabel('化合物')
        self.chart_canvas.axes.set_ylabel('析出温度 (°C)')
        self.chart_canvas.axes.set_title(f'析出顺序 ({result["phase"]})')
        self.chart_canvas.axes.grid(True, alpha=0.3, axis='y')
        self.chart_canvas.fig.tight_layout()
        self.chart_canvas.draw()
