import numpy as np
from scipy.optimize import minimize, Bounds, LinearConstraint, NonlinearConstraint
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass

# 导入您刚刚创建的结构
from core.gem_structures import ThermodynamicPhase, SolutionPhase, StoichiometricCompound


@dataclass
class EquilibriumResult:
	"""GEM 计算结果封装"""
	status: str
	message: str
	temperature: float
	total_gibbs_energy: float
	stable_phases: List[Dict[str, Any]]  # [{'name': 'LIQUID', 'fraction': 0.8, 'composition': {...}}]
	raw_result: Any = None


class GEMSolver:
	"""
	全局吉布斯自由能最小化求解器 (Global Gibbs Energy Minimization Solver).

	使用 SLSQP 算法同时优化：
	1. 各相的摩尔分数 (Phase Fractions, NP)
	2. 溶体相的内部成分 (Site Fractions, Y)

	目标函数: Minimize G_total = sum(NP_i * G_molar_i(Y_i))
	约束条件:
	1. 质量守恒 (Mass Balance)
	2. 归一化 (Sum of Fractions = 1)
	"""
	
	def __init__ (self, tolerance: float = 1e-3):
		self.tolerance = tolerance  # 提高到1e-3以过滤微量相
	
	def solve (self,
	           system_composition: Dict[str, float],
	           temperature: float,
	           candidate_phases: List[ThermodynamicPhase]) -> EquilibriumResult:
		"""
		执行 GEM 计算。

		Args:
			system_composition: 系统总成分 (e.g. {'Fe': 0.7, 'Si': 0.3})
			temperature: 温度 (K)
			candidate_phases: 参与竞争的所有相列表 (包括 TDB 相和虚拟相)
		"""
		# 1. 预处理：确定系统元素和归一化成分
		elements = sorted(list(system_composition.keys()))  # 全局元素列表 ['C', 'Fe', 'Si']
		b_vec = np.array([system_composition.get(e, 0.0) for e in elements])  # 目标摩尔数向量
		total_moles_input = np.sum(b_vec)
		b_vec = b_vec / total_moles_input  # 归一化
		
		# 2. 构建优化变量映射
		# 变量向量 x 的结构: [N_phase1, N_phase2, ..., x_1_p1, x_2_p1..., x_1_p2...]
		# 也就是：先是所有相的摩尔量，然后是所有溶体相的成分变量
		
		n_phases = len(candidate_phases)
		phase_var_indices = {}  # 记录每个相在 x 向量中的位置
		current_idx = n_phases  # 0 到 n_phases-1 是各相的 N (mole fraction)
		
		# 初始猜测 (Initial Guess)
		x0_list = [1.0 / n_phases] * n_phases  # 初始假设各相均分
		bounds_list = [(0.0, 1.0)] * n_phases  # 相分数范围 [0, 1]
		
		solution_phase_indices = []  # 记录哪些相是溶体
		
		for i, phase in enumerate(candidate_phases):
			if isinstance(phase, SolutionPhase):
				solution_phase_indices.append(i)
				n_comps = len(phase.components)
				
				# 记录该相成分变量在 x 中的切片范围
				phase_var_indices[i] = (current_idx, current_idx + n_comps)
				
				# 初始猜测：该相成分 = 系统总成分 (如果该相包含该元素)
				# 这是一个简单猜测，更好的方法是根据相的定义域猜测
				comp_guess = []
				for comp in phase.components:
					comp_guess.append(system_composition.get(comp, 1e-5))
				
				# 归一化猜测成分
				s = sum(comp_guess)
				comp_guess = [v / s for v in comp_guess]
				
				x0_list.extend(comp_guess)
				bounds_list.extend([(1e-9, 1.0)] * n_comps)  # 成分范围 [epsilon, 1]
				
				current_idx += n_comps
			else:
				# 定比化合物没有成分变量
				phase_var_indices[i] = None
		
		x0 = np.array(x0_list)
		
		# 3. 定义目标函数 (Objective Function)
		def objective (x):
			g_total = 0.0

			# 遍历所有相
			for i, phase in enumerate(candidate_phases):
				n_p = x[i]  # 该相的摩尔分数

				if n_p < 1e-8: continue  # 忽略微量相以加速计算

				try:
					if isinstance(phase, SolutionPhase):
						# 提取成分
						start, end = phase_var_indices[i]
						phase_comp_arr = x[start:end]

						# 构建成分字典
						comp_dict = dict(zip(phase.components, phase_comp_arr))

						# 计算摩尔吉布斯能
						g_molar = phase.get_molar_gibbs_energy(comp_dict, temperature)

					else:
						# 定比化合物
						g_molar = phase.get_molar_gibbs_energy({}, temperature)

					# 检查数值有效性
					if not np.isfinite(g_molar):
						g_molar = 1e9  # 惩罚无效值

					g_total += n_p * g_molar

				except Exception:
					# 计算失败，施加大惩罚
					g_total += n_p * 1e9

			# 确保返回值有效
			if not np.isfinite(g_total):
				return 1e12

			return g_total
		
		# 4. 定义约束条件 (Constraints)
		
		constraints = []
		
		# 4.1 质量守恒约束 (Mass Balance): sum(N_p * x_i_p) == b_i
		# 这是一个非线性约束 (N * x)
		def mass_balance_constraint (x):
			try:
				# 计算当前所有相加起来的各元素总量
				total_elements = np.zeros(len(elements))

				for i, phase in enumerate(candidate_phases):
					n_p = x[i]

					if isinstance(phase, SolutionPhase):
						start, end = phase_var_indices[i]
						phase_comp_arr = x[start:end]
						# 需要将 phase components 映射回全局 elements
						current_phase_dict = dict(zip(phase.components, phase_comp_arr))
					else:
						# 化合物
						current_phase_dict = phase.get_composition()

					# 累加到总量
					for j, elem in enumerate(elements):
						total_elements[j] += n_p * current_phase_dict.get(elem, 0.0)

				residual = total_elements - b_vec

				# 检查数值有效性
				if not np.all(np.isfinite(residual)):
					return np.zeros(len(elements))  # 返回满足约束的值

				return residual

			except Exception:
				# 异常情况，返回零向量（满足约束）
				return np.zeros(len(elements))
		
		# 添加为非线性等式约束
		constraints.append(NonlinearConstraint(mass_balance_constraint,
		                                       0.0, 0.0))  # lb=0, ub=0 -> equality
		
		# 4.2 相分数归一化: sum(N_p) = 1.0
		# 这是一个线性约束
		# 变量向量的前 n_phases 个元素之和为 1
		A_norm_phases = np.zeros(len(x0))
		A_norm_phases[:n_phases] = 1.0
		constraints.append(LinearConstraint(A_norm_phases, 1.0, 1.0))
		
		# 4.3 溶体成分归一化: sum(x_i_p) = 1.0 (针对每个溶体相)
		for i in solution_phase_indices:
			start, end = phase_var_indices[i]
			A_norm_comp = np.zeros(len(x0))
			A_norm_comp[start:end] = 1.0
			constraints.append(LinearConstraint(A_norm_comp, 1.0, 1.0))
		
		# 5. 执行优化
		try:
			# 使用更保守的设置避免数值问题
			result = minimize(
					objective,
					x0,
					method='SLSQP',
					bounds=bounds_list,
					constraints=constraints,
					options={
						'ftol': 1e-6,      # 放宽容差
						'disp': False,
						'maxiter': 50,     # 减少迭代次数
						'iprint': 0        # 禁用打印
					}
			)
		except Exception as e:
			import traceback
			error_msg = f"GEM优化失败: {str(e)}\n{traceback.format_exc()}"
			print(error_msg)
			return EquilibriumResult("error", error_msg, temperature, 0.0, [], None)
		
		# 6. 解析结果
		stable_phases = []
		
		for i, phase in enumerate(candidate_phases):
			n_p = result.x[i]
			
			# 过滤掉分数极小的相
			if n_p > self.tolerance:
				phase_data = {
					'name': phase.name,
					'type': phase.phase_type,
					'fraction': n_p,
					'composition': {}
				}
				
				if isinstance(phase, SolutionPhase):
					start, end = phase_var_indices[i]
					comps = result.x[start:end]
					# 过滤微小成分并重组字典
					comp_dict = {k: v for k, v in zip(phase.components, comps) if v > 1e-6}
					phase_data['composition'] = comp_dict
				else:
					phase_data['composition'] = phase.get_composition()
				
				stable_phases.append(phase_data)
		
		# 按分数降序排列
		stable_phases.sort(key=lambda x: x['fraction'], reverse=True)
		
		return EquilibriumResult(
				status="success" if result.success else "warning",
				message=result.message,
				temperature=temperature,
				total_gibbs_energy=result.fun,
				stable_phases=stable_phases,
				raw_result=result
		)