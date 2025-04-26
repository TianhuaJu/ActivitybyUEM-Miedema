import sys
import math
import re
import numpy as np
import matplotlib
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

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
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QPalette, QColor, QGuiApplication

# 导入计算模块 (确保这些文件存在)
from Activity import Element
from Activity import BinaryModel
# from Activity import TernaryMelts # Not needed for this tab
from Activity import ActivityCoefficient
from Activity import Melt # May not be needed if not comparing with experimental activity


class MplCanvas(FigureCanvas):
    """Matplotlib画布类"""
    axes: Axes

    def __init__ (self, parent=None, width=7, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)


class ActivityCalculatorGUI(QMainWindow):
    def __init__ (self):
        super().__init__()
        self.setWindowTitle("AlloyAct Pro - 活度计算器") # Modified title
        self.resize(1400, 900) # Keep original size for context
        self.setMinimumSize(1000, 900) # Keep original size

        # 新版PyQt5中将窗口居中
        qr = self.frameGeometry()
        cp = QGuiApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

        # 创建计算实例
        self.binary_model = BinaryModel()
        self.activity_coefficient = ActivityCoefficient() # Needed for activity calc

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


        # --- 只创建活度计算选项卡 ---
        # 创建一个基础的 QWidget 来容纳活度计算的布局
        activity_widget = QWidget()
        self.main_layout.addWidget(activity_widget) # Directly add the widget
        self.create_activity_tab(activity_widget) # Pass the widget to populate it
        # --- End of tab creation ---


        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("就绪 - 请输入活度计算参数")

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
        title_label = QLabel("合金热力学计算器 - 活度计算") # Modified title
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50;")

        # 版本
        version_font = QFont("Microsoft YaHei UI", 12)
        version_label = QLabel("版本 1.0 (Activity Module)") # Modified version
        version_label.setFont(version_font)
        version_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(version_label)

        self.main_layout.addLayout(title_layout)

    def update_status (self, message):
        """更新状态栏消息"""
        self.status_bar.showMessage(message)

    def create_activity_tab (self, parent_widget): # Takes parent widget to add layout
        """创建活度计算控件"""
        activity_layout = QVBoxLayout(parent_widget) # Use the passed widget's layout

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        activity_layout.addWidget(splitter)

        # 左侧输入面板
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 创建输入字段分组
        input_group = QGroupBox("输入参数")
        input_layout = QGridLayout(input_group)

        # 合金成分 (修改: 明确包含基体)
        input_layout.addWidget(QLabel("完整合金成分:"), 0, 0, Qt.AlignRight)
        self.activity_alloy_full = QLineEdit("Fe0.70C0.03Si0.27") # Example: Full composition
        input_layout.addWidget(self.activity_alloy_full, 0, 1, 1, 2) # Span 2 columns
        self.activity_alloy_full.setPlaceholderText("例如: Fe0.7C0.03Si0.27 (包含所有组分)")

        # 基体元素 (用于计算和参考)
        input_layout.addWidget(QLabel("基体元素 (参考):"), 1, 0, Qt.AlignRight)
        self.activity_solvent = QLineEdit("Fe")
        input_layout.addWidget(self.activity_solvent, 1, 1)
        self.activity_solvent.setPlaceholderText('例如: Fe')
        self.activity_solvent.setToolTip("指定用于计算的参考基体元素")

        # 溶质元素 (目标元素)
        input_layout.addWidget(QLabel("目标溶质元素 (i):"), 2, 0, Qt.AlignRight)
        self.activity_solute = QLineEdit("C")
        input_layout.addWidget(self.activity_solute, 2, 1)
        self.activity_solute.setPlaceholderText('例如: C')
        self.activity_solute.setToolTip("需要计算其活度的溶质元素")


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

        # 外推模型 (可选，因为活度计算模型是固定的)
        # input_layout.addWidget(QLabel("外推模型 (参考):"), 5, 0,Qt.AlignRight)
        # self.activity_model = QComboBox()
        # self.activity_model.addItems(["UEM1", "UEM2", "GSM", "Muggianu"]) # Keep for context if needed
        # input_layout.addWidget(self.activity_model, 5, 1)
        # self.activity_model.setEnabled(False) # Disable as it's not directly used by the 3 activity methods

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
        chart_group = QGroupBox("数据可视化 (不同模型对比)") # Clarify chart purpose
        chart_layout = QVBoxLayout(chart_group)

        self.activity_canvas = MplCanvas(self, width=5, height=4, dpi=100)
        chart_layout.addWidget(self.activity_canvas)

        # 添加结果分组和图表分组到右侧布局
        right_layout.addWidget(result_group, 1)
        right_layout.addWidget(chart_group, 1)

        # 添加左右面板到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([350, 650])  # Adjusted initial split ratio slightly

        # 初始绘制空图表
        self.init_activity_chart()


    def setup_value_labels (self, axes:matplotlib.axes.Axes, bars, values, min_height_ratio=0.1):
        """设置统一的数值标签位置, 基于Y轴范围调整"""
        y_min, y_max = axes.get_ylim()
        y_range = y_max - y_min
        if y_range == 0: y_range = 1.0 # Avoid division by zero

        min_abs_height = min_height_ratio * y_range # Minimum height to place label inside

        for i, bar in enumerate(bars):
            height = bar.get_height()
            value = values[i]
            abs_height = abs(height)

            # 确定标签位置和样式
            if abs_height >= min_abs_height and height != 0:
                # 对于较高的柱子，将标签放在柱内
                y_pos = height * 0.5 # Place in the middle
                va = 'center'
                color = 'white'
                fontweight = 'bold'
                fontsize = 9 # Smaller font inside
            else:
                # 对于较矮的柱子，将标签放在柱子上方或下方
                offset = 0.03 * y_range # Offset based on y-range
                if height >= 0:
                    y_pos = height + offset
                    va = 'bottom'
                else:
                    y_pos = height - offset
                    va = 'top'
                color = 'black'
                fontweight = 'normal'
                fontsize = 10 # Standard font outside

            axes.text(
                    bar.get_x() + bar.get_width() / 2., y_pos,
                    f'{value:.3f}', ha='center', va=va,
                    fontsize=fontsize, color=color, fontweight=fontweight
            )

    def set_fixed_y_axis(self,axes:matplotlib.axes.Axes,values, y_min_default=0.0, y_max_default=1.0):
        """设置Y轴范围，确保包含所有数据点和0，并增加边距"""
        if not values: # Handle empty data
            axes.set_ylim(y_min_default, y_max_default)
            return

        # Include 0 in the range determination
        all_points = values + [0]
        max_val = max(all_points) if all_points else y_max_default
        min_val = min(all_points) if all_points else y_min_default

        # Determine padding based on the range, ensuring it's not zero
        data_range = max_val - min_val
        padding = data_range * 0.1 if data_range > 1e-6 else 0.1 # Add padding, minimum 0.1 if range is tiny

        y_max = max_val + padding
        y_min = min_val - padding

        # Ensure min <= 0 if data includes non-positives, max >= 0 if data includes non-negatives
        if min_val < 0:
            y_min = min(y_min, min_val - padding)
        else:
            y_min = max(0, min_val - padding) # Don't go below 0 unless data is negative

        if max_val > 0:
             y_max = max(y_max, max_val + padding)
        else:
             y_max = min(0, max_val + padding) # Don't go above 0 unless data is positive


        # Ensure min < max
        if y_min >= y_max - 1e-6: # Add tolerance for floating point issues
            y_min = min_val - 0.1
            y_max = max_val + 0.1
            if y_min >= y_max: # Final fallback
                y_min = y_min_default
                y_max = y_max_default


        axes.set_ylim(y_min, y_max)



    def clear_activity_result (self):
            """清除活度计算结果"""
            self.activity_result.clear()
            self.init_activity_chart()

    def init_activity_chart (self):
        """初始化活度图表"""
        self.activity_canvas.axes.clear()
        self.activity_canvas.axes.set_title('活度计算模型对比')
        self.activity_canvas.axes.set_ylabel('活度值 ($a_i$)')
        self.activity_canvas.axes.set_xticklabels([])  # 隐藏x轴标签
        self.activity_canvas.axes.grid(True, linestyle='--', alpha=0.7)
        self.activity_canvas.fig.tight_layout()
        self.activity_canvas.draw()

    def update_activity_chart (self, results):
        """更新活度图表"""
        self.activity_canvas.axes.clear()

        # 数据
        models = ['Darken', 'Wagner', 'Elliot']
        values = [results['activity_darken'], results['activity_wagner'], results['activity_elliot']]

        # 创建柱状图
        bars = self.activity_canvas.axes.bar(models, values, color=['#3498db', '#2ecc71', '#e74c3c'])

        # 设置Y轴范围 (包含0和摩尔分数)
        all_plot_values = values + [results.get('mole_fraction', 0)]
        self.set_fixed_y_axis(self.activity_canvas.axes, all_plot_values, 0.0, 1.0)


        # 添加数值标签
        self.setup_value_labels(self.activity_canvas.axes, bars, values, min_height_ratio=0.1)


        # 设置图表属性
        solute = results.get("solute", "?")
        solvent = results.get("solvent", "?")
        self.activity_canvas.axes.set_title(f'${solute}$ 在 ${solvent}$ 基合金中的活度 ($a_{{{solute}}}$)', fontsize=14)
        self.activity_canvas.axes.set_ylabel(f'活度 ($a_{{{solute}}}$)', fontsize=13)
        self.activity_canvas.axes.grid(True, axis='y', linestyle='--', alpha=0.7)
        self.activity_canvas.axes.tick_params(axis='x', labelsize=11)

        # 添加摩尔分数参考线 (如果可用)
        mole_fraction = results.get('mole_fraction')
        if mole_fraction is not None:
            xi_val = round(mole_fraction, 3)
            self.activity_canvas.axes.axhline(y=xi_val, color='r', linestyle='--', alpha=0.6, linewidth=1.5)
            # Adjust text position based on y-axis limits
            y_min, y_max = self.activity_canvas.axes.get_ylim()
            text_y_pos = xi_val + 0.02 * (y_max - y_min) # Place text slightly above the line
            if text_y_pos > y_max * 0.95: # Avoid going too high
                text_y_pos = xi_val - 0.04 * (y_max - y_min)

            self.activity_canvas.axes.text(0.05, text_y_pos, # Position relative to x-axis
                                           f'摩尔分数 $X_{{{solute}}} = {xi_val:.3f}$',
                                           color='r', alpha=0.8, fontsize=11, ha='left')


        self.activity_canvas.fig.tight_layout(pad=1.5) # Add padding
        self.activity_canvas.draw()


    def validate_input (self, fields):
        """验证输入字段"""
        for field, name in fields:
            if not field.text().strip():
                QMessageBox.critical(self, "输入错误", f"{name}不能为空")
                return False
        return True

    def parse_composition (self, alloy_str):
        """解析合金成分字符串为字典, 并进行归一化"""
        comp_dict = {}
        # Regex to find element (1-2 letters, first capitalized) and its amount (float or int)
        pattern = r"([A-Z][a-z]?)(\d*\.?\d+|\d+)"
        matches = re.findall(pattern, alloy_str)

        if not matches:
            QMessageBox.critical(self, "成分解析错误", f"无法从 '{alloy_str}' 中解析出任何元素和含量。请使用类似 Fe0.7C0.3 的格式。")
            return None

        total = 0.0
        try:
            for element, amount_str in matches:
                if not amount_str: # Skip if amount is missing (should not happen with regex but good practice)
                    continue
                amount = float(amount_str)
                if amount < 0:
                   QMessageBox.critical(self, "成分解析错误", f"元素 '{element}' 的含量不能为负数: {amount}")
                   return None
                if element in comp_dict:
                   QMessageBox.warning(self, "成分解析警告", f"元素 '{element}' 在成分中重复出现，将使用最后一次出现的值。")
                comp_dict[element] = amount
                total += amount
        except ValueError as e:
            QMessageBox.critical(self, "成分解析错误", f"含量必须是有效的数字: {e}")
            return None

        # 归一化检查与执行
        if abs(total - 1.0) > 1e-6: # Allow small floating point inaccuracies
            if total <= 0:
                QMessageBox.critical(self, "成分解析错误", "总含量必须大于 0 才能进行归一化。")
                return None
            QMessageBox.information(self, "成分归一化", f"提供的成分总和 ({total:.4f}) 不为 1，将自动归一化。")
            for element in comp_dict:
                comp_dict[element] /= total
        elif total == 0 and len(comp_dict)>0 : # Handles case where only zero compositions were entered
             QMessageBox.critical(self, "成分解析错误", "成分总和为零。")
             return None

        if not comp_dict: # Double check if dict ended up empty
            QMessageBox.critical(self, "成分解析错误", "未能成功解析任何有效成分。")
            return None


        return comp_dict

    def get_model_function (self, model_name):
        """获取对应的二元交互作用模型函数 (活度计算本身不直接选模型，但其依赖的系数计算需要)"""
        # This function might be less relevant here if the activity methods
        # internally select or don't require a specific binary model choice from UI.
        # Kept for potential use by the ActivityCoefficient methods if they need it.
        if model_name == "UEM1":
            return self.binary_model.UEM1
        elif model_name == "UEM2":
            return self.binary_model.UEM2
        elif model_name == "GSM":
            return self.binary_model.GSM
        elif model_name == "Muggianu":
            if hasattr(self.binary_model, 'Muggianu'):
                return self.binary_model.Muggianu
            else:
                # Don't show warning here unless explicitly needed by calculation
                # QMessageBox.warning(self, "模型未实现", "Muggianu 模型当前不可用，将使用 UEM1 代替。")
                return self.binary_model.UEM1 # Fallback
        else:
            # Don't show warning here
            # QMessageBox.warning(self, "未知模型", f"未知的模型 '{model_name}'，将使用 UEM1 代替。")
            return self.binary_model.UEM1 # Default fallback

    def calculate_activity (self):
        """计算活度"""
        try:
            # 验证输入
            fields = [
                (self.activity_alloy_full, "完整合金成分"),
                (self.activity_solvent, "基体元素 (参考)"),
                (self.activity_solute, "目标溶质元素"),
                (self.activity_temp, "温度")
            ]

            if not self.validate_input(fields):
                return

            # 获取输入值
            alloy_full_str = self.activity_alloy_full.text()
            solvent = self.activity_solvent.text().strip() # Base element for reference
            solute = self.activity_solute.text().strip()   # Target element
            try:
                temp = float(self.activity_temp.text())
                if temp <= 0:
                    QMessageBox.critical(self, "输入错误", "温度必须是正数")
                    return
            except ValueError:
                QMessageBox.critical(self, "输入错误", "温度必须是数值")
                return

            state = self.activity_state.currentText()
            # model_name = self.activity_model.currentText() # Not directly used for selection here

            # 更新状态栏
            self.update_status(f"正在解析成分并计算 {solute} 在合金中的活度...")

            # 解析完整合金成分 (包含归一化)
            comp_dict = self.parse_composition(alloy_full_str)
            if comp_dict is None: # Check if parsing failed
                self.update_status("计算失败 - 成分解析错误")
                return

            # 检查目标溶质和基体是否存在于成分中
            if solute not in comp_dict:
                QMessageBox.critical(self, "输入错误", f"目标溶质元素 '{solute}' 不在提供的合金成分中。")
                self.update_status("计算失败 - 目标溶质不存在")
                return
            if solvent not in comp_dict:
                QMessageBox.warning(self, "输入警告", f"参考基体元素 '{solvent}' 不在提供的合金成分中。计算仍将进行，但请确保输入正确。")
                # Allow calculation to proceed, ActivityCoefficient should handle it

            # 获取摩尔分数
            xi = comp_dict.get(solute, 0.0) # Should exist based on check above

            # --- 模型函数获取 (可能需要，取决于ActivityCoefficient实现) ---
            # If ActivityCoefficient methods require the binary model func, uncomment:
            # dummy_model_name = "UEM1" # Or read from the (potentially disabled) combo box
            # model_func = self.get_model_function(dummy_model_name)
            # if model_func is None:
            #     self.update_status("计算失败 - 获取内部模型函数失败")
            #     return
            # --- Pass model_func to the calculation methods below if needed ---


            # 实际计算
            # Pass the full parsed composition dictionary
            self.activity_coefficient.set_composition_dict_direct(comp_dict) # Assuming a method to set dict directly

            self.update_status(f"正在计算 {solute} 活度 (模型: Darken, Wagner, Elliot)...")

            # Calculate activity coefficients (ln_gamma_i) using the three models
            # Pass None for model_func and model_name if they are not needed by the implementation
            ln_gamma_darken = self.activity_coefficient.activity_coefficient_darken(
                    comp_dict, solute, solvent, temp, state, None, None) # Pass None if model func not needed

            ln_gamma_wagner = self.activity_coefficient.activity_coefficient_wagner(
                    comp_dict, solvent, solute, temp, state, None, None) # Note order solvent, solute

            ln_gamma_elliot = self.activity_coefficient.activity_coefficient_elloit(
                    comp_dict, solute, solvent, temp, state, None, None) # Pass None if model func not needed


            # 计算活度 a_i = gamma_i * X_i
            activity_darken = math.exp(ln_gamma_darken) * xi
            activity_wagner = math.exp(ln_gamma_wagner) * xi
            activity_elliot = math.exp(ln_gamma_elliot) * xi

            # 准备结果
            results = {
                "composition_str": alloy_full_str,
                "composition_dict": comp_dict,
                "solvent": solvent, # The reference solvent entered by user
                "solute": solute,   # The target solute
                "temperature": temp,
                "state": state,
                # "model": model_name, # Not applicable for selection here
                "activity_darken": round(activity_darken, 4), # Increase precision
                "activity_wagner": round(activity_wagner, 4),
                "activity_elliot": round(activity_elliot, 4),
                "mole_fraction": round(xi, 4),
                "gamma_darken": round(math.exp(ln_gamma_darken), 4),
                "gamma_wagner": round(math.exp(ln_gamma_wagner), 4),
                "gamma_elliot": round(math.exp(ln_gamma_elliot), 4)
            }

            # 显示结果 - 添加到当前结果而不是清空
            current_text = self.activity_result.toPlainText()
            if current_text:
                result_text = f"\n{'-' * 50}\n\n"
            else:
                result_text = ""

            result_text += f"活度计算结果 (a = γ * X):\n\n"
            result_text += f"输入合金成分: {results['composition_str']}\n"
            # Optional: Show normalized composition
            comp_norm_str = ", ".join([f"{el}:{val:.4f}" for el, val in results['composition_dict'].items()])
            result_text += f"归一化成分: {comp_norm_str}\n"
            result_text += f"目标溶质 (i): {results['solute']}\n"
            result_text += f"参考基体: {results['solvent']}\n"
            result_text += f"温度: {results['temperature']} K\n"
            result_text += f"状态: {results['state']}\n"
            result_text += f"目标摩尔分数 (Xi): {results['mole_fraction']}\n\n"

            result_text += f"--- 计算结果 ---\n"
            result_text += f"模型      | 活度系数 (γi) | 活度 (ai)\n"
            result_text += f"----------|---------------|-----------\n"
            result_text += f"Darken    | {results['gamma_darken']:<13.4f} | {results['activity_darken']:.4f}\n"
            result_text += f"Wagner    | {results['gamma_wagner']:<13.4f} | {results['activity_wagner']:.4f}\n"
            result_text += f"Elliot    | {results['gamma_elliot']:<13.4f} | {results['activity_elliot']:.4f}\n"


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
            self.update_status(f"已完成 {solute} 在合金中的活度计算")

        except AttributeError as e:
             if "'ActivityCoefficient' object has no attribute 'set_composition_dict_direct'" in str(e):
                 QMessageBox.critical(self, "代码错误", "计算模块 'ActivityCoefficient' 需要 'set_composition_dict_direct' 方法来直接设置成分字典。")
             else:
                 QMessageBox.critical(self, "计算错误", f"发生属性错误: {str(e)}")
             self.update_status("计算失败 - 代码错误")
             import traceback
             traceback.print_exc()
        except Exception as e:
            QMessageBox.critical(self, "计算错误", f"计算过程中发生意外错误: {str(e)}")
            self.update_status("计算失败")
            import traceback
            traceback.print_exc() # Print detailed error for debugging


# 主程序入口
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置高DPI缩放
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    window = ActivityCalculatorGUI()
    window.show()
    sys.exit(app.exec_())