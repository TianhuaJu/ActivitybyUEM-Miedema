import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from gui.alloyact_gui import AlloyActGUI
from gui.ActivityVaryTemperatureWdget import ActivityTemperatureVariationWidget
from gui.Alloyact_GUI_Pro import AlloyActProGUI
from gui.ActivityVaryConcentrationWdget import CompositionVariationWidget

def run_gui():
    """
    设置并运行 PyQt5 图形用户界面应用程序。
    """
    # 创建应用程序实例
    app = QApplication(sys.argv)

    # 设置高 DPI 缩放支持 (与您 alloyact_gui.py 中的设置一致)
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # 创建主窗口实例
    main_window = AlloyActGUI()
    main_window_pro = AlloyActProGUI()
    
    

    # 显示窗口
    main_window_pro.show()

    # 进入应用程序事件循环
    sys.exit(app.exec_())


if __name__ == "__main__":
    # 当直接运行 Main.py 时，调用 run_gui 函数
    run_gui()