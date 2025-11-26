import math
import numpy as np
from typing import Tuple, Optional, Union
from functools import lru_cache
from dataclasses import dataclass

# 导入您的 Element 类
try:
	from core.element import Element
except ImportError:
	import sys
	import os
	
	sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
	from core.element import Element


# ===============================================================
# 常量定义 (基于 Cohesion in Metals, 1988 及 Sun et al. 2011)
# ===============================================================
@dataclass
class MiedemaConstants:
	# --- 基础 Miedema 参数 ---
	Q_over_P: float = 9.4
	P_TRANSITION: float = 14.1  # 两个过渡金属
	P_NON_TRANSITION: float = 10.6  # 两个非过渡金属
	P_MIXED: float = 12.3  # 过渡金属 + 非过渡金属
	
	# --- R/P 常数 (p-d 杂化修正项) ---
	RP_RATIOS = {
		'H': 3.9, 'B': 1.9, 'C': 2.1, 'N': 2.3,
		'Si': 2.1, 'Ge': 2.1, 'Sn': 2.1, 'Pb': 2.1,
		'P': 2.3, 'As': 2.3, 'Sb': 2.3, 'Bi': 2.3
	}
	
	# --- 转换焓 (kJ/mol) ---
	TRANS_ENTHALPIES = {
		'H': 100, 'B': 30, 'C': 180,
		'Si': 34, 'Ge': 25, 'N': 310, 'P': 17
	}
	
	# --- 内置弹性模量库 (单位: GPa) ---
	ELASTIC_DATA = {
		'Fe': (170.0, 82.0), 'Si': (100.0, 65.0), 'C': (33.0, 10.0),
		'Al': (76.0, 26.0), 'Cu': (140.0, 48.0), 'Mg': (45.0, 17.0),
		'Ni': (180.0, 76.0), 'Ti': (110.0, 44.0), 'Cr': (160.0, 115.0),
		'Mn': (120.0, 75.0), 'Mo': (230.0, 120.0), 'W': (310.0, 160.0),
		'V': (160.0, 47.0), 'Co': (180.0, 75.0), 'Zr': (83.0, 33.0),
		'Nb': (170.0, 38.0), 'Zn': (70.0, 43.0), 'Pb': (46.0, 5.6),
		'Sn': (58.0, 18.0), 'Ag': (100.0, 30.0), 'Au': (180.0, 27.0),
		'Pt': (230.0, 61.0), 'Pd': (180.0, 44.0), 'Ta': (200.0, 69.0),
		'Hf': (110.0, 30.0), 'Re': (370.0, 178.0), 'Ru': (220.0, 173.0),
		'Ir': (320.0, 210.0), 'Os': (462.0, 222.0), 'Rh': (270.0, 150.0),
		'Y': (41.0, 25.0), 'La': (28.0, 15.0), 'Ce': (22.0, 14.0),
		'Li': (11.0, 4.2), 'Na': (6.3, 3.3), 'K': (3.1, 1.3),
		'Be': (130.0, 132.0), 'Ca': (17.0, 7.4)
	}


# ===============================================================
# 缓存装饰器
# ===============================================================
@lru_cache(maxsize=128)
def get_element_cached (symbol: str) -> Element:
	return Element(symbol)


class MiedemaModel:
	"""
	Miedema 模型完整实现。
	特性：
	1. 智能应用 Sun et al. (2011) 修正（仅针对 TM-TM 体系）。
	2. 内置弹性模量库，解决固溶体相分离问题。
	"""
	
	_NUMERICAL_DELTA = 1e-6
	
	def __init__ (self, composition: Tuple[str, str], phase: str = "LIQUID"):
		self.comp1_name, self.comp2_name = composition
		self.A = get_element_cached(self.comp1_name)
		self.B = get_element_cached(self.comp2_name)
		self.consts = MiedemaConstants()
		
		self.phase_name = phase.upper()
		if self.phase_name in ["LIQUID", "L"]:
			self.phase_type = "liquid"
		elif self.phase_name in ["COMPOUND", "ORDERED"]:
			self.phase_type = "compound"
		else:
			self.phase_type = "solid_solution"
		
		# 预先判断是否适用 Sun's Correction
		# 仅适用于两个过渡金属 (TM-TM)
		self.is_TM_A = self._is_transition_metal(self.A)
		self.is_TM_B = self._is_transition_metal(self.B)
		self.apply_sun_correction = self.is_TM_A and self.is_TM_B
	
	def calculate_enthalpy (self, fraction_solute: float, T: float = 298.15) -> float:
		cA = fraction_solute
		cB = 1.0 - cA
		
		if cA <= 1e-9 or cB <= 1e-9: return 0.0
		if not (self.A.is_exist and self.B.is_exist): return 0.0
		
		# 1. 摩尔体积项 V^(2/3)
		V23_A = self.A.v ** (2.0 / 3.0)
		V23_B = self.B.v ** (2.0 / 3.0)
		
		# 2. 表面浓度
		denom = cA * V23_A + cB * V23_B
		if denom == 0: return 0.0
		cS_A = (cA * V23_A) / denom
		cS_B = (cB * V23_B) / denom
		
		# 3. 界面焓
		H_interface_A_in_B = self._calculate_interface_enthalpy(self.A, self.B)
		
		# === Sun's Correction (原子尺寸修正因子) ===
		# 仅在 TM-TM 系统中应用，防止对 Fe-Si 等 TM-NonTM 系统过度惩罚
		correction_S = 1.0
		if self.apply_sun_correction:
			denom_size_factor = cS_A * V23_A + cS_B * V23_B
			if denom_size_factor > 1e-9:
				size_mismatch_term = abs(V23_A - V23_B)
				correction_S = 1.0 - (math.sqrt(cS_A * cS_B) * size_mismatch_term) / denom_size_factor
		
		# 4. 化学贡献
		f_B_A = 0.0
		if self.phase_type == 'compound':
			ordering_factor = 1.0 + 8.0 * (cS_A * cS_B) ** 2
			f_B_A = cS_B * ordering_factor
		else:  # liquid or solid_solution (unordered base)
			f_B_A = cS_B
		
		H_chem = cA * f_B_A * H_interface_A_in_B * V23_A * correction_S
		
		# 5. 转换焓
		H_trans = cA * self.A.dh_trans + cB * self.B.dh_trans
		
		# 6. 弹性错配能 (仅固溶体)
		H_elastic = 0.0
		if self.phase_type == 'solid_solution':
			H_elastic = self._calculate_elastic_mismatch(cA, cB)
		
		total_H_kJ = H_chem + H_trans + H_elastic
		return total_H_kJ * 1000.0
	
	def _is_transition_metal (self, elem: Element) -> bool:
		"""
		判断是否为过渡金属 (用于决定模型参数选择)
		包括传统过渡金属及贵金属 Cu, Ag, Au
		"""
		# 如果数据库有 is_trans_group 标记
		if hasattr(elem, 'is_trans_group') and elem.is_trans_group:
			return True
		# 兜底名单
		tm_list = [
			'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu',
			'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag',
			'La', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au'
		]
		return elem.name in tm_list
	
	def _calculate_interface_enthalpy (self, elem_i: Element, elem_j: Element) -> float:
		n_i = elem_i.n_ws ** (1.0 / 3.0)
		n_j = elem_j.n_ws ** (1.0 / 3.0)
		phi_i = elem_i.phi
		phi_j = elem_j.phi
		
		P = self._determine_P()
		R = self._determine_R(P)
		Q = self.consts.Q_over_P * P
		
		term1 = -P * (phi_i - phi_j) ** 2
		term2 = Q * (n_i - n_j) ** 2
		term3 = -R
		
		den = 1.0 / n_i + 1.0 / n_j
		if den == 0: return 0.0
		
		return 2.0 * (term1 + term2 + term3) / den
	
	def _calculate_elastic_mismatch (self, cA: float, cB: float) -> float:
		def get_elastic_term (solute: Element, solvent: Element) -> float:
			K_solute = getattr(solute, 'bkm', 0.0)
			G_solvent = getattr(solvent, 'shm', 0.0)
			
			if K_solute <= 1e-6:
				vals = self.consts.ELASTIC_DATA.get(solute.name)
				K_solute = vals[0] if vals else 0.0
			if G_solvent <= 1e-6:
				vals = self.consts.ELASTIC_DATA.get(solvent.name)
				G_solvent = vals[1] if vals else 0.0
			
			if K_solute <= 1e-6 or G_solvent <= 1e-6: return 0.0
			
			alpha = 0.07
			V_solute = solute.v
			V_solvent = solvent.v
			
			d_phi = solvent.phi - solute.phi
			
			if solute.n_ws > 0:
				W_A = V_solute + alpha * d_phi / solute.n_ws
			else:
				W_A = V_solute
			W_B = V_solvent
			dW = W_B - W_A
			
			num = 2 * K_solute * G_solvent * (dW) ** 2
			den = 3 * K_solute * W_B + 4 * G_solvent * W_A
			
			if den == 0: return 0.0
			return num / den
		
		E_A_in_B = get_elastic_term(self.A, self.B)
		E_B_in_A = get_elastic_term(self.B, self.A)
		return cA * cB * (cB * E_A_in_B + cA * E_B_in_A)
	
	def _determine_P (self) -> float:
		if self.is_TM_A and self.is_TM_B:
			return self.consts.P_TRANSITION
		elif not self.is_TM_A and not self.is_TM_B:
			return self.consts.P_NON_TRANSITION
		else:
			return self.consts.P_MIXED
	
	def _determine_R (self, P: float) -> float:
		# 只有混合类型才有 R*
		if (self.is_TM_A and self.is_TM_B) or (not self.is_TM_A and not self.is_TM_B):
			return 0.0
		
		ntm = self.A if not self.is_TM_A else self.B
		
		if hasattr(ntm, 'hybrid_value') and ntm.hybrid_value > 0:
			return ntm.hybrid_value * P
		
		ratio = self.consts.RP_RATIOS.get(ntm.name, 0.0)
		return ratio * P
	
	# ... (兼容旧接口代码保持不变，省略以节省空间) ...
	def getmixingEnthalpy_by_Miedema_Model (self, component: str, x_component: float, temp: float = 298.15) -> float:
		if component == self.A.name:
			xA = x_component
		elif component == self.B.name:
			xA = 1.0 - x_component
		else:
			return 0.0
		return self.calculate_enthalpy(xA, temp)
	
	def get_excess_Gibbs (self, component: str, x_component: float, temp: float = 298.15) -> float:
		H_mix = self.getmixingEnthalpy_by_Miedema_Model(component, x_component, temp)
		alpha = 1.0 / 14.0 if self.phase_type == 'liquid' else 1.0 / 15.1
		Tm_A = self.A.tm if self.A.tm > 0 else 1000.0
		Tm_B = self.B.tm if self.B.tm > 0 else 1000.0
		if abs(H_mix) < 1e-9: return 0.0
		S_ex = alpha * (1.0 / Tm_A + 1.0 / Tm_B) * H_mix
		return H_mix - temp * S_ex
	
	def get_partial_molar_property (self, target_component: str, x_target: float, T: float,
	                                prop_type: str = 'G') -> float:
		delta = self._NUMERICAL_DELTA
		
		def integral_func (x_A_val):
			x_A_val = max(0.0, min(1.0, x_A_val))
			if prop_type == 'H':
				return self.calculate_enthalpy(x_A_val, T)
			else:
				return self.get_excess_Gibbs(self.A.name, x_A_val, T)
		
		if target_component == self.A.name:
			xA = x_target
		else:
			xA = 1.0 - x_target
		Y_mix = integral_func(xA)
		if xA < delta:
			deriv = (integral_func(xA + delta) - Y_mix) / delta
		elif xA > 1.0 - delta:
			deriv = (Y_mix - integral_func(xA - delta)) / delta
		else:
			deriv = (integral_func(xA + delta) - integral_func(xA - delta)) / (2 * delta)
		if target_component == self.A.name:
			return Y_mix + (1.0 - xA) * deriv
		else:
			return Y_mix - xA * deriv