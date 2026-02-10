"""
TDB (Thermodynamic Database) Parser
====================================
解析SGTE Unary Database (TDB格式)，提取纯元素的热力学函数

(已修正 - V3)
- 增加了 get_element_phases 函数，用于获取指定元素的所有可用相

"""

import re
import os
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ElementData:
	"""元素基本数据"""
	symbol: str  # 元素符号
	reference_phase: str  # 参考相态
	molar_mass: float  # 摩尔质量 (g/mol)
	reference_enthalpy: float  # 298.15K参考焓 (J/mol)
	reference_entropy: float  # 298.15K参考熵 (J/(mol*K))


class TDBFunction:
	"""TDB热力学函数类 - 处理分段温度依赖的Gibbs能函数"""
	
	def __init__ (self, name: str, parser=None):
		self.name = name
		self.temperature_ranges: List[Tuple[float, float]] = []  # [(T_start, T_end), ...]
		self.expressions: List[str] = []  # 每个温度区间的表达式
		self.parser = parser  # 引用父parser以支持函数间引用
	
	def add_range (self, t_start: float, t_end: float, expression: str):
		"""添加温度范围和对应的表达式"""
		self.temperature_ranges.append((t_start, t_end))
		self.expressions.append(expression.strip())
	
	def evaluate (self, temperature: float) -> float:
		"""
        计算指定温度下的函数值

        Args:
            temperature: 温度 (K)

        Returns:
            函数值 (J/mol)
        """
		# 查找适用的温度范围
		for i, (t_start, t_end) in enumerate(self.temperature_ranges):
			if t_start <= temperature <= t_end:
				return self._evaluate_expression(self.expressions[i], temperature)
		
		# 如果温度超出所有范围，使用最后一个表达式（外推）
		if self.temperature_ranges and temperature > self.temperature_ranges[-1][1]:
			return self._evaluate_expression(self.expressions[-1], temperature)
		
		# 如果温度低于所有范围，使用第一个表达式（外推）
		if self.temperature_ranges and temperature < self.temperature_ranges[0][0]:
			return self._evaluate_expression(self.expressions[0], temperature)
		
		raise ValueError(f"Temperature {temperature}K not covered by function {self.name}")
	
	def _evaluate_expression (self, expression: str, T: float) -> float:
		"""
        计算表达式的值
        """
		# 替换 LN(T) -> log(T)
		# (使用正则表达式确保只替换 'LN(T)' 而不是 'ALN(T)')
		try:
			# 确保 T > 0 以便 log(T)
			if T <= 0:
				T = 1.0  # 避免 log(0)
			
			expr = re.sub(r'(?<!\w)LN\(T\)', f'log({T})', expression, flags=re.IGNORECASE)
			
			# 替换 T**n -> T的n次方
			expr = re.sub(r'T\*\*(-?\d+)', lambda m: f'({T}**{m.group(1)})', expr)
			
			# 替换单独的 T -> 温度值
			expr = re.sub(r'(?<!\w)T(?!\w)', str(T), expr)
			
			# 处理科学计数法 (如 1.790585E-3)
			expr = re.sub(r'(\d+\.?\d*)E([+-]?\d+)', r'\1e\2', expr)
			
			# 处理其他函数引用（如 GHSERAL, GHSERC 等）
			if self.parser is not None:
				func_pattern = r'\b([A-Z][A-Z0-9_]*)\b'
				func_matches = re.findall(func_pattern, expr)
				
				for func_name in set(func_matches):
					if func_name in ['T', 'LN', 'EXP', 'LOG', 'SQRT', 'Y', 'N']:
						continue
					
					if func_name in self.parser.functions:
						try:
							func_value = self.parser.functions[func_name].evaluate(T)
							expr = re.sub(r'\b' + func_name + r'\b', f'({func_value})', expr)
						except Exception:
							pass
			
			safe_dict = {
				'log': math.log,
				'exp': math.exp,
				'sqrt': math.sqrt,
				'__builtins__': {}
			}
			result = eval(expr, safe_dict)
			return float(result)
		except Exception as e:
			raise ValueError(f"Failed to evaluate expression '{expression}' at T={T}K: {e}")


class TDBParser:
	"""TDB文件解析器"""
	
	def __init__ (self, tdb_file_path: str):
		"""
        初始化TDB解析器

        Args:
            tdb_file_path: TDB文件路径
        """
		self.tdb_file = tdb_file_path
		self.elements: Dict[str, ElementData] = {}
		self.functions: Dict[str, TDBFunction] = {}
		
		
		self._phase_function_map: Dict[Tuple[str, str], str] = {}
		
		
		# 用于那些没有 FUNCTION 引用的简单 PARAMETER (例如 +1000+10*T)
		self._phase_raw_expression_map: Dict[Tuple[str, str], str] = {}
		
		# ---  磁性相关容器 ---
		# 存储相的类型定义，例如 {'BCC_A2': {'p': 0.4}}
		self.phase_type_defs: Dict[str, Dict[str, float]] = {}
		
		# 存储磁性参数映射 {(ParamType, Phase, Constituents): FunctionName}
		# Key示例: ('TC', 'BCC_A2', 'FE:VA')
		self._magnetic_param_map: Dict[Tuple[str, str, str], str] = {}
		
		if os.path.exists(tdb_file_path):
			self.parse()
		else:
			raise FileNotFoundError(f"TDB file not found: {tdb_file_path}")
	
	def parse (self):
		"""解析TDB文件"""
		with open(self.tdb_file, 'r', encoding='utf-8') as f:
			content = f.read()
		
		# 必须按顺序解析
		self._parse_elements(content)
		self._parse_functions(content)
		self._parse_parameters(content)  # 解析 Gibbs 能参数
		
		# --- 解析磁性相关数据 ---
		self._parse_type_definitions(content)  # 解析 TYPE_DEFINITION
		self._parse_magnetic_parameters(content)  # 解析 TC, BM, BMAGN
	
	def _parse_elements (self, content: str):
		"""
        解析ELEMENT定义
        """
		# (修正) 匹配更灵活的 ELEMENT 格式 (S+ 是为了捕捉 /-)
		pattern = r'ELEMENT\s+(\S+)\s+(\S+)\s+([\d.E+-]+)\s+([\d.E+-]+)\s+([\d.E+-]+)\s*!'
		matches = re.finditer(pattern, content, re.MULTILINE)
		
		for match in matches:
			symbol = match.group(1)
			ref_phase = match.group(2)
			if symbol in ['/-', 'VA']:
				continue
			
			self.elements[symbol] = ElementData(
					symbol=symbol,
					reference_phase=ref_phase,
					molar_mass=float(match.group(3)),
					reference_enthalpy=float(match.group(4)),
					reference_entropy=float(match.group(5))
			)
	
	def _parse_functions (self, content: str):
		"""
        解析FUNCTION定义
        """
		function_blocks = re.findall(
				r'FUNCTION\s+(\w+)\s+([\d.]+)\s+(.*?)(?=FUNCTION|\$|\Z)',
				content,
				re.DOTALL
		)
		
		for func_name, t_start_str, func_body in function_blocks:
			t_start = float(t_start_str)
			tdb_func = TDBFunction(func_name, parser=self)
			lines = func_body.strip().split('\n')
			current_t_start = t_start
			full_expression = ""
			
			for line in lines:
				line = line.strip()
				if not line or line.startswith('$') or line.startswith('!'):
					continue
				full_expression += " " + line
				if ';' in full_expression:
					parts = full_expression.split(';')
					if len(parts) >= 2:
						expression = parts[0].strip()
						end_part = parts[1].strip()
						temp_match = re.match(r'([\d.]+)\s+([YN])', end_part)
						if temp_match:
							t_end = float(temp_match.group(1))
							is_final = temp_match.group(2) == 'N'
							tdb_func.add_range(current_t_start, t_end, expression)
							current_t_start = t_end
							full_expression = ""
							if is_final:
								break
			self.functions[func_name] = tdb_func
	
	
	def _parse_parameters (self, content: str):
		"""
        (新增) 解析 PARAMETER G(...) 块
        
        匹配: PARAMETER G(PHASE,ELEM:VA;0) T_start FUNCTION_NAME; T_end N !
        或:   PARAMETER G(PHASE,ELEM;0) T_start +EXPRESSION; T_end N !
        """
		# 匹配 PARAMETER G(...) 行
		param_pattern = r'PARAMETER\s+G\(([^)]+)\)\s+([\d.]+)\s+([^;]+);.*!'
		
		matches = re.finditer(param_pattern, content, re.MULTILINE)
		
		for match in matches:
			try:
				param_def = match.group(1)  # e.g., "BCC_A2,FE:VA;0" or "LIQUID,FE;0"
				expression = match.group(3).strip()  # e.g., "GHSERFE" or "+1000+10*T"
				
				# 提取 Phase 和 Element
				parts = param_def.split(',')
				if len(parts) < 2:
					continue
				
				phase = parts[0].strip()
				element = parts[1].split(':')[0].split(';')[0].strip()
				
				if not element or not phase:
					continue
				
				key = (element.upper(), phase.upper())
				
				# 检查 expression 是函数引用还是原始表达式
				if re.fullmatch(r'[A-Z][A-Z0-9_]+', expression):
					# 这是一个函数引用, e.g., "GHSERFE"
					if expression in self.functions:
						self._phase_function_map[key] = expression
					else:
						print(f"Warning: PARAMETER for {key} points to unknown FUNCTION '{expression}'")
				else:
					# 这是一个原始表达式, e.g., "+1000+10*T"
					self._phase_raw_expression_map[key] = expression
			
			except Exception as e:
				print(f"Warning: Failed to parse PARAMETER line: '{match.group(0)}'. Error: {e}")
	
	
	def _parse_type_definitions (self, content: str):
		"""
		解析 TYPE_DEFINITION 行以获取磁性结构因子 p
		示例: TYPE_DEFINITION & GES A_P_D BCC_A2 MAGNETIC -1.0 0.4 !
		"""
		# 正则匹配: TYPE_DEFINITION [char] [code] ... [PHASE_NAME] MAGNETIC [n] [p] !
		pattern = r'TYPE_DEFINITION\s+\S\s+.*?\s+([A-Z0-9_]+)\s+MAGNETIC\s+([\d.-]+)\s+([\d.]+)\s*!'
		
		matches = re.finditer(pattern, content, re.MULTILINE)
		for match in matches:
			try:
				phase_name = match.group(1).upper()
				# group(2) 是 n (通常-1或-3), group(3) 是 p (结构因子)
				p_factor = float(match.group(3))
				
				self.phase_type_defs[phase_name] = {'magnetic_p': p_factor}
			except Exception:
				pass
	
	def _parse_magnetic_parameters (self, content: str):
		"""
		解析磁性参数 TC (居里温度) 和 BM/BMAGN (磁矩)
		示例: PARAMETER TC(BCC_A2,FE:VA;0) 298.15 1043; ...
		"""
		# 匹配 PARAMETER TC(...) 或 BM(...) 或 BMAGN(...)
		# Group 1: TC/BM/BMAGN
		# Group 2: 定义体 (PHASE, CONST; 0)
		# Group 3: 表达式
		pattern = r'PARAMETER\s+(TC|BM|BMAGN)\(([^)]+)\)\s+([\d.]+)\s+([^;]+);.*!'
		
		matches = re.finditer(pattern, content, re.MULTILINE)
		
		for match in matches:
			try:
				param_type = match.group(1).upper()
				param_def = match.group(2)  # e.g. "BCC_A2,FE:VA;0"
				expression = match.group(4).strip()
				
				parts = param_def.split(',')
				if len(parts) < 2: continue
				
				phase = parts[0].strip().upper()
				# 提取组分字符串，移除 ;0 和空格，例如 "FE:VA"
				constituents = parts[1].split(';')[0].strip().upper()
				
				key = (param_type, phase, constituents)
				
				# 只有当表达式是函数引用时才存入 (简化处理，暂不支持内联公式)
				if re.fullmatch(r'[A-Z][A-Z0-9_]+', expression):
					self._magnetic_param_map[key] = expression
				else:
					# 如果是内联公式(如数字)，需要创建一个临时函数名或者特殊处理
					# 为了简化，这里假设如果是纯数字，直接存字符串，后续 evaluate 处理
					pass
					# 你的 unary50.tdb 中磁性参数基本都是数字或简单表达式
					# 为了支持 "1043" 这种纯数字，我们最好把它存入 parser.functions
					# 或者修改 evaluate 逻辑。
					# 简便方案：如果找不到函数名，尝试直接解析表达式。
					# 此处我们直接存储表达式字符串
					self._magnetic_param_map[key] = expression
			
			except Exception as e:
				print(f"Warning: Failed to parse magnetic param: {match.group(0)}")
				
	
	def get_stable_phase (self, element: str, temperature: float) -> Optional[str]:
		"""
		获取指定温度下元素的稳定相（Gibbs能最低的相）。

		Args:
			element: 元素符号 (e.g., 'AL')
			temperature: 温度 (K)

		Returns:
			稳定相的名称 (e.g., 'LIQUID' or 'FCC_A1')。如果找不到数据则返回 None。
		"""
		phases = self.get_element_phases(element)
		if not phases:
			return None
		
		min_g = float('inf')
		stable_phase = None
		
		for phase in phases:
			# 计算该相在当前温度下的 Gibbs 能
			g_val = self.get_gibbs_energy(element, phase, temperature)
			
			# 如果计算成功且能量更低，则更新稳定相
			if g_val is not None and g_val < min_g:
				min_g = g_val
				stable_phase = phase
		
		return stable_phase
	
	
	def get_gibbs_energy (self, element: str, phase: str, temperature: float) -> Optional[float]:
		element_upper = element.upper()
		phase_upper = phase.upper()
		
		
		
		phase_alias_map = {'BCC': 'BCC_A2', 'FCC': 'FCC_A1', 'HCP': 'HCP_A3', 'LIQ': 'LIQUID'}
		phase_upper = phase_alias_map.get(phase_upper, phase_upper)
		
		# --- SER 处理 (Step 3) ---
		if phase_upper == 'SER':
			ref_phase = self.get_reference_phase(element_upper)
			if ref_phase and ref_phase != 'SER':
				return self.get_gibbs_energy(element_upper, ref_phase, temperature)
		
		key = (element_upper, phase_upper)
		g_non_mag = None
		
		# --- 1. 获取非磁性部分 Gibbs 能 ---
		func_name = self._phase_function_map.get(key)
		if func_name:
			try:
				g_non_mag = self.functions[func_name].evaluate(temperature)
			except Exception as e:
				# Log warning...
				return None
		else:
			# 检查 raw expression
			raw_expression = self._phase_raw_expression_map.get(key)
			if raw_expression:
				
				temp_func = TDBFunction(f"temp_eval", parser=self)
				g_non_mag = temp_func._evaluate_expression(raw_expression, temperature)
		
		if g_non_mag is None:
			return None
		
		# --- 2. [关键修正] 添加磁性贡献 ---
		# 检查该元素在该相是否有磁性参数 (TC, BMAGN)
		
		magnetic_contrib = self._calculate_magnetic_contribution(element_upper, phase_upper, temperature)
		
		return g_non_mag + magnetic_contrib
	
	def _calculate_magnetic_contribution (self, element: str, phase: str, temperature: float) -> float:
		"""
		(修正版) 计算 Inden-Hillert-Jarl 磁性吉布斯自由能贡献。
		已修复：处理负数 beta 导致的 math domain error。
		"""
		element_upper = element.upper()
		phase_upper = phase.upper()
		
		# 1. 获取磁性参数
		try:
			tc_val = self._evaluate_magnetic_param('TC', element_upper, phase_upper, temperature)
			# 尝试获取 BM 或 BMAGN
			beta_val = self._evaluate_magnetic_param('BM', element_upper, phase_upper, temperature)
			if beta_val is None or abs(beta_val) < 1e-10:
				beta_val = self._evaluate_magnetic_param('BMAGN', element_upper, phase_upper, temperature)
		except Exception:
			return 0.0
		
		# 检查参数有效性
		if not tc_val or not beta_val:
			return 0.0
		
		# ============== 关键修正开始 ==============
		# SGTE 数据库中，反铁磁性通常用负的 Tc 或 Beta 表示。
		# 在代入公式前，必须取绝对值。
		tc_abs = abs(tc_val)
		beta_abs = abs(beta_val)
		
		# 防止 log(0) 或负数错误 (即便取了绝对值，beta也可能为-1.0，导致log(0))
		if beta_abs < 1e-5:
			return 0.0
		# ============== 关键修正结束 ==============
		
		# 2. 获取结构因子 p
		p = self._get_magnetic_structure_factor(phase_upper)
		
		# 3. 计算归一化温度 tau
		if tc_abs < 1e-5: return 0.0  # 防止除以零
		tau = temperature / tc_abs
		
		# 4. 计算 g(tau)
		A = 518 / 1125 + (11692 / 15975) * (1 / p - 1)
		
		if tau < 1.0:
			term1 = (79 / (140 * p * tau))
			term2 = (474 / 497) * (1 / p - 1) * ((tau ** 3) / 6 + (tau ** 9) / 135 + (tau ** 15) / 600)
			g_tau = 1 - (1 / A) * (term1 + term2)
		else:
			term = (tau ** -5) / 10 + (tau ** -15) / 315 + (tau ** -25) / 1500
			g_tau = - (1 / A) * term
		
		# 5. 计算最终 G_mag
		R = 8.314462618
		# 使用 beta_abs 替代 beta_val
		try:
			g_mag = R * temperature * math.log(beta_abs + 1) * g_tau
		except ValueError:
			# 最后的防线，防止 log 依然出错
			print(
				f"Warning: Magnetic calculation error for {element} in {phase} at {temperature}K. Beta_abs={beta_abs}")
			return 0.0
		
		return g_mag
	
	def _evaluate_magnetic_param (self, param_type: str, element: str, phase: str, temperature: float) -> float:
		element_upper = element.upper()
		phase_upper = phase.upper()
		
		# 构建可能的键
		constituents_va = f"{element_upper}:VA"
		constituents_pure = element_upper
		
		expr = None
		
		# 1. 优先查找带 VA 的形式 (例如 TC, BCC_A2, FE:VA)
		key_va = (param_type, phase_upper, constituents_va)
		if key_va in self._magnetic_param_map:
			expr = self._magnetic_param_map[key_va]
		else:
			# 2. 回退查找纯组元形式
			key_pure = (param_type, phase_upper, constituents_pure)
			if key_pure in self._magnetic_param_map:
				expr = self._magnetic_param_map[key_pure]
		
		if not expr:
			return 0.0
		
		# 3. 评估表达式
		# 情况 A: 它是函数名 (在 FUNCTION 块中定义)
		if expr in self.functions:
			return self.functions[expr].evaluate(temperature)
		
		# 情况 B: 它是直接的数值或表达式字符串 (例如 "1043" 或 "1043+0.1*T")
		try:
			# 利用临时的 TDBFunction 来计算表达式
			temp_func = TDBFunction("temp_mag", parser=self)
			return temp_func._evaluate_expression(expr, temperature)
		except Exception:
			return 0.0
	
	def _get_magnetic_structure_factor (self, phase: str) -> float:
		# 1. 尝试从解析到的 TYPE_DEFINITION 中获取
		if phase in self.phase_type_defs:
			return self.phase_type_defs[phase].get('magnetic_p', 0.28)
		
		# 2. 兜底默认值 (SGTE 标准)
		if 'BCC' in phase: return 0.40
		return 0.28
	
	
	def get_element_phases (self, element: str) -> List[str]:
		"""
        获取指定元素的所有可用相名称。
        
        遍历解析出的参数映射表，找出所有与该元素相关的相。
        
        Args:
            element: 元素符号 (例如 'AL', 'Fe')
            
        Returns:
            相名称列表 (例如 ['LIQUID', 'FCC_A1', 'BCC_A2'])，按字母顺序排序
        """
		element_upper = element.upper()
		phases = set()
		
		# 1. 遍历函数映射表 _phase_function_map
		# 键是 (Element, Phase)
		for (elem, phase) in self._phase_function_map.keys():
			if elem == element_upper:
				phases.add(phase)
		
		# 2. 遍历原始表达式映射表 _phase_raw_expression_map
		for (elem, phase) in self._phase_raw_expression_map.keys():
			if elem == element_upper:
				phases.add(phase)
		
		return sorted(list(phases))
	
	def get_enthalpy (self, element: str, phase: str, temperature: float) -> Optional[float]:
		"""
        计算指定温度下的摩尔焓
        """
		delta_T = 0.1
		G_T = self.get_gibbs_energy(element, phase, temperature)
		if G_T is None: return None
		try:
			G_plus = self.get_gibbs_energy(element, phase, temperature + delta_T)
			G_minus = self.get_gibbs_energy(element, phase, temperature - delta_T)
			if G_plus is None or G_minus is None: return None
			dG_dT = (G_plus - G_minus) / (2 * delta_T)
			H = G_T - temperature * dG_dT
			return H
		except Exception as e:
			print(f"Warning: Failed to calculate enthalpy for {element}-{phase} at {temperature}K: {e}")
			return None
	
	def get_entropy (self, element: str, phase: str, temperature: float) -> Optional[float]:
		"""
        计算指定温度下的摩尔熵
        """
		delta_T = 0.1
		try:
			G_plus = self.get_gibbs_energy(element, phase, temperature + delta_T)
			G_minus = self.get_gibbs_energy(element, phase, temperature - delta_T)
			if G_plus is None or G_minus is None: return None
			dG_dT = (G_plus - G_minus) / (2 * delta_T)
			S = -dG_dT
			return S
		except Exception as e:
			print(f"Warning: Failed to calculate entropy for {element}-{phase} at {temperature}K: {e}")
			return None
	
	def get_heat_capacity (self, element: str, phase: str, temperature: float) -> Optional[float]:
		"""
        计算指定温度下的等压热容
        """
		delta_T = 0.1
		try:
			G_T = self.get_gibbs_energy(element, phase, temperature)
			G_plus = self.get_gibbs_energy(element, phase, temperature + delta_T)
			G_minus = self.get_gibbs_energy(element, phase, temperature - delta_T)
			if G_T is None or G_plus is None or G_minus is None: return None
			d2G_dT2 = (G_plus - 2 * G_T + G_minus) / (delta_T ** 2)
			Cp = -temperature * d2G_dT2
			return Cp
		except Exception as e:
			print(f"Warning: Failed to calculate heat capacity for {element}-{phase} at {temperature}K: {e}")
			return None

	def _parse_sgte_polynomial_coefficients(self, expression: str) -> Dict[str, float]:
		"""
		解析SGTE多项式表达式，提取各项系数

		SGTE多项式格式:
		G(T) = a + b*T + c*T*LN(T) + d*T^2 + e*T^3 + f*T^-1 + g*T^7 + h*T^-9

		参数:
		-----
		expression : str
			SGTE多项式表达式字符串

		返回:
		-----
		Dict[str, float]: 系数字典
			{'a': 常数项, 'b': T系数, 'c': T*ln(T)系数,
			 'd': T^2系数, 'e': T^3系数, 'f': T^-1系数,
			 'g': T^7系数, 'h': T^-9系数}
		"""
		coeffs = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'd': 0.0,
		          'e': 0.0, 'f': 0.0, 'g': 0.0, 'h': 0.0}

		# 清理表达式：移除空格，统一大小写
		expr = expression.upper().replace(' ', '')

		# 移除对其他函数的引用（如 +GHSERAL, +GHSERFE）
		# 这些是固相参考态，不参与ΔG_f的计算
		expr = re.sub(r'[+\-]?GHSER[A-Z]+', '', expr)
		expr = re.sub(r'[+\-]?GHS[A-Z]+', '', expr)

		# 数字模式：匹配整数、小数、科学计数法
		num_pattern = r'[+-]?\d+\.?\d*(?:E[+-]?\d+)?'

		# 直接在整个表达式上匹配各类项

		# T**7 项 (如 +79.337E-21*T**7)
		match_t7 = re.search(rf'({num_pattern})\*?T\*\*7', expr)
		if match_t7:
			coeffs['g'] = float(match_t7.group(1))

		# T**(-9) 项
		match_tn9 = re.search(rf'({num_pattern})\*?T\*\*\(?-9\)?', expr)
		if match_tn9:
			coeffs['h'] = float(match_tn9.group(1))

		# T**(-1) 项
		match_tn1 = re.search(rf'({num_pattern})\*?T\*\*\(?-1\)?', expr)
		if match_tn1:
			coeffs['f'] = float(match_tn1.group(1))

		# T**3 项
		match_t3 = re.search(rf'({num_pattern})\*?T\*\*3', expr)
		if match_t3:
			coeffs['e'] = float(match_t3.group(1))

		# T**2 项
		match_t2 = re.search(rf'({num_pattern})\*?T\*\*2', expr)
		if match_t2:
			coeffs['d'] = float(match_t2.group(1))

		# T*LN(T) 项 (如 -31.748192*T*LN(T))
		match_tlnt = re.search(rf'({num_pattern})\*?T\*?LN\(T\)', expr)
		if match_tlnt:
			coeffs['c'] = float(match_tlnt.group(1))

		# 纯T项 (如 -11.84185*T)，但不是 T*LN(T) 或 T**n
		# 使用负向前瞻排除 T*LN 和 T**
		match_t = re.search(rf'({num_pattern})\*T(?!\*|LN)', expr)
		if match_t:
			coeffs['b'] = float(match_t.group(1))

		# 常数项：表达式开头的数字，或者 + 后面紧跟的数字（不含T）
		# 先移除所有已匹配的项
		remaining = expr
		remaining = re.sub(rf'{num_pattern}\*?T\*\*\(?-?\d+\)?', '', remaining)
		remaining = re.sub(rf'{num_pattern}\*?T\*?LN\(T\)', '', remaining)
		remaining = re.sub(rf'{num_pattern}\*T', '', remaining)

		# 提取剩余的常数
		const_matches = re.findall(rf'^{num_pattern}|(?<=[+\-])\d+\.?\d*(?:E[+-]?\d+)?', remaining)
		for const in const_matches:
			try:
				coeffs['a'] += float(const)
			except ValueError:
				pass

		# 如果上面方法没找到常数，尝试直接匹配开头的数字
		if coeffs['a'] == 0.0:
			match_const = re.match(rf'({num_pattern})(?=[+\-]|$)', expr)
			if match_const:
				coeffs['a'] = float(match_const.group(1))

		return coeffs

	def get_enthalpy_of_fusion(self, element: str, temperature: float = None) -> Optional[float]:
		"""
		计算元素在熔点处的熔化焓 ΔH_f

		从SGTE TDB文件解析液相Gibbs能函数，提取ΔG_f多项式系数，
		然后使用热力学关系计算ΔH_f：

		对于 ΔG_f = a + b*T + c*T*ln(T) + d*T² + e*T³ + f*T⁻¹ + g*T⁷ + h*T⁻⁹
		熔化焓为：
		ΔH_f(T) = a - c*T - d*T² - 2*e*T³ + 2*f*T⁻¹ - 6*g*T⁷ + 10*h*T⁻⁹

		注意：ΔG_f表达式仅在熔点以下有效。高温区间的GLIQ表达式是绝对Gibbs能，
		不能用于计算熔化焓。因此本方法始终使用第一个温度区间（熔点以下）的表达式。

		参数:
		-----
		element : str
			元素符号 (如 'Al', 'Fe')
		temperature : float, optional
			温度 (K)。如果为None，使用元素的熔点

		返回:
		-----
		float or None: 熔化焓 (J/mol)，如果无法计算则返回None
		"""
		element_upper = element.upper()

		# 如果没有指定温度，使用熔点
		if temperature is None:
			from core.element import Element
			elem = Element(element)
			if elem.is_exist and elem.tm:
				temperature = elem.tm
			else:
				temperature = 1000.0  # 默认值

		# 获取液相函数名 (GLIQAL, GLIQFE, etc.)
		liquid_func_name = f"GLIQ{element_upper}"

		# 检查是否有该函数
		if liquid_func_name not in self.functions:
			# 尝试其他命名方式
			for func_name in self.functions.keys():
				if 'LIQ' in func_name and element_upper in func_name:
					liquid_func_name = func_name
					break
			else:
				return None

		# 获取函数表达式
		func = self.functions.get(liquid_func_name)
		if not func or not func.expressions:
			return None

		# 重要：始终使用第一个表达式（熔点以下的ΔG_f表达式）
		# 高温区间的表达式是绝对Gibbs能，不包含+GHSER项，不能用于计算ΔH_f
		expression = func.expressions[0]

		if not expression:
			return None

		# 检查表达式是否包含GHSER引用（这是ΔG_f表达式的特征）
		if 'GHSER' not in expression.upper() and 'GHS' not in expression.upper():
			# 如果没有GHSER引用，可能不是ΔG_f表达式，尝试其他方法
			# 使用数值微分计算
			return None

		# 解析系数
		coeffs = self._parse_sgte_polynomial_coefficients(expression)

		# 计算熔化焓（在熔点温度处）
		# ΔH_f(T) = a - c*T - d*T² - 2*e*T³ + 2*f*T⁻¹ - 6*g*T⁷ + 10*h*T⁻⁹
		T = temperature
		delta_H_f = coeffs['a']
		delta_H_f -= coeffs['c'] * T
		delta_H_f -= coeffs['d'] * T**2
		delta_H_f -= 2 * coeffs['e'] * T**3
		if T > 0:
			delta_H_f += 2 * coeffs['f'] / T
		delta_H_f -= 6 * coeffs['g'] * T**7
		if T > 0:
			delta_H_f += 10 * coeffs['h'] / (T**9)

		return delta_H_f

	def get_enthalpy_of_fusion_coefficients(self, element: str) -> Optional[Dict[str, float]]:
		"""
		获取元素熔化焓的SGTE多项式系数

		返回ΔG_f表达式的系数，可用于计算任意温度下的ΔH_f

		参数:
		-----
		element : str
			元素符号

		返回:
		-----
		Dict[str, float] or None: 系数字典
		"""
		element_upper = element.upper()

		# 获取液相函数名
		liquid_func_name = f"GLIQ{element_upper}"

		if liquid_func_name not in self.functions:
			for func_name in self.functions.keys():
				if 'LIQ' in func_name and element_upper in func_name:
					liquid_func_name = func_name
					break
			else:
				return None

		func = self.functions.get(liquid_func_name)
		if not func or not func.expressions:
			return None

		# 通常使用高温区间的表达式（熔点以上）
		expression = func.expressions[-1] if func.expressions else None

		if not expression:
			return None

		return self._parse_sgte_polynomial_coefficients(expression)

	def get_element_info (self, element: str) -> Optional[ElementData]:
		"""
        获取元素基本信息
        """
		return self.elements.get(element.upper())
	
	
	def get_reference_phase (self, element_symbol: str) -> Optional[str]:
		"""
        (已修正) 从缓存中获取元素的标准元素参考 (SER) 固相。
        """
		element_data = self.elements.get(element_symbol.upper())
		if element_data:
			return element_data.reference_phase
		
		return None
	
	def list_available_elements (self) -> List[str]:
		"""返回所有可用元素的列表"""
		return sorted(list(self.elements.keys()))
	
	def list_available_functions (self, element: str = None) -> List[str]:
		"""
        列出可用的函数
        """
		if element is None:
			return sorted(list(self.functions.keys()))
		else:
			element_upper = element.upper()
			return sorted([f for f in self.functions.keys() if element_upper in f])


# 单例模式：全局TDB解析器实例
_global_tdb_parser: Optional[TDBParser] = None


def get_tdb_parser () -> TDBParser:
	"""
    获取全局TDB解析器实例（单例模式）
    """
	global _global_tdb_parser
	
	if _global_tdb_parser is None:
		# 查找TDB文件路径
		current_dir = os.path.dirname(os.path.abspath(__file__))
		tdb_path = os.path.join(current_dir, '..', 'database', 'data', 'unary50.tdb')
		tdb_path = os.path.normpath(tdb_path)
		
		if not os.path.exists(tdb_path):
			tdb_path = os.path.join(os.path.dirname(__file__), 'unary50.tdb')
		
		_global_tdb_parser = TDBParser(tdb_path)
	
	return _global_tdb_parser
