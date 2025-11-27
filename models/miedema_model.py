import math
import numpy as np
from typing import Tuple, Optional, Union
from functools import lru_cache
from dataclasses import dataclass
from core.properties_estimator import get_properties_estimator
# 导入您的 Element 类
try:
	from core.element import Element
except ImportError:
	import sys
	import os
	
	sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
	from core.element import Element


# ===============================================================
# 常量定义 (基于 Cohesion in Metals, 1988)
# ===============================================================
@dataclass
class MiedemaConstants:
	# --- 基础 Miedema 参数 ---
	Q_over_P: float = 9.4
	P_TRANSITION: float = 14.1  # 两个过渡金属
	P_NON_TRANSITION: float = 10.6  # 两个非过渡金属
	P_MIXED: float = 12.3  # 过渡金属 + 非过渡金属
	
	# --- R/P 常数 (p-d 杂化修正项) ---
	# 针对过渡金属(TM)与多价非过渡金属(NTM)的合金
	# 数据来源: [cite: 2207-2221] (Fig 2.28 衍生数据)
	RP_RATIOS = {
		'H': 3.9, 'B': 1.9, 'C': 2.1, 'N': 2.3,
		'Si': 2.1, 'Ge': 2.1, 'Sn': 2.1, 'Pb': 2.1,
		'P': 2.3, 'As': 2.3, 'Sb': 2.3, 'Bi': 2.3,
		'Al': 1.9, 'Ga': 1.9, 'In': 1.9, 'Tl': 1.9,
		'Zn': 1.4, 'Cd': 1.4, 'Hg': 1.4,
		'Be': 0.4, 'Mg': 0.4, 'Li': 0.0, 'Na': 0.0, 'K': 0.0
	}
	
	# --- 转换焓 (Transformation Enthalpy) [kJ/mol] ---
	# 将非金属元素从参考态(气体/共价晶体)转变为假想金属态所需的能量
	# 数据来源:  (Table II-2)
	TRANS_ENTHALPIES = {
		'H': 100,
		'B': 30,
		'C': 180,  # 石墨 -> 金属碳
		'N': 310,  # 1/2 N2 -> 金属氮 (非常大，阻碍固溶)
		'Si': 34,
		'Ge': 25,
		'P': 17
	}
	
	DEFAULT_SF_METAL = 9.6
	
	# --- 弹性模量兜底数据 (Bulk K, Shear G) [GPa] ---
	# 用于计算固溶体弹性错配能
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
		'Be': (130.0, 132.0), 'Ca': (17.0, 7.4), 'B': (320.0, 170.0)
	}


@lru_cache(maxsize=128)
def get_element_cached (symbol: str) -> Element:
	return Element(symbol)


class MiedemaModel:
	"""
	Miedema 模型完整实现。

	物理特性支持：
	1. 转换焓 (Transformation Enthalpy): 仅对固相(化合物/固溶体)的非金属元素应用。
	   液相视为金属态，不应用转换焓。适用于 Si, Ge, C, N, P, B, H。
	2. 原子尺寸修正 (Sun's Correction): 仅对 TM-TM 系统应用。
	3. 弹性错配能 (Elastic Mismatch): 仅对固溶体应用。
	4. 有序化效应: 仅对化合物应用。
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
		
		self.is_TM_A = self._is_transition_metal(self.A)
		self.is_TM_B = self._is_transition_metal(self.B)
		self.apply_sun_correction = self.is_TM_A and self.is_TM_B
	
	def calculate_enthalpy (self, fraction_solute: float, T: float = 298.15) -> float:
		"""计算形成焓 Delta H (J/mol)"""
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
		H_interface = self._calculate_interface_enthalpy(self.A, self.B)
		
		# Sun's Correction (仅 TM-TM)
		correction_S = 1.0
		if self.apply_sun_correction:
			denom_size = cS_A * V23_A + cS_B * V23_B
			if denom_size > 1e-9:
				correction_S = 1.0 - (math.sqrt(cS_A * cS_B) * abs(V23_A - V23_B)) / denom_size
		
		# 4. 化学项
		f_B_A = cS_B
		if self.phase_type == 'compound':
			# 有序增强
			f_B_A *= (1.0 + 8.0 * (cS_A * cS_B) ** 2)
		
		H_chem = cA * f_B_A * H_interface * V23_A * correction_S
		
		# 5. 转换焓 (Transformation Enthalpy)
		# 【关键逻辑】：液相豁免
		# 对 B, C, N, Si, Ge, P 等元素，液相不加转换焓。
		# 固相（固溶体或化合物）必须加。
		H_trans = 0.0
		if self.phase_type != 'liquid':
			# 获取转换焓，如果元素是金属则为0
			dh_a = self.consts.TRANS_ENTHALPIES.get(self.A.name, 0.0)
			dh_b = self.consts.TRANS_ENTHALPIES.get(self.B.name, 0.0)
			# 如果 Element 对象本身加载了 dh_trans (数据库值)，优先使用
			# 但要注意数据库可能没存，或者存了0。这里做个兼容。
			if abs(self.A.dh_trans) > 1e-3: dh_a = self.A.dh_trans
			if abs(self.B.dh_trans) > 1e-3: dh_b = self.B.dh_trans
			
			H_trans = cA * dh_a + cB * dh_b
		
		# 6. 弹性能 (仅固溶体)
		H_elastic = 0.0
		if self.phase_type == 'solid_solution':
			H_elastic = self._calculate_elastic_mismatch(cA, cB)
		
		# 汇总 (单位转换为 J/mol)
		return (H_chem + H_trans + H_elastic) * 1000.0
	
	def estimate_fusion_entropy (self, fraction_solute: float) -> float:
		"""
		预测熔化熵 Delta Sf (J/mol/K)
		"""
		cA = fraction_solute
		cB = 1.0 - cA
		estimator = get_properties_estimator()
		# 1. 纯组元熔化熵 (动态获取)
		props_A = estimator.get_element_properties(self.A.name)
		props_B = estimator.get_element_properties(self.B.name)
		
		Sf_A = props_A['Sf']
		Sf_B = props_B['Sf']
		
		S_weighted = cA * Sf_A + cB * Sf_B
		
		# 构型熵贡献 (有序->无序)
		S_mix = 0.0
		if cA > 1e-9 and cB > 1e-9:
			R = 8.314
			S_mix = -R * (cA * math.log(cA) + cB * math.log(cB))
		
		return S_weighted + S_mix
	
	def _is_transition_metal (self, elem: Element) -> bool:
		tm_list = ['Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd',
		           'Ag', 'La', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au']
		return elem.name in tm_list or (hasattr(elem, 'is_trans_group') and elem.is_trans_group)
	
	def _calculate_interface_enthalpy (self, elem_i: Element, elem_j: Element) -> float:
		n_i = elem_i.n_ws ** (1.0 / 3.0);
		n_j = elem_j.n_ws ** (1.0 / 3.0)
		phi_i = elem_i.phi;
		phi_j = elem_j.phi
		P = self._determine_P(elem_i, elem_j)
		R = self._determine_R(elem_i, elem_j, P)
		Q = self.consts.Q_over_P * P
		den = 1.0 / n_i + 1.0 / n_j
		if den == 0: return 0.0
		return 2.0 * (-P * (phi_i - phi_j) ** 2 + Q * (n_i - n_j) ** 2 - R) / den
	
	def _calculate_elastic_mismatch (self, cA: float, cB: float) -> float:
		def get_term (sol, solv):
			# 获取模量，优先对象属性，其次查表
			K = getattr(sol, 'bkm', 0)
			G = getattr(solv, 'shm', 0)
			if K < 1e-6: K = self.consts.ELASTIC_DATA.get(sol.name, (0, 0))[0]
			if G < 1e-6: G = self.consts.ELASTIC_DATA.get(solv.name, (0, 0))[1]
			if K < 1e-6 or G < 1e-6: return 0.0
			
			# 体积修正系数 alpha (0.04-0.14)
			alpha = 0.07
			# 电负性差导致的体积变化
			dV_chem = alpha * (solv.phi - sol.phi) / (sol.n_ws if sol.n_ws > 0 else 1.0)
			
			# 有效体积差
			dV = (sol.v + dV_chem) - solv.v
			
			num = 2 * K * G * dV ** 2
			den = 3 * K * solv.v + 4 * G * sol.v
			return num / den if den != 0 else 0.0
		
		return cA * cB * (cB * get_term(self.A, self.B) + cA * get_term(self.B, self.A))
	
	def _determine_P (self, ei, ej):
		tm_a = self._is_transition_metal(ei);
		tm_b = self._is_transition_metal(ej)
		if tm_a and tm_b:
			return self.consts.P_TRANSITION
		elif not tm_a and not tm_b:
			return self.consts.P_NON_TRANSITION
		return self.consts.P_MIXED
	
	def _determine_R (self, ei, ej, P):
		tm_a = self._is_transition_metal(ei)
		tm_b = self._is_transition_metal(ej)
		if (tm_a and tm_b) or (not tm_a and not tm_b): return 0.0
		ntm = ei if not tm_a else ej
		# 优先使用 hybrid_value
		if hasattr(ntm, 'hybrid_value') and ntm.hybrid_value > 0: return ntm.hybrid_value * P
		return self.consts.RP_RATIOS.get(ntm.name, 0.0) * P
	
	# ... (兼容旧接口保持不变) ...
	def getmixingEnthalpy_by_Miedema_Model (self, c, x, t=298.15):
		xA = x if c == self.A.name else 1 - x
		return self.calculate_enthalpy(xA, t)
	
	def get_excess_Gibbs (self, component: str, x_component: float, temp: float = 298.15) -> float:
		"""
		计算过剩吉布斯自由能 G_ex (J/mol)

		修改策略：
		1. 固相/化合物：保持 Tanaka 模型 (考虑有序化带来的低熵)
		2. 液相：强制 S_ex = 0 (理想熵)，或大幅降低 Tanaka 系数
		"""
		H_mix = self.getmixingEnthalpy_by_Miedema_Model(component, x_component, temp)
		
		# 默认过剩熵为 0 (理想溶液假设)
		S_ex = 0.0
		
		# 仅对固相应用 Tanaka 过剩熵 (有序化导致熵减)
		# 对于液相，假设高温下接近理想混合 (S_ex ~ 0)，避免过度惩罚液相稳定性
		if self.phase_type != 'liquid':
			# Tanaka 经验公式: S_ex = alpha * (1/Tm_A + 1/Tm_B) * H_mix
			# alpha: Solid=1/15.1
			alpha = 1.0 / 15.1
			
			Tm_A = self.A.tm if self.A.tm > 0 else 1000.0
			Tm_B = self.B.tm if self.B.tm > 0 else 1000.0
			
			S_ex = alpha * (1.0 / Tm_A + 1.0 / Tm_B) * H_mix
		
		# 如果您仍想保留液相的 Tanaka 项但减弱其影响，
		# 可以取消注释下面几行，并使用更小的 alpha (如 1/30)
		# elif self.phase_type == 'liquid':
		#     alpha = 1.0 / 30.0 # 减弱系数
		#     Tm_A = self.A.tm if self.A.tm > 0 else 1000.0
		#     Tm_B = self.B.tm if self.B.tm > 0 else 1000.0
		#     S_ex = alpha * (1.0/Tm_A + 1.0/Tm_B) * H_mix
		
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