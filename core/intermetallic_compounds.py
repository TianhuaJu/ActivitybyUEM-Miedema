"""
Intermetallic Compounds Database
=================================
金属间化合物数据库

定义常见的金属间化合物及其化学计量比

作者: Claude
日期: 2025-11-23
"""

from typing import Dict, List, Tuple

class IntermetallicCompoundsDB:
    """金属间化合物数据库"""

    def __init__(self):
        # 定义常见的金属间化合物
        # 格式: 化合物名称 -> (元素1, 元素2, 化学计量比1, 化学计量比2)
        self.compounds = {
            # ===== Fe基化合物 =====
            'FE3C': ('FE', 'C', 3, 1),      # 渗碳体 (Cementite)
            'FE2SI': ('FE', 'SI', 2, 1),    # Fe2Si
            'FESI': ('FE', 'SI', 1, 1),     # FeSi
            'FE5SI3': ('FE', 'SI', 5, 3),   # Fe5Si3
            'FE3SI': ('FE', 'SI', 3, 1),    # Fe3Si
            'FE4N': ('FE', 'N', 4, 1),      # γ'-氮化铁
            'FE3MN': ('FE', 'MN', 3, 1),    # Fe3Mn
            'FECR': ('FE', 'CR', 1, 1),     # FeCr σ相

            # ===== Ni基化合物 =====
            'NI3AL': ('NI', 'AL', 3, 1),    # Ni3Al (γ'相)
            'NIAL': ('NI', 'AL', 1, 1),     # NiAl (β相)
            'NI3TI': ('NI', 'TI', 3, 1),    # Ni3Ti
            'NI3FE': ('NI', 'FE', 3, 1),    # Ni3Fe
            'NI3SI': ('NI', 'SI', 3, 1),    # Ni3Si

            # ===== Al基化合物 =====
            'AL3TI': ('AL', 'TI', 3, 1),    # Al3Ti
            'AL3FE': ('AL', 'FE', 3, 1),    # Al3Fe
            'AL3NI': ('AL', 'NI', 3, 1),    # Al3Ni
            'AL2CU': ('AL', 'CU', 2, 1),    # Al2Cu (θ相)

            # ===== Ti基化合物 =====
            'TI3AL': ('TI', 'AL', 3, 1),    # Ti3Al (α2相)
            'TIAL': ('TI', 'AL', 1, 1),     # TiAl (γ相)
            'TI2AL': ('TI', 'AL', 2, 1),    # Ti2Al
            'TI2NI': ('TI', 'NI', 2, 1),    # Ti2Ni
            'TINI': ('TI', 'NI', 1, 1),     # TiNi (形状记忆合金)

            # ===== Cu基化合物 =====
            'CU3AL': ('CU', 'AL', 3, 1),    # Cu3Al
            'CU9AL4': ('CU', 'AL', 9, 4),   # Cu9Al4 (β相)
            'CU3SN': ('CU', 'SN', 3, 1),    # Cu3Sn
            'CU6SN5': ('CU', 'SN', 6, 5),   # Cu6Sn5 (η相)

            # ===== 其他二元化合物 =====
            'MGZN2': ('MG', 'ZN', 1, 2),    # MgZn2 (Laves相)
            'MG2SI': ('MG', 'SI', 2, 1),    # Mg2Si
            'MNSI': ('MN', 'SI', 1, 1),     # MnSi
            'CRSI2': ('CR', 'SI', 1, 2),    # CrSi2
        }

        # 为快速查询，建立元素对 -> 化合物列表的映射
        self.element_pair_to_compounds = {}
        self._build_element_pair_index()

    def _build_element_pair_index(self):
        """建立元素对到化合物的索引"""
        for compound_name, (elem1, elem2, n1, n2) in self.compounds.items():
            # 标准化元素对（按字母顺序）
            pair = tuple(sorted([elem1, elem2]))

            if pair not in self.element_pair_to_compounds:
                self.element_pair_to_compounds[pair] = []

            self.element_pair_to_compounds[pair].append(compound_name)

    def get_possible_compounds(self, element1: str, element2: str) -> List[str]:
        """
        获取两个元素可能形成的金属间化合物

        参数:
            element1: 元素1
            element2: 元素2

        返回:
            化合物名称列表
        """
        elem1 = element1.upper()
        elem2 = element2.upper()

        pair = tuple(sorted([elem1, elem2]))

        return self.element_pair_to_compounds.get(pair, [])

    def get_compound_stoichiometry(self, compound_name: str) -> Tuple[str, str, int, int]:
        """
        获取化合物的化学计量比

        返回:
            (元素1, 元素2, 化学计量比1, 化学计量比2)
        """
        compound_name = compound_name.upper()

        if compound_name not in self.compounds:
            raise ValueError(f"未知的化合物: {compound_name}")

        return self.compounds[compound_name]

    def get_compound_composition(self, compound_name: str) -> Dict[str, float]:
        """
        获取化合物的摩尔分数组成

        例如: FE3C -> {'FE': 0.75, 'C': 0.25}

        返回:
            {元素: 摩尔分数}
        """
        elem1, elem2, n1, n2 = self.get_compound_stoichiometry(compound_name)

        total_moles = n1 + n2

        return {
            elem1: n1 / total_moles,
            elem2: n2 / total_moles
        }

    def get_all_compounds_for_element(self, element: str) -> List[str]:
        """
        获取包含指定元素的所有化合物

        参数:
            element: 元素符号

        返回:
            化合物名称列表
        """
        elem = element.upper()
        compounds = []

        for compound_name, (elem1, elem2, n1, n2) in self.compounds.items():
            if elem1 == elem or elem2 == elem:
                compounds.append(compound_name)

        return compounds

    def is_binary_compound(self, compound_name: str) -> bool:
        """判断是否为二元化合物"""
        return compound_name.upper() in self.compounds

    def get_compound_elements(self, compound_name: str) -> Tuple[str, str]:
        """
        获取化合物中的元素

        返回:
            (元素1, 元素2)
        """
        elem1, elem2, _, _ = self.get_compound_stoichiometry(compound_name)
        return elem1, elem2


# 全局实例
intermetallic_db = IntermetallicCompoundsDB()


if __name__ == "__main__":
    # 测试代码
    db = IntermetallicCompoundsDB()

    print("=== 金属间化合物数据库测试 ===\n")

    # 测试1: 查询Fe-C系统的化合物
    print("1. Fe-C系统的化合物:")
    compounds_fe_c = db.get_possible_compounds('Fe', 'C')
    print(f"   {compounds_fe_c}")
    for comp in compounds_fe_c:
        composition = db.get_compound_composition(comp)
        print(f"   {comp}: {composition}")

    print("\n2. Fe-Si系统的化合物:")
    compounds_fe_si = db.get_possible_compounds('Fe', 'Si')
    print(f"   {compounds_fe_si}")
    for comp in compounds_fe_si:
        composition = db.get_compound_composition(comp)
        print(f"   {comp}: {composition}")

    print("\n3. 包含Ti的所有化合物:")
    ti_compounds = db.get_all_compounds_for_element('Ti')
    print(f"   {ti_compounds}")

    print("\n4. Ni3Al的详细信息:")
    elem1, elem2, n1, n2 = db.get_compound_stoichiometry('NI3AL')
    print(f"   元素: {elem1}, {elem2}")
    print(f"   化学计量比: {n1}:{n2}")
    print(f"   摩尔分数: {db.get_compound_composition('NI3AL')}")
