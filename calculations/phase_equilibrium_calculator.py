import sys
import os
import itertools
import math
import numpy as np
from typing import Dict, List, Any

from core.properties_estimator import get_properties_estimator

# 确保能导入 core 和 models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gem_solver import GEMSolver, EquilibriumResult
from core.gem_structures import SolutionPhase, MiedemaPhaseFactory
from core.element import Element
from models.miedema_model import MiedemaModel, MiedemaConstants
from core.tdb_parser import get_tdb_parser


class PhaseEquilibriumCalculator:
	"""
	通用相平衡计算器 (物理增强版)。

	特性：
	1. 普适性 TDB 加载: 自动扫描所有相，通过能量试算筛选，不依赖白名单。
	2. 物理熔点预测: 基于 G_liquid = G_solid 平衡条件精确估算虚拟化合物熔点。
	"""
	
	def __init__ (self):
		self.tdb_parser = get_tdb_parser()
		self.solver = GEMSolver()
		
		# 常见金属间化合物比例
		self.stoichiometry_ratios = [
			(0.833, 0.167), (0.750, 0.250), (0.667, 0.333),
			(0.500, 0.500),
			(0.333, 0.667), (0.250, 0.750), (0.167, 0.833),
		]
	
	def calculate_phase_equilibrium (self,
	                                 composition: Dict[str, float],
	                                 temperature: float) -> EquilibriumResult:
		candidate_phases = self._build_candidate_phases(composition, temperature)
		result = self.solver.solve(composition, temperature, candidate_phases)
		return result
	
	def _build_candidate_phases (self, composition: Dict[str, float], temperature: float) -> List[Any]:
		phases = []
		elements = sorted(list(composition.keys()))
		
		# 构建 TDB 上下文适配器
		class TDBContext:
			def __init__ (self, parser): self.tdb_parser = parser
		
		context = TDBContext(self.tdb_parser)
		
		# =========================================================================
		# A. 动态 TDB 相筛选 (Energy-based Filtering)
		# =========================================================================
		# 1. 发现所有可能的相
		possible_tdb_phases = set()
		for elem in elements:
			try:
				possible_tdb_phases.update(self.tdb_parser.get_element_phases(elem))
			except:
				continue
		possible_tdb_phases.add('LIQUID')
		
		# 2. 计算基准能量 (液相能量) 用于相对稳定性判断
		ref_liq_g = 0.0
		try:
			liq_phase = SolutionPhase('LIQUID', elements, context)
			ref_liq_g = liq_phase.get_molar_gibbs_energy(composition, temperature)
		except:
			ref_liq_g = 0.0  # 如果液相都算不出，则无法比较，设为0
		
		# 3. 遍历并筛选
		for p_name in sorted(list(possible_tdb_phases)):
			# 确定该相支持的元素
			valid_components = []
			for elem in elements:
				if p_name == 'LIQUID' or p_name in self.tdb_parser.get_element_phases(elem):
					valid_components.append(elem)
			
			if not valid_components: continue
			
			try:
				# 实例化相
				phase_obj = SolutionPhase(p_name, valid_components, context)
				
				# 【关键逻辑】试算能量进行筛选
				# 使用当前体系成分试算 G。如果成分不匹配（例如 Graphite 只有 C），
				# get_molar_gibbs_energy 内部会自动归一化处理。
				g_test = phase_obj.get_molar_gibbs_energy(composition, temperature)
				
				# 判据 1: 是否返回有效值 (SolutionPhase 遇到无法计算会返回 1e9)
				if g_test > 0.9e9:
					continue
				
				# 判据 2: 相对稳定性检查 (可选)
				# 如果某相能量比液相高出太多 (例如 > 200 kJ/mol)，说明极不稳定，可忽略
				# 这能有效过滤掉那些完全不可能存在的复杂高能相
				if g_test - ref_liq_g > 200000:
					continue
				
				phases.append(phase_obj)
			
			except Exception:
				continue
		
		# =========================================================================
		# B. Miedema 虚拟化合物 (物理熔点估算)
		# =========================================================================
		for el1, el2 in itertools.combinations(elements, 2):
			# 分别创建 compound 和 liquid 模型用于计算 enthalpy differences
			model_comp = MiedemaModel((el1, el2), phase='COMPOUND')
			model_liq = MiedemaModel((el1, el2), phase='LIQUID')
			
			for x1, x2 in self.stoichiometry_ratios:
				# 1. 计算形成焓 (Compound vs Pure Solid)
				# H_form 是相对于纯组元固相的
				h_form_solid = model_comp.calculate_enthalpy(x1, T=298.15)
				
				# 筛选不稳定相
				if h_form_solid > -100.0: continue
				
				# 2. 计算物理熔点 (基于 G_liq = G_solid)
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

		修正：
		1. 基础热力学数据(Tm, Sf)改为从 TDB 动态获取，确保与 SolutionPhase 一致。
		2. 保留短程有序(SRO)修正逻辑 (gamma因子)。
		"""
		# 获取属性估算器
		estimator = get_properties_estimator()
		
		# 1. 获取纯组元熔化参数 (动态 TDB 数据)
		props1 = estimator.get_element_properties(el1)
		props2 = estimator.get_element_properties(el2)
		
		tm1 = props1['Tm']
		sf1 = props1['Sf']
		tm2 = props2['Tm']
		sf2 = props2['Sf']
		
		# 纯组元熔化焓贡献 (结构破坏)
		# H_fusion = Tm * Sf
		hf1 = tm1 * sf1
		hf2 = tm2 * sf2
		
		term_structure_H = x1 * hf1 + x2 * hf2
		
		# 2. 化学键破坏贡献 (Chemical Bond Breaking)
		# H_disorder_cost = H_liquid(disordered) - H_solid(ordered)
		# 假设液相是无序的 Miedema 混合能 (高温 2000K)
		h_mix_liquid_disordered = model_liq.calculate_enthalpy(x1, T=2000.0)
		chem_diff = h_mix_liquid_disordered - h_form_solid
		
		# SRO 因子: 假设液相保留了 70% 的有序度，只破坏 30%
		gamma = 0.1
		term_chemical_H = gamma * chem_diff
		
		# 3. 总熔化焓
		delta_H_total = term_structure_H + term_chemical_H
		
		# 4. 总熔化熵
		# Delta S = 结构熵(TDB) + gamma * 构型熵(Ideal)
		R = 8.314
		if x1 > 1e-9 and x2 > 1e-9:
			s_ideal_mix = -R * (x1 * math.log(x1) + x2 * math.log(x2))
		else:
			s_ideal_mix = 0.0
		
		term_structure_S = x1 * sf1 + x2 * sf2
		term_config_S = gamma * s_ideal_mix
		
		delta_S_total = term_structure_S + term_config_S
		
		# 5. 计算 Tm = dH / dS
		if delta_S_total <= 1.0:
			# 异常保护：如果没有熵增，熔点将趋于无穷
			return 2500.0
		
		Tm = delta_H_total / delta_S_total
		
		# 安全范围限制
		return max(300.0, min(Tm, 5000.0))
	
if __name__ == "__main__":
	try:
		calc = PhaseEquilibriumCalculator()
		comp = {'Fe': 0.7, 'Si': 0.27, 'C': 0.03}
		T = 1873.0
		
		print(f"=== 通用相平衡计算测试 (T={T} K) ===")
		print(f"System: {comp}")
		
		res = calc.calculate_phase_equilibrium(comp, T)
		
		print(f"\n计算状态: {res.status}")
		print(f"总 Gibbs 能量: {res.total_gibbs_energy:.2f} J/mol")
		print("\n稳定相组成:")
		for p in res.stable_phases:
			if p['fraction'] > 0.001:
				comp_str = ", ".join([f"{k}:{v:.4f}" for k, v in p['composition'].items()])
				# 如果是虚拟相，显示估算的熔点
				extra_info = ""
				if "Virt" in p['name']:
					# 这里 hack 一下找回对象来显示熔点，实际项目可以优化结构
					pass
				print(f"  -> {p['name']:<20} 摩尔分数: {p['fraction']:.4f}  | 成分: {comp_str}")
	
	except Exception as e:
		print(f"\nError: {e}")
		import traceback
		
		traceback.print_exc()