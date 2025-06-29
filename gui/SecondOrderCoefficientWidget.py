from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton,
                             QSplitter, QFrame, QGroupBox, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.element import Element
from models.activity_interaction_parameters import TernaryMelts


class MplCanvas(FigureCanvas):
	"""Matplotlib画布类"""
	
	def __init__ (self, parent=None, width=7, height=6, dpi=100):
		self.fig = Figure(figsize=(width, height), dpi=dpi)
		self.axes = self.fig.add_subplot(111)
		super(MplCanvas, self).__init__(self.fig)


class SecondOrderCoefficientWidget(QWidget):
	"""二阶相互作用系数计算组件"""
	
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
		input_group = QGroupBox("二阶相互作用系数计算 - 输入参数")
		input_layout = QGridLayout(input_group)
		input_layout.setSpacing(15)
		input_layout.setContentsMargins(20, 25, 20, 20)
		
		row = 0
		
		# 基体元素输入
		input_layout.addWidget(QLabel("基体元素:"), row, 0, Qt.AlignRight)
		self.solvent_input = QLineEdit("Al")
		self.solvent_input.setPlaceholderText("e.g.: Al")
		input_layout.addWidget(self.solvent_input, row, 1)
		row += 1
		
		# 溶质 i 输入
		input_layout.addWidget(QLabel("溶质 i:"), row, 0, Qt.AlignRight)
		self.solute_i_input = QLineEdit("Si")
		self.solute_i_input.setPlaceholderText("e.g.: Si")
		input_layout.addWidget(self.solute_i_input, row, 1)
		row += 1
		
		# 溶质 j 输入
		input_layout.addWidget(QLabel("溶质 j:"), row, 0, Qt.AlignRight)
		self.solute_j_input = QLineEdit("Cu")
		self.solute_j_input.setPlaceholderText("e.g.: Cu")
		input_layout.addWidget(self.solute_j_input, row, 1)
		row += 1
		
		# 溶质 k 输入
		input_layout.addWidget(QLabel("溶质 k:"), row, 0, Qt.AlignRight)
		self.solute_k_input = QLineEdit("Mn")
		self.solute_k_input.setPlaceholderText("e.g.: Mn")
		input_layout.addWidget(self.solute_k_input, row, 1)
		row += 1
		
		# 温度输入
		input_layout.addWidget(QLabel("温度 (K):"), row, 0, Qt.AlignRight)
		self.temp_input = QLineEdit("805.0")
		self.temp_input.setPlaceholderText("e.g.: 805.0")
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
		calculate_btn.clicked.connect(self.calculate_second_order)
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
	
	def validate_input (self):
		"""验证输入"""
		# 检查字段
		fields = [
			(self.solvent_input, "基体元素"),
			(self.solute_i_input, "溶质 i"),
			(self.solute_j_input, "溶质 j"),
			(self.solute_k_input, "溶质 k"),
			(self.temp_input, "温度")
		]
		
		for field, name in fields:
			if not field.text().strip():
				QMessageBox.critical(self, "输入错误", f"{name}不能为空")
				return False
		
		# 检查温度
		try:
			temp = float(self.temp_input.text())
			if temp <= 0:
				QMessageBox.critical(self, "输入错误", "温度必须大于0")
				return False
		except ValueError:
			QMessageBox.critical(self, "输入错误", "温度必须是数值")
			return False
		
		return True
	
	def calculate_second_order (self):
		"""计算二阶相互作用系数"""
		try:
			if not self.validate_input():
				return
			
			# 获取输入值
			solvent = self.solvent_input.text()
			solute_i = self.solute_i_input.text()
			solute_j = self.solute_j_input.text()
			solute_k = self.solute_k_input.text()
			temp = float(self.temp_input.text())
			state = self.state_combo.currentText()
			model_name = self.model_combo.currentText()
			
			# 更新状态栏
			self.update_status(f"正在计算 {solute_i}-{solute_j}-{solute_k} 在 {solvent} 中的二阶相互作用系数...")
			
			# 创建元素实例
			solv = Element(solvent)
			solui = Element(solute_i)
			soluj = Element(solute_j)
			soluk = Element(solute_k)
			
			# 获取模型函数
			model_func = self.get_model_function(model_name)
			
			# 创建 TernaryMelts 实例
			is_entropy = False
			ternary = TernaryMelts(temp, state, is_entropy)
			
			# 计算二阶系数
			ri_ii = ternary.roui_ii(solv, solui, temp, state, model_func, model_name)
			ri_ij = ternary.roui_ij(solv, solui, soluj, temp, state, model_func, model_name)
			ri_jj = ternary.roui_jj(solv, solui, soluj, temp, state, model_func, model_name)
			ri_jk = ternary.roui_jk(solv, solui, soluj, soluk, temp, state, model_func, model_name)
			ri_ik = ternary.roui_ij(solv, solui, soluk, temp, state, model_func, model_name)
			ri_kk = ternary.roui_jj(solv, solui, soluk, temp, state, model_func, model_name)
			
			# 准备结果
			results = {
				"solvent": solvent,
				"solute_i": solute_i,
				"solute_j": solute_j,
				"solute_k": solute_k,
				"temperature": temp,
				"state": state,
				"model": model_name,
				"ri_ii": round(ri_ii, 3),
				"ri_ij": round(ri_ij, 3),
				"ri_jj": round(ri_jj, 3),
				"ri_jk": round(ri_jk, 3),
				"ri_kk": round(ri_kk, 3),
				"ri_ik": round(ri_ik, 3),
			}
			
			# 显示结果
			self.display_results(results)
			
			# 更新图表
			self.update_chart(results)
			
			# 更新状态栏
			self.update_status(f"已完成二阶相互作用系数计算")
		
		except Exception as e:
			QMessageBox.critical(self, "计算错误", f"发生错误: {str(e)}")
			self.update_status("计算失败")
	
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
		"""显示二阶相互作用系数计算结果"""
		current_timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		current_text = self.result_text.toPlainText()
		
		if current_text:
			result_text = f"\n{'-' * 50}\n\n"
		else:
			result_text = ""
		
		result_text += f"记录时间: {current_timestamp_str}\n"
		result_text += f"二阶相互作用系数计算结果:\n\n"
		result_text += f"基体元素: {results['solvent']}\n"
		result_text += f"溶质 i: {results['solute_i']}\n"
		result_text += f"溶质 j: {results['solute_j']}\n"
		result_text += f"溶质 k: {results['solute_k']}\n"
		result_text += f"温度: {results['temperature']} K\n"
		result_text += f"状态: {results['state']}\n"
		result_text += f"外推模型: {results['model']}\n\n"
		result_text += f"ρi^ii: {results['ri_ii']}\n"
		result_text += f"ρi^ij: {results['ri_ij']}\n"
		result_text += f"ρi^ik: {results['ri_ik']}\n"
		result_text += f"ρi^jj: {results['ri_jj']}\n"
		result_text += f"ρi^jk: {results['ri_jk']}\n"
		result_text += f"ρi^kk: {results['ri_kk']}\n"
		
		if current_text:
			self.result_text.append(result_text)
		else:
			self.result_text.setText(result_text)
		
		# 自动滚动到底部
		self.result_text.verticalScrollBar().setValue(
				self.result_text.verticalScrollBar().maximum())
	
	def update_chart (self, results):
		"""更新二阶相互作用系数图表"""
		self.canvas.axes.clear()
		
		# 数据
		solute_i = results["solute_i"]
		solute_j = results["solute_j"]
		solute_k = results["solute_k"]
		
		# 创建更具数学意义的标签
		coefficients = [
			f'$\\rho_{{{results['solute_i']}}}^{{{results['solute_i']},{results['solute_i']}}}$',
			f'$\\rho_{{{results['solute_i']}}}^{{{results['solute_i']},{results['solute_j']}}}$',
			f'$\\rho_{{{results['solute_i']}}}^{{{results['solute_i']},{results['solute_k']}}}$',
			f'$\\rho_{{{results['solute_i']}}}^{{{results['solute_j']},{results['solute_j']}}}$',
			f'$\\rho_{{{results['solute_i']}}}^{{{results['solute_j']},{results['solute_k']}}}$',
			f'$\\rho_{{{results['solute_i']}}}^{{{results['solute_k']},{results['solute_k']}}}$'
		]
		
		values = [
			results['ri_ii'],
			results['ri_ij'],
			results['ri_ik'],
			results['ri_jj'],
			results['ri_jk'],
			results['ri_kk']
		]
		
		# 创建柱状图
		colors = ['#3498db', '#2ecc71', '#e74c3c', '#9b59b6', '#f1c40f', '#e67e22']
		bars = self.canvas.axes.bar(coefficients, values, color=colors[:len(values)])
		
		# 添加数值标签
		self.setup_value_labels(self.canvas.axes, bars, values)
		
		if values:
			self.set_fixed_y_axis(self.canvas.axes, values, -20.0, 20.0)
		else:
			self.canvas.axes.set_ylim(-20.0, 20.0)
		
		# 设置图表属性
		solvent = results["solvent"]
		title = f'二阶相互作用系数 ({solvent}-{solute_i}-{solute_j}'
		if solute_k and solute_k.strip():
			title += f'-{solute_k}'
		title += ')'
		
		self.canvas.axes.set_title(title, fontsize=14)
		self.canvas.axes.set_ylabel('系数值', fontsize=13)
		self.canvas.axes.grid(True, axis='y', linestyle='--', alpha=0.7)
		
		# 旋转x轴标签以避免重叠
		self.canvas.axes.tick_params(axis='x', rotation=45, labelsize=10)
		
		self.canvas.fig.tight_layout()
		self.canvas.draw()
	
	def setup_value_labels (self, axes, bars, values):
		"""设置数值标签"""
		for i, bar in enumerate(bars):
			height = bar.get_height()
			value = values[i]
			
			if abs(height) > 0.0:
				y_pos = height / 2
				va = 'center'
				color = 'white'
				fontweight = 'bold'
			else:
				if height >= 0:
					y_pos = height + 1.0
					va = 'bottom'
				else:
					y_pos = height - 1.0
					va = 'top'
				color = 'black'
				fontweight = 'normal'
			
			axes.text(
					bar.get_x() + bar.get_width() / 2., y_pos,
					f'{value:.3f}', ha='center', va=va,
					fontsize=10, color=color, fontweight=fontweight
			)
	
	def set_fixed_y_axis (self, axes, values, y_min, y_max):
		"""设置固定的Y轴范围"""
		max_values = max(values)
		min_values = min(values)
		
		if max_values * min_values < 0:
			y_max_calc = max_values * 1.2
			y_min_calc = min_values * 1.2
		elif max_values == 0 and min_values == 0:
			y_max_calc = y_max
			y_min_calc = y_min
		elif max_values * min_values == 0:
			if max_values > 0:
				y_max_calc = max_values * 1.2
				y_min_calc = y_min
			else:
				y_max_calc = y_max
				y_min_calc = min_values * 1.2
		elif max_values > 0:
			y_max_calc = max_values * 1.2
			y_min_calc = 0
		else:
			y_max_calc = 0
			y_min_calc = min_values * 1.2
		
		axes.set_ylim(y_min_calc, y_max_calc)
	
	def init_chart (self):
		"""初始化二阶相互作用系数图表"""
		self.canvas.axes.clear()
		self.canvas.axes.set_title('二阶相互作用系数', fontsize=14)
		self.canvas.axes.set_ylabel('系数值', fontsize=12)
		self.canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.canvas.fig.tight_layout()
		self.canvas.draw()
	
	def clear_result (self):
		"""清除二阶相互作用系数计算结果"""
		self.result_text.clear()
		self.init_chart()
	
	def update_status (self, message):
		"""更新状态栏"""
		if self.parent:
			self.parent.update_status(message)