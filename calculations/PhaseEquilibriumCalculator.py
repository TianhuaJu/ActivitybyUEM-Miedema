import math
import sys
import os
import copy
from typing import Dict, List, Optional, Tuple
from itertools import combinations

# 确保能找到父类
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculations.phase_diagram import PhaseDiagramCalculator
from models.miedema_model import MiedemaModel


class PhaseEquilibriumCalculator(PhaseDiagramCalculator):
	"""
	基于“稳定性收缩-剥离法”的多相平衡计算器 (V6 - 化合物优先剥离版)。

	修正点：
	当检测到化合物导致不稳定时，优先剥离化合物相，而不是强制剥离溶剂基体。
	这能正确模拟金属间化合物的消耗过程，避免溶剂过早耗尽。
	"""
	
	def __init__ (self):
		super().__init__()
	
	def calculate_phase_equilibrium (self,
	                                 alloy_composition: Dict[str, float],
	                                 temperature: float,
	                                 extrapolation_model_func=None,
	                                 extrapolation_model_name='UEM1',
	                                 activity_model='Wagner',
	                                 min_phase_fraction: float = 1e-4,
	                                 max_iterations: int = 20) -> List[Dict]:
		
		# --- 0. 自动加载默认模型 ---
		if extrapolation_model_func is None:
			try:
				from models.extrapolation_models import BinaryModel
				extrapolation_model_func = BinaryModel().UEM1
			except ImportError:
				print("Error: Could not load BinaryModel.")
				return []
		
		results = []
		current_moles_dict = alloy_composition.copy()
		total_moles_system = sum(current_moles_dict.values())
		current_moles_dict = {k: v / total_moles_system for k, v in current_moles_dict.items()}
		
		print(f"--- 开始多相平衡计算 (T={temperature}K) ---")
		
		for iteration in range(max_iterations):
			total_current_moles = sum(current_moles_dict.values())
			if total_current_moles < 1e-6:
				break
			
			# 计算当前的归一化成分
			current_comp_norm = {k: v / total_current_moles for k, v in current_moles_dict.items()}
			
			# 格式化输出
			comp_str = self._format_comp(current_comp_norm)
			print(f"\n[Iteration {iteration + 1}] 当前对象 (总量 {total_current_moles:.4f}): {comp_str}")
			
			# --- 步骤 1: 识别基础结构 ---
			base_phase_struct = self._identify_stable_structure_tdb(current_comp_norm, temperature)
			solvent_name = max(current_comp_norm.items(), key=lambda x: x[1])[0]
			print(f"  -> 假定基体溶剂: {solvent_name}, 结构: {base_phase_struct}")
			
			# --- 步骤 2: 判断稳定性 ---
			is_stable, unstable_details = self._check_phase_stability_strict(
					current_comp_norm, base_phase_struct, temperature,
					extrapolation_model_func, extrapolation_model_name, activity_model,
					solvent_name=solvent_name
			)
			
			target_phase_name = ""
			target_composition = {}
			target_type = ""
			
			if is_stable:
				# 稳定：直接输出当前相
				target_phase_name = self._generate_phase_name(current_comp_norm, base_phase_struct)
				print(f"  -> [判定] 成分稳定。识别为: {target_phase_name}")
				results.append({
					'phase_name': target_phase_name,
					'composition': current_comp_norm,
					'mole_fraction': total_current_moles,
					'type': 'Primary' if iteration == 0 else 'Residue'
				})
				break
			
			else:
				# 不稳定：分析原因
				primary_cause = unstable_details[0]
				cause_type = primary_cause.get('type', 'pure')
				cause_info = primary_cause.get('info', 'Unknown')
				
				print(f"  -> [判定] 不稳定。诱因: {cause_info} (ΔG_drive={primary_cause['driving_force']:.1f})")
				
				# =========================================================
				# 分支策略：根据不稳定类型选择剥离对象
				# =========================================================
				
				if cause_type == 'compound':
					# --- 策略 A: 剥离化合物 ---
					# 如果是因为化合物不稳定，说明该化合物比基体更稳定，应优先剥离
					print(f"  -> [策略] 优先形成并剥离金属间化合物: {cause_info}")
					
					target_composition = primary_cause['stoichiometry']
					# 为化合物生成一个名称，如 "Al2Cu (Intermetallic)"
					# 尝试从 Miedema_AL2CU1 解析出 Al2Cu
					try:
						clean_name = cause_info.replace("Miedema_", "")
						# 简单的重命名逻辑，可根据需要优化
						target_phase_name = f"{clean_name} (Intermetallic)"
					except:
						target_phase_name = f"{cause_info} (Compound)"
					
					target_type = "Precipitate"
				
				else:
					# --- 策略 B: 剥离基体 (原逻辑) ---
					# 如果是因为单质溶解度超标，说明应该形成饱和固溶体
					print(f"  -> [策略] 收缩溶解度，剥离饱和基体")
					
					target_composition = self._find_stable_phase_composition(
							base_alloy=current_comp_norm,
							matrix_phase=base_phase_struct,
							temperature=temperature,
							extrap_func=extrapolation_model_func,
							params=(extrapolation_model_name, activity_model),
							solvent_name=solvent_name
					)
					
					target_phase_name = self._generate_phase_name(target_composition, base_phase_struct)
					target_type = "Matrix" if iteration == 0 else "Intermediate"
				
				# --- 步骤 3: 物质守恒剥离 ---
				print(f"  -> 目标成分: {self._format_comp(target_composition)}")
				
				phase_fraction_abs = self._calculate_max_phase_fraction(
						current_moles_dict, target_composition
				)
				
				print(f"  -> 剥离 {target_phase_name}: {phase_fraction_abs:.4f} mol")
				
				if phase_fraction_abs < min_phase_fraction:
					print("  -> 剥离量过小，停止迭代。")
					final_name = self._generate_phase_name(current_comp_norm, base_phase_struct)
					results.append({
						'phase_name': final_name,
						'composition': current_comp_norm,
						'mole_fraction': total_current_moles,
						'type': 'Residue'
					})
					break
				
				results.append({
					'phase_name': target_phase_name,
					'composition': target_composition,
					'mole_fraction': phase_fraction_abs,
					'type': target_type
				})
				
				# --- 步骤 4: 更新剩余物质 ---
				new_moles_dict = {}
				for el, mols in current_moles_dict.items():
					consumed = phase_fraction_abs * target_composition.get(el, 0.0)
					rem = mols - consumed
					new_moles_dict[el] = max(0.0, rem)
				
				current_moles_dict = new_moles_dict
		
		return results
	
	# =========================================================================
	# 以下辅助函数保持不变 (但为了完整性，包含了之前修改的逻辑)
	# =========================================================================
	
	def _identify_stable_structure_tdb (self, composition, temperature):
		elements = list(composition.keys())
		solvent = max(composition.items(), key=lambda x: x[1])[0]
		try:
			ref = self.tdb_parser.get_stable_phase(solvent, temperature)
			if ref: return ref
		except:
			pass
		return 'FCC_A1'
	
	def _generate_phase_name (self, composition, base_struct):
		sorted_els = sorted(composition.items(), key=lambda x: x[1], reverse=True)
		major_el, major_frac = sorted_els[0]
		if major_frac > 0.90: return f"{base_struct} ({major_el} Matrix)"
		if len(sorted_els) >= 2:
			el1, x1 = sorted_els[0];
			el2, x2 = sorted_els[1]
			sub_total = x1 + x2
			p1 = x1 / sub_total
			ratios = [(2, 1, "2:1"), (1, 2, "1:2"), (3, 1, "3:1"), (1, 3, "1:3"), (1, 1, "1:1"), (5, 1, "5:1"),
			          (1, 5, "1:5"), (3, 2, "3:2"), (2, 3, "2:3")]
			for n1, n2, label in ratios:
				target_p1 = n1 / (n1 + n2)
				if abs(p1 - target_p1) < 0.05:
					return f"{base_struct} ({el1}{n1}{el2}{n2}-like)"
		return f"{base_struct} (Solid Solution)"
	
	def _scan_miedema_compounds (self, composition, temperature, chemical_potentials, solvent_name=None):
		elements = [k for k in composition.keys() if composition[k] > 1e-6]
		if len(elements) < 2: return []
		potential_compounds = []
		ratios = [(1, 1), (1, 2), (1, 3), (2, 1), (3, 1), (2, 3), (3, 2), (1, 5), (5, 1)]
		
		# 仅打印一次开始信息
		# print(f"    [Miedema Check] 正在扫描化合物...")
		
		for el1, el2 in combinations(elements, 2):
			try:
				miedema_model = MiedemaModel((el1, el2), "SOLID")
			except:
				continue
			
			g_pure1 = self.tdb_parser.get_gibbs_energy(el1, 'SER', temperature) or self.tdb_parser.get_gibbs_energy(el1,
			                                                                                                        'SER',
			                                                                                                        298.15)
			g_pure2 = self.tdb_parser.get_gibbs_energy(el2, 'SER', temperature) or self.tdb_parser.get_gibbs_energy(el2,
			                                                                                                        'SER',
			                                                                                                        298.15)
			if g_pure1 is None or g_pure2 is None: continue
			
			mu1, mu2 = chemical_potentials.get(el1), chemical_potentials.get(el2)
			if mu1 is None or mu2 is None: continue
			
			for n1, n2 in ratios:
				x1 = n1 / (n1 + n2)
				x2 = 1.0 - x1
				try:
					h = miedema_model.getmixingEnthalpy_by_Miedema_Model(el1, x1, temperature, order_degree='IM')
				except:
					continue
				
				g_cmp = h + (x1 * g_pure1 + x2 * g_pure2)
				drive = (x1 * mu1 + x2 * mu2) - g_cmp
				
				if drive > 100.0:
					potential_compounds.append({
						'element': el1,  # 此字段在 compound 策略中不重要，但保留兼容性
						'type': 'compound',
						'driving_force': drive,
						'info': f"Miedema_{el1}{n1}{el2}{n2}",
						'stoichiometry': {el1: x1, el2: x2}  # 关键字段
					})
		return potential_compounds
	
	def _check_phase_stability_strict (self, comp, phase, T, func, model, act, solvent_name=None):
		details = []
		is_stable = True
		chemical_potentials = {}
		
		for el in comp:
			if comp[el] < 1e-10: continue
			mu = self._get_chemical_potential(comp, el, T, phase, func, model, act)
			if mu is None: continue
			chemical_potentials[el] = mu
			
			# 单质检查 (Pure Element)
			stable_phase = self.tdb_parser.get_stable_phase(el, T)
			g_ppt = self.tdb_parser.get_gibbs_energy(el, stable_phase, T) or self.tdb_parser.get_gibbs_energy(el, 'SER',
			                                                                                                  T)
			if g_ppt is not None and (mu - g_ppt) > 50.0:
				# 只有当不是溶剂本身时才报错（防止数值噪音）
				if not solvent_name or el != solvent_name:
					is_stable = False
					details.append({'element': el, 'type': 'pure', 'driving_force': mu - g_ppt, 'info': f"Pure {el}"})
		
		# 化合物检查
		if len(chemical_potentials) >= 2:
			compounds = self._scan_miedema_compounds(comp, T, chemical_potentials, solvent_name)
			if compounds:
				is_stable = False
				details.extend(compounds)
		
		details.sort(key=lambda x: x['driving_force'], reverse=True)
		return is_stable, details
	
	def _find_stable_phase_composition (self, base_alloy, matrix_phase, temperature, extrap_func, params, solvent_name):
		# 保持原有的收缩逻辑不变，用于处理 Pure Element 析出的情况
		model_name, act_model = params
		proxy_base = {solvent_name: 1.0}
		candidate_comp = {}
		sum_solutes = 0.0
		
		for el, original_x in base_alloy.items():
			if el == solvent_name: continue
			try:
				res = self.calculate_solubility_v2(proxy_base, el, 'SOLID', temperature, extrap_func, model_name,
				                                act_model)
				limit = res.get('solubility_mole_fraction', 1.0) or 1.0
			except:
				limit = 1.0
			cx = min(original_x, limit)
			candidate_comp[el] = cx
			sum_solutes += cx
		
		candidate_comp[solvent_name] = 1.0 - sum_solutes
		
		for step in range(50):
			tot = sum(candidate_comp.values())
			candidate_comp = {k: v / tot for k, v in candidate_comp.items()}
			stable, details = self._check_phase_stability_strict(candidate_comp, matrix_phase, temperature, extrap_func,
			                                                     model_name, act_model, solvent_name)
			if stable: return candidate_comp
			
			# 如果是 compound 导致的不稳定，削减溶质
			# 找到第一个非溶剂的元素进行削减
			target_el = None
			for d in details:
				if d.get('element') != solvent_name and d.get('element') in candidate_comp:
					target_el = d['element']
					break
			
			if target_el:
				candidate_comp[target_el] *= 0.8
				if candidate_comp[target_el] < 1e-10: candidate_comp[target_el] = 1e-10
			else:
				break
		return candidate_comp
	
	def _calculate_max_phase_fraction (self, total_moles_dict, phase_comp_norm):
		max_frac = float('inf')
		for el, x_phase in phase_comp_norm.items():
			if x_phase < 1e-9: continue
			n_tot = total_moles_dict.get(el, 0.0)
			possible = n_tot / x_phase
			if possible < max_frac: max_frac = possible
		return max_frac
	
	def _format_comp (self, comp):
		return ", ".join([f"{k}:{v:.4f}" for k, v in comp.items() if v > 1e-5])


# =============================================================================
# 测试入口
# =============================================================================
if __name__ == '__main__':
	try:
		from models.extrapolation_models import BinaryModel
		
		model_func = BinaryModel().UEM1
	except ImportError:
		sys.exit(1)
	
	calc = PhaseEquilibriumCalculator()
	
	# 测试案例：Al-10Cu-10Fe @ 200K
	my_alloy = {'AL': 0.80, 'CU': 0.10, "FE": 0.10}
	T_test = 400.0
	
	res = calc.calculate_phase_equilibrium(my_alloy, T_test, extrapolation_model_func=model_func)
	
	print("\n================ 最终计算结果 ================")
	for i, p in enumerate(res):
		print(f"Phase {i + 1}: [{p['phase_name']}] ({p['type']})")
		print(f"  Fraction: {p['mole_fraction']:.2%}")
		print(f"  Composition: {calc._format_comp(p['composition'])}")
		print("-" * 30)