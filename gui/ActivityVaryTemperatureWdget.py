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
                             QProgressDialog, QTabWidget, QButtonGroup, QRadioButton)
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
		self.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
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
                QPushButton:disabled {
                    background: #CCCCCC;
                    color: #666666;
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
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #E8E8E8, stop:1 #DDDDDD);
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
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1E8449, stop:1 #186239);
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
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 20px;
                border: none;
                background: transparent;
            }
            QDoubleSpinBox::up-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 6px solid #666666;
            }
            QDoubleSpinBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #666666;
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
                image: none;
            }
            QCheckBox::indicator:checked:after {
                content: "✓";
                color: white;
                font-weight: bold;
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


class ActivityTemperatureVariationWidget(QWidget):
	"""
	用于显示活度和活度系数随温度变化的独立窗口。
	"""
	
	def __init__ (self, parent=None):
		super().__init__(parent)
		
		self.binary_model = BinaryModel()
		self.activity_calc_module = ActivityCoefficient()
		
		# 修改数据结构，支持Elliott原始值和Darken修正值
		self.calculation_results = {
			"activity": {},  # Elliott模型的活度
			"activity_coefficient": {},  # Elliott模型的活度系数
			"activity_darken": {},  # Darken模型的活度
			"activity_coefficient_darken": {}  # Darken模型的活度系数
		}
		
		self.current_parameters = {
			"base_matrix": "", "solute": "", "solvent": "", "phase_state": "",
			"order_degree": "", "temp_range": [], "selected_models": []
		}
		self.historical_results_html = ""
		self.has_calculated = False
		self.legend_cids = []
		
		self.setWindowTitle("热力学性质随温度变化计算器")
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
                font-size: 9pt;
                padding: 8px;
            }
            QTextEdit:focus {
                border-color: #4A90E2;
            }
            QSplitter::handle {
                background-color: #CCCCCC;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #4A90E2;
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
                    stop:0 #2C3E50, stop:1 #3498DB);
                color: white;
            }
        """)
		
		layout = QHBoxLayout(title_widget)
		layout.setContentsMargins(20, 10, 20, 10)
		
		# 标题
		title_label = QLabel("热力学性质随温度变化计算器")
		title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
		title_label.setStyleSheet("color: white;")
		layout.addWidget(title_label)
		
		layout.addStretch()
		
		# 副标题
		subtitle_label = QLabel("Advanced Thermodynamic Property Calculator")
		subtitle_label.setFont(QFont("Microsoft YaHei", 10))
		subtitle_label.setStyleSheet("color: #BDC3C7;")
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
		
		layout.addWidget(self.create_alloy_and_calc_params_group())
		layout.addWidget(self.create_temperature_range_group())
		layout.addWidget(self.create_model_selection_group())
		layout.addStretch(1)
		layout.addLayout(self.create_action_buttons())
		
		return left_panel
	
	def create_alloy_and_calc_params_group (self):
		"""创建合金与计算参数组"""
		group = ModernGroupBox("🔬 合金与计算参数")
		layout = QFormLayout(group)
		layout.setSpacing(10)
		layout.setContentsMargins(15, 20, 15, 15)
		layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
		layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
		
		# 合金组成输入
		comp_layout = QHBoxLayout()
		comp_layout.setSpacing(8)
		self.matrix_input = ModernLineEdit("例如: Fe0.7Ni0.3")
		self.matrix_input.setMinimumWidth(200)
		comp_layout.addWidget(self.matrix_input)
		
		update_btn = ModernButton("解析", "secondary")
		update_btn.setFixedWidth(60)
		update_btn.clicked.connect(self.update_element_dropdowns)
		comp_layout.addWidget(update_btn)
		
		layout.addRow(QLabel("合金组成:"), comp_layout)
		
		# 溶剂和溶质选择
		self.solvent_combo = ModernComboBox()
		self.solvent_combo.setFixedWidth(280)
		layout.addRow(QLabel("溶剂元素:"), self.solvent_combo)
		
		self.solute_combo = ModernComboBox()
		self.solute_combo.setFixedWidth(280)
		layout.addRow(QLabel("溶质元素:"), self.solute_combo)
		
		# 相态选择
		self.phase_combo = ModernComboBox()
		self.phase_combo.addItems(["liquid", "solid"])
		self.phase_combo.setFixedWidth(280)
		layout.addRow(QLabel("相态:"), self.phase_combo)
		
		# 合金类型
		self.order_combo = ModernComboBox()
		self.order_combo.addItems(["固溶体 (SS)", "非晶态 (AMP)", "金属间化合物 (IM)"])
		self.order_combo.setToolTip("选择合金的有序度类型")
		self.order_combo.setFixedWidth(280)
		layout.addRow(QLabel("合金类型:"), self.order_combo)
		
		# 热力学性质选择
		self.property_combo = ModernComboBox()
		self.property_combo.addItems(["活度 (a)", "活度系数 (γ)"])
		self.property_combo.currentIndexChanged.connect(self.update_plot_display_only)
		self.property_combo.setFixedWidth(280)
		layout.addRow(QLabel("热力学性质:"), self.property_combo)
		
		return group
	
	def create_temperature_range_group (self):
		"""创建温度范围组"""
		group = ModernGroupBox("🌡️ 温度范围设置")
		layout = QFormLayout(group)
		layout.setSpacing(10)
		layout.setContentsMargins(15, 20, 15, 15)
		layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
		layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
		
		self.min_temp = ModernSpinBox()
		self.min_temp.setRange(1, 5000)
		self.min_temp.setValue(800)
		self.min_temp.setSingleStep(50)
		self.min_temp.setSuffix(" K")
		self.min_temp.setFixedWidth(280)
		layout.addRow(QLabel("最低温度:"), self.min_temp)
		
		self.max_temp = ModernSpinBox()
		self.max_temp.setRange(1, 5000)
		self.max_temp.setValue(1600)
		self.max_temp.setSingleStep(50)
		self.max_temp.setSuffix(" K")
		self.max_temp.setFixedWidth(280)
		layout.addRow(QLabel("最高温度:"), self.max_temp)
		
		self.step_temp = ModernSpinBox()
		self.step_temp.setRange(1, 500)
		self.step_temp.setValue(50)
		self.step_temp.setSingleStep(10)
		self.step_temp.setSuffix(" K")
		self.step_temp.setFixedWidth(280)
		layout.addRow(QLabel("温度步长:"), self.step_temp)
		
		return group
	
	def create_model_selection_group (self):
		"""创建模型选择组"""
		group = ModernGroupBox("⚙️ 外推模型选择")
		layout = QGridLayout(group)
		layout.setSpacing(10)
		layout.setContentsMargins(15, 20, 15, 15)
		
		self.model_checkboxes = {}
		models = [
			("UEM1 模型", "UEM1"),
			("GSM 模型", "GSM"),
			("UEM2 模型", "UEM2"),
			("Muggianu 模型", "Muggianu")
		]
		
		for index, (name, key) in enumerate(models):
			checkbox = ModernCheckBox(name)
			if key in ["UEM1", "GSM"]:
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
                    stop:0 #4A90E2, stop:1 #2E5BBA);
                color: white;
                border-color: #2E5BBA;
            }
            QTabBar::tab:hover:!selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F0F0);
                border-color: #4A90E2;
            }
        """)
		
		# 创建图表页面
		chart_tab = self.create_chart_tab()
		self.tab_widget.addTab(chart_tab, "📈 图表显示")
		
		# 创建结果页面
		results_tab = self.create_results_tab()
		self.tab_widget.addTab(results_tab, "📊 计算结果")
		
		layout.addWidget(self.tab_widget)
		
		return right_panel
	
	def create_chart_tab (self):
		"""创建图表标签页"""
		chart_widget = QWidget()
		
		layout = QVBoxLayout(chart_widget)
		layout.setSpacing(10)
		layout.setContentsMargins(15, 15, 15, 15)
		
		# 图表标题
		chart_title = QLabel("温度变化图表")
		chart_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
		chart_title.setStyleSheet("color: #2C3E50; padding: 5px;")
		layout.addWidget(chart_title)
		
		# 图表显示选项控制区域
		options_frame = QFrame()
		options_frame.setStyleSheet("""
			QFrame {
				background-color: #F8F9FA;
				border: 1px solid #E0E0E0;
				border-radius: 6px;
				padding: 8px;
			}
		""")
		options_layout = QHBoxLayout(options_frame)
		options_layout.setContentsMargins(10, 8, 10, 8)
		
		# 显示模式选择
		mode_label = QLabel("📊 显示模式:")
		mode_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
		mode_label.setStyleSheet("color: #2C3E50; background: transparent; border: none;")
		options_layout.addWidget(mode_label)
		
		# 创建单选按钮组
		self.display_mode_group = QButtonGroup(self)
		
		# 仅显示Darken方法结果 (修改为默认)
		self.darken_only_radio = QRadioButton("仅Darken方法")
		self.darken_only_radio.setChecked(True)  # 设置为默认选中
		self.darken_only_radio.setToolTip("仅显示Darken修正方法的计算结果")
		
		# 对比显示Darken和Elliott方法
		self.comparison_radio = QRadioButton("Darken vs Elliott对比")
		self.comparison_radio.setToolTip("同时显示Darken修正方法和传统Elliott方法的对比结果")
		
		# 设置样式
		radio_style = """
			QRadioButton {
				font-size: 10pt;
				color: #2C3E50;
				background: transparent;
				border: none;
				spacing: 5px;
			}
			QRadioButton::indicator {
				width: 16px;
				height: 16px;
			}
			QRadioButton::indicator:unchecked {
				border: 2px solid #BDC3C7;
				border-radius: 8px;
				background-color: white;
			}
			QRadioButton::indicator:checked {
				border: 2px solid #3498DB;
				border-radius: 8px;
				background-color: #3498DB;
			}
		"""
		self.darken_only_radio.setStyleSheet(radio_style)
		self.comparison_radio.setStyleSheet(radio_style)
		
		# 添加到按钮组
		self.display_mode_group.addButton(self.darken_only_radio, 0)
		self.display_mode_group.addButton(self.comparison_radio, 1)
		
		# 连接信号
		self.darken_only_radio.toggled.connect(self.on_display_mode_changed)
		self.comparison_radio.toggled.connect(self.on_display_mode_changed)
		
		options_layout.addWidget(self.darken_only_radio)
		options_layout.addWidget(self.comparison_radio)
		options_layout.addStretch()
		
		# 添加图例说明
		legend_label = QLabel("💡 实线=Darken方法, 虚线=Elliott方法")
		legend_label.setFont(QFont("Microsoft YaHei", 9))
		legend_label.setStyleSheet("color: #7F8C8D; background: transparent; border: none;")
		options_layout.addWidget(legend_label)
		
		layout.addWidget(options_frame)
		
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
		
		refresh_results_btn = ModernButton("🔄 刷新显示", "secondary")
		refresh_results_btn.setMaximumWidth(140)
		refresh_results_btn.setFont(QFont("Microsoft YaHei", 8, QFont.Bold))
		refresh_results_btn.clicked.connect(self.refresh_results_display)
		button_layout.addWidget(refresh_results_btn)
		
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
		self.results_text_right.setPlaceholderText("计算结果将在此处按时间顺序显示...")
		
		self.results_text_right.setStyleSheet("""
            QTextEdit {
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                background-color: #FAFAFA;
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                font-size: 10pt;
                padding: 12px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border-color: #4A90E2;
                background-color: white;
            }
        """)
		
		layout.addWidget(self.results_text_right, 1)
		
		# 结果统计信息
		stats_layout = QHBoxLayout()
		self.stats_label = QLabel("统计信息：暂无计算记录")
		self.stats_label.setStyleSheet("color: #666666; font-size: 9pt; padding: 5px;")
		stats_layout.addWidget(self.stats_label)
		stats_layout.addStretch()
		
		layout.addLayout(stats_layout)
		
		return results_widget
	
	def refresh_results_display (self):
		"""刷新结果显示"""
		if hasattr(self, 'results_text_right'):
			self.results_text_right.setHtml(self.historical_results_html)
			self.status_bar.set_status("结果显示已刷新")
	
	def update_results_stats (self):
		"""更新结果统计信息"""
		if hasattr(self, 'stats_label'):
			calc_count = self.historical_results_html.count('<hr>')
			if calc_count > 0:
				self.stats_label.setText(f"统计信息：共 {calc_count} 次计算记录")
			else:
				self.stats_label.setText("统计信息：暂无计算记录")
	
	def clear_history (self):
		"""清除计算历史"""
		reply = QMessageBox.question(self, "确认清除", "确定要清除所有计算历史记录吗？",
		                             QMessageBox.Yes | QMessageBox.No,
		                             QMessageBox.No)
		if reply == QMessageBox.Yes:
			self.historical_results_html = ""
			if hasattr(self, 'results_text_right'):
				self.results_text_right.clear()
			self.update_results_stats()
			self.status_bar.set_status("历史记录已清除")
	
	def update_element_dropdowns (self):
		"""更新元素下拉列表"""
		comp_input = self.matrix_input.text().strip()
		self.solvent_combo.blockSignals(True)
		self.solute_combo.blockSignals(True)
		self.solvent_combo.clear()
		self.solute_combo.clear()
		
		if not comp_input:
			self.solvent_combo.blockSignals(False)
			self.solute_combo.blockSignals(False)
			return
		
		try:
			elements = sorted(list(set(re.findall(r"([A-Z][a-z]?)", comp_input))))
			if not elements:
				self.solvent_combo.blockSignals(False)
				self.solute_combo.blockSignals(False)
				return
			
			self.solvent_combo.addItems(elements)
			self.solute_combo.addItems(elements)
			
			if elements:
				self.solvent_combo.setCurrentIndex(0)
				self.solute_combo.setCurrentIndex(1 if len(elements) > 1 else 0)
			
			self.status_bar.set_status(f"检测到 {len(elements)} 个元素: {', '.join(elements)}")
		
		except Exception as e:
			print(f"更新元素下拉列表时出错: {str(e)}")
			self.status_bar.set_status("合金组成解析失败")
		finally:
			self.solvent_combo.blockSignals(False)
			self.solute_combo.blockSignals(False)
	
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
			"UEM2": self.binary_model.UEM2,
			"GSM": self.binary_model.GSM,
			"Muggianu": getattr(self.binary_model, 'Muggianu', None)
		}
		
		func = model_method_map.get(model_name_str)
		if func is None:
			QMessageBox.warning(self, "模型警告", f"模型 '{model_name_str}' 未找到或未实现。")
			return None
		
		return func
	
	def run_calculation_thread (self):
		"""运行计算线程"""
		# 验证输入
		if not self.matrix_input.text().strip():
			QMessageBox.warning(self, "输入缺失", "请输入合金组成。")
			return
		
		if not self.solvent_combo.currentText() or not self.solute_combo.currentText():
			QMessageBox.warning(self, "输入缺失", "请选择溶剂和溶质元素。")
			return
		
		if self.min_temp.value() >= self.max_temp.value():
			QMessageBox.warning(self, "温度范围错误", "最低温度必须小于最高温度。")
			return
		
		if self.step_temp.value() <= 0:
			QMessageBox.warning(self, "温度步长错误", "温度步长必须为正数。")
			return
		
		# 创建进度对话框
		self.progress_dialog = QProgressDialog("正在计算，请稍候...", "取消", 0, 0, self)
		self.progress_dialog.setWindowModality(Qt.WindowModal)
		self.progress_dialog.setMinimumDuration(0)
		self.progress_dialog.setValue(0)
		self.progress_dialog.show()
		QApplication.processEvents()
		
		self.status_bar.set_status("正在计算...")
		self.calculate_all_properties()
		
		if hasattr(self, 'progress_dialog') and self.progress_dialog:
			self.progress_dialog.close()
	
	def calculate_all_properties (self):
		"""计算所有属性 - Elliott原始值和Darken修正值"""
		try:
			self.has_calculated = False
			# 重置所有数据结构
			self.calculation_results = {
				"activity": {},
				"activity_coefficient": {},
				"activity_darken": {},
				"activity_coefficient_darken": {}
			}
			
			# 获取参数
			base_matrix_str = self.matrix_input.text().strip()
			solvent_elem = self.solvent_combo.currentText()
			solute_elem = self.solute_combo.currentText()
			phase = self.phase_combo.currentText().lower()
			order_deg = self.order_combo.currentText()
			min_t, max_t, step_t = self.min_temp.value(), self.max_temp.value(), self.step_temp.value()
			
			# 解析组成
			comp_dict_main = ActivityTemperatureVariationWidget._parse_composition_static(base_matrix_str)
			if comp_dict_main is None:
				QMessageBox.critical(self, "成分解析失败", f"无法解析: {base_matrix_str}")
				return
			
			if solute_elem not in comp_dict_main:
				QMessageBox.critical(self, "输入错误", f"溶质 '{solute_elem}' 不在合金 '{base_matrix_str}' 中。")
				return
			
			if solvent_elem not in comp_dict_main:
				QMessageBox.warning(self, "输入警告", f"溶剂 '{solvent_elem}' 不在 '{base_matrix_str}' 中。")
			
			# 生成温度序列
			temperatures = np.arange(min_t, max_t + step_t / 2, step_t)
			if len(temperatures) == 0:
				QMessageBox.warning(self, "温度范围错误", "无有效温度点。")
				return
			
			# 更新当前参数
			self.current_parameters = {
				"base_matrix": base_matrix_str,
				"solute": solute_elem,
				"solvent": solvent_elem,
				"phase_state": phase,
				"order_degree": order_deg,
				"temp_range": [min_t, max_t, step_t],
				"selected_models": []
			}
			
			# 获取选择的模型
			selected_models_to_run = []
			for mk, cbx in self.model_checkboxes.items():
				if cbx.isChecked():
					gmf = self.get_model_function(mk)
					if gmf:
						selected_models_to_run.append((mk, gmf))
						self.current_parameters["selected_models"].append(mk)
			
			if not selected_models_to_run:
				QMessageBox.warning(self, "模型未选择", "请至少选择一个外推模型。")
				return
			
			# 创建结果HTML - 始终显示两种方法的对比结果
			current_timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
			new_results_html = f"<hr><b>🕐 计算时间: {current_timestamp}</b><br>"
			new_results_html += f"<b>📋 计算参数:</b><br>"
			new_results_html += f"合金: {base_matrix_str}, 溶剂: {solvent_elem}, 溶质: {solute_elem}<br>"
			new_results_html += f"相态: {phase}, 温度: {min_t}K - {max_t}K (步长 {step_t}K)<br>"
			new_results_html += f"外推模型: {', '.join(self.current_parameters['selected_models'])}<br><hr>"
			
			# 设置进度条
			total_calcs = len(selected_models_to_run) * len(temperatures)
			if hasattr(self, 'progress_dialog'):
				self.progress_dialog.setRange(0, total_calcs)
			calcs_done = 0
			
			# 执行计算
			for model_key_geo, geo_model_function in selected_models_to_run:
				current_activities = []
				current_coefficients = []
				current_activities_darken = []
				current_coefficients_darken = []
				
				new_results_html += f"<br><b>⚙️ 外推模型: {model_key_geo}</b><br>"
				new_results_html += f"<font face='Courier New' color='#2C3E50'><b>Temp(K)  | Darken-Act | Darken-γ  | Elliott-Act | Elliott-γ  | Δa(%)  | Δγ(%)</b></font><br>"
				new_results_html += f"<font face='Courier New'>---------|------------|-----------|-------------|-----------|--------|------</font><br>"
				
				for temp_k in temperatures:
					if hasattr(self, 'progress_dialog') and self.progress_dialog.wasCanceled():
						new_results_html += "❌ 计算已取消<br>"
						break
					
					comp_for_calc = comp_dict_main.copy()
					xi_solute = comp_for_calc.get(solute_elem, 0.0)
					
					try:
						# 计算Elliott原始方法
						ln_gamma_elliott = self.activity_calc_module.activity_coefficient_elliott(
								comp_for_calc, solute_elem, solvent_elem, temp_k, phase,
								geo_model_function, model_key_geo
						)
						gamma_elliott = math.exp(ln_gamma_elliott) if not (
								math.isnan(ln_gamma_elliott) or math.isinf(ln_gamma_elliott)) else float('nan')
						act_elliott = gamma_elliott * xi_solute if not math.isnan(gamma_elliott) else float('nan')
						
						# 计算Darken修正方法
						ln_gamma_darken = self.activity_calc_module.activity_coefficient_darken(
								comp_for_calc, solute_elem, solvent_elem, temp_k, phase,
								geo_model_function, model_key_geo, gd_verbose=True
						)
						gamma_darken = math.exp(ln_gamma_darken) if not (
								math.isnan(ln_gamma_darken) or math.isinf(ln_gamma_darken)) else float('nan')
						act_darken = gamma_darken * xi_solute if not math.isnan(gamma_darken) else float('nan')
						
						# 计算相对差异百分比
						if not (math.isnan(act_elliott) or math.isnan(act_darken)) and abs(act_darken) > 1e-10:
							delta_act_percent = abs((act_elliott - act_darken) / act_darken) * 100
						else:
							delta_act_percent = float('nan')
						
						if not (math.isnan(gamma_elliott) or math.isnan(gamma_darken)) and abs(gamma_darken) > 1e-10:
							delta_gamma_percent = abs((gamma_elliott - gamma_darken) / gamma_darken) * 100
						else:
							delta_gamma_percent = float('nan')
						
						# 存储数据
						current_activities.append(act_elliott)
						current_coefficients.append(gamma_elliott)
						current_activities_darken.append(act_darken)
						current_coefficients_darken.append(gamma_darken)
						
						# 格式化差异显示 - 带颜色标识 (现在以Darken为基准)
						delta_act_str = f"{delta_act_percent:6.2f}" if not math.isnan(delta_act_percent) else "  N/A"
						delta_gamma_str = f"{delta_gamma_percent:6.2f}" if not math.isnan(
								delta_gamma_percent) else "  N/A"
						
						# 根据差异大小设置颜色
						if not math.isnan(delta_act_percent) and delta_act_percent > 5:
							delta_act_color = "#E74C3C"  # 红色：差异大
						elif not math.isnan(delta_act_percent) and delta_act_percent > 1:
							delta_act_color = "#F39C12"  # 橙色：差异中等
						else:
							delta_act_color = "#27AE60"  # 绿色：差异小
						
						if not math.isnan(delta_gamma_percent) and delta_gamma_percent > 5:
							delta_gamma_color = "#E74C3C"
						elif not math.isnan(delta_gamma_percent) and delta_gamma_percent > 1:
							delta_gamma_color = "#F39C12"
						else:
							delta_gamma_color = "#27AE60"
						
						# 调整显示顺序：Darken在前，Elliott在后
						new_results_html += (
							f"<font face='Courier New'>{temp_k:<9.1f}| {act_darken:<11.4f}| {gamma_darken:<10.4f}| "
							f"{act_elliott:<12.4f}| {gamma_elliott:<10.4f}| "
							f"<font color='{delta_act_color}'>{delta_act_str}</font>| "
							f"<font color='{delta_gamma_color}'>{delta_gamma_str}</font></font><br>"
						)
					
					except Exception as e_calc:
						print(f"计算错误 (T={temp_k}K, 模型={model_key_geo}): {e_calc}")
						current_activities.append(float('nan'))
						current_coefficients.append(float('nan'))
						current_activities_darken.append(float('nan'))
						current_coefficients_darken.append(float('nan'))
						
						new_results_html += f"<font face='Courier New'>{temp_k:<9.1f}|     N/A    |    N/A    |      N/A    |    N/A    |  N/A   |  N/A</font><br>"
					
					calcs_done += 1
					if hasattr(self, 'progress_dialog'):
						self.progress_dialog.setValue(calcs_done)
						QApplication.processEvents()
				
				if hasattr(self, 'progress_dialog') and self.progress_dialog.wasCanceled():
					break
				
				# 存储所有结果
				self.calculation_results["activity"][model_key_geo] = {
					"temperatures": temperatures.copy(),
					"values": np.array(current_activities)
				}
				self.calculation_results["activity_coefficient"][model_key_geo] = {
					"temperatures": temperatures.copy(),
					"values": np.array(current_coefficients)
				}
				self.calculation_results["activity_darken"][model_key_geo] = {
					"temperatures": temperatures.copy(),
					"values": np.array(current_activities_darken)
				}
				self.calculation_results["activity_coefficient_darken"][model_key_geo] = {
					"temperatures": temperatures.copy(),
					"values": np.array(current_coefficients_darken)
				}
				
				# 添加统计对比信息 (以Darken为基准)
				if len(current_activities) > 0 and len(current_activities_darken) > 0:
					valid_elliott_act = [x for x in current_activities if not math.isnan(x)]
					valid_darken_act = [x for x in current_activities_darken if not math.isnan(x)]
					valid_elliott_gamma = [x for x in current_coefficients if not math.isnan(x)]
					valid_darken_gamma = [x for x in current_coefficients_darken if not math.isnan(x)]
					
					if valid_elliott_act and valid_darken_act and len(valid_elliott_act) == len(valid_darken_act):
						avg_diff_act = np.mean(
								[abs((e - d) / d) * 100 for d, e in zip(valid_darken_act, valid_elliott_act) if
								 abs(d) > 1e-10])
						max_diff_act = np.max(
								[abs((e - d) / d) * 100 for d, e in zip(valid_darken_act, valid_elliott_act) if
								 abs(d) > 1e-10])
						
						if valid_elliott_gamma and valid_darken_gamma and len(valid_elliott_gamma) == len(
								valid_darken_gamma):
							avg_diff_gamma = np.mean(
									[abs((e - d) / d) * 100 for d, e in zip(valid_darken_gamma, valid_elliott_gamma) if
									 abs(d) > 1e-10])
							max_diff_gamma = np.max(
									[abs((e - d) / d) * 100 for d, e in zip(valid_darken_gamma, valid_elliott_gamma) if
									 abs(d) > 1e-10])
							
							new_results_html += f"<br><b>📊 模型 {model_key_geo} 对比统计 (以Darken为基准):</b><br>"
							new_results_html += f"<font color='#2980B9'>活度 - Elliott与Darken平均差异: {avg_diff_act:.2f}%, 最大差异: {max_diff_act:.2f}%</font><br>"
							new_results_html += f"<font color='#8E44AD'>活度系数 - Elliott与Darken平均差异: {avg_diff_gamma:.2f}%, 最大差异: {max_diff_gamma:.2f}%</font><br>"
			
			# 更新界面
			self.historical_results_html = new_results_html + self.historical_results_html
			if hasattr(self, 'results_text_right'):
				self.results_text_right.setHtml(self.historical_results_html)
			self.update_results_stats()
			self.has_calculated = True
			self.update_plot_display_only()
			self.status_bar.set_status("✅ 计算完成")
		
		except Exception as e_outer:
			QMessageBox.critical(self, "计算主流程出错", f"发生严重错误: {str(e_outer)}\n{traceback.format_exc()}")
			self.status_bar.set_status("❌ 计算失败")
		finally:
			if hasattr(self, 'progress_dialog') and self.progress_dialog:
				self.progress_dialog.close()
	
	def on_display_mode_changed (self):
		"""显示模式改变时的处理函数"""
		if hasattr(self, 'has_calculated') and self.has_calculated:
			self.update_plot_display_only()
		
		# 更新状态栏
		if self.get_current_display_mode():
			self.status_bar.set_status("图表模式: Darken vs Elliott对比")
		else:
			self.status_bar.set_status("图表模式: 默认Darken")
	
	def get_current_display_mode (self):
		"""获取当前显示模式"""
		return hasattr(self, 'comparison_radio') and self.comparison_radio.isChecked()
	
	def set_display_mode (self, show_comparison):
		"""设置显示模式"""
		if hasattr(self, 'comparison_radio') and hasattr(self, 'darken_only_radio'):
			if show_comparison:
				self.comparison_radio.setChecked(True)
			else:
				self.darken_only_radio.setChecked(True)
	
	def update_plot_display_only (self):
		"""仅更新图表显示"""
		if not self.has_calculated:
			self.figure.clear()
			self.canvas.draw()
			return
		
		selected_prop_idx = self.property_combo.currentIndex()
		is_comparison_enabled = self.get_current_display_mode()
		
		if is_comparison_enabled:
			# 对比模式：同时显示Darken和Elliott值
			prop_to_plot = "activity" if selected_prop_idx == 0 else "activity_coefficient"
			darken_data = self.calculation_results.get(f"{prop_to_plot}_darken", {})
			elliott_data = self.calculation_results.get(prop_to_plot, {})
			
			self.plot_comparison_variation(darken_data, elliott_data, prop_to_plot)
		else:
			# 默认模式：只显示Darken值
			prop_to_plot = "activity" if selected_prop_idx == 0 else "activity_coefficient"
			data_for_plotting = self.calculation_results.get(f"{prop_to_plot}_darken", {})
			
			if not data_for_plotting:
				self.figure.clear()
				ax = self.figure.add_subplot(111)
				ax.text(0.5, 0.5, "无数据可显示", ha='center', va='center', transform=ax.transAxes,
				        fontsize=14, color='#666666')
				ax.set_facecolor('#F8F9FA')
				self.canvas.draw()
				return
			
			self.plot_property_variation(data_for_plotting, prop_to_plot, method_name="Darken")
	
	def plot_property_variation (self, model_data_dict, property_type, method_name="Darken"):
		"""绘制属性变化图（仅Darken方法）"""
		self.figure.clear()
		ax = self.figure.add_subplot(111)
		
		# 设置图表样式
		ax.set_facecolor('#FAFAFA')
		self.figure.patch.set_facecolor('white')
		
		plot_handles, plot_labels = [], []
		# 避免与理想线颜色(#7F8C8D)重合的颜色方案
		color_cycle = ['#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6', '#1ABC9C', '#E67E22', '#34495E']
		marker_cycle = ['o', 's', '^', 'D', 'v', 'P', '*', 'X']
		min_T_overall, max_T_overall = float('inf'), float('-inf')
		
		for i, (model_key, data) in enumerate(model_data_dict.items()):
			temps, vals = data.get("temperatures"), data.get("values")
			if temps is None or vals is None or len(temps) == 0 or len(vals) == 0:
				continue
			
			valid_indices = ~np.isnan(vals) & ~np.isinf(vals)
			temps_p, vals_p = temps[valid_indices], vals[valid_indices]
			
			if len(temps_p) == 0:
				continue
			
			min_T_overall = min(min_T_overall, temps_p.min())
			max_T_overall = max(max_T_overall, temps_p.max())
			
			line, = ax.plot(temps_p, vals_p,
			                label=model_key,
			                color=color_cycle[i % len(color_cycle)],
			                marker=marker_cycle[i % len(marker_cycle)],
			                markersize=6,
			                linewidth=2.5,
			                alpha=0.8)
			plot_handles.append(line)
			plot_labels.append(model_key)
		
		# 设置标签和标题
		solute = self.current_parameters.get("solute", "?")
		prop_name_cn = "活度" if property_type == "activity" else "活度系数"
		y_label = f"{prop_name_cn} ($a_{{{solute}}}$)" if property_type == "activity" else f"{prop_name_cn} ($\\gamma_{{{solute}}}$)"
		
		title = (f"{self.current_parameters.get('base_matrix', 'N/A')} 中 {solute} 的 {prop_name_cn} vs. 温度\n"
		         f"溶剂: {self.current_parameters.get('solvent', 'N/A')}, "
		         f"相态: {self.current_parameters.get('phase_state', 'N/A')} ({method_name} 方法)")
		
		ax.set_xlabel("温度 (K)", fontsize=12, fontweight='bold')
		ax.set_ylabel(y_label, fontsize=12, fontweight='bold')
		ax.set_title(title, fontsize=13, fontweight='bold', pad=20, color='#2C3E50')
		
		# 网格设置
		ax.grid(True, linestyle='--', alpha=0.3, color='#BDC3C7')
		ax.tick_params(axis='both', which='major', labelsize=10)
		
		# 添加参考线（避免与数据线颜色重合）
		if plot_handles and min_T_overall != float('inf'):
			if property_type == "activity":
				comp_dict_ref = ActivityTemperatureVariationWidget._parse_composition_static(
						self.current_parameters["base_matrix"])
				if comp_dict_ref and solute in comp_dict_ref:
					mole_frac = comp_dict_ref[solute]
					ax.axhline(y=mole_frac, color='#7F8C8D', linestyle=':', linewidth=2, alpha=0.7,
					           label=f"$X_{{{solute}}}$ = {mole_frac:.3f}")
			elif property_type == "activity_coefficient":
				ax.axhline(y=1.0, color='#7F8C8D', linestyle=':', linewidth=2, alpha=0.7,
				           label="理想溶液 ($\\gamma=1$)")
		
		# 图例设置
		if plot_handles:
			ax.legend(loc='best', fontsize=10, frameon=True, fancybox=True, shadow=True,
			          framealpha=0.9, facecolor='white', edgecolor='#CCCCCC')
		else:
			ax.text(0.5, 0.5, "无有效数据", ha='center', va='center', transform=ax.transAxes,
			        fontsize=14, color='#E74C3C', fontweight='bold')
		
		# 调整布局
		self.figure.tight_layout(rect=[0, 0, 1, 0.96])
		self.canvas.draw()
	
	def plot_comparison_variation (self, darken_data, elliott_data, property_type):
		"""绘制对比图表：Darken修正 vs Elliott原始方法"""
		self.figure.clear()
		ax = self.figure.add_subplot(111)
		
		# 设置图表样式
		ax.set_facecolor('#FAFAFA')
		self.figure.patch.set_facecolor('white')
		
		# 避免与理想线颜色(#7F8C8D)重合的明亮颜色方案
		color_cycle = ['#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6', '#1ABC9C', '#E67E22', '#C0392B']
		marker_cycle = ['o', 's', '^', 'D', 'v', 'P', '*', 'X']
		min_T_overall, max_T_overall = float('inf'), float('-inf')
		
		legend_elements = []
		
		# 绘制Darken vs Elliott对比曲线
		for i, model_key in enumerate(darken_data.keys()):
			if model_key not in elliott_data:
				continue
			
			# Darken修正数据
			darken_data_dict = darken_data[model_key]
			darken_temps, darken_vals = darken_data_dict.get("temperatures"), darken_data_dict.get("values")
			
			# Elliott原始数据
			elliott_data_dict = elliott_data[model_key]
			elliott_temps, elliott_vals = elliott_data_dict.get("temperatures"), elliott_data_dict.get("values")
			
			if (darken_temps is None or darken_vals is None or len(darken_temps) == 0 or
					elliott_temps is None or elliott_vals is None or len(elliott_temps) == 0):
				continue
			
			# 处理Darken数据
			darken_valid_indices = ~np.isnan(darken_vals) & ~np.isinf(darken_vals)
			darken_temps_p, darken_vals_p = darken_temps[darken_valid_indices], darken_vals[darken_valid_indices]
			
			# 处理Elliott数据
			elliott_valid_indices = ~np.isnan(elliott_vals) & ~np.isinf(elliott_vals)
			elliott_temps_p, elliott_vals_p = elliott_temps[elliott_valid_indices], elliott_vals[elliott_valid_indices]
			
			if len(darken_temps_p) == 0 and len(elliott_temps_p) == 0:
				continue
			
			# 更新温度范围
			if len(darken_temps_p) > 0:
				min_T_overall = min(min_T_overall, darken_temps_p.min())
				max_T_overall = max(max_T_overall, darken_temps_p.max())
			if len(elliott_temps_p) > 0:
				min_T_overall = min(min_T_overall, elliott_temps_p.min())
				max_T_overall = max(max_T_overall, elliott_temps_p.max())
			
			color = color_cycle[i % len(color_cycle)]
			marker = marker_cycle[i % len(marker_cycle)]
			
			# 绘制Darken修正曲线（主要）
			if len(darken_temps_p) > 0:
				line_darken, = ax.plot(darken_temps_p, darken_vals_p,
				                       color=color,
				                       marker=marker,
				                       markersize=6,
				                       linewidth=2.5,
				                       linestyle='-',  # 实线 - Darken作为主要方法
				                       alpha=0.8,
				                       markeredgewidth=0.5,
				                       markeredgecolor='white',
				                       label=f'{model_key} (Darken)')
				legend_elements.append(line_darken)
			
			# 绘制Elliott原始曲线（对比）
			if len(elliott_temps_p) > 0:
				line_elliott, = ax.plot(elliott_temps_p, elliott_vals_p,
				                        color=color,
				                        marker=marker,
				                        markersize=5,
				                        linewidth=2,
				                        linestyle='--',  # 虚线区分 - Elliott作为对比
				                        alpha=0.7,
				                        markerfacecolor='white',
				                        markeredgecolor=color,
				                        markeredgewidth=1.5,
				                        label=f'{model_key} (Elliott)')
				legend_elements.append(line_elliott)
		
		# 设置标签和标题
		solute = self.current_parameters.get("solute", "?")
		prop_name_cn = "活度" if property_type == "activity" else "活度系数"
		y_label = f"{prop_name_cn} ($a_{{{solute}}}$)" if property_type == "activity" else f"{prop_name_cn} ($\\gamma_{{{solute}}}$)"
		
		title = (f"{self.current_parameters.get('base_matrix', 'N/A')} 中 {solute} 的 {prop_name_cn} vs. 温度\n"
		         f"Darken修正方法 vs Elliott传统方法 | 溶剂: {self.current_parameters.get('solvent', 'N/A')}, "
		         f"相态: {self.current_parameters.get('phase_state', 'N/A')}")
		
		ax.set_xlabel("温度 (K)", fontsize=12, fontweight='bold')
		ax.set_ylabel(y_label, fontsize=12, fontweight='bold')
		ax.set_title(title, fontsize=13, fontweight='bold', pad=20, color='#2C3E50')
		
		# 网格设置
		ax.grid(True, linestyle='--', alpha=0.3, color='#BDC3C7')
		ax.tick_params(axis='both', which='major', labelsize=10)
		
		# 添加参考线（避免与数据线颜色重合）
		if legend_elements and min_T_overall != float('inf'):
			if property_type == "activity":
				comp_dict_ref = ActivityTemperatureVariationWidget._parse_composition_static(
						self.current_parameters["base_matrix"])
				if comp_dict_ref and solute in comp_dict_ref:
					mole_frac = comp_dict_ref[solute]
					ref_line = ax.axhline(y=mole_frac, color='#7F8C8D', linestyle=':', linewidth=2, alpha=0.7,
					                      label=f"$X_{{{solute}}}$ = {mole_frac:.3f}")
					legend_elements.append(ref_line)
			elif property_type == "activity_coefficient":
				ref_line = ax.axhline(y=1.0, color='#7F8C8D', linestyle=':', linewidth=2, alpha=0.7,
				                      label="理想溶液 ($\\gamma=1$)")
				legend_elements.append(ref_line)
		
		# 图例设置 - 修正了图例重复问题
		if legend_elements:
			ax.legend(handles=legend_elements, loc='best', fontsize=9, frameon=True,
			          fancybox=True, shadow=True, framealpha=0.9, facecolor='white',
			          edgecolor='#CCCCCC', ncol=1)
		else:
			ax.text(0.5, 0.5, "无有效数据", ha='center', va='center', transform=ax.transAxes,
			        fontsize=14, color='#E74C3C', fontweight='bold')
		
		# 调整布局
		self.figure.tight_layout(rect=[0, 0, 1, 0.96])
		self.canvas.draw()
	
	def export_data (self):
		"""导出数据"""
		if not self.has_calculated or not any(self.calculation_results.values()):
			QMessageBox.warning(self, "导出错误", "请先计算数据。")
			return
		
		file_path, _ = QFileDialog.getSaveFileName(
				self, "导出数据", f"热力学计算结果_{QDateTime.currentDateTime().toString('yyyyMMdd_hhmmss')}",
				"Excel 文件 (*.xlsx);;CSV 文件 (*.csv)"
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
	
	def _get_value_at_temperature (self, model_key, property_type, temperature):
		"""获取指定温度点的属性值"""
		if property_type not in self.calculation_results or model_key not in self.calculation_results[property_type]:
			return float('nan')
		
		data = self.calculation_results[property_type][model_key]
		temps = data["temperatures"]
		values = data["values"]
		
		# 查找最接近的温度点
		idx = np.argmin(np.abs(temps - temperature))
		if abs(temps[idx] - temperature) < 1e-6:  # 容差检查
			return values[idx]
		return float('nan')
	
	def _export_to_csv_internal (self, file_path):
		"""导出到CSV文件"""
		import csv
		
		all_temps = set()
		sel_models = self.current_parameters.get("selected_models", [])
		
		if not sel_models:
			return
		
		# 收集所有温度点
		for prop_data in self.calculation_results.values():
			for model_key in sel_models:
				if model_key in prop_data and "temperatures" in prop_data[model_key]:
					all_temps.update(prop_data[model_key]["temperatures"])
		
		sorted_temps = sorted(list(all_temps))
		if not sorted_temps:
			QMessageBox.warning(self, "无数据", "无温度点可导出。")
			return
		
		with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
			writer = csv.writer(csvfile)
			
			# 写入参数信息
			writer.writerow(['# 热力学性质计算结果 (Darken vs Elliott 对比)'])
			writer.writerow(['# 计算参数'])
			for key, val in self.current_parameters.items():
				value_str = ", ".join(val) if isinstance(val, list) and key == "selected_models" else str(val)
				writer.writerow([f"# {key}", value_str])
			writer.writerow([])
			
			# 表头：调整为以Darken为主
			header = ['温度 (K)']
			for mk in sel_models:
				header.extend([
					f'{mk}-Darken-活度', f'{mk}-Darken-活度系数',
					f'{mk}-Elliott-活度', f'{mk}-Elliott-活度系数'
				])
			
			writer.writerow(header)
			
			# 写入数据
			for temp_k in sorted_temps:
				row = [temp_k]
				for model_key in sel_models:
					# Darken修正活度
					act_darken = self._get_value_at_temperature(model_key, "activity_darken", temp_k)
					act_darken_str = f"{act_darken:.6f}" if not math.isnan(act_darken) else "N/A"
					
					# Darken修正活度系数
					coef_darken = self._get_value_at_temperature(model_key, "activity_coefficient_darken", temp_k)
					coef_darken_str = f"{coef_darken:.6f}" if not math.isnan(coef_darken) else "N/A"
					
					# Elliott原始活度
					act_elliott = self._get_value_at_temperature(model_key, "activity", temp_k)
					act_elliott_str = f"{act_elliott:.6f}" if not math.isnan(act_elliott) else "N/A"
					
					# Elliott原始活度系数
					coef_elliott = self._get_value_at_temperature(model_key, "activity_coefficient", temp_k)
					coef_elliott_str = f"{coef_elliott:.6f}" if not math.isnan(coef_elliott) else "N/A"
					
					row.extend([act_darken_str, coef_darken_str, act_elliott_str, coef_elliott_str])
				
				writer.writerow(row)
	
	def _export_to_excel_internal (self, file_path):
		"""导出到Excel文件"""
		try:
			import xlsxwriter
		except ImportError:
			QMessageBox.warning(self, "依赖缺失", "导出Excel需要安装 xlsxwriter 库。\n请使用: pip install xlsxwriter")
			return
		
		workbook = xlsxwriter.Workbook(file_path)
		worksheet = workbook.add_worksheet('Darken_vs_Elliott对比')
		
		# 定义格式
		title_format = workbook.add_format({
			'bold': True, 'font_size': 16, 'align': 'center',
			'bg_color': '#2C3E50', 'font_color': 'white'
		})
		header_format = workbook.add_format({
			'bold': True, 'align': 'center', 'bg_color': '#3498DB',
			'font_color': 'white', 'border': 1, 'text_wrap': True
		})
		data_format = workbook.add_format({
			'num_format': '0.000000', 'align': 'center', 'border': 1
		})
		darken_format = workbook.add_format({
			'num_format': '0.000000', 'align': 'center', 'border': 1,
			'bg_color': '#E8F6F3'  # 浅绿色背景 - Darken
		})
		elliott_format = workbook.add_format({
			'num_format': '0.000000', 'align': 'center', 'border': 1,
			'bg_color': '#E8F4FD'  # 浅蓝色背景 - Elliott
		})
		param_format = workbook.add_format({
			'bold': True, 'bg_color': '#ECF0F1', 'border': 1
		})
		
		row = 0
		
		# 标题
		worksheet.merge_range(row, 0, row, 12, 'Darken vs Elliott 方法对比数据', title_format)
		row += 2
		
		# 参数信息
		worksheet.write(row, 0, '计算参数', param_format)
		row += 1
		
		for k, v in self.current_parameters.items():
			value_str = ", ".join(v) if isinstance(v, list) and k == "selected_models" else str(v)
			worksheet.write(row, 0, k, param_format)
			worksheet.write(row, 1, value_str)
			row += 1
		
		row += 1
		
		# 数据表头
		col = 0
		worksheet.write(row, col, '温度 (K)', header_format)
		col += 1
		
		for model_key in self.current_parameters.get("selected_models", []):
			worksheet.write(row, col, f'{model_key}\nDarken-活度', header_format)
			col += 1
			worksheet.write(row, col, f'{model_key}\nDarken-活度系数', header_format)
			col += 1
			worksheet.write(row, col, f'{model_key}\nElliott-活度', header_format)
			col += 1
			worksheet.write(row, col, f'{model_key}\nElliott-活度系数', header_format)
			col += 1
		
		row += 1
		
		# 收集温度点
		all_temps = set()
		for prop_data in self.calculation_results.values():
			for model_key in self.current_parameters.get("selected_models", []):
				if model_key in prop_data:
					all_temps.update(prop_data[model_key]["temperatures"])
		
		# 数据行
		for temp_k in sorted(all_temps):
			col = 0
			worksheet.write(row, col, temp_k, data_format)
			col += 1
			
			for model_key in self.current_parameters.get("selected_models", []):
				# 获取数据
				act_darken = self._get_value_at_temperature(model_key, "activity_darken", temp_k)
				act_elliott = self._get_value_at_temperature(model_key, "activity", temp_k)
				gamma_darken = self._get_value_at_temperature(model_key, "activity_coefficient_darken", temp_k)
				gamma_elliott = self._get_value_at_temperature(model_key, "activity_coefficient", temp_k)
				
				# 写入数据，使用不同颜色格式 - 调整顺序为Darken在前
				worksheet.write(row, col, act_darken if not math.isnan(act_darken) else "N/A", darken_format)
				col += 1
				worksheet.write(row, col, gamma_darken if not math.isnan(gamma_darken) else "N/A", darken_format)
				col += 1
				worksheet.write(row, col, act_elliott if not math.isnan(act_elliott) else "N/A", elliott_format)
				col += 1
				worksheet.write(row, col, gamma_elliott if not math.isnan(gamma_elliott) else "N/A", elliott_format)
				col += 1
			
			row += 1
		
		# 自动调整列宽
		worksheet.autofit()
		workbook.close()


if __name__ == "__main__":
	app = QApplication(sys.argv)
	
	# 设置高DPI支持
	if hasattr(Qt, 'AA_EnableHighDpiScaling'):
		QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
	if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
		QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
	
	# 设置应用程序属性
	app.setApplicationName("热力学性质计算器")
	app.setApplicationVersion("1.0")
	app.setOrganizationName("Material Science Lab")
	
	main_window = ActivityTemperatureVariationWidget()
	main_window.show()
	
	sys.exit(app.exec_())