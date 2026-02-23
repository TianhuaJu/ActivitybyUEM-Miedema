#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
化合物热力学数据库模块

该模块创建和管理化合物热力学数据的SQLite数据库。
包含碳化物、氮化物、氧化物、硫化物等析出相的热力学数据。

Author: AlloyAct Pro Team
Date: 2024
"""

import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json

# 数据库文件路径
DATABASE_PATH = Path(__file__).parent / "data" / "compounds.db"


def get_database_path() -> Path:
    """获取数据库文件路径"""
    return DATABASE_PATH


def init_database(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    初始化化合物数据库

    Parameters:
        db_path: 数据库路径，默认为 database/data/compounds.db

    Returns:
        sqlite3.Connection: 数据库连接对象
    """
    if db_path is None:
        db_path = DATABASE_PATH

    # 确保目录存在
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 创建表结构
    _create_tables(conn)

    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    """创建数据库表结构"""
    cursor = conn.cursor()

    # 1. 化合物热力学数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compound_thermodynamics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compound_formula TEXT NOT NULL UNIQUE,
            compound_name TEXT,
            compound_type TEXT NOT NULL,  -- carbide, nitride, oxide, sulfide, intermetallic
            metal_element TEXT NOT NULL,
            nonmetal_element TEXT NOT NULL,
            metal_stoichiometry INTEGER NOT NULL DEFAULT 1,
            nonmetal_stoichiometry INTEGER NOT NULL DEFAULT 1,
            crystal_structure TEXT,
            space_group TEXT,
            lattice_parameter_a REAL,
            lattice_parameter_b REAL,
            lattice_parameter_c REAL,
            molar_volume REAL,  -- cm³/mol
            density REAL,  -- g/cm³
            melting_point REAL,  -- K
            delta_gf_A REAL NOT NULL,  -- ΔG°f = A + B*T (J/mol), A项
            delta_gf_B REAL NOT NULL,  -- ΔG°f = A + B*T (J/mol), B项
            delta_gf_C REAL DEFAULT 0,  -- ΔG°f = A + B*T + C*T*ln(T) (J/mol), C项
            delta_hf_298 REAL,  -- 标准生成焓 (J/mol)
            delta_sf_298 REAL,  -- 标准生成熵 (J/mol/K)
            cp_A REAL,  -- Cp = A + B*T + C/T² (J/mol/K)
            cp_B REAL,
            cp_C REAL,
            T_min REAL DEFAULT 298.15,  -- 有效温度范围下限 (K)
            T_max REAL DEFAULT 2000,  -- 有效温度范围上限 (K)
            data_source TEXT,
            reference TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. 溶解度积数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS solubility_product (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compound_formula TEXT NOT NULL,
            matrix_phase TEXT NOT NULL,  -- FCC, BCC, HCP, Liquid
            matrix_base TEXT DEFAULT 'Fe',  -- 基体元素
            log_ksp_A REAL NOT NULL,  -- log(Ksp) = A/T + B + C*ln(T)
            log_ksp_B REAL NOT NULL DEFAULT 0,
            log_ksp_C REAL DEFAULT 0,
            ksp_unit TEXT DEFAULT 'wt_pct',  -- wt_pct 或 mole_frac
            T_min REAL DEFAULT 800,
            T_max REAL DEFAULT 2000,
            data_source TEXT,
            reference TEXT,
            notes TEXT,
            UNIQUE(compound_formula, matrix_phase, matrix_base)
        )
    ''')

    # 3. 二元相图数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS binary_phase_diagram (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            element_A TEXT NOT NULL,
            element_B TEXT NOT NULL,
            diagram_type TEXT,  -- eutectic, peritectic, isomorphous, etc.
            liquidus_data TEXT,  -- JSON格式的液相线数据
            solidus_data TEXT,  -- JSON格式的固相线数据
            solvus_data TEXT,  -- JSON格式的溶解度线数据
            invariant_reactions TEXT,  -- JSON格式的不变反应数据
            data_source TEXT,
            reference TEXT,
            UNIQUE(element_A, element_B)
        )
    ''')

    # 4. 实验溶解度数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS experimental_solubility (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            solute_element TEXT NOT NULL,
            matrix_element TEXT NOT NULL,
            matrix_phase TEXT NOT NULL,
            temperature REAL NOT NULL,  -- K
            solubility_wt_pct REAL,
            solubility_at_pct REAL,
            measurement_method TEXT,
            uncertainty REAL,
            data_source TEXT,
            reference TEXT,
            year INTEGER
        )
    ''')

    # 5. 格点稳定性数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lattice_stability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            element TEXT NOT NULL,
            phase TEXT NOT NULL,  -- FCC, BCC, HCP, Liquid
            G_ref_A REAL NOT NULL,  -- G - G_SER = A + B*T + C*T*ln(T) + D*T²
            G_ref_B REAL DEFAULT 0,
            G_ref_C REAL DEFAULT 0,
            G_ref_D REAL DEFAULT 0,
            T_min REAL DEFAULT 298.15,
            T_max REAL DEFAULT 6000,
            data_source TEXT DEFAULT 'SGTE',
            reference TEXT,
            UNIQUE(element, phase)
        )
    ''')

    # 6. Wagner相互作用系数表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wagner_interaction (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            solvent TEXT NOT NULL,  -- 溶剂元素 (如 Fe)
            solute_i TEXT NOT NULL,  -- 溶质i
            solute_j TEXT NOT NULL,  -- 溶质j (可以等于i)
            phase TEXT NOT NULL,  -- FCC, BCC, Liquid
            epsilon_ij_A REAL NOT NULL,  -- ε_ij = A + B/T
            epsilon_ij_B REAL DEFAULT 0,
            T_min REAL DEFAULT 800,
            T_max REAL DEFAULT 2000,
            data_source TEXT,
            reference TEXT,
            UNIQUE(solvent, solute_i, solute_j, phase)
        )
    ''')

    conn.commit()


def populate_sample_data(conn: sqlite3.Connection) -> None:
    """
    填充示例化合物数据

    数据来源：
    - SGTE纯物质数据库
    - Turkdogan, Physical Chemistry of High Temperature Technology
    - Barin, Thermochemical Data of Pure Substances
    - Uhrenius, Calculation of Phase Equilibria
    """
    cursor = conn.cursor()

    # ==================== 碳化物数据 ====================
    carbide_data = [
        # TiC - 碳化钛
        {
            'compound_formula': 'TiC',
            'compound_name': 'Titanium Carbide',
            'compound_type': 'carbide',
            'metal_element': 'Ti',
            'nonmetal_element': 'C',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'NaCl (B1)',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 4.327,
            'molar_volume': 12.18,
            'density': 4.93,
            'melting_point': 3340,
            'delta_gf_A': -184000,
            'delta_gf_B': 22.0,
            'delta_hf_298': -184000,
            'delta_sf_298': -22.0,
            'cp_A': 48.97,
            'cp_B': 0.00234,
            'cp_C': -795000,
            'T_min': 298.15,
            'T_max': 3000,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995, SGTE 2014'
        },
        # NbC - 碳化铌
        {
            'compound_formula': 'NbC',
            'compound_name': 'Niobium Carbide',
            'compound_type': 'carbide',
            'metal_element': 'Nb',
            'nonmetal_element': 'C',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'NaCl (B1)',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 4.469,
            'molar_volume': 13.46,
            'density': 7.78,
            'melting_point': 3773,
            'delta_gf_A': -138000,
            'delta_gf_B': 15.0,
            'delta_hf_298': -138000,
            'delta_sf_298': -15.0,
            'cp_A': 52.6,
            'cp_B': 0.0012,
            'cp_C': -750000,
            'T_min': 298.15,
            'T_max': 3500,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995, SGTE 2014'
        },
        # VC - 碳化钒
        {
            'compound_formula': 'VC',
            'compound_name': 'Vanadium Carbide',
            'compound_type': 'carbide',
            'metal_element': 'V',
            'nonmetal_element': 'C',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'NaCl (B1)',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 4.165,
            'molar_volume': 10.87,
            'density': 5.77,
            'melting_point': 3083,
            'delta_gf_A': -102000,
            'delta_gf_B': 13.0,
            'delta_hf_298': -102000,
            'delta_sf_298': -13.0,
            'cp_A': 46.5,
            'cp_B': 0.0025,
            'cp_C': -680000,
            'T_min': 298.15,
            'T_max': 2800,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995'
        },
        # Fe3C - 渗碳体
        {
            'compound_formula': 'Fe3C',
            'compound_name': 'Cementite',
            'compound_type': 'carbide',
            'metal_element': 'Fe',
            'nonmetal_element': 'C',
            'metal_stoichiometry': 3,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'Orthorhombic',
            'space_group': 'Pnma',
            'lattice_parameter_a': 5.091,
            'lattice_parameter_b': 6.743,
            'lattice_parameter_c': 4.526,
            'molar_volume': 23.33,
            'density': 7.69,
            'melting_point': 1523,
            'delta_gf_A': 11369,
            'delta_gf_B': 10.4,
            'delta_hf_298': 25100,
            'delta_sf_298': -28.5,
            'cp_A': 105.0,
            'cp_B': 0.022,
            'cp_C': -1200000,
            'T_min': 298.15,
            'T_max': 1500,
            'data_source': 'SGTE',
            'reference': 'SGTE 2014, Hillert 1985'
        },
        # Cr7C3 - 铬碳化物
        {
            'compound_formula': 'Cr7C3',
            'compound_name': 'Chromium Carbide (Cr7C3)',
            'compound_type': 'carbide',
            'metal_element': 'Cr',
            'nonmetal_element': 'C',
            'metal_stoichiometry': 7,
            'nonmetal_stoichiometry': 3,
            'crystal_structure': 'Orthorhombic',
            'space_group': 'Pnma',
            'lattice_parameter_a': 4.526,
            'lattice_parameter_b': 7.010,
            'lattice_parameter_c': 12.142,
            'molar_volume': 58.0,
            'density': 6.92,
            'melting_point': 2036,
            'delta_gf_A': -155000,
            'delta_gf_B': 45.0,
            'delta_hf_298': -155000,
            'delta_sf_298': -45.0,
            'cp_A': 420.0,
            'cp_B': 0.05,
            'cp_C': -3000000,
            'T_min': 298.15,
            'T_max': 1800,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995, Hillert 1999'
        },
        # Cr23C6
        {
            'compound_formula': 'Cr23C6',
            'compound_name': 'Chromium Carbide (Cr23C6)',
            'compound_type': 'carbide',
            'metal_element': 'Cr',
            'nonmetal_element': 'C',
            'metal_stoichiometry': 23,
            'nonmetal_stoichiometry': 6,
            'crystal_structure': 'FCC',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 10.659,
            'molar_volume': 180.0,
            'density': 6.97,
            'melting_point': 1793,
            'delta_gf_A': -335000,
            'delta_gf_B': 95.0,
            'delta_hf_298': -350000,
            'delta_sf_298': -95.0,
            'cp_A': 1100.0,
            'cp_B': 0.12,
            'cp_C': -8000000,
            'T_min': 298.15,
            'T_max': 1700,
            'data_source': 'SGTE',
            'reference': 'SGTE 2014, Hillert 1999'
        },
        # Mo2C
        {
            'compound_formula': 'Mo2C',
            'compound_name': 'Molybdenum Carbide',
            'compound_type': 'carbide',
            'metal_element': 'Mo',
            'nonmetal_element': 'C',
            'metal_stoichiometry': 2,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'Hexagonal',
            'space_group': 'P63/mmc',
            'lattice_parameter_a': 3.002,
            'lattice_parameter_c': 4.724,
            'molar_volume': 25.5,
            'density': 9.18,
            'melting_point': 2960,
            'delta_gf_A': -46000,
            'delta_gf_B': 8.0,
            'delta_hf_298': -46000,
            'delta_sf_298': -8.0,
            'cp_A': 70.0,
            'cp_B': 0.008,
            'cp_C': -900000,
            'T_min': 298.15,
            'T_max': 2800,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995'
        },
        # WC
        {
            'compound_formula': 'WC',
            'compound_name': 'Tungsten Carbide',
            'compound_type': 'carbide',
            'metal_element': 'W',
            'nonmetal_element': 'C',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'Hexagonal',
            'space_group': 'P-6m2',
            'lattice_parameter_a': 2.906,
            'lattice_parameter_c': 2.837,
            'molar_volume': 15.6,
            'density': 15.63,
            'melting_point': 3143,
            'delta_gf_A': -38000,
            'delta_gf_B': 6.5,
            'delta_hf_298': -38000,
            'delta_sf_298': -6.5,
            'cp_A': 40.0,
            'cp_B': 0.003,
            'cp_C': -500000,
            'T_min': 298.15,
            'T_max': 3000,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995'
        },
    ]

    # ==================== 氮化物数据 ====================
    nitride_data = [
        # TiN - 氮化钛
        {
            'compound_formula': 'TiN',
            'compound_name': 'Titanium Nitride',
            'compound_type': 'nitride',
            'metal_element': 'Ti',
            'nonmetal_element': 'N',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'NaCl (B1)',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 4.241,
            'molar_volume': 11.52,
            'density': 5.40,
            'melting_point': 3223,
            'delta_gf_A': -337000,
            'delta_gf_B': 93.0,
            'delta_hf_298': -337000,
            'delta_sf_298': -93.0,
            'cp_A': 49.5,
            'cp_B': 0.002,
            'cp_C': -850000,
            'T_min': 298.15,
            'T_max': 3000,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995, Frisk 2003'
        },
        # AlN - 氮化铝
        {
            'compound_formula': 'AlN',
            'compound_name': 'Aluminum Nitride',
            'compound_type': 'nitride',
            'metal_element': 'Al',
            'nonmetal_element': 'N',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'Wurtzite',
            'space_group': 'P63mc',
            'lattice_parameter_a': 3.111,
            'lattice_parameter_c': 4.978,
            'molar_volume': 12.6,
            'density': 3.26,
            'melting_point': 2473,
            'delta_gf_A': -287000,
            'delta_gf_B': 79.0,
            'delta_hf_298': -318000,
            'delta_sf_298': -79.0,
            'cp_A': 45.0,
            'cp_B': 0.003,
            'cp_C': -600000,
            'T_min': 298.15,
            'T_max': 2400,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995, Hillert 1991'
        },
        # VN - 氮化钒
        {
            'compound_formula': 'VN',
            'compound_name': 'Vanadium Nitride',
            'compound_type': 'nitride',
            'metal_element': 'V',
            'nonmetal_element': 'N',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'NaCl (B1)',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 4.139,
            'molar_volume': 10.64,
            'density': 6.13,
            'melting_point': 2593,
            'delta_gf_A': -191000,
            'delta_gf_B': 52.0,
            'delta_hf_298': -217000,
            'delta_sf_298': -52.0,
            'cp_A': 48.0,
            'cp_B': 0.0025,
            'cp_C': -720000,
            'T_min': 298.15,
            'T_max': 2500,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995'
        },
        # CrN - 氮化铬
        {
            'compound_formula': 'CrN',
            'compound_name': 'Chromium Nitride',
            'compound_type': 'nitride',
            'metal_element': 'Cr',
            'nonmetal_element': 'N',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'NaCl (B1)',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 4.148,
            'molar_volume': 10.73,
            'density': 6.14,
            'melting_point': 1773,
            'delta_gf_A': -105000,
            'delta_gf_B': 26.0,
            'delta_hf_298': -117000,
            'delta_sf_298': -26.0,
            'cp_A': 47.0,
            'cp_B': 0.003,
            'cp_C': -650000,
            'T_min': 298.15,
            'T_max': 1700,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995, Frisk 1991'
        },
        # BN - 氮化硼
        {
            'compound_formula': 'BN',
            'compound_name': 'Boron Nitride (Hexagonal)',
            'compound_type': 'nitride',
            'metal_element': 'B',
            'nonmetal_element': 'N',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'Hexagonal',
            'space_group': 'P63/mmc',
            'lattice_parameter_a': 2.504,
            'lattice_parameter_c': 6.661,
            'molar_volume': 10.9,
            'density': 2.28,
            'melting_point': 3273,
            'delta_gf_A': -227000,
            'delta_gf_B': 45.0,
            'delta_hf_298': -254000,
            'delta_sf_298': -45.0,
            'cp_A': 40.0,
            'cp_B': 0.015,
            'cp_C': -400000,
            'T_min': 298.15,
            'T_max': 3000,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995'
        },
        # NbN - 氮化铌
        {
            'compound_formula': 'NbN',
            'compound_name': 'Niobium Nitride',
            'compound_type': 'nitride',
            'metal_element': 'Nb',
            'nonmetal_element': 'N',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'NaCl (B1)',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 4.392,
            'molar_volume': 12.80,
            'density': 8.47,
            'melting_point': 2573,
            'delta_gf_A': -220000,
            'delta_gf_B': 58.0,
            'delta_hf_298': -235000,
            'delta_sf_298': -58.0,
            'cp_A': 51.0,
            'cp_B': 0.002,
            'cp_C': -800000,
            'T_min': 298.15,
            'T_max': 2500,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995'
        },
    ]

    # ==================== 氧化物数据 ====================
    oxide_data = [
        # Al2O3 - 氧化铝
        {
            'compound_formula': 'Al2O3',
            'compound_name': 'Aluminum Oxide (Corundum)',
            'compound_type': 'oxide',
            'metal_element': 'Al',
            'nonmetal_element': 'O',
            'metal_stoichiometry': 2,
            'nonmetal_stoichiometry': 3,
            'crystal_structure': 'Corundum',
            'space_group': 'R-3c',
            'lattice_parameter_a': 4.761,
            'lattice_parameter_c': 12.991,
            'molar_volume': 25.58,
            'density': 3.99,
            'melting_point': 2327,
            'delta_gf_A': -1675700,
            'delta_gf_B': 313.0,
            'delta_hf_298': -1675700,
            'delta_sf_298': -313.0,
            'cp_A': 115.0,
            'cp_B': 0.012,
            'cp_C': -3500000,
            'T_min': 298.15,
            'T_max': 2200,
            'data_source': 'SGTE, Barin, JANAF',
            'reference': 'JANAF 1998, Barin 1995'
        },
        # SiO2 - 二氧化硅
        {
            'compound_formula': 'SiO2',
            'compound_name': 'Silicon Dioxide (Quartz)',
            'compound_type': 'oxide',
            'metal_element': 'Si',
            'nonmetal_element': 'O',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 2,
            'crystal_structure': 'Hexagonal (α-Quartz)',
            'space_group': 'P3121',
            'lattice_parameter_a': 4.913,
            'lattice_parameter_c': 5.405,
            'molar_volume': 22.69,
            'density': 2.65,
            'melting_point': 1996,
            'delta_gf_A': -910700,
            'delta_gf_B': 175.0,
            'delta_hf_298': -910700,
            'delta_sf_298': -175.0,
            'cp_A': 75.0,
            'cp_B': 0.006,
            'cp_C': -1800000,
            'T_min': 298.15,
            'T_max': 1900,
            'data_source': 'SGTE, Barin, JANAF',
            'reference': 'JANAF 1998, Barin 1995'
        },
        # MnO - 氧化锰
        {
            'compound_formula': 'MnO',
            'compound_name': 'Manganese(II) Oxide',
            'compound_type': 'oxide',
            'metal_element': 'Mn',
            'nonmetal_element': 'O',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'NaCl (B1)',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 4.445,
            'molar_volume': 13.22,
            'density': 5.37,
            'melting_point': 2115,
            'delta_gf_A': -385000,
            'delta_gf_B': 73.0,
            'delta_hf_298': -385000,
            'delta_sf_298': -73.0,
            'cp_A': 48.0,
            'cp_B': 0.005,
            'cp_C': -600000,
            'T_min': 298.15,
            'T_max': 2000,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995'
        },
        # FeO - 氧化亚铁
        {
            'compound_formula': 'FeO',
            'compound_name': 'Iron(II) Oxide (Wüstite)',
            'compound_type': 'oxide',
            'metal_element': 'Fe',
            'nonmetal_element': 'O',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'NaCl (B1)',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 4.307,
            'molar_volume': 12.00,
            'density': 5.99,
            'melting_point': 1650,
            'delta_gf_A': -264000,
            'delta_gf_B': 65.0,
            'delta_hf_298': -272000,
            'delta_sf_298': -65.0,
            'cp_A': 52.0,
            'cp_B': 0.006,
            'cp_C': -500000,
            'T_min': 298.15,
            'T_max': 1600,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995, Sundman 1991'
        },
        # TiO2 - 二氧化钛
        {
            'compound_formula': 'TiO2',
            'compound_name': 'Titanium Dioxide (Rutile)',
            'compound_type': 'oxide',
            'metal_element': 'Ti',
            'nonmetal_element': 'O',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 2,
            'crystal_structure': 'Rutile',
            'space_group': 'P42/mnm',
            'lattice_parameter_a': 4.594,
            'lattice_parameter_c': 2.958,
            'molar_volume': 18.82,
            'density': 4.25,
            'melting_point': 2116,
            'delta_gf_A': -944000,
            'delta_gf_B': 185.0,
            'delta_hf_298': -944000,
            'delta_sf_298': -185.0,
            'cp_A': 75.0,
            'cp_B': 0.008,
            'cp_C': -1600000,
            'T_min': 298.15,
            'T_max': 2000,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995'
        },
    ]

    # ==================== 硫化物数据 ====================
    sulfide_data = [
        # MnS - 硫化锰
        {
            'compound_formula': 'MnS',
            'compound_name': 'Manganese Sulfide',
            'compound_type': 'sulfide',
            'metal_element': 'Mn',
            'nonmetal_element': 'S',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'NaCl (B1)',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 5.224,
            'molar_volume': 21.4,
            'density': 4.05,
            'melting_point': 1883,
            'delta_gf_A': -214600,
            'delta_gf_B': 64.0,
            'delta_hf_298': -214600,
            'delta_sf_298': -64.0,
            'cp_A': 50.0,
            'cp_B': 0.004,
            'cp_C': -600000,
            'T_min': 298.15,
            'T_max': 1800,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995, Ohtani 1984'
        },
        # CaS - 硫化钙
        {
            'compound_formula': 'CaS',
            'compound_name': 'Calcium Sulfide',
            'compound_type': 'sulfide',
            'metal_element': 'Ca',
            'nonmetal_element': 'S',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'NaCl (B1)',
            'space_group': 'Fm-3m',
            'lattice_parameter_a': 5.689,
            'molar_volume': 27.6,
            'density': 2.59,
            'melting_point': 2798,
            'delta_gf_A': -473200,
            'delta_gf_B': 97.0,
            'delta_hf_298': -473200,
            'delta_sf_298': -97.0,
            'cp_A': 47.0,
            'cp_B': 0.005,
            'cp_C': -500000,
            'T_min': 298.15,
            'T_max': 2700,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995'
        },
        # FeS - 硫化亚铁
        {
            'compound_formula': 'FeS',
            'compound_name': 'Iron Sulfide (Troilite)',
            'compound_type': 'sulfide',
            'metal_element': 'Fe',
            'nonmetal_element': 'S',
            'metal_stoichiometry': 1,
            'nonmetal_stoichiometry': 1,
            'crystal_structure': 'Hexagonal (NiAs)',
            'space_group': 'P63/mmc',
            'lattice_parameter_a': 3.438,
            'lattice_parameter_c': 5.877,
            'molar_volume': 18.2,
            'density': 4.84,
            'melting_point': 1463,
            'delta_gf_A': -101000,
            'delta_gf_B': 60.0,
            'delta_hf_298': -101000,
            'delta_sf_298': -60.0,
            'cp_A': 52.0,
            'cp_B': 0.008,
            'cp_C': -700000,
            'T_min': 298.15,
            'T_max': 1400,
            'data_source': 'SGTE, Barin',
            'reference': 'Barin 1995, Ohtani 1984'
        },
    ]

    # 合并所有化合物数据
    all_compound_data = carbide_data + nitride_data + oxide_data + sulfide_data

    # 插入化合物热力学数据
    for compound in all_compound_data:
        columns = ', '.join(compound.keys())
        placeholders = ', '.join(['?' for _ in compound])
        sql = f'INSERT OR REPLACE INTO compound_thermodynamics ({columns}) VALUES ({placeholders})'
        cursor.execute(sql, list(compound.values()))

    # ==================== 溶解度积数据 ====================
    solubility_product_data = [
        # FCC-Fe (奥氏体) 中的溶解度积
        {'compound_formula': 'TiC', 'matrix_phase': 'FCC', 'matrix_base': 'Fe',
         'log_ksp_A': -7000, 'log_ksp_B': -2.75, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Irvine 1967', 'reference': 'Irvine et al., JISI 205 (1967) 161'},
        {'compound_formula': 'NbC', 'matrix_phase': 'FCC', 'matrix_base': 'Fe',
         'log_ksp_A': -6770, 'log_ksp_B': -2.26, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Narita 1975', 'reference': 'Narita, Trans. ISIJ 15 (1975) 145'},
        {'compound_formula': 'VC', 'matrix_phase': 'FCC', 'matrix_base': 'Fe',
         'log_ksp_A': -6560, 'log_ksp_B': -4.45, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Narita 1975', 'reference': 'Narita, Trans. ISIJ 15 (1975) 145'},
        {'compound_formula': 'TiN', 'matrix_phase': 'FCC', 'matrix_base': 'Fe',
         'log_ksp_A': -15790, 'log_ksp_B': -5.40, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Morita 1987', 'reference': 'Morita & Kunisada, Trans. ISIJ 17 (1977) 479'},
        {'compound_formula': 'VN', 'matrix_phase': 'FCC', 'matrix_base': 'Fe',
         'log_ksp_A': -7700, 'log_ksp_B': -2.86, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Narita 1975', 'reference': 'Narita, Trans. ISIJ 15 (1975) 145'},
        {'compound_formula': 'AlN', 'matrix_phase': 'FCC', 'matrix_base': 'Fe',
         'log_ksp_A': -7184, 'log_ksp_B': -1.79, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Leslie 1971', 'reference': 'Leslie et al., Trans. ASM 46 (1954) 1470'},
        {'compound_formula': 'NbN', 'matrix_phase': 'FCC', 'matrix_base': 'Fe',
         'log_ksp_A': -10230, 'log_ksp_B': -3.40, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Narita 1975', 'reference': 'Narita, Trans. ISIJ 15 (1975) 145'},

        # BCC-Fe (铁素体) 中的溶解度积
        {'compound_formula': 'TiC', 'matrix_phase': 'BCC', 'matrix_base': 'Fe',
         'log_ksp_A': -10475, 'log_ksp_B': -4.06, 'T_min': 773, 'T_max': 1173,
         'data_source': 'Turkdogan 1989', 'reference': 'Turkdogan, Physical Chemistry of High Temperature Technology'},
        {'compound_formula': 'NbC', 'matrix_phase': 'BCC', 'matrix_base': 'Fe',
         'log_ksp_A': -9830, 'log_ksp_B': -3.90, 'T_min': 773, 'T_max': 1173,
         'data_source': 'Turkdogan 1989', 'reference': 'Turkdogan, Physical Chemistry of High Temperature Technology'},
        {'compound_formula': 'VC', 'matrix_phase': 'BCC', 'matrix_base': 'Fe',
         'log_ksp_A': -9500, 'log_ksp_B': -6.72, 'T_min': 773, 'T_max': 1173,
         'data_source': 'Turkdogan 1989', 'reference': 'Turkdogan, Physical Chemistry of High Temperature Technology'},
        {'compound_formula': 'MnS', 'matrix_phase': 'BCC', 'matrix_base': 'Fe',
         'log_ksp_A': -8200, 'log_ksp_B': -4.50, 'T_min': 773, 'T_max': 1173,
         'data_source': 'Ohtani 1984', 'reference': 'Ohtani & Hillert, CALPHAD 8 (1984) 189'},

        # 液相 (Liquid) 中的溶解度积
        {'compound_formula': 'TiC', 'matrix_phase': 'Liquid', 'matrix_base': 'Fe',
         'log_ksp_A': -5070, 'log_ksp_B': -1.05, 'T_min': 1773, 'T_max': 2173,
         'data_source': 'Turkdogan 1989', 'reference': 'Turkdogan, Physical Chemistry of High Temperature Technology'},
        {'compound_formula': 'TiN', 'matrix_phase': 'Liquid', 'matrix_base': 'Fe',
         'log_ksp_A': -14400, 'log_ksp_B': -4.94, 'T_min': 1773, 'T_max': 2173,
         'data_source': 'Turkdogan 1989', 'reference': 'Turkdogan, Physical Chemistry of High Temperature Technology'},
        {'compound_formula': 'Al2O3', 'matrix_phase': 'Liquid', 'matrix_base': 'Fe',
         'log_ksp_A': -62680, 'log_ksp_B': -20.5, 'T_min': 1773, 'T_max': 2173,
         'data_source': 'Sigworth 1974', 'reference': 'Sigworth & Elliott, Met. Sci. 8 (1974) 298'},
    ]

    for ksp in solubility_product_data:
        columns = ', '.join(ksp.keys())
        placeholders = ', '.join(['?' for _ in ksp])
        sql = f'INSERT OR REPLACE INTO solubility_product ({columns}) VALUES ({placeholders})'
        cursor.execute(sql, list(ksp.values()))

    # ==================== 格点稳定性数据 (SGTE) ====================
    lattice_stability_data = [
        # Fe 的格点稳定性
        {'element': 'Fe', 'phase': 'BCC', 'G_ref_A': 0, 'G_ref_B': 0, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 1811, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},
        {'element': 'Fe', 'phase': 'FCC', 'G_ref_A': -1462.4, 'G_ref_B': 8.282, 'G_ref_C': -1.15, 'G_ref_D': 0.00064,
         'T_min': 298.15, 'T_max': 1811, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},
        {'element': 'Fe', 'phase': 'HCP', 'G_ref_A': -3705.78, 'G_ref_B': 12.591, 'G_ref_C': -1.15, 'G_ref_D': 0.00064,
         'T_min': 298.15, 'T_max': 1811, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},
        {'element': 'Fe', 'phase': 'Liquid', 'G_ref_A': 12040.17, 'G_ref_B': -6.55, 'G_ref_C': -0.4723, 'G_ref_D': -0.00000439,
         'T_min': 298.15, 'T_max': 6000, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},

        # C 的格点稳定性 (在金属相中的假想参考态)
        {'element': 'C', 'phase': 'FCC', 'G_ref_A': 50000, 'G_ref_B': 0, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 6000, 'data_source': 'SGTE', 'reference': 'Gustafson 1985'},
        {'element': 'C', 'phase': 'BCC', 'G_ref_A': 80000, 'G_ref_B': 0, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 6000, 'data_source': 'SGTE', 'reference': 'Gustafson 1985'},

        # N 的格点稳定性 (在金属相中的假想参考态)
        {'element': 'N', 'phase': 'FCC', 'G_ref_A': 45000, 'G_ref_B': 0, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 6000, 'data_source': 'SGTE', 'reference': 'Frisk 1991'},
        {'element': 'N', 'phase': 'BCC', 'G_ref_A': 65000, 'G_ref_B': 0, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 6000, 'data_source': 'SGTE', 'reference': 'Frisk 1991'},

        # Ti 的格点稳定性
        {'element': 'Ti', 'phase': 'BCC', 'G_ref_A': 6787.856, 'G_ref_B': 1.098, 'G_ref_C': -1.5835, 'G_ref_D': 0.000067,
         'T_min': 298.15, 'T_max': 1941, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},
        {'element': 'Ti', 'phase': 'FCC', 'G_ref_A': 6000, 'G_ref_B': 0.1, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 1941, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},
        {'element': 'Ti', 'phase': 'HCP', 'G_ref_A': 0, 'G_ref_B': 0, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 1941, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},

        # Nb 的格点稳定性
        {'element': 'Nb', 'phase': 'BCC', 'G_ref_A': 0, 'G_ref_B': 0, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 2750, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},
        {'element': 'Nb', 'phase': 'FCC', 'G_ref_A': 13500, 'G_ref_B': 1.7, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 2750, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},

        # V 的格点稳定性
        {'element': 'V', 'phase': 'BCC', 'G_ref_A': 0, 'G_ref_B': 0, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 2183, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},
        {'element': 'V', 'phase': 'FCC', 'G_ref_A': 7500, 'G_ref_B': 1.0, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 2183, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},

        # Al 的格点稳定性
        {'element': 'Al', 'phase': 'FCC', 'G_ref_A': 0, 'G_ref_B': 0, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 933.47, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},
        {'element': 'Al', 'phase': 'BCC', 'G_ref_A': 10083, 'G_ref_B': -4.813, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 933.47, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},

        # Cr 的格点稳定性
        {'element': 'Cr', 'phase': 'BCC', 'G_ref_A': 0, 'G_ref_B': 0, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 2180, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},
        {'element': 'Cr', 'phase': 'FCC', 'G_ref_A': 7284, 'G_ref_B': 0.163, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 2180, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},

        # Mn 的格点稳定性
        {'element': 'Mn', 'phase': 'BCC', 'G_ref_A': -3235.3, 'G_ref_B': 2.234, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 1519, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},
        {'element': 'Mn', 'phase': 'FCC', 'G_ref_A': -3439.3, 'G_ref_B': 2.02, 'G_ref_C': 0, 'G_ref_D': 0,
         'T_min': 298.15, 'T_max': 1519, 'data_source': 'SGTE', 'reference': 'Dinsdale 1991'},
    ]

    for lattice in lattice_stability_data:
        columns = ', '.join(lattice.keys())
        placeholders = ', '.join(['?' for _ in lattice])
        sql = f'INSERT OR REPLACE INTO lattice_stability ({columns}) VALUES ({placeholders})'
        cursor.execute(sql, list(lattice.values()))

    # ==================== Wagner相互作用系数数据 ====================
    wagner_data = [
        # Fe基体中 C 的自相互作用系数
        {'solvent': 'Fe', 'solute_i': 'C', 'solute_j': 'C', 'phase': 'FCC',
         'epsilon_ij_A': 22.0, 'epsilon_ij_B': 0, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Sigworth 1974', 'reference': 'Sigworth & Elliott, Met. Sci. 8 (1974) 298'},
        {'solvent': 'Fe', 'solute_i': 'C', 'solute_j': 'C', 'phase': 'BCC',
         'epsilon_ij_A': 38.0, 'epsilon_ij_B': 0, 'T_min': 773, 'T_max': 1173,
         'data_source': 'Wada 1971', 'reference': 'Wada et al., Trans. ISIJ 11 (1971) 181'},

        # Fe基体中 Ti-C 相互作用
        {'solvent': 'Fe', 'solute_i': 'Ti', 'solute_j': 'C', 'phase': 'FCC',
         'epsilon_ij_A': -120, 'epsilon_ij_B': 0, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Sigworth 1974', 'reference': 'Sigworth & Elliott, Met. Sci. 8 (1974) 298'},

        # Fe基体中 V-C 相互作用
        {'solvent': 'Fe', 'solute_i': 'V', 'solute_j': 'C', 'phase': 'FCC',
         'epsilon_ij_A': -62, 'epsilon_ij_B': 0, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Sigworth 1974', 'reference': 'Sigworth & Elliott, Met. Sci. 8 (1974) 298'},

        # Fe基体中 Nb-C 相互作用
        {'solvent': 'Fe', 'solute_i': 'Nb', 'solute_j': 'C', 'phase': 'FCC',
         'epsilon_ij_A': -88, 'epsilon_ij_B': 0, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Sigworth 1974', 'reference': 'Sigworth & Elliott, Met. Sci. 8 (1974) 298'},

        # Fe基体中 N 的自相互作用系数
        {'solvent': 'Fe', 'solute_i': 'N', 'solute_j': 'N', 'phase': 'FCC',
         'epsilon_ij_A': 0, 'epsilon_ij_B': 0, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Sigworth 1974', 'reference': 'Sigworth & Elliott, Met. Sci. 8 (1974) 298'},

        # Fe基体中 Ti-N 相互作用
        {'solvent': 'Fe', 'solute_i': 'Ti', 'solute_j': 'N', 'phase': 'FCC',
         'epsilon_ij_A': -246, 'epsilon_ij_B': 0, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Morita 1987', 'reference': 'Morita & Kunisada, Trans. ISIJ 17 (1977) 479'},

        # Fe基体中 Al-N 相互作用
        {'solvent': 'Fe', 'solute_i': 'Al', 'solute_j': 'N', 'phase': 'FCC',
         'epsilon_ij_A': -25, 'epsilon_ij_B': 0, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Sigworth 1974', 'reference': 'Sigworth & Elliott, Met. Sci. 8 (1974) 298'},

        # Fe基体中 Mn-S 相互作用
        {'solvent': 'Fe', 'solute_i': 'Mn', 'solute_j': 'S', 'phase': 'FCC',
         'epsilon_ij_A': -56, 'epsilon_ij_B': 0, 'T_min': 1173, 'T_max': 1773,
         'data_source': 'Ohtani 1984', 'reference': 'Ohtani & Hillert, CALPHAD 8 (1984) 189'},
    ]

    for wagner in wagner_data:
        columns = ', '.join(wagner.keys())
        placeholders = ', '.join(['?' for _ in wagner])
        sql = f'INSERT OR REPLACE INTO wagner_interaction ({columns}) VALUES ({placeholders})'
        cursor.execute(sql, list(wagner.values()))

    conn.commit()
    print(f"成功插入 {len(all_compound_data)} 个化合物热力学数据")
    print(f"成功插入 {len(solubility_product_data)} 条溶解度积数据")
    print(f"成功插入 {len(lattice_stability_data)} 条格点稳定性数据")
    print(f"成功插入 {len(wagner_data)} 条Wagner相互作用系数数据")


# ==================== 数据库查询函数 ====================

def get_compound_data(conn: sqlite3.Connection, formula: str) -> Optional[Dict]:
    """
    获取化合物热力学数据

    Parameters:
        conn: 数据库连接
        formula: 化合物分子式

    Returns:
        Dict 或 None
    """
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM compound_thermodynamics WHERE compound_formula = ?', (formula,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_solubility_product(conn: sqlite3.Connection, formula: str, phase: str,
                          matrix_base: str = 'Fe') -> Optional[Dict]:
    """
    获取溶解度积数据

    Parameters:
        conn: 数据库连接
        formula: 化合物分子式
        phase: 基体相 (FCC, BCC, Liquid)
        matrix_base: 基体元素

    Returns:
        Dict 或 None
    """
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM solubility_product
        WHERE compound_formula = ? AND matrix_phase = ? AND matrix_base = ?
    ''', (formula, phase, matrix_base))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_lattice_stability(conn: sqlite3.Connection, element: str, phase: str) -> Optional[Dict]:
    """
    获取格点稳定性数据

    Parameters:
        conn: 数据库连接
        element: 元素符号
        phase: 相 (FCC, BCC, HCP, Liquid)

    Returns:
        Dict 或 None
    """
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM lattice_stability WHERE element = ? AND phase = ?', (element, phase))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_wagner_interaction(conn: sqlite3.Connection, solvent: str, solute_i: str,
                          solute_j: str, phase: str) -> Optional[Dict]:
    """
    获取Wagner相互作用系数

    Parameters:
        conn: 数据库连接
        solvent: 溶剂元素
        solute_i: 溶质i
        solute_j: 溶质j
        phase: 相

    Returns:
        Dict 或 None
    """
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM wagner_interaction
        WHERE solvent = ? AND solute_i = ? AND solute_j = ? AND phase = ?
    ''', (solvent, solute_i, solute_j, phase))
    row = cursor.fetchone()
    return dict(row) if row else None


def list_compounds_by_type(conn: sqlite3.Connection, compound_type: str) -> List[Dict]:
    """
    列出某类型的所有化合物

    Parameters:
        conn: 数据库连接
        compound_type: 化合物类型 (carbide, nitride, oxide, sulfide)

    Returns:
        化合物列表
    """
    cursor = conn.cursor()
    cursor.execute('''
        SELECT compound_formula, compound_name, metal_element, nonmetal_element,
               melting_point, delta_gf_A, delta_gf_B
        FROM compound_thermodynamics
        WHERE compound_type = ?
        ORDER BY compound_formula
    ''', (compound_type,))
    return [dict(row) for row in cursor.fetchall()]


def calculate_delta_gf(compound_data: Dict, T: float) -> float:
    """
    计算化合物在指定温度下的标准生成吉布斯自由能

    ΔG°f = A + B*T + C*T*ln(T)

    Parameters:
        compound_data: 化合物数据字典
        T: 温度 (K)

    Returns:
        ΔG°f (J/mol)
    """
    A = compound_data['delta_gf_A']
    B = compound_data['delta_gf_B']
    C = compound_data.get('delta_gf_C', 0) or 0

    import math
    return A + B * T + C * T * math.log(T) if C != 0 else A + B * T


def calculate_log_ksp(ksp_data: Dict, T: float) -> float:
    """
    计算指定温度下的溶解度积对数

    log(Ksp) = A/T + B + C*ln(T)

    Parameters:
        ksp_data: 溶解度积数据字典
        T: 温度 (K)

    Returns:
        log(Ksp)
    """
    A = ksp_data['log_ksp_A']
    B = ksp_data['log_ksp_B']
    C = ksp_data.get('log_ksp_C', 0) or 0

    import math
    return A / T + B + C * math.log(T) if C != 0 else A / T + B


# ==================== 主程序 ====================

def create_and_populate_database(db_path: Optional[Path] = None) -> Path:
    """
    创建并填充化合物数据库

    Returns:
        数据库文件路径
    """
    if db_path is None:
        db_path = DATABASE_PATH

    print(f"正在创建数据库: {db_path}")
    conn = init_database(db_path)

    print("正在填充示例数据...")
    populate_sample_data(conn)

    conn.close()
    print(f"数据库创建完成: {db_path}")

    return db_path


if __name__ == '__main__':
    # 创建数据库并填充数据
    db_path = create_and_populate_database()

    # 验证数据
    conn = init_database(db_path)

    print("\n" + "="*60)
    print("数据库内容验证")
    print("="*60)

    # 显示碳化物
    print("\n碳化物 (Carbides):")
    for compound in list_compounds_by_type(conn, 'carbide'):
        print(f"  {compound['compound_formula']}: {compound['compound_name']}, Tm={compound['melting_point']}K")

    # 显示氮化物
    print("\n氮化物 (Nitrides):")
    for compound in list_compounds_by_type(conn, 'nitride'):
        print(f"  {compound['compound_formula']}: {compound['compound_name']}, Tm={compound['melting_point']}K")

    # 显示氧化物
    print("\n氧化物 (Oxides):")
    for compound in list_compounds_by_type(conn, 'oxide'):
        print(f"  {compound['compound_formula']}: {compound['compound_name']}, Tm={compound['melting_point']}K")

    # 显示硫化物
    print("\n硫化物 (Sulfides):")
    for compound in list_compounds_by_type(conn, 'sulfide'):
        print(f"  {compound['compound_formula']}: {compound['compound_name']}, Tm={compound['melting_point']}K")

    # 测试计算函数
    print("\n" + "="*60)
    print("计算示例")
    print("="*60)

    tic_data = get_compound_data(conn, 'TiC')
    if tic_data:
        T = 1473  # 1200°C
        delta_gf = calculate_delta_gf(tic_data, T)
        print(f"\nTiC @ {T}K: ΔG°f = {delta_gf/1000:.2f} kJ/mol")

    ksp_data = get_solubility_product(conn, 'TiC', 'FCC', 'Fe')
    if ksp_data:
        T = 1473
        log_ksp = calculate_log_ksp(ksp_data, T)
        print(f"TiC in FCC-Fe @ {T}K: log(Ksp) = {log_ksp:.3f}")

    conn.close()
