import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable

# 引入新的 Miedema 模型
from models.miedema_model import MiedemaModel
from core.properties_estimator import get_properties_estimator

class ThermodynamicPhase(ABC):
	"""
	GEM 算法通用的相接口抽象基类。
	"""
	
	def __init__ (self, name: str, components: List[str], phase_type: str):
		self.name = name
		self.components = sorted(components)
		self.phase_type = phase_type  # 'liquid', 'solid_solution', 'compound'
	
	@abstractmethod
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		"""计算摩尔吉布斯自由能 (J/mol)"""
		pass
	
	def get_composition_array (self, composition_dict: Dict[str, float]) -> np.ndarray:
		"""辅助函数：将字典转换为按 components 排序的数组"""
		return np.array([composition_dict.get(c, 0.0) for c in self.components])
	
	def get_composition (self) -> Dict[str, float]:
		"""返回默认成分"""
		return {}


class SolutionPhase(ThermodynamicPhase):
	"""
	溶体相封装 (如 LIQUID, FCC_A1, BCC_A2)。

	能量 = G_ref(TDB) + G_ideal + G_excess(Miedema)
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
		
		# 缓存二元模型实例
		self._binary_models = {}
		self.prop_estimator = get_properties_estimator()
	
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		# 1. 归一化摩尔分数
		total_moles = sum(composition.values())
		if total_moles < 1e-12: return 0.0
		X = {k: v / total_moles for k, v in composition.items()}
		
		G_ref = 0.0
		G_ideal = 0.0
		G_excess = 0.0
		R = 8.314462618
		
		# 准备元素列表和物理参数
		elements = sorted(list(X.keys()))
		n_elems = len(elements)
		
		# 缓存 V^(2/3) 用于计算表面分数
		# 这是 UEM 模型中“组分性质差异”的核心体现
		v23_values = {}
		for elem in elements:
			# 简单获取 Element 对象的方式
			# 实际项目中建议优化 import 位置以防循环引用
			from core.element import Element
			el_obj = Element(elem)
			v23_values[elem] = el_obj.v ** (2.0 / 3.0)
		
		# ---------------------------------------------------------
		# Part 1: 参考能 (G_ref) 和 理想熵 (G_ideal)
		# 包含熔点惩罚逻辑
		# ---------------------------------------------------------
		for elem, x_i in X.items():
			if x_i < 1e-12: continue
			
			# A. TDB 纯组元能量
			g_pure = self.calculator.tdb_parser.get_gibbs_energy(elem, self.name, temperature)
			
			# 兜底：如果是液相但 TDB 没数据，尝试用 LIQUID
			if g_pure is None:
				if self.phase_type == 'liquid':
					g_pure = self.calculator.tdb_parser.get_gibbs_energy(elem, 'LIQUID', temperature)
				if g_pure is None: return 1e9  # 惩罚
			
			# B. 熔点惩罚 (仅固相)
			penalty = 0.0
			if self.phase_type == 'solid_solution':
				tm = self.melting_points.get(elem, 2000.0)
				if temperature > tm:
					sf = 30.0 if elem in ['Si', 'Ge'] else self.Sf_default
					penalty = (temperature - tm) * sf
			
			G_ref += x_i * (g_pure + penalty)
			G_ideal += x_i * np.log(x_i)
		
		G_ideal *= R * temperature
		
		# ---------------------------------------------------------
		# Part 2: 过剩能 (G_excess) - UEM / Surface Fraction Model
		# ---------------------------------------------------------
		# 1. 计算体系总摩尔表面积 S_total = Sum(xi * Vi^2/3)
		total_surface = sum(X[e] * v23_values[e] for e in elements)
		
		if total_surface < 1e-12: return G_ref + G_ideal
		
		# 2. 计算各组分的表面分数 (Surface Fractions)
		# c_s_i = (x_i * V_i^2/3) / S_total
		CS = {e: (X[e] * v23_values[e]) / total_surface for e in elements}
		
		# 3. 遍历二元对进行 UEM 外推
		for i in range(n_elems):
			for j in range(i + 1, n_elems):
				el_i = elements[i]
				el_j = elements[j]
				
				cs_i = CS[el_i]
				cs_j = CS[el_j]
				
				# 二元对在总表面积中的总占比 (用于归一化)
				sum_cs_pair = cs_i + cs_j
				if sum_cs_pair < 1e-9: continue
				
				# A. 确定二元子体系中的有效坐标 (Projection)
				# UEM 核心: 使用表面分数比来投影，而非摩尔分数比
				# u_s_i = cs_i / (cs_i + cs_j)
				u_s_i = cs_i / sum_cs_pair
				
				# B. 将表面分数投影转回摩尔分数 (Inverse Calculation)
				# MiedemaModel 计算能量需要摩尔分数 x_bin
				# 公式推导: x_i / x_j = (u_s_i * V_j^2/3) / (u_s_j * V_i^2/3)
				vi = v23_values[el_i]
				vj = v23_values[el_j]
				
				# 二元系中组分 i 的摩尔分数
				x_bin_i = (u_s_i * vj) / (u_s_i * vj + (1.0 - u_s_i) * vi)
				
				# C. 计算二元相互作用能 G_binary(x_bin)
				# 获取/创建模型
				model_key = tuple(sorted((el_i, el_j)))
				if model_key not in self._binary_models:
					self._binary_models[model_key] = MiedemaModel(model_key, phase=self.phase_type)
				
				# 获取单位为 J/mol 的二元过剩能
				g_ex_binary = self._binary_models[model_key].get_excess_Gibbs(el_i, x_bin_i, temperature)
				
				# D. 权重分配 (Contribution Coefficient)
				# UEM/Miedema 权重: 该二元对的表面积贡献
				# Weight = (Total Surface of binary pair i-j) / (Total Surface of system)
				# 这个权重因子实际上就是: (x_i * Vi + x_j * Vj) / S_total
				# 注意：这里要用二元系混合后的有效表面积去乘 g_ex_binary 吗？
				# 不，标准处理是将 G_binary 视为摩尔性质，然后按摩尔分数或表面积加权。
				# Miedema 的推导指出：Delta H_ternary = Sum ( c_s_i * c_s_j * ... )
				# 简化实现：使用表面积加权
				
				# 权重 = (x_i * Vi^2/3 + x_j * Vj^2/3) / Total_Surface
				# 这等价于 sum_cs_pair (如果忽略体积变化)
				# 这种权重分配考虑了原子尺寸差异带来的“接触概率”差异
				weight = (X[el_i] * vi + X[el_j] * vj) / total_surface
				
				# 修正系数：将二元摩尔性质映射回三元贡献
				# 在 Muggianu 中是 x_i + x_j。在 UEM/Surface 中是 weight。
				G_excess += weight * g_ex_binary
		
		return G_ref + G_ideal + G_excess
	
class StoichiometricCompound(ThermodynamicPhase):
	"""
	定比化合物 (如 SiC, FeSi)。
	包含:
	1. Miedema 形成焓 (含 Sun 修正 + 有序因子)
	2. 熔化惩罚 (Melting Penalty): 当 T > Tm 时，施加熵惩罚。
	"""
	
	def __init__ (self,
	              name: str,
	              fixed_composition: Dict[str, float],
	              Tm: float = 5000.0,  # <--- 新增：熔点
	              Sf: float = 15.0):  # <--- 新增：熔化熵
		
		components = list(fixed_composition.keys())
		super().__init__(name, components, phase_type='Stoichiometric')
		self.fixed_composition = fixed_composition
		self.Tm = Tm
		self.Sf = Sf
		
		# 初始化 Miedema 模型 (phase='COMPOUND' 触发有序因子)
		if len(components) == 2:
			self.model = MiedemaModel((components[0], components[1]), phase='COMPOUND')
		else:
			self.model = None
	
	def set_calculator (self, calculator):
		self.calculator = calculator
	
	def get_absolute_energy (self, temperature):
		"""计算绝对吉布斯能"""
		if not hasattr(self, 'calculator'):
			return 0.0
		
		# 1. 纯组元参考能 (通常相对于固相)
		G_ref = 0.0
		for el, x in self.fixed_composition.items():
			# 获取参考相 (SER)，如果未知则尝试 BCC
			ref_phase = self.calculator.tdb_parser.get_reference_phase(el) or 'BCC_A2'
			g_pure = self.calculator.tdb_parser.get_gibbs_energy(el, ref_phase, temperature)
			if g_pure is None:
				# 再次兜底：尝试任意固相
				for ph in ['FCC_A1', 'HCP_A3', 'GRAPHITE', 'DIAMOND_A4']:
					g_pure = self.calculator.tdb_parser.get_gibbs_energy(el, ph, temperature)
					if g_pure: break
			
			if g_pure:
				G_ref += x * g_pure
		
		# 2. Miedema 形成能 (Excess Gibbs)
		g_form = 0.0
		if self.model:
			comps = list(self.fixed_composition.keys())
			# get_excess_Gibbs 返回的是相对于纯组元的形成能
			g_form = self.model.get_excess_Gibbs(comps[0], self.fixed_composition[comps[0]], temperature)
		
		# 3. 高温熔化惩罚 (Melting Penalty)
		# 当 T > Tm 时，通过 (T-Tm)*Sf 提高能量，模拟熔化后的不稳定性
		G_penalty = 0.0
		if temperature > self.Tm:
			G_penalty = (temperature - self.Tm) * self.Sf
		
		return G_ref + g_form + G_penalty
	
	# 覆盖基类方法
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		return self.get_absolute_energy(temperature)
	
	def get_composition (self) -> Dict[str, float]:
		return self.fixed_composition


# =============================================================================
# Miedema 预测相工厂
# =============================================================================

class MiedemaPhaseFactory:
	"""
	生成虚拟化合物相的工厂类。
	"""
	
	@staticmethod
	def create_virtual_compound (element_a: str, element_b: str,
	                             xa: float, xb: float,
	                             calculator_instance,
	                             Tm: float = 5000.0,  # <--- 关键修复：支持 Tm 参数
	                             phase_name: str = None) -> StoichiometricCompound:
		
		if phase_name is None:
			phase_name = f"Virt_{element_a}{xa:.2f}_{element_b}{xb:.2f}"
		
		comp = {element_a: xa, element_b: xb}
		
		# 创建化合物对象，传入 Tm
		compound = StoichiometricCompound(phase_name, comp, Tm=Tm)
		
		# 注入 TDB 计算器
		compound.set_calculator(calculator_instance)
		
		# 【自动估算熔化熵】
		# 使用 MiedemaModel 中的经验规则预测该化合物的熔化熵
		try:
			temp_model = MiedemaModel((element_a, element_b))
			estimated_Sf = temp_model.estimate_fusion_entropy(xa)
			compound.Sf = estimated_Sf
		except Exception:
			pass  # 保持默认值 15.0
		
		return compound