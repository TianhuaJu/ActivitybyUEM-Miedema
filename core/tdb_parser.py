"""
TDB (Thermodynamic Database) Parser
====================================
解析SGTE Unary Database (TDB格式)，提取纯元素的热力学函数

(已修正 - V3)
- 增加了 get_element_phases 函数，用于获取指定元素的所有可用相

作者: Claude
日期: 2025-11-08
"""

import re
import os
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ElementData:
    """元素基本数据"""
    symbol: str              # 元素符号
    reference_phase: str     # 参考相态
    molar_mass: float        # 摩尔质量 (g/mol)
    reference_enthalpy: float  # 298.15K参考焓 (J/mol)
    reference_entropy: float   # 298.15K参考熵 (J/(mol*K))


class TDBFunction:
    """TDB热力学函数类 - 处理分段温度依赖的Gibbs能函数"""

    def __init__(self, name: str, parser=None):
        self.name = name
        self.temperature_ranges: List[Tuple[float, float]] = []  # [(T_start, T_end), ...]
        self.expressions: List[str] = []  # 每个温度区间的表达式
        self.parser = parser  # 引用父parser以支持函数间引用

    def add_range(self, t_start: float, t_end: float, expression: str):
        """添加温度范围和对应的表达式"""
        self.temperature_ranges.append((t_start, t_end))
        self.expressions.append(expression.strip())

    def evaluate(self, temperature: float) -> float:
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

    def _evaluate_expression(self, expression: str, T: float) -> float:
        """
        计算表达式的值
        """
        # 替换 LN(T) -> log(T)
        # (使用正则表达式确保只替换 'LN(T)' 而不是 'ALN(T)')
        try:
            # 确保 T > 0 以便 log(T)
            if T <= 0:
                T = 1.0 # 避免 log(0)
                
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

    def __init__(self, tdb_file_path: str):
        """
        初始化TDB解析器

        Args:
            tdb_file_path: TDB文件路径
        """
        self.tdb_file = tdb_file_path
        self.elements: Dict[str, ElementData] = {}
        self.functions: Dict[str, TDBFunction] = {}
        
        # (新增) (Element, Phase) -> FunctionName 映射
        # 例如: {('FE', 'BCC_A2'): 'GHSERFE', ('NI', 'BCC_A2'): 'GBCCNI'}
        self._phase_function_map: Dict[Tuple[str, str], str] = {}
        
        # (新增) (Element, Phase) -> Raw Parameter String 映射
        # 用于那些没有 FUNCTION 引用的简单 PARAMETER (例如 +1000+10*T)
        self._phase_raw_expression_map: Dict[Tuple[str, str], str] = {}


        if os.path.exists(tdb_file_path):
            self.parse()
        else:
            raise FileNotFoundError(f"TDB file not found: {tdb_file_path}")

    def parse(self):
        """解析TDB文件"""
        with open(self.tdb_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 必须按顺序解析
        self._parse_elements(content)
        self._parse_functions(content)
        # (新增)
        self._parse_parameters(content)

    def _parse_elements(self, content: str):
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

    def _parse_functions(self, content: str):
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

    # --- (新增方法) ---
    def _parse_parameters(self, content: str):
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
                param_def = match.group(1) # e.g., "BCC_A2,FE:VA;0" or "LIQUID,FE;0"
                expression = match.group(3).strip() # e.g., "GHSERFE" or "+1000+10*T"
                
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

    # --- (重写的方法) ---
    def get_gibbs_energy(self, element: str, phase: str, temperature: float) -> Optional[float]:
        """
        (已重写) 获取指定元素、相态和温度下的Gibbs能。
        
        此函数现在使用 _phase_function_map (来自 PARAMETER 块)
        来查找正确的函数。
        """
        element_upper = element.upper()
        phase_upper = phase.upper()
        key = (element_upper, phase_upper)

        # 1. 检查 (Element, Phase) 是否在 PARAMETER 映射中
        func_name = self._phase_function_map.get(key)
        if func_name:
            try:
                # 找到了函数引用 (例如 'GHSERFE' )
                return self.functions[func_name].evaluate(temperature)
            except Exception as e:
                print(f"Warning: Failed to evaluate {func_name} for {key} at {temperature}K: {e}")
                return None
        
        # 2. 检查 (Element, Phase) 是否有原始表达式
        raw_expression = self._phase_raw_expression_map.get(key)
        if raw_expression:
            try:
                # 找到了原始表达式 (例如 10000-2*T)
                # 我们需要一个临时的 TDBFunction 来评估它
                temp_func = TDBFunction(f"temp_{element_upper}_{phase_upper}", parser=self)
                return temp_func._evaluate_expression(raw_expression, temperature)
            except Exception as e:
                print(f"Warning: Failed to evaluate raw expression '{raw_expression}' for {key} at {temperature}K: {e}")
                return None

        # 3. (回退) 如果请求的是 'SER'，则查找其参考相并再次尝试
        if phase_upper == 'SER':
            ref_phase = self.get_reference_phase(element_upper)
            if ref_phase and ref_phase != 'SER':
                # 递归调用 G(element, 'BCC_A2', T)
                return self.get_gibbs_energy(element_upper, ref_phase, temperature)

        # 4. (回退) 尝试通用相名 (例如 'BCC' -> 'BCC_A2')
        phase_map = {'BCC': 'BCC_A2', 'FCC': 'FCC_A1', 'HCP': 'HCP_A3'}
        if phase_upper in phase_map:
            mapped_phase = phase_map[phase_upper]
            return self.get_gibbs_energy(element_upper, mapped_phase, temperature)
            
        # 5. 最终失败
        print(f"Warning: TDB function for {element}-{phase} not found in PARAMETER block.")
        return None
    
    def get_element_phases(self, element: str) -> List[str]:
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

    def get_enthalpy(self, element: str, phase: str, temperature: float) -> Optional[float]:
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

    def get_entropy(self, element: str, phase: str, temperature: float) -> Optional[float]:
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

    def get_heat_capacity(self, element: str, phase: str, temperature: float) -> Optional[float]:
        """
        计算指定温度下的等压热容
        """
        delta_T = 0.1
        try:
            G_T = self.get_gibbs_energy(element, phase, temperature)
            G_plus = self.get_gibbs_energy(element, phase, temperature + delta_T)
            G_minus = self.get_gibbs_energy(element, phase, temperature - delta_T)
            if G_T is None or G_plus is None or G_minus is None: return None
            d2G_dT2 = (G_plus - 2*G_T + G_minus) / (delta_T ** 2)
            Cp = -temperature * d2G_dT2
            return Cp
        except Exception as e:
            print(f"Warning: Failed to calculate heat capacity for {element}-{phase} at {temperature}K: {e}")
            return None

    def get_element_info(self, element: str) -> Optional[ElementData]:
        """
        获取元素基本信息
        """
        return self.elements.get(element.upper())

    # --- (此函数现在使用 self.elements 缓存) ---
    def get_reference_phase(self, element_symbol: str) -> Optional[str]:
        """
        (已修正) 从缓存中获取元素的标准元素参考 (SER) 固相。
        """
        element_data = self.elements.get(element_symbol.upper())
        if element_data:
            return element_data.reference_phase
        
        return None

    def list_available_elements(self) -> List[str]:
        """返回所有可用元素的列表"""
        return sorted(list(self.elements.keys()))

    def list_available_functions(self, element: str = None) -> List[str]:
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


def get_tdb_parser() -> TDBParser:
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
    
 


# 测试代码
if __name__ == "__main__":
    parser = get_tdb_parser()

    print("=" * 60)
    print("TDB Parser Test (V2 - PARAMETER-aware)")
    print("=" * 60)

    print("\n1. Element Information:")
    for elem in ['FE', 'AL', 'CU', 'NI']:
        info = parser.get_element_info(elem)
        if info:
            print(f"\n{elem}:")
            print(f"  Reference Phase: {info.reference_phase}")

    print("\n1b. Get Reference Phase (Test):")
    for elem in ['FE', 'SI', 'C', 'AL']:
        ref_phase = parser.get_reference_phase(elem)
        print(f"  {elem} -> {ref_phase}")
        
    print("\n1c. Testing get_element_phases:")
    for elem in ['FE', 'AL', 'C']:
        phases = parser.get_element_phases(elem)
        print(f"  Phases for {elem}: {phases}")
        
    print("\n2. Thermodynamic Properties at 1873K (1600°C):")
    test_elements = ['FE', 'AL', 'CU', 'NI']
    T_test = 1873.0

    for elem in test_elements:
        print(f"\n{elem}:")

        G_liq = parser.get_gibbs_energy(elem, 'LIQUID', T_test)
        print(f"  G(liquid, {T_test}K) = {G_liq:.2f} J/mol")

        # (修正测试) 测试 'BCC_A2'
        G_bcc = parser.get_gibbs_energy(elem, 'BCC_A2', T_test)
        if G_bcc:
            print(f"  G(BCC_A2, {T_test}K) = {G_bcc:.2f} J/mol")

        # (修正测试) 测试 'FCC_A1'
        G_fcc = parser.get_gibbs_energy(elem, 'FCC_A1', T_test)
        if G_fcc:
            print(f"  G(FCC_A1, {T_test}K) = {G_fcc:.2f} J/mol")

    print("\n" + "=" * 60)
    print(f"Total elements parsed: {len(parser.elements)}")
    print(f"Total functions parsed: {len(parser.functions)}")
    print(f"Total (Elem, Phase) maps parsed: {len(parser._phase_function_map)}")
    print("=" * 60)