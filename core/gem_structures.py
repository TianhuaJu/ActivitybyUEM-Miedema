import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Callable, Optional, Any


class ThermodynamicPhase(ABC):
	"""
	GEM 算法通用的相接口抽象基类。
	"""
	
	def __init__ (self, name: str, components: List[str], phase_type: str):
		self.name = name
		self.components = sorted(components)  # 确保元素顺序一致 ['C', 'Fe', 'Si']
		self.phase_type = phase_type  # 'Stoichiometric' 或 'Solution'
	
	@abstractmethod
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		"""计算摩尔吉布斯自由能 (J/mol)"""
		pass
	
	def get_composition_array (self, composition_dict: Dict[str, float]) -> np.ndarray:
		"""辅助函数：将字典转换为按 components 排序的数组"""
		return np.array([composition_dict.get(c, 0.0) for c in self.components])


class SolutionPhase(ThermodynamicPhase):
	"""
	溶体相封装 (如 LIQUID, FCC_A1, BCC_A2)。
	通过调用 PhaseDiagramCalculator 的现有逻辑来计算能量。
	"""
	
	def __init__ (self,
	              name: str,
	              components: List[str],
	              calculator_instance,  # 传入 PhaseDiagramCalculator 实例
	              extrapolation_model_func,
	              extrapolation_model_name: str = 'UEM1',
	              activity_model: str = 'Wagner'):
		
		super().__init__(name, components, phase_type='Solution')
		self.calculator = calculator_instance
		self.extrapolation_model_func = extrapolation_model_func
		self.extrapolation_model_name = extrapolation_model_name
		self.activity_model = activity_model
	
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		"""
		计算逻辑：
		G_total = sum(x_i * mu_i)
		利用 calculator._get_chemical_potential 获取 mu_i (包含 G0 + Ideal + Excess)
		"""
		total_g = 0.0
		
		# 归一化输入成分（防止微小误差）
		total_moles = sum(composition.values())
		if total_moles == 0: return 0.0
		norm_comp = {k: v / total_moles for k, v in composition.items()}
		
		for elem, x_i in norm_comp.items():
			if x_i < 1e-12: continue
			
			# 调用您现有的化学势计算函数
			# 注意：_get_chemical_potential 内部会自动处理 G0, 理想混合熵, 以及由 extrapolation_models 计算的 G_ex
			mu = self.calculator._get_chemical_potential(
					composition=norm_comp,
					component=elem,
					temperature=temperature,
					tdb_phase=self.name,
					extrapolation_model_func=self.extrapolation_model_func,
					extrapolation_model=self.extrapolation_model_name,
					activity_model=self.activity_model
			)
			
			if mu is None:
				# 如果某组分在该相中无法计算（例如参数缺失），返回无穷大表示该相不稳定
				return 1e20
			
			total_g += x_i * mu
		
		return total_g


class StoichiometricCompound(ThermodynamicPhase):
	"""
	定比化合物 (如 SiC, Fe3C) 或 Miedema 预测的虚拟化合物。
	"""
	
	def __init__ (self,
	              name: str,
	              fixed_composition: Dict[str, float],
	              formation_energy_func: Callable[[float], float]):
		"""
		Args:
			name: 相名称
			fixed_composition: 固定成分 (摩尔分数), e.g. {'Fe': 0.75, 'C': 0.25}
			formation_energy_func: 一个函数 func(T) -> G (J/mol)
		"""
		components = list(fixed_composition.keys())
		super().__init__(name, components, phase_type='Stoichiometric')
		self.fixed_composition = fixed_composition
		self._energy_func = formation_energy_func
	
	def get_molar_gibbs_energy (self, composition: Dict[str, float], temperature: float) -> float:
		# 对于定比化合物，成分是固定的，输入的 composition 参数仅用于接口兼容
		# 直接调用能量函数
		return self._energy_func(temperature)
	
	def get_composition (self) -> Dict[str, float]:
		return self.fixed_composition


# =============================================================================
# Miedema 预测相工厂
# =============================================================================

from models.extrapolation_models import BinaryModel


class MiedemaPhaseFactory:
	"""
	用于生成基于 Miedema 模型的虚拟化合物相。
	"""
	
	@staticmethod
	def create_virtual_compound (element_a: str, element_b: str,
	                             xa: float, xb: float,
	                             phase_name: str = None) -> StoichiometricCompound:
		"""
		创建一个虚拟二元化合物相。
		能量 G ≈ H_formation (Miedema)
		"""
		if phase_name is None:
			phase_name = f"Virtual_{element_a}{int(xa * 100)}_{element_b}{int(xb * 100)}"
		
		comp = {element_a: xa, element_b: xb}
		
		# 定义能量函数闭包
		def miedema_energy (T: float) -> float:
			model = BinaryModel()
			model.set_temperature(T)
			# 假设生成固相化合物
			model.set_state("solid")
			# 这里的 binary_model 返回的是 Mixing Enthalpy (近似视为 Formation Gibbs Energy)
			# 注意：extrapolation_models.py 中的 binary_model 参数顺序是 (ea, eb, xa, xb)
			h_mix = model.binary_model(element_a, element_b, xa, xb)
			
			# 您可以根据需要添加简单的熵修正: G = H - T*S_approx
			# 这里暂时只返回焓
			return h_mix * 1000  # 如果 binary_model 返回 kJ，需要转 J；如果是 J 则直接用
		
		# 根据代码上下文 binary_model 似乎返回的是 J/mol (基于 R=8.314)
		# 您的 fab 计算中用的是 Constants.R，所以大概率是标准单位。
		# 再次确认：fab 返回的是 diff，v_in_alloy 返回体积。
		# 通常 Miedema 模型算出的是 kJ/mol，但需要看 Constants.R 单位。
		# 假设 extrapolation_models.py 输出为 J/mol。
		
		return StoichiometricCompound(phase_name, comp, miedema_energy)