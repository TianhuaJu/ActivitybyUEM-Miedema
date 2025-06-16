import os
import sys
from datetime import datetime  # <--- 添加了 datetime 的全局导入

import matplotlib
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.utils import *
from gui.UnitConversionWidget import UnitConversionWidget

# Set matplotlib font settings
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'FangSong', 'SimSun', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['font.size'] = 12
matplotlib.rcParams['text.usetex'] = False
matplotlib.rcParams['mathtext.default'] = 'regular'

# Import PyQt5 modules
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QLabel, QLineEdit, QComboBox, QPushButton,
                             QTabWidget, QFrame, QGroupBox, QTextEdit, QMessageBox,
                             QStatusBar, QAction, QSystemTrayIcon, QMenu)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QGuiApplication, QIcon

# 导入计算模块
from models.extrapolation_models import BinaryModel
from calculations.activity_calculator import ActivityCoefficient

# 导入新的界面组件
from gui.ActivityVaryTemperatureWdget import ActivityTemperatureVariationWidget
from gui.ActivityVaryConcentrationWdget import CompositionVariationWidget
from gui.ActivityVaryConcentrationWdget2 import AlloyAdditionWidget
from gui.data_ui import DatabaseManagerTab
from gui.ActivityCalculationWidget import ActivityCalculationWidget
from gui.InteractionCoefficientWidget import InteractionCoefficientWidget
from gui.SecondOrderCoefficientWidget import SecondOrderCoefficientWidget


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
		self.conversion_window = None
		# 设置应用字体
		self.app_font = QFont("Microsoft YaHei UI", 12)
		QApplication.setFont(self.app_font)
		
		# 创建界面
		self.setup_ui()
		self.setup_menu_bar()
		self.set_global_styles()
		self.setup_icon()
		self.setup_tray_icon()
	
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
		self.create_AlloyAdditionWidget()
		self.create_database_mangner_tabs()
		
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
	
	# self.main_layout.addLayout(title_layout)
	
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
	def create_database_mangner_tabs (self):
		self.database_widget = DatabaseManagerTab(self)
		self.tabs.addTab(self.database_widget, "数据管理")
	def create_concentration_variation_tab (self):
		"""创建浓度变化分析选项卡"""
		# 创建浓度变化分析组件实例
		self.conc_variation_widget = CompositionVariationWidget(self)
		
		# 添加到选项卡
		self.tabs.addTab(self.conc_variation_widget, "浓度变化分析")
	
	def create_AlloyAdditionWidget(self):
		self.AlloyAdditionWidget = AlloyAdditionWidget(self)
		tab_index = self.tabs.addTab(self.AlloyAdditionWidget,"浓度变化分析2")
		self.tabs.setTabToolTip(tab_index,
		                        "Alloy Element Addition Effect Calculator\nFixed base alloy composition, study the effect of adding elements on target component activity/activity coefficient")

	def create_activity_tab (self):
		"""创建活度计算选项卡"""
		self.activity_widget = ActivityCalculationWidget(self)
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
        <li>多种外推模型支持 (UEM1, UEM2, GSM, Muggianu, etc)</li>
        </ul>
        <p><b>开发团队:</b> 合金热力学计算实验室</p>
        <p><b>技术支持:</b> <a href="mailto:jutianhua@gxu.edu.cn">jutianhua@gxu.edu.cn</a></p>
        """
		QMessageBox.about(self, "关于 AlloyAct Pro", about_text)
		
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
		# from datetime import datetime # datetime 已在模块顶部导入
		timestamp = datetime.now().strftime("%H:%M:%S")
		self.status_bar.showMessage(f"[{timestamp}] {message}")
	
	def on_tab_changed (self, index):
		"""选项卡切换事件处理"""
		tab_text = self.tabs.tabText(index)
		self.update_status(f"切换到 {tab_text} 模块")
		
	
	def setup_icon (self):
		icon_path = self.get_resource_path('resources/app_ico_Alloyact_Pro.png')
		if os.path.exists(icon_path):
			
			self.setWindowIcon(QIcon(icon_path))
	
	def setup_tray_icon (self):
		"""设置系统托盘图标"""
		if QSystemTrayIcon.isSystemTrayAvailable():
			self.tray_icon = QSystemTrayIcon(self)
			
			# 设置托盘图标
			icon_path = self.get_resource_path('resources/app_ico_Alloyact_Pro.png')
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
	
	def get_resource_path (self, relative_path):
		"""获取资源文件路径"""
		try:
			base_path = sys._MEIPASS
		except AttributeError:
			base_path = os.path.abspath(".")
		return os.path.join(base_path, relative_path)
		


def main ():
	"""主程序入口"""
	app = QApplication(sys.argv)
	
	# 设置应用程序属性
	app.setApplicationName("AlloyAct Pro")
	app.setApplicationVersion("2.0")
	app.setOrganizationName("Material Science Lab")
	
	# 设置高DPI缩放 (Qt 5.6+). AA_EnableHighDpiScaling 是推荐的方式
	if hasattr(Qt, 'AA_EnableHighDpiScaling'):
		QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
	if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
		QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
	
	# 创建并显示主窗口
	window = AlloyActProGUI()
	window.show()
	
	return app.exec_()


if __name__ == "__main__":
	# 确保 core, models, calculations, gui 目录在 Python 路径中
	# 或者将它们放在与此脚本相同的目录中
	sys.exit(main())