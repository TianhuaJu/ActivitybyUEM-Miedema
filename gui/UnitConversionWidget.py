import sys
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QFormLayout,
                             QLabel, QLineEdit, QPushButton, QMessageBox, QApplication, QDoubleSpinBox)
from PyQt5.QtCore import Qt

import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# 设置 Matplotlib 字体以支持中文和公式
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['mathtext.fontset'] = 'stix'
matplotlib.rcParams['mathtext.default'] = 'regular'

# 常见元素的近似摩尔质量 (g/mol)
ELEMENT_MASSES = {
	'H': 1.008, 'He': 4.003, 'Li': 6.941, 'Be': 9.012, 'B': 10.81, 'C': 12.011,
	'N': 14.007, 'O': 15.999, 'F': 18.998, 'Ne': 20.180, 'Na': 22.990, 'Mg': 24.305,
	'Al': 26.982, 'Si': 28.085, 'P': 30.974, 'S': 32.06, 'Cl': 35.45, 'Ar': 39.948,
	'K': 39.098, 'Ca': 40.078, 'Sc': 44.956, 'Ti': 47.867, 'V': 50.942, 'Cr': 51.996,
	'Mn': 54.938, 'Fe': 55.845, 'Co': 58.933, 'Ni': 58.693, 'Cu': 63.546, 'Zn': 65.38,
	'Ga': 69.723, 'Ge': 72.630, 'As': 74.922, 'Se': 78.971, 'Br': 79.904, 'Kr': 83.798,
	'Rb': 85.468, 'Sr': 87.62, 'Y': 88.906, 'Zr': 91.224, 'Nb': 92.906, 'Mo': 95.96,
	'Ru': 101.07, 'Rh': 102.91, 'Pd': 106.42, 'Ag': 107.87, 'Cd': 112.41, 'In': 114.82,
	'Sn': 118.71, 'Sb': 121.76, 'Te': 127.60, 'I': 126.90, 'W': 183.84, 'Au': 196.97,
	'Pb': 207.2, 'Bi': 208.98
}


class Element:
	def __init__ (self, name, M):
		self.name = name
		self.M = M


class MathTextCanvas(FigureCanvas):
	"""一个专门用于显示Matplotlib MathText的画布。"""
	
	def __init__ (self, parent=None, width=5, height=1, dpi=100):
		fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#f0f0f0')  # 使用更中性的背景色
		fig.patch.set_alpha(0.7)  # 背景半透明
		super(MathTextCanvas, self).__init__(fig)
		self.axes = fig.add_subplot(111)
		self.axes.set_axis_off()
		self.set_text("点击转换按钮计算结果")
	
	def set_text (self, text):
		self.axes.clear()
		self.axes.set_axis_off()
		# 渲染公式，使用深色以保证清晰度
		self.axes.text(0.5, 0.5, text,
		               horizontalalignment='center',
		               verticalalignment='center',
		               fontsize=22,
		               color='#003366')  # 深蓝色
		self.draw()


class UnitConversionWidget(QWidget):
	"""一阶相互作用系数单位转换UI，支持LaTeX渲染。"""
	
	def __init__ (self, parent=None):
		super().__init__(parent)
		self.init_ui()
	
	def init_ui (self):
		main_layout = QVBoxLayout(self)
		# --- 修改处 1: 简化 GroupBox 标题为纯文本 ---
		group_box = QGroupBox("一阶相互作用系数 单位转换")
		main_layout.addWidget(group_box)
		
		form_layout = QFormLayout(group_box)
		form_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
		form_layout.setLabelAlignment(Qt.AlignRight)
		
		self.matrix_input = QLineEdit("Fe")
		self.solute_i_input = QLineEdit("C")
		self.solute_j_input = QLineEdit("Si")
		
		self.value_input = QDoubleSpinBox()
		self.value_input.setRange(-100000, 100000)
		self.value_input.setDecimals(4)
		self.value_input.setValue(5.5)
		
		form_layout.addRow("基体 (Solvent):", self.matrix_input)
		form_layout.addRow("被影响的溶质 (i):", self.solute_i_input)
		form_layout.addRow("施加影响的溶质 (j):", self.solute_j_input)
		form_layout.addRow("待转换的系数值:", self.value_input)
		
		button_layout = QHBoxLayout()
		# --- 修改处 2: 简化按钮文字为纯文本，使用 Unicode 符号 ---
		epsilon_to_e_button = QPushButton("摩尔分数 (ε)  →  质量分数 (e)")
		e_to_epsilon_button = QPushButton("质量分数 (e)  →  摩尔分数 (ε)")
		button_layout.addWidget(epsilon_to_e_button)
		button_layout.addWidget(e_to_epsilon_button)
		form_layout.addRow(button_layout)
		
		self.result_canvas = MathTextCanvas(self)
		self.result_canvas.setMinimumHeight(80)
		form_layout.addRow(self.result_canvas)
		
		epsilon_to_e_button.clicked.connect(self.convert_epsilon_to_e)
		e_to_epsilon_button.clicked.connect(self.convert_e_to_epsilon)
	
	def _validate_and_get_elements (self):
		matrix_symbol = self.matrix_input.text().strip().capitalize()
		solute_i_symbol = self.solute_i_input.text().strip().capitalize()
		solute_j_symbol = self.solute_j_input.text().strip().capitalize()
		
		if not all([matrix_symbol, solute_i_symbol, solute_j_symbol]):
			QMessageBox.critical(self, "输入错误", "基体、溶质i 和溶质j 的元素符号均不能为空。")
			return None, None, None, None
		
		if solute_j_symbol not in ELEMENT_MASSES or solute_i_symbol not in ELEMENT_MASSES:
			QMessageBox.critical(self, "元素错误", "未找到溶质元素符号对应的摩尔质量。")
			return None, None, None, None
		
		if matrix_symbol not in ELEMENT_MASSES:
			QMessageBox.critical(self, "元素错误", f"未找到基体元素 '{matrix_symbol}' 的摩尔质量。")
			return None, None, None, None
		
		ej = Element(solute_j_symbol, ELEMENT_MASSES[solute_j_symbol])
		matrix = Element(matrix_symbol, ELEMENT_MASSES[matrix_symbol])
		
		return ej, matrix, solute_i_symbol, solute_j_symbol
	
	def convert_epsilon_to_e (self):
		ej, matrix, i_sym, j_sym = self._validate_and_get_elements()
		if not ej: return
		
		epsilon_ji = self.value_input.value()
		eji = (epsilon_ji - 1 + ej.M / matrix.M) * matrix.M / (230 * ej.M)
		
		# LaTeX 字符串生成 (这部分是正确的，并会由 Matplotlib 正确渲染)
		latex_str = r"$e_{{{}}}^{{{}}} = {:.4f}$".format(i_sym, j_sym, eji)
		self.result_canvas.set_text(latex_str)
	
	def convert_e_to_epsilon (self):
		ej, matrix, i_sym, j_sym = self._validate_and_get_elements()
		if not ej: return
		
		eji = self.value_input.value()
		epsilon_ij = 230 * eji * ej.M / matrix.M + (1 - ej.M / matrix.M)
		
		# LaTeX 字符串生成 (这部分是正确的，并会由 Matplotlib 正确渲染)
		latex_str = r"$\varepsilon_{{{}}}^{{{}}} = {:.2f}$".format(i_sym, j_sym, epsilon_ij)
		self.result_canvas.set_text(latex_str)


# 如果直接运行此文件，用于测试
if __name__ == '__main__':
	app = QApplication(sys.argv)
	app.setStyleSheet("""
        QWidget { font-size: 11pt; }
        QLineEdit, QDoubleSpinBox { padding: 6px; border: 1px solid #b8b8b8; border-radius: 4px; }
        QPushButton {
            padding: 8px 12px; background-color: #3498db; color: white;
            border: none; border-radius: 4px; font-weight: bold;
        }
        QPushButton:hover { background-color: #2980b9; }
        QGroupBox {
            font-weight: bold; border: 1px solid #b8b8b8; border-radius: 4px;
            margin-top: 10px; padding: 15px;
        }
        QGroupBox::title {
            subcontrol-origin: margin; subcontrol-position: top center; padding: 0 10px;
        }
    """)
	window = UnitConversionWidget()
	window.setWindowTitle("单位转换工具 ")
	window.resize(680, 300)
	window.show()
	sys.exit(app.exec_())