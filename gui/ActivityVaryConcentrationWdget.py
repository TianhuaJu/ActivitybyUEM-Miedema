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


class CompositionVariationWidget(QWidget):
	"""
	用于显示活度和活度系数随组分浓度变化的独立窗口。
	"""
	
	def __init__ (self, parent=None):
		super().__init__(parent)
		
		self.binary_model = BinaryModel()
		self.activity_calc_module = ActivityCoefficient()
		
		# 扩展数据结构以支持修正值
		self.calculation_results = {
			"activity": {},
			"activity_coefficient": {},
			"activity_corrected": {},  # 新增：修正活度
			"activity_coefficient_corrected": {}  # 新增：修正活度系数
		}
		self.current_parameters = {
			"base_matrix": "", "target_element": "", "varying_element": "", "matrix_element": "",
			"phase_state": "", "temperature": 0, "composition_range": [], "selected_models": []
		}
		self.historical_results_html = ""
		self.has_calculated = False
		self.legend_cids = []
		
		self.setWindowTitle("组分浓度变化计算器")
		self.resize(1400, 800)  # 减少窗口高度
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
                    stop:0 #8E44AD, stop:1 #3498DB);
                color: white;
            }
        """)
		
		layout = QHBoxLayout(title_widget)
		layout.setContentsMargins(20, 10, 20, 10)
		
		# 标题
		title_label = QLabel("组分浓度变化计算器")
		title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
		title_label.setStyleSheet("color: white;")
		layout.addWidget(title_label)
		
		layout.addStretch()
		
		# 副标题
		subtitle_label = QLabel("Composition-dependent Activity Calculator")
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
		
		layout.addWidget(self.create_alloy_composition_group())
		layout.addWidget(self.create_calculation_setup_group())
		layout.addWidget(self.create_composition_range_group())
		layout.addWidget(self.create_model_selection_group())
		layout.addStretch(1)  # 弹性空间
		layout.addLayout(self.create_action_buttons())
		
		return left_panel
	
	def create_alloy_composition_group (self):
		"""创建合金组成组"""
		group = ModernGroupBox("🧪 合金基础组成")
		layout = QFormLayout(group)
		layout.setSpacing(10)  # 减少间距
		layout.setContentsMargins(15, 20, 15, 15)  # 减少内边距
		layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
		layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
		
		# 合金组成输入
		comp_layout = QHBoxLayout()
		comp_layout.setSpacing(8)  # 减少间距
		self.matrix_input = ModernLineEdit("例如: Fe0.7Ni0.2C0.1")
		self.matrix_input.setMinimumWidth(200)  # 稍微减少宽度
		comp_layout.addWidget(self.matrix_input)
		
		update_btn = ModernButton("刷新", "secondary")
		update_btn.setFixedWidth(60)  # 稍微减小按钮
		update_btn.clicked.connect(self.update_element_dropdowns)
		comp_layout.addWidget(update_btn)
		
		layout.addRow(QLabel("基础组成:"), comp_layout)
		
		# 基体元素选择
		self.matrix_element_combo = ModernComboBox()
		self.matrix_element_combo.setFixedWidth(280)
		self.matrix_element_combo.setToolTip("基体元素浓度将自动调整以保持总摩尔分数为1")
		layout.addRow(QLabel("基体元素:"), self.matrix_element_combo)
		
		# 相态选择
		self.phase_combo = ModernComboBox()
		self.phase_combo.addItems(["liquid", "solid"])
		self.phase_combo.setFixedWidth(280)
		layout.addRow(QLabel("相态:"), self.phase_combo)
		
		return group
	
	def create_calculation_setup_group (self):
		"""创建计算设置组"""
		group = ModernGroupBox("⚙️ 计算设置")
		layout = QFormLayout(group)
		layout.setSpacing(10)  # 减少间距
		layout.setContentsMargins(15, 20, 15, 15)  # 减少内边距
		layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
		layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
		
		# 变化组分选择
		self.varying_element_combo = ModernComboBox()
		self.varying_element_combo.setFixedWidth(280)
		self.varying_element_combo.setToolTip("选择浓度要变化的组分")
		layout.addRow(QLabel("变化组分:"), self.varying_element_combo)
		
		# 目标组分选择（计算其活度/活度系数）
		self.target_element_combo = ModernComboBox()
		self.target_element_combo.setFixedWidth(280)
		self.target_element_combo.setToolTip("选择要计算活度/活度系数的目标组分")
		layout.addRow(QLabel("目标组分:"), self.target_element_combo)
		
		# 温度设置
		self.temperature_input = ModernSpinBox()
		self.temperature_input.setRange(300, 3000)
		self.temperature_input.setValue(1200)
		self.temperature_input.setSingleStep(50)
		self.temperature_input.setSuffix(" K")
		self.temperature_input.setFixedWidth(280)
		layout.addRow(QLabel("计算温度:"), self.temperature_input)
		
		# 热力学性质选择
		self.property_combo = ModernComboBox()
		self.property_combo.addItems(["活度 (a)", "活度系数 (γ)"])
		self.property_combo.currentIndexChanged.connect(self.update_plot_display_only)
		self.property_combo.setFixedWidth(280)
		layout.addRow(QLabel("热力学性质:"), self.property_combo)
		
		return group
	
	def create_composition_range_group (self):
		"""创建组分浓度范围组"""
		group = ModernGroupBox("📊 组分浓度范围")
		layout = QFormLayout(group)
		layout.setSpacing(10)  # 减少间距
		layout.setContentsMargins(15, 20, 15, 15)  # 减少内边距
		layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
		layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
		layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
		
		# 最小浓度
		self.min_composition = ModernSpinBox()
		self.min_composition.setRange(0.001, 0.990)
		self.min_composition.setValue(0.05)
		self.min_composition.setSingleStep(0.01)
		self.min_composition.setDecimals(3)
		self.min_composition.setFixedWidth(280)
		layout.addRow(QLabel("最小摩尔分数:"), self.min_composition)
		
		# 最大浓度
		self.max_composition = ModernSpinBox()
		self.max_composition.setRange(0.010, 0.999)
		self.max_composition.setValue(0.30)
		self.max_composition.setSingleStep(0.01)
		self.max_composition.setDecimals(3)
		self.max_composition.setFixedWidth(280)
		layout.addRow(QLabel("最大摩尔分数:"), self.max_composition)
		
		# 步长
		self.step_composition = ModernSpinBox()
		self.step_composition.setRange(0.001, 0.100)
		self.step_composition.setValue(0.01)
		self.step_composition.setSingleStep(0.001)
		self.step_composition.setDecimals(3)
		self.step_composition.setFixedWidth(280)
		layout.addRow(QLabel("浓度步长:"), self.step_composition)
		
		return group
	
	def create_model_selection_group (self):
		"""创建模型选择组"""
		group = ModernGroupBox("🔧 外推模型选择")
		layout = QGridLayout(group)
		layout.setSpacing(10)  # 减少间距
		layout.setContentsMargins(15, 20, 15, 15)  # 减少内边距
		
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
		button_layout.setSpacing(12)  # 减少间距
		button_layout.setContentsMargins(0, 15, 0, 15)  # 减少上下边距
		
		calculate_button = ModernButton("🚀 开始计算", "primary")
		calculate_button.clicked.connect(self.run_calculation_thread)
		
		export_button = ModernButton("📤 导出数据", "success")
		export_button.clicked.connect(self.export_data)
		
		# 新增：导出对比数据按钮
		export_comparison_button = ModernButton("📊 导出对比", "secondary")
		export_comparison_button.clicked.connect(self.export_comparison_data)
		export_comparison_button.setToolTip("导出原始值与修正值的对比数据")
		
		button_layout.addWidget(calculate_button)
		button_layout.addWidget(export_button)
		button_layout.addWidget(export_comparison_button)
		
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
		chart_title = QLabel("组分浓度变化图表")
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
		
		self.results_text_right.setStyleSheet("""
            QTextEdit {
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                background-color: #FAFAFA;
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                font-size: 13pt;
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
		
		# 阻止信号
		for combo in [self.matrix_element_combo, self.varying_element_combo, self.target_element_combo]:
			combo.blockSignals(True)
			combo.clear()
		
		if not comp_input:
			for combo in [self.matrix_element_combo, self.varying_element_combo, self.target_element_combo]:
				combo.blockSignals(False)
			return
		
		try:
			# 按照在合金组成中出现的顺序提取元素，保持顺序
			pattern = r"([A-Z][a-z]?)(\d*\.?\d+|\d+)"
			matches = re.findall(pattern, comp_input)
			if not matches:
				for combo in [self.matrix_element_combo, self.varying_element_combo, self.target_element_combo]:
					combo.blockSignals(False)
				return
			
			# 提取元素并保持出现顺序，去重但保持第一次出现的位置
			elements = []
			seen = set()
			for element, _ in matches:
				if element not in seen:
					elements.append(element)
					seen.add(element)
			
			if not elements:
				for combo in [self.matrix_element_combo, self.varying_element_combo, self.target_element_combo]:
					combo.blockSignals(False)
				return
			
			# 填充下拉框
			for combo in [self.matrix_element_combo, self.varying_element_combo, self.target_element_combo]:
				combo.addItems(elements)
			
			# 根据元素数量设置默认选择
			if len(elements) >= 3:
				self.matrix_element_combo.setCurrentIndex(0)  # 第一个元素作为基体
				self.varying_element_combo.setCurrentIndex(1)  # 第二个元素作为变化组分
				self.target_element_combo.setCurrentIndex(2)  # 第三个元素作为目标组分
				default_info = f"默认: 基体={elements[0]}, 变化组分={elements[1]}, 目标组分={elements[2]}"
			elif len(elements) == 2:
				self.matrix_element_combo.setCurrentIndex(0)  # 第一个元素作为基体
				self.varying_element_combo.setCurrentIndex(1)  # 第二个元素作为变化组分
				self.target_element_combo.setCurrentIndex(1)  # 第二个元素也作为目标组分
				default_info = f"默认: 基体={elements[0]}, 变化组分={elements[1]}, 目标组分={elements[1]}"
			elif len(elements) == 1:
				self.matrix_element_combo.setCurrentIndex(0)
				self.varying_element_combo.setCurrentIndex(0)
				self.target_element_combo.setCurrentIndex(0)
				default_info = f"默认: 基体={elements[0]}, 变化组分={elements[0]}, 目标组分={elements[0]}"
			else:
				default_info = ""
			
			status_msg = f"检测到 {len(elements)} 个元素: {', '.join(elements)}"
			if default_info:
				status_msg += f" | {default_info}"
			self.status_bar.set_status(status_msg)
		
		except Exception as e:
			print(f"更新元素下拉列表时出错: {str(e)}")
			self.status_bar.set_status("合金组成解析失败")
		finally:
			for combo in [self.matrix_element_combo, self.varying_element_combo, self.target_element_combo]:
				combo.blockSignals(False)
	
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
		
		# 归一化
		if not (abs(total_fraction - 1.0) < 1e-6):
			if abs(total_fraction - 100.0) < 1e-2:
				for element in comp_dict:
					comp_dict[element] /= 100.0
				total_fraction /= 100.0
			
			if not (abs(total_fraction - 1.0) < 1e-6) and abs(total_fraction) > 1e-9:
				for element in comp_dict:
					comp_dict[element] /= total_fraction
		
		return comp_dict
	
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
		if not self.matrix_input.text().strip():
			QMessageBox.warning(self, "输入缺失", "请输入合金基础组成。")
			return
		
		if not all([self.matrix_element_combo.currentText(),
		            self.varying_element_combo.currentText(),
		            self.target_element_combo.currentText()]):
			QMessageBox.warning(self, "输入缺失", "请选择基体元素、变化组分和目标组分。")
			return
		
		if self.min_composition.value() >= self.max_composition.value():
			QMessageBox.warning(self, "浓度范围错误", "最小摩尔分数必须小于最大摩尔分数。")
			return
		
		if self.step_composition.value() <= 0:
			QMessageBox.warning(self, "浓度步长错误", "浓度步长必须为正数。")
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
		"""计算所有属性 - 包含原始值和修正值"""
		try:
			self.has_calculated = False
			# 扩展数据结构以支持修正值
			self.calculation_results = {
				"activity": {},
				"activity_coefficient": {},
				"activity_corrected": {},  # 新增：修正活度
				"activity_coefficient_corrected": {}  # 新增：修正活度系数
			}
			
			# 获取参数
			base_matrix_str = self.matrix_input.text().strip()
			matrix_elem = self.matrix_element_combo.currentText()
			varying_elem = self.varying_element_combo.currentText()
			target_elem = self.target_element_combo.currentText()
			phase = self.phase_combo.currentText().lower()
			temperature = self.temperature_input.value()
			min_comp = self.min_composition.value()
			max_comp = self.max_composition.value()
			step_comp = self.step_composition.value()
			
			# 解析基础组成
			base_comp_dict = CompositionVariationWidget._parse_composition_static(base_matrix_str)
			if base_comp_dict is None:
				QMessageBox.critical(self, "成分解析失败", f"无法解析: {base_matrix_str}")
				return
			
			# 验证元素存在性
			for elem, name in [(varying_elem, "变化组分"), (target_elem, "目标组分"), (matrix_elem, "基体元素")]:
				if elem not in base_comp_dict:
					QMessageBox.critical(self, "输入错误", f"{name} '{elem}' 不在合金组成中。")
					return
			
			# 生成组分序列
			compositions = np.arange(min_comp, max_comp + step_comp / 2, step_comp)
			if len(compositions) == 0:
				QMessageBox.warning(self, "组分范围错误", "无有效组分点。")
				return
			
			# 更新当前参数
			self.current_parameters = {
				"base_matrix": base_matrix_str,
				"target_element": target_elem,
				"varying_element": varying_elem,
				"matrix_element": matrix_elem,
				"phase_state": phase,
				"temperature": temperature,
				"composition_range": [min_comp, max_comp, step_comp],
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
			
			# 创建结果HTML - 增强对比显示
			current_timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
			new_results_html = f"<hr><b>🕐 计算时间: {current_timestamp}</b><br>"
			new_results_html += f"<b>📋 计算参数:</b><br>"
			new_results_html += f"基础组成: {base_matrix_str}<br>"
			new_results_html += f"变化组分: {varying_elem}, 目标组分: {target_elem}, 基体元素: {matrix_elem}<br>"
			new_results_html += f"温度: {temperature}K, 相态: {phase}<br>"
			new_results_html += f"浓度范围: {min_comp:.3f} - {max_comp:.3f} (步长 {step_comp:.3f})<br>"
			new_results_html += f"外推模型: {', '.join(self.current_parameters['selected_models'])}<hr>"
			
			# 设置进度条
			total_calcs = len(selected_models_to_run) * len(compositions)
			if hasattr(self, 'progress_dialog'):
				self.progress_dialog.setRange(0, total_calcs)
			calcs_done = 0
			
			# 执行计算
			for model_key_geo, geo_model_function in selected_models_to_run:
				# 初始化数据数组
				current_activities, current_coefficients = [], []
				current_activities_corrected, current_coefficients_corrected = [], []
				composition_values = []
				
				new_results_html += f"<br><b>⚙️ 外推模型: {model_key_geo}</b><br>"
				# 更新表头，增加修正值和差异列
				new_results_html += f"<font face='Courier New' color='#2C3E50'><b>X_{varying_elem}   | Act(原始) | ActCoef(原始) | Act(修正) | ActCoef(修正) | Δa(%)  | Δγ(%)</b></font><br>"
				new_results_html += f"<font face='Courier New'>---------|-----------|-------------|-----------|-------------|--------|------</font><br>"
				
				for comp_val in compositions:
					if hasattr(self, 'progress_dialog') and self.progress_dialog.wasCanceled():
						new_results_html += "<font color='red'>❌ 计算已取消</font><br>"
						break
					
					# 构建当前组成
					current_comp = self.build_composition_at_point(base_comp_dict, varying_elem, matrix_elem, comp_val)
					if current_comp is None:
						current_activities.append(float('nan'))
						current_coefficients.append(float('nan'))
						current_activities_corrected.append(float('nan'))
						current_coefficients_corrected.append(float('nan'))
						new_results_html += f"<font face='Courier New'>{comp_val:<9.3f}|   N/A     |     N/A     |   N/A     |     N/A     |  N/A   |  N/A</font><br>"
						calcs_done += 1
						continue
					
					try:
						# 计算原始活度系数
						ln_gamma = self.activity_calc_module.activity_coefficient_elliott(current_comp, target_elem,
						                                                                  matrix_elem, temperature,
						                                                                  phase, geo_model_function,
						                                                                  model_key_geo,verify_gd= True,gd_verbose=True)
						gamma_val = math.exp(ln_gamma) if not (math.isnan(ln_gamma) or math.isinf(ln_gamma)) else float(
							'nan')
						
						# 计算修正活度系数
						ln_gamma_corrc = self.activity_calc_module.activity_coefficient_corrected(
								current_comp, target_elem, matrix_elem, temperature, phase, geo_model_function,
								model_key_geo,verify_gd= True,gd_verbose=True)
						gamma_corr_val = math.exp(ln_gamma_corrc) if not (
									math.isnan(ln_gamma_corrc) or math.isinf(ln_gamma_corrc)) else float('nan')
						
						# 计算活度
						xi_target = current_comp.get(target_elem, 0.0)
						act_val = gamma_val * xi_target if not math.isnan(gamma_val) else float('nan')
						act_val_corrc = gamma_corr_val * xi_target if not math.isnan(gamma_corr_val) else float('nan')
						
						# 计算相对差异百分比
						if not (math.isnan(act_val) or math.isnan(act_val_corrc)) and abs(act_val) > 1e-10:
							delta_act_percent = abs((act_val_corrc - act_val) / act_val) * 100
						else:
							delta_act_percent = float('nan')
						
						if not (math.isnan(gamma_val) or math.isnan(gamma_corr_val)) and abs(gamma_val) > 1e-10:
							delta_gamma_percent = abs((gamma_corr_val - gamma_val) / gamma_val) * 100
						else:
							delta_gamma_percent = float('nan')
						
						# 存储结果
						current_activities.append(act_val)
						current_coefficients.append(gamma_val)
						current_activities_corrected.append(act_val_corrc)
						current_coefficients_corrected.append(gamma_corr_val)
						composition_values.append(comp_val)
						
						# 格式化显示 - 带颜色标识差异大小
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
						
						new_results_html += (
							f"<font face='Courier New'>{comp_val:<9.3f}| {act_val:<10.4f}| {gamma_val:<12.4f}| "
							f"{act_val_corrc:<10.4f}| {gamma_corr_val:<12.4f}| "
							f"<font color='{delta_act_color}'>{delta_act_str}</font>| "
							f"<font color='{delta_gamma_color}'>{delta_gamma_str}</font></font><br>"
						)
					
					except Exception as e_calc:
						print(f"计算错误 (X={comp_val}, 模型={model_key_geo}): {e_calc}")
						current_activities.append(float('nan'))
						current_coefficients.append(float('nan'))
						current_activities_corrected.append(float('nan'))
						current_coefficients_corrected.append(float('nan'))
						composition_values.append(comp_val)
						new_results_html += f"<font face='Courier New'>{comp_val:<9.3f}|   N/A     |     N/A     |   N/A     |     N/A     |  N/A   |  N/A</font><br>"
					
					calcs_done += 1
					if hasattr(self, 'progress_dialog'):
						self.progress_dialog.setValue(calcs_done)
						QApplication.processEvents()
				
				if hasattr(self, 'progress_dialog') and self.progress_dialog.wasCanceled():
					break
				
				# 存储所有结果（原始值和修正值）
				self.calculation_results["activity"][model_key_geo] = {
					"compositions": np.array(composition_values),
					"values": np.array(current_activities)
				}
				self.calculation_results["activity_coefficient"][model_key_geo] = {
					"compositions": np.array(composition_values),
					"values": np.array(current_coefficients)
				}
				self.calculation_results["activity_corrected"][model_key_geo] = {
					"compositions": np.array(composition_values),
					"values": np.array(current_activities_corrected)
				}
				self.calculation_results["activity_coefficient_corrected"][model_key_geo] = {
					"compositions": np.array(composition_values),
					"values": np.array(current_coefficients_corrected)
				}
				
				# 添加统计对比信息
				if len(current_activities) > 0 and len(current_activities_corrected) > 0:
					valid_orig_act = [x for x in current_activities if not math.isnan(x)]
					valid_corr_act = [x for x in current_activities_corrected if not math.isnan(x)]
					valid_orig_gamma = [x for x in current_coefficients if not math.isnan(x)]
					valid_corr_gamma = [x for x in current_coefficients_corrected if not math.isnan(x)]
					
					if valid_orig_act and valid_corr_act and len(valid_orig_act) == len(valid_corr_act):
						avg_diff_act = np.mean(
								[abs((c - o) / o) * 100 for o, c in zip(valid_orig_act, valid_corr_act) if
								 abs(o) > 1e-10])
						max_diff_act = np.max([abs((c - o) / o) * 100 for o, c in zip(valid_orig_act, valid_corr_act) if
						                       abs(o) > 1e-10])
						
						if valid_orig_gamma and valid_corr_gamma and len(valid_orig_gamma) == len(valid_corr_gamma):
							avg_diff_gamma = np.mean(
									[abs((c - o) / o) * 100 for o, c in zip(valid_orig_gamma, valid_corr_gamma) if
									 abs(o) > 1e-10])
							max_diff_gamma = np.max(
									[abs((c - o) / o) * 100 for o, c in zip(valid_orig_gamma, valid_corr_gamma) if
									 abs(o) > 1e-10])
							
							new_results_html += f"<br><b>📊 模型 {model_key_geo} 对比统计:</b><br>"
							new_results_html += f"<font color='#2980B9'>活度 - 平均差异: {avg_diff_act:.2f}%, 最大差异: {max_diff_act:.2f}%</font><br>"
							new_results_html += f"<font color='#8E44AD'>活度系数 - 平均差异: {avg_diff_gamma:.2f}%, 最大差异: {max_diff_gamma:.2f}%</font><br>"
			
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
	
	def normalize_dict (self, comp, exclude_key):
		'''归一化去掉指定组元后的合金组成'''
		filtered_comp = {k: v for k, v in comp.items() if k != exclude_key}
		total = sum(filtered_comp.values())
		normalized_comp = {k: v / total for k, v in filtered_comp.items()}
		return normalized_comp
	
	def build_composition_at_point (self, base_comp, varying_elem, matrix_elem, new_varying_value):
		"""在指定点构建组成"""
		try:
			# 复制基础组成
			comp = base_comp.copy()
			comp = self.normalize_dict(comp, varying_elem)
			# 设置变化组分的新值
			comp[varying_elem] = new_varying_value
			org_matrix_elem_con = comp[matrix_elem]
			new_matrix_elem_con = org_matrix_elem_con - new_varying_value
			if new_matrix_elem_con >= 0:
				comp[matrix_elem] = new_matrix_elem_con
			else:
				return None
			
			return comp
		
		except Exception as e:
			print(f"构建组成时出错: {e}")
			return None
	
	def update_plot_display_only (self):
		"""更新图表显示 - 支持对比模式"""
		if not self.has_calculated:
			self.figure.clear()
			self.canvas.draw()
			return
		
		selected_prop_idx = self.property_combo.currentIndex()
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
		"""绘制属性变化图 - 支持原始值和修正值对比"""
		self.figure.clear()
		ax = self.figure.add_subplot(111)
		
		# 设置图表样式
		ax.set_facecolor('#FAFAFA')
		self.figure.patch.set_facecolor('white')
		
		plot_handles, plot_labels = [], []
		color_cycle = ['#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6', '#1ABC9C']
		marker_cycle = ['o', 's', '^', 'D', 'v', 'P']
		
		# 获取对应的修正值数据
		corrected_property_type = f"{property_type}_corrected"
		corrected_data_dict = self.calculation_results.get(corrected_property_type, {})
		
		# 收集所有组分数据以确定坐标轴范围
		all_comps = []
		for model_key, data in model_data_dict.items():
			comps = data.get("compositions")
			if comps is not None and len(comps) > 0:
				valid_indices = ~np.isnan(comps)
				if np.any(valid_indices):
					all_comps.extend(comps[valid_indices])
		
		if all_comps:
			x_min, x_max = min(all_comps), max(all_comps)
			x_range = x_max - x_min
			x_min_ext = max(0, x_min - 0.05 * x_range)
			x_max_ext = min(1, x_max + 0.05 * x_range)
		else:
			x_min_ext, x_max_ext = 0, 1
		
		# 绘制每个模型的原始值和修正值
		for i, (model_key, data) in enumerate(model_data_dict.items()):
			comps, vals = data.get("compositions"), data.get("values")
			if comps is None or vals is None or len(comps) == 0 or len(vals) == 0:
				continue
			
			# 原始值数据处理
			valid_indices = ~np.isnan(vals) & ~np.isinf(vals)
			comps_orig = comps[valid_indices]
			vals_orig = vals[valid_indices]
			
			if len(comps_orig) > 0:
				# 对数据排序
				sorted_indices = np.argsort(comps_orig)
				comps_orig = comps_orig[sorted_indices]
				vals_orig = vals_orig[sorted_indices]
				
				# 绘制原始值曲线
				base_color = color_cycle[i % len(color_cycle)]
				marker = marker_cycle[i % len(marker_cycle)]
				
				line_orig, = ax.plot(comps_orig, vals_orig,
				                     label=f"{model_key} (原始)",
				                     color=base_color,
				                     marker=marker,
				                     markersize=5,
				                     linewidth=2.5,
				                     alpha=0.9,
				                     linestyle='-',
				                     markeredgewidth=0.5,
				                     markeredgecolor='white')
				
				plot_handles.append(line_orig)
				plot_labels.append(f"{model_key} (原始)")
			
			# 修正值数据处理
			if model_key in corrected_data_dict:
				corr_data = corrected_data_dict[model_key]
				comps_corr, vals_corr = corr_data.get("compositions"), corr_data.get("values")
				
				if comps_corr is not None and vals_corr is not None and len(comps_corr) > 0:
					valid_indices_corr = ~np.isnan(vals_corr) & ~np.isinf(vals_corr)
					comps_corr = comps_corr[valid_indices_corr]
					vals_corr = vals_corr[valid_indices_corr]
					
					if len(comps_corr) > 0:
						# 对数据排序
						sorted_indices_corr = np.argsort(comps_corr)
						comps_corr = comps_corr[sorted_indices_corr]
						vals_corr = vals_corr[sorted_indices_corr]
						
						# 绘制修正值曲线（使用虚线和不同标记）
						line_corr, = ax.plot(comps_corr, vals_corr,
						                     label=f"{model_key} (修正)",
						                     color=base_color,
						                     marker=marker,
						                     markersize=4,
						                     linewidth=2,
						                     alpha=0.7,
						                     linestyle='--',  # 虚线区分
						                     markerfacecolor='white',
						                     markeredgecolor=base_color,
						                     markeredgewidth=1.5)
						
						plot_handles.append(line_corr)
						plot_labels.append(f"{model_key} (修正)")
		
		# 设置标签和标题
		varying_elem = self.current_parameters.get("varying_element", "?")
		target_elem = self.current_parameters.get("target_element", "?")
		prop_name_cn = "活度" if property_type == "activity" else "活度系数"
		y_label = f"{prop_name_cn} ($a_{{{target_elem}}}$)" if property_type == "activity" else f"{prop_name_cn} ($\\gamma_{{{target_elem}}}$)"
		
		title = (
			f"{self.current_parameters.get('base_matrix', 'N/A')} 中 {target_elem} 的 {prop_name_cn} vs. {varying_elem} 浓度\n"
			f"温度: {self.current_parameters.get('temperature', 'N/A')}K, "
			f"相态: {self.current_parameters.get('phase_state', 'N/A')} (原始值 vs 修正值对比)")
		
		ax.set_xlabel(f"{varying_elem} 摩尔分数", fontsize=12, fontweight='bold')
		ax.set_ylabel(y_label, fontsize=12, fontweight='bold')
		ax.set_title(title, fontsize=11, fontweight='bold', pad=20, color='#2C3E50')
		
		# 网格设置
		ax.grid(True, linestyle='--', alpha=0.3, color='#BDC3C7', linewidth=0.5)
		ax.tick_params(axis='both', which='major', labelsize=10)
		
		# 添加理想线
		if all_comps:
			if property_type == "activity_coefficient":
				# 活度系数的理想线：γ = 1
				ax.axhline(y=1.0, color='#34495E', linestyle='-.', linewidth=2, alpha=0.6,
				           label="理想溶液 ($\\gamma=1$)", zorder=0)
			
			elif property_type == "activity":
				# 活度的理想线
				base_comp_dict = CompositionVariationWidget._parse_composition_static(
						self.current_parameters.get("base_matrix", ""))
				matrix_elem = self.current_parameters.get("matrix_element", "")
				
				if base_comp_dict and matrix_elem:
					ideal_compositions = []
					ideal_activities = []
					
					for comp_val in sorted(all_comps):
						current_comp = self.build_composition_at_point(base_comp_dict, varying_elem, matrix_elem,
						                                               comp_val)
						if current_comp:
							target_fraction = current_comp.get(target_elem, 0.0)
							ideal_compositions.append(comp_val)
							ideal_activities.append(target_fraction)
					
					if ideal_compositions and ideal_activities:
						ax.plot(ideal_compositions, ideal_activities,
						        color='#34495E', linestyle='-.', linewidth=2, alpha=0.6,
						        label=f"理想溶液 ($a_{{{target_elem}}} = X_{{{target_elem}}}$)",
						        zorder=0)
		
		# 图例设置 - 分组显示
		if plot_handles:
			# 创建自定义图例，将原始值和修正值分组
			legend = ax.legend(loc='best', fontsize=9, frameon=True, fancybox=True, shadow=True,
			                   framealpha=0.95, facecolor='white', edgecolor='#CCCCCC',
			                   ncol=2 if len(plot_handles) > 6 else 1)  # 如果项目太多就分两列
			legend.get_frame().set_linewidth(0.5)
		else:
			ax.text(0.5, 0.5, "无有效数据", ha='center', va='center', transform=ax.transAxes,
			        fontsize=14, color='#E74C3C', fontweight='bold')
		
		# 调整布局
		self.figure.tight_layout(rect=[0, 0, 1, 0.96])
		
		# 绘制
		self.canvas.draw()
	
	def export_data (self):
		"""导出数据"""
		if not self.has_calculated or not any(self.calculation_results.values()):
			QMessageBox.warning(self, "导出错误", "请先计算数据。")
			return
		
		file_path, _ = QFileDialog.getSaveFileName(
				self, "导出数据", f"组分浓度变化计算结果_{QDateTime.currentDateTime().toString('yyyyMMdd_hhmmss')}",
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
	
	def export_comparison_data (self):
		"""导出原始值与修正值对比数据"""
		if not self.has_calculated or not any(self.calculation_results.values()):
			QMessageBox.warning(self, "导出错误", "请先计算数据。")
			return
		
		file_path, _ = QFileDialog.getSaveFileName(
				self, "导出对比数据",
				f"活度对比数据_{QDateTime.currentDateTime().toString('yyyyMMdd_hhmmss')}",
				"Excel 文件 (*.xlsx);;CSV 文件 (*.csv)"
		)
		
		if not file_path:
			return
		
		try:
			self.status_bar.set_status("正在导出对比数据...")
			if file_path.lower().endswith('.xlsx'):
				self._export_comparison_to_excel(file_path)
			else:
				self._export_comparison_to_csv(file_path if file_path.lower().endswith('.csv') else file_path + ".csv")
			
			QMessageBox.information(self, "导出成功", f"对比数据已成功导出至:\n{file_path}")
			self.status_bar.set_status("✅ 对比数据导出完成")
		
		except Exception as e:
			QMessageBox.critical(self, "导出失败", f"导出时发生错误:\n{e}")
			self.status_bar.set_status("❌ 对比数据导出失败")
	
	def _export_comparison_to_csv (self, file_path):
		"""导出对比数据到CSV"""
		import csv
		
		varying_elem = self.current_parameters.get("varying_element", "X")
		target_elem = self.current_parameters.get("target_element", "Y")
		
		with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
			writer = csv.writer(csvfile)
			
			# 写入标题
			writer.writerow(['# 活度/活度系数原始值与修正值对比数据'])
			writer.writerow(['# 计算参数'])
			for key, val in self.current_parameters.items():
				value_str = ", ".join(val) if isinstance(val, list) and key == "selected_models" else str(val)
				writer.writerow([f"# {key}", value_str])
			writer.writerow([])
			
			# 写入表头
			header = [f'{varying_elem} 摩尔分数']
			for model_key in self.current_parameters.get("selected_models", []):
				header.extend([
					f'{model_key}-活度(原始)', f'{model_key}-活度(修正)', f'{model_key}-活度差异(%)',
					f'{model_key}-活度系数(原始)', f'{model_key}-活度系数(修正)', f'{model_key}-活度系数差异(%)'
				])
			writer.writerow(header)
			
			# 收集所有组分点
			all_comps = set()
			for prop_data in self.calculation_results.values():
				for model_key in self.current_parameters.get("selected_models", []):
					if model_key in prop_data:
						all_comps.update(prop_data[model_key]["compositions"])
			
			# 写入数据
			for comp_val in sorted(all_comps):
				row = [comp_val]
				for model_key in self.current_parameters.get("selected_models", []):
					# 获取各种数据
					act_orig = self._get_value_at_composition(model_key, "activity", comp_val)
					act_corr = self._get_value_at_composition(model_key, "activity_corrected", comp_val)
					gamma_orig = self._get_value_at_composition(model_key, "activity_coefficient", comp_val)
					gamma_corr = self._get_value_at_composition(model_key, "activity_coefficient_corrected", comp_val)
					
					# 计算差异
					act_diff = abs((act_corr - act_orig) / act_orig) * 100 if not math.isnan(act_orig) and abs(
						act_orig) > 1e-10 and not math.isnan(act_corr) else float('nan')
					gamma_diff = abs((gamma_corr - gamma_orig) / gamma_orig) * 100 if not math.isnan(
						gamma_orig) and abs(gamma_orig) > 1e-10 and not math.isnan(gamma_corr) else float('nan')
					
					row.extend([
						f"{act_orig:.6f}" if not math.isnan(act_orig) else "N/A",
						f"{act_corr:.6f}" if not math.isnan(act_corr) else "N/A",
						f"{act_diff:.2f}" if not math.isnan(act_diff) else "N/A",
						f"{gamma_orig:.6f}" if not math.isnan(gamma_orig) else "N/A",
						f"{gamma_corr:.6f}" if not math.isnan(gamma_corr) else "N/A",
						f"{gamma_diff:.2f}" if not math.isnan(gamma_diff) else "N/A"
					])
				
				writer.writerow(row)
	
	def _export_comparison_to_excel (self, file_path):
		"""导出对比数据到Excel"""
		try:
			import xlsxwriter
		except ImportError:
			QMessageBox.warning(self, "依赖缺失", "导出Excel需要安装 xlsxwriter 库。\n请使用: pip install xlsxwriter")
			return
		
		workbook = xlsxwriter.Workbook(file_path)
		worksheet = workbook.add_worksheet('对比数据')
		
		# 定义格式
		title_format = workbook.add_format({
			'bold': True, 'font_size': 16, 'align': 'center',
			'bg_color': '#8E44AD', 'font_color': 'white'
		})
		header_format = workbook.add_format({
			'bold': True, 'align': 'center', 'bg_color': '#3498DB',
			'font_color': 'white', 'border': 1, 'text_wrap': True
		})
		data_format = workbook.add_format({
			'num_format': '0.000000', 'align': 'center', 'border': 1
		})
		diff_small_format = workbook.add_format({
			'num_format': '0.00', 'align': 'center', 'border': 1,
			'bg_color': '#D5EFDF', 'font_color': '#27AE60'  # 绿色：差异小
		})
		diff_medium_format = workbook.add_format({
			'num_format': '0.00', 'align': 'center', 'border': 1,
			'bg_color': '#FCF3E3', 'font_color': '#F39C12'  # 橙色：差异中等
		})
		diff_large_format = workbook.add_format({
			'num_format': '0.00', 'align': 'center', 'border': 1,
			'bg_color': '#F5D6D6', 'font_color': '#E74C3C'  # 红色：差异大
		})
		
		row = 0
		varying_elem = self.current_parameters.get("varying_element", "X")
		
		# 标题
		worksheet.merge_range(row, 0, row, 12, '活度/活度系数原始值与修正值对比数据', title_format)
		row += 2
		
		# 参数信息
		param_format = workbook.add_format({'bold': True, 'bg_color': '#ECF0F1', 'border': 1})
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
		worksheet.write(row, col, f'{varying_elem} 摩尔分数', header_format)
		col += 1
		
		for model_key in self.current_parameters.get("selected_models", []):
			worksheet.write(row, col, f'{model_key}\n活度(原始)', header_format)
			col += 1
			worksheet.write(row, col, f'{model_key}\n活度(修正)', header_format)
			col += 1
			worksheet.write(row, col, f'{model_key}\n活度差异(%)', header_format)
			col += 1
			worksheet.write(row, col, f'{model_key}\n活度系数(原始)', header_format)
			col += 1
			worksheet.write(row, col, f'{model_key}\n活度系数(修正)', header_format)
			col += 1
			worksheet.write(row, col, f'{model_key}\n活度系数差异(%)', header_format)
			col += 1
		
		row += 1
		
		# 收集组分点
		all_comps = set()
		for prop_data in self.calculation_results.values():
			for model_key in self.current_parameters.get("selected_models", []):
				if model_key in prop_data:
					all_comps.update(prop_data[model_key]["compositions"])
		
		# 数据行
		for comp_val in sorted(all_comps):
			col = 0
			worksheet.write(row, col, comp_val, data_format)
			col += 1
			
			for model_key in self.current_parameters.get("selected_models", []):
				# 获取数据
				act_orig = self._get_value_at_composition(model_key, "activity", comp_val)
				act_corr = self._get_value_at_composition(model_key, "activity_corrected", comp_val)
				gamma_orig = self._get_value_at_composition(model_key, "activity_coefficient", comp_val)
				gamma_corr = self._get_value_at_composition(model_key, "activity_coefficient_corrected", comp_val)
				
				# 计算差异
				act_diff = abs((act_corr - act_orig) / act_orig) * 100 if not math.isnan(act_orig) and abs(
					act_orig) > 1e-10 and not math.isnan(act_corr) else float('nan')
				gamma_diff = abs((gamma_corr - gamma_orig) / gamma_orig) * 100 if not math.isnan(gamma_orig) and abs(
					gamma_orig) > 1e-10 and not math.isnan(gamma_corr) else float('nan')
				
				# 写入数据
				worksheet.write(row, col, act_orig if not math.isnan(act_orig) else "N/A", data_format)
				col += 1
				worksheet.write(row, col, act_corr if not math.isnan(act_corr) else "N/A", data_format)
				col += 1
				
				# 活度差异（带颜色标识）
				if not math.isnan(act_diff):
					if act_diff > 5:
						worksheet.write(row, col, act_diff, diff_large_format)
					elif act_diff > 1:
						worksheet.write(row, col, act_diff, diff_medium_format)
					else:
						worksheet.write(row, col, act_diff, diff_small_format)
				else:
					worksheet.write(row, col, "N/A", data_format)
				col += 1
				
				worksheet.write(row, col, gamma_orig if not math.isnan(gamma_orig) else "N/A", data_format)
				col += 1
				worksheet.write(row, col, gamma_corr if not math.isnan(gamma_corr) else "N/A", data_format)
				col += 1
				
				# 活度系数差异（带颜色标识）
				if not math.isnan(gamma_diff):
					if gamma_diff > 5:
						worksheet.write(row, col, gamma_diff, diff_large_format)
					elif gamma_diff > 1:
						worksheet.write(row, col, gamma_diff, diff_medium_format)
					else:
						worksheet.write(row, col, gamma_diff, diff_small_format)
				else:
					worksheet.write(row, col, "N/A", data_format)
				col += 1
			
			row += 1
		
		# 自动调整列宽
		worksheet.autofit()
		workbook.close()
	
	def _get_value_at_composition (self, model_key, property_type, composition):
		"""获取指定组分点的属性值"""
		if property_type not in self.calculation_results or model_key not in self.calculation_results[property_type]:
			return float('nan')
		
		data = self.calculation_results[property_type][model_key]
		comps = data["compositions"]
		values = data["values"]
		
		# 查找最接近的组分点
		idx = np.argmin(np.abs(comps - composition))
		if abs(comps[idx] - composition) < 1e-6:  # 容差检查
			return values[idx]
		return float('nan')
	
	def _export_to_csv_internal (self, file_path):
		"""导出到CSV文件"""
		import csv
		
		varying_elem = self.current_parameters.get("varying_element", "X")
		
		# 收集所有组分点
		all_comps = set()
		sel_models = self.current_parameters.get("selected_models", [])
		
		if not sel_models:
			return
		
		for prop_data in self.calculation_results.values():
			for model_key in sel_models:
				if model_key in prop_data and "compositions" in prop_data[model_key]:
					all_comps.update(prop_data[model_key]["compositions"])
		
		sorted_comps = sorted(list(all_comps))
		if not sorted_comps:
			QMessageBox.warning(self, "无数据", "无组分点可导出。")
			return
		
		with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
			writer = csv.writer(csvfile)
			
			# 写入参数信息
			writer.writerow(['# 组分浓度变化计算结果'])
			writer.writerow(['# 计算参数'])
			for key, val in self.current_parameters.items():
				value_str = ", ".join(val) if isinstance(val, list) and key == "selected_models" else str(val)
				writer.writerow([f"# {key}", value_str])
			writer.writerow([])
			
			# 写入数据表头
			header = [f'{varying_elem} 摩尔分数']
			for mk in sel_models:
				header.extend([f'{mk}-活度(a)', f'{mk}-活度系数(γ)'])
			writer.writerow(header)
			
			# 写入数据
			for comp_val in sorted_comps:
				row = [comp_val]
				for model_key in sel_models:
					act_v, coef_v = "N/A", "N/A"
					
					# 活度数据
					if model_key in self.calculation_results["activity"]:
						comps_list_act = list(self.calculation_results["activity"][model_key]["compositions"])
						if comp_val in comps_list_act:
							idx_act = comps_list_act.index(comp_val)
							val_act = self.calculation_results["activity"][model_key]["values"][idx_act]
							if not (math.isnan(val_act) or math.isinf(val_act)):
								act_v = f"{val_act:.6f}"
					
					# 活度系数数据
					if model_key in self.calculation_results["activity_coefficient"]:
						comps_list_coef = list(
								self.calculation_results["activity_coefficient"][model_key]["compositions"])
						if comp_val in comps_list_coef:
							idx_coef = comps_list_coef.index(comp_val)
							val_coef = self.calculation_results["activity_coefficient"][model_key]["values"][idx_coef]
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
			'bg_color': '#8E44AD', 'font_color': 'white'
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
		
		row = 0
		varying_elem = self.current_parameters.get("varying_element", "X")
		
		# 标题
		worksheet.write(row, 0, '组分浓度变化计算结果', title_format)
		worksheet.merge_range(row, 0, row, 5, '组分浓度变化计算结果', title_format)
		row += 2
		
		# 参数信息
		worksheet.write(row, 0, '计算参数', param_format)
		row += 1
		
		param_names = {
			'base_matrix': '基础组成',
			'target_element': '目标组分',
			'varying_element': '变化组分',
			'matrix_element': '基体元素',
			'phase_state': '相态',
			'temperature': '计算温度',
			'composition_range': '浓度范围',
			'selected_models': '选择的模型'
		}
		
		for k, v in self.current_parameters.items():
			param_name = param_names.get(k, k)
			value_str = ", ".join(v) if isinstance(v, list) and k == "selected_models" else str(v)
			worksheet.write(row, 0, param_name, param_format)
			worksheet.write(row, 1, value_str)
			row += 1
		
		row += 1
		
		# 数据表格
		all_comps = set()
		sel_models = self.current_parameters.get("selected_models", [])
		
		if not sel_models:
			workbook.close()
			return
		
		for pd in self.calculation_results.values():
			for mk in sel_models:
				if mk in pd and "compositions" in pd[mk]:
					all_comps.update(pd[mk]["compositions"])
		
		sorted_comps = sorted(list(all_comps))
		if not sorted_comps:
			QMessageBox.warning(self, "无数据", "无组分点可导出。")
			workbook.close()
			return
		
		# 表头
		col = 0
		worksheet.write(row, col, f'{varying_elem} 摩尔分数', header_format)
		col += 1
		
		for mk in sel_models:
			worksheet.write(row, col, f'{mk}-活度(a)', header_format)
			col += 1
			worksheet.write(row, col, f'{mk}-活度系数(γ)', header_format)
			col += 1
		
		row += 1
		
		# 数据行
		for comp_val in sorted_comps:
			col = 0
			worksheet.write(row, col, comp_val, data_format)
			col += 1
			
			for mk in sel_models:
				# 活度
				act_v = np.nan
				if mk in self.calculation_results["activity"]:
					comps_list_act = list(self.calculation_results["activity"][mk]["compositions"])
					if comp_val in comps_list_act:
						idx_act = comps_list_act.index(comp_val)
						act_v = self.calculation_results["activity"][mk]["values"][idx_act]
				
				# 活度系数
				coef_v = np.nan
				if mk in self.calculation_results["activity_coefficient"]:
					comps_list_coef = list(self.calculation_results["activity_coefficient"][mk]["compositions"])
					if comp_val in comps_list_coef:
						idx_coef = comps_list_coef.index(comp_val)
						coef_v = self.calculation_results["activity_coefficient"][mk]["values"][idx_coef]
				
				# 写入数据
				worksheet.write(row, col, act_v if not (math.isnan(act_v) or math.isinf(act_v)) else "N/A", data_format)
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
	app.setApplicationName("组分浓度变化计算器")
	app.setApplicationVersion("1.0")
	app.setOrganizationName("Material Science Lab")
	
	main_window = CompositionVariationWidget()
	main_window.show()
	
	sys.exit(app.exec_())