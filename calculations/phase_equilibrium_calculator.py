import sys
import os
import itertools
import math
import numpy as np
from typing import Dict, List, Any

# 确保能导入 core 和 models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gem_solver import GEMSolver, EquilibriumResult
from core.gem_structures import SolutionPhase, MiedemaPhaseFactory
from core.element import Element
from models.miedema_model import MiedemaModel
from core.tdb_parser import get_tdb_parser
from core.properties_estimator import get_properties_estimator


class PhaseEquilibriumCalculator:
	"""
	通用相平衡计算器 (物理增强版)。

	算法核心：
	1. TDB 层: 自动扫描数据库中所有可能的相，通过能量试算筛选出相对稳定的相（不依赖硬编码白名单）。
	2. Miedema 层: 自动生成二元虚拟化合物，基于 SRO (短程有序) 理论估算物理熔点。
	3. GEM 层: 全局吉布斯自由能最小化。
	"""
	
	def __init__ (self):
		# 初始化核心组件
		self.tdb_parser = get_tdb_parser()
		self.solver = GEMSolver()
		self.estimator = get_properties_estimator()
		
		# 预定义常见的金属间化合物化学计量比
		self.stoichiometry_ratios = [
			(0.833, 0.167), (0.750, 0.250), (0.667, 0.333),
			(0.500, 0.500),
			(0.333, 0.667), (0.250, 0.750), (0.167, 0.833),
		]
	
	def calculate_phase_equilibrium (self,
	                                 composition: Dict[str, float],
	                                 temperature: float) -> EquilibriumResult:
		"""
		计算多相平衡 (前端调用主入口)。

		Args:
			composition: 初始成分字典, e.g. {'Fe': 0.7, 'Si': 0.3}
			temperature: 计算温度 (K)

		Returns:
			EquilibriumResult: 包含稳定相列表和热力学数据的结果对象
		"""
		# 1. 动态构建候选相列表
		candidate_phases = self._build_candidate_phases(composition, temperature)
		
		# 2. 调用 GEM 求解器
		result = self.solver.solve(composition, temperature, candidate_phases)
		
		return result
	
	def _build_candidate_phases (self, composition: Dict[str, float], temperature: float) -> List[Any]:
		"""
		构建参与竞争的所有相 (内部核心逻辑)。
		"""
		phases = []
		elements = sorted(list(composition.keys()))
		
		# 为了适配 SolutionPhase 接口，构建上下文对象
		class TDBContext:
			def __init__ (self, parser): self.tdb_parser = parser
		
		context = TDBContext(self.tdb_parser)
		
		# =========================================================================
		# A. 动态 TDB 相筛选 (Energy-based Filtering)
		# =========================================================================
		
		# 1. 发现所有可能的相名称
		possible_tdb_phases = set()
		for elem in elements:
			try:
				# 从 TDB 获取该元素涉及的所有相
				possible_tdb_phases.update(self.tdb_parser.get_element_phases(elem))
			except:
				continue
		possible_tdb_phases.add('LIQUID')  # 强制包含液相
		
		# 2. 计算基准能量 (液相能量) 用于相对稳定性判断
		ref_liq_g = 0.0
		try:
			liq_phase = SolutionPhase('LIQUID', elements, context)
			ref_liq_g = liq_phase.get_molar_gibbs_energy(composition, temperature)
			# 如果液相能量无效，设为0
			if ref_liq_g > 0.9e9: ref_liq_g = 0.0
		except:
			ref_liq_g = 0.0
		
		# 3. 遍历并筛选相
		for p_name in sorted(list(possible_tdb_phases)):
			# 确定该相支持的元素
			valid_components = []
			for elem in elements:
				# 液相默认支持所有，其他相需查表
				if p_name == 'LIQUID' or p_name in self.tdb_parser.get_element_phases(elem):
					valid_components.append(elem)
			
			if not valid_components: continue
			
			try:
				# 实例化相
				phase_obj = SolutionPhase(p_name, valid_components, context)
				
				# 【筛选逻辑】: 能量试算
				# 使用当前体系总成分试算 G。SolutionPhase 会自动处理归一化。
				g_test = phase_obj.get_molar_gibbs_energy(composition, temperature)
				
				# 判据 1: 是否返回有效值 (SolutionPhase 遇到无法计算参数会返回 1e9)
				if g_test > 0.9e9:
					continue
				
				# 判据 2: 相对稳定性检查 (Energy Threshold)
				# 如果某相能量比液相高出太多 (例如 > 200 kJ/mol)，说明极不稳定，直接忽略
				# 这能有效过滤掉 TDB 中存在的但在当前条件下不可能出现的复杂高能相
				if ref_liq_g != 0 and (g_test - ref_liq_g > 200000):
					continue
				
				phases.append(phase_obj)
			
			except Exception:
				continue
		
		# =========================================================================
		# B. Miedema 虚拟化合物 (物理熔点估算)
		# =========================================================================
		for el1, el2 in itertools.combinations(elements, 2):
			# 创建临时模型用于计算焓变
			model_comp = MiedemaModel((el1, el2), phase='COMPOUND')
			model_liq = MiedemaModel((el1, el2), phase='LIQUID')
			
			for x1, x2 in self.stoichiometry_ratios:
				# 1. 计算固相形成焓 (Reference: Pure Solid)
				# 我们关心低温稳定性，所以用标准温度计算 H_form
				h_form_solid = model_comp.calculate_enthalpy(x1, T=298.15)
				
				# 筛选不稳定相 (H > 0)
				if h_form_solid > -100.0: continue
				
				# 2. 估算物理熔点 (SRO修正版)
				tm_phys = self._calculate_physical_melting_point(
						el1, el2, x1, x2, h_form_solid, model_liq
				)
				
				# 3. 创建对象
				phase_name = f"Virt_{el1}{x1:.2f}{el2}{x2:.2f}"
				phases.append(MiedemaPhaseFactory.create_virtual_compound(
						el1, el2, x1, x2,
						calculator_instance=context,
						Tm=tm_phys,
						phase_name=phase_name
				))
		
		return phases
	
	def _calculate_physical_melting_point (self, el1: str, el2: str, x1: float, x2: float,
	                                       h_form_solid: float, model_liq: MiedemaModel) -> float:
		"""
		基于物理模型估算化合物熔点 Tm。
		采用 SRO (Short-Range Order) 修正，假设液相保留了大部分有序结构。

		原理: Tm = Delta H_total / Delta S_total
		"""
		# 1. 获取纯组元熔化参数 (动态 TDB 数据)
		props1 = self.estimator.get_element_properties(el1)
		props2 = self.estimator.get_element_properties(el2)
		
		tm1, sf1 = props1['Tm'], props1['Sf']
		tm2, sf2 = props2['Tm'], props2['Sf']
		
		# 结构破坏贡献 (晶格崩塌)
		hf1 = tm1 * sf1
		hf2 = tm2 * sf2
		term_structure_H = x1 * hf1 + x2 * hf2
		
		# 2. 化学键破坏贡献 (SRO Factor)
		# H_disorder_cost = H_liquid(disordered) - H_solid(ordered)
		h_mix_liquid_disordered = model_liq.calculate_enthalpy(x1, T=2000.0)
		chem_diff = h_mix_liquid_disordered - h_form_solid
		
		# gamma = 0.1: 假设液相保留了 90% 的化学短程有序
		# 这意味着熔化过程只破坏了 10% 的化学键
		# 这样会显著降低熔化焓，从而避免算出虚高的熔点
		gamma = 0.1
		term_chemical_H = gamma * chem_diff
		
		delta_H_total = term_structure_H + term_chemical_H
		
		# 3. 总熔化熵
		# Delta S = 结构熵 + gamma * 理想混合熵
		R = 8.314
		s_ideal_mix = 0.0
		if x1 > 1e-9 and x2 > 1e-9:
			s_ideal_mix = -R * (x1 * math.log(x1) + x2 * math.log(x2))
		
		term_structure_S = x1 * sf1 + x2 * sf2
		term_config_S = gamma * s_ideal_mix
		
		delta_S_total = term_structure_S + term_config_S
		
		# 4. 计算 Tm
		if delta_S_total <= 1.0: return 2000.0
		
		Tm = delta_H_total / delta_S_total
		
		# 安全范围限制
		return max(300.0, min(Tm, 5000.0))


# 调试接口 (仅用于直接运行此文件测试，不影响外部调用)
if __name__ == "__main__":
	try:
		calc = PhaseEquilibriumCalculator()
		comp = {'Fe': 0.7, 'Si': 0.27, 'C': 0.03}
		T = 1873.0
		
		print(f"=== 通用相平衡计算测试 (T={T} K) ===")
		res = calc.calculate_phase_equilibrium(comp, T)
		
		print(f"\n计算状态: {res.status}")
		print(f"总 Gibbs 能量: {res.total_gibbs_energy:.2f} J/mol")
		print("\n稳定相组成:")
		for p in res.stable_phases:
			if p['fraction'] > 0.001:
				comp_str = ", ".join([f"{k}:{v:.4f}" for k, v in p['composition'].items()])
				print(f"  -> {p['name']:<20} 摩尔分数: {p['fraction']:.4f}  | 成分: {comp_str}")
	
	except Exception as e:
		print(f"\nError: {e}")
		import traceback
		
		traceback.print_exc()