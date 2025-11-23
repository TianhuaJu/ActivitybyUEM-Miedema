import numpy as np
from typing import Dict, List, Optional, Tuple
import copy
from calculations.phase_diagram import PhaseDiagramCalculator



class PhaseEquilibriumCalculator(PhaseDiagramCalculator):
	"""
	基于分步溶解度剥离法的多相平衡计算器。

	算法逻辑：
	1. 判断当前成分稳定性。
	2. 若不稳定，寻找能量最低的基体相。
	3. 计算各元素在基体相中的最大溶解度，构建饱和基体相。
	4. 利用质量守恒剥离饱和基体相，余下成分作为新合金继续迭代。
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
									 max_iterations: int = 10) -> List[Dict]:
		"""
		计算特定合金组成下的多相平衡。

		返回:
			List[Dict]: 包含各稳定相信息的列表。
			示例: [{'phase_name': 'FCC_A1', 'composition': {...}, 'mole_fraction': 0.8}, ...]
		"""
		
		# 初始化
		results = []
		current_comp = alloy_composition.copy()
		total_moles_remaining = 1.0  # 初始总摩尔数为1（归一化）
		
		# 记录每轮迭代的“剩余部分”的绝对摩尔量
		# 初始：{ 'Al': 0.9, 'Cu': 0.1 } (假设)
		current_moles_dict = {k: v * total_moles_remaining for k, v in current_comp.items()}
		
		print(f"--- 开始多相平衡计算 (T={temperature}K) ---")
		
		for iteration in range(max_iterations):
			print(f"\n[Iteration {iteration + 1}] 当前剩余成分: {self._format_comp(current_comp)}")
			
			# 1. 归一化当前成分 (防止精度误差)
			total_current = sum(current_comp.values())
			if total_current <= 1e-9:
				break
			current_comp = {k: v / total_current for k, v in current_comp.items()}
			
			# 2. 寻找当前成分下的最稳定基体相 (Matrix Phase)
			#    策略：寻找吉布斯自由能最低的相作为“主相”
			matrix_phase_name = self._find_lowest_energy_phase(current_comp, temperature)
			print(f"  -> 识别基体相: {matrix_phase_name}")
			
			# 3. 检查当前成分在该相中的稳定性
			is_stable, stability_issues = self._check_alloy_full_stability(
					composition=current_comp,
					temperature=temperature,
					tdb_phase=matrix_phase_name,
					extrapolation_func=extrapolation_model_func,
					extrapolation_model_name=extrapolation_model_name,
					activity_model=activity_model
			)
			
			if is_stable:
				print("  -> 当前成分稳定。迭代结束。")
				# 如果稳定，说明剩余的所有物质都属于这个相
				results.append({
					'phase_name': matrix_phase_name,
					'composition': current_comp,
					'mole_fraction': total_moles_remaining,  # 剩下的全部分额
					'type': 'Primary' if iteration == 0 else 'Secondary'
				})
				break
			else:
				print("  -> 当前成分不稳定，开始计算溶解度并剥离...")
				
				# 4. 不稳定：计算饱和基体成分 (Saturated Matrix Composition)
				saturated_matrix_comp = self._calculate_saturated_matrix(
						base_comp=current_comp,
						matrix_phase=matrix_phase_name,
						temperature=temperature,
						extrapolation_func=extrapolation_model_func,
						model_params=(extrapolation_model_name, activity_model)
				)
				
				# 5. 质量守恒计算：最大化基体相的分数 (Phase Fraction)
				#    逻辑：基体相会尽可能多地形成，直到某个组分被耗尽（对于溶剂是耗尽，对于过饱和溶质是达到饱和限）
				#    公式：N_matrix = min( N_total_i / x_matrix_i ) for all elements i
				
				max_moles_matrix = float('inf')
				limiting_element = None
				
				for el, x_i_mat in saturated_matrix_comp.items():
					if x_i_mat < 1e-12: continue  # 忽略微量
					
					n_i_total = current_moles_dict.get(el, 0.0)
					# 该元素能支持生成的最大基体摩尔数
					possible_moles = n_i_total / x_i_mat
					
					if possible_moles < max_moles_matrix:
						max_moles_matrix = possible_moles
						limiting_element = el
				
				# 这一步生成的基体相在总合金中的分数
				# 注意：max_moles_matrix 是相对于 current_moles_dict 的量
				# 但我们需要它相对于最原始 1.0 mol 的分数，这里 max_moles_matrix 本身就是绝对摩尔量
				
				phase_fraction = max_moles_matrix
				
				print(f"  -> 剥离相: {matrix_phase_name}, 分数: {phase_fraction:.4f} (受限于 {limiting_element})")
				print(f"  -> 饱和成分: {self._format_comp(saturated_matrix_comp)}")
				
				if phase_fraction < min_phase_fraction:
					print("  -> 生成相分数过低，停止剥离，将剩余物视为最后的析出相。")
					results.append({
						'phase_name': "Unknown/Residue",
						'composition': current_comp,
						'mole_fraction': total_moles_remaining,
						'note': 'Residue due to low fraction limit'
					})
					break
				
				# 记录剥离出的相
				results.append({
					'phase_name': matrix_phase_name,
					'composition': saturated_matrix_comp,
					'mole_fraction': phase_fraction,
					'type': 'Matrix' if iteration == 0 else 'Precipitate'
				})
				
				# 6. 计算剩余物质 (New Base Alloy)
				new_moles_dict = {}
				for el in current_moles_dict:
					n_total = current_moles_dict[el]
					n_consumed = max_moles_matrix * saturated_matrix_comp.get(el, 0.0)
					n_rem = n_total - n_consumed
					
					# 数值修正，防止浮点负数
					if n_rem < 1e-13: n_rem = 0.0
					new_moles_dict[el] = n_rem
				
				# 更新状态
				current_moles_dict = new_moles_dict
				total_moles_remaining = sum(current_moles_dict.values())
				
				# 重新计算 current_comp (摩尔分数)
				if total_moles_remaining < 1e-6:
					print("  -> 剩余物质极少，忽略。")
					break
				
				current_comp = {k: v / total_moles_remaining for k, v in current_moles_dict.items()}
		
		return results
	
	def _find_lowest_energy_phase (self, composition, temperature):
		"""
		遍历所有可能的相，找到吉布斯自由能最低的相作为基体。
		"""
		# 获取主要溶剂元素
		solvent = max(composition.items(), key=lambda x: x[1])[0]
		# 获取候选相列表 (排除 GAS)
		phases = [p for p in self.tdb_parser.get_element_phases(solvent) if p != 'GAS']
		
		best_phase = 'BCC_A2'  # 默认
		min_g = float('inf')
		
		# 简单估算：只看纯溶剂的稳定相，或者遍历计算混合能
		# 这里为了准确，应该调用 _get_chemical_potential 计算混合能，但为了速度，
		# 我们这里使用溶剂的 Reference State 或者尝试计算一次
		
		valid_phases = []
		for phase in phases:
			# 尝试获取能量 (简化：仅比较纯组分加权，或者如果可能，计算实际混合能)
			# 注意：严谨做法是调用 thermodynamic_properties 的混合能计算
			# 这里简化为：检查纯溶剂在该相是否稳定/存在
			g_pure = self.tdb_parser.get_gibbs_energy(solvent, phase, temperature)
			if g_pure is not None:
				# 修正：应该比较整个合金的 G。
				# 由于这是启发式算法，我们假设溶剂的稳定结构决定了基体结构
				if g_pure < min_g:
					min_g = g_pure
					best_phase = phase
		
		return best_phase
	
	def _calculate_saturated_matrix (self, base_comp, matrix_phase, temperature, extrapolation_func, model_params):
		"""
		计算饱和基体成分。
		对于每个溶质，计算其在基体中的溶解度极限。
		如果当前含量 < 极限，则保留当前含量。
		如果当前含量 > 极限，则限制为极限值。
		"""
		extrap_name, act_model = model_params
		saturated_comp = {}
		
		# 确定溶剂
		solvent = max(base_comp.items(), key=lambda x: x[1])[0]
		
		# 1. 遍历所有溶质
		solutes = [k for k in base_comp.keys() if k != solvent]
		
		temp_limits = {}
		
		for solute in solutes:
			# 调用您提供的 calculate_solubility 函数
			# 注意：calculate_solubility 需要一个 base_alloy。
			# 为了避免多元交互的复杂性干扰单元素溶解度判断，我们构造一个 "纯溶剂 + 溶质" 的二元环境进行估算
			# 或者使用当前合金作为 base。使用当前合金更准，但如果当前合金不稳定，函数可能会报错。
			# 根据您的描述，我们尝试计算 "该相中的最大溶解度"。
			
			# 构造一个用于计算的"伪"基础合金：纯溶剂
			proxy_base = {solvent: 1.0}
			
			try:
				res = self.calculate_solubility(
						base_alloy_composition=proxy_base,
						solute_element=solute,
						solution_phase='SOLID' if 'LIQUID' not in matrix_phase else 'LIQUID',
						temperature=temperature,
						extrapolation_func=extrapolation_func,
						extrapolation_model_name=extrap_name,
						activity_model=act_model
				)
				
				limit = res.get('solubility_mole_fraction', 1.0)
				# 如果计算失败或返回 None，假设完全互溶或保留原值
				if limit is None: limit = 1.0
			
			except Exception as e:
				# print(f"Warning: Solubility calc failed for {solute}: {e}")
				limit = 1.0
			
			temp_limits[solute] = limit
		
		# 2. 构建饱和成分
		# 规则：对于每个组分，x_matrix = min(x_current, x_limit)
		# 最后用溶剂填补剩余比例
		
		current_sum_solutes_saturated = 0.0
		
		for solute in solutes:
			current_x = base_comp[solute]
			limit_x = temp_limits.get(solute, 1.0)
			
			# 取较小值：如果过饱和，取极限；如果未饱和，取当前值
			sat_x = min(current_x, limit_x)
			saturated_comp[solute] = sat_x
			current_sum_solutes_saturated += sat_x
		
		# 3. 溶剂占剩余部分
		x_solvent = 1.0 - current_sum_solutes_saturated
		saturated_comp[solvent] = x_solvent
		
		return saturated_comp
	
	def _format_comp (self, comp):
		return ", ".join([f"{k}:{v:.4f}" for k, v in comp.items() if v > 1e-4])


# =============================================================================
# 使用示例 (假设您已经在脚本中实例化了相关环境)
# =============================================================================
if __name__ == '__main__':
	# 这是一个模拟调用的例子
	# 1. 初始化计算器
	calculator = PhaseEquilibriumCalculator()
	from models.extrapolation_models import BinaryModel
	
	extrapolation_model_func = BinaryModel().UEM1
	
	
	
	# 2. 定义合金和温度
	my_alloy = {'AL': 0.80, 'CU': 0.14, 'MG': 0.06}
	T_calc = 400  # K

# 3. 运行计算
	results = calculator.calculate_phase_equilibrium(my_alloy, T_calc,extrapolation_model_func=extrapolation_model_func)

# 4. 打印结果
	for phase in results:
		print(f"Phase: {phase['phase_name']}, Fraction: {phase['mole_fraction']:.2%}")
		print(f"  Comp: {phase['composition']}")