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
		
		
		filename = f"ContributionCoefficients({model_name}).txt"
		
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
		
		content.append(f"Extrapolation Model: {model_name} 模型")
		content.append("=" * 60)
		
		# Calculation Record
		content.append(f"\n# --- Calculation Record: {timestamp} ---")
		content.append(f"Alloy System:  {ternary_system}")
		content.append(f"T =  {temperature:.2f} K")
		content.append("#" + "-" * 50)
		
		# 遍历贡献系数数据来格式化输出
		for subsystem, contributions in contribution_data.items():
			
			parts = [f"{contributor:<12}: {value:.4f}" for contributor, value in contributions.items()]
			line = "\t\t".join(parts) + f"\t\t in ({subsystem})"
			content.append(line)
				
		
		# 写入文件
		with open(filepath, "a", encoding="utf-8") as f:
			f.write("\n".join(content))
	
	except Exception as e:
		print(f"Error while writing log file: {e}")