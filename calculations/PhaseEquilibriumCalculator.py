import math
import sys
import os
import copy
from typing import Dict, List, Optional, Tuple

# 确保能找到父类
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculations.phase_diagram import PhaseDiagramCalculator


class PhaseEquilibriumCalculator(PhaseDiagramCalculator):
	"""
	基于“稳定性收缩-剥离法”的多相平衡计算器。
	逻辑：
	1. 检查整体合金稳定性。若稳定 -> 结束。
	2. 若不稳定 -> 计算单元素最大溶解度作为初始猜测。
	3. 收缩循环：若猜测成分仍不稳定，找到驱动力最大的元素逐步减少其含量，直至找到稳定边界。
	4. 剥离稳定相，剩余残渣进入下一轮。
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
		# 追踪当前的绝对摩尔量 (初始设为 1.0 mol)
		current_moles_dict = alloy_composition.copy()
		total_moles_system = sum(current_moles_dict.values())  # 应该是 1.0
		
		# 归一化初始摩尔量到1
		current_moles_dict = {k: v / total_moles_system for k, v in current_moles_dict.items()}
		
		print(f"--- 开始多相平衡计算 (T={temperature}K) ---")
		
		for iteration in range(max_iterations):
			total_current_moles = sum(current_moles_dict.values())
			if total_current_moles < 1e-6:
				break
			
			# 计算当前的归一化成分 (Mole Fraction)
			current_comp_norm = {k: v / total_current_moles for k, v in current_moles_dict.items()}
			
			# 格式化输出
			comp_str = self._format_comp(current_comp_norm)
			print(f"\n[Iteration {iteration + 1}] 剩余合金 (总量 {total_current_moles:.4f}): {comp_str}")
			
			# --- 步骤 1: 确定基体相 (Matrix Phase) ---
			# 通常是溶剂对应的相
			solvent = max(current_comp_norm.items(), key=lambda x: x[1])[0]
			# 简单策略：根据温度和溶剂选择基体结构
			matrix_phase = self._determine_matrix_structure(solvent, temperature)
			print(f"  -> 假定基体结构: {matrix_phase}")
			
			# --- 步骤 2: 判断当前基础合金的稳定性 ---
			is_stable, unstable_details = self._check_phase_stability_strict(
					current_comp_norm, matrix_phase, temperature,
					extrapolation_model_func, extrapolation_model_name, activity_model
			)
			
			if is_stable:
				print("  -> [判定] 当前合金稳定 (单一相)。")
				results.append({
					'phase_name': matrix_phase,
					'composition': current_comp_norm,
					'mole_fraction': total_current_moles,  # 剩余所有物质都属于此相
					'type': 'Primary' if iteration == 0 else 'Residue'
				})
				break  # 结束循环
			else:
				print(
					f"  -> [判定] 不稳定。最显著的不稳定元素: {unstable_details[0]['element']} (Δμ={unstable_details[0]['driving_force']:.2f})")
				
				# --- 步骤 3 & 4: 寻找稳定相边界 (先溶解度，后收缩) ---
				stable_matrix_comp = self._find_stable_phase_composition(
						base_alloy=current_comp_norm,
						matrix_phase=matrix_phase,
						temperature=temperature,
						extrap_func=extrapolation_model_func,
						params=(extrapolation_model_name, activity_model)
				)
				
				print(f"  -> 确定稳定相成分: {self._format_comp(stable_matrix_comp)}")
				
				# --- 步骤 5: 物质守恒剥离 (Peeling) ---
				# 计算能形成的最大相分数
				phase_fraction_abs = self._calculate_max_phase_fraction(
						current_moles_dict, stable_matrix_comp
				)
				
				print(f"  -> 剥离量: {phase_fraction_abs:.4f} mol")
				
				if phase_fraction_abs < min_phase_fraction:
					print("  -> 剥离量过小，视为残余相并停止。")
					results.append({
						'phase_name': "Precipitate_Mix",
						'composition': current_comp_norm,
						'mole_fraction': total_current_moles,
						'type': 'Residue'
					})
					break
				
				# 记录剥离出的稳定相
				results.append({
					'phase_name': matrix_phase,
					'composition': stable_matrix_comp,
					'mole_fraction': phase_fraction_abs,
					'type': 'Matrix' if iteration == 0 else 'Intermediate'
				})
				
				# --- 步骤 6: 计算余下成分 (New Base Alloy) ---
				new_moles_dict = {}
				for el, mols in current_moles_dict.items():
					consumed = phase_fraction_abs * stable_matrix_comp.get(el, 0.0)
					rem = mols - consumed
					new_moles_dict[el] = max(0.0, rem)  # 修正负数
				
				current_moles_dict = new_moles_dict
		
		return results
	
	def _determine_matrix_structure (self, solvent, temperature):
		"""根据溶剂和温度确定基体结构"""
		# 这里可以使用更复杂的逻辑，目前简化处理
		tm = 933.0 if solvent == 'AL' else 1350.0
		if temperature > tm:
			return 'LIQUID'
		
		# 获取溶剂的参考相
		ref = self.tdb_parser.get_reference_phase(solvent)
		return ref if ref else 'FCC_A1'
	
	def _check_phase_stability_strict (self, comp, phase, T, func, model, act):
		"""
		严格检查相稳定性。
		计算每个组分的化学势 mu_i。
		如果 mu_i > G_precipitate_i，则不稳定。
		返回: (bool, list_of_details)
		"""
		details = []
		is_stable = True
		
		for el in comp:
			if comp[el] < 1e-10: continue  # 忽略微量
			
			# 1. 计算当前相中的化学势
			mu = self._get_chemical_potential(comp, el, T, phase, func, model, act)
			if mu is None: continue
			
			# 2. 获取该元素以析出相存在时的能量 (G_ppt)
			#    这里假设析出相为该元素的稳定态 (如 Al_2Cu 需要更复杂的逻辑，这里简化为纯组分或稳定晶格)
			#    为了更严谨，这里应该比较所有可能的析出相，取最低能量。
			#    简化：取该元素的参考状态 (SER) 或 稳定相
			stable_phase_name = self.tdb_parser.get_stable_phase(el, T)
			g_ppt = self.tdb_parser.get_gibbs_energy(el, stable_phase_name, T)
			
			if g_ppt is None: continue
			
			# 3. 计算驱动力 Delta_Mu = mu_solution - G_precipitate
			#    如果 > 0，说明倾向于析出
			driving_force = mu - g_ppt
			
			# 设置容差 (如 100 J/mol)
			tolerance = 10.0
			if driving_force > tolerance:
				is_stable = False
				details.append({
					'element': el,
					'driving_force': driving_force,
					'mu': mu,
					'g_ppt': g_ppt
				})
		
		# 按驱动力排序，最大的排前面
		details.sort(key=lambda x: x['driving_force'], reverse=True)
		return is_stable, details
	
	def _find_stable_phase_composition (self, base_alloy, matrix_phase, temperature, extrap_func, params):
		"""
		核心逻辑：寻找稳定相成分。
		1. 先计算各元素的最大理论溶解度 (Max Solubility)。
		2. 构建初始猜测相。
		3. 如果不稳定，按驱动力最大的元素逐步减少含量，直到稳定。
		"""
		model_name, act_model = params
		solvent = max(base_alloy.items(), key=lambda x: x[1])[0]
		
		# --- A. 计算初始溶解度 (使用纯溶剂作为基准) ---
		proxy_base = {solvent: 1.0}
		solubility_limits = {}
		
		for el in base_alloy:
			if el == solvent: continue
			try:
				res = self.calculate_solubility(
						base_alloy_composition=proxy_base,
						solute_element=el,
						solution_phase='LIQUID' if matrix_phase == 'LIQUID' else 'SOLID',
						temperature=temperature,
						extrapolation_func=extrap_func,
						extrapolation_model_name=model_name,
						activity_model=act_model
				)
				limit = res.get('solubility_mole_fraction', 1.0)
				if limit is None: limit = 1.0
				solubility_limits[el] = limit
			except:
				solubility_limits[el] = 1.0
		
		# --- B. 构建初始候选相 ---
		# 候选相中 solute = min(base_alloy[solute], solubility_limit)
		candidate_comp = {}
		sum_solutes = 0.0
		
		for el, original_x in base_alloy.items():
			if el == solvent: continue
			limit = solubility_limits.get(el, 1.0)
			candidate_x = min(original_x, limit)
			candidate_comp[el] = candidate_x
			sum_solutes += candidate_x
		
		candidate_comp[solvent] = 1.0 - sum_solutes
		
		# --- C. 收缩循环 (Reduction Loop) ---
		# 按照您要求的思路：如果依然不稳，逐渐减少其中影响最大的元素含量
		
		max_reduction_steps = 50
		reduction_factor = 0.8  # 每次减少 20%
		
		for step in range(max_reduction_steps):
			# 归一化
			tot = sum(candidate_comp.values())
			candidate_comp = {k: v / tot for k, v in candidate_comp.items()}
			
			# 检查稳定性
			stable, details = self._check_phase_stability_strict(
					candidate_comp, matrix_phase, temperature, extrap_func, model_name, act_model
			)
			
			if stable:
				# 找到了！
				return candidate_comp
			
			# 找到了不稳定因素，开始削减
			# details[0] 是驱动力最大的那个元素
			worst_element = details[0]['element']
			driving_force = details[0]['driving_force']
			
			# print(f"    [Step {step}] 修正: 减少 {worst_element} (Δμ={driving_force:.1f})")
			
			# 削减该元素含量
			old_x = candidate_comp[worst_element]
			new_x = old_x * reduction_factor
			
			# 如果削减到极低，直接设为痕量
			if new_x < 1e-9: new_x = 1e-9
			
			candidate_comp[worst_element] = new_x
		# 溶剂会自动在下一轮归一化时补齐
		
		return candidate_comp
	
	def _calculate_max_phase_fraction (self, total_moles_dict, phase_comp_norm):
		"""
		利用物质守恒计算相分数。
		Fraction = min( Total_i / Phase_i )
		"""
		max_frac = float('inf')
		
		for el, x_phase in phase_comp_norm.items():
			if x_phase < 1e-9: continue
			
			n_tot = total_moles_dict.get(el, 0.0)
			possible = n_tot / x_phase
			
			if possible < max_frac:
				max_frac = possible
		
		return max_frac
	
	def _format_comp (self, comp):
		return ", ".join([f"{k}:{v:.4f}" for k, v in comp.items() if v > 1e-5])


# =============================================================================
# 测试入口
# =============================================================================
if __name__ == '__main__':
	# 1. 显式加载模型函数 (必须步骤)
	try:
		from models.extrapolation_models import BinaryModel
		
		model_func = BinaryModel().UEM1
	except ImportError:
		print("错误：无法导入 BinaryModel，请检查路径。")
		sys.exit(1)
	
	# 2. 初始化
	calc = PhaseEquilibriumCalculator()
	
	# 3. 设置测试条件
	# Al-14at%Cu (过饱和固溶体), T=400K (低温)
	# 预期：
	# 第一步：识别 FCC 不稳定 (Cu过饱和)。
	# 第二步：计算出 FCC 中 Cu 的极限溶解度极低 (例如 0.001)。
	# 第三步：剥离出近乎纯铝的 FCC 相。
	# 第四步：剩余物变成高 Cu 浓度的相 (Al2Cu 前体)。
	
	my_alloy = {'AL': 0.66, 'CU': 0.14,'SI':0.2}
	T_test = 400.0
	
	# 4. 运行
	res = calc.calculate_phase_equilibrium(
			my_alloy,
			T_test,
			extrapolation_model_func=model_func
	)
	
	# 5. 结果展示
	print("\n================ 最终计算结果 ================")
	for i, p in enumerate(res):
		name = p['phase_name']
		frac = p['mole_fraction']
		ctype = p['type']
		comp = calc._format_comp(p['composition'])
		print(f"Phase {i + 1}: [{name}] ({ctype})")
		print(f"  Fraction: {frac:.2%}")
		print(f"  Composition: {comp}")
		print("-" * 30)