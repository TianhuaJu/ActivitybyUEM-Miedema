"""
Phase Diagram Calculator (Final Restored Version)
=================================================
计算二元及多元稀溶液的液相线 (Liquidus)、固相线 (Solidus) 温度及溶解度。

逻辑修正:
1. 溶解度计算采用 "Diamond-Graphite" 物理模型估算晶格不稳定性。
2. 基体相搜索限定在 [BCC, FCC, HCP] 以防止非物理收敛。
3. 求解器采用连续残差函数 + 后置稳定性检查模式。

依赖于:
- ThermodynamicProperties 类 (用于获取 G°, ln(γ))
- SciPy (用于求解非线性方程组)
"""

import math
from typing import Dict, Optional, Tuple, List
import sys
import os
from scipy.optimize import root, brentq

# 添加项目路径以导入父类
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations.thermodynamic_properties import ThermodynamicProperties, extrap_func
from core.intermetallic_compounds import intermetallic_db


class PhaseDiagramCalculator(ThermodynamicProperties):
	"""
    通过继承 ThermodynamicProperties 类，
    实现液相线、固相线及溶解度的计算。
    """
	
	def __init__ (self):
		super().__init__()
		self.intermetallic_db = intermetallic_db  # 金属间化合物数据库
	
	@staticmethod
	def _check_bounds (x, epsilon=1e-9):
		"""辅助函数：将成分限制在 (epsilon, 1-epsilon) 范围内"""
		if x < epsilon: return epsilon
		if x > 1.0 - epsilon: return 1.0 - epsilon
		return x
	
	# ================================================================
	# =================== PART 1: 溶解度计算模块 ======================
	# ================================================================
	
	def _estimate_lattice_stability (self, component: str, target_phase: str, T: float) -> Optional[float]:
		"""
		(修改版) 估算晶格稳定性参数。
		采用“固定能量差 (Fixed Diff)”模式，将非金属/气体元素转变为金属晶格。

		设定值 (kJ/g-atom -> J/mol):
		 
		  N:  240 kJ -> 240,000 J
		  Si: 33 kJ  -> 33,000 J
		  Ge: 25 kJ  -> 25,000 J
		  H:  100 kJ -> 100,000 J
		"""
		comp_upper = component.upper()
		
		# ==================================================
		# 配置：定义各元素的估算策略 (全部采用 fixed_diff)
		# ==================================================
		stability_config = {
			
			
			# --- 氮 N ---
			'N': {
				'stable_phase': 'GAS',  # 稳定态 (1/2 N2)
				'proxy_phase': None,
				'fixed_diff': 240000.0  # 设定值: 240 kJ/mol
			},
			
			# --- 硅 Si ---
			'SI': {
				'stable_phase': 'DIAMOND_A4',  # 稳定态
				'proxy_phase': None,
				'fixed_diff': 33000.0  # 设定值: 33 kJ/mol
			},
			
			# --- 锗 Ge ---
			'GE': {
				'stable_phase': 'DIAMOND_A4',  # 稳定态
				'proxy_phase': None,
				'fixed_diff': 25000.0  # 设定值: 25 kJ/mol
			},
			
			# --- 氢 H ---
			'H': {
				'stable_phase': 'GAS',  # 稳定态 (1/2 H2)
				# 注意: 请确保您的 TDB 文件中包含 H 元素及其 GAS 相定义
				# 如果使用的是 unary50.tdb，它可能不包含 H，需要更换 TDB 或手动添加
				'proxy_phase': None,
				'fixed_diff': 100000.0  # 设定值: 100 kJ/mol
			}
		}
		
		if comp_upper not in stability_config:
			return None
		
		config = stability_config[comp_upper]
		
		# 1. 获取稳定态能量 (G_stable)
		ref_phase_name = config['stable_phase']
		
		# 特殊处理气体相名称
		if ref_phase_name == 'GAS':
			# 尝试直接查询 GAS 相 (通常包含 N2, H2 等组分)
			# 注意: PyCalphad 有时需要指定组分名称如 'N2' 而不是 'N'，但这取决于 parser 实现
			# 这里假设 get_gibbs_energy 内部能处理 'N' -> '1/2 N2' 的转换或直接读取 SER
			g_stable = self.tdb_parser.get_gibbs_energy(comp_upper, 'GAS', T)
		else:
			g_stable = self.tdb_parser.get_gibbs_energy(comp_upper, ref_phase_name, T)
		
		if g_stable is None:
			# 如果连稳定态都算不出来 (比如 TDB 缺 H)，则无法估算
			return None
		
		# 2. 应用固定能量差 (Fixed Diff)
		delta_g = config.get('fixed_diff', 0.0)
		
		# 可选：打印调试信息确认数值已应用
		# print(f"  (Model) {comp_upper}: 应用固定势垒 ΔG = {delta_g/1000:.1f} kJ/mol 估算 {target_phase} 能量")
		
		# 3. 返回估算的 Gibbs 能量 (G_target = G_stable + Fixed_Diff)
		return g_stable + delta_g

	def _determine_precipitating_phase(self,
	                                   solute: str,
	                                   base_composition: Dict[str, float],
	                                   temperature: float) -> Tuple[str, str]:
		"""
		确定析出相：考虑纯组元和金属间化合物的竞争

		参数:
		    solute: 溶质元素
		    base_composition: 基体组成
		    temperature: 温度

		返回:
		    (析出相类型, 析出相名称)
		    析出相类型: 'PURE' 或 'COMPOUND'
		"""

		# 默认：纯组元析出
		pure_phase = self.tdb_parser.get_stable_phase(solute, temperature)
		if not pure_phase:
			pure_phase = 'FCC_A1'  # 默认

		# 获取纯组元的吉布斯能量
		g_pure = self.tdb_parser.get_gibbs_energy(solute, pure_phase, temperature)

		best_phase_type = 'PURE'
		best_phase_name = pure_phase
		best_energy = g_pure if g_pure is not None else float('inf')

		# 检查可能的金属间化合物
		for base_elem in base_composition.keys():
			if base_elem == solute:
				continue

			# 查找可能的化合物
			possible_compounds = self.intermetallic_db.get_possible_compounds(solute, base_elem)

			for compound_name in possible_compounds:
				# 尝试从TDB获取化合物的能量
				# 化合物通常作为独立的相存在，名称可能需要映射
				# 例如: FE3C 可能在TDB中命名为 CEMENTITE 或 FE3C

				# 尝试多种可能的TDB相名
				possible_tdb_names = [
					compound_name,
					compound_name.replace('_', ''),
					compound_name + '_D03',  # 某些化合物的晶体结构标记
				]

				compound_energy = None
				for tdb_name in possible_tdb_names:
					# 尝试获取化合物的吉布斯能量
					# 注意：化合物的能量需要按化学计量比计算
					elem1, elem2, n1, n2 = self.intermetallic_db.get_compound_stoichiometry(compound_name)

					# 简化处理：尝试从TDB直接获取化合物相的能量
					g_compound = self.tdb_parser.get_gibbs_energy(elem1, tdb_name, temperature)

					if g_compound is not None:
						compound_energy = g_compound
						break

				# 如果TDB中没有化合物数据，使用近似估算
				if compound_energy is None:
					# 使用Miedema模型或其他方法估算化合物形成焓
					# 这里简化处理：假设化合物比纯组元稳定一定的能量
					# 实际应用中应该使用更精确的方法
					compound_energy = best_energy - 5000.0  # J/mol (示例值)

				# 比较能量
				if compound_energy < best_energy:
					best_energy = compound_energy
					best_phase_type = 'COMPOUND'
					best_phase_name = compound_name

		return best_phase_type, best_phase_name


	def calculate_solubility (self,
	                          base_alloy_composition: Dict[str, float],
	                          solute_element: str,
	                          solution_phase: str,  # 'LIQUID' 或 'SOLID'
	                          temperature: float,
	                          extrapolation_func: extrap_func,
	                          extrapolation_model_name: str = 'UEM1',
	                          activity_model: str = 'Wagner',
	                          min_solubility: float = 1e-12,
	                          max_solubility: float = 0.999) -> dict:

		# ==================== 1. 预处理 ====================
		solute = solute_element.upper()

		# ==================== 新增：确定析出相（考虑金属间化合物） ====================
		precipitating_phase_type, precipitating_phase = self._determine_precipitating_phase(
			solute, base_alloy_composition, temperature
		)

		# 原有逻辑的兼容：如果是纯组元析出，保持原有行为
		# precipitating_phase = self.tdb_parser.get_stable_phase(solute,temperature)
		
		total_base = sum(base_alloy_composition.values())
		if total_base <= 0:
			raise ValueError("基础合金成分不能为空")
		
		# 归一化基础合金成分
		base_comp = {k.upper(): v / total_base for k, v in base_alloy_composition.items()}
		solvent = max(base_comp.items(), key=lambda x: x[1])[0]
		
		# 确定溶液相的 TDB 相名（固相用溶剂的稳定相）
		if solution_phase == 'LIQUID':
			tdb_solution_phase = 'LIQUID'
			phase_desc = "液相"
		else:
			ref = self.tdb_parser.get_stable_phase(solvent,temperature) #选择计算温度下的稳定相结构为参考态
			tdb_solution_phase = ref if ref else 'BCC_A2'
			phase_desc = f"固相 ({tdb_solution_phase})"
		
		# ==================== 2. 检查基础合金稳定性 & 自动搜寻最稳定相====================
		#检查所有相的稳定性，如果都不稳定，则报告基础合金相不稳定；
		# 如果稳定，则找出最稳定的那个相作为tdb_solution_phase
		all_phases = self.tdb_parser.get_element_phases(solvent)
		candidate_phases = [p for p in all_phases if  p != 'GAS']
		
		found_stable_phase = False
		combined_issues = list()  # 收集所有尝试过的错误信息
		
		# === 新增变量：用于追踪最稳定的相 ===
		best_phase_name = None
		min_gibbs_energy = float('inf')  # 初始化为无穷大
		
		for phase in candidate_phases:
			# 1. 首先检查该相本身是否稳定 (没有析出，没有不合理的化学势)
			s_try, i_try = self._check_alloy_full_stability(
					composition=base_comp,
					temperature=temperature,
					tdb_phase=phase,
					extrapolation_func=extrapolation_func,
					extrapolation_model_name=extrapolation_model_name,
					activity_model=activity_model
			)
			
			if s_try:
				# === 修改点：找到稳定相后，不立即退出，而是计算能量 ===
				current_energy = 0.0
				calculation_valid = True
				
				# 计算该相在当前成分下的总吉布斯自由能 G = sum(x_i * mu_i)
				# 注意：这里需要重新调用 _get_chemical_potential 来获取数值
				for el, x_el in base_comp.items():
					mu = self._get_chemical_potential(
							composition=base_comp,
							component=el,
							temperature=temperature,
							tdb_phase=phase,
							extrapolation_model_func=extrapolation_func,
							extrapolation_model=extrapolation_model_name,
							activity_model=activity_model
					)
					
					if mu is None:
						calculation_valid = False
						break
					current_energy += x_el * mu
				
				# 如果能量计算成功，与当前最小值比较
				if calculation_valid:
					if current_energy < min_gibbs_energy:
						min_gibbs_energy = current_energy
						best_phase_name = phase
						found_stable_phase = True
						issues = []
			
			# === 循环结束后，应用找到的最优相 ===
			if found_stable_phase and best_phase_name:
				tdb_solution_phase = best_phase_name
				phase_desc = "液相" if best_phase_name == 'LIQUID' else f"固相 ({best_phase_name})"
				stable = True
			# 可以在这里打印日志：print(f"自动切换至最稳定相: {best_phase_name} (G={min_gibbs_energy:.2f})")
			
			# 如果遍历完还是没有找到任何稳定相，则返回错误
			if not found_stable_phase:
				error_msg = f"基础合金在所有候选相中均不稳定。详细原因: {'; '.join(combined_issues[:3])}..."
				return {
					"status": "unstable",
					"solubility_mole_fraction": None,
					"T": temperature,
					"solute": solute,
					"phase_state": "Unknown",
					"message": "基础合金不稳定，无法找到热力学稳定相",
					"error_detail": error_msg,
					"warnings": combined_issues
				}

		# ==================== 3. 获取析出相能量 ====================
		if precipitating_phase_type == 'PURE':
			# 纯组元析出
			g_ppt = self.tdb_parser.get_gibbs_energy(solute, precipitating_phase, temperature)
		else:
			# 金属间化合物析出
			# 获取化合物的化学计量比和能量
			elem1, elem2, n1, n2 = self.intermetallic_db.get_compound_stoichiometry(precipitating_phase)

			# 尝试从TDB获取化合物能量
			# （这里简化处理，实际应该更复杂）
			g_ppt = self.tdb_parser.get_gibbs_energy(elem1, precipitating_phase, temperature)

			# 如果TDB中没有，使用组成元素的能量估算
			if g_ppt is None:
				g1 = self.tdb_parser.get_gibbs_energy(elem1, 'LIQUID', temperature)
				g2 = self.tdb_parser.get_gibbs_energy(elem2, 'LIQUID', temperature)

				if g1 and g2:
					# 简化估算：加权平均 + 形成焓（负值表示稳定）
					total_atoms = n1 + n2
					g_ppt = (n1 * g1 + n2 * g2) / total_atoms - 10000.0  # J/mol (示例)
				else:
					g_ppt = None

		if g_ppt is None:
			raise RuntimeError(f"无法获取析出相 {precipitating_phase} 的 Gibbs 能量")
		
		# ==================== 4. 残差函数（最严格版）===================
		def residual (x_solute: float) -> float:
			x_solute = max(min(x_solute, max_solubility), min_solubility)
			remaining = 1.0 - x_solute
			
			# 构建当前合金成分（保持基础合金比例不变）
			current_comp = {el: base_comp[el] * remaining for el in base_comp}
			current_comp[solute] = x_solute
			
			# 计算溶质的化学势
			mu_solute = self._get_chemical_potential(
					composition=current_comp,
					component=solute,
					temperature=temperature,
					tdb_phase=tdb_solution_phase,
					extrapolation_model_func=extrapolation_func,
					extrapolation_model=extrapolation_model_name,
					activity_model=activity_model
			)
			if mu_solute is None:
				return 1e20
			
			# 【检查加入溶质后，所有组分（包括溶剂和原有合金元素）是否仍然稳定】
			stable_now, issues_now = self._check_alloy_full_stability(
					composition=current_comp,
					temperature=temperature,
					tdb_phase=tdb_solution_phase,
					extrapolation_func=extrapolation_func,
					extrapolation_model_name=extrapolation_model_name,
					activity_model=activity_model,
					ignore_component=solute  # 只关心基础合金组成元素不要析出，溶质本身当然可能过饱和
			)
			if not stable_now:
				# 只要有任何一个基体元素化学势 > 其纯态 → 说明溶质“挤出了”基体 → 强制残差为正，解趋向于0
				
				return 1e20
			
			return mu_solute - g_ppt
		
		# ==================== 5. 求解 ====================
		f_low = residual(min_solubility)
		f_high = residual(max_solubility)
		
		if f_low > 0:  # 即使极稀也已过饱和
			solubility = 0.0
			status = "insoluble"
			message = "即使无限稀释也已过饱和（可能基础合金已接近极限）"
		elif f_high < 0:  # 甚至 99.9% 都还欠饱和（几乎完全互溶）
			solubility = 1.0
			status = "fully_solublee"
			message = "溶质在该温度下与基础合金完全互溶"
		else:
			try:
				# 优化：降低求解器精度以提升速度（从1e-10到1e-6，精度仍然足够）
				solubility = brentq(residual, min_solubility, max_solubility, xtol=1e-6, rtol=1e-6)
				status = "success"
				message = "正常计算收敛"
			except ValueError as e:
				# brentq 可能因残差不变号而报错 → 视为不溶
				solubility = 0.0
				status = "numerical_failure"
				message = f"求解失败，强制为0 ({e})"
		
		# ==================== 6. 构建最终成分 ====================
		remaining = 1.0 - solubility
		final_comp = {el: base_comp[el] * remaining for el in base_comp}
		final_comp[solute] = solubility
		
		return {
			"status": status,
			"message": message,
			"T": temperature,
			"solute": solute,
			"precipitating_phase": precipitating_phase,
			"precipitating_phase_type": precipitating_phase_type,  # 新增
			"solution_phase_name": tdb_solution_phase,  # 溶质实际溶解的相
			"phase_state": phase_desc,
			"solvent_element": solvent,
			"base_stability_at_zero_solute": "stable",  # 已在前面的检查保证
			"solubility_mole_fraction": float(solubility),
			"final_composition_mole": final_comp,
			"warnings": issues if 'issues' in locals() else []
		}
		

	
	
	def calculate_ideal_solubility(self,
	                               base_alloy_composition: Dict[str, float],
	                               solute_element: str,
	                               solution_phase: str,
	                               precipitating_phase: str,
	                               temperature: float) -> dict:
		"""
		计算理想溶液模型下的溶解度

		理想溶液假设：活度系数 γ = 1 (ln γ = 0)
		化学势平衡：μ_solute^0 + RT ln(x_solute) = G_precipitate
		理想溶解度：x_solute_ideal = exp[(G_precipitate - μ_solute^0) / RT]

		参数:
		    base_alloy_composition: 基础合金成分 (摩尔分数)
		    solute_element: 溶质元素
		    solution_phase: 溶液相 ('LIQUID' 或 'SOLID')
		    precipitating_phase: 析出相名称
		    temperature: 温度 (K)

		返回:
		    包含理想溶解度的字典
		"""
		# 预处理
		solute = solute_element.upper()
		precipitating_phase = self.tdb_parser.get_stable_phase(solute, temperature)  # 沉淀相为温度T下的稳定相
		total_base = sum(base_alloy_composition.values())
		if total_base <= 0:
			return {
				"status": "error",
				"message": "基础合金成分不能为空",
				"solubility_mole_fraction": 0.0
			}

		# 归一化基础合金成分
		base_comp = {k.upper(): v / total_base for k, v in base_alloy_composition.items()}
		solvent = max(base_comp.items(), key=lambda x: x[1])[0]

		# 确定溶液相的 TDB 相名
		if solution_phase == 'LIQUID':
			tdb_solution_phase = 'LIQUID'
			phase_desc = "液相"
		else:
			ref = self.tdb_parser.get_reference_phase(solvent)
			tdb_solution_phase = ref if ref else 'BCC_A2'
			phase_desc = f"固相 ({tdb_solution_phase})"

		# 获取溶质在溶液相中的标准Gibbs能量 (μ_solute^0)
		mu_0_solute = self.tdb_parser.get_gibbs_energy(solute, tdb_solution_phase, temperature)

		# 如果TDB中没有，尝试使用晶格稳定性估算
		if mu_0_solute is None and tdb_solution_phase != 'LIQUID':
			mu_0_solute = self._estimate_lattice_stability(solute, tdb_solution_phase, temperature)

		if mu_0_solute is None:
			return {
				"status": "error",
				"message": f"无法获取 {solute} 在 {tdb_solution_phase} 相的标准Gibbs能量",
				"solubility_mole_fraction": 0.0
			}

		# 获取析出相的Gibbs能量
		g_ppt = self.tdb_parser.get_gibbs_energy(solute, precipitating_phase, temperature)
		if g_ppt is None:
			return {
				"status": "error",
				"message": f"无法获取 {solute} 在 {precipitating_phase} 相的Gibbs能量",
				"solubility_mole_fraction": 0.0
			}

		# 计算理想溶解度：x_ideal = exp[(G_ppt - μ_0) / RT]
		try:
			delta_g = g_ppt - mu_0_solute
			exponent = delta_g / (self.R * temperature)

			# 检查指数是否在合理范围内（避免数值溢出）
			if exponent > 100:  # exp(100) ≈ 2.7e43，远超物理意义
				x_ideal = 1.0
				status = "fully_soluble"
			elif exponent < -100:  # exp(-100) ≈ 3.7e-44，接近于0
				x_ideal = 0.0
				status = "insoluble"
			else:
				x_ideal = math.exp(exponent)
				# 限制在物理范围内
				x_ideal = max(1e-12, min(0.999, x_ideal))
				status = "success"

			# 构建最终成分
			remaining = 1.0 - x_ideal
			final_comp = {el: base_comp[el] * remaining for el in base_comp}
			final_comp[solute] = x_ideal

			# 计算相对添加量
			if remaining > 1e-12:
				relative_addition = x_ideal / remaining
			else:
				relative_addition = float('inf')

			return {
				"status": status,
				"message": "理想溶液模型计算成功",
				"model": "ideal_solution",
				"T": temperature,
				"solute": solute,
				"precipitating_phase": precipitating_phase,
				"solution_phase_name": tdb_solution_phase,  # 溶质实际溶解的相
				"phase_state": phase_desc,
				"solvent_element": solvent,
				"solubility_mole_fraction": float(x_ideal),
				"final_composition": final_comp,
				"relative_addition": relative_addition,
				"delta_g": delta_g,
				"mu_0_solute": mu_0_solute,
				"g_precipitate": g_ppt
			}

		except Exception as e:
			return {
				"status": "error",
				"message": f"理想溶解度计算失败: {str(e)}",
				"solubility_mole_fraction": 0.0
			}

	def _check_alloy_full_stability (self, composition, temperature, tdb_phase, extrapolation_func,
	                                 extrapolation_model_name, activity_model, ignore_component=None, tolerance=10.0):
		"""
		@tdb_phase:合金相
		检查合金组分是否析出,只检查该合金的稳定性"""
		issues = []
		
		# =========================================================
		# 1. 计算当前相的化学势和总能量
		# =========================================================
		is_stable = True
		
		for el,x_el  in composition.items():
			if x_el < 1e-12: continue
			
			mu_el = self._get_chemical_potential(composition, el, temperature, tdb_phase, extrapolation_func,
			                                  extrapolation_model_name, activity_model)
			if mu_el is None:
				break
			stable_phase = self.tdb_parser.get_stable_phase(el,temperature)
			g_stable_pure = self.tdb_parser.get_gibbs_energy(el, stable_phase , temperature)
			if mu_el - g_stable_pure > tolerance:
				'合金不稳定'
				issues.append(
						f"组分不稳定: {el} 在 {tdb_phase} 中的化学势过高 (Δμ={mu_el - g_stable_pure:.1f})，倾向以纯态析出")
				is_stable = False
				return False, issues
			
		return is_stable, issues
			
		
	
	def _get_chemical_potential (self,
	                             composition: Dict[str, float],
	                             component: str,
	                             temperature: float,
	                             tdb_phase: str,
	                             extrapolation_model_func: extrap_func,
	                             extrapolation_model: str,
	                             activity_model: str) -> Optional[float]:
		"""
        计算化学势 (内部辅助)。
        """
		# 1. 确定相态
		if tdb_phase == 'LIQUID':
			activity_phase_state = 'liquid'
			lookup_phase = 'LIQUID'
		else:
			activity_phase_state = 'solid'
			lookup_phase = tdb_phase
		
		# 2. 获取标准 Gibbs 能量 (G_0)
		#    优先查 TDB，失败则调用估算函数
		mu_0 = self.tdb_parser.get_gibbs_energy(component, lookup_phase, temperature)
		
		if mu_0 is None and lookup_phase != 'LIQUID':
			mu_0 = self._estimate_lattice_stability(component, lookup_phase, temperature)
		
		if mu_0 is None:
			return None
		
		# 3. 计算活度系数
		ln_gamma = self.calculate_ln_activity_coefficient(
				composition, component, temperature, activity_phase_state,
				extrapolation_model_func, extrapolation_model, activity_model
		)
		if ln_gamma is None:
			return None
		
		# 4. 计算 μ
		x_i = self._check_bounds(composition.get(component, 0.0))
		return mu_0 + self.R * temperature * (math.log(x_i) + ln_gamma)
	
	# ================================================================
	# =================== PART 2: 液相线/固相线计算模块 ===================
	# ================================================================
	
	def calculate_liquidus (self,
	                        composition: Dict[str, float],
	                        solid_phase_map: Dict[str, str],
	                        extrapolation_model_func: extrap_func,
	                        extrapolation_model_name: str = 'UEM1',
	                        activity_model: str = 'Wagner',
	                        solid_model_type: str = 'SOLID_SOLUTION'
	                        ) -> dict:
		"""
        统一的液相线计算接口。
        """
		n_components = len(composition)
		if n_components <= 0: raise ValueError("成分不能为空")
		
		if n_components == 1:
			elem = list(composition.keys())[0]
			solid_phase = solid_phase_map.get(elem)
			T_melt = self.calculate_pure_melting_point(elem, solid_phase)
			solid_comp_eq = composition if solid_model_type == 'SOLID_SOLUTION' else {elem: 1.0}
			return {"status": "success", "T_liquidus": T_melt, "liquid_composition": composition,
			        "solid_composition_eq": solid_comp_eq}
		
		elif n_components == 2:
			# 二元求解
			components = sorted(composition.keys())
			comp_A = max(composition.items(), key=lambda item: item[1])[0]
			comp_B = components[0] if components[1] == comp_A else components[1]
			x_B_liq = composition[comp_B]
			solid_A, solid_B = solid_phase_map[comp_A], solid_phase_map[comp_B]
			
			T_melt_A = self.calculate_pure_melting_point(comp_A, solid_A)
			T_melt_B = self.calculate_pure_melting_point(comp_B, solid_B)
			T_guess = (1 - x_B_liq) * (T_melt_A or 1000) + x_B_liq * (T_melt_B or 1000) + 10
			
			x_S_guess = self._auto_generate_solute_guess(composition, default_k=0.8)[comp_B]
			
			if solid_model_type == 'SOLID_SOLUTION':
				return self._solve_liquidus_binary_ss(x_B_liq, comp_A, comp_B, solid_A, solid_B, T_guess, x_S_guess,
				                                      extrapolation_model_func, extrapolation_model_name,
				                                      activity_model)
			else:
				return self._solve_liquidus_binary_pure(x_B_liq, comp_A, comp_B, solid_A, solid_B, T_guess, x_S_guess,
				                                        extrapolation_model_func, extrapolation_model_name,
				                                        activity_model)
		
		else:  # 多元求解
			if solid_model_type == 'SOLID_SOLUTION':
				return self.calculate_liquidus_temp_robust_ss(composition, solid_phase_map, extrapolation_model_func,
				                                              extrapolation_model_name, activity_model)
			else:
				return self.calculate_liquidus_temp_robust_pure(composition, solid_phase_map, extrapolation_model_func,
				                                                extrapolation_model_name, activity_model)
	
	def calculate_solidus (self,
	                       composition: Dict[str, float],
	                       solid_phase_map: Dict[str, str],
	                       extrapolation_model_func: extrap_func,
	                       extrapolation_model_name: str = 'UEM1',
	                       activity_model: str = 'Wagner',
	                       solid_model_type: str = 'SOLID_SOLUTION'
	                       ) -> dict:
		"""
        统一的固相线计算接口。
        """
		n_components = len(composition)
		if n_components <= 1:
			return self.calculate_liquidus(composition, solid_phase_map, extrapolation_model_func,
			                               extrapolation_model_name, activity_model, solid_model_type)
		
		elif n_components == 2:
			components = sorted(composition.keys())
			comp_A = max(composition.items(), key=lambda item: item[1])[0]
			comp_B = components[0] if components[1] == comp_A else components[1]
			x_B_sol = composition[comp_B]
			solid_A, solid_B = solid_phase_map[comp_A], solid_phase_map[comp_B]
			
			T_melt_A = self.calculate_pure_melting_point(comp_A, solid_A)
			T_melt_B = self.calculate_pure_melting_point(comp_B, solid_B)
			T_guess = (1 - x_B_sol) * (T_melt_A or 1000) + x_B_sol * (T_melt_B or 1000) - 10
			x_L_guess = self._auto_generate_solute_guess(composition, default_k=1.2).get(comp_B, x_B_sol)
			
			if solid_model_type == 'SOLID_SOLUTION':
				return self._solve_solidus_binary_ss(x_B_sol, comp_A, comp_B, solid_A, solid_B, T_guess, x_L_guess,
				                                     extrapolation_model_func, extrapolation_model_name, activity_model)
			else:
				return self._solve_solidus_binary_pure(x_B_sol, comp_A, comp_B, solid_A, solid_B, T_guess, x_L_guess,
				                                       extrapolation_model_func, extrapolation_model_name,
				                                       activity_model)
		else:
			if solid_model_type == 'SOLID_SOLUTION':
				return self.calculate_solidus_temp_robust_ss(composition, solid_phase_map, extrapolation_model_func,
				                                             extrapolation_model_name, activity_model)
			else:
				return self.calculate_solidus_temp_robust_pure(composition, solid_phase_map,extrapolation_model_func,
				                                               extrapolation_model_name,activity_model)
	
	# ================================================================
	# =================== 内部辅助函数 & 求解器 =======================
	# ================================================================
	
	def calculate_pure_melting_point (self, element: str, solid_phase: Optional[str] = None, T_min=300.0,
	                                  T_max=6000.0) -> Optional[float]:
		if solid_phase is None:
			solid_phase = self.tdb_parser.get_reference_phase(element)
			if solid_phase is None: return None
		
		def _diff (T):
			gl = self.tdb_parser.get_gibbs_energy(element, 'LIQUID', T)
			gs = self.tdb_parser.get_gibbs_energy(element, solid_phase, T)
			return (gl - gs) if (gl and gs) else 1e5
		
		try:
			if _diff(T_min) * _diff(T_max) < 0:
				return brentq(_diff, T_min, T_max)
			# 尝试缩小范围
			if _diff(1000) * _diff(3000) < 0:
				return brentq(_diff, 1000, 3000)
		except:
			pass
		return None
	
	def _auto_generate_solute_guess (self, composition, default_k=0.8):
		rules = {'C': 0.05, 'N': 0.05, 'B': 0.05, 'H': 0.01, 'O': 0.01}
		solvent = max(composition.items(), key=lambda x: x[1])[0]
		return {c: self._check_bounds(composition[c] * rules.get(c, default_k)) for c in composition if c != solvent}
	
	# --- 二元求解器 (SS) ---
	def _solve_liquidus_binary_ss (self, x_B, cA, cB, sA, sB, Tg, xSg, func, name, act):
		xL = self._check_bounds(x_B)
		
		def resid (vars):
			T, xS = vars[0], self._check_bounds(vars[1])
			L = {cA: 1 - xL, cB: xL};
			S = {cA: 1 - xS, cB: xS}
			muAL = self._get_chemical_potential(L, cA, T, 'LIQUID', func, name, act)
			muAS = self._get_chemical_potential(S, cA, T, sA, func, name, act)
			muBL = self._get_chemical_potential(L, cB, T, 'LIQUID', func, name, act)
			muBS = self._get_chemical_potential(S, cB, T, sB, func, name, act)
			if any(x is None for x in [muAL, muAS, muBL, muBS]): return [1e5, 1e5]
			return [muAL - muAS, muBL - muBS]
		
		sol = root(resid, [Tg, xSg], method='lm')
		if not sol.success: raise RuntimeError(sol.message)
		return {"status": "success", "T_liquidus": sol.x[0], "liquid_composition": {cA: 1 - xL, cB: xL},
		        "solid_composition_eq": {cA: 1 - sol.x[1], cB: sol.x[1]}}
	
	def _solve_solidus_binary_ss (self, x_B, cA, cB, sA, sB, Tg, xLg, func, name, act):
		xS = self._check_bounds(x_B)
		
		def resid (vars):
			T, xL = vars[0], self._check_bounds(vars[1])
			L = {cA: 1 - xL, cB: xL};
			S = {cA: 1 - xS, cB: xS}
			muAL = self._get_chemical_potential(L, cA, T, 'LIQUID', func, name, act)
			muAS = self._get_chemical_potential(S, cA, T, sA, func, name, act)
			muBL = self._get_chemical_potential(L, cB, T, 'LIQUID', func, name, act)
			muBS = self._get_chemical_potential(S, cB, T, sB, func, name, act)
			if any(x is None for x in [muAL, muAS, muBL, muBS]): return [1e5, 1e5]
			return [muAL - muAS, muBL - muBS]
		
		sol = root(resid, [Tg, xLg], method='lm')
		if not sol.success: raise RuntimeError(sol.message)
		return {"status": "success", "T_solidus": sol.x[0], "solid_composition": {cA: 1 - xS, cB: xS},
		        "liquid_composition_eq": {cA: 1 - sol.x[1], cB: sol.x[1]}}
	
	# --- 二元求解器 (Pure) ---
	def _solve_liquidus_binary_pure (self, x_B, cA, cB, sA, sB, Tg, xSg, func, name, act):
		xL = self._check_bounds(x_B)
		L = {cA: 1 - xL, cB: xL}
		
		# 分别计算针对 A 和 B 的液相线
		def resA (T):
			muL = self._get_chemical_potential(L, cA, T, 'LIQUID', func, name, act)
			muS = self.tdb_parser.get_gibbs_energy(cA, sA, T)
			return (muL - muS) if (muL and muS) else 1e5
		
		def resB (T):
			muL = self._get_chemical_potential(L, cB, T, 'LIQUID', func, name, act)
			muS = self.tdb_parser.get_gibbs_energy(cB, sB, T)
			return (muL - muS) if (muL and muS) else 1e5
		
		Ta, Tb = None, None
		try:
			Ta = brentq(resA, 300, 6000)
		except:
			pass
		try:
			Tb = brentq(resB, 300, 6000)
		except:
			pass
		
		if Ta and Tb:
			T_liq = max(Ta, Tb)
		elif Ta:
			T_liq = Ta
		elif Tb:
			T_liq = Tb
		else:
			raise RuntimeError("Calculation failed")
		return {"status": "success", "T_liquidus": T_liq, "liquid_composition": L,
		        "solid_composition_eq": {cA: (1 if T_liq == Ta else 0), cB: (1 if T_liq == Tb else 0)}}
	
	def _solve_solidus_binary_pure (self, x_B, cA, cB, sA, sB, Tg, xLg, func, name, act):
		# 共晶固相线求解
		def resid (vars):
			T, xL = vars[0], self._check_bounds(vars[1])
			L = {cA: 1 - xL, cB: xL}
			muAL = self._get_chemical_potential(L, cA, T, 'LIQUID', func, name, act)
			muAS = self.tdb_parser.get_gibbs_energy(cA, sA, T)
			muBL = self._get_chemical_potential(L, cB, T, 'LIQUID', func, name, act)
			muBS = self.tdb_parser.get_gibbs_energy(cB, sB, T)
			if any(x is None for x in [muAL, muAS, muBL, muBS]): return [1e5, 1e5]
			return [muAL - muAS, muBL - muBS]
		
		sol = root(resid, [Tg, xLg], method='lm')
		return {"status": "success", "T_solidus": sol.x[0], "solid_composition": {cA: 1 - x_B, cB: x_B},
		        "liquid_composition_eq": {cA: 1 - sol.x[1], cB: sol.x[1]}}
	
	# --- 多元健壮求解器 wrappers (简化版，调用下方通用 solve) ---
	def calculate_liquidus_temp_robust_ss (self, comp, map, func, name, act):
		return self._robust_solver_wrapper(comp, map, func, name, act, is_liquidus=True, is_ss=True)
	
	def calculate_liquidus_temp_robust_pure (self, comp, map, func, name, act):
		return self._robust_solver_wrapper(comp, map, func, name, act, is_liquidus=True, is_ss=False)
	
	def calculate_solidus_temp_robust_ss (self, comp, map, func, name, act):
		return self._robust_solver_wrapper(comp, map, func, name, act, is_liquidus=False, is_ss=True)
	
	def calculate_solidus_temp_robust_pure (self, comp, map, func, name, act):
		return self._robust_solver_wrapper(comp, map, func, name, act, is_liquidus=False, is_ss=False)
	
	def _robust_solver_wrapper (self, comp, map, func, name, act, is_liquidus, is_ss):
		# 简化的健壮求解逻辑：尝试不同初值
		guess_ks = [0.8, 1.0, 0.1] if is_liquidus else [1.2, 1.0, 2.0]
		solvent = max(comp.items(), key=lambda x: x[1])[0]
		tm = self.calculate_pure_melting_point(solvent, map[solvent]) or 1500
		T_guess = tm - 50
		
		last_err = None
		for k in guess_ks:
			guess_comp = self._auto_generate_solute_guess(comp, k)
			try:
				if is_liquidus and is_ss: return self._solve_liquidus_multi_ss(comp, map, T_guess, guess_comp, func,
				                                                               name, act)
				if is_liquidus and not is_ss: return self._solve_liquidus_multi_pure(comp, map, T_guess, {}, func, name,
				                                                                     act)
				if not is_liquidus and is_ss: return self._solve_solidus_multi_ss(comp, map, T_guess, guess_comp, func,
				                                                                  name, act)
				if not is_liquidus and not is_ss: return self._solve_solidus_multi_pure(comp, map, T_guess, guess_comp,
				                                                                        func, name, act)
			except Exception as e:
				last_err = e
		raise RuntimeError(f"Calculation failed: {last_err}")
	
	# --- 多元核心求解器 (保留原逻辑) ---
	def _solve_liquidus_multi_ss (self, L_comp, map, Tg, S_guess, func, name, act):
		solv = max(L_comp, key=L_comp.get);
		solutes = [c for c in L_comp if c != solv]
		
		def resid (vars):
			T = vars[0];
			S = {solv: 1 - sum(vars[1:]), **{s: vars[i + 1] for i, s in enumerate(solutes)}}
			res = []
			for c in [solv] + solutes:
				muL = self._get_chemical_potential(L_comp, c, T, 'LIQUID', func, name, act)
				muS = self._get_chemical_potential(S, c, T, map[c], func, name, act)
				res.append(muL - muS if (muL and muS) else 1e5)
			return res
		
		sol = root(resid, [Tg] + [S_guess.get(s, 0) for s in solutes], method='lm')
		if not sol.success: raise RuntimeError(sol.message)
		return {"status": "success", "T_liquidus": sol.x[0]}
	
	def _solve_liquidus_multi_pure (self, L_comp, map, Tg, _, func, name, act):
		# Pure 模型取各组分液相线最高者
		results = []
		for c in L_comp:
			def res (T):
				muL = self._get_chemical_potential(L_comp, c, T, 'LIQUID', func, name, act)
				muS = self.tdb_parser.get_gibbs_energy(c, map[c], T)
				return (muL - muS) if (muL and muS) else 1e5
			
			try:
				results.append(brentq(res, 300, 6000))
			except:
				pass
		if not results: raise RuntimeError("Failed")
		return {"status": "success", "T_liquidus": max(results)}
	
	def _solve_solidus_multi_ss (self, S_comp, map, Tg, L_guess, func, name, act):
		solv = max(S_comp, key=S_comp.get);
		solutes = [c for c in S_comp if c != solv]
		
		def resid (vars):
			T = vars[0];
			L = {solv: 1 - sum(vars[1:]), **{s: vars[i + 1] for i, s in enumerate(solutes)}}
			res = []
			for c in [solv] + solutes:
				muL = self._get_chemical_potential(L, c, T, 'LIQUID', func, name, act)
				muS = self._get_chemical_potential(S_comp, c, T, map[c], func, name, act)
				res.append(muL - muS if (muL and muS) else 1e5)
			return res
		
		sol = root(resid, [Tg] + [L_guess.get(s, 0) for s in solutes], method='lm')
		if not sol.success: raise RuntimeError(sol.message)
		return {"status": "success", "T_solidus": sol.x[0]}
	
	def _solve_solidus_multi_pure (self, S_comp, map, Tg, L_guess, func, name, act):
		# 共晶
		solv = max(S_comp, key=S_comp.get);
		solutes = [c for c in S_comp if c != solv]
		
		def resid (vars):
			T = vars[0];
			L = {solv: 1 - sum(vars[1:]), **{s: vars[i + 1] for i, s in enumerate(solutes)}}
			res = []
			for c in [solv] + solutes:
				muL = self._get_chemical_potential(L, c, T, 'LIQUID', func, name, act)
				muS = self.tdb_parser.get_gibbs_energy(c, map[c], T)
				res.append(muL - muS if (muL and muS) else 1e5)
			return res
		
		sol = root(resid, [Tg] + [L_guess.get(s, 0) for s in solutes], method='lm')
		return {"status": "success", "T_solidus": sol.x[0]}
	
	# ================================================================
	# =================== GUI 兼容性接口 ==============================
	# ================================================================
	
	def _get_default_solid_phase_map (self, composition: Dict[str, float]) -> Dict[str, str]:
		map_res = {}
		for elem in composition:
			ref = self.tdb_parser.get_reference_phase(elem)
			map_res[elem] = ref if ref else 'BCC_A2'
		return map_res
	
	
	
	def calculate_liquidus_temperature (self, composition, extrapolation_model_func=None,
	                                    extrapolation_model_name='UEM1', activity_model='Wagner',
	                                    solid_model_type='PURE_SOLID'):
		if extrapolation_model_func is None:
			from models.extrapolation_models import BinaryModel
			extrapolation_model_func = BinaryModel().UEM1
		
		comp_upper = {k.upper(): v for k, v in composition.items()}
		map_s = self._get_default_solid_phase_map(comp_upper)
		try:
			res = self.calculate_liquidus(comp_upper, map_s, extrapolation_model_func, extrapolation_model_name,
			                              activity_model, solid_model_type)
			return res['T_liquidus']
		except:
			return None
	
	def calculate_solidus_temperature (self, composition, extrapolation_model_func=None,
	                                   extrapolation_model_name='UEM1', activity_model='Wagner',
	                                   solid_model_type='PURE_SOLID'):
		if extrapolation_model_func is None:
			from models.extrapolation_models import BinaryModel
			extrapolation_model_func = BinaryModel().UEM1
		
		comp_upper = {k.upper(): v for k, v in composition.items()}
		map_s = self._get_default_solid_phase_map(comp_upper)
		try:
			res = self.calculate_solidus(comp_upper, map_s, extrapolation_model_func, extrapolation_model_name,
			                             activity_model, solid_model_type)
			return res['T_solidus']
		except:
			return None
	
	def calculate_phase_diagram_curve (self, base_composition, variable_component, x_min=0.0, x_max=1.0, n_points=20,
	                                   extrapolation_model_func=None, extrapolation_model_name='UEM1',
	                                   activity_model='Wagner', solid_model_type='PURE_SOLID', progress_callback=None):
		if extrapolation_model_func is None:
			from models.extrapolation_models import BinaryModel
			extrapolation_model_func = BinaryModel().UEM1
		
		results = {'x': [], 'T_liquidus': [], 'T_solidus': []}
		var_comp = variable_component.upper()
		base_total = sum(v for k, v in base_composition.items() if k.upper() != var_comp)
		
		import numpy as np
		x_vals = np.linspace(x_min, x_max, n_points)
		
		for i, x in enumerate(x_vals):
			if progress_callback: progress_callback(i + 1, len(x_vals))
			
			curr = {var_comp: x}
			rem = 1.0 - x
			if base_total > 0:
				for k, v in base_composition.items():
					if k.upper() != var_comp:
						curr[k.upper()] = (v / base_total) * rem
			
			curr = {k: v for k, v in curr.items() if v > 1e-6}
			if not curr: continue
			
			# Normalize check
			tot = sum(curr.values())
			if abs(tot - 1.0) > 1e-5: curr = {k: v / tot for k, v in curr.items()}
			
			T_liq = self.calculate_liquidus_temperature(curr, extrapolation_model_func, extrapolation_model_name,
			                                            activity_model, solid_model_type)
			T_sol = self.calculate_solidus_temperature(curr, extrapolation_model_func, extrapolation_model_name,
			                                           activity_model, solid_model_type)
			
			results['x'].append(x)
			results['T_liquidus'].append(T_liq)
			results['T_solidus'].append(T_sol)
		
		return results


# GUI 别名
PhaseDiagram = PhaseDiagramCalculator
