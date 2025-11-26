import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from calculations.phase_diagram import PhaseDiagramCalculator
from models.extrapolation_models import BinaryModel


def compare_potentials ():
	print("\n=== 深度诊断：化学势对比 (T=1873 K) ===")
	calc = PhaseDiagramCalculator()
	extrap_func = BinaryModel().UEM1
	
	# 目标成分
	comp = {'Fe': 0.70, 'Si': 0.27, 'C': 0.03}
	T = 1873.0
	
	print(f"当前成分: {comp}")
	
	# 1. 计算 LIQUID 中的化学势
	print(f"\n--- LIQUID 相中的化学势 ---")
	mus_liq = {}
	total_g_liq = 0.0
	for el, x in comp.items():
		mu = calc._get_chemical_potential(comp, el, T, 'LIQUID',
		                                  extrap_func, 'UEM1', 'Wagner')
		mus_liq[el] = mu
		total_g_liq += x * mu
		print(f"  mu({el})_LIQ = {mu:.2f} J/mol")
	print(f"  G_total(LIQUID) = {total_g_liq:.2f} J/mol")
	
	# 2. 计算 FCC 中的化学势 (假设强制形成 FCC)
	print(f"\n--- FCC_A1 相中的化学势 (假设同成分) ---")
	mus_fcc = {}
	total_g_fcc = 0.0
	for el, x in comp.items():
		mu = calc._get_chemical_potential(comp, el, T, 'FCC_A1',
		                                  extrap_func, 'UEM1', 'Wagner')
		if mu is None:
			print(f"  mu({el})_FCC = 无法计算 (TDB缺失参数)")
			# 为了对比，给个大数
			mu = 0.0
		else:
			print(f"  mu({el})_FCC = {mu:.2f} J/mol")
		
		mus_fcc[el] = mu
		total_g_fcc += x * mu
	print(f"  G_total(FCC)    = {total_g_fcc:.2f} J/mol")
	
	# 3. 对比分析
	print("\n--- 差异分析 (负值表示固相更稳定，即异常来源) ---")
	diff_g = total_g_fcc - total_g_liq
	print(f"ΔG (FCC - LIQ) = {diff_g:.2f} J/mol")
	
	if diff_g < 0:
		print("警告: 固相 FCC 能量更低！这就是为什么 GEM 算出固相的原因。")
		print("分项差异 (mu_FCC - mu_LIQ):")
		for el in comp:
			d = mus_fcc[el] - mus_liq[el]
			print(f"  {el}: {d:.2f}")
			if d < -1000:
				print(f"    -> 罪魁祸首可能是 {el}！它在固相中极其稳定。")


if __name__ == "__main__":
	compare_potentials()