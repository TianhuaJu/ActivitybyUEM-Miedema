import sys
import math
import re
import traceback
import numpy as np
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QComboBox, QPushButton, QSplitter,
                             QFrame, QGroupBox, QTextEdit, QMessageBox, QSizePolicy,
                             QDoubleSpinBox, QCheckBox, QFileDialog, QFormLayout,
                             QProgressDialog, QScrollArea, QTabWidget, QSpacerItem)
from PyQt5.QtCore import Qt, QDateTime, QPropertyAnimation, QEasingCurve, QRect, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPixmap, QPainter, QLinearGradient

from models.extrapolation_models import BinaryModel
from calculations.activity_calculator import ActivityCoefficient


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
		
		# 🆕 修改数据结构，支持原始值和修正值
		self.calculation_results = {
			"activity": {},  # 原始Elliott模型的活度
			"activity_coefficient": {},  # 原始Elliott模型的活度系数
			"activity_corrected": {},  # 修正模型的活度
			"activity_coefficient_corrected": {}  # 修正模型的活度系数
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
		
		# 直接使用VBoxLayout，不使用滚动区域
		layout = QVBoxLayout(left_panel)
		layout.setSpacing(12)  # 减少组件间距
		layout.setContentsMargins(0, 0, 10, 0)
		
		layout.addWidget(self.create_alloy_and_calc_params_group())
		layout.addWidget(self.create_temperature_range_group())
		layout.addWidget(self.create_model_selection_group())
		layout.addStretch(1)  # 弹性空间
		layout.addLayout(self.create_action_buttons())
		
		return left_panel
	
	def adjust_font_size (self,button):
		# 获取按钮的宽度
		button_width = button.width()
		
		# 根据按钮的宽度动态调整字体大小，假设字体大小是宽度的1/5
		font_size = max(10, int(button_width / 2))  # 设置最小字体大小为 10
		
		# 设置字体
		font = QFont("Microsoft YaHei", font_size, QFont.Bold)
		button.setFont(font)
	def create_alloy_and_calc_params_group (self):
		"""创建合金与计算参数组"""
		group = ModernGroupBox("🔬 合金与计算参数")
		layout = QFormLayout(group)
		layout.setSpacing(10)  # 减少间距
		layout.setContentsMargins(15, 20, 15, 15)  # 减少内边距
		layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
		layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
		
		# 合金组成输入
		comp_layout = QHBoxLayout()
		comp_layout.setSpacing(8)  # 减少间距
		self.matrix_input = ModernLineEdit("例如: Fe0.7Ni0.3")
		self.matrix_input.setMinimumWidth(200)  # 稍微减少宽度
		comp_layout.addWidget(self.matrix_input)
		
		update_btn = ModernButton("刷新", "secondary")
		update_btn.setFixedWidth(60)  # 稍微减小按钮
		#update_btn.setMinimumWidth(60)
		#self.adjust_font_size(update_btn)
		update_btn.adjustSize()
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
		layout.setSpacing(10)  # 减少间距
		layout.setContentsMargins(15, 20, 15, 15)  # 减少内边距
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
		
		# 🆕 添加对比选项
		layout.addWidget(QFrame(), 2, 0, 1, 2)  # 分隔线
		
		# 对比选项复选框
		self.comparison_checkbox = ModernCheckBox("📊 显示Elliott vs 修正模型对比")
		self.comparison_checkbox.setStyleSheet("""
	        QCheckBox {
	            font-weight: bold;
	            color: #2E5BBA;
	            padding: 5px;
	        }
	        QCheckBox::indicator {
	            width: 18px;
	            height: 18px;
	        }
	        QCheckBox::indicator:unchecked {
	            border: 2px solid #BDC3C7;
	            background-color: white;
	            border-radius: 3px;
	        }
	        QCheckBox::indicator:checked {
	            border: 2px solid #2E5BBA;
	            background-color: #2E5BBA;
	            border-radius: 3px;
	        }
	        QCheckBox::indicator:checked::before {
	            content: "✓";
	            color: white;
	            font-weight: bold;
	            position: absolute;
	            left: 3px;
	            top: 1px;
	        }
	    """)
		self.comparison_checkbox.setToolTip("勾选后将在图表和结果中同时显示Elliott原始模型和修正模型的对比")
		self.comparison_checkbox.stateChanged.connect(self.on_comparison_option_changed)
		layout.addWidget(self.comparison_checkbox, 3, 0, 1, 2)
		
		return group
	
	def create_action_buttons (self):
		"""创建操作按钮"""
		button_layout = QHBoxLayout()
		button_layout.setSpacing(12)  # 减少间距
		button_layout.setContentsMargins(0, 15, 0, 15)  # 减少上下边距
		
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
		refresh_results_btn.setMaximumWidth(120)
		refresh_results_btn.clicked.connect(self.refresh_results_display)
		button_layout.addWidget(refresh_results_btn)
		
		clear_results_btn = ModernButton("🗑️ 清除历史", "secondary")
		clear_results_btn.setMaximumWidth(120)
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
		comp_dict = {}
		pattern = r"([A-Z][a-z]?)(\d*\.?\d+|\d+)"
		matches = re.findall(pattern, alloy_str)
		if not matches:
			return None
		
		try:
			for element, amount_str in matches:
				amount = float(amount_str) if amount_str else 1.0
				if amount < 0:
					return None
				comp_dict[element] = comp_dict.get(element, 0) + amount
		except ValueError:
			return None
		
		if not comp_dict:
			return None
		
		total_fraction = sum(comp_dict.values())
		if abs(total_fraction) < 1e-9:
			return None
		
		if not (abs(total_fraction - 1.0) < 1e-6):
			if abs(total_fraction - 100.0) < 1e-2:
				for element in comp_dict:
					comp_dict[element] /= 100.0
				total_fraction /= 100.0
				if abs(total_fraction) < 1e-9:
					return None
			
			if not (abs(total_fraction - 1.0) < 1e-6) and abs(total_fraction) > 1e-9:
				for element in comp_dict:
					comp_dict[element] /= total_fraction
			elif abs(total_fraction) < 1e-9:
				return None
		
		return comp_dict
	
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
		"""计算所有属性"""
		try:
			self.has_calculated = False
			# 🆕 重置所有数据结构
			self.calculation_results = {
				"activity": {},
				"activity_coefficient": {},
				"activity_corrected": {},
				"activity_coefficient_corrected": {}
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
			
			# 🆕 检查是否启用对比
			is_comparison_enabled = self.comparison_checkbox.isChecked()
			
			# 创建结果HTML
			current_timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
			new_results_html = f"<hr><b>🕐 计算时间: {current_timestamp}</b><br>"
			new_results_html += f"<b>📋 计算参数:</b><br>"
			new_results_html += f"合金: {base_matrix_str}, 溶剂: {solvent_elem}, 溶质: {solute_elem}<br>"
			new_results_html += f"相态: {phase}, 温度: {min_t}K - {max_t}K (步长 {step_t}K)<br>"
			new_results_html += f"外推模型: {', '.join(self.current_parameters['selected_models'])}<br>"
			
			# 🆕 显示对比选项状态
			comparison_status = "是" if is_comparison_enabled else "否"
			new_results_html += f"Elliott vs 修正模型对比: {comparison_status}<hr>"
			
			# 设置进度条
			total_calcs = len(selected_models_to_run) * len(temperatures) * (2 if is_comparison_enabled else 1)
			if hasattr(self, 'progress_dialog'):
				self.progress_dialog.setRange(0, total_calcs)
			calcs_done = 0
			
			# 执行计算
			for model_key_geo, geo_model_function in selected_models_to_run:
				# 🆕 为每个模型存储原始值和修正值
				current_activities = []
				current_coefficients = []
				current_activities_corrected = []
				current_coefficients_corrected = []
				
				new_results_html += f"<br><b>⚙️ 外推模型: {model_key_geo}</b><br>"
				
				if is_comparison_enabled:
					# 🆕 对比模式的表头
					new_results_html += "<font face='Courier New'>Temp(K)  | Elliott-Act | Elliott-γ  | Corrected-Act | Corrected-γ</font><br>"
					new_results_html += "<font face='Courier New'>---------|------------|------------|---------------|-------------</font><br>"
				else:
					# 原始模式的表头
					new_results_html += "<font face='Courier New'>Temp(K)  | Act(a)   | ActCoef(γ)</font><br>"
					new_results_html += "<font face='Courier New'>---------|----------|-----------</font><br>"
				
				for temp_k in temperatures:
					if hasattr(self, 'progress_dialog') and self.progress_dialog.wasCanceled():
						new_results_html += "❌ 计算已取消<br>"
						break
					
					comp_for_calc = comp_dict_main.copy()
					xi_solute = comp_for_calc.get(solute_elem, 0.0)
					
					try:
						# 🆕 计算原始Elliott模型
						ln_gamma = self.activity_calc_module.activity_coefficient_elliott(
								comp_for_calc, solute_elem, solvent_elem, temp_k, phase,
								geo_model_function, model_key_geo
						)
						gamma_val = math.exp(ln_gamma) if not (math.isnan(ln_gamma) or math.isinf(ln_gamma)) else float(
								'nan')
						act_val = gamma_val * xi_solute if not math.isnan(gamma_val) else float('nan')
						
						# 🆕 计算修正模型
						ln_gamma_corr = self.activity_calc_module.activity_coefficient_corrected(
								comp_for_calc, solute_elem, solvent_elem, temp_k, phase,
								geo_model_function, model_key_geo
						)
						gamma_corr_val = math.exp(ln_gamma_corr) if not (
								math.isnan(ln_gamma_corr) or math.isinf(ln_gamma_corr)) else float('nan')
						act_corr_val = gamma_corr_val * xi_solute if not math.isnan(gamma_corr_val) else float('nan')
						
						# 存储数据
						current_activities.append(act_val)
						current_coefficients.append(gamma_val)
						current_activities_corrected.append(act_corr_val)
						current_coefficients_corrected.append(gamma_corr_val)
						
						# 🆕 根据对比选项显示结果
						if is_comparison_enabled:
							new_results_html += f"<font face='Courier New'>{temp_k:<9.1f}| {act_val:<11.4f}| {gamma_val:<11.4f}| {act_corr_val:<14.4f}| {gamma_corr_val:<12.4f}</font><br>"
						else:
							new_results_html += f"<font face='Courier New'>{temp_k:<9.1f}| {act_val:<9.4f}| {gamma_val:<10.4f}</font><br>"
					
					except Exception as e_calc:
						print(f"计算错误 (T={temp_k}K, 模型={model_key_geo}): {e_calc}")
						current_activities.append(float('nan'))
						current_coefficients.append(float('nan'))
						current_activities_corrected.append(float('nan'))
						current_coefficients_corrected.append(float('nan'))
						
						if is_comparison_enabled:
							new_results_html += f"<font face='Courier New'>{temp_k:<9.1f}|     N/A    |     N/A    |      N/A      |     N/A     </font><br>"
						else:
							new_results_html += f"<font face='Courier New'>{temp_k:<9.1f}|   N/A    |     N/A    </font><br>"
					
					calcs_done += 1
					if hasattr(self, 'progress_dialog'):
						self.progress_dialog.setValue(calcs_done)
						QApplication.processEvents()
				
				if hasattr(self, 'progress_dialog') and self.progress_dialog.wasCanceled():
					break
				
				# 🆕 存储所有结果
				self.calculation_results["activity"][model_key_geo] = {
					"temperatures": temperatures.copy(),
					"values": np.array(current_activities)
				}
				self.calculation_results["activity_coefficient"][model_key_geo] = {
					"temperatures": temperatures.copy(),
					"values": np.array(current_coefficients)
				}
				self.calculation_results["activity_corrected"][model_key_geo] = {
					"temperatures": temperatures.copy(),
					"values": np.array(current_activities_corrected)
				}
				self.calculation_results["activity_coefficient_corrected"][model_key_geo] = {
					"temperatures": temperatures.copy(),
					"values": np.array(current_coefficients_corrected)
				}
			
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
	
	def update_plot_display_only (self):
		"""仅更新图表显示"""
		if not self.has_calculated:
			self.figure.clear()
			self.canvas.draw()
			return
		
		selected_prop_idx = self.property_combo.currentIndex()
		is_comparison_enabled = self.comparison_checkbox.isChecked()
		
		if is_comparison_enabled:
			# 🆕 对比模式：同时显示原始和修正值
			prop_to_plot = "activity" if selected_prop_idx == 0 else "activity_coefficient"
			original_data = self.calculation_results.get(prop_to_plot, {})
			corrected_data = self.calculation_results.get(f"{prop_to_plot}_corrected", {})
			
			self.plot_comparison_variation(original_data, corrected_data, prop_to_plot)
		else:
			# 原始模式：只显示Elliott原始值
			prop_to_plot = "activity" if selected_prop_idx == 0 else "activity_coefficient"
			data_for_plotting = self.calculation_results.get(prop_to_plot, {})
			
			if not data_for_plotting:
				self.figure.clear()
				ax = self.figure.add_subplot(111)
				ax.text(0.5, 0.5, "无数据可显示", ha='center', va='center', transform=ax.transAxes,
				        fontsize=14, color='#666666')
				ax.set_facecolor('#F8F9FA')
				self.canvas.draw()
				return
			
			self.plot_property_variation(data_for_plotting, prop_to_plot)
	
	def plot_property_variation (self, model_data_dict, property_type):
		"""绘制属性变化图"""
		self.figure.clear()
		ax = self.figure.add_subplot(111)
		
		# 设置图表样式
		ax.set_facecolor('#FAFAFA')
		self.figure.patch.set_facecolor('white')
		
		plot_handles, plot_labels = [], []
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
		         f"相态: {self.current_parameters.get('phase_state', 'N/A')}")
		
		ax.set_xlabel("温度 (K)", fontsize=12, fontweight='bold')
		ax.set_ylabel(y_label, fontsize=12, fontweight='bold')
		ax.set_title(title, fontsize=13, fontweight='bold', pad=20, color='#2C3E50')
		
		# 网格设置
		ax.grid(True, linestyle='--', alpha=0.3, color='#BDC3C7')
		ax.tick_params(axis='both', which='major', labelsize=10)
		
		# 添加参考线
		if plot_handles and min_T_overall != float('inf'):
			ref_temps = np.linspace(min_T_overall, max_T_overall, 50)
			
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
	
	def on_comparison_option_changed (self):
		"""处理对比选项变化"""
		if self.has_calculated:
			# 如果已经有计算结果，重新绘制图表
			self.update_plot_display_only()
			# 重新显示结果
			self.refresh_results_display()
		
		if self.comparison_checkbox.isChecked():
			self.status_bar.set_status("已启用Elliott vs 修正模型对比显示")
		else:
			self.status_bar.set_status("已关闭对比显示")
	
	def plot_comparison_variation (self, original_data, corrected_data, property_type):
		"""绘制对比图表：Elliott原始 vs 修正模型"""
		self.figure.clear()
		ax = self.figure.add_subplot(111)
		
		# 设置图表样式
		ax.set_facecolor('#FAFAFA')
		self.figure.patch.set_facecolor('white')
		
		plot_handles, plot_labels = [], []
		color_cycle = ['#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6', '#1ABC9C', '#E67E22', '#34495E']
		marker_cycle = ['o', 's', '^', 'D', 'v', 'P', '*', 'X']
		line_styles = ['-', '--']  # 实线表示原始，虚线表示修正
		min_T_overall, max_T_overall = float('inf'), float('-inf')
		
		plot_index = 0
		
		# 🆕 绘制对比曲线
		for i, model_key in enumerate(original_data.keys()):
			if model_key not in corrected_data:
				continue
			
			# 原始Elliott数据
			orig_data = original_data[model_key]
			orig_temps, orig_vals = orig_data.get("temperatures"), orig_data.get("values")
			
			# 修正模型数据
			corr_data = corrected_data[model_key]
			corr_temps, corr_vals = corr_data.get("temperatures"), corr_data.get("values")
			
			if (orig_temps is None or orig_vals is None or len(orig_temps) == 0 or
					corr_temps is None or corr_vals is None or len(corr_temps) == 0):
				continue
			
			# 处理原始数据
			orig_valid_indices = ~np.isnan(orig_vals) & ~np.isinf(orig_vals)
			orig_temps_p, orig_vals_p = orig_temps[orig_valid_indices], orig_vals[orig_valid_indices]
			
			# 处理修正数据
			corr_valid_indices = ~np.isnan(corr_vals) & ~np.isinf(corr_vals)
			corr_temps_p, corr_vals_p = corr_temps[corr_valid_indices], corr_vals[corr_valid_indices]
			
			if len(orig_temps_p) == 0 and len(corr_temps_p) == 0:
				continue
			
			# 更新温度范围
			if len(orig_temps_p) > 0:
				min_T_overall = min(min_T_overall, orig_temps_p.min())
				max_T_overall = max(max_T_overall, orig_temps_p.max())
			if len(corr_temps_p) > 0:
				min_T_overall = min(min_T_overall, corr_temps_p.min())
				max_T_overall = max(max_T_overall, corr_temps_p.max())
			
			color = color_cycle[i % len(color_cycle)]
			marker = marker_cycle[i % len(marker_cycle)]
			
			# 绘制原始Elliott曲线
			if len(orig_temps_p) > 0:
				line_orig, = ax.plot(orig_temps_p, orig_vals_p,
				                     label=f'{model_key} (Elliott)',
				                     color=color,
				                     marker=marker,
				                     markersize=6,
				                     linewidth=2.5,
				                     linestyle='-',
				                     alpha=0.8)
				plot_handles.append(line_orig)
				plot_labels.append(f'{model_key} (Elliott)')
			
			# 绘制修正模型曲线
			if len(corr_temps_p) > 0:
				line_corr, = ax.plot(corr_temps_p, corr_vals_p,
				                     label=f'{model_key} (修正)',
				                     color=color,
				                     marker=marker,
				                     markersize=6,
				                     linewidth=2.5,
				                     linestyle='--',
				                     alpha=0.8)
				plot_handles.append(line_corr)
				plot_labels.append(f'{model_key} (修正)')
		
		# 设置标签和标题
		solute = self.current_parameters.get("solute", "?")
		prop_name_cn = "活度" if property_type == "activity" else "活度系数"
		y_label = f"{prop_name_cn} ($a_{{{solute}}}$)" if property_type == "activity" else f"{prop_name_cn} ($\\gamma_{{{solute}}}$)"
		
		title = (f"{self.current_parameters.get('base_matrix', 'N/A')} 中 {solute} 的 {prop_name_cn} vs. 温度\n"
		         f"Elliott模型 vs 修正模型对比 | 溶剂: {self.current_parameters.get('solvent', 'N/A')}, "
		         f"相态: {self.current_parameters.get('phase_state', 'N/A')}")
		
		ax.set_xlabel("温度 (K)", fontsize=12, fontweight='bold')
		ax.set_ylabel(y_label, fontsize=12, fontweight='bold')
		ax.set_title(title, fontsize=13, fontweight='bold', pad=20, color='#2C3E50')
		
		# 网格设置
		ax.grid(True, linestyle='--', alpha=0.3, color='#BDC3C7')
		ax.tick_params(axis='both', which='major', labelsize=10)
		
		# 添加参考线
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
		
		# 🆕 特殊的对比图例设置
		if plot_handles:
			# 创建自定义图例
			import matplotlib.lines as mlines
			legend_elements = []
			
			# 添加数据线条
			for handle, label in zip(plot_handles, plot_labels):
				legend_elements.append(handle)
			
			# 添加图例说明
			legend_elements.append(mlines.Line2D([], [], color='black', linestyle='-', label='Elliott原始'))
			legend_elements.append(mlines.Line2D([], [], color='black', linestyle='--', label='修正模型'))
			
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
	
	def _export_to_csv_internal (self, file_path):
		"""导出到CSV文件"""
		import csv
		
		all_temps = set()
		sel_models = self.current_parameters.get("selected_models", [])
		is_comparison_enabled = self.comparison_checkbox.isChecked()
		
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
			writer.writerow(['# 热力学性质计算结果'])
			writer.writerow(['# 计算参数'])
			for key, val in self.current_parameters.items():
				value_str = ", ".join(val) if isinstance(val, list) and key == "selected_models" else str(val)
				writer.writerow([f"# {key}", value_str])
			writer.writerow([f"# 对比模式", "是" if is_comparison_enabled else "否"])
			writer.writerow([])
			
			# 🆕 根据对比模式写入不同的表头
			if is_comparison_enabled:
				header = ['温度 (K)']
				for mk in sel_models:
					header.extend([
						f'{mk}-Elliott-活度(a)', f'{mk}-Elliott-活度系数(γ)',
						f'{mk}-修正-活度(a)', f'{mk}-修正-活度系数(γ)'
					])
			else:
				header = ['温度 (K)']
				for mk in sel_models:
					header.extend([f'{mk}-活度(a)', f'{mk}-活度系数(γ)'])
			
			writer.writerow(header)
			
			# 写入数据
			for temp_k in sorted_temps:
				row = [temp_k]
				for model_key in sel_models:
					if is_comparison_enabled:
						# 🆕 对比模式：输出4列数据
						# Elliott原始活度
						act_elliott = "N/A"
						if model_key in self.calculation_results["activity"]:
							temps_list = list(self.calculation_results["activity"][model_key]["temperatures"])
							if temp_k in temps_list:
								idx = temps_list.index(temp_k)
								val = self.calculation_results["activity"][model_key]["values"][idx]
								if not (math.isnan(val) or math.isinf(val)):
									act_elliott = f"{val:.6f}"
						
						# Elliott原始活度系数
						coef_elliott = "N/A"
						if model_key in self.calculation_results["activity_coefficient"]:
							temps_list = list(
									self.calculation_results["activity_coefficient"][model_key]["temperatures"])
							if temp_k in temps_list:
								idx = temps_list.index(temp_k)
								val = self.calculation_results["activity_coefficient"][model_key]["values"][idx]
								if not (math.isnan(val) or math.isinf(val)):
									coef_elliott = f"{val:.6f}"
						
						# 修正模型活度
						act_corrected = "N/A"
						if model_key in self.calculation_results["activity_corrected"]:
							temps_list = list(self.calculation_results["activity_corrected"][model_key]["temperatures"])
							if temp_k in temps_list:
								idx = temps_list.index(temp_k)
								val = self.calculation_results["activity_corrected"][model_key]["values"][idx]
								if not (math.isnan(val) or math.isinf(val)):
									act_corrected = f"{val:.6f}"
						
						# 修正模型活度系数
						coef_corrected = "N/A"
						if model_key in self.calculation_results["activity_coefficient_corrected"]:
							temps_list = list(
									self.calculation_results["activity_coefficient_corrected"][model_key][
										"temperatures"])
							if temp_k in temps_list:
								idx = temps_list.index(temp_k)
								val = self.calculation_results["activity_coefficient_corrected"][model_key]["values"][
									idx]
								if not (math.isnan(val) or math.isinf(val)):
									coef_corrected = f"{val:.6f}"
						
						row.extend([act_elliott, coef_elliott, act_corrected, coef_corrected])
					else:
						# 原始模式：只输出Elliott原始值
						act_v, coef_v = "N/A", "N/A"
						
						# 活度数据
						if model_key in self.calculation_results["activity"]:
							temps_list_act = list(self.calculation_results["activity"][model_key]["temperatures"])
							if temp_k in temps_list_act:
								idx_act = temps_list_act.index(temp_k)
								val_act = self.calculation_results["activity"][model_key]["values"][idx_act]
								if not (math.isnan(val_act) or math.isinf(val_act)):
									act_v = f"{val_act:.6f}"
						
						# 活度系数数据
						if model_key in self.calculation_results["activity_coefficient"]:
							temps_list_coef = list(
									self.calculation_results["activity_coefficient"][model_key]["temperatures"])
							if temp_k in temps_list_coef:
								idx_coef = temps_list_coef.index(temp_k)
								val_coef = self.calculation_results["activity_coefficient"][model_key]["values"][
									idx_coef]
								if not (math.isnan(val_coef) or math.isinf(val_coef)):
									coef_v = f"{val_coef:.6f}"
						
						row.extend([act_v, coef_v])
				
				writer.writerow(row)
	
	def _export_to_excel_internal (self, file_path):
		"""导出到Excel文件"""
		try:
			import xlsxwriter
		except ImportError:
			QMessageBox.warning(self, "依赖缺失", "导出Excel需要安装 xlsxwriter 库。\n请使用: pip install xlsxwriter")
			return
		
		workbook = xlsxwriter.Workbook(file_path)
		worksheet = workbook.add_worksheet('计算结果')
		
		# 定义格式
		title_format = workbook.add_format({
			'bold': True, 'font_size': 14, 'align': 'left',
			'bg_color': '#2C3E50', 'font_color': 'white'
		})
		header_format = workbook.add_format({
			'bold': True, 'align': 'center', 'bg_color': '#3498DB',
			'font_color': 'white', 'border': 1
		})
		data_format = workbook.add_format({
			'num_format': '0.000000', 'align': 'center', 'border': 1
		})
		param_format = workbook.add_format({
			'bold': True, 'bg_color': '#ECF0F1', 'border': 1
		})
		
		# 🆕 对比模式的特殊格式
		elliott_format = workbook.add_format({
			'num_format': '0.000000', 'align': 'center', 'border': 1,
			'bg_color': '#E8F4FD'  # 浅蓝色背景
		})
		corrected_format = workbook.add_format({
			'num_format': '0.000000', 'align': 'center', 'border': 1,
			'bg_color': '#E8F6F3'  # 浅绿色背景
		})
		
		row = 0
		is_comparison_enabled = self.comparison_checkbox.isChecked()
		
		# 标题
		title_text = '热力学性质计算结果 (对比模式)' if is_comparison_enabled else '热力学性质计算结果'
		worksheet.write(row, 0, title_text, title_format)
		worksheet.merge_range(row, 0, row, 8 if is_comparison_enabled else 5, title_text, title_format)
		row += 2
		
		# 参数信息
		worksheet.write(row, 0, '计算参数', param_format)
		row += 1
		
		for k, v in self.current_parameters.items():
			param_name = {
				'base_matrix': '合金组成',
				'solute': '溶质元素',
				'solvent': '溶剂元素',
				'phase_state': '相态',
				'order_degree': '合金类型',
				'temp_range': '温度范围',
				'selected_models': '选择的模型'
			}.get(k, k)
			
			value_str = ", ".join(v) if isinstance(v, list) and k == "selected_models" else str(v)
			worksheet.write(row, 0, param_name, param_format)
			worksheet.write(row, 1, value_str)
			row += 1
		
		# 🆕 添加对比模式说明
		worksheet.write(row, 0, '对比模式', param_format)
		worksheet.write(row, 1, "是" if is_comparison_enabled else "否")
		row += 2
		
		# 数据表格
		all_temps = set()
		sel_models = self.current_parameters.get("selected_models", [])
		
		if not sel_models:
			workbook.close()
			return
		
		for pd in self.calculation_results.values():
			for mk in sel_models:
				if mk in pd and "temperatures" in pd[mk]:
					all_temps.update(pd[mk]["temperatures"])
		
		sorted_temps = sorted(list(all_temps))
		if not sorted_temps:
			QMessageBox.warning(self, "无数据", "无温度点可导出。")
			workbook.close()
			return
		
		# 🆕 根据对比模式设置不同的表头
		col = 0
		worksheet.write(row, col, '温度 (K)', header_format)
		col += 1
		
		if is_comparison_enabled:
			for mk in sel_models:
				worksheet.write(row, col, f'{mk}-Elliott-活度', header_format)
				col += 1
				worksheet.write(row, col, f'{mk}-Elliott-γ', header_format)
				col += 1
				worksheet.write(row, col, f'{mk}-修正-活度', header_format)
				col += 1
				worksheet.write(row, col, f'{mk}-修正-γ', header_format)
				col += 1
		else:
			for mk in sel_models:
				worksheet.write(row, col, f'{mk}-活度(a)', header_format)
				col += 1
				worksheet.write(row, col, f'{mk}-活度系数(γ)', header_format)
				col += 1
		
		row += 1
		
		# 数据行
		for tk in sorted_temps:
			col = 0
			worksheet.write(row, col, tk, data_format)
			col += 1
			
			for mk in sel_models:
				if is_comparison_enabled:
					# 🆕 对比模式：4列数据，使用不同颜色
					# Elliott原始活度
					act_elliott = np.nan
					if mk in self.calculation_results["activity"]:
						temps_list = list(self.calculation_results["activity"][mk]["temperatures"])
						if tk in temps_list:
							idx = temps_list.index(tk)
							act_elliott = self.calculation_results["activity"][mk]["values"][idx]
					
					# Elliott原始活度系数
					coef_elliott = np.nan
					if mk in self.calculation_results["activity_coefficient"]:
						temps_list = list(self.calculation_results["activity_coefficient"][mk]["temperatures"])
						if tk in temps_list:
							idx = temps_list.index(tk)
							coef_elliott = self.calculation_results["activity_coefficient"][mk]["values"][idx]
					
					# 修正活度
					act_corrected = np.nan
					if mk in self.calculation_results["activity_corrected"]:
						temps_list = list(self.calculation_results["activity_corrected"][mk]["temperatures"])
						if tk in temps_list:
							idx = temps_list.index(tk)
							act_corrected = self.calculation_results["activity_corrected"][mk]["values"][idx]
					
					# 修正活度系数
					coef_corrected = np.nan
					if mk in self.calculation_results["activity_coefficient_corrected"]:
						temps_list = list(
								self.calculation_results["activity_coefficient_corrected"][mk]["temperatures"])
						if tk in temps_list:
							idx = temps_list.index(tk)
							coef_corrected = self.calculation_results["activity_coefficient_corrected"][mk]["values"][
								idx]
					
					# 写入数据，使用不同颜色格式
					worksheet.write(row, col,
					                act_elliott if not (math.isnan(act_elliott) or math.isinf(act_elliott)) else "N/A",
					                elliott_format)
					col += 1
					worksheet.write(row, col,
					                coef_elliott if not (
								                math.isnan(coef_elliott) or math.isinf(coef_elliott)) else "N/A",
					                elliott_format)
					col += 1
					worksheet.write(row, col, act_corrected if not (
							math.isnan(act_corrected) or math.isinf(act_corrected)) else "N/A", corrected_format)
					col += 1
					worksheet.write(row, col, coef_corrected if not (
							math.isnan(coef_corrected) or math.isinf(coef_corrected)) else "N/A", corrected_format)
					col += 1
				else:
					# 原始模式：只有Elliott原始值
					act_v = np.nan
					if mk in self.calculation_results["activity"]:
						temps_list_act = list(self.calculation_results["activity"][mk]["temperatures"])
						if tk in temps_list_act:
							idx_act = temps_list_act.index(tk)
							act_v = self.calculation_results["activity"][mk]["values"][idx_act]
					
					coef_v = np.nan
					if mk in self.calculation_results["activity_coefficient"]:
						temps_list_coef = list(self.calculation_results["activity_coefficient"][mk]["temperatures"])
						if tk in temps_list_coef:
							idx_coef = temps_list_coef.index(tk)
							coef_v = self.calculation_results["activity_coefficient"][mk]["values"][idx_coef]
					
					worksheet.write(row, col, act_v if not (math.isnan(act_v) or math.isinf(act_v)) else "N/A",
					                data_format)
					col += 1
					worksheet.write(row, col, coef_v if not (math.isnan(coef_v) or math.isinf(coef_v)) else "N/A",
					                data_format)
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