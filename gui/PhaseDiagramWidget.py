"""
Phase Diagram Widget
====================
相图计算与可视化GUI组件

功能:
- 计算液相线和固相线温度
- 绘制二元相图
- 绘制液相线/固相线随成分变化的曲线

作者: Claude
日期: 2025-11-08
"""

import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton,
                             QSplitter, QFrame, QGroupBox, QTextEdit,
                             QMessageBox, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils import parse_composition_static
from calculations.phase_diagram import PhaseDiagram


class MplCanvas(FigureCanvas):
    """Matplotlib画布类"""

    def __init__(self, parent=None, width=7, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)


class PhaseDiagramWidget(QWidget):
    """相图计算与可视化组件"""

    def __init__(self):
        super().__init__()

        self.phase_calc = PhaseDiagram()
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

        # 初始化图表
        self.init_chart()

    def create_input_panel(self):
        """创建输入面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 计算模式选择
        mode_group = QGroupBox("计算模式")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_button_group = QButtonGroup()

        self.mode_single = QRadioButton("单点计算（液相线/固相线温度）")
        self.mode_binary = QRadioButton("二元相图")
        self.mode_curve = QRadioButton("成分变化曲线")

        self.mode_button_group.addButton(self.mode_single, 1)
        self.mode_button_group.addButton(self.mode_binary, 2)
        self.mode_button_group.addButton(self.mode_curve, 3)

        self.mode_single.setChecked(True)
        self.mode_single.toggled.connect(self.on_mode_changed)
        self.mode_binary.toggled.connect(self.on_mode_changed)
        self.mode_curve.toggled.connect(self.on_mode_changed)

        mode_layout.addWidget(self.mode_single)
        mode_layout.addWidget(self.mode_binary)
        mode_layout.addWidget(self.mode_curve)

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
        row += 1

        # 固相模型类型
        model_layout.addWidget(QLabel("固相模型:"), row, 0, Qt.AlignRight)
        self.solid_model_combo = QComboBox()
        self.solid_model_combo.addItems(["PURE_SOLID", "SOLID_SOLUTION"])
        self.solid_model_combo.setToolTip(
            "PURE_SOLID: 液相与纯固相平衡（共晶系统）\n"
            "SOLID_SOLUTION: 液相与固溶体平衡（连续固溶体）"
        )
        model_layout.addWidget(self.solid_model_combo, row, 1)

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

        self.export_button = QPushButton("导出结果")
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

        # 单点计算模式
        if self.mode_single.isChecked():
            self.input_layout.addWidget(QLabel("合金成分:"), row, 0, Qt.AlignRight)
            self.alloy_input = QLineEdit("Fe0.97C0.03")
            self.alloy_input.setPlaceholderText("例如: Fe0.97C0.03")
            self.input_layout.addWidget(self.alloy_input, row, 1)

        # 二元相图模式
        elif self.mode_binary.isChecked():
            self.input_layout.addWidget(QLabel("组分A:"), row, 0, Qt.AlignRight)
            self.component_a_input = QLineEdit("FE")
            self.input_layout.addWidget(self.component_a_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("组分B:"), row, 0, Qt.AlignRight)
            self.component_b_input = QLineEdit("C")
            self.input_layout.addWidget(self.component_b_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("采样点数:"), row, 0, Qt.AlignRight)
            self.n_points_input = QLineEdit("20")
            self.input_layout.addWidget(self.n_points_input, row, 1)

        # 成分变化曲线模式
        elif self.mode_curve.isChecked():
            self.input_layout.addWidget(QLabel("基础成分:"), row, 0, Qt.AlignRight)
            self.base_comp_input = QLineEdit("Fe0.97")
            self.base_comp_input.setPlaceholderText("例如: Fe0.97 (不含变化组分)")
            self.input_layout.addWidget(self.base_comp_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("变化组分:"), row, 0, Qt.AlignRight)
            self.var_component_input = QLineEdit("C")
            self.input_layout.addWidget(self.var_component_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("X_min:"), row, 0, Qt.AlignRight)
            self.x_min_input = QLineEdit("0.0")
            self.input_layout.addWidget(self.x_min_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("X_max:"), row, 0, Qt.AlignRight)
            self.x_max_input = QLineEdit("0.1")
            self.input_layout.addWidget(self.x_max_input, row, 1)
            row += 1

            self.input_layout.addWidget(QLabel("采样点数:"), row, 0, Qt.AlignRight)
            self.n_points_input_curve = QLineEdit("20")
            self.input_layout.addWidget(self.n_points_input_curve, row, 1)

    def on_mode_changed(self):
        """模式切换时更新输入字段"""
        self.create_input_fields()

    def create_results_panel(self):
        """创建结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 结果文本
        results_group = QGroupBox("计算结果")
        results_layout = QVBoxLayout(results_group)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(150)
        results_layout.addWidget(self.results_text)

        layout.addWidget(results_group)

        # 相图绘制区域
        chart_group = QGroupBox("相图可视化")
        chart_layout = QVBoxLayout(chart_group)

        self.chart_canvas = MplCanvas(self, width=7, height=5, dpi=100)
        chart_layout.addWidget(self.chart_canvas)

        layout.addWidget(chart_group)

        return widget

    def init_chart(self):
        """初始化图表"""
        self.chart_canvas.axes.clear()
        self.chart_canvas.axes.set_title("相图")
        self.chart_canvas.axes.set_xlabel("成分")
        self.chart_canvas.axes.set_ylabel("温度 (K)")
        self.chart_canvas.axes.grid(True, alpha=0.3)
        self.chart_canvas.draw()

    def perform_calculation(self):
        """执行计算"""
        try:
            if self.mode_single.isChecked():
                self.calculate_single_point()
            elif self.mode_binary.isChecked():
                self.calculate_binary_diagram()
            elif self.mode_curve.isChecked():
                self.calculate_composition_curve()

            self.export_button.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "计算错误", f"计算过程中发生错误:\n{str(e)}")
            self.results_text.setText(f"错误: {str(e)}")

    def calculate_single_point(self):
        """计算单点液相线和固相线温度"""
        alloy_str = self.alloy_input.text().strip()
        if not alloy_str:
            QMessageBox.warning(self, "输入错误", "请输入合金成分！")
            return

        composition = parse_composition_static(alloy_str)
        if not composition:
            QMessageBox.warning(self, "输入错误", "无法解析合金成分！")
            return

        # 获取模型参数
        extrap_model = self.extrap_model_combo.currentText()
        activity_model = self.activity_model_combo.currentText()
        solid_model_type = self.solid_model_combo.currentText()

        # 计算
        T_liquidus = self.phase_calc.calculate_liquidus_temperature(
            composition, extrap_model, activity_model, solid_model_type
        )
        T_solidus = self.phase_calc.calculate_solidus_temperature(
            composition, extrap_model, activity_model, solid_model_type
        )

        # 显示结果
        text_output = "=" * 70 + "\n"
        text_output += "液相线/固相线温度计算结果\n"
        text_output += "=" * 70 + "\n\n"
        text_output += f"合金成分: {composition}\n"
        text_output += f"外推模型: {extrap_model}\n"
        text_output += f"活度模型: {activity_model}\n"
        text_output += f"固相模型: {solid_model_type}\n\n"

        if T_liquidus:
            text_output += f"液相线温度: {T_liquidus:.2f} K ({T_liquidus-273.15:.2f} °C)\n"
        else:
            text_output += "液相线温度: 未计算成功\n"

        if T_solidus:
            text_output += f"固相线温度: {T_solidus:.2f} K ({T_solidus-273.15:.2f} °C)\n"
        else:
            text_output += "固相线温度: 未计算成功\n"

        if T_liquidus and T_solidus:
            text_output += f"\n凝固温度区间: {T_liquidus - T_solidus:.2f} K\n"

        text_output += "=" * 70 + "\n"

        self.results_text.setText(text_output)

        # 绘制示意图
        self.chart_canvas.axes.clear()
        if T_liquidus and T_solidus:
            self.chart_canvas.axes.barh(['固相线', '液相线'],
                                        [T_solidus, T_liquidus],
                                        color=['#3498db', '#e74c3c'])
            self.chart_canvas.axes.set_xlabel('温度 (K)')
            self.chart_canvas.axes.set_title('液相线与固相线温度')
            self.chart_canvas.axes.grid(True, alpha=0.3, axis='x')
        self.chart_canvas.draw()

    def calculate_binary_diagram(self):
        """计算二元相图"""
        comp_a = self.component_a_input.text().strip().upper()
        comp_b = self.component_b_input.text().strip().upper()
        n_points = int(self.n_points_input.text())

        if not comp_a or not comp_b:
            QMessageBox.warning(self, "输入错误", "请输入组分A和组分B！")
            return

        # 获取模型参数
        extrap_model = self.extrap_model_combo.currentText()
        activity_model = self.activity_model_combo.currentText()
        solid_model_type = self.solid_model_combo.currentText()

        # 计算相图
        self.results_text.setText("正在计算二元相图，请稍候...")
        phase_data = self.phase_calc.calculate_binary_phase_diagram(
            comp_a, comp_b, n_points=n_points,
            extrapolation_model=extrap_model,
            activity_model=activity_model,
            solid_model_type=solid_model_type
        )

        # 显示结果
        text_output = "=" * 70 + "\n"
        text_output += f"二元相图: {comp_a}-{comp_b}\n"
        text_output += "=" * 70 + "\n\n"
        text_output += f"外推模型: {extrap_model}\n"
        text_output += f"活度模型: {activity_model}\n"
        text_output += f"固相模型: {solid_model_type}\n\n"
        text_output += f"{'X_' + comp_b:<10} {'T_liquidus (K)':<15} {'T_solidus (K)':<15}\n"
        text_output += "-" * 70 + "\n"

        for i, x_b in enumerate(phase_data['x_b']):
            T_liq = phase_data['T_liquidus'][i]
            T_sol = phase_data['T_solidus'][i]
            text_output += f"{x_b:<10.3f} "
            text_output += f"{T_liq if T_liq else 'N/A':<15} "
            text_output += f"{T_sol if T_sol else 'N/A':<15}\n"

        text_output += "=" * 70 + "\n"
        self.results_text.setText(text_output)

        # 绘制相图
        self.chart_canvas.axes.clear()

        x_b = phase_data['x_b']
        T_liq = [T if T else None for T in phase_data['T_liquidus']]
        T_sol = [T if T else None for T in phase_data['T_solidus']]

        self.chart_canvas.axes.plot(x_b, T_liq, 'r-o', label='液相线', linewidth=2)
        self.chart_canvas.axes.plot(x_b, T_sol, 'b-s', label='固相线', linewidth=2)

        self.chart_canvas.axes.set_xlabel(f'X_{comp_b} (摩尔分数)')
        self.chart_canvas.axes.set_ylabel('温度 (K)')
        self.chart_canvas.axes.set_title(f'{comp_a}-{comp_b} 二元相图')
        self.chart_canvas.axes.legend()
        self.chart_canvas.axes.grid(True, alpha=0.3)

        self.chart_canvas.draw()

    def calculate_composition_curve(self):
        """计算成分变化曲线"""
        base_comp_str = self.base_comp_input.text().strip()
        var_comp = self.var_component_input.text().strip().upper()
        x_min = float(self.x_min_input.text())
        x_max = float(self.x_max_input.text())
        n_points = int(self.n_points_input_curve.text())

        base_composition = parse_composition_static(base_comp_str) if base_comp_str else {}

        # 获取模型参数
        extrap_model = self.extrap_model_combo.currentText()
        activity_model = self.activity_model_combo.currentText()
        solid_model_type = self.solid_model_combo.currentText()

        # 计算曲线
        self.results_text.setText("正在计算成分变化曲线，请稍候...")
        curve_data = self.phase_calc.calculate_phase_diagram_curve(
            base_composition=base_composition,
            variable_component=var_comp,
            x_min=x_min,
            x_max=x_max,
            n_points=n_points,
            extrapolation_model=extrap_model,
            activity_model=activity_model,
            solid_model_type=solid_model_type
        )

        # 显示结果
        text_output = "=" * 70 + "\n"
        text_output += f"成分变化曲线: 变化组分 {var_comp}\n"
        text_output += "=" * 70 + "\n\n"
        text_output += f"基础成分: {base_composition}\n"
        text_output += f"外推模型: {extrap_model}\n"
        text_output += f"活度模型: {activity_model}\n"
        text_output += f"固相模型: {solid_model_type}\n\n"
        text_output += f"{'X_' + var_comp:<10} {'T_liquidus (K)':<15} {'T_solidus (K)':<15}\n"
        text_output += "-" * 70 + "\n"

        for i, x in enumerate(curve_data['x']):
            T_liq = curve_data['T_liquidus'][i]
            T_sol = curve_data['T_solidus'][i]
            text_output += f"{x:<10.3f} "
            text_output += f"{T_liq if T_liq else 'N/A':<15} "
            text_output += f"{T_sol if T_sol else 'N/A':<15}\n"

        text_output += "=" * 70 + "\n"
        self.results_text.setText(text_output)

        # 绘制曲线
        self.chart_canvas.axes.clear()

        x_values = curve_data['x']
        T_liq = [T if T else None for T in curve_data['T_liquidus']]
        T_sol = [T if T else None for T in curve_data['T_solidus']]

        self.chart_canvas.axes.plot(x_values, T_liq, 'r-o', label='液相线', linewidth=2)
        self.chart_canvas.axes.plot(x_values, T_sol, 'b-s', label='固相线', linewidth=2)

        self.chart_canvas.axes.set_xlabel(f'X_{var_comp} (摩尔分数)')
        self.chart_canvas.axes.set_ylabel('温度 (K)')
        self.chart_canvas.axes.set_title(f'液相线/固相线 vs. {var_comp} 含量')
        self.chart_canvas.axes.legend()
        self.chart_canvas.axes.grid(True, alpha=0.3)

        self.chart_canvas.draw()

    def export_results(self):
        """导出结果"""
        try:
            results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'results')
            os.makedirs(results_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(results_dir, f"phase_diagram_{timestamp}.txt")

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
    widget = PhaseDiagramWidget()
    widget.setWindowTitle("相图计算")
    widget.resize(1200, 800)
    widget.show()
    sys.exit(app.exec_())
