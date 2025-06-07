import re
import sys

import matplotlib
import numpy as np
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Set matplotlib font settings
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'FangSong', 'SimSun', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
matplotlib.rcParams['font.size'] = 12  # 增加图表字体大小

# 使用Matplotlib的数学文本渲染（不依赖LaTeX）
matplotlib.rcParams['text.usetex'] = False
matplotlib.rcParams['mathtext.default'] = 'regular'
# Import PyQt5 modules
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QLabel, QLineEdit, QComboBox, QPushButton,
                             QSplitter, QFrame, QGroupBox, QTextEdit, QMessageBox,
                             QStatusBar)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QGuiApplication

# 导入计算模块 (确保这些文件存在)
from core.element import Element
from models.extrapolation_models import BinaryModel
from models.activity_interaction_parameters import TernaryMelts
# from Activity import ActivityCoefficient # Interaction tab doesn't directly use this
from core.database_handler import Melt


class MplCanvas(FigureCanvas):
	"""Matplotlib画布类"""
	axes: Axes

	def __init__ (self, parent=None, width=7, height=6, dpi=100):
		self.fig = Figure(figsize=(width, height), dpi=dpi)
		self.axes = self.fig.add_subplot(111)
		super(MplCanvas, self).__init__(self.fig)


class InteractionCalculatorGUI(QMainWindow):
	def __init__ (self):
		super().__init__()
		self.setWindowTitle("AlloyAct Pro - 相互作用系数计算器")
		self.resize(1400, 900) # Keep original size for context, adjust as needed
		self.setMinimumSize(1000, 900) # Keep original size for context

		# 新版PyQt5中将窗口居中
		qr = self.frameGeometry()
		cp = QGuiApplication.primaryScreen().availableGeometry().center()
		qr.moveCenter(cp)
		self.move(qr.topLeft())

		# 创建计算实例
		self.binary_model = BinaryModel()
		# self.activity_coefficient = ActivityCoefficient() # Not needed for this tab

		# 设置应用字体（增大字号）
		self.app_font = QFont("Microsoft YaHei UI", 12)  # 增大基础字体
		QApplication.setFont(self.app_font)

		# 创建主窗口布局
		self.central_widget = QWidget()
		self.setCentralWidget(self.central_widget)

		# 主布局
		self.main_layout = QVBoxLayout(self.central_widget)

		# 创建标题栏
		self.create_title_bar()


		# --- 只创建相互作用系数选项卡 ---
		# 创建一个基础的 QWidget 来容纳相互作用系数的布局
		interaction_widget = QWidget()
		self.main_layout.addWidget(interaction_widget) # Directly add the widget, not via tabs
		self.create_interaction_tab(interaction_widget) # Pass the widget to populate it
		# --- End of tab creation ---


		# 创建状态栏
		self.status_bar = QStatusBar()
		self.setStatusBar(self.status_bar)
		self.update_status("就绪 - 请输入相互作用系数计算参数")

		# 设置全局样式
		self.set_global_styles()

	def set_global_styles (self):
		"""设置全局样式"""
		# 设置输入框样式
		self.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                background-color: white;
                font-size: 13pt;
            }
            QComboBox {
                padding: 8px;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                background-color: white;
                selection-background-color: #3498db;
                font-size: 13pt;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #b8b8b8;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QPushButton {
                padding: 10px 20px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13pt;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f618d;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 15px;
                font-size: 13pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                font-size: 13pt;
            }
            QTextEdit {
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                background-color: white;
                font-family: "Microsoft YaHei UI";
                font-size: 12pt;
            }
            QLabel {
                font-size: 12pt;
            }
            QStatusBar {
                background-color: #e0e0e0;
                font-size: 12pt;
            }
            QDoubleSpinBox {
                padding: 8px;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                background-color: white;
                font-size: 13pt;
            }
        """)

	def create_title_bar (self):
		"""创建标题栏"""
		title_layout = QHBoxLayout()

		# 标题
		title_font = QFont("Microsoft YaHei UI", 18, QFont.Bold)  # 增大标题字体
		title_label = QLabel("合金热力学计算器 - 相互作用系数") # Modified title
		title_label.setFont(title_font)
		title_label.setStyleSheet("color: #2c3e50;")

		# 版本
		version_font = QFont("Microsoft YaHei UI", 12)
		version_label = QLabel("版本 1.0 (Interaction Module)") # Modified version
		version_label.setFont(version_font)
		version_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

		title_layout.addWidget(title_label)
		title_layout.addStretch()
		title_layout.addWidget(version_label)

		self.main_layout.addLayout(title_layout)

	def update_status (self, message):
		"""更新状态栏消息"""
		self.status_bar.showMessage(message)

	def create_interaction_tab (self, parent_widget): # Takes parent widget to add layout
		"""创建相互作用系数计算控件"""
		interact_layout = QVBoxLayout(parent_widget) # Use the passed widget's layout

		# 创建分割器
		splitter = QSplitter(Qt.Horizontal)
		interact_layout.addWidget(splitter)

		# 左侧输入面板
		left_widget = QWidget()
		left_layout = QVBoxLayout(left_widget)

		# 创建输入字段分组
		input_group = QGroupBox("输入参数")
		input_layout = QGridLayout(input_group)

		# 基体元素
		input_layout.addWidget(QLabel("基体元素:"), 0, 0,Qt.AlignRight)
		self.interact_solvent = QLineEdit("Fe")
		input_layout.addWidget(self.interact_solvent, 0, 1)
		self.interact_solvent.setPlaceholderText('e.g.:Fe')

		# 溶质 i
		input_layout.addWidget(QLabel("溶质 i:"), 1, 0,Qt.AlignRight)
		self.interact_solute_i = QLineEdit("C")
		input_layout.addWidget(self.interact_solute_i, 1, 1)
		self.interact_solute_i.setPlaceholderText('e.g.:C')

		# 溶质 j
		input_layout.addWidget(QLabel("溶质 j:"), 2, 0,Qt.AlignRight)
		self.interact_solute_j = QLineEdit("Si")
		input_layout.addWidget(self.interact_solute_j, 2, 1)
		self.interact_solute_j.setPlaceholderText('e.g.:Si')

		# 温度
		input_layout.addWidget(QLabel("温度 (K):"), 3, 0,Qt.AlignRight)
		self.interact_temp = QLineEdit("1873.0")
		input_layout.addWidget(self.interact_temp, 3, 1)
		self.interact_temp.setPlaceholderText('e.g.:1873.0')

		# 状态
		input_layout.addWidget(QLabel("状态:"), 4, 0,Qt.AlignRight)
		self.interact_state = QComboBox()
		self.interact_state.addItems(["liquid", "solid"])
		input_layout.addWidget(self.interact_state, 4, 1)

		# 外推模型
		input_layout.addWidget(QLabel("外推模型:"), 5, 0,Qt.AlignRight)
		self.interact_model = QComboBox()
		self.interact_model.addItems(["UEM1", "UEM2", "GSM", "Muggianu"])
		input_layout.addWidget(self.interact_model, 5, 1)

		# 添加分隔线
		line = QFrame()
		line.setFrameShape(QFrame.HLine)
		line.setFrameShadow(QFrame.Sunken)
		input_layout.addWidget(line, 6, 0, 1, 3)

		# 计算按钮
		btn_layout = QHBoxLayout()
		calculate_btn = QPushButton("计算相互作用系数")
		calculate_btn.clicked.connect(self.calculate_interaction)
		btn_layout.addWidget(calculate_btn)

		clear_btn = QPushButton("清除结果")
		clear_btn.clicked.connect(self.clear_interact_result)
		btn_layout.addWidget(clear_btn)

		input_layout.addLayout(btn_layout, 7, 0, 1, 3)

		# 添加输入分组到左侧布局
		left_layout.addWidget(input_group)
		left_layout.addStretch()

		# 右侧结果面板
		right_widget = QWidget()
		right_layout = QVBoxLayout(right_widget)

		# 结果文本区域
		result_group = QGroupBox("计算结果")
		result_layout = QVBoxLayout(result_group)

		self.interact_result = QTextEdit()
		self.interact_result.setReadOnly(True)
		result_layout.addWidget(self.interact_result)

		# 图表区域
		chart_group = QGroupBox("数据可视化")
		chart_layout = QVBoxLayout(chart_group)

		self.interact_canvas = MplCanvas(self, width=5, height=4, dpi=100)
		chart_layout.addWidget(self.interact_canvas)

		# 添加结果分组和图表分组到右侧布局
		right_layout.addWidget(result_group, 1)
		right_layout.addWidget(chart_group, 1)

		# 添加左右面板到分割器
		splitter.addWidget(left_widget)
		splitter.addWidget(right_widget)
		splitter.setSizes([300, 700])  # 设置初始分割比例

		# 初始绘制空图表
		self.init_interact_chart()

	def setup_value_labels (self, axes:matplotlib.axes.Axes, bars, values, min_height=0.0):
		"""设置统一的数值标签位置"""
		for i, bar in enumerate(bars):
			height = bar.get_height()
			value = values[i]

			# 确定标签位置和样式
			if abs(height) > min_height and height != 0: # Avoid division by zero for zero height
				# 对于较高的柱子，将标签放在柱内
				y_pos = height / 2 if height != 0 else 0.05 # Adjust if height is 0
				va = 'center'
				color = 'white'
				fontweight = 'bold'
			else:
				# 对于较矮的柱子，将标签放在柱子上方或下方
				if height >= 0:
					y_pos = height + 0.05 * max(1, abs(axes.get_ylim()[1] - axes.get_ylim()[0]) / 2) # Scale offset based on y-range
					va = 'bottom'
				else:
					y_pos = height - 0.05 * max(1, abs(axes.get_ylim()[1] - axes.get_ylim()[0]) / 2) # Scale offset
					va = 'top'
				color = 'black'
				fontweight = 'normal'

			axes.text(
					bar.get_x() + bar.get_width() / 2., y_pos,
					f'{value:.3f}', ha='center', va=va,
					fontsize=10, color=color, fontweight=fontweight
			)

	def set_fixed_y_axis(self,axes:matplotlib.axes.Axes,values,y_min_default=-10.0,y_max_default=10.0):
		"""设置Y轴范围，优先考虑实际数据范围，并增加边距"""
		if not values: # Handle empty data
			axes.set_ylim(y_min_default, y_max_default)
			return

		max_val = max(values) if values else y_max_default
		min_val = min(values) if values else y_min_default

		# Determine padding based on the range, ensuring it's not zero
		data_range = max_val - min_val
		padding = data_range * 0.1 if data_range > 1e-6 else 1.0 # Add padding, minimum 1 if range is tiny

		y_max = max_val + padding
		y_min = min_val - padding

		# Handle cases where min/max are near zero or cross zero
		if max_val > 0 and min_val < 0:
			# Data crosses zero, use calculated padding
			pass
		elif max_val >= 0 and min_val >= 0:
			# All positive or zero
			y_min = 0 if min_val < padding else min_val - padding # Start from 0 if min is close to 0
			y_max = max_val + padding
		elif max_val <= 0 and min_val <= 0:
			# All negative or zero
			y_max = 0 if abs(max_val) < padding else max_val + padding # End at 0 if max is close to 0
			y_min = min_val - padding

		# Ensure min < max
		if y_min >= y_max:
			y_min = y_min_default
			y_max = y_max_default

		axes.set_ylim(y_min, y_max)


	def clear_interact_result (self):
		"""清除相互作用系数计算结果"""
		self.interact_result.clear()
		self.init_interact_chart()

	def init_interact_chart (self):
		"""初始化相互作用系数图表"""
		self.interact_canvas.axes.clear()
		self.interact_canvas.axes.set_title('相互作用系数比较')
		self.interact_canvas.axes.set_ylabel('相互作用系数')
		self.interact_canvas.axes.set_xticklabels([])  # 隐藏x轴标签
		self.interact_canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.interact_canvas.fig.tight_layout()
		self.interact_canvas.draw()

	def update_interact_chart (self, results):
		"""更新相互作用系数图表"""
		self.interact_canvas.axes.clear()

		# 数据
		models = ['UEM1', 'UEM2-Adv'] # Updated model name
		values = [
			results['sij_uem1'],
			results['sij_uem2'],
		]
		colors = ['#3498db', '#2ecc71']

		# Add experimental value if available
		if not np.isnan(results['sij_experimental']):
			models.append('实验值')
			values.append(results['sij_experimental'])
			colors.append('#e74c3c')

		# 创建柱状图
		bars = self.interact_canvas.axes.bar(models, values, color=colors)

		# Set Y axis before adding labels for better scaling
		self.set_fixed_y_axis(self.interact_canvas.axes, values, -10.0, 10.0)

		# 添加数值标签
		self.setup_value_labels(self.interact_canvas.axes, bars, values)


		# 设置图表属性
		solvent = results["solvent"]
		solute_i = results["solute_i"]
		solute_j = results["solute_j"]
		self.interact_canvas.axes.set_title(
				f'${solute_j}$ 对 ${solute_i}$ 在 ${solvent}$ 中的相互作用系数 ($\epsilon$)', fontsize=14) # Use epsilon symbol
		self.interact_canvas.axes.set_ylabel(f'$\\varepsilon^{{{solute_j}}}_{{{solute_i}}}$', fontsize=14) # Proper LaTeX label
		self.interact_canvas.axes.grid(True, axis='y', linestyle='--', alpha=0.7)
		self.interact_canvas.axes.tick_params(axis='x', labelsize=11) # Slightly larger x labels

		self.interact_canvas.fig.tight_layout()
		self.interact_canvas.draw()

	def validate_input (self, fields):
		"""验证输入字段"""
		for field, name in fields:
			if not field.text().strip():
				QMessageBox.critical(self, "输入错误", f"{name}不能为空")
				return False
		return True

	def parse_composition (self, alloy_str):
		"""解析合金成分字符串为字典"""
		comp_dict = {}
		# Improved regex to handle various formats (e.g., FeC0.03Si0.1)
		pattern = r"([A-Z][a-z]?)(\d*\.?\d+|\d+)"
		pos = 0
		while pos < len(alloy_str):
			match = re.match(pattern, alloy_str[pos:])
			if match:
				element = match.group(1)
				try:
					# Handle cases like 'Fe' without explicit number (assumed 1 unless normalized later)
					amount_str = match.group(2) if match.group(2) else '1'
					amount = float(amount_str)
				except ValueError:
					QMessageBox.critical(self, "成分解析错误", f"无法解析元素 '{element}' 的含量: '{match.group(2)}'")
					return None # Indicate error
				comp_dict[element] = amount
				pos += match.end()
			else:
				# Skip non-matching characters (e.g., spaces) or report error
				unmatched_char = alloy_str[pos]
				if not unmatched_char.isspace(): # Report error only for non-space characters
					QMessageBox.critical(self, "成分解析错误", f"无法识别的字符或格式: '{unmatched_char}' 在位置 {pos}")
					return None # Indicate error
				pos += 1


		# 归一化 (Optional - depends on how calculation modules expect input)
		# If normalization is needed:
		# if comp_dict:
		#     total = sum(comp_dict.values())
		#     if abs(total - 1.0) > 1e-6: # Normalize only if not already close to 1
		#         if total <= 0:
		#              QMessageBox.critical(self, "成分解析错误", "总含量必须大于0才能归一化")
		#              return None
		#         for element in comp_dict:
		#             comp_dict[element] /= total
		# else:
		#     QMessageBox.critical(self, "成分解析错误", "未能解析出任何元素成分")
		#     return None # Indicate error

		return comp_dict

	def get_model_function (self, model_name):
		"""获取对应的模型函数"""
		# Assuming BinaryModel class has these methods
		if model_name == "UEM1":
			return self.binary_model.UEM1
		elif model_name == "UEM2":
			return self.binary_model.UEM2
		elif model_name == "GSM":
			return self.binary_model.GSM
		elif model_name == "Muggianu":
			# Ensure Muggianu is implemented in BinaryModel
			if hasattr(self.binary_model, 'Muggianu'):
				return self.binary_model.Muggianu
			else:
				QMessageBox.warning(self, "模型未实现", "Muggianu 模型当前不可用，将使用 UEM1 代替。")
				return self.binary_model.UEM1 # Fallback
		else:
			QMessageBox.warning(self, "未知模型", f"未知的模型 '{model_name}'，将使用 UEM1 代替。")
			return self.binary_model.UEM1 # Default fallback

	def calculate_interaction (self):
		"""计算相互作用系数"""
		try:
			# 验证输入
			fields = [
				(self.interact_solvent, "基体元素"),
				(self.interact_solute_i, "溶质 i"),
				(self.interact_solute_j, "溶质 j"),
				(self.interact_temp, "温度")
			]

			if not self.validate_input(fields):
				return

			# 获取输入值
			solvent = self.interact_solvent.text().strip()
			solute_i = self.interact_solute_i.text().strip()
			solute_j = self.interact_solute_j.text().strip()
			try:
				temp = float(self.interact_temp.text())
				if temp <= 0:
					QMessageBox.critical(self, "输入错误", "温度必须是正数")
					return
			except ValueError:
				QMessageBox.critical(self, "输入错误", "温度必须是数值")
				return

			state = self.interact_state.currentText()
			model_name = self.interact_model.currentText()

			# 更新状态栏
			self.update_status(f"正在计算 {solute_j} 对 {solute_i} 在 {solvent} 中的相互作用系数...")

			# 创建元素实例
			try:
				solv = Element(solvent)
				solui = Element(solute_i)
				soluj = Element(solute_j)
			except Exception as e: # Catch potential errors during Element initialization (e.g., invalid element)
				QMessageBox.critical(self, "元素错误", f"创建元素实例时出错: {e}")
				self.update_status("计算失败 - 无效的元素")
				return

			# 创建 Melt 对象获取实验值 (Handle potential errors)
			melt = None
			sij_exp = float('nan')
			try:
				if state == "liquid":
					melt = Melt(solvent, solute_i, solute_j, t = temp)
					sij_exp = melt.sji # Assuming Melt class and sji attribute exist
					if sij_exp is None: # Explicitly check for None if Melt might return it
						sij_exp = float('nan')
			except Exception as e:
				print(f"无法获取实验值: {e}") # Log the error, don't stop calculation
				sij_exp = float('nan')


			# 获取模型函数
			model_func = self.get_model_function(model_name)
			if model_func is None: # Check if get_model_function indicated an error
			    self.update_status("计算失败 - 无效的模型")
			    return

			# 创建 TernaryMelts 实例
			# Placeholder for entropy_judge logic if needed
			is_entropy = False
			try:
				ternary = TernaryMelts(temp, state, is_entropy)
			except Exception as e:
				QMessageBox.critical(self, "计算模块错误", f"初始化 TernaryMelts 时出错: {e}")
				self.update_status("计算失败 - 计算模块错误")
				return

			# 计算相互作用系数
			sij_uem1 = ternary.activity_interact_coefficient_1st(
					solv, solui, soluj, temp, state, self.binary_model.UEM1, "UEM1") # Calculate with UEM1 explicitly

			# Calculate with the selected model for comparison/display
			sij_selected_model = ternary.activity_interact_coefficient_1st(
					solv, solui, soluj, temp, state, model_func, model_name)

			# Calculate with UEM2 explicitly for the chart comparison
			sij_uem2_adv = ternary.activity_interact_coefficient_1st(
					solv, solui, soluj, temp, state, self.binary_model.UEM2, "UEM2-Adv") # Use UEM2 for the second bar


			# 准备结果
			results = {
				"solvent": solvent,
				"solute_i": solute_i,
				"solute_j": solute_j,
				"temperature": temp,
				"state": state,
				"model": model_name, # The model selected by the user
				"sij_selected": round(sij_selected_model, 3), # Result for the selected model
				"sij_uem1": round(sij_uem1, 3),        # Result for UEM1 (for chart/comparison)
				"sij_uem2": round(sij_uem2_adv, 3),     # Result for UEM2-Adv (for chart/comparison)
				"sij_experimental": sij_exp if not np.isnan(sij_exp) else float('nan') # Use NaN if not available
			}

			# 显示结果 - 添加到当前结果而不是清空
			current_text = self.interact_result.toPlainText()
			if current_text:
				# 添加分隔线
				result_text = f"\n{'-' * 50}\n\n"
			else:
				result_text = ""

			result_text += f"相互作用系数计算结果:\n\n"
			result_text += f"基体元素: {results['solvent']}\n"
			result_text += f"溶质 i: {results['solute_i']}\n"
			result_text += f"溶质 j: {results['solute_j']}\n"
			result_text += f"温度: {results['temperature']} K\n"
			result_text += f"状态: {results['state']}\n"
			result_text += f"选择的外推模型: {results['model']}\n\n" # Label clearly which model result this is
			result_text += f"{results['model']} 模型系数 (εij): {results['sij_selected']}\n"
			# Optionally show other models for comparison in text:
			# result_text += f"UEM1 模型系数 (εij): {results['sij_uem1']}\n"
			# result_text += f"UEM2-Adv 模型系数 (εij): {results['sij_uem2']}\n"


			if not np.isnan(results['sij_experimental']):
				exp_value = f"{results['sij_experimental']:.3f}"
				result_text += f"实验值 (εij): {exp_value}\n"
			else:
				result_text += "实验值 (εij): 无可用数据\n"

			if current_text:
				self.interact_result.append(result_text)
			else:
				self.interact_result.setText(result_text)

			# 自动滚动到底部
			self.interact_result.verticalScrollBar().setValue(
					self.interact_result.verticalScrollBar().maximum())

			# 更新图表 (Pass UEM1, UEM2, and Exp results to chart)
			chart_results = {
			    "solvent": solvent, "solute_i": solute_i, "solute_j": solute_j,
                "sij_uem1": results['sij_uem1'],
                "sij_uem2": results['sij_uem2'], # Pass UEM2 result for chart
                "sij_experimental": results['sij_experimental']
            }
			self.update_interact_chart(chart_results)


			# 更新状态栏
			self.update_status(f"已完成 {solute_j} 对 {solute_i} 在 {solvent} 中的相互作用系数计算")

		except Exception as e:
			QMessageBox.critical(self, "计算错误", f"计算过程中发生意外错误: {str(e)}")
			self.update_status("计算失败")
			import traceback
			traceback.print_exc() # Print detailed error for debugging


# 主程序入口
if __name__ == "__main__":
	app = QApplication(sys.argv)

	# 设置高DPI缩放
	app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
	app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

	window = InteractionCalculatorGUI()
	window.show()
	sys.exit(app.exec_())