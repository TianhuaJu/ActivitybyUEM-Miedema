import os
from datetime import datetime
from core.utils import get_canonical_alloy_name

# 定义存放所有日志的文件夹名称
LOG_DIRECTORY = "calculation_logs"


def log_contribution_coefficients (
		ternary_system: str,
		model_name: str,
		temperature: float,
		contribution_data: dict,
		full_alloy_context: str = ""
):
	"""
	根据用户指定的最终精确格式，将贡献系数记录到日志文件中。
	"""
	try:
		# --- 文件名生成逻辑 (此部分已正确，无需修改) ---
		if full_alloy_context:
			canonical_name = get_canonical_alloy_name(full_alloy_context)
		else:
			canonical_name = get_canonical_alloy_name(ternary_system)
		
		filename = f"Log_{canonical_name}_{model_name}.txt"
		
		# --- 目录和路径逻辑 (无需修改) ---
		current_dir = os.path.dirname(os.path.abspath(__file__))
		project_root = os.path.dirname(current_dir)
		log_path = os.path.join(project_root, LOG_DIRECTORY)
		
		if not os.path.exists(log_path):
			os.makedirs(log_path)
		
		filepath = os.path.join(log_path, filename)
		
		# ★★★★★ 内容格式化逻辑 (精确对齐修正) ★★★★★
		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		
		content = []
		# Header
		content.append(f"Contribution Coefficient Log for Alloy System: {canonical_name}")
		content.append(f"Extrapolation Model: {model_name} 模型")
		content.append("=" * 60)
		
		# Calculation Record
		content.append(f"\n# --- Calculation Record: {timestamp} ---")
		content.append(f"# Calculation Type: Fixed Point")
		content.append(f"# Parameter 'temperature': {temperature:.2f}K")
		content.append("#" + "-" * 50)
		
		# 遍历贡献系数数据来格式化输出
		for subsystem, contributions in contribution_data.items():
			content.append(f"\n# For Binary Sub-system: {subsystem}")
			for contributor, value in contributions.items():
				# 使用 f-string 的格式化功能来创建对齐的列
				# {contributor:<12} 表示左对齐，并占用12个字符的宽度
				line = f"{contributor:<12}: {value:.4f}"
				content.append(line)
			content.append(f"\t\t in {subsystem}")  # 此处的对齐保持不变
		
		# 写入文件
		with open(filepath, "w", encoding="utf-8") as f:
			f.write("\n".join(content))
	
	except Exception as e:
		print(f"Error while writing log file: {e}")