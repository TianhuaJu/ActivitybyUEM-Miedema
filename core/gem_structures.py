import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

# 引入新的 Miedema 模型
from models.miedema_model import MiedemaModel


class ThermodynamicPhase(ABC):
	"""
	GEM 算法通用的相接口抽象基类。
	"""
	
	def __init__ (self, name: str, components: List[str], phase_type: str):
		self.name = name
		self.components = sorted(components)  # 确保元素顺序一致 ['C', 'Fe', 'Si']
		self.phase_type = phase_type  # 'liquid', 'solid_solution', 'compound'
	
	@abstractmethod
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		"""计算摩尔吉布斯自由能 (J/mol)"""
		pass
	
	def get_composition_array (self, composition_dict: Dict[str, float]) -> np.ndarray:
		"""辅助函数：将字典转换为按 components 排序的数组"""
		return np.array([composition_dict.get(c, 0.0) for c in self.components])
	
	def get_composition (self) -> Dict[str, float]:
		"""返回默认成分（对于化合物有用，溶体则返回空或默认）"""
		return {}


class SolutionPhase(ThermodynamicPhase):
	"""
	溶体相封装 (如 LIQUID, FCC_A1, BCC_A2)。

	能量计算公式：
	G_total = G_ref + G_ideal + G_excess

	1. G_ref: 纯组元吉布斯能 (来自 TDB)
	2. G_ideal: 理想混合熵 (RT * sum(x * ln x))
	3. G_excess: 过剩混合能 (来自新的 MiedemaModel，包含化学+弹性+结构项)
	"""
	
	def __init__ (self,
	              name: str,
	              components: List[str],
	              calculator_instance):
		
		# 自动识别相类型
		p_type = 'solid_solution'
		if 'LIQUID' in name.upper() or 'L' == name.upper():
			p_type = 'liquid'
		
		super().__init__(name, components, phase_type=p_type)
		self.calculator = calculator_instance
		
		# 缓存二元模型实例，避免重复创建
		self._binary_models = {}
	
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		# 1. 归一化成分
		total_moles = sum(composition.values())
		if total_moles < 1e-12: return 0.0
		X = {k: v / total_moles for k, v in composition.items()}
		
		G_ref = 0.0
		G_ideal = 0.0
		G_excess = 0.0
		R = 8.314462618
		
		# 2. 计算 G_ref (纯组元能量) 和 G_ideal (理想混合熵)
		for elem, x_i in X.items():
			if x_i < 1e-12: continue
			
			# A. G_ref (从 TDB 获取)
			# 优先尝试获取该元素在当前相中的能量
			# 如果 TDB 中没有该元素在当前相的参数 (如 C in BCC)，则尝试估算或返回 None
			g_pure = self.calculator.tdb_parser.get_gibbs_energy(elem, self.name, temperature)
			
			if g_pure is None:
				# 只有当相是 LIQUID 时，我们才假设完全互溶并使用 LIQUID 能量
				# 对于固相，如果 TDB 没定义，说明该元素极难溶入 (如 Fe -> Graphite)
				if self.phase_type == 'liquid':
					g_pure = self.calculator.tdb_parser.get_gibbs_energy(elem, 'LIQUID', temperature)
				
				# 如果仍然没有，或者不是液相，则施加惩罚 (说明该相不稳定)
				if g_pure is None:
					return 1e9  # 巨大的正能量，迫使求解器放弃此相
			
			G_ref += x_i * g_pure
			
			# B. G_ideal
			G_ideal += x_i * np.log(x_i)
		
		G_ideal *= R * temperature
		
		# 3. 计算 G_excess (Miedema 模型)
		# 采用 Muggianu 几何外推法处理三元/多元系:
		# G_ex = Sum_{i<j} [ (4 * xi * xj) / (xi + xj)^2 ] * G_binary((xi+xj)/2) * (xi + xj) ???
		# 简化版 Muggianu (Redlich-Kister style summation):
		# G_ex = Sum_{i<j} x_i * x_j * Interaction_Parameter
		# 但 Miedema 的 G_ex 不是常数。
		# 我们使用: Sum_{i<j} (xi + xj) * G_binary_excess(u_i, u_j)
		# 其中 u_i = xi / (xi + xj)
		
		elements = sorted(list(X.keys()))
		n_elems = len(elements)
		
		for i in range(n_elems):
			for j in range(i + 1, n_elems):
				el_i = elements[i]
				el_j = elements[j]
				xi = X[el_i]
				xj = X[el_j]
				
				x_sum = xi + xj
				if x_sum < 1e-9: continue
				
				# 二元系中的相对摩尔分数
				u_i = xi / x_sum
				
				# 获取或创建 Miedema 模型
				model_key = tuple(sorted((el_i, el_j)))
				if model_key not in self._binary_models:
					# 传入当前相类型 (liquid 或 solid_solution)
					# 这决定了是否包含弹性畸变能
					self._binary_models[model_key] = MiedemaModel(model_key, phase=self.phase_type)
				
				model = self._binary_models[model_key]
				
				# 计算二元过剩吉布斯能 (J/mol)
				# 注意: u_i 是 el_i 在二元系中的分数
				g_ex_bin = model.get_excess_Gibbs(el_i, u_i, temperature)
				
				# 累加到总过剩能 (Muggianu 权重)
				G_excess += x_sum * g_ex_bin
		
		return G_ref + G_ideal + G_excess


class StoichiometricCompound(ThermodynamicPhase):
	"""
	定比化合物 (如 SiC, Fe3C) 或 Miedema 预测的虚拟化合物。
	使用 MiedemaModel(phase='COMPOUND') 进行计算。
	"""
	
	def __init__ (self,
	              name: str,
	              fixed_composition: Dict[str, float]):
		
		components = list(fixed_composition.keys())
		super().__init__(name, components, phase_type='Stoichiometric')
		self.fixed_composition = fixed_composition
		
		# 初始化 Miedema 模型用于计算形成能
		# 假设化合物是二元的 (目前大多数预测仅针对二元)
		if len(components) == 2:
			self.model = MiedemaModel((components[0], components[1]), phase='COMPOUND')
		else:
			self.model = None  # 多元化合物暂不支持直接预测，需手动指定能量函数
	
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		# 对于化合物，忽略输入的 composition (它是固定的)
		
		if not self.model:
			return 0.0  # 或抛出错误
		
		comps = list(self.fixed_composition.keys())
		el_A = comps[0]
		frac_A = self.fixed_composition[el_A]
		
		# 1. 计算 Miedema 形成焓 (Delta H_form)
		# 包含有序化因子的修正
		H_form = self.model.calculate_enthalpy(frac_A, temperature)
		
		# 2. 计算基准能量 (Reference Energy)
		# G_compound = Sum(x_i * G_pure_i) + Delta_H_form - T * S_form
		# 假设 S_form (形成熵) 很小，或者由 Miedema 的 g_ex 包含 (get_excess_Gibbs)
		# 为了更准确，我们使用 get_excess_Gibbs (它包含 H - T*S_ex)
		
		# 注意: get_excess_Gibbs 返回的是相对于纯组元液相/固相的 G_excess
		# 所以 G_total = Sum(x_i * G_pure_i) + G_excess
		
		G_excess = self.model.get_excess_Gibbs(el_A, frac_A, temperature)
		
		# 获取纯组元参考能量 (固相)
		# 化合物通常相对于固相组元定义
		# 这里我们需要 TDB parser 的实例。
		# 为了简化架构，这里我们做一个权衡：
		# 在 Factory 创建时，我们通常关注的是相对稳定性 (Formation Energy)。
		# 但 GEM 需要绝对能量 (Absolute Gibbs Energy)。
		
		# 修正方案：StoichiometricCompound 需要访问 calculator 来获取 G_pure
		# 但为了不破坏 __init__，我们假设 G_total = G_excess (formation) + Linear Combination
		# 如果没有 calculator 实例，我们无法计算绝对 G。
		
		# 因此，必须传入 calculator 实例（类似于 SolutionPhase）
		# 见下方的 Factory 修改
		return G_excess  # 这里暂时只返回 G_excess，后面会补上 G_ref
	
	def set_calculator (self, calculator):
		"""注入计算器以获取纯组元能量"""
		self.calculator = calculator
	
	def get_absolute_energy (self, temperature):
		"""计算绝对吉布斯能 (G_ref + G_form)"""
		if not hasattr(self, 'calculator'):
			return 0.0
		
		G_ref = 0.0
		for el, x in self.fixed_composition.items():
			# 化合物参考态通常是标准固相 (SER)
			ref_phase = self.calculator.tdb_parser.get_reference_phase(el) or 'BCC_A2'
			g_pure = self.calculator.tdb_parser.get_gibbs_energy(el, ref_phase, temperature)
			if g_pure:
				G_ref += x * g_pure
		
		# G_form (from Miedema)
		comps = list(self.fixed_composition.keys())
		g_form = self.model.get_excess_Gibbs(comps[0], self.fixed_composition[comps[0]], temperature)
		
		return G_ref + g_form
	
	# 覆盖基类方法，重定向到 get_absolute_energy
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		return self.get_absolute_energy(temperature)
	
	def get_composition (self) -> Dict[str, float]:
		return self.fixed_composition


# =============================================================================
# Miedema 预测相工厂
# =============================================================================

class MiedemaPhaseFactory:
	"""
	用于生成基于 Miedema 模型的虚拟化合物相。
	"""
	
	@staticmethod
	def create_virtual_compound (element_a: str, element_b: str,
	                             xa: float, xb: float,
	                             calculator_instance,
	                             phase_name: str = None) -> StoichiometricCompound:
		if phase_name is None:
			phase_name = f"Virtual_{element_a}{xa:.2f}_{element_b}{xb:.2f}"
		
		comp = {element_a: xa, element_b: xb}
		
		# 创建化合物对象
		compound = StoichiometricCompound(phase_name, comp)
		
		# 注入 calculator 以便计算绝对能量
		compound.set_calculator(calculator_instance)
		
		return compound