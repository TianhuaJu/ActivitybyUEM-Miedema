import os
import re
import sys

import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Set matplotlib font settings
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'FangSong', 'SimSun', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
matplotlib.rcParams['font.size'] = 12  # 增加图表字体大小

# 使用Matplotlib的数学文本渲染（不依赖LaTeX）
matplotlib.rcParams['text.usetex'] = False
matplotlib.rcParams['mathtext.default'] = 'regular'

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QTabWidget, QMessageBox,
                             QStatusBar, QAction, QMenu, QSystemTrayIcon)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QGuiApplication, QIcon
from models.extrapolation_models import BinaryModel
from calculations.activity_calculator import ActivityCoefficient

from gui.ActivityCalculationWidget import ActivityCalculationWidget
from gui.InteractionCoefficientWidget import InteractionCoefficientWidget
from gui.SecondOrderCoefficientWidget import SecondOrderCoefficientWidget
# 1. 导入 UnitConversionWidget
from gui.UnitConversionWidget import UnitConversionWidget


class MplCanvas(FigureCanvas):
	"""Matplotlib画布类"""
	
	def __init__ (self, parent=None, width=7, height=6, dpi=100):
		self.fig = Figure(figsize=(width, height), dpi=dpi)
		self.axes = self.fig.add_subplot(111)
		super(MplCanvas, self).__init__(self.fig)


class AlloyActGUI(QMainWindow):
	def __init__ (self):
		super().__init__()
		self.setWindowTitle("AlloyAct V1.0 - 合金热力学计算器")
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
		# 2. 添加一个变量用于跟踪单位转换窗口
		self.conversion_window = None
		
		# 设置应用字体
		self.app_font = QFont("Microsoft YaHei UI", 10)
		QApplication.setFont(self.app_font)
		
		# 创建主窗口布局
		self.central_widget = QWidget()
		self.setCentralWidget(self.central_widget)
		
		# 主布局
		self.main_layout = QVBoxLayout(self.central_widget)
		
		
		# 创建选项卡控件
		self.tabs = QTabWidget()
		self.main_layout.addWidget(self.tabs)
		# 创建菜单栏
		self.setup_menu_bar()
		# 设置选项卡样式
		self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d7d7d7;
                background: #f5f5f5;
            }
            QTabBar::tab {
                background: #e0e0e0;
                color: #333333;
                padding: 10px 30px;
                margin-right: 8px;
                border: 1px solid #b8b8b8;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
                font-size: 15px;
                min-width:150px;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background: #d0d0d0;
            }
        """)
		
		# 创建各个选项卡 (不再创建单位转换选项卡)
		self.create_activity_tab()
		self.create_interaction_tab()
		self.create_second_order_tab()
		
		# 创建状态栏
		self.status_bar = QStatusBar()
		self.setStatusBar(self.status_bar)
		self.update_status("就绪 - 请选择计算类型并输入参数")
		
		# 设置选项卡切换事件
		self.tabs.currentChanged.connect(self.on_tab_changed)
		
		# 设置全局样式
		self.set_global_styles()
	
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
		
		# 3. 修改菜单项的连接
		conversion_action = QAction('单位转换(&U)', self)
		conversion_action.setShortcut('Ctrl+U')
		conversion_action.triggered.connect(self.open_conversion_tool)
		tools_menu.addAction(conversion_action)
		
		tools_menu.addSeparator()
		
		# 帮助菜单
		help_menu = menubar.addMenu('帮助(&H)')
		
		about_action = QAction('关于(&A)', self)
		about_action.triggered.connect(self.show_about)
		help_menu.addAction(about_action)
	
	# 4. 添加打开独立窗口的新方法
	def open_conversion_tool (self):
		"""以独立窗口的形式打开单位转换工具"""
		if self.conversion_window is None:
			self.conversion_window = UnitConversionWidget()
			self.conversion_window.setWindowTitle("单位转换工具")
		
		self.conversion_window.show()
		self.conversion_window.activateWindow()
	
	def set_global_styles (self):
		"""设置全局样式"""
		self.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                background-color: white;
                font-size: 14pt;
            }
            QComboBox {
                padding: 6px;
                border: 1px solid #b8b8b8;
                border-radius: 4px;
                background-color: white;
                selection-background-color: #3498db;
                font-size: 14pt;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #b8b8b8;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QPushButton {
                padding: 8px 16px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
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
                margin-top: 10px;
                padding-top: 15px;
                font-size: 12pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                font-size: 12pt;
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
	
	def setup_icon (self):
		icon_path = self.get_resource_path('resources/app_icon.ico')
		if os.path.exists(icon_path):
			self.setWindowIcon(QIcon(icon_path))
	
	def setup_tray_icon (self):
		"""设置系统托盘图标"""
		if QSystemTrayIcon.isSystemTrayAvailable():
			self.tray_icon = QSystemTrayIcon(self)
			
			# 设置托盘图标
			icon_path = self.get_resource_path('resources/app_icon.ico')
			if os.path.exists(icon_path):
				self.tray_icon.setIcon(QIcon(icon_path))
			
			# 创建托盘菜单
			tray_menu = QMenu()
			
			# 显示主窗口动作
			show_action = QAction("显示主窗口", self)
			show_action.triggered.connect(self.show)
			tray_menu.addAction(show_action)
			
			# 退出动作
			quit_action = QAction("退出", self)
			quit_action.triggered.connect(QApplication.instance().quit)
			tray_menu.addAction(quit_action)
			
			# 设置托盘菜单
			self.tray_icon.setContextMenu(tray_menu)
			
			# 显示托盘图标
			self.tray_icon.show()
			
			# 设置托盘图标提示
			self.tray_icon.setToolTip("AlloyAct Pro")
	
	
	def update_status (self, message):
		"""更新状态栏消息"""
		self.status_bar.showMessage(message)
	
	def on_tab_changed (self, index):
		"""选项卡切换事件处理"""
		tab_text = self.tabs.tabText(index)
		self.update_status(f"就绪 - {tab_text}")
	
	def create_activity_tab (self):
		"""创建活度计算选项卡"""
		self.activity_widget = ActivityCalculationWidget()
		self.tabs.addTab(self.activity_widget, "活度计算")
	
	def create_interaction_tab (self):
		"""创建相互作用系数计算选项卡"""
		self.interaction_widget = InteractionCoefficientWidget(self)
		self.tabs.addTab(self.interaction_widget, "相互作用系数")
	
	def create_second_order_tab (self):
		"""创建二阶相互作用系数计算选项卡"""
		self.second_order_widget = SecondOrderCoefficientWidget(self)
		self.tabs.addTab(self.second_order_widget, "二阶相互作用系数")
	
	def show_about (self):
		"""显示关于对话框"""
		QMessageBox.about(self, "关于 AlloyAct Pro",
		                  "AlloyAct Pro 版本 1.0\n\n"
		                  "一个用于计算合金活度和相互作用系数的工具。\n\n"
		                  "版权所有 © 2025")
	

	
	


# 主程序入口
if __name__ == "__main__":
	app = QApplication(sys.argv)
	
	app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
	app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
	
	window = AlloyActGUI()
	window.show()
	sys.exit(app.exec_())