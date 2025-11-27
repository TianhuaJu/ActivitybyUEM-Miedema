import os
import sys
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QApplication, QSplashScreen

from gui.Alloyact_GUI_Pro import AlloyActProGUI


def get_resource_path (relative_path):
	"""获取资源文件路径"""
	try:
		base_path = sys._MEIPASS
	except AttributeError:
		base_path = os.path.abspath(".")
	return os.path.join(base_path, relative_path)


def run_gui ():
	"""
	设置并运行 PyQt5 图形用户界面应用程序。
	"""
	# 创建应用程序实例
	app = QApplication(sys.argv)
	
	# 设置高 DPI 缩放支持
	app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
	app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
	
	# 设置应用程序图标
	icon_path = get_resource_path('resources/AlloyActApp.ico')
	if os.path.exists(icon_path):
		app.setWindowIcon(QIcon(icon_path))
	
	# === 创建启动画面 ===
	splash = None
	splash_path = get_resource_path('resources/splash.png')
	
	if os.path.exists(splash_path):
		# 创建启动画面
		splash_pixmap = QPixmap(splash_path)
		splash = QSplashScreen(splash_pixmap, Qt.WindowStaysOnTopHint)
		
		# 设置启动画面样式
		splash.setMask(splash_pixmap.mask())
		splash.show()
		
		# 显示加载信息
		splash.showMessage(
				"正在加载 AlloyThermocal Pro...",
				Qt.AlignBottom | Qt.AlignCenter,
				Qt.white
		)
		
		# 处理事件，确保启动画面显示
		app.processEvents()
		
		# 模拟加载时间（可选）
		time.sleep(1)
	
	# === 创建主窗口 ===
	try:
		# 更新启动画面信息
		if splash:
			splash.showMessage(
					"正在初始化界面组件...",
					Qt.AlignBottom | Qt.AlignCenter,
					Qt.white
			)
			app.processEvents()
		
		# 创建主窗口实例
		main_window_pro = AlloyActProGUI()
		
		# 设置窗口图标
		if os.path.exists(icon_path):
			main_window_pro.setWindowIcon(QIcon(icon_path))
		
		# 更新启动画面
		if splash:
			splash.showMessage(
					"启动完成！",
					Qt.AlignBottom | Qt.AlignCenter,
					Qt.white
			)
			app.processEvents()
			time.sleep(0.5)
		
		# 显示主窗口
		main_window_pro.show()
		
		# 关闭启动画面
		if splash:
			splash.finish(main_window_pro)
	
	except Exception as e:
		# 如果出错，确保关闭启动画面
		if splash:
			splash.close()
		
		# 显示错误信息
		from PyQt5.QtWidgets import QMessageBox
		QMessageBox.critical(None, "启动错误", f"应用程序启动失败:\n{str(e)}")
		sys.exit(1)
	
	# 进入应用程序事件循环
	sys.exit(app.exec_())


def run_gui_with_timer ():
	"""
	使用定时器的启动画面版本（更流畅的用户体验）
	"""
	app = QApplication(sys.argv)
	app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
	app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
	
	# 设置应用程序图标
	icon_path = get_resource_path('resources/app_icon.ico')
	if os.path.exists(icon_path):
		app.setWindowIcon(QIcon(icon_path))
	
	# 创建启动画面
	splash = None
	splash_path = get_resource_path('resources/splash.png')
	
	if os.path.exists(splash_path):
		splash_pixmap = QPixmap(splash_path)
		splash = QSplashScreen(splash_pixmap, Qt.WindowStaysOnTopHint)
		splash.show()
		
		# 启动加载进度
		messages = [
			"正在加载核心模块...",
			"正在初始化数据库...",
			"正在加载界面组件...",
			"正在准备计算引擎...",
			"启动完成！"
		]
		
		progress = 0
		
		def update_splash ():
			nonlocal progress
			if progress < len(messages):
				splash.showMessage(
						messages[progress],
						Qt.AlignBottom | Qt.AlignCenter,
						Qt.white
				)
				progress += 1
				app.processEvents()
			else:
				# 加载完成，创建主窗口
				timer.stop()
				initialize_main_window()
		
		def initialize_main_window ():
			try:
				main_window_pro = AlloyActProGUI()
				if os.path.exists(icon_path):
					main_window_pro.setWindowIcon(QIcon(icon_path))
				
				main_window_pro.show()
				if splash:
					splash.finish(main_window_pro)
			
			except Exception as e:
				if splash:
					splash.close()
				from PyQt5.QtWidgets import QMessageBox
				QMessageBox.critical(None, "启动错误", f"应用程序启动失败:\n{str(e)}")
				sys.exit(1)
		
		# 创建定时器
		timer = QTimer()
		timer.timeout.connect(update_splash)
		timer.start(500)  # 每500ms更新一次
	
	else:
		# 没有启动画面图片时，创建默认启动画面或直接启动
		try:
			# 尝试创建默认启动画面
			splash_widget = create_default_splash()
			splash_widget.show()
			app.processEvents()
			time.sleep(2)  # 显示2秒
			splash_widget.close()
		except:
			# 如果默认启动画面也失败，直接启动
			pass
		
		# 直接启动主窗口
		try:
			main_window_pro = AlloyActProGUI()
			if os.path.exists(icon_path):
				main_window_pro.setWindowIcon(QIcon(icon_path))
			main_window_pro.show()
		except Exception as e:
			from PyQt5.QtWidgets import QMessageBox
			QMessageBox.critical(None, "启动错误", f"应用程序启动失败:\n{str(e)}")
			sys.exit(1)
	
	sys.exit(app.exec_())


def create_default_splash ():
	"""
	如果没有启动画面图片，创建一个简单的默认启动画面
	"""
	from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget
	from PyQt5.QtCore import Qt
	from PyQt5.QtGui import QFont
	
	splash_widget = QWidget()
	splash_widget.setFixedSize(400, 300)
	splash_widget.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
	
	layout = QVBoxLayout(splash_widget)
	layout.setAlignment(Qt.AlignCenter)
	
	# 标题
	title_label = QLabel("AlloyThermoCal Pro")
	title_label.setAlignment(Qt.AlignCenter)
	title_label.setFont(QFont("Arial", 24, QFont.Bold))
	title_label.setStyleSheet("color: #2C3E50; margin: 20px;")
	
	# 副标题
	subtitle_label = QLabel("合金活度计算专业版")
	subtitle_label.setAlignment(Qt.AlignCenter)
	subtitle_label.setFont(QFont("Arial", 12))
	subtitle_label.setStyleSheet("color: #7F8C8D; margin: 10px;")
	
	# 状态信息
	status_label = QLabel("正在加载...")
	status_label.setAlignment(Qt.AlignCenter)
	status_label.setFont(QFont("Arial", 10))
	status_label.setStyleSheet("color: #95A5A6; margin: 20px;")
	
	layout.addWidget(title_label)
	layout.addWidget(subtitle_label)
	layout.addWidget(status_label)
	
	# 设置背景
	splash_widget.setStyleSheet("""
        QWidget {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #ECF0F1, stop:1 #BDC3C7);
            border-radius: 10px;
        }
    """)
	
	return splash_widget


if __name__ == "__main__":
	# 选择启动方式
	# run_gui()           # 简单启动画面版本
	run_gui_with_timer()  # 带进度的启动画面版本（推荐）

# ==========================================
# 📋 启动画面资源文件要求
# ==========================================
#
# 1. 启动画面图片：resources/splash.png
#    - 推荐尺寸：400x300 或 600x400 像素
#    - 格式：PNG（支持透明背景）
#    - 内容：应用程序 Logo + 名称
#
# 2. 应用图标：resources/app_icon.ico
#    - 格式：ICO 文件
#    - 尺寸：包含多种尺寸（16x16, 32x32, 48x48, 256x256）
#
# 3. 示例启动画面设计要素：
#    - 应用程序名称：AlloyThermoCal Pro
#    - Logo 或图标
#    - 版本信息
#    - 公司/组织名称
#    - 优雅的背景色彩

# ==========================================
# 🎨 创建启动画面的 Python 代码示例
# ==========================================
