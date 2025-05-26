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
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
matplotlib.rcParams['font.size'] = 12  # 增加图表字体大小

# 使用Matplotlib的数学文本渲染（不依赖LaTeX）
matplotlib.rcParams['text.usetex'] = False
matplotlib.rcParams['mathtext.default'] = 'regular'
# Import PyQt5 modules
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QLabel, QLineEdit, QComboBox, QPushButton,
                             QTabWidget, QSplitter, QFrame, QGroupBox, QTextEdit, QMessageBox,
                             QStatusBar, QDoubleSpinBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QGuiApplication

# 导入计算模块

from models.extrapolation_models import BinaryModel
from models.activity_interaction_parameters import TernaryMelts
from calculations.activity_calculator import ActivityCoefficient
from core.element import Element
from core.database_handler import Melt


class MplCanvas(FigureCanvas):
	"""Matplotlib画布类"""
	axes: Axes
	
	def __init__ (self, parent=None, width=7, height=6, dpi=100):
		self.fig = Figure(figsize=(width, height), dpi=dpi)
		self.axes = self.fig.add_subplot(111)
		super(MplCanvas, self).__init__(self.fig)


class AlloyActProGUIp(QMainWindow):
	def __init__ (self):
		super().__init__()
		self.setWindowTitle("AlloyAct Pro - 合金热力学计算器")
		self.resize(1400, 900)
		self.setMinimumSize(1000, 900)
		
		# 新版PyQt5中将窗口居中
		qr = self.frameGeometry()
		cp = QGuiApplication.primaryScreen().availableGeometry().center()
		qr.moveCenter(cp)
		self.move(qr.topLeft())
		
		# 创建计算实例
		self.binary_model = BinaryModel()
		self.activity_coefficient = ActivityCoefficient()
		
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
		
		
		# 创建选项卡控件
		self.tabs = QTabWidget()
		self.main_layout.addWidget(self.tabs)
		
		# 设置选项卡样式
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
		
		# 创建各个选项卡
		self.create_activity_tab()
		self.create_activity_coef_tab()
		self.create_interaction_tab()
		self.create_second_order_tab()
		
		# 创建新增的两个模块选项卡
		self.create_activity_vs_conc_tab()  # 活度-浓度关系选项卡
		self.create_coef_vs_conc_tab()  # 活度系数-浓度关系选项卡
		
		# 创建状态栏
		self.status_bar = QStatusBar()
		self.setStatusBar(self.status_bar)
		self.update_status("就绪 - 请选择计算类型并输入参数")
		
		# 设置选项卡切换事件
		self.tabs.currentChanged.connect(self.on_tab_changed)
		# 设置所有选项卡的字体
		tab_font = QFont("Microsoft YaHei UI", 16,QFont.Bold)  # 设置更大的字体
		for i in range(self.tabs.count()):
			self.tabs.setTabText(i, self.tabs.tabText(i))  # 这会触发文本重新设置
			self.tabs.tabBar().setFont(tab_font)
		
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
		title_label = QLabel("合金热力学计算器")
		title_label.setFont(title_font)
		title_label.setStyleSheet("color: #2c3e50;")
		
		# 版本
		version_font = QFont("Microsoft YaHei UI", 12)
		version_label = QLabel("版本 1.0")
		version_label.setFont(version_font)
		version_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
		
		title_layout.addWidget(title_label)
		title_layout.addStretch()
		title_layout.addWidget(version_label)
		
		self.main_layout.addLayout(title_layout)
	
	def update_status (self, message):
		"""更新状态栏消息"""
		self.status_bar.showMessage(message)
	
	def on_tab_changed (self, index):
		"""选项卡切换事件处理"""
		tab_text = self.tabs.tabText(index)
		self.update_status(f"就绪 - {tab_text}")
	
	def create_activity_tab (self):
		"""创建活度计算选项卡"""
		activity_widget = QWidget()
		activity_layout = QVBoxLayout(activity_widget)
		
		# 创建分割器
		splitter = QSplitter(Qt.Horizontal)
		activity_layout.addWidget(splitter)
		
		# 左侧输入面板
		left_widget = QWidget()
		left_layout = QVBoxLayout(left_widget)
		
		# 创建输入字段分组
		input_group = QGroupBox("输入参数")
		input_layout = QGridLayout(input_group)
		
		# 合金成分
		input_layout.addWidget(QLabel("合金成分:"), 0, 0,Qt.AlignRight)
		self.activity_alloy = QLineEdit("Fe0.70C0.03Si0.27")
		input_layout.addWidget(self.activity_alloy, 0, 1)
		self.activity_alloy.setPlaceholderText("e.g.:Fe0.7C0.03Si0.27")
		
		# 基体元素
		input_layout.addWidget(QLabel("基体元素:"), 1, 0,Qt.AlignRight)
		self.activity_solvent = QLineEdit("Fe")
		input_layout.addWidget(self.activity_solvent, 1, 1)
		self.activity_solvent.setPlaceholderText('e.g.:Fe')
		
		# 溶质元素
		input_layout.addWidget(QLabel("溶质元素(i):"), 2, 0,Qt.AlignRight)
		self.activity_solute = QLineEdit("C")
		input_layout.addWidget(self.activity_solute, 2, 1)
		self.activity_solute.setPlaceholderText('e.g.:C')
		
		# 温度
		input_layout.addWidget(QLabel("温度 (K):"), 3, 0,Qt.AlignRight)
		self.activity_temp = QLineEdit("1873.0")
		input_layout.addWidget(self.activity_temp, 3, 1)
		self.activity_temp.setPlaceholderText('e.g.:1873.0')
		
		# 状态
		input_layout.addWidget(QLabel("状态:"), 4, 0,Qt.AlignRight)
		self.activity_state = QComboBox()
		self.activity_state.addItems(["liquid", "solid"])
		input_layout.addWidget(self.activity_state, 4, 1)
		
		# 外推模型
		input_layout.addWidget(QLabel("外推模型:"), 5, 0,Qt.AlignRight)
		self.activity_model = QComboBox()
		self.activity_model.addItems(["UEM1", "UEM2", "GSM", "Muggianu"])
		input_layout.addWidget(self.activity_model, 5, 1)
		
		# 添加分隔线
		line = QFrame()
		line.setFrameShape(QFrame.HLine)
		line.setFrameShadow(QFrame.Sunken)
		input_layout.addWidget(line, 6, 0, 1, 3)
		
		# 计算按钮
		btn_layout = QHBoxLayout()
		calculate_btn = QPushButton("计算活度")
		calculate_btn.clicked.connect(self.calculate_activity)
		btn_layout.addWidget(calculate_btn)
		
		clear_btn = QPushButton("清除结果")
		clear_btn.clicked.connect(self.clear_activity_result)
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
		
		self.activity_result = QTextEdit()
		self.activity_result.setReadOnly(True)
		result_layout.addWidget(self.activity_result)
		
		# 图表区域
		chart_group = QGroupBox("数据可视化")
		chart_layout = QVBoxLayout(chart_group)
		
		self.activity_canvas = MplCanvas(self, width=5, height=4, dpi=100)
		chart_layout.addWidget(self.activity_canvas)
		
		# 添加结果分组和图表分组到右侧布局
		right_layout.addWidget(result_group, 1)
		right_layout.addWidget(chart_group, 1)
		
		# 添加左右面板到分割器
		splitter.addWidget(left_widget)
		splitter.addWidget(right_widget)
		splitter.setSizes([300, 700])  # 设置初始分割比例
		
		# 初始绘制空图表
		self.init_activity_chart()
		
		# 添加到选项卡
		self.tabs.addTab(activity_widget, "活度计算")
	
	def create_activity_coef_tab (self):
		"""创建活度系数计算选项卡"""
		coef_widget = QWidget()
		coef_layout = QVBoxLayout(coef_widget)
		
		# 创建分割器
		splitter = QSplitter(Qt.Horizontal)
		coef_layout.addWidget(splitter)
		
		# 左侧输入面板
		left_widget = QWidget()
		left_layout = QVBoxLayout(left_widget)
		
		# 创建输入字段分组
		input_group = QGroupBox("输入参数")
		input_layout = QGridLayout(input_group)
		
		# 合金成分
		input_layout.addWidget(QLabel("合金成分:"), 0, 0,Qt.AlignRight)
		self.coef_alloy = QLineEdit("Fe0.8Ni0.1Al0.1")
		input_layout.addWidget(self.coef_alloy, 0, 1)
		self.coef_alloy.setPlaceholderText('e.g.:Fe0.8Ni0.1Al0.1')
		
		# 基体元素
		input_layout.addWidget(QLabel("基体元素:"), 1, 0,Qt.AlignRight)
		self.coef_solvent = QLineEdit("Fe")
		input_layout.addWidget(self.coef_solvent, 1, 1)
		self.coef_solvent.setPlaceholderText('e.g.:Fe')
		
		# 溶质元素
		input_layout.addWidget(QLabel("溶质元素:"), 2, 0,Qt.AlignRight)
		self.coef_solute = QLineEdit("Ni")
		input_layout.addWidget(self.coef_solute, 2, 1)
		self.coef_solute.setPlaceholderText('e.g.:Ni')
		
		# 温度
		input_layout.addWidget(QLabel("温度 (K):"), 3, 0,Qt.AlignRight)
		self.coef_temp = QLineEdit("1600.0")
		input_layout.addWidget(self.coef_temp, 3, 1)
		self.coef_temp.setPlaceholderText('e.g.:1873.0')
		
		# 状态
		input_layout.addWidget(QLabel("状态:"), 4, 0,Qt.AlignRight)
		self.coef_state = QComboBox()
		self.coef_state.addItems(["liquid", "solid"])
		input_layout.addWidget(self.coef_state, 4, 1)
		
		# 外推模型
		input_layout.addWidget(QLabel("外推模型:"), 5, 0,Qt.AlignRight)
		self.coef_model = QComboBox()
		self.coef_model.addItems(["UEM1", "UEM2", "GSM", "Muggianu"])
		input_layout.addWidget(self.coef_model, 5, 1)
		
		# 添加分隔线
		line = QFrame()
		line.setFrameShape(QFrame.HLine)
		line.setFrameShadow(QFrame.Sunken)
		input_layout.addWidget(line, 6, 0, 1, 3)
		
		# 计算按钮
		btn_layout = QHBoxLayout()
		calculate_btn = QPushButton("计算活度系数")
		calculate_btn.clicked.connect(self.calculate_activity_coef)
		btn_layout.addWidget(calculate_btn)
		
		clear_btn = QPushButton("清除结果")
		clear_btn.clicked.connect(self.clear_coef_result)
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
		
		self.coef_result = QTextEdit()
		self.coef_result.setReadOnly(True)
		result_layout.addWidget(self.coef_result)
		
		# 图表区域
		chart_group = QGroupBox("数据可视化")
		chart_layout = QVBoxLayout(chart_group)
		
		self.coef_canvas = MplCanvas(self, width=5, height=4, dpi=100)
		chart_layout.addWidget(self.coef_canvas)
		
		# 添加结果分组和图表分组到右侧布局
		right_layout.addWidget(result_group, 1)
		right_layout.addWidget(chart_group, 1)
		
		# 添加左右面板到分割器
		splitter.addWidget(left_widget)
		splitter.addWidget(right_widget)
		splitter.setSizes([300, 700])  # 设置初始分割比例
		
		# 初始绘制空图表
		self.init_coef_chart()
		
		# 添加到选项卡
		self.tabs.addTab(coef_widget, "活度系数计算")
	
	def create_interaction_tab (self):
		"""创建相互作用系数计算选项卡"""
		interact_widget = QWidget()
		interact_layout = QVBoxLayout(interact_widget)
		
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
		left_widget = QWidget()
		left_layout = QVBoxLayout(left_widget)
		
		# 创建输入字段分组
		input_group = QGroupBox("输入参数")
		input_layout = QGridLayout(input_group)
		
		# 基体元素
		input_layout.addWidget(QLabel("基体元素:"), 0, 0,Qt.AlignRight)
		self.second_solvent = QLineEdit("Al")
		input_layout.addWidget(self.second_solvent, 0, 1)
		self.second_solvent.setPlaceholderText('e.g.:Al')
		
		# 溶质 i
		input_layout.addWidget(QLabel("溶质 i:"), 1, 0,Qt.AlignRight)
		self.second_solute_i = QLineEdit("Si")
		input_layout.addWidget(self.second_solute_i, 1, 1)
		self.second_solute_i.setPlaceholderText('e.g.:Si')
		
		# 溶质 j
		input_layout.addWidget(QLabel("溶质 j:"), 2, 0,Qt.AlignRight)
		self.second_solute_j = QLineEdit("Cu")
		input_layout.addWidget(self.second_solute_j, 2, 1)
		self.second_solute_j.setPlaceholderText('e.g.:Cu')
		
		# 溶质 k
		input_layout.addWidget(QLabel("溶质 k:"), 3, 0,Qt.AlignRight)
		self.second_solute_k = QLineEdit("Mn")
		input_layout.addWidget(self.second_solute_k, 3, 1)
		self.second_solute_k.setPlaceholderText('e.g.:Mn')
		
		# 温度
		input_layout.addWidget(QLabel("温度 (K):"), 4, 0,Qt.AlignRight)
		self.second_temp = QLineEdit("805.0")
		input_layout.addWidget(self.second_temp, 4, 1)
		self.second_temp.setPlaceholderText('e.g.:805.0')
		
		# 状态
		input_layout.addWidget(QLabel("状态:"), 5, 0,Qt.AlignRight)
		self.second_state = QComboBox()
		self.second_state.addItems(["liquid", "solid"])
		input_layout.addWidget(self.second_state, 5, 1)
		
		# 外推模型
		input_layout.addWidget(QLabel("外推模型:"), 6, 0,Qt.AlignRight)
		self.second_model = QComboBox()
		self.second_model.addItems(["UEM1", "UEM2", "GSM", "Muggianu"])
		input_layout.addWidget(self.second_model, 6, 1)
		
		# 添加分隔线
		line = QFrame()
		line.setFrameShape(QFrame.HLine)
		line.setFrameShadow(QFrame.Sunken)
		input_layout.addWidget(line, 7, 0, 1, 3)
		
		# 计算按钮
		btn_layout = QHBoxLayout()
		calculate_btn = QPushButton("计算二阶系数")
		calculate_btn.clicked.connect(self.calculate_second_order)
		btn_layout.addWidget(calculate_btn)
		
		clear_btn = QPushButton("清除结果")
		clear_btn.clicked.connect(self.clear_second_result)
		btn_layout.addWidget(clear_btn)
		
		input_layout.addLayout(btn_layout, 8, 0, 1, 3)
		
		# 添加输入分组到左侧布局
		left_layout.addWidget(input_group)
		left_layout.addStretch()
		
		# 右侧结果面板
		right_widget = QWidget()
		right_layout = QVBoxLayout(right_widget)
		
		# 结果文本区域
		result_group = QGroupBox("计算结果")
		result_layout = QVBoxLayout(result_group)
		
		self.second_result = QTextEdit()
		self.second_result.setReadOnly(True)
		result_layout.addWidget(self.second_result)
		
		# 图表区域
		chart_group = QGroupBox("数据可视化")
		chart_layout = QVBoxLayout(chart_group)
		
		self.second_canvas = MplCanvas(self, width=5, height=4, dpi=100)
		chart_layout.addWidget(self.second_canvas)
		
		# 添加结果分组和图表分组到右侧布局
		right_layout.addWidget(result_group, 1)
		right_layout.addWidget(chart_group, 1)
		
		# 添加左右面板到分割器
		splitter.addWidget(left_widget)
		splitter.addWidget(right_widget)
		splitter.setSizes([300, 700])  # 设置初始分割比例
		
		# 初始绘制空图表
		self.init_second_chart()
		
		# 添加到选项卡
		self.tabs.addTab(second_widget, "二阶相互作用系数")
	
	def create_activity_vs_conc_tab (self):
		"""创建活度-浓度关系选项卡"""
		act_conc_widget = QWidget()
		act_conc_layout = QVBoxLayout(act_conc_widget)
		
		# 创建分割器
		splitter = QSplitter(Qt.Horizontal)
		act_conc_layout.addWidget(splitter)
		
		# 左侧输入面板
		left_widget = QWidget()
		left_layout = QVBoxLayout(left_widget)
		
		# 创建输入字段分组
		input_group = QGroupBox("输入参数")
		input_layout = QGridLayout(input_group)
		
		# 基体元素
		input_layout.addWidget(QLabel("基体元素:"), 0, 0,Qt.AlignRight)
		self.act_conc_solvent = QLineEdit("Fe")
		input_layout.addWidget(self.act_conc_solvent, 0, 1)
		self.act_conc_solvent.setPlaceholderText('e.g.:Fe')
		
		# 目标元素（追踪其活度值）
		input_layout.addWidget(QLabel("目标元素:"), 1, 0,Qt.AlignRight)
		self.act_conc_target = QLineEdit("C")
		input_layout.addWidget(self.act_conc_target, 1, 1)
		self.act_conc_target.setPlaceholderText('e.g.:C')
		
		# 变化元素（浓度变化的元素）
		input_layout.addWidget(QLabel("变化元素:"), 2, 0,Qt.AlignRight)
		self.act_conc_varying = QLineEdit("Si")
		input_layout.addWidget(self.act_conc_varying, 2, 1)
		self.act_conc_varying.setPlaceholderText('e.g.:Si')
		
		# 目标元素固定浓度
		input_layout.addWidget(QLabel("目标元素浓度:"), 3, 0,Qt.AlignRight)
		self.act_conc_target_conc = QLineEdit("0.03")
		input_layout.addWidget(self.act_conc_target_conc, 3, 1)
		self.act_conc_target_conc.setPlaceholderText('e.g.:0.01')
		
		# 温度
		input_layout.addWidget(QLabel("温度 (K):"), 4, 0,Qt.AlignRight)
		self.act_conc_temp = QLineEdit("1873.0")
		input_layout.addWidget(self.act_conc_temp, 4, 1)
		self.act_conc_temp.setPlaceholderText('e.g.:1873')
		
		# 状态
		input_layout.addWidget(QLabel("状态:"), 5, 0,Qt.AlignRight)
		self.act_conc_state = QComboBox()
		self.act_conc_state.addItems(["liquid", "solid"])
		input_layout.addWidget(self.act_conc_state, 5, 1)
		
		# 外推模型
		input_layout.addWidget(QLabel("外推模型:"), 6, 0,Qt.AlignRight)
		self.act_conc_model = QComboBox()
		self.act_conc_model.addItems(["UEM1", "UEM2", "GSM", "Muggianu"])
		input_layout.addWidget(self.act_conc_model, 6, 1)
		
		# 变化元素浓度范围
		range_group = QGroupBox("浓度范围设置")
		range_layout = QGridLayout(range_group)
		
		# 最小值
		range_layout.addWidget(QLabel("最小值:"), 0, 0)
		self.act_conc_min = QDoubleSpinBox()
		self.act_conc_min.setRange(0.0, 1.0)
		self.act_conc_min.setSingleStep(0.01)
		self.act_conc_min.setValue(0.0)
		self.act_conc_min.setDecimals(3)
		range_layout.addWidget(self.act_conc_min, 0, 1)
		
		# 最大值
		range_layout.addWidget(QLabel("最大值:"), 1, 0)
		self.act_conc_max = QDoubleSpinBox()
		self.act_conc_max.setRange(0.0, 1.0)
		self.act_conc_max.setSingleStep(0.01)
		self.act_conc_max.setValue(0.5)
		self.act_conc_max.setDecimals(3)
		range_layout.addWidget(self.act_conc_max, 1, 1)
		
		# 步长
		range_layout.addWidget(QLabel("步长:"), 2, 0)
		self.act_conc_step = QDoubleSpinBox()
		self.act_conc_step.setRange(0.01, 0.5)
		self.act_conc_step.setSingleStep(0.01)
		self.act_conc_step.setValue(0.05)
		self.act_conc_step.setDecimals(3)
		range_layout.addWidget(self.act_conc_step, 2, 1)
		
		input_layout.addWidget(range_group, 7, 0, 1, 3)
		
		# 添加分隔线
		line = QFrame()
		line.setFrameShape(QFrame.HLine)
		line.setFrameShadow(QFrame.Sunken)
		input_layout.addWidget(line, 8, 0, 1, 3)
		
		# 计算按钮
		btn_layout = QHBoxLayout()
		calculate_btn = QPushButton("计算活度-浓度关系")
		calculate_btn.clicked.connect(self.calculate_activity_vs_conc)
		btn_layout.addWidget(calculate_btn)
		
		clear_btn = QPushButton("清除结果")
		clear_btn.clicked.connect(self.clear_act_conc_result)
		btn_layout.addWidget(clear_btn)
		
		input_layout.addLayout(btn_layout, 9, 0, 1, 3)
		
		# 添加输入分组到左侧布局
		left_layout.addWidget(input_group)
		left_layout.addStretch()
		
		# 右侧结果面板
		right_widget = QWidget()
		right_layout = QVBoxLayout(right_widget)
		
		# 结果文本区域
		result_group = QGroupBox("计算结果")
		result_layout = QVBoxLayout(result_group)
		
		self.act_conc_result = QTextEdit()
		self.act_conc_result.setReadOnly(True)
		result_layout.addWidget(self.act_conc_result)
		
		# 图表区域
		chart_group = QGroupBox("数据可视化")
		chart_layout = QVBoxLayout(chart_group)
		
		self.act_conc_canvas = MplCanvas(self, width=5, height=4, dpi=100)
		chart_layout.addWidget(self.act_conc_canvas)
		
		# 添加结果分组和图表分组到右侧布局
		right_layout.addWidget(result_group, 1)
		right_layout.addWidget(chart_group, 2)  # 图表区域更大
		
		# 添加左右面板到分割器
		splitter.addWidget(left_widget)
		splitter.addWidget(right_widget)
		splitter.setSizes([300, 700])  # 设置初始分割比例
		
		# 初始绘制空图表
		self.init_act_conc_chart()
		
		# 添加到选项卡
		self.tabs.addTab(act_conc_widget, "活度-浓度关系")
	
	def create_coef_vs_conc_tab (self):
		"""创建活度系数-浓度关系选项卡"""
		coef_conc_widget = QWidget()
		coef_conc_layout = QVBoxLayout(coef_conc_widget)
		
		# 创建分割器
		splitter = QSplitter(Qt.Horizontal)
		coef_conc_layout.addWidget(splitter)
		
		# 左侧输入面板
		left_widget = QWidget()
		left_layout = QVBoxLayout(left_widget)
		
		# 创建输入字段分组
		input_group = QGroupBox("输入参数")
		input_layout = QGridLayout(input_group)
		
		# 基体元素
		input_layout.addWidget(QLabel("基体元素:"), 0, 0,Qt.AlignRight)
		self.coef_conc_solvent = QLineEdit("Fe")
		input_layout.addWidget(self.coef_conc_solvent, 0, 1)
		self.coef_conc_solvent.setPlaceholderText('e.g.:Fe')
		
		# 目标元素（追踪其活度系数）
		input_layout.addWidget(QLabel("目标元素:"), 1, 0,Qt.AlignRight)
		self.coef_conc_target = QLineEdit("C")
		input_layout.addWidget(self.coef_conc_target, 1, 1)
		self.coef_conc_target.setPlaceholderText('e.g.:C')
		
		# 变化元素（浓度变化的元素）
		input_layout.addWidget(QLabel("变化元素:"), 2, 0,Qt.AlignRight)
		self.coef_conc_varying = QLineEdit("Si")
		input_layout.addWidget(self.coef_conc_varying, 2, 1)
		self.coef_conc_varying.setPlaceholderText('e.g.:Si')
		
		# 目标元素固定浓度
		input_layout.addWidget(QLabel("目标元素浓度:"), 3, 0,Qt.AlignRight)
		self.coef_conc_target_conc = QLineEdit("0.03")
		input_layout.addWidget(self.coef_conc_target_conc, 3, 1)
		self.coef_conc_target_conc.setPlaceholderText('e.g.:0.01')
		
		# 温度
		input_layout.addWidget(QLabel("温度 (K):"), 4, 0,Qt.AlignRight)
		self.coef_conc_temp = QLineEdit("1873.0")
		input_layout.addWidget(self.coef_conc_temp, 4, 1)
		self.coef_conc_temp.setPlaceholderText('e.g.:1873.0')
		
		# 状态
		input_layout.addWidget(QLabel("状态:"), 5, 0,Qt.AlignRight)
		self.coef_conc_state = QComboBox()
		self.coef_conc_state.addItems(["liquid", "solid"])
		input_layout.addWidget(self.coef_conc_state, 5, 1)
		
		# 外推模型
		input_layout.addWidget(QLabel("外推模型:"), 6, 0,Qt.AlignRight)
		self.coef_conc_model = QComboBox()
		self.coef_conc_model.addItems(["UEM1", "UEM2", "GSM", "Muggianu"])
		input_layout.addWidget(self.coef_conc_model, 6, 1)
		
		# 变化元素浓度范围
		range_group = QGroupBox("浓度范围设置")
		range_layout = QGridLayout(range_group)
		
		# 最小值
		range_layout.addWidget(QLabel("最小值:"), 0, 0)
		self.coef_conc_min = QDoubleSpinBox()
		self.coef_conc_min.setRange(0.0, 1.0)
		self.coef_conc_min.setSingleStep(0.01)
		self.coef_conc_min.setValue(0.0)
		self.coef_conc_min.setDecimals(3)
		range_layout.addWidget(self.coef_conc_min, 0, 1)
		
		# 最大值
		range_layout.addWidget(QLabel("最大值:"), 1, 0)
		self.coef_conc_max = QDoubleSpinBox()
		self.coef_conc_max.setRange(0.0, 1.0)
		self.coef_conc_max.setSingleStep(0.01)
		self.coef_conc_max.setValue(0.5)
		self.coef_conc_max.setDecimals(3)
		range_layout.addWidget(self.coef_conc_max, 1, 1)
		
		# 步长
		range_layout.addWidget(QLabel("步长:"), 2, 0)
		self.coef_conc_step = QDoubleSpinBox()
		self.coef_conc_step.setRange(0.01, 0.5)
		self.coef_conc_step.setSingleStep(0.01)
		self.coef_conc_step.setValue(0.05)
		self.coef_conc_step.setDecimals(3)
		range_layout.addWidget(self.coef_conc_step, 2, 1)
		
		input_layout.addWidget(range_group, 7, 0, 1, 3)
		
		# 添加分隔线
		line = QFrame()
		line.setFrameShape(QFrame.HLine)
		line.setFrameShadow(QFrame.Sunken)
		input_layout.addWidget(line, 8, 0, 1, 3)
		
		# 计算按钮
		btn_layout = QHBoxLayout()
		calculate_btn = QPushButton("计算活度系数-浓度关系")
		calculate_btn.clicked.connect(self.calculate_coef_vs_conc)
		btn_layout.addWidget(calculate_btn)
		
		clear_btn = QPushButton("清除结果")
		clear_btn.clicked.connect(self.clear_coef_conc_result)
		btn_layout.addWidget(clear_btn)
		
		input_layout.addLayout(btn_layout, 9, 0, 1, 3)
		
		# 添加输入分组到左侧布局
		left_layout.addWidget(input_group)
		left_layout.addStretch()
		
		# 右侧结果面板
		right_widget = QWidget()
		right_layout = QVBoxLayout(right_widget)
		
		# 结果文本区域
		result_group = QGroupBox("计算结果")
		result_layout = QVBoxLayout(result_group)
		
		self.coef_conc_result = QTextEdit()
		self.coef_conc_result.setReadOnly(True)
		result_layout.addWidget(self.coef_conc_result)
		
		# 图表区域
		chart_group = QGroupBox("数据可视化")
		chart_layout = QVBoxLayout(chart_group)
		
		self.coef_conc_canvas = MplCanvas(self, width=5, height=4, dpi=100)
		chart_layout.addWidget(self.coef_conc_canvas)
		
		# 添加结果分组和图表分组到右侧布局
		right_layout.addWidget(result_group, 1)
		right_layout.addWidget(chart_group, 2)  # 图表区域更大
		
		# 添加左右面板到分割器
		splitter.addWidget(left_widget)
		splitter.addWidget(right_widget)
		splitter.setSizes([300, 700])  # 设置初始分割比例
		
		# 初始绘制空图表
		self.init_coef_conc_chart()
		
		# 添加到选项卡
		self.tabs.addTab(coef_conc_widget, "活度系数-浓度关系")
	
	def setup_value_labels (self, axes:matplotlib.axes.Axes, bars, values, min_height=0.0):
		"""设置统一的数值标签位置

		参数:
		axes - 图表的轴对象
		bars - 柱状图对象列表
		values - 柱状图对应的数值
		min_height - 最小高度阈值，用于决定标签是否放在柱内
		"""
		
		
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
		
	def set_fixed_y_axis(self,axes:matplotlib.axes.Axes,values,y_min,y_max):
		max_values = max(values)
		min_values = min(values)
		y_max = y_max
		y_min = y_min
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
		
	def init_activity_chart (self):
		"""初始化活度图表"""
		self.activity_canvas.axes.clear()
		self.activity_canvas.axes.set_title('活度比较')
		self.activity_canvas.axes.set_ylabel('活度值')
		self.activity_canvas.axes.set_xticklabels([])  # 隐藏x轴标签
		self.activity_canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.activity_canvas.fig.tight_layout()
		self.activity_canvas.draw()
	
	def update_activity_chart (self, results):
		"""更新活度图表"""
		self.activity_canvas.axes.clear()
		
		# 数据
		models = ['Darken', 'Wagner', 'Elliot']
		values = [results['activity'], results['activity_wagner'], results['activity_elliot']]
		
		# 创建柱状图
		bars = self.activity_canvas.axes.bar(models, values, color=['#3498db', '#2ecc71', '#e74c3c'])
		
		# 添加数值标签
		self.setup_value_labels(self.activity_canvas.axes, bars, values, 0.01)
		
		mole_fraction = results["mole_fraction"]
		max_value = max(values)
		y_max = 1.0 if max(max_value, mole_fraction) > 0.84 and max(max_value, mole_fraction) < 1.01 else max(max_value,
		                                                                                                      mole_fraction) * 1.2
		
		self.activity_canvas.axes.set_ylim(0,y_max)
		# 设置图表属性
		solute = results["solute"]
		solvent = results["solvent"]
		self.activity_canvas.axes.set_title(f'${solute}$ 在 ${solvent}$ 中的活度比较', fontsize=14)
		self.activity_canvas.axes.set_ylabel(f'Activity($a_{{{solute}}}$)', fontsize=13)
		self.activity_canvas.axes.grid(True, axis='y', linestyle='--', alpha=0.7)
		
		# 添加摩尔分数参考线
		self.activity_canvas.axes.axhline(y=results['mole_fraction'], color='r', linestyle='--', alpha=0.5)
		self.activity_canvas.axes.text(0, results['mole_fraction'] * 1.05,
		                               f'摩尔分数 $X_{{{solute}}}$: {results["mole_fraction"]:.3f}',
		                               color='r', alpha=0.7, fontsize=12)
		# 增加顶部和底部边距，防止标签出界
		self.activity_canvas.fig.subplots_adjust(bottom=0.2, top=0.85)
		
		# 设置较小的标签字体
		self.activity_canvas.axes.tick_params(axis='x', labelsize=10)
		self.activity_canvas.fig.tight_layout()
		self.activity_canvas.draw()
		
	
	def clear_coef_result (self):
		"""清除活度系数计算结果"""
		self.coef_result.clear()
		self.init_coef_chart()
	
	def init_coef_chart (self):
		"""初始化活度系数图表"""
		self.coef_canvas.axes.clear()
		self.coef_canvas.axes.set_title('活度系数比较')
		self.coef_canvas.axes.set_ylabel('活度系数')
		self.coef_canvas.axes.set_xticklabels([])  # 隐藏x轴标签
		self.coef_canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.coef_canvas.fig.tight_layout()
		self.coef_canvas.draw()
	
	def update_coef_chart (self, results):
		"""更新活度系数图表"""
		self.coef_canvas.axes.clear()
		
		# 数据
		models = ['Darken', 'Wagner', 'Elliot']
		values = [
			results['activity_coefficient_darken'],
			results['activity_coefficient_wagner'],
			results['activity_coefficient_elliot']
		]
		
		# 创建柱状图
		bars = self.coef_canvas.axes.bar(models, values, color=['#3498db', '#2ecc71', '#e74c3c'])
		
		# 添加数值标签
		self.setup_value_labels(self.coef_canvas.axes,bars,values)
		values_max = max(values)
		y_max = max(values_max,1.0)*1.2
		self.coef_canvas.axes.set_ylim(0,y_max)
		# 设置图表属性
		solute = results["solute"]
		solvent = results["solvent"]
		self.coef_canvas.axes.set_title(f'${solute}$ 在 ${solvent}$ 中的活度系数比较', fontsize=14)
		self.coef_canvas.axes.set_ylabel(f'Activity Coefficient($γ_{{{solute}}}$)', fontsize=13)
		self.coef_canvas.axes.grid(True, axis='y', linestyle='--', alpha=0.7)
		
		# 添加理想行为参考线
		self.coef_canvas.axes.axhline(y=1.0, color='r', linestyle='--', alpha=0.5)
		self.coef_canvas.axes.text(0, 1.05, '理想行为: 1.000', color='r', alpha=0.7, fontsize=12)
		
		self.coef_canvas.fig.subplots_adjust(bottom=0.2, top=0.85)
		self.coef_canvas.axes.tick_params(axis='x', labelsize=10)
		self.coef_canvas.fig.tight_layout()
		self.coef_canvas.draw()
	
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
		models = ['UEM1', 'UEM2', '实验值']
		values = [
			results['sij_uem1'],
			results['sij_uem2'],
			results['sij_experimental'] if not np.isnan(results['sij_experimental']) else 0
		]
		
		# 创建柱状图
		colors = ['#3498db', '#2ecc71', '#e74c3c']
		if np.isnan(results['sij_experimental']):
			models = models[:2]  # 如果没有实验值，则只显示两个模型
			values = values[:2]
			colors = colors[:2]
		
		bars = self.interact_canvas.axes.bar(models, values, color=colors)
		
		# 添加数值标签
		self.setup_value_labels(self.interact_canvas.axes,bars,values)
		self.set_fixed_y_axis(self.interact_canvas.axes,values,-10.0,10)
		
		
		# 设置图表属性
		solvent = results["solvent"]
		solute_i = results["solute_i"]
		solute_j = results["solute_j"]
		self.interact_canvas.axes.set_title(
				f'${solute_j}$ 对 ${solute_i}$ 在 ${solvent}$ 中的相互作用系数', fontsize=14)
		self.interact_canvas.axes.set_ylabel(f'$\\varepsilon^{{{solute_j}}}_{{{solute_i}}}$', fontsize=14)
		self.interact_canvas.axes.grid(True, axis='y', linestyle='--', alpha=0.7)
		
		self.interact_canvas.fig.tight_layout()
		self.interact_canvas.draw()
	
	def clear_second_result (self):
		"""清除二阶相互作用系数计算结果"""
		self.second_result.clear()
		self.init_second_chart()
	
	def init_second_chart (self):
		"""初始化二阶相互作用系数图表"""
		self.second_canvas.axes.clear()
		self.second_canvas.axes.set_title('二阶相互作用系数')
		self.second_canvas.axes.set_ylabel('系数值')
		self.second_canvas.axes.set_xticklabels([])  # 隐藏x轴标签
		self.second_canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.second_canvas.fig.tight_layout()
		self.second_canvas.draw()
	
	def update_second_chart (self, results):
		"""更新二阶相互作用系数图表"""
		"""更新二阶相互作用系数图表"""
		self.second_canvas.axes.clear()
		
		# 数据
		solute_i = results["solute_i"]
		solute_j = results["solute_j"]
		solute_k = results["solute_k"]
		
		# 创建更具数学意义的标签
		coefficients = [
			f'$\\rho_{{{solute_i}}}^{{{solute_i},{solute_i}}}$',
			f'$\\rho_{{{solute_i}}}^{{{solute_i},{solute_j}}}$',
			f'$\\rho_{{{solute_i}}}^{{{solute_j},{solute_j}}}$',
			f'$\\rho_{{{solute_i}}}^{{{solute_j},{solute_k}}}$'
		]
		
		values = [
			results['ri_ii'],
			results['ri_ij'],
			results['ri_jj'],
			results['ri_jk']
		]
		
		# 创建柱状图
		colors = ['#3498db', '#2ecc71', '#e74c3c', '#9b59b6']
		bars = self.second_canvas.axes.bar(coefficients, values, color=colors)
		
		# 添加数值标签
		self.setup_value_labels(self.second_canvas.axes,bars,values)
		
		self.set_fixed_y_axis(self.second_canvas.axes,values,-20,20)
		
		# 设置图表属性
		solvent = results["solvent"]
		title = f'二阶相互作用系数 (${solvent}$-${solute_i}$-${solute_j}$'
		if solute_k:
			title += f'-${solute_k}$'
		title += ')'
		
		self.second_canvas.axes.set_title(title, fontsize=14)
		self.second_canvas.axes.set_ylabel('系数值', fontsize=13)
		self.second_canvas.axes.grid(True, axis='y', linestyle='--', alpha=0.7)
		
		self.second_canvas.fig.tight_layout()
		self.second_canvas.draw()
	
	def clear_act_conc_result (self):
		"""清除活度-浓度关系计算结果"""
		self.act_conc_result.clear()
		self.init_act_conc_chart()
	
	def init_act_conc_chart (self):
		"""初始化活度-浓度关系图表"""
		self.act_conc_canvas.axes.clear()
		self.act_conc_canvas.axes.set_title('活度-浓度关系')
		self.act_conc_canvas.axes.set_xlabel('组分浓度')
		self.act_conc_canvas.axes.set_ylabel('活度值')
		self.act_conc_canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.act_conc_canvas.fig.tight_layout()
		self.act_conc_canvas.draw()
	
	def update_act_conc_chart (self, conc_list, activity_darken, activity_wagner, activity_elliot, solvent, target,
	                           varying):
		"""更新活度-浓度关系图表"""
		"""更新活度-浓度关系图表"""
		self.act_conc_canvas.axes.clear()
		
		# 绘制曲线, Darken means the activity coefficent equation is modified as G-D equation with only first order activity interaction parameter
		# Wagner means the activity coefficent equation is calculated by Wagner dilution theory which only first order activity interaction parameter is considered
		# Elloit-Lupis means the activity coefficent is calculated by considering the second order activity interaction parameter.
		self.act_conc_canvas.axes.plot(conc_list, activity_darken, 'o-', label='Darken', color='#3498db', linewidth=2)
		self.act_conc_canvas.axes.plot(conc_list, activity_wagner, 's-', label='Wagner', color='#2ecc71', linewidth=2)
		self.act_conc_canvas.axes.plot(conc_list, activity_elliot, '^-', label='Elloit', color='#e74c3c', linewidth=2)
		
		# 绘制理想线 (对比)
		ideal_line = np.array(conc_list)
		if varying == target:
			self.act_conc_canvas.axes.plot(conc_list, ideal_line, '--', label='理想行为', color='gray', alpha=0.7)
		
		# 设置图表属性
		self.act_conc_canvas.axes.set_title(f'${target}$ 的活度随 ${varying}$ 浓度的变化关系', fontsize=14)
		self.act_conc_canvas.axes.set_xlabel(f'$X_{{{varying}}}$', fontsize=13)
		self.act_conc_canvas.axes.set_ylabel(f'Activity($a_{{{target}}}$)', fontsize=14)
		self.act_conc_canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.act_conc_canvas.axes.legend(fontsize=11)
		
		self.act_conc_canvas.fig.tight_layout()
		self.act_conc_canvas.draw()
	
	def clear_coef_conc_result (self):
		"""清除活度系数-浓度关系计算结果"""
		self.coef_conc_result.clear()
		self.init_coef_conc_chart()
	
	def init_coef_conc_chart (self):
		"""初始化活度系数-浓度关系图表"""
		self.coef_conc_canvas.axes.clear()
		self.coef_conc_canvas.axes.set_title('活度系数-浓度关系')
		self.coef_conc_canvas.axes.set_xlabel('组分浓度')
		self.coef_conc_canvas.axes.set_ylabel('活度系数')
		self.coef_conc_canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.coef_conc_canvas.fig.tight_layout()
		self.coef_conc_canvas.draw()
	
	def update_coef_conc_chart (self, conc_list, coef_darken, coef_wagner, coef_elliot, solvent, target, varying):
		"""更新活度系数-浓度关系图表"""
		self.coef_conc_canvas.axes.clear()
		
		# 绘制曲线, Darken means the activity coefficent equation is modified as G-D equation with only first order activity interaction parameter
		# Wagner means the activity coefficent equation is calculated by Wagner dilution theory which only first order activity interaction parameter is considered
		# Elloit-Lupis means the activity coefficent is calculated by considering the second order activity interaction parameter.
		self.coef_conc_canvas.axes.plot(conc_list, coef_darken, 'o-', label='Darken', color='#3498db', linewidth=2)
		self.coef_conc_canvas.axes.plot(conc_list, coef_wagner, 's-', label='Wagner', color='#2ecc71', linewidth=2)
		self.coef_conc_canvas.axes.plot(conc_list, coef_elliot, '^-', label='Elliot', color='#e74c3c', linewidth=2)
		
		# 绘制理想系数线 (常数1)
		self.coef_conc_canvas.axes.axhline(y=1.0, linestyle='--', color='gray', alpha=0.7, label='理想行为')
		
		# 设置图表属性
		self.coef_conc_canvas.axes.set_title(f'${target}$ 的活度系数随 ${varying}$ 浓度的变化关系', fontsize=14)
		self.coef_conc_canvas.axes.set_xlabel(f'$X_{{{varying}}}$', fontsize=13)
		self.coef_conc_canvas.axes.set_ylabel(f'Activity Coefficient($γ_{{{target}}}$)', fontsize=14)
		self.coef_conc_canvas.axes.grid(True, linestyle='--', alpha=0.7)
		self.coef_conc_canvas.axes.legend(fontsize=11)
		
		self.coef_conc_canvas.fig.tight_layout()
		self.coef_conc_canvas.draw()
	
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
			# 这里假设存在 Muggianu 模型函数
			# 如果没有，需要在 BinaryModel 中添加
			return self.binary_model.UEM1  # 临时使用 UEM1 代替
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
					comp_dict, solute, solvent, temp, state, model_func, model_name)
			
			wagner_acf = self.activity_coefficient.activity_coefficient_wagner(
					comp_dict, solvent, solute, temp, state, model_func, model_name)
			
			elliot_acf = self.activity_coefficient.activity_coefficient_elloit(
					comp_dict, solute, solvent, temp, state, model_func, model_name)
			
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
				"activity_coefficient_elliot": round(math.exp(elliot_acf), 3)
			}
			
			# 显示结果 - 添加到当前结果而不是清空
			current_text = self.activity_result.toPlainText()
			if current_text:
				# 添加分隔线
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
			
			# 更新图表
			self.update_activity_chart(results)
			
			# 更新状态栏
			self.update_status(f"已完成 {solute} 在 {solvent} 中的活度计算")
		
		except Exception as e:
			QMessageBox.critical(self, "计算错误", f"发生错误: {str(e)}")
			self.update_status("计算失败")
	
	def calculate_activity_coef (self):
		"""计算活度系数"""
		try:
			# 验证输入
			fields = [
				(self.coef_alloy, "合金成分"),
				(self.coef_solvent, "基体元素"),
				(self.coef_solute, "溶质元素"),
				(self.coef_temp, "温度")
			]
			
			if not self.validate_input(fields):
				return
			
			# 获取输入值
			alloy = self.coef_alloy.text()
			solvent = self.coef_solvent.text()
			solute = self.coef_solute.text()
			try:
				temp = float(self.coef_temp.text())
			except ValueError:
				QMessageBox.critical(self, "输入错误", "温度必须是数值")
				return
			
			state = self.coef_state.currentText()
			model_name = self.coef_model.currentText()
			
			# 更新状态栏
			self.update_status(f"正在计算 {solute} 在 {solvent} 中的活度系数...")
			
			# 解析合金成分
			comp_dict = self.parse_composition(f"{solvent}{alloy}")
			
			# 获取模型函数
			model_func = self.get_model_function(model_name)
			
			# 实际计算
			self.activity_coefficient.set_composition_dict(f"{solvent}{alloy}")
			
			# 计算活度系数
			darken_acf = self.activity_coefficient.activity_coefficient_darken(
					comp_dict, solute, solvent, temp, state, model_func, model_name)
			
			wagner_acf = self.activity_coefficient.activity_coefficient_wagner(
					comp_dict, solvent, solute, temp, state, model_func, model_name)
			
			elliot_acf = self.activity_coefficient.activity_coefficient_elloit(
					comp_dict, solute, solvent, temp, state, model_func, model_name)
			
			# 准备结果
			results = {
				"composition": alloy,
				"solvent": solvent,
				"solute": solute,
				"temperature": temp,
				"state": state,
				"model": model_name,
				"activity_coefficient_darken": round(math.exp(darken_acf), 3),
				"activity_coefficient_wagner": round(math.exp(wagner_acf), 3),
				"activity_coefficient_elliot": round(math.exp(elliot_acf), 3)
			}
			
			# 显示结果 - 添加到当前结果而不是清空
			current_text = self.coef_result.toPlainText()
			if current_text:
				# 添加分隔线
				result_text = f"\n{'-' * 50}\n\n"
			else:
				result_text = ""
			
			result_text += f"活度系数计算结果:\n\n"
			result_text += f"合金成分: {results['composition']}\n"
			result_text += f"基体元素: {results['solvent']}\n"
			result_text += f"溶质元素: {results['solute']}\n"
			result_text += f"温度: {results['temperature']} K\n"
			result_text += f"状态: {results['state']}\n"
			result_text += f"外推模型: {results['model']}\n\n"
			result_text += f"Darken模型活度系数: {results['activity_coefficient_darken']}\n"
			result_text += f"Wagner模型活度系数: {results['activity_coefficient_wagner']}\n"
			result_text += f"Elliot模型活度系数: {results['activity_coefficient_elliot']}\n"
			
			if current_text:
				self.coef_result.append(result_text)
			else:
				self.coef_result.setText(result_text)
			
			# 自动滚动到底部
			self.coef_result.verticalScrollBar().setValue(
					self.coef_result.verticalScrollBar().maximum())
			
			# 更新图表
			self.update_coef_chart(results)
			
			# 更新状态栏
			self.update_status(f"已完成 {solute} 在 {solvent} 中的活度系数计算")
		
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
			# 在实际实现中需要导入 entropy_judge 函数
			# 这里简化处理，假设 entropy_judge 返回 False
			is_entropy = False  # 实际中应该调用 entropy_judge(solvent, solute_i, solute_j)
			ternary = TernaryMelts(temp, state, is_entropy)
			
			# 计算相互作用系数
			sij_uem1 = ternary.activity_interact_coefficient_1st(
					solv, solui, soluj, temp, state, model_func, model_name)
			
			# 这里使用 UEM2 只是为了对比
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
			# 在实际实现中需要导入 entropy_judge 函数
			is_entropy = False  # 实际中应该调用 entropy_judge(solvent, solute_i, solute_j, solute_k)
			ternary = TernaryMelts(temp, state, is_entropy)
			
			# 计算二阶系数
			rii = ternary.roui_ii(solv, solui, temp, state, model_func, model_name)
			rij = ternary.roui_ij(solv, solui, soluj, temp, state, model_func, model_name)
			rjj = ternary.roui_jj(solv, solui, soluj, temp, state, model_func, model_name)
			rjk = ternary.roui_jk(solv, solui, soluj, soluk, temp, state, model_func, model_name)
			
			# 准备结果
			results = {
				"solvent": solvent,
				"solute_i": solute_i,
				"solute_j": solute_j,
				"solute_k": solute_k,
				"temperature": temp,
				"state": state,
				"model": model_name,
				"ri_ii": round(rii, 3),
				"ri_ij": round(rij, 3),
				"ri_jj": round(rjj, 3),
				"ri_jk": round(rjk, 3)
			}
			
			# 显示结果 - 添加到当前结果而不是清空
			current_text = self.second_result.toPlainText()
			if current_text:
				# 添加分隔线
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
			result_text += f"ρi^jj: {results['ri_jj']}\n"
			result_text += f"ρi^jk: {results['ri_jk']}\n"
			
			if current_text:
				self.second_result.append(result_text)
			else:
				self.second_result.setText(result_text)
			
			# 自动滚动到底部
			self.second_result.verticalScrollBar().setValue(
					self.second_result.verticalScrollBar().maximum())
			
			# 更新图表
			self.update_second_chart(results)
			
			# 更新状态栏
			self.update_status(f"已完成二阶相互作用系数计算")
		
		except Exception as e:
			QMessageBox.critical(self, "计算错误", f"发生错误: {str(e)}")
			self.update_status("计算失败")


	def calculate_activity_vs_conc (self):
		"""计算活度随浓度变化关系"""
		try:
			# 验证输入
			fields = [
				(self.act_conc_solvent, "基体元素"),
				(self.act_conc_target, "目标元素"),
				(self.act_conc_varying, "变化元素"),
				(self.act_conc_target_conc, "目标元素浓度"),
				(self.act_conc_temp, "温度")
			]
			
			if not self.validate_input(fields):
				return
			
			# 获取输入值
			solvent = self.act_conc_solvent.text()
			target = self.act_conc_target.text()
			varying = self.act_conc_varying.text()
			
			try:
				target_conc = float(self.act_conc_target_conc.text())
				temp = float(self.act_conc_temp.text())
				
				# 获取浓度范围
				conc_min = self.act_conc_min.value()
				conc_max = self.act_conc_max.value()
				conc_step = self.act_conc_step.value()
				
				if conc_min >= conc_max:
					QMessageBox.critical(self, "输入错误", "最小值必须小于最大值")
					return
				
				if conc_step <= 0:
					QMessageBox.critical(self, "输入错误", "步长必须大于0")
					return
			except ValueError:
				QMessageBox.critical(self, "输入错误", "请确保所有数值输入都是有效的数字")
				return
			
			state = self.act_conc_state.currentText()
			model_name = self.act_conc_model.currentText()
			
			# 更新状态栏
			self.update_status(f"正在计算 {target} 的活度随 {varying} 浓度变化...")
			
			# 获取模型函数
			model_func = self.get_model_function(model_name)
			
			# 计算不同浓度下的活度
			conc_list = []
			activity_darken = []
			activity_wagner = []
			activity_elliot = []
			
			current_conc = conc_min
			while current_conc <= conc_max:
				conc_list.append(current_conc)
				
				# 构建合金成分字典
				# 注意：如果自变量和因变量是相同元素，需要特殊处理
				if varying == target:
					# 活度与自身浓度的关系
					comp_dict = {solvent: 1.0 - current_conc, varying: current_conc}
				else:
					# 保持基体元素为剩余部分
					solvent_conc = 1.0 - current_conc - target_conc
					if solvent_conc < 0:
						QMessageBox.warning(self, "计算警告",
						                    f"在 {varying} 浓度为 {current_conc:.3f} 时，总浓度超过了1。该点已跳过。")
						current_conc += conc_step
						continue
					
					comp_dict = {solvent: solvent_conc, target: target_conc, varying: current_conc}
				
				# 设置成分
				self.activity_coefficient.set_composition_dict("".join([f"{k}{v}" for k, v in comp_dict.items()]))
				
				# 计算活度系数
				darken_acf = self.activity_coefficient.activity_coefficient_darken(
						comp_dict, target, solvent, temp, state, model_func, model_name)
				
				wagner_acf = self.activity_coefficient.activity_coefficient_wagner(
						comp_dict, solvent, target, temp, state, model_func, model_name)
				
				elliot_acf = self.activity_coefficient.activity_coefficient_elloit(
						comp_dict, target, solvent, temp, state, model_func, model_name)
				
				# 获取目标元素摩尔分数
				xi = comp_dict.get(target, 0.0)
				
				# 计算活度
				act_darken = math.exp(darken_acf) * xi
				act_wagner = math.exp(wagner_acf) * xi
				act_elliot = math.exp(elliot_acf) * xi
				
				activity_darken.append(act_darken)
				activity_wagner.append(act_wagner)
				activity_elliot.append(act_elliot)
				
				current_conc += conc_step
			
			# 生成结果表格
			result_text = f"活度-浓度关系计算结果:\n\n"
			result_text += f"基体元素: {solvent}\n"
			result_text += f"目标元素: {target}\n"
			result_text += f"变化元素: {varying}\n"
			result_text += f"温度: {temp} K\n"
			result_text += f"状态: {state}\n"
			result_text += f"外推模型: {model_name}\n\n"
			
			# 表格头部
			result_text += f"{'浓度':<10} {'Darken活度':<15} {'Wagner活度':<15} {'Elliot活度':<15}\n"
			result_text += "-" * 55 + "\n"
			
			# 表格数据
			for i in range(len(conc_list)):
				result_text += f"{conc_list[i]:<10.3f} {activity_darken[i]:<15.4f} {activity_wagner[i]:<15.4f} {activity_elliot[i]:<15.4f}\n"
			
			# 显示结果
			self.act_conc_result.setText(result_text)
			
			# 更新图表
			self.update_act_conc_chart(conc_list, activity_darken, activity_wagner, activity_elliot,
			                           solvent, target, varying)
			
			# 更新状态栏
			self.update_status(f"已完成 {target} 的活度随 {varying} 浓度变化计算")
		
		except Exception as e:
			QMessageBox.critical(self, "计算错误", f"发生错误: {str(e)}")
			self.update_status("计算失败")
	

	def calculate_coef_vs_conc (self):
		"""计算活度系数随浓度变化关系"""
		try:
			# 验证输入
			fields = [
				(self.coef_conc_solvent, "基体元素"),
				(self.coef_conc_target, "目标元素"),
				(self.coef_conc_varying, "变化元素"),
				(self.coef_conc_target_conc, "目标元素浓度"),
				(self.coef_conc_temp, "温度")
			]
			
			if not self.validate_input(fields):
				return
			
			# 获取输入值
			solvent = self.coef_conc_solvent.text()
			target = self.coef_conc_target.text()
			varying = self.coef_conc_varying.text()
			
			try:
				target_conc = float(self.coef_conc_target_conc.text())
				temp = float(self.coef_conc_temp.text())
				
				# 获取浓度范围
				conc_min = self.coef_conc_min.value()
				conc_max = self.coef_conc_max.value()
				conc_step = self.coef_conc_step.value()
				
				if conc_min >= conc_max:
					QMessageBox.critical(self, "输入错误", "最小值必须小于最大值")
					return
				
				if conc_step <= 0:
					QMessageBox.critical(self, "输入错误", "步长必须大于0")
					return
			except ValueError:
				QMessageBox.critical(self, "输入错误", "请确保所有数值输入都是有效的数字")
				return
			
			state = self.coef_conc_state.currentText()
			model_name = self.coef_conc_model.currentText()
			
			# 更新状态栏
			self.update_status(f"正在计算 {target} 的活度系数随 {varying} 浓度变化...")
			
			# 获取模型函数
			model_func = self.get_model_function(model_name)
			
			# 计算不同浓度下的活度系数
			conc_list = []
			coef_darken = []
			coef_wagner = []
			coef_elliot = []
			
			current_conc = conc_min
			while current_conc <= conc_max:
				conc_list.append(current_conc)
				
				# 构建合金成分字典
				# 注意：如果自变量和因变量是相同元素，需要特殊处理
				if varying == target:
					# 活度系数与自身浓度的关系
					comp_dict = {solvent: 1.0 - current_conc, varying: current_conc}
				else:
					# 保持基体元素为剩余部分
					solvent_conc = 1.0 - current_conc - target_conc
					if solvent_conc < 0:
						QMessageBox.warning(self, "计算警告",
						                    f"在 {varying} 浓度为 {current_conc:.3f} 时，总浓度超过了1。该点已跳过。")
						current_conc += conc_step
						continue
					
					comp_dict = {solvent: solvent_conc, target: target_conc, varying: current_conc}
				
				# 设置成分
				self.activity_coefficient.set_composition_dict("".join([f"{k}{v}" for k, v in comp_dict.items()]))
				
				# 计算活度系数
				darken_acf = self.activity_coefficient.activity_coefficient_darken(
						comp_dict, target, solvent, temp, state, model_func, model_name)
				
				wagner_acf = self.activity_coefficient.activity_coefficient_wagner(
						comp_dict, solvent, target, temp, state, model_func, model_name)
				
				elliot_acf = self.activity_coefficient.activity_coefficient_elloit(
						comp_dict, target, solvent, temp, state, model_func, model_name)
				
				# 计算活度系数
				coef_darken.append(math.exp(darken_acf))
				coef_wagner.append(math.exp(wagner_acf))
				coef_elliot.append(math.exp(elliot_acf))
				
				current_conc += conc_step
			
			# 生成结果表格
			result_text = f"活度系数-浓度关系计算结果:\n\n"
			result_text += f"基体元素: {solvent}\n"
			result_text += f"目标元素: {target}\n"
			result_text += f"变化元素: {varying}\n"
			result_text += f"温度: {temp} K\n"
			result_text += f"状态: {state}\n"
			result_text += f"外推模型: {model_name}\n\n"
			
			# 表格头部
			result_text += f"{'浓度':<10} {'Darken系数':<15} {'Wagner系数':<15} {'Elliot系数':<15}\n"
			result_text += "-" * 55 + "\n"
			
			# 表格数据
			for i in range(len(conc_list)):
				result_text += f"{conc_list[i]:<10.3f} {coef_darken[i]:<15.4f} {coef_wagner[i]:<15.4f} {coef_elliot[i]:<15.4f}\n"
			
			# 显示结果
			self.coef_conc_result.setText(result_text)
			
			# 更新图表
			self.update_coef_conc_chart(conc_list, coef_darken, coef_wagner, coef_elliot,
			                            solvent, target, varying)
			
			# 更新状态栏
			self.update_status(f"已完成 {target} 的活度系数随 {varying} 浓度变化计算")
		
		except Exception as e:
			QMessageBox.critical(self, "计算错误", f"发生错误: {str(e)}")
			self.update_status("计算失败")
	

# 主程序入口
if __name__ == "__main__":
	app = QApplication(sys.argv)
	
	# 设置高DPI缩放
	app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
	app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
	
	window = AlloyActProGUIp()
	window.show()
	sys.exit(app.exec_())