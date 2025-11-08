"""
TDB (Thermodynamic Database) Parser
====================================
解析SGTE Unary Database (TDB格式)，提取纯元素的热力学函数

主要功能:
- 解析ELEMENT定义（元素基本信息）
- 解析FUNCTION定义（分段Gibbs能函数）
- 计算指定温度下的Gibbs能、焓、熵等热力学性质
- 支持CALPHAD格式的热力学函数表达式

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
        if temperature > self.temperature_ranges[-1][1]:
            return self._evaluate_expression(self.expressions[-1], temperature)

        # 如果温度低于所有范围，使用第一个表达式（外推）
        if temperature < self.temperature_ranges[0][0]:
            return self._evaluate_expression(self.expressions[0], temperature)

        raise ValueError(f"Temperature {temperature}K not covered by function {self.name}")

    def _evaluate_expression(self, expression: str, T: float) -> float:
        """
        计算表达式的值

        支持的CALPHAD表达式格式:
        - a + b*T + c*T*LN(T) + d*T**2 + e*T**3 + f*T**(-1) + g*T**7 + h*T**(-9)
        - 可以包含对其他函数的引用（递归计算）

        Args:
            expression: 数学表达式字符串
            T: 温度 (K)

        Returns:
            表达式的值
        """
        # 替换 LN(T) -> log(T)
        expr = expression.replace('LN(T)', f'log({T})')

        # 替换 T**n -> T的n次方
        expr = re.sub(r'T\*\*(-?\d+)', lambda m: f'({T}**{m.group(1)})', expr)

        # 替换单独的 T -> 温度值
        expr = re.sub(r'(?<!\w)T(?!\w)', str(T), expr)

        # 处理科学计数法 (如 1.790585E-3)
        expr = re.sub(r'(\d+\.?\d*)E([+-]?\d+)', r'\1e\2', expr)

        # 处理其他函数引用（如 GHSERAL, GHSERC 等）
        # 查找所有可能的函数名（大写字母开头的标识符）
        if self.parser is not None:
            # 查找所有函数引用
            func_pattern = r'\b([A-Z][A-Z0-9_]*)\b'
            func_matches = re.findall(func_pattern, expr)

            # 替换每个函数引用为其计算值
            for func_name in set(func_matches):
                # 排除已经替换过的T和常见数学常数
                if func_name in ['T', 'LN', 'EXP', 'LOG', 'SQRT', 'Y', 'N']:
                    continue

                if func_name in self.parser.functions:
                    try:
                        # 递归计算引用的函数值
                        func_value = self.parser.functions[func_name].evaluate(T)
                        # 替换函数名为其值
                        expr = re.sub(r'\b' + func_name + r'\b', f'({func_value})', expr)
                    except Exception as e:
                        # 如果无法求值，保持原样
                        pass

        try:
            # 计算表达式（使用 eval，但在受控环境中）
            # 提供安全的数学函数
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

        if os.path.exists(tdb_file_path):
            self.parse()
        else:
            raise FileNotFoundError(f"TDB file not found: {tdb_file_path}")

    def parse(self):
        """解析TDB文件"""
        with open(self.tdb_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析ELEMENT定义
        self._parse_elements(content)

        # 解析FUNCTION定义
        self._parse_functions(content)

    def _parse_elements(self, content: str):
        """
        解析ELEMENT定义

        格式: ELEMENT SYMBOL REFERENCE_PHASE MASS ENTHALPY ENTROPY !
        例如: ELEMENT FE BCC_A2 5.5847E+01 4.4890E+03 2.7280E+01 !
        """
        # 匹配ELEMENT定义的正则表达式
        pattern = r'ELEMENT\s+(\w+)\s+(\S+)\s+([\d.E+-]+)\s+([\d.E+-]+)\s+([\d.E+-]+)\s*!'

        matches = re.finditer(pattern, content, re.MULTILINE)

        for match in matches:
            symbol = match.group(1)
            ref_phase = match.group(2)
            mass = float(match.group(3).replace('E', 'e'))
            enthalpy = float(match.group(4).replace('E', 'e'))
            entropy = float(match.group(5).replace('E', 'e'))

            # 跳过特殊元素（电子气、真空）
            if symbol in ['/-', 'VA']:
                continue

            self.elements[symbol] = ElementData(
                symbol=symbol,
                reference_phase=ref_phase,
                molar_mass=mass,
                reference_enthalpy=enthalpy,
                reference_entropy=entropy
            )

    def _parse_functions(self, content: str):
        """
        解析FUNCTION定义

        格式:
        FUNCTION FNAME T_start
        expression1; T_end1 Y
        expression2; T_end2 Y
        ...
        expressionN; T_endN N !
        """
        # 分割成独立的FUNCTION块
        function_blocks = re.findall(
            r'FUNCTION\s+(\w+)\s+([\d.]+)\s+(.*?)(?=FUNCTION|\$|\Z)',
            content,
            re.DOTALL
        )

        for func_name, t_start_str, func_body in function_blocks:
            t_start = float(t_start_str)

            # 创建函数对象，传递parser引用以支持函数间引用
            tdb_func = TDBFunction(func_name, parser=self)

            # 解析分段函数
            # 每一行格式: expression; T_end Y/N
            lines = func_body.strip().split('\n')

            current_t_start = t_start
            full_expression = ""

            for line in lines:
                line = line.strip()
                if not line or line.startswith('$') or line.startswith('!'):
                    continue

                # 累积表达式（可能跨多行）
                full_expression += " " + line

                # 检查是否是段的结束（包含 ; T_end Y/N）
                if ';' in full_expression:
                    parts = full_expression.split(';')
                    if len(parts) >= 2:
                        expression = parts[0].strip()
                        end_part = parts[1].strip()

                        # 提取温度上限
                        temp_match = re.match(r'([\d.]+)\s+([YN])', end_part)
                        if temp_match:
                            t_end = float(temp_match.group(1))
                            is_final = temp_match.group(2) == 'N'

                            # 添加这个温度范围
                            tdb_func.add_range(current_t_start, t_end, expression)

                            # 准备下一段
                            current_t_start = t_end
                            full_expression = ""

                            if is_final:
                                break

            # 存储函数
            self.functions[func_name] = tdb_func

    def get_gibbs_energy(self, element: str, phase: str, temperature: float) -> Optional[float]:
        """
        获取指定元素、相态和温度下的Gibbs能

        Args:
            element: 元素符号 (如 'FE', 'AL')
            phase: 相态 ('LIQUID', 'BCC', 'FCC', 'HCP', 'SER'等)
            temperature: 温度 (K)

        Returns:
            Gibbs能 (J/mol)，如果未找到则返回None
        """
        # 构建函数名
        # 标准命名: GLIQ** (liquid), GBCC** (BCC), GFCC** (FCC), GHSER** (SER)
        phase_prefix_map = {
            'LIQUID': 'GLIQ',
            'BCC': 'GBCC',
            'BCC_A2': 'GBCC',
            'FCC': 'GFCC',
            'FCC_A1': 'GFCC',
            'HCP': 'GHCP',
            'HCP_A3': 'GHCP',
            'SER': 'GHSER',  # Standard Element Reference
        }

        phase_key = phase.upper()
        if phase_key in phase_prefix_map:
            func_name = f"{phase_prefix_map[phase_key]}{element.upper()}"
        else:
            func_name = f"G{phase.upper()}{element.upper()}"

        if func_name in self.functions:
            try:
                return self.functions[func_name].evaluate(temperature)
            except Exception as e:
                print(f"Warning: Failed to evaluate {func_name} at {temperature}K: {e}")
                return None
        else:
            # 如果请求的函数不存在，尝试回退到标准态
            if phase_key != 'SER':
                return self.get_gibbs_energy(element, 'SER', temperature)
            return None

    def get_enthalpy(self, element: str, phase: str, temperature: float) -> Optional[float]:
        """
        计算指定温度下的摩尔焓

        H(T) = G(T) - T * (dG/dT)
        使用数值微分近似: dG/dT ≈ [G(T+ΔT) - G(T-ΔT)] / (2*ΔT)

        Args:
            element: 元素符号
            phase: 相态
            temperature: 温度 (K)

        Returns:
            摩尔焓 (J/mol)
        """
        delta_T = 0.1  # 温度微扰

        G_T = self.get_gibbs_energy(element, phase, temperature)
        if G_T is None:
            return None

        try:
            G_plus = self.get_gibbs_energy(element, phase, temperature + delta_T)
            G_minus = self.get_gibbs_energy(element, phase, temperature - delta_T)

            if G_plus is None or G_minus is None:
                return None

            dG_dT = (G_plus - G_minus) / (2 * delta_T)
            H = G_T - temperature * dG_dT

            return H
        except Exception as e:
            print(f"Warning: Failed to calculate enthalpy for {element}-{phase} at {temperature}K: {e}")
            return None

    def get_entropy(self, element: str, phase: str, temperature: float) -> Optional[float]:
        """
        计算指定温度下的摩尔熵

        S(T) = -dG/dT
        使用数值微分近似

        Args:
            element: 元素符号
            phase: 相态
            temperature: 温度 (K)

        Returns:
            摩尔熵 (J/(mol*K))
        """
        delta_T = 0.1

        try:
            G_plus = self.get_gibbs_energy(element, phase, temperature + delta_T)
            G_minus = self.get_gibbs_energy(element, phase, temperature - delta_T)

            if G_plus is None or G_minus is None:
                return None

            dG_dT = (G_plus - G_minus) / (2 * delta_T)
            S = -dG_dT

            return S
        except Exception as e:
            print(f"Warning: Failed to calculate entropy for {element}-{phase} at {temperature}K: {e}")
            return None

    def get_heat_capacity(self, element: str, phase: str, temperature: float) -> Optional[float]:
        """
        计算指定温度下的等压热容

        Cp(T) = dH/dT = -T * d²G/dT²
        使用数值二阶微分近似

        Args:
            element: 元素符号
            phase: 相态
            temperature: 温度 (K)

        Returns:
            等压热容 (J/(mol*K))
        """
        delta_T = 0.1

        try:
            G_T = self.get_gibbs_energy(element, phase, temperature)
            G_plus = self.get_gibbs_energy(element, phase, temperature + delta_T)
            G_minus = self.get_gibbs_energy(element, phase, temperature - delta_T)

            if G_T is None or G_plus is None or G_minus is None:
                return None

            # 二阶导数: d²G/dT² ≈ [G(T+ΔT) - 2*G(T) + G(T-ΔT)] / ΔT²
            d2G_dT2 = (G_plus - 2*G_T + G_minus) / (delta_T ** 2)
            Cp = -temperature * d2G_dT2

            return Cp
        except Exception as e:
            print(f"Warning: Failed to calculate heat capacity for {element}-{phase} at {temperature}K: {e}")
            return None

    def get_element_info(self, element: str) -> Optional[ElementData]:
        """
        获取元素基本信息

        Args:
            element: 元素符号

        Returns:
            ElementData对象
        """
        return self.elements.get(element.upper())

    def list_available_elements(self) -> List[str]:
        """返回所有可用元素的列表"""
        return sorted(list(self.elements.keys()))

    def list_available_functions(self, element: str = None) -> List[str]:
        """
        列出可用的函数

        Args:
            element: 如果指定，只返回该元素的函数

        Returns:
            函数名列表
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

    Returns:
        TDBParser实例
    """
    global _global_tdb_parser

    if _global_tdb_parser is None:
        # 查找TDB文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tdb_path = os.path.join(current_dir, '..', 'database', 'data', 'unary50.tdb')

        # 规范化路径
        tdb_path = os.path.normpath(tdb_path)

        if not os.path.exists(tdb_path):
            # 备用路径
            tdb_path = os.path.join(os.path.dirname(__file__), 'unary50.tdb')

        _global_tdb_parser = TDBParser(tdb_path)

    return _global_tdb_parser


# 测试代码
if __name__ == "__main__":
    # 测试TDB解析器
    parser = get_tdb_parser()

    print("=" * 60)
    print("TDB Parser Test")
    print("=" * 60)

    # 测试元素信息
    print("\n1. Element Information:")
    for elem in ['FE', 'AL', 'CU', 'NI']:
        info = parser.get_element_info(elem)
        if info:
            print(f"\n{elem}:")
            print(f"  Reference Phase: {info.reference_phase}")
            print(f"  Molar Mass: {info.molar_mass:.4f} g/mol")
            print(f"  H(298K): {info.reference_enthalpy:.2f} J/mol")
            print(f"  S(298K): {info.reference_entropy:.4f} J/(mol*K)")

    # 测试热力学性质计算
    print("\n2. Thermodynamic Properties at 1873K (1600°C):")
    test_elements = ['FE', 'AL', 'CU']
    T_test = 1873.0  # 1600°C

    for elem in test_elements:
        print(f"\n{elem}:")

        # 液相Gibbs能
        G_liq = parser.get_gibbs_energy(elem, 'LIQUID', T_test)
        if G_liq:
            print(f"  G(liquid, {T_test}K) = {G_liq:.2f} J/mol")

        # 固相Gibbs能（参考态）
        G_ser = parser.get_gibbs_energy(elem, 'SER', T_test)
        if G_ser:
            print(f"  G(SER, {T_test}K) = {G_ser:.2f} J/mol")

        # 焓
        H_liq = parser.get_enthalpy(elem, 'LIQUID', T_test)
        if H_liq:
            print(f"  H(liquid, {T_test}K) = {H_liq:.2f} J/mol")

        # 熵
        S_liq = parser.get_entropy(elem, 'LIQUID', T_test)
        if S_liq:
            print(f"  S(liquid, {T_test}K) = {S_liq:.4f} J/(mol*K)")

        # 热容
        Cp_liq = parser.get_heat_capacity(elem, 'LIQUID', T_test)
        if Cp_liq:
            print(f"  Cp(liquid, {T_test}K) = {Cp_liq:.4f} J/(mol*K)")

    print("\n" + "=" * 60)
    print(f"Total elements parsed: {len(parser.elements)}")
    print(f"Total functions parsed: {len(parser.functions)}")
    print("=" * 60)
