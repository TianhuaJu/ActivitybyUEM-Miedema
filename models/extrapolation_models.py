# extrapolation_models.py

import math
from typing import Callable

from scipy import integrate
from core.constants import Constants
from core.element import Element
import mpmath





class BinaryModel:
	"""处理二元体系的热力学计算。"""
	
	def __init__ (self):
		self._temperature = 1873
		
		self._ea = None
		self._eb = None
		self._state = "liquid"
		self._lambda = 0
		
		self._is_entropy = False
		
		self.yeta_dict = {}
		self.df_uem2 = {}
		self.df_uem2adv_x = {}
		self.df_uem2adv_y = {}
		self.df_uem2adv_a = {}
	
	def set_temperature (self, temp):
		self._temperature = temp
	
	def set_pair_element (self, element_a, element_b):
		self._ea = Element(element_a)
		self._eb = Element(element_b)
	
	def set_state (self, state):
		self._state = state
	
	def set_lambda (self, n):
		self._lambda = n
	
	def set_entropy (self, is_se):
		self._is_entropy = is_se

	def fab (self, ea:Element, eb:Element, state):
		"""计算 Miedema 模型中的 Fab 值。"""
		if not (ea.is_exist and eb.is_exist): return float('nan')
		
		
		p_ab = Constants.P_TT if (ea.is_trans_group and eb.is_trans_group) else \
			(Constants.P_TN if (ea.is_trans_group or eb.is_trans_group) else Constants.P_NN)
		rp_value = self.rp(ea, eb, state)
		diff = 2 * p_ab * (-(ea.phi - eb.phi) ** 2 + Constants.QtoP * (ea.n_ws - eb.n_ws) ** 2 - rp_value) / \
		       (1.0 / ea.n_ws + 1.0 / eb.n_ws)
		return diff
	
	def rp (self, ea, eb, state):
		"""计算 Miedema 模型中的 RP 项。"""
		alpha = 1.0 if state == "solid" else 0.73
		if ea.hybrid_factor == "other" or eb.hybrid_factor == "other": return 0.0
		return 0.0 if ea.hybrid_factor == eb.hybrid_factor else alpha * ea.hybrid_value * eb.hybrid_value
	
	def v_in_alloy (self, ea, eb, xa, xb):
		"""计算合金中的体积。xa+xb=1"""
		ya = xa / (xa + xb)
		yb = xb / (xa + xb)
		
		vaa = ea.v
		vba = eb.v
		
		if ea.name == "H" or eb.name == "H":
			max_iterations = 1000
			for _ in range(max_iterations):
				new_vaa, new_vba = vaa, vba
				pax = ya * vaa / (ya * vaa + yb * vba)
				pbx = yb * vba / (ya * vaa + yb * vba)
				vaa = ea.v * (1 + ea.u * pbx * (1 + self._lambda * (pax * pbx) ** 2) * (ea.phi - eb.phi))
				vba = eb.v * (1 + eb.u * pax * (1 + self._lambda * (pax * pbx) ** 2) * (eb.phi - ea.phi))
				if abs(vaa - new_vaa) < 1e-6 and abs(vba - new_vba) < 1e-6: break
		else:
			vaa = ea.v * (1 + ea.u * ya * (ea.phi - eb.phi))
			vba = eb.v * (1 + eb.u * yb * (eb.phi - ea.phi))
		return vaa, vba
	
	def binary_model (self, a, b, xa, xb):
		"""二元模型计算。"""
		self.set_pair_element(a, b)
		f_ab = self.fab(self._ea, self._eb, self._state)
		entropy_term = 0
		
		if self._is_entropy:
			if self._ea.tm and self._eb.tm:  # Avoid division by zero
				avg_tm = 1.0 / self._ea.tm + 1.0 / self._eb.tm
				factor = 15.1 if self._state == "solid" else 14.0
				entropy_term = 1.0 / factor * avg_tm * self._temperature
			else:
				entropy_term = 0.0
		
		f_ab *= (1 - entropy_term)
		vaa, vba = self.v_in_alloy(self._ea, self._eb, xa, xb)
		ca = xa / (xa + xb)
		cb = xb / (xa + xb)
		if (ca * vaa + cb * vba) == 0: return 0.0  # Avoid division by zero
		cas = ca * vaa / (ca * vaa + cb * vba)
		cbs = cb * vba / (ca * vaa + cb * vba)
		fb = cbs * (1 + self._lambda * (cas * cbs) ** 2)
		dh_trans_a = 0
		dh_trans_b = 0
		if self._state == "liquid":
			if self._ea.name not in ["Si", "Ge"]:
				dh_trans_a = self._ea.dh_trans
			if self._eb.name not in ["Si", "Ge"]:
				dh_trans_b = self._eb.dh_trans
		dh_trans = dh_trans_a * ca + dh_trans_b * cb
		
		return fb * f_ab * ca * vaa + dh_trans
	
	def elastic_a_in_b (self, a, b):
		"""计算固溶体相的弹性项。"""
		self.set_pair_element(a, b)
		if not (self._ea.n_ws and self._eb.n_ws): return float('nan')
		
		alpha = -6.0 * self._ea.v * (1 + self._ea.u * (self._ea.phi - self._eb.phi)) / \
		        (1.0 / self._ea.n_ws + 1.0 / self._eb.n_ws)
		va = self._ea.v ** 1.5 + alpha * (self._eb.phi - self._ea.phi) / self._ea.n_ws ** 3
		vb = self._eb.v ** 1.5 + alpha * (self._eb.phi - self._ea.phi) / self._eb.n_ws ** 3
		
		if (3 * self._ea.bkm * vb + 4 * self._eb.shm * va) == 0: return float('nan')
		dhe = 2 * self._ea.bkm * self._eb.shm * (vb - va) ** 2 / (3 * self._ea.bkm * vb + 4 * self._eb.shm * va)
		return 1e-9 * dhe
	
	
	
	def integrate_miedema_mpmath_arbitrary_precision (self, model: Callable[[float], float],  decimal_places=30):
		"""
		使用 mpmath 库以任意精度对 Miedema 二元模型进行积分。

		此函数适用于对积分精度有极高要求的场景。

		参数:
		model: Miedema 模型的实例对象。
		e1: 组分1的 Element 对象。
		e2: 组分2的 Element 对象。
		decimal_places (int): 计算结果需要精确到的小数位数，默认为30位。

		返回:
		float: 积分结果，以标准浮点数形式返回。
		"""
		# 设置 mpmath 的计算精度
		mpmath.mp.dps = decimal_places
	
		
		# 使用 mpmath.quad 进行高精度积分
		# 注意：mpmath.quad 的返回值是 mpmath 的浮点数类型
		integral_value_mp = mpmath.quad(model, [0, 1])
		
		# 将结果转换为标准的 Python 浮点数后返回
		return float(integral_value_mp)
	
	
	def yeta (self, k, a, b, temp: float, state: str):
		"""计算 GSM 的相似系数。"""
		m1 = BinaryModel()
		m2 = BinaryModel()
		m1.set_state(state)
		m2.set_state(state)
		m1.set_temperature(temp)
		m2.set_temperature(temp)
		m1.set_entropy(True)
		m2.set_entropy(True)
		
		key = k + a + b + str(temp) + state
		if key in self.yeta_dict: return self.yeta_dict[key]
		
		func = lambda x: m1.binary_model(a, b, x, 1 - x) - m2.binary_model(a, k, x, 1 - x)
		func2 = lambda x: func(x) ** 2
		result = self.integrate_miedema_mpmath_arbitrary_precision(func2,30)
		self.yeta_dict[key] = result
		return result
	
	def _get_dki_uem2 (self, k: str, i: str, j: str, t: float):
		
		mij = BinaryModel()
		mkj = BinaryModel()
		
		# Conditional entropy setting based on element names
		non_entropy_elements = {"H", "O", "N"}
		mij.set_entropy(not (i in non_entropy_elements or j in non_entropy_elements))
		mkj.set_entropy(not (k in non_entropy_elements or j in non_entropy_elements))
		
		mij.set_pair_element(i, j)
		mij.set_state("liquid")
		mij.set_temperature(t)
		
		mkj.set_pair_element(k, j)
		mkj.set_state("liquid")
		mkj.set_temperature(t)
		
		def get_integral (model_instance, e1_name, e2_name):
			# Cache key includes all relevant parameters
			key = f"{e1_name}-{e2_name}-{model_instance._lambda}-{model_instance._state}-{t}"
			if key in self.df_uem2:
				return self.df_uem2[key]
			
			func = lambda x: model_instance.binary_model(e1_name, e2_name, x, 1 - x) * 1000 / (Constants.R * t)
			f_val = self.integrate_miedema_mpmath_arbitrary_precision(func, 30)
			self.df_uem2[key] = f_val
			return f_val
		
		f_ij = get_integral(mij, i, j)
		f_kj = get_integral(mkj, k, j)
		
		denominator = f_ij + f_kj
		if denominator == 0:
			return float('inf')
		
		return abs((f_ij - f_kj) / denominator)
	
	def get_graphic_center (self, k, i, T: float, phase_state="liquid"):
		"""计算函数图像的中心坐标 (x, y)。"""
		mki = BinaryModel()
		mki.set_entropy(True)
		mki.set_pair_element(i, k)
		mki.set_state(phase_state)  # Use passed phase_state
		mki.set_temperature(self._temperature)
		
		key = i + k + str(self._lambda) + phase_state + str(self._temperature)
		
		if key in self.df_uem2adv_x:
			x_bar = self.df_uem2adv_x[key]
			a = self.df_uem2adv_a[key]
			y = self.df_uem2adv_y[key]
		else:
			func_x = lambda x: mki.binary_model(k, i, x, 1 - x) * 1000
			xfunc_x = lambda x: x * func_x(x)
			func_x2 = lambda x: func_x(x) * func_x(x)
			x_bar = integrate.quad(xfunc_x, 0, 1)[0]
			a = integrate.quad(func_x, 0, 1)[0]
			y = integrate.quad(func_x2, 0, 1)[0]
			self.df_uem2adv_x[key] = x_bar
			self.df_uem2adv_a[key] = a
			self.df_uem2adv_y[key] = y
		
		x_ = x_bar / a if a != 0 else 0
		y_ = y / (2.0 * a) if a != 0 else 0
		return (x_ - 0.5, y_)
	
	def delta_x (self, x, y):
		"""get_d_ki 的辅助函数。"""
		pi_half = math.pi / 2.0
		pi = math.pi
		ax, ay = abs(x), abs(y)
		if (0 <= ax <= pi_half and 0 <= ay <= pi_half) or \
				(pi_half <= ax <= pi and pi_half <= ay <= pi):
			return 0
		else:
			return pi_half
	
	def get_d_ki (self, k, i, j,T: float, phase_state: str):
		"""计算组元 k 和 i 之间的属性差异。"""
		xij, yij = self.get_graphic_center(i, j, T,phase_state)
		xkj, ykj = self.get_graphic_center(k, j, T,phase_state)
		
		theta10 = math.atan2(xij, yij)
		theta20 = math.atan2(xkj, ykj)
		a = math.sqrt(xij ** 2 + yij ** 2)
		b = math.sqrt(xkj ** 2 + ykj ** 2)
		
		denom1 = (theta10 ** 2 + theta20 ** 2)
		denom2 = math.sqrt(a ** 2 + b ** 2)
		
		if denom1 == 0 or denom2 == 0: return float('inf')
		
		dki = abs((math.pi / 2.0 * (theta10 ** 2 - theta20 ** 2) + self.delta_x(theta10, theta20)) / denom1) * \
		      abs(a - b) / denom2
		return dki
	
	def kexi (self, solvent, solutei):
		"""Calculate ξ^k_i for UEM1 model
			previous method for trans-ennergy for nonmetalic is rigly according to the method in doctor Thesis
			In some previouscalculation, parameter for C is modified
			 which is from the " Statiscal Thermodynamics of Alloys" by N. A. Gokcen
		"""
		fik = self.fab(solvent, solutei,self._state)
		elements_lst = ["Si", "Ge"]
		
		if self._state == "liquid":
			if solutei.name in elements_lst:
				dhtrans_i = 0
			else:
				dhtrans_i = solutei.dh_trans
			
			if solvent.name in elements_lst:
				dhtrans_slv = 0
			else:
				dhtrans_slv = solvent.dh_trans
		else:
			dhtrans_i = 0
			dhtrans_slv = 0
		
		dhtrans = dhtrans_i - dhtrans_slv
		
		lny0 = 1000 * fik * solutei.v * (1 + solutei.u * (solutei.phi - solvent.phi)) / \
		       (Constants.R * self._temperature) + 1000 * dhtrans / (Constants.R * self._temperature)
		
		return lny0
	def _asym_component_choice (self, k: str, i: str, j: str, Tem: float, phase_state: str):
		"""Qiao's 不对称组元选择规则。"""
		self.set_state(phase_state)
		self.set_temperature(Tem)
		self.set_entropy(True)
		bij = self.binary_model(i, j, 0.5, 0.5)
		bik = self.binary_model(i, k, 0.5, 0.5)
		bjk = self.binary_model(k, j, 0.5, 0.5)
		
		if (bij > 0 and bik > 0 and bjk > 0) or (bij < 0 and bik < 0 and bjk < 0):
			enthalpies = {k: abs(bij), j: abs(bik), i: abs(bjk)}
			return min(enthalpies, key=enthalpies.get)
		else:
			if bij * bik > 0:
				return i
			elif bij * bjk > 0:
				return j
			else:
				return k
	
	def UEM1 (self, k, i, j, Tem: float, phase_state: str):
		"""UEM1 模型实现。"""
		
		inter_ik = self.kexi(Element(k), Element(i))
		inter_ki = self.kexi(Element(i), Element(k))
		inter_jk = self.kexi(Element(k), Element(j))
		inter_kj = self.kexi(Element(j), Element(k))
		df_ki = abs(inter_ik - inter_ki)
		df_kj = abs(inter_jk - inter_kj)
		if df_ki + df_kj == 0: return 0.5  # Avoid division by zero
		alpha = math.exp(-df_ki)
		beta3 = df_kj / (df_ki + df_kj)
		return alpha * beta3
	
	
	def UEM2 (self, k, i, j, Tem: float, phase_state: str):
		"""UEM2 模型实现，采用新的偏差函数计算方法。"""
		
		df_ki = self._get_dki_uem2(k, i, j, Tem)
		df_kj = self._get_dki_uem2(k, j, i, Tem)
		
		denominator = df_ki + df_kj
		if denominator == 0:
			return 0.5
		
		weight1 = df_kj / denominator
		return math.exp(-df_ki) * weight1
	
	def GSM (self, k, i, j, Tem: float, phase_state: str):
		"""GSM 模型实现。"""
		nki = self.yeta(k, i, j, Tem, phase_state)
		nkj = self.yeta(k, j, i, Tem, phase_state)
		return nki / (nki + nkj) if (nki + nkj) != 0 else 0.5
	
	def Muggianu (self, k, i, j, Tem: float, phase_state: str):
		return 0.5
	
	def Toop_Muggianu (self, k, i, j, Tem: float, phase_state: str):
		asym = self._asym_component_choice(k, i, j, Tem, phase_state)
		if k == asym:
			return 0.5
		elif i == asym:
			return 0.0
		else:
			return 1.0
	
	def Toop_Kohler (self, k: str, i: str, j: str, T: float, phase_state: str):
		asym = self._asym_component_choice(k, i, j, T, phase_state)
		return 0.0 if asym == k or asym == i else 1.0
	
	def UEM2_Adv(self, k: str, i: str, j: str, T: float, phase_state: str):
		
		d_ki = self.get_d_ki(k,i,j, T,phase_state)
		d_kj = self.get_d_ki(k,j,i, T,phase_state)
		
		return d_kj/(d_ki + d_kj)*math.exp(-d_ki)
		
		pass
	