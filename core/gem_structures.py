import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

# 引入 Miedema 模型和属性估算器
from models.miedema_model import MiedemaModel
from core.properties_estimator import get_properties_estimator
from core.element import Element


class ThermodynamicPhase(ABC):
	"""GEM 算法通用的相接口抽象基类"""
	
	def __init__ (self, name: str, components: List[str], phase_type: str):
		self.name = name
		self.components = sorted(components)
		self.phase_type = phase_type  # 'liquid', 'solid_solution', 'compound'
	
	@abstractmethod
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		pass
	
	def get_composition_array (self, composition_dict: Dict[str, float]) -> np.ndarray:
		return np.array([composition_dict.get(c, 0.0) for c in self.components])
	
	def get_composition (self) -> Dict[str, float]:
		return {}


class SolutionPhase(ThermodynamicPhase):
	"""
	溶体相封装 (LIQUID, FCC, BCC...)。
	能量 = G_ref(TDB) + G_ideal + G_excess(Miedema UEM)
	"""
	
	def __init__ (self, name: str, components: List[str], calculator_instance):
		# 自动识别相类型
		p_type = 'liquid' if ('LIQUID' in name.upper() or 'L' == name.upper()) else 'solid_solution'
		super().__init__(name, components, phase_type=p_type)
		self.calculator = calculator_instance
		self._binary_models = {}
		# 获取属性估算器 (用于获取纯组元熔点)
		self.prop_estimator = get_properties_estimator()
	
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		# 1. 归一化成分
		total_moles = sum(composition.values())
		if total_moles < 1e-12: return 0.0
		X = {k: v / total_moles for k, v in composition.items()}
		
		G_ref = 0.0
		G_ideal = 0.0
		G_excess = 0.0
		R = 8.314462618
		
		# 准备数据：获取摩尔体积 V^(2/3) 用于 UEM 外推
		elements = sorted(list(X.keys()))
		v23_values = {}
		for elem in elements:
			el_obj = Element(elem)
			v23_values[elem] = el_obj.v ** (2.0 / 3.0)
		
		# 2. 计算 G_ref (含熔点惩罚) 和 G_ideal
		for elem, x_i in X.items():
			if x_i < 1e-12: continue
			
			# A. 从 TDB 获取能量
			g_pure = self.calculator.tdb_parser.get_gibbs_energy(elem, self.name, temperature)
			
			# 兜底：如果固相没数据，尝试用 LIQUID
			if g_pure is None:
				if self.phase_type == 'liquid':
					g_pure = self.calculator.tdb_parser.get_gibbs_energy(elem, 'LIQUID', temperature)
				if g_pure is None:
					return 1e9  # 惩罚，表示该元素不支持此相
			
			# B. 熔点惩罚 (仅固相)
			# 防止纯组元在远高于熔点的温度下以固态存在
			penalty = 0.0
			if self.phase_type == 'solid_solution':
				# 从 TDB 动态获取熔点信息
				props = self.prop_estimator.get_element_properties(elem)
				tm = props['Tm']
				sf = props['Sf']
				
				if temperature > tm:
					# G_pen = (T - Tm) * Sf
					penalty = (temperature - tm) * sf
			
			G_ref += x_i * (g_pure + penalty)
			G_ideal += x_i * np.log(x_i)
		
		G_ideal *= R * temperature
		
		# 3. 计算 G_excess (UEM / Surface Fraction Model)
		# -----------------------------------------------------------
		# Step A: 计算体系总摩尔表面积
		total_surface = sum(X[e] * v23_values[e] for e in elements)
		if total_surface < 1e-12: return G_ref + G_ideal
		
		# Step B: 计算各组分的表面分数 (Surface Fractions)
		CS = {e: (X[e] * v23_values[e]) / total_surface for e in elements}
		
		# Step C: 遍历二元对进行外推
		n_elems = len(elements)
		for i in range(n_elems):
			for j in range(i + 1, n_elems):
				el_i = elements[i]
				el_j = elements[j]
				
				cs_i = CS[el_i]
				cs_j = CS[el_j]
				sum_cs_pair = cs_i + cs_j
				if sum_cs_pair < 1e-9: continue
				
				# UEM 投影: 二元系内的相对表面分数
				u_s_i = cs_i / sum_cs_pair
				
				# 转回二元摩尔分数 (MiedemaModel 需要摩尔分数)
				vi = v23_values[el_i]
				vj = v23_values[el_j]
				x_bin_i = (u_s_i * vj) / (u_s_i * vj + (1.0 - u_s_i) * vi)
				
				# 获取/创建模型
				model_key = tuple(sorted((el_i, el_j)))
				if model_key not in self._binary_models:
					self._binary_models[model_key] = MiedemaModel(model_key, phase=self.phase_type)
				
				# 计算二元过剩能 (J/mol)
				g_ex_bin = self._binary_models[model_key].get_excess_Gibbs(el_i, x_bin_i, temperature)
				
				# UEM 权重: 该二元对的表面积贡献
				weight = (X[el_i] * vi + X[el_j] * vj) / total_surface
				
				G_excess += weight * g_ex_bin
		
		return G_ref + G_ideal + G_excess


class StoichiometricCompound(ThermodynamicPhase):
	"""定比化合物 (如 SiC, FeSi)"""
	
	def __init__ (self, name: str, fixed_composition: Dict[str, float], Tm: float = 5000.0, Sf: float = 15.0):
		super().__init__(name, list(fixed_composition.keys()), phase_type='Stoichiometric')
		self.fixed_composition = fixed_composition
		self.Tm = Tm
		self.Sf = Sf
		self.model = MiedemaModel((self.components[0], self.components[1]), phase='COMPOUND') if len(
			self.components) == 2 else None
	
	def set_calculator (self, calculator):
		self.calculator = calculator
	
	def get_absolute_energy (self, temperature):
		if not hasattr(self, 'calculator'): return 0.0
		
		# 1. 参考能 (Reference) - 相对于纯组元固相
		G_ref = 0.0
		for el, x in self.fixed_composition.items():
			ref_phase = self.calculator.tdb_parser.get_reference_phase(el) or 'BCC_A2'
			g_pure = self.calculator.tdb_parser.get_gibbs_energy(el, ref_phase, temperature)
			# 兜底
			if g_pure is None:
				g_pure = self.calculator.tdb_parser.get_gibbs_energy(el, 'LIQUID', temperature)
			if g_pure: G_ref += x * g_pure
		
		# 2. 形成能 G_form
		g_form = 0.0
		if self.model:
			comps = list(self.fixed_composition.keys())
			g_form = self.model.get_excess_Gibbs(comps[0], self.fixed_composition[comps[0]], temperature)
		
		# 3. 熔化惩罚
		G_penalty = 0.0
		if temperature > self.Tm:
			G_penalty = (temperature - self.Tm) * self.Sf
		
		return G_ref + g_form + G_penalty
	
	def get_molar_gibbs_energy (self, composition, temperature):
		return self.get_absolute_energy(temperature)
	
	def get_composition (self):
		return self.fixed_composition


class MiedemaPhaseFactory:
	"""生成虚拟化合物相的工厂类"""
	
	@staticmethod
	def create_virtual_compound (element_a, element_b, xa, xb, calculator_instance, Tm=5000.0, phase_name=None):
		if phase_name is None: phase_name = f"Virt_{element_a}{xa:.2f}_{element_b}{xb:.2f}"
		comp = {element_a: xa, element_b: xb}
		
		compound = StoichiometricCompound(phase_name, comp, Tm=Tm)
		compound.set_calculator(calculator_instance)
		
		# 尝试估算熔化熵
		try:
			m = MiedemaModel((element_a, element_b))
			compound.Sf = m.estimate_fusion_entropy(xa)
		except:
			pass
		
		return compound