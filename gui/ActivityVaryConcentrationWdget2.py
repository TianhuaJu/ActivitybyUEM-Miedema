import math
import sys
import traceback

import matplotlib
import numpy as np
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton, QSplitter,
                             QFrame, QGroupBox, QTextEdit, QDoubleSpinBox, QCheckBox, QFileDialog, QFormLayout,
                             QProgressDialog, QTabWidget, QMessageBox)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from calculations.activity_calculator import ActivityCoefficient
from core.utils import *
from models.extrapolation_models import BinaryModel

# Matplotlib 全局设置
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'FangSong', 'SimSun', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['font.size'] = 10


class ModernGroupBox(QGroupBox):
	"""现代化的GroupBox组件"""
	
	def __init__ (self, title="", parent=None):
		super().__init__(title, parent)
		self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 12px;
                padding-bottom: 8px;
                padding-left: 10px;
                padding-right: 10px;
                background-color: #FAFAFA;
                color: #333333;
                font-size: 11pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                background-color: #FFFFFF;
                border-radius: 4px;
                font-size: 11pt;
                font-weight: bold;
                color: #2C3E50;
            }
        """)


class ModernButton(QPushButton):
	"""现代化的按钮组件"""
	
	def __init__ (self, text="", button_type="primary", parent=None):
		super().__init__(text, parent)
		self.button_type = button_type
		self.setMinimumHeight(40)
		self.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
		self.update_style()
	
	def update_style (self):
		if self.button_type == "primary":
			style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #4A90E2, stop:1 #2E5BBA);
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #5BA0F2, stop:1 #3E6BCA);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3A80D2, stop:1 #1E4BAA);
                }
            """
		elif self.button_type == "secondary":
			style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #F5F5F5, stop:1 #E8E8E8);
                    color: #333333;
                    border: 1px solid #CCCCCC;
                    border-radius: 6px;
                    padding: 8px 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #FFFFFF, stop:1 #F0F0F0);
                    border-color: #4A90E2;
                }
            """
		else:  # success
			style = """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #27AE60, stop:1 #1E8449);
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2ECC71, stop:1 #229954);
                }
            """
		self.setStyleSheet(style)


class ModernComboBox(QComboBox):
	"""现代化的下拉框组件"""
	
	def __init__ (self, parent=None):
		super().__init__(parent)
		self.setMinimumHeight(35)
		self.setStyleSheet("""
            QComboBox {
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 10pt;
                background-color: white;
                selection-background-color: #4A90E2;
            }
            QComboBox:hover {
                border-color: #4A90E2;
            }
            QComboBox:focus {
                border-color: #2E5BBA;
                outline: none;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #666666;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #CCCCCC;
                background-color: white;
                selection-background-color: #4A90E2;
                selection-color: white;
            }
        """)


class ModernLineEdit(QLineEdit):
	"""现代化的输入框组件"""
	
	def __init__ (self, placeholder="", parent=None):
		super().__init__(parent)
		self.setPlaceholderText(placeholder)
		self.setMinimumHeight(35)
		self.setStyleSheet("""
            QLineEdit {
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 10pt;
                background-color: white;
            }
            QLineEdit:hover {
                border-color: #4A90E2;
            }
            QLineEdit:focus {
                border-color: #2E5BBA;
                outline: none;
            }
        """)


class ModernSpinBox(QDoubleSpinBox):
	"""现代化的数字输入框组件"""
	
	def __init__ (self, parent=None):
		super().__init__(parent)
		self.setMinimumHeight(35)
		self.setStyleSheet("""
            QDoubleSpinBox {
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 10pt;
                background-color: white;
            }
            QDoubleSpinBox:hover {
                border-color: #4A90E2;
            }
            QDoubleSpinBox:focus {
                border-color: #2E5BBA;
                outline: none;
            }
        """)


class ModernCheckBox(QCheckBox):
	"""现代化的复选框组件"""
	
	def __init__ (self, text="", parent=None):
		super().__init__(text, parent)
		self.setStyleSheet("""
            QCheckBox {
                font-size: 10pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #CCCCCC;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:hover {
                border-color: #4A90E2;
            }
            QCheckBox::indicator:checked {
                background-color: #4A90E2;
                border-color: #4A90E2;
            }
        """)


class StatusBar(QWidget):
	"""现代化的状态栏"""
	
	def __init__ (self, parent=None):
		super().__init__(parent)
		self.setFixedHeight(30)
		self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F8F9FA, stop:1 #E9ECEF);
                border-top: 1px solid #CCCCCC;
            }
        """)
		
		layout = QHBoxLayout(self)
		layout.setContentsMargins(10, 5, 10, 5)
		
		self.status_label = QLabel("就绪")
		self.status_label.setStyleSheet("color: #666666; font-size: 9pt;")
		layout.addWidget(self.status_label)
		layout.addStretch()
		
		self.version_label = QLabel("版本 1.0")
		self.version_label.setStyleSheet("color: #999999; font-size: 8pt;")
		layout.addWidget(self.version_label)
	
	def set_status (self, text):
		self.status_label.setText(text)


class AlloyAdditionWidget(QWidget):
	"""
	合金元素添加效应计算器
	基体合金比例固定，研究添加元素对目标组分活度/活度系数的影响
	"""
	
	def __init__ (self, parent=None):
		super().__init__(parent)
		
		self.binary_model = BinaryModel()
		self.activity_calc_module = ActivityCoefficient()
		
		# 数据结构
		self.calculation_results = {
			"activity_darken": {},
			"activity_coefficient_darken": {},
			"activity_elliott": {},
			"activity_coefficient_elliott": {}
		}
		
		self.current_parameters = {
			"base_alloy": "", "addition_element": "", "target_element": "", "solvent_element": "",
			"phase_state": "", "temperature": 0, "addition_range": [], "selected_models": []
		}
		self.historical_results_html = ""
		self.has_calculated = False
		
		self.setWindowTitle("合金元素添加效应计算器")
		self.resize(1400, 800)
		self.init_ui()
		self.update_element_dropdowns()
		self.apply_global_style()
	
	def apply_global_style (self):
		"""应用全局样式"""
		self.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                color: #333333;
                font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
            }
            QLabel {
                font-size: 10pt;
                color: #555555;
            }
            QTextEdit {
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                background-color: white;
                font-family: "Consolas", "Monaco", monospace;
                font-size: 10pt;
                padding: 8px;
            }
            QTextEdit:focus {
                border-color: #4A90E2;
            }
        """)
	
	def init_ui (self):
		main_layout = QVBoxLayout(self)
		main_layout.setSpacing(0)
		main_layout.setContentsMargins(0, 0, 0, 0)
		
		# 标题栏
		title_bar = self.create_title_bar()
		main_layout.addWidget(title_bar)
		
		# 主内容区域
		content_widget = QWidget()
		content_layout = QVBoxLayout(content_widget)
		content_layout.setSpacing(15)
		content_layout.setContentsMargins(20, 20, 20, 10)
		
		splitter = QSplitter(Qt.Horizontal)
		splitter.setHandleWidth(8)
		
		left_panel = self.create_left_panel()
		right_panel = self.create_right_panel()
		
		splitter.addWidget(left_panel)
		splitter.addWidget(right_panel)
		splitter.setSizes([450, 950])
		
		content_layout.addWidget(splitter)
		main_layout.addWidget(content_widget)
		
		# 状态栏
		self.status_bar = StatusBar()
		main_layout.addWidget(self.status_bar)
	
	def create_title_bar (self):
		"""创建标题栏"""
		title_widget = QWidget()
		title_widget.setFixedHeight(80)
		title_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #E67E22, stop:1 #F39C12);
                color: white;
            }
        """)
		
		layout = QHBoxLayout(title_widget)
		layout.setContentsMargins(20, 10, 20, 10)
		
		# 标题
		title_label = QLabel("合金元素添加效应计算器")
		title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
		title_label.setStyleSheet("color: white;")
		layout.addWidget(title_label)
		
		layout.addStretch()
		
		# 副标题
		subtitle_label = QLabel("Alloy Element Addition Effect Calculator")
		subtitle_label.setFont(QFont("Microsoft YaHei", 10))
		subtitle_label.setStyleSheet("color: #F4F6F7;")
		layout.addWidget(subtitle_label)
		
		return title_widget
	
	def create_left_panel (self):
		"""创建左侧面板"""
		left_panel = QWidget()
		left_panel.setMinimumWidth(420)
		left_panel.setMaximumWidth(500)
		
		layout = QVBoxLayout(left_panel)
		layout.setSpacing(12)
		layout.setContentsMargins(0, 0, 10, 0)
		
		layout.addWidget(self.create_base_alloy_group())
		layout.addWidget(self.create_addition_setup_group())
		layout.addWidget(self.create_addition_range_group())
		layout.addWidget(self.create_calculation_setup_group())
		layout.addWidget(self.create_calculation_method_group())
		layout.addWidget(self.create_model_selection_group())
		layout.addStretch(1)
		layout.addLayout(self.create_action_buttons())
		
		return left_panel
	
	def create_base_alloy_group (self):
		"""创建基体合金组"""
		group = ModernGroupBox("🧪 基体合金组成 (比例固定)")
		group.setFixedHeight(170)
		layout = QFormLayout(group)
		layout.setSpacing(14)
		layout.setContentsMargins(15, 20, 15, 20)
		layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
		layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
		
		# 基体合金输入
		comp_layout = QHBoxLayout()
		comp_layout.setSpacing(8)
		self.base_alloy_composition = ModernLineEdit("例如: Fe0.7Cr0.2Ni0.1")
		self.base_alloy_composition.setMinimumWidth(200)
		comp_layout.addWidget(self.base_alloy_composition)
		
		update_btn = ModernButton("解析", "secondary")
		update_btn.setFixedWidth(60)
		update_btn.clicked.connect(self.update_element_dropdowns)
		comp_layout.addWidget(update_btn)
		
		layout.addRow(QLabel("基体组成:"), comp_layout)
		
		# 溶剂组分选择
		self.solvent_element_combo = ModernComboBox()
		self.solvent_element_combo.setFixedWidth(280)
		self.solvent_element_combo.setToolTip("选择溶剂组分（基体合金中的主要元素）")
		layout.addRow(QLabel("溶剂组分:"), self.solvent_element_combo)
		
		# 相态选择
		self.phase_combo = ModernComboBox()
		self.phase_combo.addItems(["liquid", "solid"])
		self.phase_combo.setFixedWidth(280)
		layout.addRow(QLabel("相态:"), self.phase_combo)
		
		return group
	
	def create_addition_setup_group (self):
		"""创建添加元素设置组"""
		group = ModernGroupBox("➕ 添加元素设置")
		layout = QFormLayout(group)
		layout.setSpacing(10)
		layout.setContentsMargins(15, 20, 15, 15)
		layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
		layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
		
		# 添加元素输入
		self.addition_element_input = ModernLineEdit("例如: C")
		self.addition_element_input.setFixedWidth(280)
		self.addition_element_input.setToolTip("输入要添加的元素符号")
		self.addition_element_input.textChanged.connect(self.update_element_dropdowns)
		layout.addRow(QLabel("添加元素:"), self.addition_element_input)
		
		return group
	
	def create_addition_range_group (self):
		"""创建添加元素浓度范围组"""
		group = ModernGroupBox("📊 添加元素浓度范围")
		group.setFixedHeight(180)
		layout = QFormLayout(group)
		layout.setSpacing(10)
		layout.setContentsMargins(15, 20, 15, 15)
		layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
		layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
		
		# 最小浓度
		self.min_addition = ModernSpinBox()
		self.min_addition.setRange(0.001, 0.500)
		self.min_addition.setValue(0.01)
		self.min_addition.setSingleStep(0.01)
		self.min_addition.setDecimals(3)
		self.min_addition.setFixedWidth(280)
		layout.addRow(QLabel("最小摩尔分数:"), self.min_addition)
		
		# 最大浓度
		self.max_addition = ModernSpinBox()
		self.max_addition.setRange(0.010, 0.800)
		self.max_addition.setValue(0.20)
		self.max_addition.setSingleStep(0.01)
		self.max_addition.setDecimals(3)
		self.max_addition.setFixedWidth(280)
		layout.addRow(QLabel("最大摩尔分数:"), self.max_addition)
		
		# 步长
		self.step_addition = ModernSpinBox()
		self.step_addition.setRange(0.001, 0.100)
		self.step_addition.setValue(0.01)
		self.step_addition.setSingleStep(0.001)
		self.step_addition.setDecimals(3)
		self.step_addition.setFixedWidth(280)
		layout.addRow(QLabel("浓度步长:"), self.step_addition)
		
		return group
	
	def create_calculation_setup_group (self):
		"""创建计算设置组"""
		group = ModernGroupBox("⚙️ 计算设置")
		group.setFixedHeight(180)
		layout = QFormLayout(group)
		layout.setSpacing(15)
		layout.setContentsMargins(15, 25, 15, 25)
		layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
		layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
		
		# 温度设置
		self.temperature_input = ModernSpinBox()
		self.temperature_input.setRange(300, 3000)
		self.temperature_input.setValue(1200)
		self.temperature_input.setSingleStep(50)
		self.temperature_input.setSuffix(" K")
		self.temperature_input.setFixedWidth(280)
		layout.addRow(QLabel("计算温度:"), self.temperature_input)
		
		# 目标组分选择
		self.target_element_combo = ModernComboBox()
		self.target_element_combo.setFixedWidth(280)
		self.target_element_combo.setToolTip("选择要计算活度/活度系数的目标组分")
		layout.addRow(QLabel("目标组分:"), self.target_element_combo)
		
		# 热力学性质选择
		self.property_combo = ModernComboBox()
		self.property_combo.addItems(["活度 (a)", "活度系数 (γ)"])
		self.property_combo.currentIndexChanged.connect(self.update_plot_display_only)
		self.property_combo.setFixedWidth(280)
		layout.addRow(QLabel("热力学性质:"), self.property_combo)
		
		return group
	
	def create_calculation_method_group (self):
		"""创建计算方法选择组"""
		group = ModernGroupBox("🔬 计算方法选择")
		layout = QGridLayout(group)
		layout.setSpacing(10)
		layout.setContentsMargins(15, 20, 15, 15)
		
		self.method_checkboxes = {}
		methods = [
			("Darken 方法", "darken"),
			("Elliott 方法", "elliott")
		]
		
		for index, (name, key) in enumerate(methods):
			checkbox = ModernCheckBox(name)
			if key == "darken":  # 默认选中Darken方法
				checkbox.setChecked(True)
			self.method_checkboxes[key] = checkbox
			layout.addWidget(checkbox, 0, index)
		
		return group
	
	def create_model_selection_group (self):
		"""创建模型选择组"""
		group = ModernGroupBox("🔧 外推模型选择")
		layout = QGridLayout(group)
		layout.setSpacing(10)
		layout.setContentsMargins(15, 20, 15, 15)
		
		self.model_checkboxes = {}
		models = [
			("UEM1 模型", "UEM1"),
			("GSM 模型", "GSM"),
			("Toop-Muggianu 模型", "Toop-Muggianu"),
			("Muggianu 模型", "Muggianu")
		]
		
		for index, (name, key) in enumerate(models):
			checkbox = ModernCheckBox(name)
			if key in ["UEM1", "Muggianu"]:
				checkbox.setChecked(True)
			self.model_checkboxes[key] = checkbox
			row, col = index // 2, index % 2
			layout.addWidget(checkbox, row, col)
		
		return group
	
	def create_action_buttons (self):
		"""创建操作按钮"""
		button_layout = QHBoxLayout()
		button_layout.setSpacing(12)
		button_layout.setContentsMargins(0, 15, 0, 15)
		
		calculate_button = ModernButton("🚀 开始计算", "primary")
		calculate_button.clicked.connect(self.run_calculation_thread)
		
		export_button = ModernButton("📤 导出数据", "success")
		export_button.clicked.connect(self.export_data)
		
		button_layout.addWidget(calculate_button)
		button_layout.addWidget(export_button)
		
		return button_layout
	
	def create_right_panel (self):
		"""创建右侧面板"""
		right_panel = QWidget()
		layout = QVBoxLayout(right_panel)
		layout.setSpacing(0)
		layout.setContentsMargins(0, 0, 0, 0)
		
		# 创建标签页控件
		self.tab_widget = QTabWidget()
		self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                background-color: white;
            }
            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #F5F5F5, stop:1 #E8E8E8);
                color: #333333;
                border: 1px solid #CCCCCC;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 20px;
                margin-right: 2px;
                font-weight: bold;
                font-size: 10pt;
                min-width: 120px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #E67E22, stop:1 #D68910);
                color: white;
                border-color: #D68910;
            }
            QTabBar::tab:hover:!selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F0F0);
                border-color: #E67E22;
            }
        """)
		
		# 创建图表页面
		chart_tab = self.create_chart_tab()
		self.tab_widget.addTab(chart_tab, "📊 图表显示")
		
		# 创建结果页面
		results_tab = self.create_results_tab()
		self.tab_widget.addTab(results_tab, "📈 计算结果")
		
		layout.addWidget(self.tab_widget)
		
		return right_panel
	
	def create_chart_tab (self):
		"""创建图表标签页"""
		chart_widget = QWidget()
		
		layout = QVBoxLayout(chart_widget)
		layout.setSpacing(10)
		layout.setContentsMargins(15, 15, 15, 15)
		
		# 图表标题
		chart_title = QLabel("添加元素效应图表")
		chart_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
		chart_title.setStyleSheet("color: #2C3E50; padding: 5px;")
		layout.addWidget(chart_title)
		
		# 分隔线
		separator = QFrame()
		separator.setFrameShape(QFrame.HLine)
		separator.setStyleSheet("QFrame { color: #E0E0E0; }")
		layout.addWidget(separator)
		
		self.figure = Figure(figsize=(8, 6), dpi=100)
		self.figure.patch.set_facecolor('white')
		self.canvas = FigureCanvas(self.figure)
		
		# 工具栏
		toolbar_frame = QFrame()
		toolbar_layout = QHBoxLayout(toolbar_frame)
		toolbar_layout.setContentsMargins(0, 5, 0, 5)
		self.toolbar = NavigationToolbar(self.canvas, toolbar_frame)
		self.toolbar.setStyleSheet("""
            QToolBar {
                border: none;
                background: transparent;
            }
            QToolButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 2px;
            }
            QToolButton:hover {
                background: #F0F0F0;
                border-color: #CCCCCC;
            }
        """)
		toolbar_layout.addWidget(self.toolbar)
		toolbar_layout.addStretch()
		
		layout.addWidget(toolbar_frame)
		layout.addWidget(self.canvas, 1)
		
		return chart_widget
	
	def create_results_tab (self):
		"""创建结果标签页"""
		results_widget = QWidget()
		
		layout = QVBoxLayout(results_widget)
		layout.setSpacing(10)
		layout.setContentsMargins(15, 15, 15, 15)
		
		# 结果标题
		results_title = QLabel("计算结果历史记录")
		results_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
		results_title.setStyleSheet("color: #2C3E50; padding: 5px;")
		layout.addWidget(results_title)
		
		# 分隔线
		separator = QFrame()
		separator.setFrameShape(QFrame.HLine)
		separator.setStyleSheet("QFrame { color: #E0E0E0; }")
		layout.addWidget(separator)
		
		# 操作按钮行
		button_layout = QHBoxLayout()
		button_layout.setSpacing(10)
		
		clear_results_btn = ModernButton("🗑️ 清除历史", "secondary")
		clear_results_btn.setMaximumWidth(140)
		clear_results_btn.setFont(QFont("Microsoft YaHei", 8, QFont.Bold))
		clear_results_btn.clicked.connect(self.clear_history)
		button_layout.addWidget(clear_results_btn)
		
		button_layout.addStretch()
		layout.addLayout(button_layout)
		
		# 结果显示区域
		self.results_text_right = QTextEdit()
		self.results_text_right.setReadOnly(True)
		self.results_text_right.setStyleSheet("""
            QTextEdit {
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                background-color: #FAFAFA;
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                font-size: 11pt;
                padding: 12px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border-color: #E67E22;
                background-color: white;
            }
        """)
		
		layout.addWidget(self.results_text_right, 1)
		
		return results_widget
	
	def clear_history (self):
		"""清除计算历史"""
		reply = QMessageBox.question(self, "确认清除", "确定要清除所有计算历史记录吗？",
		                             QMessageBox.Yes | QMessageBox.No,
		                             QMessageBox.No)
		if reply == QMessageBox.Yes:
			self.historical_results_html = ""
			if hasattr(self, 'results_text_right'):
				self.results_text_right.clear()
			self.status_bar.set_status("历史记录已清除")
	
	def update_element_dropdowns (self):
		"""更新元素下拉列表"""
		base_alloy_input = self.base_alloy_composition.text().strip()
		addition_elem = self.addition_element_input.text().strip()
		
		# 清空下拉列表
		self.target_element_combo.blockSignals(True)
		self.solvent_element_combo.blockSignals(True)
		self.target_element_combo.clear()
		self.solvent_element_combo.clear()
		
		if not base_alloy_input:
			self.target_element_combo.blockSignals(False)
			self.solvent_element_combo.blockSignals(False)
			self.status_bar.set_status("请输入基体合金组成")
			return
		
		try:
			# 解析基体合金组成
			base_comp_dict = self._parse_composition_static(base_alloy_input)
			
			if not base_comp_dict:
				self.target_element_combo.blockSignals(False)
				self.solvent_element_combo.blockSignals(False)
				self.status_bar.set_status("无法解析合金组成")
				return
			
			# 填充溶剂组分选择（仅基体合金中的元素）
			base_elements = list(base_comp_dict.keys())
			self.solvent_element_combo.addItems(base_elements)
			
			# 填充目标组分选择（基体合金中的元素 + 添加元素）
			target_elements = base_elements.copy()
			if addition_elem and addition_elem not in base_elements:
				target_elements.append(addition_elem)
			
			self.target_element_combo.addItems(target_elements)
			
			# 如果添加元素存在，默认选择添加元素作为目标组分
			if addition_elem and addition_elem in target_elements:
				index = target_elements.index(addition_elem)
				self.target_element_combo.setCurrentIndex(index)
			
			status_msg = f"检测到 {len(base_elements)} 个基体元素: {', '.join(base_elements)}"
			if addition_elem:
				status_msg += f" | 添加元素: {addition_elem}"
			self.status_bar.set_status(status_msg)
		
		except Exception as e:
			print(f"更新元素下拉列表时出错: {str(e)}")
			self.status_bar.set_status("合金组成解析失败")
		finally:
			self.target_element_combo.blockSignals(False)
			self.solvent_element_combo.blockSignals(False)
	
	@staticmethod
	def _parse_composition_static (alloy_str):
		"""解析合金组成的静态方法"""
		return parse_composition_static(alloy_str)
	
	def get_model_function (self, model_name_str):
		"""获取模型函数"""
		if not hasattr(self, 'binary_model') or self.binary_model is None:
			QMessageBox.critical(self, "内部错误", "BinaryModel 未初始化。")
			return None
		
		model_method_map = {
			"UEM1": self.binary_model.UEM1,
			"Toop-Muggianu": self.binary_model.Toop_Muggianu,
			"GSM": self.binary_model.GSM,
			"Muggianu": self.binary_model.Muggianu
		}
		
		func = model_method_map.get(model_name_str)
		if func is None:
			QMessageBox.warning(self, "模型警告", f"模型 '{model_name_str}' 未找到或未实现。")
			return None
		
		return func
	
	def run_calculation_thread (self):
		"""运行计算线程"""
		# 验证输入
		if not self.base_alloy_composition.text().strip():
			QMessageBox.warning(self, "输入缺失", "请输入基体合金组成。")
			return
		
		if not self.addition_element_input.text().strip():
			QMessageBox.warning(self, "输入缺失", "请输入添加元素。")
			return
		
		if not self.target_element_combo.currentText():
			QMessageBox.warning(self, "输入缺失", "请选择目标组分。")
			return
		
		if not self.solvent_element_combo.currentText():
			QMessageBox.warning(self, "输入缺失", "请选择溶剂组分。")
			return
		
		if self.min_addition.value() >= self.max_addition.value():
			QMessageBox.warning(self, "浓度范围错误", "最小摩尔分数必须小于最大摩尔分数。")
			return
		
		if self.step_addition.value() <= 0:
			QMessageBox.warning(self, "浓度步长错误", "浓度步长必须为正数。")
			return
		
		# 检查计算方法选择
		selected_methods = [k for k, v in self.method_checkboxes.items() if v.isChecked()]
		if not selected_methods:
			QMessageBox.warning(self, "方法未选择", "请至少选择一种计算方法。")
			return
		
		# 创建进度对话框
		self.progress_dialog = QProgressDialog("正在计算，请稍候...", "取消", 0, 0, self)
		self.progress_dialog.setWindowModality(Qt.WindowModal)
		self.progress_dialog.setMinimumDuration(0)
		self.progress_dialog.setValue(0)
		self.progress_dialog.show()
		QApplication.processEvents()
		
		self.status_bar.set_status("正在计算...")
		self.calculate_addition_effects()
		
		if hasattr(self, 'progress_dialog') and self.progress_dialog:
			self.progress_dialog.close()
	
	def calculate_addition_effects (self):
		"""计算添加元素效应"""
		try:
			self.has_calculated = False
			# 重置数据结构
			self.calculation_results = {
				"activity_darken": {},
				"activity_coefficient_darken": {},
				"activity_elliott": {},
				"activity_coefficient_elliott": {}
			}
			
			# 获取参数
			base_alloy_str = self.base_alloy_composition.text().strip()
			addition_elem = self.addition_element_input.text().strip()
			target_elem = self.target_element_combo.currentText()
			solvent_elem = self.solvent_element_combo.currentText()
			phase = self.phase_combo.currentText().lower()
			temperature = self.temperature_input.value()
			min_add = self.min_addition.value()
			max_add = self.max_addition.value()
			step_add = self.step_addition.value()
			
			print(f"=== 添加元素效应计算 ===")
			print(f"基体合金: {base_alloy_str}")
			print(f"添加元素: {addition_elem}, 目标组分: {target_elem}, 溶剂组分: {solvent_elem}")
			print(f"添加浓度范围: {min_add} - {max_add}, 步长: {step_add}")
			
			# 解析基体合金组成
			base_comp_dict = AlloyAdditionWidget._parse_composition_static(base_alloy_str)
			if base_comp_dict is None:
				QMessageBox.critical(self, "成分解析失败", f"无法解析: {base_alloy_str}")
				return
			
			print(f"基体合金解析结果: {base_comp_dict}")
			
			# 生成添加元素浓度序列
			addition_concentrations = np.arange(min_add, max_add + step_add / 2, step_add)
			print(f"添加浓度点数: {len(addition_concentrations)}")
			
			if len(addition_concentrations) == 0:
				QMessageBox.warning(self, "浓度范围错误", "无有效浓度点。")
				return
			
			# 更新当前参数
			self.current_parameters = {
				"base_alloy": base_alloy_str,
				"addition_element": addition_elem,
				"target_element": target_elem,
				"solvent_element": solvent_elem,
				"phase_state": phase,
				"temperature": temperature,
				"addition_range": [min_add, max_add, step_add],
				"selected_models": []
			}
			
			# 获取选择的模型和方法
			selected_models_to_run = []
			for mk, cbx in self.model_checkboxes.items():
				if cbx.isChecked():
					gmf = self.get_model_function(mk)
					if gmf:
						selected_models_to_run.append((mk, gmf))
						self.current_parameters["selected_models"].append(mk)
			
			selected_methods = [k for k, v in self.method_checkboxes.items() if v.isChecked()]
			
			if not selected_models_to_run:
				QMessageBox.warning(self, "模型未选择", "请至少选择一个外推模型。")
				return
			
			print(f"选择的模型: {[mk for mk, _ in selected_models_to_run]}")
			print(f"选择的方法: {selected_methods}")
			
			# 创建结果HTML
			current_timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
			new_results_html = f"<hr><b>🕐 计算时间: {current_timestamp}</b><br>"
			new_results_html += f"<b>📋 计算参数:</b><br>"
			new_results_html += f"基体合金: {base_alloy_str}<br>"
			new_results_html += f"添加元素: {addition_elem}, 目标组分: {target_elem}, 溶剂组分: {solvent_elem}<br>"
			new_results_html += f"温度: {temperature}K, 相态: {phase}<br>"
			new_results_html += f"添加浓度范围: {min_add:.3f} - {max_add:.3f} (步长 {step_add:.3f})<br>"
			new_results_html += f"计算方法: {', '.join(selected_methods)}<br>"
			new_results_html += f"外推模型: {', '.join(self.current_parameters['selected_models'])}<hr>"
			
			# 设置进度条
			total_calcs = len(selected_models_to_run) * len(addition_concentrations) * len(selected_methods)
			if hasattr(self, 'progress_dialog'):
				self.progress_dialog.setRange(0, total_calcs)
			calcs_done = 0
			
			# 执行计算
			for method in selected_methods:
				for model_key_geo, geo_model_function in selected_models_to_run:
					print(f"\n--- 开始计算: {method} 方法, {model_key_geo} 模型 ---")
					
					# 预分配大数组
					MAX_ARRAY_SIZE = 10000
					current_activities = np.full(MAX_ARRAY_SIZE, float('nan'))
					current_coefficients = np.full(MAX_ARRAY_SIZE, float('nan'))
					addition_values = np.full(MAX_ARRAY_SIZE, float('nan'))
					
					valid_count = 0
					
					new_results_html += f"<br><b>⚙️ {method.upper()} 方法 - {model_key_geo} 模型</b><br>"
					new_results_html += f"<font face='Courier New' color='#2C3E50'><b>X_{addition_elem}   | {target_elem}-活度    | {target_elem}-γ        | 基体缩减比</b></font><br>"
					new_results_html += f"<font face='Courier New'>---------|-------------|-------------|--------</font><br>"
					
					successful_calcs = 0
					failed_calcs = 0
					
					for i, add_conc in enumerate(addition_concentrations):
						if hasattr(self, 'progress_dialog') and self.progress_dialog.wasCanceled():
							new_results_html += "<font color='red'>❌ 计算已取消</font><br>"
							break
						
						# 构建当前组成（基体按比例缩减）
						current_comp = self.build_composition_with_addition(base_comp_dict, addition_elem, add_conc)
						if current_comp is None:
							print(f"添加浓度点{i} (X={add_conc:.3f}): 组成构建失败")
							new_results_html += f"<font face='Courier New'>{add_conc:<9.3f}|     N/A     |     N/A     |   N/A</font><br>"
							failed_calcs += 1
							calcs_done += 1
							continue
						
						try:
							# 根据方法选择计算函数
							if method == "darken":
								ln_gamma = self.activity_calc_module.activity_coefficient_darken(
										current_comp, target_elem, solvent_elem, temperature, phase,
										geo_model_function, model_key_geo, gd_verbose=False)
							else:  # elliott
								ln_gamma = self.activity_calc_module.activity_coefficient_elliott(
										current_comp, target_elem, solvent_elem, temperature, phase,
										geo_model_function, model_key_geo, gd_verbose=False)
							
							gamma = math.exp(ln_gamma) if not (
									math.isnan(ln_gamma) or math.isinf(ln_gamma)) else float('nan')
							
							# 计算活度
							xi_target = current_comp.get(target_elem, 0.0)
							activity = gamma * xi_target if not math.isnan(gamma) else float('nan')
							
							# 计算基体缩减比例
							base_scale_factor = 1.0 - add_conc
							
							# 存储有效数据
							current_activities[valid_count] = activity
							current_coefficients[valid_count] = gamma
							addition_values[valid_count] = add_conc
							
							valid_count += 1
							successful_calcs += 1
							
							new_results_html += (
								f"<font face='Courier New'>{add_conc:<9.3f}| {activity:<12.4f}| {gamma:<12.4f}| {base_scale_factor:.4f}</font><br>"
							)
							
							if i < 5:
								print(f"添加点{i} (X={add_conc:.3f}): 计算成功, 存储索引{valid_count - 1}")
						
						except Exception as e_calc:
							print(f"添加点{i} (X={add_conc:.3f}): 计算异常 - {e_calc}")
							new_results_html += f"<font face='Courier New'>{add_conc:<9.3f}|     N/A     |     N/A     |   N/A</font><br>"
							failed_calcs += 1
						
						calcs_done += 1
						if hasattr(self, 'progress_dialog'):
							self.progress_dialog.setValue(calcs_done)
							QApplication.processEvents()
					
					print(
						f"{method} 方法 {model_key_geo} 计算完成: 成功 {successful_calcs}/{len(addition_concentrations)}, 有效数据点: {valid_count}")
					
					if hasattr(self, 'progress_dialog') and self.progress_dialog.wasCanceled():
						break
					
					# 截取有效数据
					if valid_count > 0:
						final_additions = addition_values[:valid_count].copy()
						final_activities = current_activities[:valid_count].copy()
						final_coefficients = current_coefficients[:valid_count].copy()
						
						print(f"最终数组长度: {len(final_additions)} (一致性验证通过)")
					else:
						final_additions = np.array([])
						final_activities = np.array([])
						final_coefficients = np.array([])
					
					# 存储结果
					activity_key = f"activity_{method}"
					coefficient_key = f"activity_coefficient_{method}"
					
					self.calculation_results[activity_key][model_key_geo] = {
						"compositions": final_additions,
						"values": final_activities
					}
					self.calculation_results[coefficient_key][model_key_geo] = {
						"compositions": final_additions,
						"values": final_coefficients
					}
					
					# 添加统计信息
					if valid_count > 1:
						valid_activities = final_activities[~np.isnan(final_activities)]
						
						if len(valid_activities) > 0:
							avg_activity = np.mean(valid_activities)
							activity_range = np.max(valid_activities) - np.min(valid_activities)
							
							new_results_html += f"<br><b>📊 {method} 方法 {model_key_geo} 统计:</b><br>"
							new_results_html += f"<font color='#27AE60'>成功计算: {successful_calcs}/{len(addition_concentrations)}</font><br>"
							new_results_html += f"<font color='#2980B9'>{target_elem}平均活度: {avg_activity:.4f}, 变化范围: {activity_range:.4f}</font><br>"
			
			# 更新界面
			self.historical_results_html = new_results_html + self.historical_results_html
			if hasattr(self, 'results_text_right'):
				self.results_text_right.setHtml(self.historical_results_html)
			self.has_calculated = True
			self.update_plot_display_only()
			self.status_bar.set_status("✅ 计算完成")
			
			print("=== 添加元素效应计算完成 ===")
		
		except Exception as e_outer:
			print(f"计算主流程异常: {e_outer}")
			QMessageBox.critical(self, "计算主流程出错", f"发生严重错误: {str(e_outer)}\n{traceback.format_exc()}")
			self.status_bar.set_status("❌ 计算失败")
		finally:
			if hasattr(self, 'progress_dialog') and self.progress_dialog:
				self.progress_dialog.close()
	
	def build_composition_with_addition (self, base_comp_dict, addition_elem, addition_conc):
		"""构建添加元素后的组成（基体按比例缩减）"""
		try:
			if addition_conc >= 1.0:
				return None
			
			# 基体缩减系数
			base_scale_factor = 1.0 - addition_conc
			
			# 构建新组成
			new_comp = {}
			
			# 基体元素按比例缩减
			for elem, orig_frac in base_comp_dict.items():
				new_comp[elem] = orig_frac * base_scale_factor
			
			# 添加新元素
			new_comp[addition_elem] = addition_conc
			
			# 验证总和
			total = sum(new_comp.values())
			if abs(total - 1.0) > 1e-6:
				print(f"警告：组成总和不为1: {total}")
				return None
			
			return new_comp
		
		except Exception as e:
			print(f"构建添加组成时出错: {e}")
			return None
	
	def update_plot_display_only (self):
		"""更新图表显示"""
		if not self.has_calculated:
			self.figure.clear()
			self.canvas.draw()
			return
		
		selected_prop_idx = self.property_combo.currentIndex()
		if selected_prop_idx == 0:  # 活度
			data_darken = self.calculation_results.get("activity_darken", {})
			data_elliott = self.calculation_results.get("activity_elliott", {})
			property_type = "activity"
		else:  # 活度系数
			data_darken = self.calculation_results.get("activity_coefficient_darken", {})
			data_elliott = self.calculation_results.get("activity_coefficient_elliott", {})
			property_type = "activity_coefficient"
		
		if not data_darken and not data_elliott:
			self.figure.clear()
			ax = self.figure.add_subplot(111)
			ax.text(0.5, 0.5, "无数据可显示", ha='center', va='center', transform=ax.transAxes,
			        fontsize=14, color='#666666')
			ax.set_facecolor('#F8F9FA')
			self.canvas.draw()
			return
		
		self.plot_addition_effects(data_darken, data_elliott, property_type)
	
	def plot_addition_effects (self, data_darken, data_elliott, property_type):
		"""绘制添加元素效应图"""
		self.figure.clear()
		ax = self.figure.add_subplot(111)
		
		# 设置图表样式
		ax.set_facecolor('#FAFAFA')
		self.figure.patch.set_facecolor('white')
		
		plot_handles = []
		color_cycle = ['#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6', '#1ABC9C']
		marker_cycle = ['o', 's', '^', 'D', 'v', 'P']
		
		model_count = 0
		
		# 绘制Darken方法结果
		for model_key, data in data_darken.items():
			comps, vals = data.get("compositions"), data.get("values")
			if comps is None or vals is None or len(comps) == 0 or len(vals) == 0:
				continue
			
			# 数据处理
			valid_mask = ~np.isnan(vals) & ~np.isinf(vals) & ~np.isnan(comps) & ~np.isinf(comps)
			comps_p = comps[valid_mask]
			vals_p = vals[valid_mask]
			
			if len(comps_p) > 0:
				# 对数据排序
				sorted_indices = np.argsort(comps_p)
				comps_p = comps_p[sorted_indices]
				vals_p = vals_p[sorted_indices]
				
				# 绘制曲线
				base_color = color_cycle[model_count % len(color_cycle)]
				marker = marker_cycle[model_count % len(marker_cycle)]
				
				try:
					line, = ax.plot(comps_p, vals_p,
					                label=f"{model_key} (Darken)",
					                color=base_color,
					                marker=marker,
					                markersize=6,
					                linewidth=3,
					                alpha=0.9,
					                linestyle='-',
					                markeredgewidth=0.5,
					                markeredgecolor='white')
					
					plot_handles.append(line)
					print(f"Darken {model_key}: 绘制成功")
				except Exception as plot_error:
					print(f"Darken {model_key}: 绘制失败 - {plot_error}")
			
			model_count += 1
		
		# 绘制Elliott方法结果
		for model_key, data in data_elliott.items():
			comps, vals = data.get("compositions"), data.get("values")
			if comps is None or vals is None or len(comps) == 0 or len(vals) == 0:
				continue
			
			# 数据处理
			valid_mask = ~np.isnan(vals) & ~np.isinf(vals) & ~np.isnan(comps) & ~np.isinf(comps)
			comps_p = comps[valid_mask]
			vals_p = vals[valid_mask]
			
			if len(comps_p) > 0:
				# 对数据排序
				sorted_indices = np.argsort(comps_p)
				comps_p = comps_p[sorted_indices]
				vals_p = vals_p[sorted_indices]
				
				# 使用不同的线型来区分Elliott方法
				base_color = color_cycle[model_count % len(color_cycle)]
				
				try:
					line, = ax.plot(comps_p, vals_p,
					                label=f"{model_key} (Elliott)",
					                color=base_color,
					                linewidth=3,
					                alpha=0.7,
					                linestyle='--')
					
					plot_handles.append(line)
					print(f"Elliott {model_key}: 绘制成功")
				except Exception as plot_error:
					print(f"Elliott {model_key}: 绘制失败 - {plot_error}")
			
			model_count += 1
		
		# 绘制理想线
		addition_elem = self.current_parameters.get("addition_element", "?")
		target_elem = self.current_parameters.get("target_element", "?")
		
		# 获取浓度范围用于绘制理想线
		min_add = self.current_parameters.get("addition_range", [0, 0.2, 0.01])[0]
		max_add = self.current_parameters.get("addition_range", [0, 0.2, 0.01])[1]
		x_ideal = np.linspace(min_add, max_add, 100)
		
		if property_type == "activity":
			# 活度理想线 = 目标组分的摩尔分数
			if target_elem == addition_elem:
				# 如果目标组分是添加元素，理想活度就是添加浓度
				y_ideal = x_ideal
			else:
				# 如果目标组分是基体元素，需要考虑基体缩减
				try:
					base_comp_dict = self._parse_composition_static(self.current_parameters.get("base_alloy", ""))
					if base_comp_dict and target_elem in base_comp_dict:
						original_frac = base_comp_dict[target_elem]
						y_ideal = original_frac * (1 - x_ideal)  # 基体缩减后的摩尔分数
					else:
						y_ideal = np.ones_like(x_ideal) * 0.1  # 默认值
				except:
					y_ideal = np.ones_like(x_ideal) * 0.1
			
			ax.plot(x_ideal, y_ideal, 'k:', linewidth=2, alpha=0.7,
			        label=f"理想活度 (X_{{{target_elem}}})", zorder=0)
		else:
			# 活度系数理想线 = 1
			y_ideal = np.ones_like(x_ideal)
			ax.plot(x_ideal, y_ideal, 'k:', linewidth=2, alpha=0.7,
			        label="理想活度系数 (γ=1)", zorder=0)
		
		# 设置标签和标题
		prop_name_cn = "活度" if property_type == "activity" else "活度系数"
		y_label = f"{prop_name_cn} ($a_{{{target_elem}}}$)" if property_type == "activity" else f"{prop_name_cn} ($\\gamma_{{{target_elem}}}$)"
		
		title = (
			f"{self.current_parameters.get('base_alloy', 'N/A')} + {addition_elem} 中 {target_elem} 的 {prop_name_cn}\n"
			f"温度: {self.current_parameters.get('temperature', 'N/A')}K, "
			f"相态: {self.current_parameters.get('phase_state', 'N/A')}")
		
		ax.set_xlabel(f"{addition_elem} 添加摩尔分数", fontsize=12, fontweight='bold')
		ax.set_ylabel(y_label, fontsize=12, fontweight='bold')
		ax.set_title(title, fontsize=11, fontweight='bold', pad=20, color='#2C3E50')
		
		# 网格设置
		ax.grid(True, linestyle='--', alpha=0.3, color='#BDC3C7', linewidth=0.5)
		ax.tick_params(axis='both', which='major', labelsize=10)
		
		# 图例设置
		if plot_handles or property_type == "activity_coefficient":
			try:
				legend = ax.legend(loc='best', fontsize=9, frameon=True, fancybox=True, shadow=True,
				                   framealpha=0.95, facecolor='white', edgecolor='#CCCCCC')
				legend.get_frame().set_linewidth(0.5)
			except Exception as legend_error:
				print(f"设置图例时出错: {legend_error}")
		else:
			ax.text(0.5, 0.5, "无有效数据", ha='center', va='center', transform=ax.transAxes,
			        fontsize=14, color='#E74C3C', fontweight='bold')
		
		# 调整布局
		try:
			self.figure.tight_layout(rect=[0, 0, 1, 0.96])
			self.canvas.draw()
			print("添加效应图表绘制完成")
		except Exception as layout_error:
			print(f"调整布局时出错: {layout_error}")
	
	def export_data (self):
		"""导出数据"""
		if not self.has_calculated or not any(self.calculation_results.values()):
			QMessageBox.warning(self, "导出错误", "请先计算数据。")
			return
		
		file_path, _ = QFileDialog.getSaveFileName(
				self, "导出数据", f"合金添加元素效应计算结果_{QDateTime.currentDateTime().toString('yyyyMMdd_hhmmss')}",
				"CSV 文件 (*.csv);;Excel 文件 (*.xlsx)"
		)
		
		if not file_path:
			return
		
		try:
			self.status_bar.set_status("正在导出数据...")
			if file_path.lower().endswith('.xlsx'):
				self._export_to_excel_internal(file_path)
			else:
				self._export_to_csv_internal(file_path if file_path.lower().endswith('.csv') else file_path + ".csv")
			
			QMessageBox.information(self, "导出成功", f"数据已成功导出至:\n{file_path}")
			self.status_bar.set_status("✅ 数据导出完成")
		
		except Exception as e:
			QMessageBox.critical(self, "导出失败", f"导出时发生错误:\n{e}\n\n{traceback.format_exc()}")
			self.status_bar.set_status("❌ 数据导出失败")
	
	def _export_to_csv_internal (self, file_path):
		"""导出到CSV文件"""
		import csv
		
		addition_elem = self.current_parameters.get("addition_element", "X")
		target_elem = self.current_parameters.get("target_element", "Y")
		
		# 收集所有浓度点
		all_concentrations = set()
		sel_models = self.current_parameters.get("selected_models", [])
		
		for prop_data in self.calculation_results.values():
			for model_key in sel_models:
				if model_key in prop_data and "compositions" in prop_data[model_key]:
					all_concentrations.update(prop_data[model_key]["compositions"])
		
		sorted_concentrations = sorted(list(all_concentrations))
		
		with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
			writer = csv.writer(csvfile)
			
			# 写入参数信息
			writer.writerow(['# 合金元素添加效应计算结果'])
			writer.writerow(['# 计算参数'])
			for key, val in self.current_parameters.items():
				value_str = ", ".join(val) if isinstance(val, list) and key == "selected_models" else str(val)
				writer.writerow([f"# {key}", value_str])
			writer.writerow([])
			
			# 表头
			header = [f'{addition_elem} 添加摩尔分数']
			for mk in sel_models:
				if "activity_darken" in self.calculation_results and mk in self.calculation_results["activity_darken"]:
					header.extend([f'{mk}-{target_elem}-活度(Darken)', f'{mk}-{target_elem}-活度系数(Darken)'])
				if "activity_elliott" in self.calculation_results and mk in self.calculation_results[
					"activity_elliott"]:
					header.extend([f'{mk}-{target_elem}-活度(Elliott)', f'{mk}-{target_elem}-活度系数(Elliott)'])
			writer.writerow(header)
			
			# 写入数据
			for conc_val in sorted_concentrations:
				row = [conc_val]
				for model_key in sel_models:
					# Darken方法数据
					if "activity_darken" in self.calculation_results and mk in self.calculation_results[
						"activity_darken"]:
						act_val = self._get_value_at_concentration(model_key, "activity_darken", conc_val)
						gamma_val = self._get_value_at_concentration(model_key, "activity_coefficient_darken", conc_val)
						row.extend([
							f"{act_val:.6f}" if not math.isnan(act_val) else "N/A",
							f"{gamma_val:.6f}" if not math.isnan(gamma_val) else "N/A"
						])
					
					# Elliott方法数据
					if "activity_elliott" in self.calculation_results and mk in self.calculation_results[
						"activity_elliott"]:
						act_val = self._get_value_at_concentration(model_key, "activity_elliott", conc_val)
						gamma_val = self._get_value_at_concentration(model_key, "activity_coefficient_elliott",
						                                             conc_val)
						row.extend([
							f"{act_val:.6f}" if not math.isnan(act_val) else "N/A",
							f"{gamma_val:.6f}" if not math.isnan(gamma_val) else "N/A"
						])
				
				writer.writerow(row)
	
	def _export_to_excel_internal (self, file_path):
		"""导出到Excel文件（简化版本）"""
		# 如果需要Excel导出，可以参考原代码实现
		# 这里使用CSV格式作为备选
		csv_path = file_path.replace('.xlsx', '.csv')
		self._export_to_csv_internal(csv_path)
		QMessageBox.information(self, "提示", f"已导出为CSV格式: {csv_path}")
	
	def _get_value_at_concentration (self, model_key, property_type, concentration):
		"""获取指定浓度点的属性值"""
		if property_type not in self.calculation_results or model_key not in self.calculation_results[property_type]:
			return float('nan')
		
		data = self.calculation_results[property_type][model_key]
		comps = data["compositions"]
		values = data["values"]
		
		# 查找最接近的浓度点
		idx = np.argmin(np.abs(comps - concentration))
		if abs(comps[idx] - concentration) < 1e-6:
			return values[idx]
		return float('nan')


if __name__ == "__main__":
	app = QApplication(sys.argv)
	
	# 设置高DPI支持
	if hasattr(Qt, 'AA_EnableHighDpiScaling'):
		QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
	if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
		QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
	
	# 设置应用程序属性
	app.setApplicationName("合金元素添加效应计算器")
	app.setApplicationVersion("1.0")
	app.setOrganizationName("Material Science Lab")
	
	main_window = AlloyAdditionWidget()
	main_window.show()
	
	sys.exit(app.exec_())