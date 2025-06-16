import math
import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton,
                             QSplitter, QFrame, QGroupBox, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.utils import parse_composition_static


class MplCanvas(FigureCanvas):
	"""Matplotlib画布类"""
	
	def __init__ (self, parent=None, width=7, height=6, dpi=100):
		self.fig = Figure(figsize=(width, height), dpi=dpi)
		self.axes = self.fig.add_subplot(111)
		super(MplCanvas, self).__init__(self.fig)


class ActivityCalculationWidget(QWidget):
	"""活度计算组件"""
	
	def __init__ (self, parent=None):
		super().__init__()
		self.parent = parent
		self.setup_ui()
	
	def setup_ui (self):
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
		
		# 初始绘制空图表
		self.init_chart()
	
	def create_input_panel (self):
		"""创建输入面板"""
		widget = QWidget()
		layout = QVBoxLayout(widget)
		
		# 创建输入字段分组
		input_group = QGroupBox("活度计算 - 输入参数")
		input_layout = QGridLayout(input_group)
		input_layout.setSpacing(15)
		input_layout.setContentsMargins(20, 25, 20, 20)
		
		row = 0
		
		# 合金成分输入
		input_layout.addWidget(QLabel("合金成分:"), row, 0, Qt.AlignRight)
		
		# 合金成分输入框容器
		alloy_container = QWidget()
		alloy_layout = QHBoxLayout(alloy_container)
		alloy_layout.setContentsMargins(0, 0, 0, 0)
		alloy_layout.setSpacing(8)
		
		# 合金成分输入框
		self.alloy_input = QLineEdit("Fe0.70C0.03Si0.27")
		self.alloy_input.setPlaceholderText("请输入合金组成，例如: Fe0.7C0.03Si0.27")
		self.alloy_input.setToolTip(
				"输入格式: 元素符号+摩尔分数，如Fe0.7C0.03Si0.27\n支持多种格式: Fe0.7C0.03Si0.27 或 Fe:0.7,C:0.03,Si:0.27")
		
		# 连接文本变化信号到解析函数
		self.alloy_input.textChanged.connect(self.update_element_dropdowns)
		
		alloy_layout.addWidget(self.alloy_input)
		
		# 解析按钮
		parse_btn = QPushButton("解析")
		parse_btn.setFixedWidth(80)
		parse_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                font-size: 11pt;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
		parse_btn.clicked.connect(self.update_element_dropdowns)
		alloy_layout.addWidget(parse_btn)
		
		input_layout.addWidget(alloy_container, row, 1)
		row += 1
		
		# 基体元素下拉框
		input_layout.addWidget(QLabel("基体元素:"), row, 0, Qt.AlignRight)
		self.solvent_combo = QComboBox()
		self.solvent_combo.setToolTip("选择基体元素（溶剂）")
		input_layout.addWidget(self.solvent_combo, row, 1)
		row += 1
		
		# 溶质元素下拉框
		input_layout.addWidget(QLabel("溶质元素(i):"), row, 0, Qt.AlignRight)
		self.solute_combo = QComboBox()
		self.solute_combo.setToolTip("选择要计算活度的溶质元素")
		input_layout.addWidget(self.solute_combo, row, 1)
		row += 1
		
		# 温度输入
		input_layout.addWidget(QLabel("温度 (K):"), row, 0, Qt.AlignRight)
		self.temp_input = QLineEdit("1873.0")
		self.temp_input.setPlaceholderText("请输入温度，例如: 1873.0")
		input_layout.addWidget(self.temp_input, row, 1)
		row += 1
		
		# 状态下拉框
		input_layout.addWidget(QLabel("状态:"), row, 0, Qt.AlignRight)
		self.state_combo = QComboBox()
		self.state_combo.addItems(["liquid", "solid"])
		input_layout.addWidget(self.state_combo, row, 1)
		row += 1
		
		# 外推模型下拉框
		input_layout.addWidget(QLabel("外推模型:"), row, 0, Qt.AlignRight)
		self.model_combo = QComboBox()
		self.model_combo.addItems(["UEM1", "UEM2", "GSM", "Muggianu"])
		input_layout.addWidget(self.model_combo, row, 1)
		row += 1
		
		# 添加分隔线
		line = QFrame()
		line.setFrameShape(QFrame.HLine)
		line.setFrameShadow(QFrame.Sunken)
		input_layout.addWidget(line, row, 0, 1, 2)
		row += 1
		
		# 计算按钮
		btn_layout = QHBoxLayout()
		calculate_btn = QPushButton("开始计算")
		calculate_btn.clicked.connect(self.calculate_activity)
		calculate_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                font-size: 13pt;
                padding: 15px 25px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
		btn_layout.addWidget(calculate_btn)
		
		clear_btn = QPushButton("清除结果")
		clear_btn.clicked.connect(self.clear_result)
		clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                font-size: 13pt;
                padding: 15px 25px;
            }
            QPushButton:hover {
                background-color: #545b62;
            }
        """)
		btn_layout.addWidget(clear_btn)
		
		input_layout.addLayout(btn_layout, row, 0, 1, 2)
		row += 1
		
		# 添加输入分组到布局
		layout.addWidget(input_group)
		layout.addStretch()
		
		return widget
	
	def create_results_panel (self):
		"""创建结果面板"""
		widget = QWidget()
		layout = QVBoxLayout(widget)
		
		# 结果文本区域
		result_group = QGroupBox("计算结果")
		result_layout = QVBoxLayout(result_group)
		
		self.result_text = QTextEdit()
		self.result_text.setReadOnly(True)
		result_layout.addWidget(self.result_text)
		
		# 图表区域
		chart_group = QGroupBox("数据可视化")
		chart_layout = QVBoxLayout(chart_group)
		
		self.canvas = MplCanvas(self, width=6, height=4, dpi=100)
		chart_layout.addWidget(self.canvas)
		
		layout.addWidget(result_group, 1)
		layout.addWidget(chart_group, 2)
		
		return widget
	
	def update_element_dropdowns (self):
		"""更新元素下拉框"""
		alloy_input = self.alloy_input.text().strip()
		
		# 清空下拉框
		self.solvent_combo.blockSignals(True)
		self.solute_combo.blockSignals(True)
		self.solvent_combo.clear()
		self.solute_combo.clear()
		
		if not alloy_input:
			self.solvent_combo.blockSignals(False)
			self.solute_combo.blockSignals(False)
			return
		
		try:
			# 解析合金组成
			comp_dict = self.parse_composition(alloy_input)
			
			if not comp_dict:
				self.solvent_combo.blockSignals(False)
				self.solute_combo.blockSignals(False)
				return
			
			# 填充元素下拉框
			elements = list(comp_dict.keys())
			elements.sort()  # 按字母顺序排序
			
			self.solvent_combo.addItems(elements)
			self.solute_combo.addItems(elements)
			
			# 智能选择默认元素
			# 基体元素：选择摩尔分数最大的元素
			max_element = max(comp_dict.items(), key=lambda x: x[1])[0]
			solvent_index = elements.index(max_element)
			self.solvent_combo.setCurrentIndex(solvent_index)
			
			# 溶质元素：选择摩尔分数最小的元素（通常是合金元素）
			min_element = min(comp_dict.items(), key=lambda x: x[1])[0]
			if min_element != max_element:
				solute_index = elements.index(min_element)
				self.solute_combo.setCurrentIndex(solute_index)
			elif len(elements) > 1:
				# 如果最大和最小是同一个元素，选择第二个元素
				other_elements = [elem for elem in elements if elem != max_element]
				if other_elements:
					self.solute_combo.setCurrentIndex(elements.index(other_elements[0]))
			
			self.update_status(f"成功解析 {len(elements)} 个元素: {', '.join(elements)}")
		
		except Exception as e:
			self.update_status("合金组成解析失败")
		finally:
			self.solvent_combo.blockSignals(False)
			self.solute_combo.blockSignals(False)
	
	def parse_composition (self, alloy_str):
		"""解析合金成分字符串为字典"""
		return parse_composition_static(alloy_str)
	
	def validate_input (self):
		"""验证输入"""
		# 检查合金组成
		if not self.alloy_input.text().strip():
			QMessageBox.critical(self, "输入错误", "合金成分不能为空")
			return False
		
		# 检查元素选择
		if not self.solvent_combo.currentText():
			QMessageBox.critical(self, "输入错误", "请选择基体元素")
			return False
		
		if not self.solute_combo.currentText():
			QMessageBox.critical(self, "输入错误", "请选择溶质元素")
			return False
		
		# 检查是否选择了相同的元素
		if self.solvent_combo.currentText() == self.solute_combo.currentText():
			QMessageBox.warning(self, "输入警告", "基体元素和溶质元素不能相同\n请选择不同的元素进行计算")
			return False
		
		# 检查温度
		try:
			temp = float(self.temp_input.text())
			if temp <= 0:
				QMessageBox.critical(self, "输入错误", "温度必须大于0")
				return False
		except ValueError:
			QMessageBox.critical(self, "输入错误", "温度必须是有效的数值")
			return False
		
		return True
	
	def calculate_activity (self):
		"""计算活度"""
		try:
			if not self.validate_input():
				return
			
			alloy_composition_str = self.alloy_input.text()
			solvent = self.solvent_combo.currentText()
			solute = self.solute_combo.currentText()
			temp = float(self.temp_input.text())
			state = self.state_combo.currentText()
			model_name = self.model_combo.currentText()
			
			self.update_status(f"正在计算 {solute} 在 {solvent} 中的活度...")
			
			comp_dict = self.parse_composition(alloy_composition_str)
			if not comp_dict:
				QMessageBox.critical(self, "输入错误", "无法解析合金成分，请检查格式是否正确。")
				self.update_status("合金成分解析失败")
				return
			
			# 验证选择的元素确实在合金成分中
			if solvent not in comp_dict:
				QMessageBox.critical(self, "输入错误", f"选择的基体元素 '{solvent}' 不在合金成分中")
				self.update_status(f"基体元素 '{solvent}' 无效")
				return
			
			if solute not in comp_dict:
				QMessageBox.critical(self, "输入错误", f"选择的溶质元素 '{solute}' 不在合金成分中")
				self.update_status(f"溶质元素 '{solute}' 无效")
				return
			
			xi = comp_dict.get(solute)
			
			model_func = self.get_model_function(model_name)
			self.parent.activity_coefficient.set_composition_dict(alloy_composition_str)
			
			# 计算不同方法的活度系数
			darken_acf = self.parent.activity_coefficient.activity_coefficient_darken(
					comp_dict, solute, solvent, temp, state, model_func, model_name)
			wagner_acf = self.parent.activity_coefficient.activity_coefficient_wagner(
					comp_dict, solvent, solute, temp, state, model_func, model_name)
			elliot_acf = self.parent.activity_coefficient.activity_coefficient_elliott(
					comp_dict, solute, solvent, temp, state, model_func, model_name)
			
			# 计算活度
			darken_activity = math.exp(darken_acf) * xi
			wagner_activity = math.exp(wagner_acf) * xi
			elliot_activity = math.exp(elliot_acf) * xi
			
			results = {
				"composition": alloy_composition_str,
				"solvent": solvent,
				"solute": solute,
				"temperature": temp,
				"state": state,
				"model": model_name,
				"activity_darken": round(darken_activity, 3),
				"activity_wagner": round(wagner_activity, 3),
				"activity_elliot": round(elliot_activity, 3),
				"mole_fraction": round(xi, 3),
				"activity_coefficient_darken": round(math.exp(darken_acf), 3),
				"activity_coefficient_wagner": round(math.exp(wagner_acf), 3),
				"activity_coefficient_elliott": round(math.exp(elliot_acf), 3),
			}
			
			self.display_results(results)
			self.update_chart(results)
			self.update_status(f"✅ 完成 {solute} 在 {solvent} 中的活度计算")
		
		except Exception as e:
			QMessageBox.critical(self, "计算错误", f"计算过程中发生错误: {str(e)}")
			self.update_status("❌ 计算失败")
	
	def get_model_function (self, model_name):
		"""获取对应的模型函数"""
		if model_name == "UEM1":
			return self.parent.binary_model.UEM1
		elif model_name == "UEM2":
			return self.parent.binary_model.UEM2
		elif model_name == "GSM":
			return self.parent.binary_model.GSM
		elif model_name == "Muggianu":
			return self.parent.binary_model.Muggianu
		elif model_name == "Toop-Muggianu":
			return self.parent.binary_model.Toop_Muggianu
		elif model_name == "Toop-Kohler":
			return self.parent.binary_model.Toop_Kohler
		else:
			return self.parent.binary_model.UEM1
	
	def display_results (self, results):
		"""显示计算结果"""
		current_timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		
		entry_text = f"记录时间: {current_timestamp_str}\n"
		entry_text += f"活度计算结果:\n\n"
		entry_text += f"合金成分: {results['composition']}\n"
		entry_text += f"基体元素: {results['solvent']}\n"
		entry_text += f"溶质元素: {results['solute']}\n"
		entry_text += f"温度: {results['temperature']} K\n"
		entry_text += f"状态: {results['state']}\n"
		entry_text += f"外推模型: {results['model']}\n\n"
		entry_text += f"活度值 (Wagner模型): {results['activity_wagner']}\n"
		entry_text += f"活度值 (Darken模型): {results['activity_darken']}\n"
		entry_text += f"活度值 (Elliot模型): {results['activity_elliot']}\n\n"
		entry_text += f"摩尔分数: {results['mole_fraction']}\n\n"
		entry_text += f"活度系数 (Wagner模型): {results['activity_coefficient_wagner']}\n"
		entry_text += f"活度系数 (Darken模型): {results['activity_coefficient_darken']}\n"
		entry_text += f"活度系数 (Elliot模型): {results['activity_coefficient_elliott']}\n"
		
		current_content = self.result_text.toPlainText()
		
		if current_content:
			text_to_display = f"\n{'-' * 50}\n\n{entry_text}"
			self.result_text.append(text_to_display)
		else:
			self.result_text.setText(entry_text)
		
		# 自动滚动到底部
		self.result_text.verticalScrollBar().setValue(
				self.result_text.verticalScrollBar().maximum())
	
	def update_chart (self, results):
		"""更新图表"""
		self.canvas.axes.clear()
		
		# 数据
		models = ['Wagner', 'Darken', 'Elliot']
		values = [results['activity_wagner'], results['activity_darken'], results['activity_elliot']]
		
		# 创建柱状图
		bars = self.canvas.axes.bar(models, values, color=['#3498db', '#2ecc71', '#e74c3c'])
		
		# 添加数值标签
		self.setup_value_labels(self.canvas.axes, bars, values, 0.01)
		
		mole_fraction = results["mole_fraction"]
		max_value_plot = max(values) if values else 0
		
		y_max = 1.0
		if max(max_value_plot, mole_fraction) > 0.84 and max(max_value_plot, mole_fraction) < 1.01:
			y_max = 1.0
		elif values:
			y_max = max(max_value_plot, mole_fraction) * 1.2
		else:
			y_max = mole_fraction * 1.2 if mole_fraction > 0 else 1.0
		
		self.canvas.axes.set_ylim(0, y_max if y_max > 0 else 1.0)
		
		# 设置图表属性
		solute = results["solute"]
		solvent = results["solvent"]
		self.canvas.axes.set_title(f'{solute} 在 {solvent} 中的活度比较', fontsize=14)
		self.canvas.axes.set_ylabel(rf'Activity($\mathbf{{a}}_{{{solute}}}$)', fontsize=13)
		self.canvas.axes.grid(True, axis='y', linestyle='--', alpha=0.7)
		
		# 添加摩尔分数参考线
		self.canvas.axes.axhline(y=results['mole_fraction'], color='r', linestyle='--', alpha=0.5)
		self.canvas.axes.text(0, results['mole_fraction'] * 1.05,
		                      f'摩尔分数 X_{solute}: {results["mole_fraction"]:.3f}',
		                      color='r', alpha=0.7, fontsize=12)
		
		self.canvas.fig.tight_layout()
		self.canvas.draw()
	
	def setup_value_labels (self, axes, bars, values, min_height=0.0):
		"""设置数值标签"""
		for i, bar in enumerate(bars):
			height = bar.get_height()
			value = values[i]
			
			if abs(height) > min_height:
				y_pos = height / 2
				va = 'center'
				color = 'white'
				fontweight = 'bold'
			else:
				if height >= 0:
					y_pos = height + 0.05
					va = 'bottom'
				else:
					y_pos = height - 0.15
					va = 'top'
				color = 'black'
				fontweight = 'normal'
			
			axes.text(
					bar.get_x() + bar.get_width() / 2., y_pos,
					f'{value:.3f}', ha='center', va=va,
					fontsize=10, color=color, fontweight=fontweight
			)
	
	def init_chart (self):
		"""初始化图表"""
		self.canvas.axes.clear()
		self.canvas.axes.set_title('活度比较', fontsize=14)
		self.canvas.axes.set_ylabel('活度值', fontsize=12)
		self.canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.canvas.fig.tight_layout()
		self.canvas.draw()
	
	def clear_result (self):
		"""清除结果"""
		self.result_text.clear()
		self.init_chart()
	
	def switch_to_temperature_tab (self):
		"""切换到温度变化分析选项卡"""
		if self.parent:
			self.parent.switch_to_temperature_tab()
	
	def switch_to_concentration_tab (self):
		"""切换到浓度变化分析选项卡"""
		if self.parent:
			self.parent.switch_to_concentration_tab()
	
	def update_status (self, message):
		"""更新状态栏"""
		if self.parent:
			self.parent.update_status(message)