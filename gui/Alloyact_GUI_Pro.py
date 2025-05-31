import sys
import math
import re
import numpy as np
import matplotlib
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# Set matplotlib font settings
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'FangSong', 'SimSun', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['font.size'] = 12
matplotlib.rcParams['text.usetex'] = False
matplotlib.rcParams['mathtext.default'] = 'regular'

# Import PyQt5 modules
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QLabel, QLineEdit, QComboBox, QPushButton,
                             QTabWidget, QSplitter, QFrame, QGroupBox, QTextEdit, QMessageBox,
                             QStatusBar, QDoubleSpinBox, QMenuBar, QAction)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QGuiApplication, QIcon

# 导入计算模块
from models.extrapolation_models import BinaryModel
from models.activity_interaction_parameters import TernaryMelts
from calculations.activity_calculator import ActivityCoefficient
from core.element import Element
from core.database_handler import Melt

# 导入新的界面组件
from gui.ActivityVaryTemperatureWdget import ActivityTemperatureVariationWidget
from gui.ActivityVaryConcentrationWdget import CompositionVariationWidget


class MplCanvas(FigureCanvas):
	"""Matplotlib画布类"""
	axes: Axes
	
	def __init__ (self, parent=None, width=7, height=6, dpi=100):
		self.fig = Figure(figsize=(width, height), dpi=dpi)
		self.axes = self.fig.add_subplot(111)
		super(MplCanvas, self).__init__(self.fig)


class AlloyActProGUI(QMainWindow):
	def __init__ (self):
		super().__init__()
		self.setWindowTitle("AlloyAct Pro - 合金热力学计算器")
		self.resize(1400, 1000)
		self.setMinimumSize(1000, 1200)
		
		# 窗口居中
		self.center_window()
		
		# 创建计算实例
		self.binary_model = BinaryModel()
		self.activity_coefficient = ActivityCoefficient()
		
		# 设置应用字体
		self.app_font = QFont("Microsoft YaHei UI", 12)
		QApplication.setFont(self.app_font)
		
		# 创建界面
		self.setup_ui()
		self.setup_menu_bar()
		self.set_global_styles()
	
	def center_window (self):
		"""窗口居中"""
		qr = self.frameGeometry()
		cp = QGuiApplication.primaryScreen().availableGeometry().center()
		qr.moveCenter(cp)
		self.move(qr.topLeft())
	
	def setup_ui (self):
		"""设置用户界面"""
		# 创建主窗口布局
		self.central_widget = QWidget()
		self.setCentralWidget(self.central_widget)
		
		# 主布局
		self.main_layout = QVBoxLayout(self.central_widget)
		
		# 创建标题栏
		self.create_title_bar()
		
		# 创建选项卡控件
		self.tabs = QTabWidget()
		self.main_layout.addWidget(self.tabs)
		
		# 设置选项卡样式
		self.setup_tab_styles()
		
		# 创建基础计算选项卡
		self.create_basic_calculation_tabs()
		
		# 创建高级分析选项卡
		self.create_advanced_analysis_tabs()
		
		# 创建状态栏
		self.status_bar = QStatusBar()
		self.setStatusBar(self.status_bar)
		self.update_status("就绪 - 请选择计算类型并输入参数")
		
		# 设置选项卡切换事件
		self.tabs.currentChanged.connect(self.on_tab_changed)
	
	def setup_menu_bar (self):
		"""设置菜单栏"""
		menubar = self.menuBar()
		
		# 文件菜单
		file_menu = menubar.addMenu('文件(&F)')
		
		exit_action = QAction('退出(&E)', self)
		exit_action.setShortcut('Ctrl+Q')
		exit_action.triggered.connect(self.close)
		file_menu.addAction(exit_action)
		
		# 工具菜单
		tools_menu = menubar.addMenu('工具(&T)')
		
		# 温度变化分析
		temp_variation_action = QAction('温度变化分析(&T)', self)
		temp_variation_action.setShortcut('Ctrl+T')
		temp_variation_action.triggered.connect(self.switch_to_temperature_tab)
		tools_menu.addAction(temp_variation_action)
		
		# 浓度变化分析
		conc_variation_action = QAction('浓度变化分析(&C)', self)
		conc_variation_action.setShortcut('Ctrl+C')
		conc_variation_action.triggered.connect(self.switch_to_concentration_tab)
		tools_menu.addAction(conc_variation_action)
		
		tools_menu.addSeparator()
		
		# 批量计算
		batch_calc_action = QAction('批量计算(&B)', self)
		batch_calc_action.setShortcut('Ctrl+B')
		batch_calc_action.triggered.connect(self.open_batch_calculation)
		tools_menu.addAction(batch_calc_action)
		
		# 帮助菜单
		help_menu = menubar.addMenu('帮助(&H)')
		
		about_action = QAction('关于(&A)', self)
		about_action.triggered.connect(self.show_about)
		help_menu.addAction(about_action)
	
	def setup_tab_styles (self):
		"""设置选项卡样式"""
		self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d7d7d7;
                background: #f5f5f5;
            }
            QTabBar::tab {
                background: #e0e0e0;
                color: #333333;
                padding: 10px 18px;
                margin-right: 2px;
                border: 1px solid #b8b8b8;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
                font-size: 16px;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background: #d0d0d0;
            }
        """)
	
	def create_title_bar (self):
		"""创建标题栏"""
		title_layout = QHBoxLayout()
		
		# 标题
		title_font = QFont("Microsoft YaHei UI", 18, QFont.Bold)
		title_label = QLabel("合金热力学计算器")
		title_label.setFont(title_font)
		title_label.setStyleSheet("color: #2c3e50; padding: 10px;")
		
		# 版本
		version_font = QFont("Microsoft YaHei UI", 12)
		version_label = QLabel("版本 2.0")
		version_label.setFont(version_font)
		version_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		version_label.setStyleSheet("color: #7f8c8d; padding: 10px;")
		
		title_layout.addWidget(title_label)
		title_layout.addStretch()
		title_layout.addWidget(version_label)
		
		#self.main_layout.addLayout(title_layout)
	
	def create_basic_calculation_tabs (self):
		"""创建基础计算选项卡"""
		# 活度计算选项卡
		self.create_activity_tab()
		
		# 相互作用系数计算选项卡
		self.create_interaction_tab()
		
		# 二阶相互作用系数计算选项卡
		self.create_second_order_tab()
	
	def create_advanced_analysis_tabs (self):
		"""创建高级分析选项卡"""
		# 温度变化分析选项卡
		self.create_temperature_variation_tab()
		
		# 浓度变化分析选项卡
		self.create_concentration_variation_tab()
	
	def create_temperature_variation_tab (self):
		"""创建温度变化分析选项卡"""
		# 创建温度变化分析组件实例
		self.temp_variation_widget = ActivityTemperatureVariationWidget(self)
		
		# 添加到选项卡
		self.tabs.addTab(self.temp_variation_widget, "温度变化分析")
	
	def create_concentration_variation_tab (self):
		"""创建浓度变化分析选项卡"""
		# 创建浓度变化分析组件实例
		self.conc_variation_widget = CompositionVariationWidget(self)
		
		# 添加到选项卡
		self.tabs.addTab(self.conc_variation_widget, "浓度变化分析")
	
	def switch_to_temperature_tab (self):
		"""切换到温度变化分析选项卡"""
		# 查找温度变化分析选项卡的索引
		for i in range(self.tabs.count()):
			if self.tabs.tabText(i) == "温度变化分析":
				self.tabs.setCurrentIndex(i)
				
				# 如果主界面有输入数据，自动填充
				if hasattr(self, 'activity_alloy') and self.activity_alloy.text().strip():
					self.temp_variation_widget.matrix_input.setText(self.activity_alloy.text())
					self.temp_variation_widget.update_element_dropdowns()
				break
	
	def switch_to_concentration_tab (self):
		"""切换到浓度变化分析选项卡"""
		# 查找浓度变化分析选项卡的索引
		for i in range(self.tabs.count()):
			if self.tabs.tabText(i) == "浓度变化分析":
				self.tabs.setCurrentIndex(i)
				
				# 如果主界面有输入数据，自动填充
				if hasattr(self, 'activity_alloy') and self.activity_alloy.text().strip():
					self.conc_variation_widget.matrix_input.setText(self.activity_alloy.text())
					self.conc_variation_widget.update_element_dropdowns()
				break
	
	def create_activity_tab (self):
		"""创建活度计算选项卡"""
		activity_widget = QWidget()
		activity_layout = QVBoxLayout(activity_widget)
		
		# 创建分割器
		splitter = QSplitter(Qt.Horizontal)
		activity_layout.addWidget(splitter)
		
		# 左侧输入面板
		left_widget = self.create_input_panel("活度计算", [
			("合金成分:", "activity_alloy", "Fe0.70C0.03Si0.27", "e.g.: Fe0.7C0.03Si0.27"),
			("基体元素:", "activity_solvent", "Fe", "e.g.: Fe"),
			("溶质元素(i):", "activity_solute", "C", "e.g.: C"),
			("温度 (K):", "activity_temp", "1873.0", "e.g.: 1873.0"),
		], [
			                                      ("状态:", "activity_state", ["liquid", "solid"]),
			                                      ("外推模型:", "activity_model", ["UEM1", "UEM2", "GSM", "Muggianu"])
		                                      ], self.calculate_activity, self.clear_activity_result)
		
		# 右侧结果面板
		right_widget = self.create_results_panel("activity")
		
		splitter.addWidget(left_widget)
		splitter.addWidget(right_widget)
		splitter.setSizes([400, 800])
		
		# 初始绘制空图表
		self.init_activity_chart()
		
		# 添加到选项卡
		self.tabs.addTab(activity_widget, "活度计算")
	
	def create_interaction_tab (self):
		"""创建相互作用系数计算选项卡"""
		interact_widget = QWidget()
		interact_layout = QVBoxLayout(interact_widget)
		
		# 创建分割器
		splitter = QSplitter(Qt.Horizontal)
		interact_layout.addWidget(splitter)
		
		# 左侧输入面板
		left_widget = self.create_input_panel("相互作用系数计算", [
			("基体元素:", "interact_solvent", "Fe", "e.g.: Fe"),
			("溶质 i:", "interact_solute_i", "C", "e.g.: C"),
			("溶质 j:", "interact_solute_j", "Si", "e.g.: Si"),
			("温度 (K):", "interact_temp", "1873.0", "e.g.: 1873.0"),
		], [
			                                      ("状态:", "interact_state", ["liquid", "solid"]),
			                                      ("外推模型:", "interact_model", ["UEM1", "UEM2", "GSM", "Muggianu"])
		                                      ], self.calculate_interaction, self.clear_interact_result)
		
		# 右侧结果面板
		right_widget = self.create_results_panel("interact")
		
		splitter.addWidget(left_widget)
		splitter.addWidget(right_widget)
		splitter.setSizes([400, 800])
		
		# 初始绘制空图表
		self.init_interact_chart()
		
		# 添加到选项卡
		self.tabs.addTab(interact_widget, "相互作用系数")
	
	def create_second_order_tab (self):
		"""创建二阶相互作用系数计算选项卡"""
		second_widget = QWidget()
		second_layout = QVBoxLayout(second_widget)
		
		# 创建分割器
		splitter = QSplitter(Qt.Horizontal)
		second_layout.addWidget(splitter)
		
		# 左侧输入面板
		left_widget = self.create_input_panel("二阶相互作用系数计算", [
			("基体元素:", "second_solvent", "Al", "e.g.: Al"),
			("溶质 i:", "second_solute_i", "Si", "e.g.: Si"),
			("溶质 j:", "second_solute_j", "Cu", "e.g.: Cu"),
			("溶质 k:", "second_solute_k", "Mn", "e.g.: Mn"),
			("温度 (K):", "second_temp", "805.0", "e.g.: 805.0"),
		], [
			                                      ("状态:", "second_state", ["liquid", "solid"]),
			                                      ("外推模型:", "second_model", ["UEM1", "UEM2", "GSM", "Muggianu"])
		                                      ], self.calculate_second_order, self.clear_second_result)
		
		# 右侧结果面板
		right_widget = self.create_results_panel("second")
		
		splitter.addWidget(left_widget)
		splitter.addWidget(right_widget)
		splitter.setSizes([400, 800])
		
		# 初始绘制空图表
		self.init_second_chart()
		
		# 添加到选项卡
		self.tabs.addTab(second_widget, "二阶相互作用系数")
	
	def create_input_panel (self, title, text_inputs, combo_inputs, calc_func, clear_func):
		"""创建标准化的输入面板"""
		widget = QWidget()
		layout = QVBoxLayout(widget)
		
		# 创建输入字段分组
		input_group = QGroupBox(f"{title} - 输入参数")
		input_layout = QGridLayout(input_group)
		
		row = 0
		
		# 添加文本输入
		for label_text, attr_name, default_value, placeholder in text_inputs:
			input_layout.addWidget(QLabel(label_text), row, 0, Qt.AlignRight)
			line_edit = QLineEdit(default_value)
			line_edit.setPlaceholderText(placeholder)
			setattr(self, attr_name, line_edit)
			input_layout.addWidget(line_edit, row, 1)
			row += 1
		
		# 添加下拉框
		for label_text, attr_name, items in combo_inputs:
			input_layout.addWidget(QLabel(label_text), row, 0, Qt.AlignRight)
			combo = QComboBox()
			combo.addItems(items)
			setattr(self, attr_name, combo)
			input_layout.addWidget(combo, row, 1)
			row += 1
		
		# 添加分隔线
		line = QFrame()
		line.setFrameShape(QFrame.HLine)
		line.setFrameShadow(QFrame.Sunken)
		input_layout.addWidget(line, row, 0, 1, 2)
		row += 1
		
		# 计算按钮
		btn_layout = QHBoxLayout()
		calculate_btn = QPushButton(f"开始{title}")
		calculate_btn.clicked.connect(calc_func)
		btn_layout.addWidget(calculate_btn)
		
		clear_btn = QPushButton("清除结果")
		clear_btn.clicked.connect(clear_func)
		btn_layout.addWidget(clear_btn)
		
		input_layout.addLayout(btn_layout, row, 0, 1, 2)
		
		# 添加高级分析按钮
		advanced_layout = QHBoxLayout()
		
		if "activity" in title.lower():
			temp_btn = QPushButton("温度变化分析")
			temp_btn.clicked.connect(self.switch_to_temperature_tab)
			advanced_layout.addWidget(temp_btn)
			
			conc_btn = QPushButton("浓度变化分析")
			conc_btn.clicked.connect(self.switch_to_concentration_tab)
			advanced_layout.addWidget(conc_btn)
			
			input_layout.addLayout(advanced_layout, row + 1, 0, 1, 2)
		
		# 添加输入分组到布局
		layout.addWidget(input_group)
		layout.addStretch()
		
		return widget
	
	def create_results_panel (self, prefix):
		"""创建标准化的结果面板"""
		widget = QWidget()
		layout = QVBoxLayout(widget)
		
		# 结果文本区域
		result_group = QGroupBox("计算结果")
		result_layout = QVBoxLayout(result_group)
		
		result_text = QTextEdit()
		result_text.setReadOnly(True)
		setattr(self, f"{prefix}_result", result_text)
		result_layout.addWidget(result_text)
		
		# 图表区域
		chart_group = QGroupBox("数据可视化")
		chart_layout = QVBoxLayout(chart_group)
		
		canvas = MplCanvas(self, width=6, height=4, dpi=100)
		setattr(self, f"{prefix}_canvas", canvas)
		chart_layout.addWidget(canvas)
		
		layout.addWidget(result_group, 1)
		layout.addWidget(chart_group, 2)
		
		return widget
	
	def open_batch_calculation (self):
		"""打开批量计算功能"""
		QMessageBox.information(self, "功能开发中", "批量计算功能正在开发中，敬请期待！")
	
	def show_about (self):
		"""显示关于对话框"""
		about_text = """
        <h3>AlloyAct Pro - 合金热力学计算器</h3>
        <p><b>版本:</b> 2.0</p>
        <p><b>功能特性:</b></p>
        <ul>
        <li>活度和活度系数计算</li>
        <li>相互作用系数分析</li>
        <li>二阶相互作用系数计算</li>
        <li>温度变化分析</li>
        <li>浓度变化分析</li>
        <li>多种外推模型支持 (UEM1, UEM2, GSM, Muggianu)</li>
        </ul>
        <p><b>开发团队:</b> 材料科学实验室</p>
        <p><b>技术支持:</b> alloyact@example.com</p>
        """
		QMessageBox.about(self, "关于 AlloyAct Pro", about_text)
	
	def set_global_styles (self):
		"""设置全局样式"""
		self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }

            QLineEdit {
                padding: 10px;
                border: 2px solid #ced4da;
                border-radius: 6px;
                background-color: white;
                font-size: 13pt;
                min-height: 20px;
            }

            QLineEdit:focus {
                border-color: #007bff;
                outline: none;
            }

            QComboBox {
                padding: 10px;
                border: 2px solid #ced4da;
                border-radius: 6px;
                background-color: white;
                selection-background-color: #007bff;
                font-size: 13pt;
                min-height: 20px;
            }

            QComboBox:focus {
                border-color: #007bff;
                outline: none;
            }

            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #ced4da;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }

            QPushButton {
                padding: 12px 24px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13pt;
                min-height: 20px;
            }

            QPushButton:hover {
                background-color: #0056b3;
            }

            QPushButton:pressed {
                background-color: #004085;
            }

            QPushButton:disabled {
                background-color: #6c757d;
            }

            QGroupBox {
                font-weight: 600;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                margin-top: 15px;
                padding-top: 20px;
                font-size: 13pt;
                background-color: white;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                color: #495057;
            }

            QTextEdit {
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                font-size: 12pt;
                padding: 10px;
            }

            QLabel {
                font-size: 12pt;
                color: #495057;
                font-weight: 500;
            }

            QStatusBar {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
                font-size: 12pt;
                padding: 5px;
            }

            QDoubleSpinBox {
                padding: 10px;
                border: 2px solid #ced4da;
                border-radius: 6px;
                background-color: white;
                font-size: 13pt;
                min-height: 20px;
            }

            QMenuBar {
                background-color: #f8f9fa;
                color: #495057;
                border-bottom: 1px solid #dee2e6;
                font-size: 11pt;
            }

            QMenuBar::item {
                padding: 8px 12px;
                background: transparent;
            }

            QMenuBar::item:selected {
                background-color: #007bff;
                color: white;
            }

            QMenu {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-size: 11pt;
            }

            QMenu::item {
                padding: 8px 12px;
                border-bottom: 1px solid #f8f9fa;
            }

            QMenu::item:selected {
                background-color: #007bff;
                color: white;
            }
        """)
	
	def update_status (self, message):
		"""更新状态栏消息"""
		from datetime import datetime
		timestamp = datetime.now().strftime("%H:%M:%S")
		self.status_bar.showMessage(f"[{timestamp}] {message}")
	
	def on_tab_changed (self, index):
		"""选项卡切换事件处理"""
		tab_text = self.tabs.tabText(index)
		self.update_status(f"切换到 {tab_text} 模块")
	
	# ============================================================================
	# 计算方法部分
	# ============================================================================
	
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
		pattern = r"([A-Z][a-z]?)(\d+\.?\d*|\.\d+)"
		matches = re.finditer(pattern, alloy_str)
		
		for match in matches:
			element = match.group(1)
			amount = float(match.group(2))
			comp_dict[element] = amount
		
		# 归一化
		if comp_dict:
			total = sum(comp_dict.values())
			for element in comp_dict:
				comp_dict[element] /= total
		
		return comp_dict
	
	def get_model_function (self, model_name):
		"""获取对应的模型函数"""
		if model_name == "UEM1":
			return self.binary_model.UEM1
		elif model_name == "UEM2":
			return self.binary_model.UEM2
		elif model_name == "GSM":
			return self.binary_model.GSM
		elif model_name == "Muggianu":
			return self.binary_model.Muggianu
		elif model_name == "Toop-Muggianu":
			return self.binary_model.Toop_Muggianu
		elif model_name == "Toop-Kohler":
			return self.binary_model.Toop_Kohler
		else:
			return self.binary_model.UEM1
	
	def calculate_activity (self):
		"""计算活度"""
		try:
			# 验证输入
			fields = [
				(self.activity_alloy, "合金成分"),
				(self.activity_solvent, "基体元素"),
				(self.activity_solute, "溶质元素"),
				(self.activity_temp, "温度")
			]
			
			if not self.validate_input(fields):
				return
			
			# 获取输入值
			alloy = self.activity_alloy.text()
			solvent = self.activity_solvent.text()
			solute = self.activity_solute.text()
			try:
				temp = float(self.activity_temp.text())
			except ValueError:
				QMessageBox.critical(self, "输入错误", "温度必须是数值")
				return
			
			state = self.activity_state.currentText()
			model_name = self.activity_model.currentText()
			
			# 更新状态栏
			self.update_status(f"正在计算 {solute} 在 {solvent} 中的活度...")
			
			# 解析合金成分
			comp_dict = self.parse_composition(f"{solvent}{alloy}")
			
			# 获取模型函数
			model_func = self.get_model_function(model_name)
			
			# 实际计算
			self.activity_coefficient.set_composition_dict(f"{solvent}{alloy}")
			
			# 计算活度系数
			darken_acf = self.activity_coefficient.activity_coefficient_darken(
					comp_dict, solute, solvent, temp, state, model_func, model_name,True,True)
			
			wagner_acf = self.activity_coefficient.activity_coefficient_wagner(
					comp_dict, solvent, solute, temp, state, model_func, model_name)
			
			elliot_acf = self.activity_coefficient.activity_coefficient_elliott(comp_dict, solute, solvent, temp, state,
			                                                                    model_func, model_name)
			# 获取摩尔分数
			xi = comp_dict.get(solute, 0.0)
			
			# 计算活度
			acf = math.exp(darken_acf) * xi
			wagner_act = math.exp(wagner_acf) * xi
			elliot_act = math.exp(elliot_acf) * xi
			
			
			# 准备结果
			results = {
				"composition": alloy,
				"solvent": solvent,
				"solute": solute,
				"temperature": temp,
				"state": state,
				"model": model_name,
				"activity": round(acf, 3),
				"activity_wagner": round(wagner_act, 3),
				"activity_elliot": round(elliot_act, 3),
				
				"mole_fraction": round(xi, 3),
				"activity_coefficient_darken": round(math.exp(darken_acf), 3),
				"activity_coefficient_wagner": round(math.exp(wagner_acf), 3),
				"activity_coefficient_elliot": round(math.exp(elliot_acf), 3),
				
			}
			
			# 显示结果
			self.display_activity_results(results)
			
			# 更新图表
			self.update_activity_chart(results)
			
			# 更新状态栏
			self.update_status(f"已完成 {solute} 在 {solvent} 中的活度计算")
		
		except Exception as e:
			QMessageBox.critical(self, "计算错误", f"发生错误: {str(e)}")
			self.update_status("计算失败")
	
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
			solvent = self.interact_solvent.text()
			solute_i = self.interact_solute_i.text()
			solute_j = self.interact_solute_j.text()
			try:
				temp = float(self.interact_temp.text())
			except ValueError:
				QMessageBox.critical(self, "输入错误", "温度必须是数值")
				return
			
			state = self.interact_state.currentText()
			model_name = self.interact_model.currentText()
			
			# 更新状态栏
			self.update_status(f"正在计算 {solute_j} 对 {solute_i} 在 {solvent} 中的相互作用系数...")
			
			# 创建元素实例
			solv = Element(solvent)
			solui = Element(solute_i)
			soluj = Element(solute_j)
			
			# 创建 Melt 对象获取实验值
			melt = Melt(solvent, solute_i, solute_j, temp)
			
			# 获取模型函数
			model_func = self.get_model_function(model_name)
			
			# 创建 TernaryMelts 实例
			is_entropy = False
			ternary = TernaryMelts(temp, state, is_entropy)
			
			# 计算相互作用系数
			sij_uem1 = ternary.activity_interact_coefficient_1st(
					solv, solui, soluj, temp, state, model_func, model_name)
			
			# 使用 UEM2 对比
			uem2_func = self.get_model_function("UEM2")
			sij_uem2 = ternary.activity_interact_coefficient_1st(
					solv, solui, soluj, temp, state, uem2_func, "UEM2-Adv")
			
			# 获取实验值
			if state == "liquid":
				sij_exp = melt.sji
			else:
				sij_exp = float('nan')
			
			# 准备结果
			results = {
				"solvent": solvent,
				"solute_i": solute_i,
				"solute_j": solute_j,
				"temperature": temp,
				"state": state,
				"model": model_name,
				"sij_uem1": round(sij_uem1, 3),
				"sij_uem2": round(sij_uem2, 3),
				"sij_experimental": sij_exp
			}
			
			# 显示结果
			self.display_interaction_results(results)
			
			# 更新图表
			self.update_interact_chart(results)
			
			# 更新状态栏
			self.update_status(f"已完成 {solute_j} 对 {solute_i} 在 {solvent} 中的相互作用系数计算")
		
		except Exception as e:
			QMessageBox.critical(self, "计算错误", f"发生错误: {str(e)}")
			self.update_status("计算失败")
	
	def calculate_second_order (self):
		"""计算二阶相互作用系数"""
		try:
			# 验证输入
			fields = [
				(self.second_solvent, "基体元素"),
				(self.second_solute_i, "溶质 i"),
				(self.second_solute_j, "溶质 j"),
				(self.second_solute_k, "溶质 k"),
				(self.second_temp, "温度")
			]
			
			if not self.validate_input(fields):
				return
			
			# 获取输入值
			solvent = self.second_solvent.text()
			solute_i = self.second_solute_i.text()
			solute_j = self.second_solute_j.text()
			solute_k = self.second_solute_k.text()
			try:
				temp = float(self.second_temp.text())
			except ValueError:
				QMessageBox.critical(self, "输入错误", "温度必须是数值")
				return
			
			state = self.second_state.currentText()
			model_name = self.second_model.currentText()
			
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
			self.display_second_order_results(results)
			
			# 更新图表
			self.update_second_chart(results)
			
			# 更新状态栏
			self.update_status(f"已完成二阶相互作用系数计算")
		
		except Exception as e:
			QMessageBox.critical(self, "计算错误", f"发生错误: {str(e)}")
			self.update_status("计算失败")
	
	# ============================================================================
	# 结果显示方法
	# ============================================================================
	
	def display_activity_results (self, results):
		"""显示活度计算结果"""
		current_text = self.activity_result.toPlainText()
		if current_text:
			result_text = f"\n{'-' * 50}\n\n"
		else:
			result_text = ""
		
		result_text += f"活度计算结果:\n\n"
		result_text += f"合金成分: {results['composition']}\n"
		result_text += f"基体元素: {results['solvent']}\n"
		result_text += f"溶质元素: {results['solute']}\n"
		result_text += f"温度: {results['temperature']} K\n"
		result_text += f"状态: {results['state']}\n"
		result_text += f"外推模型: {results['model']}\n\n"
		result_text += f"活度值 (Darken模型): {results['activity']}\n"
		result_text += f"活度值 (Wagner模型): {results['activity_wagner']}\n"
		result_text += f"活度值 (Elliot模型): {results['activity_elliot']}\n"
		
		result_text += f"摩尔分数: {results['mole_fraction']}\n\n"
		result_text += f"活度系数 (Darken模型): {results['activity_coefficient_darken']}\n"
		result_text += f"活度系数 (Wagner模型): {results['activity_coefficient_wagner']}\n"
		result_text += f"活度系数 (Elliot模型): {results['activity_coefficient_elliot']}\n"
		
		if current_text:
			self.activity_result.append(result_text)
		else:
			self.activity_result.setText(result_text)
		
		# 自动滚动到底部
		self.activity_result.verticalScrollBar().setValue(
				self.activity_result.verticalScrollBar().maximum())
	
	def display_interaction_results (self, results):
		"""显示相互作用系数计算结果"""
		current_text = self.interact_result.toPlainText()
		if current_text:
			result_text = f"\n{'-' * 50}\n\n"
		else:
			result_text = ""
		
		result_text += f"相互作用系数计算结果:\n\n"
		result_text += f"基体元素: {results['solvent']}\n"
		result_text += f"溶质 i: {results['solute_i']}\n"
		result_text += f"溶质 j: {results['solute_j']}\n"
		result_text += f"温度: {results['temperature']} K\n"
		result_text += f"状态: {results['state']}\n"
		result_text += f"外推模型: {results['model']}\n\n"
		result_text += f"模型系数: {results['sij_uem1']}\n"
		result_text += f"UEM2模型系数: {results['sij_uem2']}\n"
		
		if not np.isnan(results['sij_experimental']):
			exp_value = f"{results['sij_experimental']:.3f}"
			result_text += f"实验值: {exp_value}\n"
		else:
			result_text += "实验值: 无可用数据\n"
		
		if current_text:
			self.interact_result.append(result_text)
		else:
			self.interact_result.setText(result_text)
		
		# 自动滚动到底部
		self.interact_result.verticalScrollBar().setValue(
				self.interact_result.verticalScrollBar().maximum())
	
	def display_second_order_results (self, results):
		"""显示二阶相互作用系数计算结果"""
		current_text = self.second_result.toPlainText()
		if current_text:
			result_text = f"\n{'-' * 50}\n\n"
		else:
			result_text = ""
		
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
			self.second_result.append(result_text)
		else:
			self.second_result.setText(result_text)
		
		# 自动滚动到底部
		self.second_result.verticalScrollBar().setValue(
				self.second_result.verticalScrollBar().maximum())
	
	# ============================================================================
	# 图表相关方法
	# ============================================================================
	
	def setup_value_labels (self, axes, bars, values, min_height=0.0):
		"""设置统一的数值标签位置"""
		for i, bar in enumerate(bars):
			height = bar.get_height()
			value = values[i]
			
			# 确定标签位置和样式
			if abs(height) > min_height:
				# 对于较高的柱子，将标签放在柱内
				y_pos = height / 2
				va = 'center'
				color = 'white'
				fontweight = 'bold'
			else:
				# 对于较矮的柱子，将标签放在柱子上方或下方
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
	
	def set_fixed_y_axis (self, axes, values, y_min, y_max):
		"""设置固定的Y轴范围"""
		max_values = max(values)
		min_values = min(values)
		
		if max_values * min_values < 0:
			y_max = max_values * 1.2
			y_min = min_values * 1.2
		elif max_values * min_values == 0:
			y_max = y_max
			y_min = y_min
		elif max_values > 0:
			y_max = max_values * 1.2
			y_min = 0
		else:
			y_max = 0
			y_min = min_values * 1.2
		
		axes.set_ylim(y_min, y_max)
	
	def clear_activity_result (self):
		"""清除活度计算结果"""
		self.activity_result.clear()
		self.init_activity_chart()
	
	def clear_interact_result (self):
		"""清除相互作用系数计算结果"""
		self.interact_result.clear()
		self.init_interact_chart()
	
	def clear_second_result (self):
		"""清除二阶相互作用系数计算结果"""
		self.second_result.clear()
		self.init_second_chart()
	
	def init_activity_chart (self):
		"""初始化活度图表"""
		self.activity_canvas.axes.clear()
		self.activity_canvas.axes.set_title('活度比较', fontsize=14)
		self.activity_canvas.axes.set_ylabel('活度值', fontsize=12)
		self.activity_canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.activity_canvas.fig.tight_layout()
		self.activity_canvas.draw()
	
	def init_interact_chart (self):
		"""初始化相互作用系数图表"""
		self.interact_canvas.axes.clear()
		self.interact_canvas.axes.set_title('相互作用系数比较', fontsize=14)
		self.interact_canvas.axes.set_ylabel('相互作用系数', fontsize=12)
		self.interact_canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.interact_canvas.fig.tight_layout()
		self.interact_canvas.draw()
	
	def init_second_chart (self):
		"""初始化二阶相互作用系数图表"""
		self.second_canvas.axes.clear()
		self.second_canvas.axes.set_title('二阶相互作用系数', fontsize=14)
		self.second_canvas.axes.set_ylabel('系数值', fontsize=12)
		self.second_canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.second_canvas.fig.tight_layout()
		self.second_canvas.draw()
	
	def update_activity_chart (self, results):
		"""更新活度图表"""
		self.activity_canvas.axes.clear()
		
		# 数据
		models = ['Darken', 'Wagner', 'Elliot','Corrected']
		values = [results['activity'], results['activity_wagner'], results['activity_elliot'],results['activity_corrected']]
		
		# 创建柱状图
		bars = self.activity_canvas.axes.bar(models, values, color=['#3498db', '#2ecc71', '#e74c3c'])
		
		# 添加数值标签
		self.setup_value_labels(self.activity_canvas.axes, bars, values, 0.01)
		
		mole_fraction = results["mole_fraction"]
		max_value = max(values)
		y_max = 1.0 if max(max_value, mole_fraction) > 0.84 and max(max_value, mole_fraction) < 1.01 else max(max_value,
		                                                                                                      mole_fraction) * 1.2
		
		self.activity_canvas.axes.set_ylim(0, y_max)
		
		# 设置图表属性
		solute = results["solute"]
		solvent = results["solvent"]
		self.activity_canvas.axes.set_title(f'{solute} 在 {solvent} 中的活度比较', fontsize=14)
		self.activity_canvas.axes.set_ylabel(f'Activity(a_{solute})', fontsize=13)
		self.activity_canvas.axes.grid(True, axis='y', linestyle='--', alpha=0.7)
		
		# 添加摩尔分数参考线
		self.activity_canvas.axes.axhline(y=results['mole_fraction'], color='r', linestyle='--', alpha=0.5)
		self.activity_canvas.axes.text(0, results['mole_fraction'] * 1.05,
		                               f'摩尔分数 X_{solute}: {results["mole_fraction"]:.3f}',
		                               color='r', alpha=0.7, fontsize=12)
		
		self.activity_canvas.fig.tight_layout()
		self.activity_canvas.draw()
	
	def update_interact_chart (self, results):
		"""更新相互作用系数图表"""
		self.interact_canvas.axes.clear()
		
		# 数据
		models = ['UEM1', 'UEM2', '实验值']
		values = [
			results['sij_uem1'],
			results['sij_uem2'],
			results['sij_experimental'] if not np.isnan(results['sij_experimental']) else 0
		]
		
		# 创建柱状图
		colors = ['#3498db', '#2ecc71', '#e74c3c']
		if np.isnan(results['sij_experimental']):
			models = models[:2]
			values = values[:2]
			colors = colors[:2]
		
		bars = self.interact_canvas.axes.bar(models, values, color=colors)
		
		# 添加数值标签
		self.setup_value_labels(self.interact_canvas.axes, bars, values)
		self.set_fixed_y_axis(self.interact_canvas.axes, values, -10.0, 10)
		
		# 设置图表属性
		solvent = results["solvent"]
		solute_i = results["solute_i"]
		solute_j = results["solute_j"]
		self.interact_canvas.axes.set_title(
				f'{solute_j} 对 {solute_i} 在 {solvent} 中的相互作用系数', fontsize=14)
		self.interact_canvas.axes.set_ylabel(f'ε^{solute_j}_{solute_i}', fontsize=14)
		self.interact_canvas.axes.grid(True, axis='y', linestyle='--', alpha=0.7)
		
		self.interact_canvas.fig.tight_layout()
		self.interact_canvas.draw()
	
	def update_second_chart (self, results):
		"""更新二阶相互作用系数图表"""
		self.second_canvas.axes.clear()
		
		# 数据
		solute_i = results["solute_i"]
		solute_j = results["solute_j"]
		solute_k = results["solute_k"]
		
		# 创建更具数学意义的标签
		coefficients = [
			f'ρ_{solute_i}^{solute_i},{solute_i}',
			f'ρ_{solute_i}^{solute_i},{solute_j}',
			f'ρ_{solute_i}^{solute_i},{solute_k}',
			f'ρ_{solute_i}^{solute_j},{solute_j}',
			f'ρ_{solute_i}^{solute_j},{solute_k}',
			f'ρ_{solute_i}^{solute_k},{solute_k}',
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
		colors = ['#3498db', '#2ecc71', '#e74c3c', '#9b59b6']
		bars = self.second_canvas.axes.bar(coefficients, values, color=colors)
		
		# 添加数值标签
		self.setup_value_labels(self.second_canvas.axes, bars, values)
		self.set_fixed_y_axis(self.second_canvas.axes, values, -20, 20)
		
		# 设置图表属性
		solvent = results["solvent"]
		title = f'二阶相互作用系数 ({solvent}-{solute_i}-{solute_j}'
		if solute_k:
			title += f'-{solute_k}'
		title += ')'
		
		self.second_canvas.axes.set_title(title, fontsize=14)
		self.second_canvas.axes.set_ylabel('系数值', fontsize=13)
		self.second_canvas.axes.grid(True, axis='y', linestyle='--', alpha=0.7)
		
		# 旋转x轴标签以避免重叠
		self.second_canvas.axes.tick_params(axis='x', rotation=45)
		
		self.second_canvas.fig.tight_layout()
		self.second_canvas.draw()


def main ():
	"""主程序入口"""
	app = QApplication(sys.argv)
	
	# 设置应用程序属性
	app.setApplicationName("AlloyAct Pro")
	app.setApplicationVersion("2.0")
	app.setOrganizationName("Material Science Lab")
	
	# 设置高DPI缩放
	app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
	app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
	
	# 创建并显示主窗口
	window = AlloyActProGUI()
	window.show()
	
	return app.exec_()


if __name__ == "__main__":
	sys.exit(main())