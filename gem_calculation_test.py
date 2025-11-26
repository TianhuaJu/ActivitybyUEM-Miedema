import sys
import os

# 确保路径包含当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from calculations.phase_diagram import PhaseDiagramCalculator
from models.extrapolation_models import BinaryModel
from core.gem_structures import SolutionPhase, MiedemaPhaseFactory
from core.gem_solver import GEMSolver


def run_gem_demo ():
	print("=== 初始化 GEM 系统 ===")
	
	# 1. 准备基础计算器 (用于提供 TDB 数据和外推模型)
	calc = PhaseDiagramCalculator()
	extrap_func = BinaryModel().UEM1
	
	# 2. 定义系统条件
	system_comp = {'Fe': 0.70, 'Si': 0.27, 'C': 0.03}
	temperature = 1873.0  # 1600 C
	
	print(f"计算条件: T={temperature}K")
	print(f"成分: {system_comp}")
	
	# ==========================================
	# 3. 构建候选相列表 (The Candidate List)
	# ==========================================
	candidate_phases = []
	
	# --- A. 添加标准 TDB 相 (已知相) ---
	tdb_phases_to_add = ['LIQUID', 'BCC_A2', 'FCC_A1', 'GRAPHITE']
	
	# 获取体系中的所有元素列表
	system_elements = sorted(list(system_comp.keys()))
	
	print("\n--- 正在扫描 TDB 相 ---")
	for p_name in tdb_phases_to_add:
		# 【关键】valid_components 列表用于存储该相支持的元素
		valid_components = []
		
		# 遍历系统中的每个元素，检查它是否能进入当前相
		for elem in system_elements:
			# 1. 检查 TDB 是否定义了该元素在该相中的参数
			# get_element_phases 返回该元素所有可用的相
			possible_phases = calc.tdb_parser.get_element_phases(elem)
			
			# 2. 判断逻辑：
			# - 如果是液相 (LIQUID)，通常假设所有元素都能进入
			# - 否则，该相必须出现在元素的可用相列表中 (例如 Fe 支持 BCC, 但不支持 GRAPHITE)
			if p_name == 'LIQUID' or p_name in possible_phases:
				valid_components.append(elem)
		
		# 循环结束后，判断该相是否有效
		if not valid_components:
			print(f"  [跳过] 相 {p_name}: 当前体系中没有任何元素支持该相")
			continue
		
		# 【修正点 1】：SolutionPhase 不再需要 extrapolation_model_func
		phase_obj = SolutionPhase(
				name=p_name,
				components=valid_components,
				calculator_instance=calc
				# 删除 extrapolation_model_func=extrap_func
		)
		candidate_phases.append(phase_obj)
		print(f"  [加入] 候选相: {p_name:<10} 支持元素: {valid_components}")
	
	# --- B. 添加 Miedema 预测相 (未知相/化合物) ---
	print("\n--- 添加 Miedema 预测相 ---")
	
	# 1. 预测 FeSi
	# 【修正点 2】：需要传入 calculator_instance 以便计算绝对能量
	fesi_virtual = MiedemaPhaseFactory.create_virtual_compound(
			'Fe', 'Si', 0.5, 0.5,
			calculator_instance=calc,  # <--- 新增参数
			phase_name="Predicted_FeSi"
	)
	candidate_phases.append(fesi_virtual)
	print(f"  [加入] 预测相: Predicted_FeSi")
	
	# 2. 预测 SiC
	sic_virtual = MiedemaPhaseFactory.create_virtual_compound(
			'Si', 'C', 0.5, 0.5,
			calculator_instance=calc,  # <--- 新增参数
			phase_name="Predicted_SiC"
	)
	candidate_phases.append(sic_virtual)
	print(f"  [加入] 预测相: Predicted_SiC")
	# 4. 运行 GEM 求解器
	print("\n=== 开始全局最小化计算 ===")
	solver = GEMSolver()
	result = solver.solve(system_comp, temperature, candidate_phases)
	
	# 5. 输出结果
	print(f"\n计算状态: {result.status}")
	print(f"总吉布斯自由能: {result.total_gibbs_energy:.2f} J/mol")
	print("\n稳定相列表:")
	
	for p in result.stable_phases:
		print(f"-> {p['name']} ({p['type']})")
		print(f"   摩尔分数: {p['fraction']:.4f}")
		# 格式化成分输出
		comp_str = ", ".join([f"{k}:{v:.4f}" for k, v in p['composition'].items() if v > 1e-4])
		print(f"   成分: {comp_str}")



# 将此代码片段加在 gem_calculation_test.py 的末尾，或者单独运行
def check_pure_iron_stability ():
	print("\n=== 基准测试：纯铁在 1873 K 的状态 ===")
	calc = PhaseDiagramCalculator()
	T = 1873.0
	
	# 1. 获取 TDB 中的基准能量 (G0)
	g_liq = calc.tdb_parser.get_gibbs_energy('Fe', 'LIQUID', T)
	g_fcc = calc.tdb_parser.get_gibbs_energy('Fe', 'FCC_A1', T)
	g_bcc = calc.tdb_parser.get_gibbs_energy('Fe', 'BCC_A2', T)
	
	print(f"G(LIQUID) = {g_liq:.2f} J/mol")
	print(f"G(FCC)    = {g_fcc:.2f} J/mol")
	print(f"G(BCC)    = {g_bcc:.2f} J/mol")
	
	min_g = min(g_liq, g_fcc, g_bcc)
	if min_g == g_liq:
		print("-> 结论：纯铁判定为【液态】 (正确)")
	else:
		print(f"-> 结论：纯铁判定为【固态】，偏差值 = {g_liq - min_g:.2f} J/mol (错误)")


if __name__ == "__main__":
	run_gem_demo() # 先注释掉上面的
	#check_pure_iron_stability()