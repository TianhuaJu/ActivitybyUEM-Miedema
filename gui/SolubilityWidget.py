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
        # 第一部分：基础合金定义 (放在最上方)
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
        
        self.input_layout.addWidget(QLabel("析出相:"), row, 0, Qt.AlignRight)
        self.precipitate_combo = QComboBox()
        self.precipitate_combo.addItems([
            "GRAPHITE", "BCC_A2", "FCC_A1", "HCP_A3", "DIAMOND_A4",
            "LIQUID", "SER", "其他..."
        ])
        self.input_layout.addWidget(self.precipitate_combo, row, 1)
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
            elif self.mode_temp_curve.isChecked():
                self.calculate_temperature_curve()

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
        text_output += f"当前相状态: {phase_state_str}\n"  # 明确显示液相/固相
        text_output += f"溶质元素: {solute}\n"
        text_output += f"析出相: {precipitate}\n"
        text_output += f"温度: {temperature:.2f} K\n"
        
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
    
    def calculate_solubility_curve (self):
        """计算溶解度随浓度变化的曲线"""
        # 获取输入参数
        solute = self.solute_input.text().strip().upper()
        precipitate = self.precipitate_combo.currentText()
        solution_phase = self._extract_phase_name(self.solution_phase_combo.currentText())
        temperature = float(self.temperature_input.text())
        
        # --- [Fix Start] 修改参数获取与解析逻辑 ---
        fixed_base_str = self.fixed_base_input.text().strip()  # 获取原始字符串，如 "Fe0.7Ni0.3"
        variable_comp = self.variable_comp_input.text().strip().upper()  # 变化组分，如 "Cr"
        
        x_min = float(self.x_min_input.text())
        x_max = float(self.x_max_input.text())
        n_points = int(self.n_points_input.text())
        
        if not all([solute, fixed_base_str, variable_comp]):
            QMessageBox.warning(self, "输入错误", "请输入所有必需参数！")
            return
        
        # 1. 解析固定基础合金成分 (例如: "Fe0.7Ni0.3" -> {'FE': 0.7, 'NI': 0.3})
        fixed_base_map = parse_composition_static(fixed_base_str)
        if not fixed_base_map:
            QMessageBox.warning(self, "输入错误", f"无法解析固定基础成分: {fixed_base_str}")
            return
        
        # 归一化固定基础成分（确保总和为1，作为混合前的基准）
        total_fixed = sum(fixed_base_map.values())
        fixed_base_norm = {k.upper(): v / total_fixed for k, v in fixed_base_map.items()}
        # --- [Fix End] ---
        
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
        def update_progress (current, total):
            self.progress_bar.setValue(current)
            QApplication.processEvents()
        
        # 计算曲线
        import numpy as np
        x_values = np.linspace(x_min, x_max, n_points)
        solubility_values = []
        results_list = []  # 保存完整结果
        
        for i, x_var in enumerate(x_values):
            update_progress(i + 1, n_points)
            
            # --- [Fix Start] 构建混合后的基础合金成分 ---
            # 逻辑: 基础合金 = (1 - x_var) * [固定基础成分] + x_var * [变化组分]
            x_fixed_fraction = 1.0 - x_var
            
            base_composition = {}
            
            # 1. 加入按比例缩小的固定基础成分
            for elem, frac in fixed_base_norm.items():
                base_composition[elem] = frac * x_fixed_fraction
            
            # 2. 加入变化组分
            # 注意：如果变化组分(如Fe)已经在固定成分中存在，需要累加
            base_composition[variable_comp] = base_composition.get(variable_comp, 0.0) + x_var
            # --- [Fix End] ---
            
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
                
                results_list.append(result)
                
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
                results_list.append({'status': 'error', 'message': str(e)})
        
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        
        # 增加计算批次计数，结果文本输出
        self.calculation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        
        
        # 显示结果
        text_output = "\n" + "=" * 70 + "\n"
        text_output += f"【计算批次 #{self.calculation_count}】 {timestamp}\n"
        text_output += "溶解度-浓度曲线计算结果\n"
        text_output += "=" * 70 + "\n\n"
        text_output += f"溶质元素: {solute}\n"
        # --- [Fix Start] 更新输出文本以反映真实成分 ---
        text_output += f"固定基础: {fixed_base_str}\n"
        text_output += f"变化组分: {variable_comp} ({x_min:.3f} ~ {x_max:.3f})\n"
        # --- [Fix End] ---
        text_output += f"溶液相: {solution_phase}\n"
        text_output += f"析出相: {precipitate}\n"
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
        text_output += f"{'状态/详情':<35}\n"  # 加宽一点以容纳错误信息
        text_output += "-" * 80 + "\n"
        
        for i, x_var in enumerate(x_values):
            result = results_list[i]
            sol = solubility_values[i]
            
            text_output += f"{x_var:<10.4f} "
            
            if sol is not None and result.get('status') == 'success':
                rel_add = result.get('relative_addition', 0)
                warnings = result.get('warnings', [])
                
                text_output += f"{sol:<16.6e} "
                text_output += f"{rel_add:<12.4f} "
                
                if warnings:
                    # 只显示第一个警告的简短版本
                    first_warning = warnings[0]
                    if len(first_warning) > 33:
                        text_output += first_warning[:30] + "..."
                    else:
                        text_output += first_warning
                else:
                    text_output += "OK"  # 成功且无警告显示 OK
                
                text_output += "\n"
            else:
                # 【修改 2：处理失败情况，显示详细错误】
                error_detail = result.get('error_detail', '')
                status = result.get('status', 'Unknown')
                
                # 如果有详细错误信息，优先显示；否则显示状态码
                if error_detail:
                    display_msg = error_detail
                elif status == 'insoluble':
                    display_msg = "不溶"
                else:
                    display_msg = status
                
                # 截断过长信息
                if len(display_msg) > 33:
                    display_msg = display_msg[:30] + "..."
                
                text_output += f"{'N/A':<16} {'N/A':<12} {display_msg}\n"
        
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
            title = f'{solute} 在{phase_type} {fixed_base_str}-{variable_comp} 合金中的溶解度 vs. {variable_comp} 含量'
            self.chart_canvas.axes.set_title(title, fontsize=12, fontweight='bold')

            self.chart_canvas.axes.grid(True, alpha=0.3)

        self.chart_canvas.draw()
    
    def calculate_temperature_curve (self):
        """计算溶解度随温度变化的曲线"""
        # 1. 获取参数
        solute = self.solute_input.text().strip().upper()
        precipitate = self.precipitate_combo.currentText()
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
        
        # 获取模型参数 (与原代码一致)
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
        
        # 2. 初始化进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, n_points)
        self.progress_bar.setValue(0)
        self.results_text.setText(f"正在计算 {solute} 在 {base_alloy_str} 中的溶解度随温度变化曲线...\n")
        
        from PyQt5.QtWidgets import QApplication
        def update_progress (current, total):
            self.progress_bar.setValue(current)
            QApplication.processEvents()
        
        # 3. 循环计算
        import numpy as np
        t_values = np.linspace(t_start, t_end, n_points)
        solubility_values = []
        results_list = []
        
        for i, t_curr in enumerate(t_values):
            update_progress(i + 1, n_points)
            
            try:
                result = self.phase_calc.calculate_solubility(
                        base_alloy_composition=base_composition,
                        solute_element=solute,
                        solution_phase=solution_phase,
                        precipitating_phase=precipitate,
                        temperature=t_curr,  # 传入当前循环的温度
                        extrapolation_func=extrap_func,
                        extrapolation_model_name=extrap_model_name,
                        activity_model=activity_model
                )
                
                results_list.append(result)
                
                if result['status'] == 'success':
                    solubility_values.append(result['solubility_mole_fraction'])
                elif result['status'] == 'fully_soluble':
                    solubility_values.append(1.0)
                elif result['status'] == 'insoluble':
                    solubility_values.append(0.0)
                else:
                    solubility_values.append(None)
            
            except Exception as e:
                print(f"Error at T={t_curr}: {e}")
                solubility_values.append(None)
                results_list.append({'status': 'error', 'message': str(e)})
        
        self.progress_bar.setVisible(False)
        
        # 4. 结果文本输出
        self.calculation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 提取第一点的溶剂信息用于显示
        first_valid = next((r for r in results_list if r.get('status') == 'success'), {})
        detected_solvent = first_valid.get('solvent_element', 'Unknown')
        
        text_output = "\n" + "=" * 70 + "\n"
        text_output += f"【计算批次 #{self.calculation_count}】 {timestamp}\n"
        text_output += "溶解度-温度曲线计算结果\n"
        text_output += "=" * 70 + "\n\n"
        text_output += f"溶质元素: {solute}\n"
        text_output += f"基础合金: {base_alloy_str}\n"
        text_output += f"  -> 自动识别溶剂: {detected_solvent}\n"
        text_output += f"温度范围: {t_start:.1f} K ~ {t_end:.1f} K\n"
        text_output += f"基体状态: {solution_phase}\n"
        text_output += f"析出相: {precipitate}\n\n"
        
        
        text_output += f"{'温度(K)':<10} {'温度(°C)':<10} {'溶解度(X_' + solute + ')':<20} {'状态详情'}\n"
        text_output += "-" * 80 + "\n"
        
        for i, t_curr in enumerate(t_values):
            sol = solubility_values[i]
            res = results_list[i]
            if sol is not None:
                status_str = "OK"
                sol_str = f"{sol:.6e}"
            else:
                sol_str = "N/A"
                # 优先显示 error_detail，如果没有则显示 status
                error_detail = res.get('error_detail', '')
                if error_detail:
                    # 截取过长信息以免换行太乱 (比如前40个字符)
                    status_str = (error_detail[:35] + '...') if len(error_detail) > 35 else error_detail
                else:
                    status_str = res.get('status', 'Unknown')
            
            text_output += f"{t_curr:<10.1f} {t_curr - 273.15:<10.1f} {sol_str:<20} {status_str}\n"
            
        self.results_text.append(text_output)
        scrollbar = self.results_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # 5. 绘制图表
        self.chart_canvas.axes.clear()
        valid_data = [(t, s) for t, s in zip(t_values, solubility_values) if s is not None]
        
        if valid_data:
            x_plot, s_plot = zip(*valid_data)
            # 绘制曲线
            self.chart_canvas.axes.plot(x_plot, [s * 100 for s in s_plot], 'r-o', linewidth=2, markersize=4,
                                        label='溶解度')
            
            self.chart_canvas.axes.set_xlabel('温度 (K)', fontsize=11)
            self.chart_canvas.axes.set_ylabel(f'{solute} 溶解度 (摩尔%)', fontsize=11)
            
            phase_type_cn = "液态" if solution_phase == "LIQUID" else "固态"
            title = f'{solute} 在{phase_type_cn} {base_alloy_str} 中的溶解度 vs. 温度'
            self.chart_canvas.axes.set_title(title, fontsize=12, fontweight='bold')
            self.chart_canvas.axes.grid(True, alpha=0.3)
            
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
