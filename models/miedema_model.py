import os
import sys
from typing import Callable, Tuple
from functools import lru_cache
import sqlite3 as sq
from core.element import Element
# ===============================================================
# 缓存装饰器：避免重复查询数据库
# ===============================================================




class MiedemaModel:
	"""
	创建Miedema模型表示的二元系性质计算器。
	"""
	
	# 用于数值微分的微小变化量
	_NUMERICAL_DELTA = 1e-7
	
	def __init__ (self, composition: Tuple[str, str], phase: str, database_path: str = None):
		
		c1 = composition[0].capitalize()
		c2 = composition[1].capitalize()
		self.component1, self.component2 = c1, c2
		
		
		self.A = Element(self.component1)
		self.B = Element(self.component2)
		
		# 修正：存储原始相，并确定相状态（LIQUID/SOLID）
		self.phase = phase
		if phase.upper() in ("LIQUID", "L"):
			self.phase_state = "LIQUID"
		else:
			self.phase_state = "SOLID"
	
	def set_X (self, xA: float, xB: float):
		# 修正：set_X 在原始代码中未被使用，但保留
		self.xA = xA / (xA + xB)
		self.xB = xB / (xA + xB)
	
	def _fab (self):
		"""计算化学相互作用项 df"""
		element_A = self.A
		element_B = self.B
		
		# _fab 依赖于 self.phase_state, 这是在 __init__ 中设置的
		if self.phase_state == "LIQUID":
			alpha = 0.73
		else:
			alpha = 1.0
		
		# [修改] 属性名称更新: alpha_beta -> hybrid_factor, hybirdvalue -> hybrid_value
		r_to_p = 0.0 if (element_A.hybrid_factor == "other" or element_B.hybrid_factor == "other") else \
			(0.0 if (
					element_A.hybrid_factor == element_B.hybrid_factor) else alpha * element_A.hybrid_value * element_B.hybrid_value)
		
		# [修改] 属性名称更新: isTrans -> is_trans_group
		p_AB = 14.2 if element_A.is_trans_group and element_B.is_trans_group else 12.35 if element_A.is_trans_group or element_B.is_trans_group else 10.7
		
		# [修改] 属性名称更新: nws -> n_ws
		df = 2.0 * p_AB * (
				-pow(element_A.phi - element_B.phi, 2.0) + 9.4 * pow(element_A.n_ws - element_B.n_ws, 2.0) - r_to_p) \
		     / (1.0 / element_A.n_ws + 1.0 / element_B.n_ws)
		
		return df
	
	def _V_in_alloy (self, xA: float, xB: float, order_degree: float):
		"""
		合金中组元的体积（迭代计算）
		注意：此处的 order_degree 是数值（lamada）
		"""
		total_x = xA + xB
		if total_x == 0:
			# [修改] 属性名称更新: V -> v
			return self.A.v, self.B.v
		
		xA_norm = xA / total_x
		xB_norm = xB / total_x
		
		# [修改] 属性名称更新: V -> v
		V_old_a = self.A.v
		V_old_b = self.B.v
		
		V_new_a = 0.0
		V_new_b = 0.0
		
		max_iterations = 100
		iteration_count = 0
		
		while (V_new_a != V_old_a or V_new_b != V_old_b) and iteration_count < max_iterations:
			iteration_count += 1
			
			if iteration_count > 1:
				V_old_a = V_new_a
				V_old_b = V_new_b
			
			# 避免除以零
			denominator = (xB_norm * V_old_b + xA_norm * V_old_a)
			if denominator == 0:
				Pax, Pbx = 0.5, 0.5  # 假设等贡献
			else:
				Pax = xA_norm * V_old_a / denominator
				Pbx = xB_norm * V_old_b / denominator
			
			# [修改] 属性名称更新: V -> v (注意 Element 类中是小写的 v)
			# 注意: self.A.u 保持不变
			V_new_a = self.A.v * (
					1.0 + self.A.u * Pbx * (1.0 + order_degree * pow(Pax * Pbx, 2.0)) * (self.A.phi - self.B.phi))
			V_new_b = self.B.v * (
					1.0 + self.B.u * Pax * (1.0 + order_degree * pow(Pax * Pbx, 2.0)) * (self.B.phi - self.A.phi))
			
			if V_new_a == V_old_a and V_new_b == V_old_b:
				break
		
		return V_new_a, V_new_b
	
	# ================================================================
	# =================== 积分性质（还原为原始签名） ===================
	# ================================================================
	
	def getmixingEnthalpy_by_Miedema_Model (self, component: str, x_component: float, temp: float, order_degree='SS'):
		"""
		计算Miedema模型混合焓 (Hmix)。
		Hmix 与温度无关。

		Args:
			component: 组分
			x_component: 组分组成比
			order_degree: 1.0 for 'SS'(无序相), 5.0 for 'AMP'(多晶相), 8.0 for 'IM'(有序相)
		@return: Miedema模型计算的生成焓
		"""
		
		# 还原：根据 component 判断 xA 和 xB
		# 注意：这里依赖 self.A.name，而不是 self.component1
		if component == self.A.name:
			xA = x_component
			xB = 1.0 - x_component
		else:
			xA = 1.0 - x_component
			xB = x_component
		
		A_el = self.A
		B_el = self.B
		
		# 修正：将 order_degree 字符串转换为数值 lamada
		if order_degree == 'SS':
			lamada = 0.0
		elif order_degree == 'AMP':
			lamada = 5.0
		elif order_degree == 'IM':
			lamada = 8.0
		else:
			# 假设传入的是数值
			try:
				lamada = float(order_degree)
			except ValueError:
				lamada = 0.0  # 默认
		
		# 归一化摩尔分数（带除零保护）
		x_sum = xA + xB
		if x_sum < 1e-15:
			return 0.0
		x1 = xA / x_sum
		x2 = xB / x_sum
		xA, xB = x1, x2
		
		df = self._fab()
		
		V_Aa, V_Ba = self._V_in_alloy(xA, xB, lamada)
		
		# 避免除以零
		denominator = (xA * V_Aa + xB * V_Ba)
		if denominator == 0:
			return 0.0  # 体积为零，焓变为零
		
		cAs = xA * V_Aa / denominator
		cBs = xB * V_Ba / denominator
		fC = (cAs * cBs * (1.0 + lamada * pow(cAs * cBs, 2.0))) * denominator
		
		# [修改] 属性名称更新: dHtrans -> dh_trans
		dH_trans = xA * A_el.dh_trans + xB * B_el.dh_trans
		
		return (fC * df + dH_trans) * 1000
	
	def _get_excess_entropy (self, component: str, x_component: float, tem=298.15, order_degree='SS'):
		"""
		采用Tanaka过剩熵关系式计算过剩熵 (sE)。
		"""
		Ei = self.A
		Ej = self.B
		
		# 还原：调用还原后的 getmixingEnthalpy...
		# 修正：Hmix 不依赖 tem
		Hmix = self.getmixingEnthalpy_by_Miedema_Model(component, x_component, tem, order_degree)
		
		# [修改] 属性名称更新: Tm -> tm
		if self.phase_state == 'LIQUID':
			excess_entropy = 1.0 / 14 * (1.0 / Ei.tm + 1.0 / Ej.tm) * Hmix
		else:
			excess_entropy = 1.0 / 15.1 * (1.0 / Ei.tm + 1.0 / Ej.tm) * Hmix
		return excess_entropy
	
	def get_excess_Gibbs (self, component: str, x_component: float, tem=298.15, order_degree='SS'):
		"""
		计算二元合金混合过剩吉布斯自由能 (gE)。
		"""
		# 还原：调用还原后的 Hmix 和 sE
		# 修正：Hmix 不依赖 tem
		Hmix = self.getmixingEnthalpy_by_Miedema_Model(component, x_component, tem, order_degree)
		sE = self._get_excess_entropy(component, x_component, tem, order_degree)
		
		g_E = Hmix - tem * sE
		return g_E
	
	# ================================================================
	# =================== 偏摩尔性质（修复原始设计） ===================
	# ================================================================
	
	def _calculate_numerical_partial_property (
			self,
			integral_func: Callable,
			target_component: str,
			x_target: float,
			temp, order_degree='SS'
	) -> float:
		"""
		使用中心差分法进行数值微分，计算偏摩尔性质。
		这是 miedema_model.py 内部的辅助函数。
		"""
		
		delta = self._NUMERICAL_DELTA
		
		def get_Y (x_A_val):
			"""安全地获取积分性质值"""
			if x_A_val < 0: x_A_val = 0
			if x_A_val > 1: x_A_val = 1
			x_B_val = 1.0 - x_A_val
			try:
				return integral_func(target_component, x_A_val, temp, order_degree)
			except Exception as e:
				raise RuntimeError(f"Miedema积分函数(wrapper)计算失败: {e}")
		
		try:
			if target_component == self.component1:
				xA = x_target
			else:  # target_component == self.component2
				xA = 1.0 - x_target  # 总是以 A 为基准
			
			Y_mix = get_Y(xA)
			
			# 中心差分法计算导数 dY_mix / dx_A
			if xA < delta:  # 接近 xA=0，使用前向差分
				Y_plus = get_Y(xA + delta)
				deriv = (Y_plus - Y_mix) / delta
			elif xA > 1.0 - delta:  # 接近 xA=1，使用后向差分
				Y_minus = get_Y(xA - delta)
				deriv = (Y_mix - Y_minus) / delta
			else:  # 使用中心差分
				Y_plus = get_Y(xA + delta)
				Y_minus = get_Y(xA - delta)
				deriv = (Y_plus - Y_minus) / (2 * delta)
			
			# Gibbs-Duhem 方程计算偏摩尔性质
			if target_component == self.component1:
				return Y_mix + (1.0 - xA) * deriv
			else:  # target_component == self.component2
				return Y_mix - xA * deriv
		
		except Exception as e:
			raise e
	
	def get_partial_molar_enthalpy (
			self,
			target_component: str,
			x_target: float,
			tem: float,
			order_degree: str = 'SS'
	) -> float:
		"""
		使用 Miedema 模型计算偏摩尔混合焓 (数值微分法)。
		"""
		
		# *args 将是 (phase_state, order_degree)
		return self._calculate_numerical_partial_property(
				self.getmixingEnthalpy_by_Miedema_Model,
				target_component, x_target,
				tem, order_degree
		)
	
	def get_partial_molar_gibbs (
			self,
			target_component: str,
			x_target: float,
			tem: float,
			order_degree: str = 'SS'
	) -> float:
		"""
		使用 Miedema 模型计算偏摩尔过剩吉布斯自由能 (数值微分法)。
		"""
		
		# *args 将是 (Tem, phase_state, order_degree)
		return self._calculate_numerical_partial_property(
				self.get_excess_Gibbs,  # 传递包装器
				target_component, x_target,
				tem, order_degree
		)
	
	# ================================================================
	# =================== 无限稀释（解析解） ===================
	# ================================================================
	
	def get_infinite_dilution_enthalpy (
			self,
			target_component: str,
			order_degree: str = 'IM'
	) -> float:
		"""
		计算 Miedema 模型的无限稀释混合焓 (x_target -> 0)。
		"""
		A_el = self.A
		B_el = self.B
		
		df = self._fab()
		
		# 修正：使用 self.component1/2 检查 target_component
		if target_component == self.component1:  # A 溶于 B
			solutei = A_el
			solvent = B_el
		else:  # B 溶于 A
			solutei = B_el
			solvent = A_el
		
		elements_lst = ["Si", "Ge"]
		if self.phase_state == 'LIQUID':
			# [修改] 属性名称更新: dHtrans -> dh_trans
			dhtrans_i = 0 if solutei.name in elements_lst else solutei.dh_trans
			dhtrans_slv = 0 if solvent.name in elements_lst else solvent.dh_trans
		else:
			dhtrans_i = solutei.dh_trans
			dhtrans_slv = solvent.dh_trans
		
		dhtrans = dhtrans_i - dhtrans_slv
		
		# [修改] 属性名称更新: V -> v
		limit_partial_enthalpy = 1000 * df * solutei.v * (1 + solutei.u * (solutei.phi - solvent.phi)) + 1000 * dhtrans
		
		return limit_partial_enthalpy
	
	def get_infinite_dilution_gibbs (
			self,
			target_component: str,
			Tem: float,
			order_degree: str = 'IM'
	) -> float:
		"""
		计算 Miedema 模型的无限稀释过剩 gE (x_target -> 0)。
		"""
		A_el = self.A
		B_el = self.B
		
		# 修正：确保 _fab() 和 S_factor 使用的是传入的 phase_state
		df_H = self._fab()
		
		# [修改] 属性名称更新: Tm -> tm
		if self.phase_state == 'LIQUID':
			S_factor = 1.0 / 14 * (1.0 / A_el.tm + 1.0 / B_el.tm)
		else:
			S_factor = 1.0 / 15.1 * (1.0 / A_el.tm + 1.0 / B_el.tm)
		
		df_G = df_H * (1 - Tem * S_factor)
		
		# 修正：使用 self.component1/2 检查 target_component
		if target_component == self.component1:  # A 溶于 B
			solutei = A_el
			solvent = B_el
		else:  # B 溶于 A
			solutei = B_el
			solvent = A_el
		
		elements_lst = ["Si", "Ge"]
		if self.phase_state == 'LIQUID':
			# [修改] 属性名称更新: dHtrans -> dh_trans
			dhtrans_i = 0 if solutei.name in elements_lst else solutei.dh_trans
			dhtrans_slv = 0 if solvent.name in elements_lst else solvent.dh_trans
		else:
			dhtrans_i = solutei.dh_trans
			dhtrans_slv = solvent.dh_trans
		
		dhtrans = dhtrans_i - dhtrans_slv
		
		# [修改] 属性名称更新: V -> v
		limit_partial_gibbs = 1000 * df_G * solutei.v * (1 + solutei.u * (solutei.phi - solvent.phi)) + 1000 * dhtrans
		
		return limit_partial_gibbs