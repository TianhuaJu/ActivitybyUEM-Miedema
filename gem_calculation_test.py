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
	
	# 3. 构建候选相列表 (The Candidate List)
	candidate_phases = []
	
	# --- A. 添加标准 TDB 相 (已知相) ---
	# 我们不仅添加 LIQUID，还添加固相 BCC/FCC/石墨，让它们公平竞争
	tdb_phases_to_add = ['LIQUID', 'BCC_A2', 'FCC_A1', 'GRAPHITE']
	# 注意：GRAPHITE 在某些 TDB 中可能叫 'GRAPHITE' 或 'C_GRAPHITE'，需根据数据库确认
	# 这里简单起见，我们假设 PhaseDiagramCalculator 能处理基本相
	system_elements = sorted(list(system_comp.keys()))
	# 获取体系元素
	elements = list(system_comp.keys())
	
	for p_name in tdb_phases_to_add:
		# 创建 SolutionPhase 对象
		# 注意：这里我们告诉 SolutionPhase 使用这三个元素。
		# PhaseDiagramCalculator 内部会处理某个相不包含某个元素的情况（通常返回高能量或自动处理）
		valid_components = []
		for elem in system_elements:
			possible_phases = calc.tdb_parser.get_element_phases(elem)
			if p_name in possible_phases or p_name == 'LIQUID':
				valid_components.append(elem)
			
			# 如果这个相在当前体系里连一个支持的元素都没有，就跳过
			if not valid_components:
				print(f"跳过相 {p_name}: 当前体系元素均不支持该相")
				continue
				
			phase_obj = SolutionPhase(
					name=p_name,
					components=elements,
					calculator_instance=calc,
					extrapolation_model_func=extrap_func
			)
			candidate_phases.append(phase_obj)
			print(f"加入候选相: {p_name}")
	
	# --- B. 添加 Miedema 预测相 (未知相/化合物) ---
	# 针对 Fe-Si 体系，预测可能存在的化合物
	# 假设我们怀疑存在 FeSi (1:1) 和 FeSi2 (1:2)
	
	# 1. 预测 FeSi
	fesi_virtual = MiedemaPhaseFactory.create_virtual_compound(
			'Fe', 'Si', 0.5, 0.5, phase_name="Predicted_FeSi"
	)
	candidate_phases.append(fesi_virtual)
	print(f"加入预测相: Predicted_FeSi (Miedema)")
	
	# 2. 预测 SiC (如果你怀疑 TDB 里没有 SiC)
	sic_virtual = MiedemaPhaseFactory.create_virtual_compound(
			'Si', 'C', 0.5, 0.5, phase_name="Predicted_SiC"
	)
	candidate_phases.append(sic_virtual)
	print(f"加入预测相: Predicted_SiC (Miedema)")
	
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


if __name__ == "__main__":
	run_gem_demo()