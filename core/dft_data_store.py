# -*- coding: utf-8 -*-
"""
DFT 数据存储
=============
缓存 DFT 计算结果（化合物能量、固溶体能量、原子体积等），
供 Miedema 模型在计算液固相线、固溶度时优先使用。

存储: ~/.alloyact/dft_data.db (SQLite)

数据类型:
1. compound_energy  — 化合物形成能 ΔH_f (J/mol), ΔG(T) = A + B*T
2. mixing_enthalpy  — 固溶体混合焓 H_mix(x, T)
3. element_property — DFT 计算的元素参数（原子体积、体模量等）
4. endpoint_energy  — 端基相能量（纯元素不同结构的能量）
"""

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

_DB_DIR = os.path.join(os.path.expanduser("~"), ".alloyact")
_DB_PATH = os.path.join(_DB_DIR, "dft_data.db")


@dataclass
class CompoundEnergy:
    """化合物形成能数据"""
    compound_name: str          # 化合物名（如 "TiC", "Fe3C", "Ni3Al"）
    elements: Tuple[str, ...]   # 组成元素（如 ("Ti", "C")）
    stoichiometry: Tuple[int, ...]  # 化学计量数（如 (1, 1)）
    formation_energy_J: float   # 形成能 ΔH_f (J/mol-atom)
    delta_G_A: float = 0.0     # ΔG(T) = A + B*T 中的 A (J/mol)
    delta_G_B: float = 0.0     # ΔG(T) = A + B*T 中的 B (J/(mol·K))
    dft_engine: str = ""        # 计算用的 DFT 引擎
    xc_functional: str = "PBE"  # 交换关联泛函
    encut: float = 0.0          # 截断能 (eV)
    kpoints: str = ""           # K 点网格
    converged: bool = True      # 是否收敛
    total_energy_eV: float = 0.0  # DFT 总能量 (eV)
    energy_per_atom_eV: float = 0.0  # 每原子能量 (eV)
    source: str = "dft"         # 数据来源: "dft" / "literature" / "user"
    reference: str = ""         # 参考文献或 task_id
    notes: str = ""


@dataclass
class MixingEnthalpyPoint:
    """固溶体混合焓数据点"""
    system: str                 # 体系名（如 "Fe-C", "Ti-Al"）
    composition: Dict[str, float]  # 成分 {元素: 摩尔分数}
    temperature_K: float        # 温度 (K)
    mixing_enthalpy_J: float    # 混合焓 (J/mol)
    phase: str = "liquid"       # 相态: "liquid" / "solid" / "fcc" / "bcc"
    dft_engine: str = ""
    source: str = "dft"
    reference: str = ""


@dataclass
class ElementDFTProperty:
    """DFT 计算的元素参数"""
    element: str                # 元素符号
    structure: str              # 结构: "fcc", "bcc", "hcp"
    total_energy_eV: float      # 纯元素总能量 (eV/atom)
    lattice_constant_A: float = 0.0   # 晶格常数 (Å)
    atomic_volume_cm3: float = 0.0    # 原子体积 (cm³/mol)
    bulk_modulus_GPa: float = 0.0     # 体模量 (GPa)
    magnetic_moment: float = 0.0      # 磁矩 (μ_B)
    dft_engine: str = ""
    xc_functional: str = "PBE"
    source: str = "dft"


class DFTDataStore:
    """
    DFT 计算数据的本地缓存。

    存储化合物形成能、混合焓、元素参数等 DFT 计算结果，
    供 Miedema 模型优先使用，提升计算精度。
    """

    def __init__(self, db_path: str = None):
        self._db_path = db_path or _DB_PATH
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._init_db()

    # ==================== 数据库初始化 ====================

    def _init_db(self) -> None:
        """创建数据表"""
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS compound_energies (
                    compound_name TEXT PRIMARY KEY,
                    elements TEXT NOT NULL,
                    stoichiometry TEXT NOT NULL,
                    formation_energy_J REAL NOT NULL,
                    delta_G_A REAL DEFAULT 0,
                    delta_G_B REAL DEFAULT 0,
                    dft_engine TEXT DEFAULT '',
                    xc_functional TEXT DEFAULT 'PBE',
                    encut REAL DEFAULT 0,
                    kpoints TEXT DEFAULT '',
                    converged INTEGER DEFAULT 1,
                    total_energy_eV REAL DEFAULT 0,
                    energy_per_atom_eV REAL DEFAULT 0,
                    source TEXT DEFAULT 'dft',
                    reference TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    created_at REAL,
                    updated_at REAL
                );

                CREATE TABLE IF NOT EXISTS mixing_enthalpies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    system TEXT NOT NULL,
                    composition TEXT NOT NULL,
                    temperature_K REAL NOT NULL,
                    mixing_enthalpy_J REAL NOT NULL,
                    phase TEXT DEFAULT 'liquid',
                    dft_engine TEXT DEFAULT '',
                    source TEXT DEFAULT 'dft',
                    reference TEXT DEFAULT '',
                    created_at REAL,
                    UNIQUE(system, composition, temperature_K, phase)
                );

                CREATE TABLE IF NOT EXISTS element_properties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    element TEXT NOT NULL,
                    structure TEXT NOT NULL,
                    total_energy_eV REAL NOT NULL,
                    lattice_constant_A REAL DEFAULT 0,
                    atomic_volume_cm3 REAL DEFAULT 0,
                    bulk_modulus_GPa REAL DEFAULT 0,
                    magnetic_moment REAL DEFAULT 0,
                    dft_engine TEXT DEFAULT '',
                    xc_functional TEXT DEFAULT 'PBE',
                    source TEXT DEFAULT 'dft',
                    created_at REAL,
                    UNIQUE(element, structure, dft_engine)
                );

                CREATE INDEX IF NOT EXISTS idx_mixing_system
                    ON mixing_enthalpies(system);
                CREATE INDEX IF NOT EXISTS idx_elem_prop
                    ON element_properties(element, structure);
            """)
            conn.commit()

    # ==================== 化合物形成能 ====================

    def store_compound_energy(self, data: CompoundEnergy) -> None:
        """存储化合物形成能"""
        now = time.time()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO compound_energies
                (compound_name, elements, stoichiometry, formation_energy_J,
                 delta_G_A, delta_G_B, dft_engine, xc_functional, encut, kpoints,
                 converged, total_energy_eV, energy_per_atom_eV,
                 source, reference, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.compound_name,
                json.dumps(data.elements),
                json.dumps(data.stoichiometry),
                data.formation_energy_J,
                data.delta_G_A,
                data.delta_G_B,
                data.dft_engine,
                data.xc_functional,
                data.encut,
                data.kpoints,
                int(data.converged),
                data.total_energy_eV,
                data.energy_per_atom_eV,
                data.source,
                data.reference,
                data.notes,
                now, now,
            ))
            conn.commit()
        logger.info("已存储化合物形成能: %s (ΔH_f = %.0f J/mol)",
                     data.compound_name, data.formation_energy_J)

    def get_compound_energy(self, compound_name: str) -> Optional[CompoundEnergy]:
        """查询化合物形成能"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM compound_energies WHERE compound_name = ?",
                (compound_name,)
            ).fetchone()
        if not row:
            return None
        return CompoundEnergy(
            compound_name=row[0],
            elements=tuple(json.loads(row[1])),
            stoichiometry=tuple(json.loads(row[2])),
            formation_energy_J=row[3],
            delta_G_A=row[4],
            delta_G_B=row[5],
            dft_engine=row[6],
            xc_functional=row[7],
            encut=row[8],
            kpoints=row[9],
            converged=bool(row[10]),
            total_energy_eV=row[11],
            energy_per_atom_eV=row[12],
            source=row[13],
            reference=row[14],
            notes=row[15],
        )

    def get_compound_delta_G(self, compound_name: str,
                             temperature_K: float) -> Optional[float]:
        """
        获取化合物在指定温度下的 Gibbs 自由能。

        如果有 DFT 数据，使用 ΔG = A + B*T。
        如果只有形成能，使用 ΔG ≈ ΔH_f (忽略熵贡献)。

        返回:
            ΔG (J/mol)，无数据返回 None
        """
        data = self.get_compound_energy(compound_name)
        if data is None:
            return None

        if data.delta_G_A != 0 or data.delta_G_B != 0:
            return data.delta_G_A + data.delta_G_B * temperature_K
        else:
            return data.formation_energy_J

    def list_compounds(self, element_filter: str = None) -> List[Dict[str, Any]]:
        """列出所有化合物数据"""
        with sqlite3.connect(self._db_path) as conn:
            if element_filter:
                rows = conn.execute(
                    "SELECT compound_name, elements, stoichiometry, "
                    "formation_energy_J, delta_G_A, delta_G_B, source, dft_engine "
                    "FROM compound_energies WHERE elements LIKE ?",
                    (f'%"{element_filter}"%',)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT compound_name, elements, stoichiometry, "
                    "formation_energy_J, delta_G_A, delta_G_B, source, dft_engine "
                    "FROM compound_energies"
                ).fetchall()

        results = []
        for row in rows:
            results.append({
                "compound": row[0],
                "elements": json.loads(row[1]),
                "stoichiometry": json.loads(row[2]),
                "formation_energy_J": row[3],
                "delta_G_A": row[4],
                "delta_G_B": row[5],
                "source": row[6],
                "dft_engine": row[7],
            })
        return results

    # ==================== 混合焓 ====================

    def store_mixing_enthalpy(self, data: MixingEnthalpyPoint) -> None:
        """存储混合焓数据点"""
        now = time.time()
        comp_json = json.dumps(data.composition, sort_keys=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO mixing_enthalpies
                (system, composition, temperature_K, mixing_enthalpy_J,
                 phase, dft_engine, source, reference, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.system, comp_json, data.temperature_K,
                data.mixing_enthalpy_J, data.phase,
                data.dft_engine, data.source, data.reference, now,
            ))
            conn.commit()

    def get_mixing_enthalpy(self, system: str,
                            phase: str = None) -> List[Dict[str, Any]]:
        """查询某体系的所有混合焓数据"""
        with sqlite3.connect(self._db_path) as conn:
            if phase:
                rows = conn.execute(
                    "SELECT composition, temperature_K, mixing_enthalpy_J, "
                    "phase, source FROM mixing_enthalpies "
                    "WHERE system = ? AND phase = ? ORDER BY temperature_K",
                    (system, phase)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT composition, temperature_K, mixing_enthalpy_J, "
                    "phase, source FROM mixing_enthalpies "
                    "WHERE system = ? ORDER BY temperature_K",
                    (system,)
                ).fetchall()

        return [{
            "composition": json.loads(r[0]),
            "temperature_K": r[1],
            "mixing_enthalpy_J": r[2],
            "phase": r[3],
            "source": r[4],
        } for r in rows]

    # ==================== 元素参数 ====================

    def store_element_property(self, data: ElementDFTProperty) -> None:
        """存储 DFT 计算的元素参数"""
        now = time.time()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO element_properties
                (element, structure, total_energy_eV, lattice_constant_A,
                 atomic_volume_cm3, bulk_modulus_GPa, magnetic_moment,
                 dft_engine, xc_functional, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.element, data.structure, data.total_energy_eV,
                data.lattice_constant_A, data.atomic_volume_cm3,
                data.bulk_modulus_GPa, data.magnetic_moment,
                data.dft_engine, data.xc_functional, data.source, now,
            ))
            conn.commit()

    def get_element_property(self, element: str,
                             structure: str = None) -> List[Dict[str, Any]]:
        """查询元素 DFT 参数"""
        with sqlite3.connect(self._db_path) as conn:
            if structure:
                rows = conn.execute(
                    "SELECT * FROM element_properties "
                    "WHERE element = ? AND structure = ?",
                    (element, structure)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM element_properties WHERE element = ?",
                    (element,)
                ).fetchall()

        return [{
            "element": r[1], "structure": r[2],
            "total_energy_eV": r[3], "lattice_constant_A": r[4],
            "atomic_volume_cm3": r[5], "bulk_modulus_GPa": r[6],
            "magnetic_moment": r[7], "dft_engine": r[8],
            "xc_functional": r[9], "source": r[10],
        } for r in rows]

    # ==================== 从 DFT 结果自动导入 ====================

    def import_from_dft_result(self, dft_result: Dict[str, Any],
                               compound_name: str = None,
                               elements: Tuple[str, ...] = None,
                               stoichiometry: Tuple[int, ...] = None,
                               reference_energies: Dict[str, float] = None
                               ) -> Dict[str, Any]:
        """
        从 DFT 计算结果自动导入数据。

        参数:
            dft_result: DFT 适配器返回的结果字典
                        (包含 total_energy_eV, energy_per_atom_eV 等)
            compound_name: 化合物名称
            elements: 组成元素
            stoichiometry: 化学计量数
            reference_energies: 纯元素参考能量 {元素: eV/atom}
                                用于计算形成能

        返回:
            {"status": "success"/"error", "data_type": str, ...}
        """
        if dft_result.get("status") != "success":
            return {"status": "error",
                    "message": "DFT 计算结果状态不是 success"}

        total_e = dft_result.get("total_energy_eV")
        e_per_atom = dft_result.get("energy_per_atom_eV")

        if total_e is None and e_per_atom is None:
            return {"status": "error",
                    "message": "DFT 结果中无能量数据"}

        # 如果提供化合物信息 → 计算形成能
        if compound_name and elements and stoichiometry and reference_energies:
            # 形成能 = E_compound - Σ(n_i * E_i_ref)
            total_atoms = sum(stoichiometry)
            ref_energy_total = 0.0
            for elem, n in zip(elements, stoichiometry):
                ref_e = reference_energies.get(elem)
                if ref_e is None:
                    return {"status": "error",
                            "message": f"缺少 {elem} 的参考能量"}
                ref_energy_total += n * ref_e

            if e_per_atom is not None:
                compound_e_total = e_per_atom * total_atoms
            else:
                compound_e_total = total_e

            # eV → J/mol  (1 eV/atom = 96485 J/mol)
            eV_to_J_per_mol = 96485.0
            formation_energy_eV = (compound_e_total - ref_energy_total) / total_atoms
            formation_energy_J = formation_energy_eV * eV_to_J_per_mol

            data = CompoundEnergy(
                compound_name=compound_name,
                elements=elements,
                stoichiometry=stoichiometry,
                formation_energy_J=formation_energy_J,
                delta_G_A=formation_energy_J,  # 近似: ΔG ≈ ΔH
                delta_G_B=0.0,  # 熵项需要声子计算
                dft_engine=dft_result.get("engine", ""),
                total_energy_eV=total_e or 0,
                energy_per_atom_eV=e_per_atom or 0,
                converged=dft_result.get("converged", True),
                source="dft",
                reference=dft_result.get("task_id", ""),
            )
            self.store_compound_energy(data)

            return {
                "status": "success",
                "data_type": "compound_energy",
                "compound": compound_name,
                "formation_energy_J": formation_energy_J,
                "formation_energy_kJ": formation_energy_J / 1000,
                "formation_energy_eV_atom": formation_energy_eV,
                "message": f"已导入 {compound_name} 的形成能: "
                           f"{formation_energy_J:.0f} J/mol "
                           f"({formation_energy_J/1000:.1f} kJ/mol)",
            }

        # 没有化合物信息 → 存储为元素参数
        elif elements and len(elements) == 1:
            elem = elements[0]
            structure = dft_result.get("structure", "unknown")
            prop = ElementDFTProperty(
                element=elem,
                structure=structure,
                total_energy_eV=e_per_atom or total_e or 0,
                dft_engine=dft_result.get("engine", ""),
                source="dft",
            )
            self.store_element_property(prop)
            return {
                "status": "success",
                "data_type": "element_property",
                "element": elem,
                "energy_eV": e_per_atom or total_e,
            }

        return {"status": "error",
                "message": "请提供化合物名、元素和计量数，或单元素信息"}

    # ==================== 统计与查询 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        with sqlite3.connect(self._db_path) as conn:
            n_compounds = conn.execute(
                "SELECT COUNT(*) FROM compound_energies"
            ).fetchone()[0]
            n_mixing = conn.execute(
                "SELECT COUNT(*) FROM mixing_enthalpies"
            ).fetchone()[0]
            n_elements = conn.execute(
                "SELECT COUNT(DISTINCT element) FROM element_properties"
            ).fetchone()[0]

            sources = conn.execute(
                "SELECT source, COUNT(*) FROM compound_energies GROUP BY source"
            ).fetchall()

        return {
            "compound_count": n_compounds,
            "mixing_enthalpy_points": n_mixing,
            "element_count": n_elements,
            "sources": {s[0]: s[1] for s in sources},
            "db_path": self._db_path,
        }
