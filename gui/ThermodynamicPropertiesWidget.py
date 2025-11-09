"""
Thermodynamic Properties Widget
================================
热力学性质计算GUI组件

功能:
- 计算活度、化学势、摩尔焓、吉布斯自由能等热力学性质
- 可视化显示计算结果
- 支持导出数据

作者: Claude
日期: 2025-11-08
"""

import sys
import os
import math
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton,
                             QSplitter, QFrame, QGroupBox, QTextEdit,
                             QMessageBox, QTableWidget, QTableWidgetItem)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils import parse_composition_static
from calculations.thermodynamic_properties import ThermodynamicProperties


class MplCanvas(FigureCanvas):
    """Matplotlib画布类"""

    def __init__(self, parent=None, width=7, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)


class ThermodynamicPropertiesWidget(QWidget):
    """热力学性质计算组件"""

    def __init__(self):
        super().__init__()

        self.thermo_calc = ThermodynamicProperties()
        self.results_data = None
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

        # 输入参数分组
        input_group = QGroupBox("热力学性质计算 - 输入参数")
        input_layout = QGridLayout(input_group)
        input_layout.setSpacing(15)
        input_layout.setContentsMargins(20, 25, 20, 20)

        row = 0

        # 合金成分
        input_layout.addWidget(QLabel("合金成分:"), row, 0, Qt.AlignRight)
        self.alloy_input = QLineEdit("Fe0.70C0.03Si0.27")
        self.alloy_input.setPlaceholderText("例如: Fe0.7C0.03Si0.27")
        self.alloy_input.setToolTip("输入格式: 元素符号+摩尔分数")
        input_layout.addWidget(self.alloy_input, row, 1)
        row += 1

        # 温度
        input_layout.addWidget(QLabel("温度 (K):"), row, 0, Qt.AlignRight)
        self.temperature_input = QLineEdit("1873")
        self.temperature_input.setPlaceholderText("温度 (K)")
        input_layout.addWidget(self.temperature_input, row, 1)
        row += 1

        # 相态
        input_layout.addWidget(QLabel("相态:"), row, 0, Qt.AlignRight)
        self.phase_combo = QComboBox()
        self.phase_combo.addItems(["liquid", "solid"])
        input_layout.addWidget(self.phase_combo, row, 1)
        row += 1

        # 溶剂
        input_layout.addWidget(QLabel("溶剂 (可选):"), row, 0, Qt.AlignRight)
        self.solvent_input = QLineEdit("")
        self.solvent_input.setPlaceholderText("留空自动选择")
        input_layout.addWidget(self.solvent_input, row, 1)
        row += 1

        # 外推模型
        input_layout.addWidget(QLabel("外推模型:"), row, 0, Qt.AlignRight)
        self.extrap_model_combo = QComboBox()
        self.extrap_model_combo.addItems([
            "UEM1", "UEM2", "UEM2-Adv", "GSM",
            "Muggianu", "Toop-Muggianu", "Toop-Kohler"
        ])
        input_layout.addWidget(self.extrap_model_combo, row, 1)
        row += 1

        # 活度模型
        input_layout.addWidget(QLabel("活度模型:"), row, 0, Qt.AlignRight)
        self.activity_model_combo = QComboBox()
        self.activity_model_combo.addItems(["Wagner", "Darken", "Elliott"])
        input_layout.addWidget(self.activity_model_combo, row, 1)
        row += 1

        layout.addWidget(input_group)

        # 计算按钮
        button_layout = QHBoxLayout()
        self.calculate_button = QPushButton("计算")
        self.calculate_button.setMinimumHeight(40)
        self.calculate_button.clicked.connect(self.perform_calculation)
        button_layout.addWidget(self.calculate_button)

        self.clear_button = QPushButton("清除历史")
        self.clear_button.setMinimumHeight(40)
        self.clear_button.clicked.connect(self.clear_history)
        button_layout.addWidget(self.clear_button)

        self.export_button = QPushButton("导出结果")
        self.export_button.setMinimumHeight(40)
        self.export_button.clicked.connect(self.export_results)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)

        layout.addLayout(button_layout)
        layout.addStretch()

        return widget

    def create_results_panel(self):
        """创建结果面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 结果文本
        results_group = QGroupBox("计算结果")
        results_layout = QVBoxLayout(results_group)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(200)
        results_layout.addWidget(self.results_text)

        layout.addWidget(results_group)

        # 结果表格
        table_group = QGroupBox("组分性质详细数据")
        table_layout = QVBoxLayout(table_group)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "组分", "摩尔分数", "ln(γ)", "活度系数 γ", "活度 a", "化学势 μ (kJ/mol)"
        ])
        table_layout.addWidget(self.results_table)

        layout.addWidget(table_group)

        return widget

    def perform_calculation(self):
        """执行计算"""
        try:
            # 解析输入
            alloy_str = self.alloy_input.text().strip()
            if not alloy_str:
                QMessageBox.warning(self, "输入错误", "请输入合金成分！")
                return

            composition = parse_composition_static(alloy_str)
            if not composition:
                QMessageBox.warning(self, "输入错误", "无法解析合金成分！")
                return

            temperature = float(self.temperature_input.text())
            phase_state = self.phase_combo.currentText()
            solvent = self.solvent_input.text().strip() or None
            extrap_model = self.extrap_model_combo.currentText()
            activity_model = self.activity_model_combo.currentText()

            # 显示计算中
            self.results_text.setText("正在计算中，请稍候...")
            self.calculate_button.setEnabled(False)

            # 执行计算
            results = self.thermo_calc.calculate_all_properties(
                composition=composition,
                temperature=temperature,
                phase_state=phase_state,
                solvent=solvent,
                extrapolation_model=extrap_model,
                activity_model=activity_model
            )

            self.results_data = results

            # 显示结果
            self.display_results(results, composition, temperature, phase_state)

            # 启用导出按钮
            self.export_button.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "计算错误", f"计算过程中发生错误:\n{str(e)}")
            self.results_text.setText(f"错误: {str(e)}")

        finally:
            self.calculate_button.setEnabled(True)

    def display_results(self, results, composition, temperature, phase_state):
        """显示计算结果"""
        from datetime import datetime

        # 1. 显示文本结果 - 追加而非覆盖
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        text_output = "\n" + "=" * 70 + "\n"
        text_output += f"计算时间: {timestamp}\n"
        text_output += "热力学性质计算结果\n"
        text_output += "=" * 70 + "\n\n"

        text_output += f"合金成分: {composition}\n"
        text_output += f"温度: {temperature} K ({temperature-273.15:.2f} °C)\n"
        text_output += f"相态: {phase_state}\n\n"

        text_output += "=" * 70 + "\n"
        text_output += "合金整体性质:\n"
        text_output += "=" * 70 + "\n"

        alloy_props = results['alloy_properties']
        if alloy_props.get('H') is not None:
            text_output += f"摩尔焓 (H):          {alloy_props['H']/1000:.2f} kJ/mol\n"
        if alloy_props.get('G') is not None:
            text_output += f"吉布斯自由能 (G):    {alloy_props['G']/1000:.2f} kJ/mol\n"
        if alloy_props.get('S') is not None:
            text_output += f"摩尔熵 (S):          {alloy_props['S']:.4f} J/(mol·K)\n"
        if alloy_props.get('H') and alloy_props.get('G'):
            text_output += f"T×S:                {(alloy_props['H'] - alloy_props['G'])/1000:.2f} kJ/mol\n"

        text_output += "\n" + "=" * 70 + "\n"
        text_output += "组分性质:\n"
        text_output += "=" * 70 + "\n"
        text_output += f"{'组分':<8} {'X_i':<10} {'ln(γ_i)':<12} {'γ_i':<12} {'a_i':<12} {'μ_i (kJ/mol)':<15}\n"
        text_output += "-" * 70 + "\n"

        # 2. 填充表格 - 追加行而非覆盖
        comp_props = results['component_properties']

        # 获取当前行数，准备追加
        current_row_count = self.results_table.rowCount()

        # 添加新行
        self.results_table.setRowCount(current_row_count + len(comp_props))

        row = current_row_count
        for comp, props in comp_props.items():
            x_i = props.get('mole_fraction', 0)
            ln_gamma = props.get('ln_gamma')
            gamma = props.get('gamma')
            activity = props.get('activity')
            mu = props.get('mu')

            # 文本输出
            text_output += f"{comp:<8} {x_i:<10.4f} "
            text_output += f"{ln_gamma if ln_gamma is not None else 'N/A':<12} "
            text_output += f"{gamma if gamma is not None else 'N/A':<12} "
            text_output += f"{activity if activity is not None else 'N/A':<12} "
            text_output += f"{mu/1000 if mu is not None else 'N/A':<15}\n"

            # 表格输出
            self.results_table.setItem(row, 0, QTableWidgetItem(comp))
            self.results_table.setItem(row, 1, QTableWidgetItem(f"{x_i:.4f}"))
            self.results_table.setItem(row, 2, QTableWidgetItem(
                f"{ln_gamma:.4f}" if ln_gamma is not None else "N/A"))
            self.results_table.setItem(row, 3, QTableWidgetItem(
                f"{gamma:.4f}" if gamma is not None else "N/A"))
            self.results_table.setItem(row, 4, QTableWidgetItem(
                f"{activity:.4e}" if activity is not None else "N/A"))
            self.results_table.setItem(row, 5, QTableWidgetItem(
                f"{mu/1000:.2f}" if mu is not None else "N/A"))

            row += 1

        text_output += "=" * 70 + "\n\n"

        # 追加结果而非覆盖
        self.results_text.append(text_output)

        # 滚动到底部显示最新结果
        scrollbar = self.results_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        self.results_table.resizeColumnsToContents()

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
            self.results_table.setRowCount(0)
            self.results_data = None
            self.export_button.setEnabled(False)

    def export_results(self):
        """导出结果"""
        if self.results_data is None:
            QMessageBox.warning(self, "导出错误", "没有可导出的结果！")
            return

        try:
            # 创建results目录
            results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'results')
            os.makedirs(results_dir, exist_ok=True)

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(results_dir, f"thermodynamic_properties_{timestamp}.txt")

            # 写入文件
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
    widget = ThermodynamicPropertiesWidget()
    widget.setWindowTitle("热力学性质计算")
    widget.resize(1200, 800)
    widget.show()
    sys.exit(app.exec_())
