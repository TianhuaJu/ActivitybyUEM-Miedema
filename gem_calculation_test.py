import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from calculations.phase_equilibrium_calculator import PhaseEquilibriumCalculator

# 设置中文字体（根据您的系统环境调整，如果乱码可注释掉）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False


def plot_phase_fractions (composition, t_start, t_end, step):
	print(f"=== 开始计算相图数据 ===")
	print(f"成分: {composition}")
	print(f"温度范围: {t_start} K - {t_end} K, 步长: {step} K")
	
	calculator = PhaseEquilibriumCalculator()
	
	# 1. 准备温度点
	temperatures = np.arange(t_start, t_end + 1, step)
	
	# 用于存储所有出现过的相名称
	all_phase_names = set()
	
	# 存储每个温度点的结果
	results_list = []
	
	# 2. 循环计算
	for T in temperatures:
		print(f"正在计算 T = {T:.0f} K ...", end="\r")
		
		try:
			res = calculator.calculate_phase_equilibrium(composition, float(T))
			
			# 提取当前温度下的相分数
			phase_fractions = {}
			for p in res.stable_phases:
				p_name = p['name']
				fraction = p['fraction']
				if fraction > 1e-4:  # 忽略极小量
					phase_fractions[p_name] = fraction
					all_phase_names.add(p_name)
			
			results_list.append(phase_fractions)
		
		except Exception as e:
			print(f"\n[Error] T={T} 计算失败: {e}")
			results_list.append({})
	
	print("\n计算完成，正在绘图...")
	
	# 3. 整理数据用于绘图
	sorted_phases = sorted(list(all_phase_names))
	
	# 构建绘图矩阵: 行=温度，列=各相分数
	# 确保 LIQUID 放在最下面或最上面，视觉效果更好
	if 'LIQUID' in sorted_phases:
		sorted_phases.remove('LIQUID')
		sorted_phases.insert(0, 'LIQUID')
	
	y_data = []
	for phase in sorted_phases:
		fractions_at_t = []
		for res_dict in results_list:
			fractions_at_t.append(res_dict.get(phase, 0.0))
		y_data.append(fractions_at_t)
	
	# 4. 绘制堆积图 (Stackplot)
	plt.figure(figsize=(10, 6))
	
	# 定义颜色映射 (可选)
	colors = plt.cm.tab10.colors
	
	plt.stackplot(temperatures, y_data, labels=sorted_phases, alpha=0.8, colors=colors[:len(y_data)])
	
	plt.title(f"平衡相分数图 (Fe-0.7, Si-0.27, C-0.03)", fontsize=14)
	plt.xlabel("温度 (K)", fontsize=12)
	plt.ylabel("摩尔分数", fontsize=12)
	plt.xlim(t_start, t_end)
	plt.ylim(0, 1.0)
	plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
	plt.grid(alpha=0.3, linestyle='--')
	
	# 标注关键区域
	# 例如：找到液相完全消失的温度（固相线）
	# 简单寻找 LIQUID < 0.99 的点
	liq_idx = -1
	if 'LIQUID' in sorted_phases:
		liq_idx = sorted_phases.index('LIQUID')
		liq_fractions = np.array(y_data[liq_idx])
		
		# 找到液相线 (Liquidus): 液相开始减少的点
		# 找到固相线 (Solidus): 液相归零的点
		solidus_indices = np.where(liq_fractions < 0.01)[0]
		if len(solidus_indices) > 0:
			ts = temperatures[solidus_indices[-1]]  # 最后一个液相为0的点
			plt.axvline(ts, color='red', linestyle=':', label=f'Solidus ~{ts}K')
	
	plt.tight_layout()
	output_file = "phase_fraction_chart.png"
	plt.savefig(output_file, dpi=300)
	print(f"图表已保存至: {output_file}")
	plt.show()


if __name__ == "__main__":
	# 设定计算参数
	comp = {'Fe': 0.70, 'Si': 0.27, 'C': 0.03}
	plot_phase_fractions(comp, t_start=1200, t_end=2000, step=20)