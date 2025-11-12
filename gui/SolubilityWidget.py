"""
Solubility Widget
==================
溶解度计算与可视化GUI组件

功能:
- 计算溶质在合金中的溶解度
- 绘制溶解度随基础合金成分变化的曲线
- 支持液相和固相溶解度计算

作者: Claude
日期: 2025-11-11
"""

import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton,
                             QSplitter, QFrame, QGroupBox, QTextEdit,
                             QMessageBox, QRadioButton, QButtonGroup, QProgressBar)
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


class SolubilityWidget(QWidget):
    """溶解度计算与可视化组件"""

    def __init__(self):
        super().__init__()

        self.phase_calc = PhaseDiagram()
        self.calculation_count = 0  # 计算批次计数器
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

        self.mode_single = QRadioButton("单点溶解度计算")
        self.mode_curve = QRadioButton("溶解度-浓度曲线")

        self.mode_button_group.addButton(self.mode_single, 1)
        self.mode_button_group.addButton(self.mode_curve, 2)

        self.mode_single.setChecked(True)
        self.mode_single.toggled.connect(self.on_mode_changed)
        self.mode_curve.toggled.connect(self.on_mode_changed)

        mode_layout.addWidget(self.mode_single)
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

        self.clear_button = QPushButton("清除历史")
        self.clear_button.setMinimumHeight(40)
        self.clear_button.clicked.connect(self.clear_history)
        button_layout.addWidget(self.clear_button)

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

        # 共同参数
        self.input_layout.addWidget(QLabel("溶质元素:"), row, 0, Qt.AlignRight)
        self.solute_input = QLineEdit("C")
        self.solute_input.setPlaceholderText("例如: C")
        self.input_layout.addWidget(self.solute_input, row, 1)
        row += 1

        self.input_layout.addWidget(QLabel("析出相:"), row, 0, Qt.AlignRight)
        self.precipitate_combo = QComboBox()
        self.precipitate_combo.addItems([
            "GRAPHITE", "BCC_A2", "FCC_A1", "HCP_A3", "DIAMOND_A4",
            "LIQUID", "SER", "其他..."
        ])
        self.input_layout.addWidget(self.precipitate_combo, row, 1)
        row += 1

        solution_label = QLabel("溶液相:")
        solution_label.setToolTip("选择溶质溶解的相:\n液相 - 液态合金\n固相 - 固态合金")
        self.input_layout.addWidget(solution_label, row, 0, Qt.AlignRight)
        self.solution_phase_combo = QComboBox()
        self.solution_phase_combo.addItems(["液相", "固相"])
        self.solution_phase_combo.setToolTip("液相和固相均采用UEM-Miedema框架计算")
        self.input_layout.addWidget(self.solution_phase_combo, row, 1)
        row += 1

        self.input_layout.addWidget(QLabel("温度 (K):"), row, 0, Qt.AlignRight)
        self.temperature_input = QLineEdit("1500")
        self.input_layout.addWidget(self.temperature_input, row, 1)
        row += 1

        # 单点计算模式
        if self.mode_single.isChecked():
            self.input_layout.addWidget(QLabel("基础合金:"), row, 0, Qt.AlignRight)
            self.base_alloy_input = QLineEdit("Fe0.7Si0.3")
            self.base_alloy_input.setPlaceholderText("例如: Fe0.7Si0.3")
            self.input_layout.addWidget(self.base_alloy_input, row, 1)

        # 曲线计算模式
        elif self.mode_curve.isChecked():
            self.input_layout.addWidget(QLabel("固定基础成分:"), row, 0, Qt.AlignRight)
            self.fixed_base_input = QLineEdit("Fe")
            self.fixed_base_input.setPlaceholderText("例如: Fe (不变化)")
            self.input_layout.addWidget(self.fixed_base_input, row, 1)
            row += 1

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
        results_layout.addWidget(self.results_text)

        layout.addWidget(results_group)

        # 图表绘制区域
        chart_group = QGroupBox("溶解度可视化")
        chart_layout = QVBoxLayout(chart_group)

        self.chart_canvas = MplCanvas(self, width=7, height=5, dpi=100)
        chart_layout.addWidget(self.chart_canvas)

        layout.addWidget(chart_group)

        return widget

    def perform_calculation(self):
        """执行计算"""
        try:
            if self.mode_single.isChecked():
                self.calculate_single_point()
            elif self.mode_curve.isChecked():
                self.calculate_solubility_curve()

            self.export_button.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "计算错误", f"计算过程中发生错误:\n{str(e)}")
            self.results_text.setText(f"错误: {str(e)}")

    def calculate_single_point(self):
        """计算单点溶解度"""
        # 获取输入参数
        solute = self.solute_input.text().strip().upper()
        precipitate = self.precipitate_combo.currentText()
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

        # 计算溶解度
        result = self.phase_calc.calculate_solubility(
            base_alloy_composition=base_composition,
            solute_element=solute,
            solution_phase=solution_phase,
            precipitating_phase=precipitate,
            temperature=temperature,
            extrapolation_func=extrap_func,
            extrapolation_model_name=extrap_model_name,
            activity_model=activity_model
        )

        # 增加计算批次计数
        self.calculation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 显示结果
        text_output = "\n" + "=" * 70 + "\n"
        text_output += f"【计算批次 #{self.calculation_count}】 {timestamp}\n"
        text_output += "溶解度计算结果\n"
        text_output += "=" * 70 + "\n\n"
        text_output += f"溶质元素: {solute}\n"
        text_output += f"基础合金: {base_composition}\n"
        text_output += f"溶液相: {solution_phase}\n"
        text_output += f"析出相: {precipitate}\n"
        text_output += f"温度: {temperature:.2f} K ({temperature-273.15:.2f} °C)\n"
        text_output += f"外推模型: {extrap_model_name}\n"
        text_output += f"活度模型: {activity_model}\n\n"

        if result['status'] == 'success':
            solubility = result['solubility_mole_fraction']
            text_output += f"✓ 溶解度 (摩尔分数): {solubility:.6e}\n"
            text_output += f"✓ 溶解度 (摩尔%): {solubility*100:.4f}%\n\n"

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

            # 确定溶液相类型：液相或固相（统一处理所有固相）
            phase_type = "液态" if solution_phase == "LIQUID" else "固态"

            # 构建基础合金成分描述
            base_alloy_str = "-".join(base_composition.keys())

            self.chart_canvas.axes.set_ylabel('溶解度 (摩尔%)', fontsize=11)

            # 标题：溶质在基体合金中的溶解度
            # 例如："Fe 在液态 Al-Si 合金中的溶解度" 或 "C 在固态 Fe-Cr 合金中的溶解度"
            title = f'{solute} 在{phase_type} {base_alloy_str} 合金中的溶解度'
            self.chart_canvas.axes.set_title(title, fontsize=12, fontweight='bold')
            self.chart_canvas.axes.grid(True, alpha=0.3, axis='y')
        self.chart_canvas.draw()

    def calculate_solubility_curve(self):
        """计算溶解度随浓度变化的曲线"""
        # 获取输入参数
        solute = self.solute_input.text().strip().upper()
        precipitate = self.precipitate_combo.currentText()
        solution_phase = self._extract_phase_name(self.solution_phase_combo.currentText())
        temperature = float(self.temperature_input.text())
        fixed_base = self.fixed_base_input.text().strip().upper()
        variable_comp = self.variable_comp_input.text().strip().upper()
        x_min = float(self.x_min_input.text())
        x_max = float(self.x_max_input.text())
        n_points = int(self.n_points_input.text())

        if not all([solute, fixed_base, variable_comp]):
            QMessageBox.warning(self, "输入错误", "请输入所有必需参数！")
            return

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

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, n_points)
        self.progress_bar.setValue(0)
        self.results_text.setText("正在计算溶解度曲线，请稍候...")

        # 定义进度回调
        from PyQt5.QtWidgets import QApplication
        def update_progress(current, total):
            self.progress_bar.setValue(current)
            QApplication.processEvents()

        # 计算曲线
        import numpy as np
        x_values = np.linspace(x_min, x_max, n_points)
        solubility_values = []

        for i, x_var in enumerate(x_values):
            update_progress(i + 1, n_points)

            # 构建基础合金成分
            x_fixed = 1.0 - x_var
            base_composition = {
                fixed_base: x_fixed,
                variable_comp: x_var
            }

            try:
                result = self.phase_calc.calculate_solubility(
                    base_alloy_composition=base_composition,
                    solute_element=solute,
                    solution_phase=solution_phase,
                    precipitating_phase=precipitate,
                    temperature=temperature,
                    extrapolation_func=extrap_func,
                    extrapolation_model_name=extrap_model_name,
                    activity_model=activity_model
                )

                if result['status'] == 'success':
                    solubility_values.append(result['solubility_mole_fraction'])
                elif result['status'] == 'fully_soluble':
                    solubility_values.append(1.0)
                elif result['status'] == 'insoluble':
                    solubility_values.append(0.0)
                else:
                    solubility_values.append(None)
            except Exception as e:
                print(f"Error at X_{variable_comp}={x_var}: {e}")
                solubility_values.append(None)

        # 隐藏进度条
        self.progress_bar.setVisible(False)

        # 增加计算批次计数
        self.calculation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 显示结果
        text_output = "\n" + "=" * 70 + "\n"
        text_output += f"【计算批次 #{self.calculation_count}】 {timestamp}\n"
        text_output += "溶解度-浓度曲线计算结果\n"
        text_output += "=" * 70 + "\n\n"
        text_output += f"溶质元素: {solute}\n"
        text_output += f"基础合金: {fixed_base} + {variable_comp}\n"
        text_output += f"变化组分: {variable_comp} ({x_min:.3f} ~ {x_max:.3f})\n"
        text_output += f"溶液相: {solution_phase}\n"
        text_output += f"析出相: {precipitate}\n"
        text_output += f"温度: {temperature:.2f} K ({temperature-273.15:.2f} °C)\n"
        text_output += f"外推模型: {extrap_model_name}\n"
        text_output += f"活度模型: {activity_model}\n"
        text_output += f"采样点数: {n_points}\n\n"

        text_output += "说明：溶解度是指溶质在【最终平衡合金】中的摩尔分数\n"
        text_output += "      例如：Si=0.3时，V溶解度=0.73，表示最终合金为 V(73%) + Fe(18.9%) + Si(8.1%)\n"
        text_output += "-" * 70 + "\n"

        text_output += f"{'X_' + variable_comp:<12} {'溶解度 (X_' + solute + ')':<20}\n"
        text_output += "-" * 70 + "\n"

        for i, x_var in enumerate(x_values):
            sol = solubility_values[i]
            text_output += f"{x_var:<12.4f} "
            text_output += f"{sol:.6e}\n" if sol is not None else "N/A\n"

        text_output += "=" * 70 + "\n"

        # 追加结果
        self.results_text.append(text_output)

        # 滚动到底部
        scrollbar = self.results_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # 绘制曲线
        self.chart_canvas.axes.clear()

        # 过滤有效数据
        valid_data = [(x, s) for x, s in zip(x_values, solubility_values) if s is not None]
        if valid_data:
            x_plot, s_plot = zip(*valid_data)
            self.chart_canvas.axes.plot(x_plot, [s*100 for s in s_plot], 'b-o', linewidth=2, markersize=5)

            # 确定溶液相类型：液相或固相（统一处理所有固相）
            phase_type = "液态" if solution_phase == "LIQUID" else "固态"

            # 构建更清晰的标签
            # X轴：变化组分的摩尔分数
            self.chart_canvas.axes.set_xlabel(f'{variable_comp} 含量 (摩尔分数)', fontsize=11)

            # Y轴：溶质的溶解度
            self.chart_canvas.axes.set_ylabel(f'{solute} 溶解度 (摩尔%)', fontsize=11)

            # 标题：溶质在基体合金中的溶解度 vs. 变化组分
            # 例如："Fe 在液态 Al-Si 合金中的溶解度 vs. Si 含量" 或 "C 在固态 Fe-Cr 合金中的溶解度 vs. Cr 含量"
            title = f'{solute} 在{phase_type} {fixed_base}-{variable_comp} 合金中的溶解度 vs. {variable_comp} 含量'
            self.chart_canvas.axes.set_title(title, fontsize=12, fontweight='bold')

            self.chart_canvas.axes.grid(True, alpha=0.3)

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
