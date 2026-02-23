# 热力学数据库结构说明

本文档描述了 AlloyAct Pro 软件所需的热力学数据库结构。

## 一、现有数据库

### 1. MiedemaParameter 表（已有）
存储Miedema模型所需的元素参数。

| 字段 | 类型 | 说明 |
|------|------|------|
| Symbol | TEXT | 元素符号 |
| phi | REAL | 电负性参数 φ* |
| nws | REAL | 电子密度参数 n_ws^(1/3) |
| V | REAL | 摩尔体积 (cm³/mol) |
| u | REAL | 电荷转移参数 |
| alpha_beta | TEXT | 杂化因子类型 (sp, d, other) |
| hybirdvalue | REAL | 杂化参数数值 |
| isTrans | INTEGER | 是否为过渡金属 (0/1) |
| dHtrans | REAL | 转变焓 ΔH_trans (kJ/mol) |
| mass | REAL | 原子量 (g/mol) |
| Tm | REAL | 熔点 (K) |
| Tb | REAL | 沸点 (K) |

### 2. first_order 表（已有）
一阶Wagner相互作用系数。

| 字段 | 类型 | 说明 |
|------|------|------|
| solv | TEXT | 溶剂元素 |
| solui | TEXT | 溶质i (被影响的元素) |
| soluj | TEXT | 溶质j (影响元素) |
| eji | TEXT | ε_j^i 质量分数表示 |
| sji | TEXT | ε_j^i 摩尔分数表示 |
| Rank | INTEGER | 数据可靠性等级 |
| T | TEXT | 适用温度 |
| reference | TEXT | 参考文献 |

### 3. second_order 表（已有）
二阶Wagner相互作用系数。

| 字段 | 类型 | 说明 |
|------|------|------|
| solv | TEXT | 溶剂元素 |
| solui | TEXT | 溶质i |
| soluj | TEXT | 溶质j |
| soluk | TEXT | 溶质k (可选) |
| ri_ij | TEXT | ρ_ij^i 质量分数表示 |
| pi_ij | TEXT | ρ_ij^i 摩尔分数表示 |
| ri_jk | TEXT | ρ_jk^i 质量分数表示 |
| pi_jk | TEXT | ρ_jk^i 摩尔分数表示 |
| T | TEXT | 适用温度 |
| Rank | INTEGER | 数据可靠性等级 |
| reference | TEXT | 参考文献 |

### 4. lnY0 表（已有）
无限稀释活度系数。

| 字段 | 类型 | 说明 |
|------|------|------|
| solv | TEXT | 溶剂元素 |
| solui | TEXT | 溶质元素 |
| lnYi0 | TEXT | ln(γ_i^0) 表达式 |
| Yi0 | TEXT | γ_i^0 数值 |
| T | TEXT | 适用温度 |

### 5. unary50.tdb（已有）
SGTE Unary Database 格式的纯元素热力学数据。

---

## 二、需要添加的数据库

### 1. compound_thermodynamics 表（新增 - 优先级：高）
**用途**：存储化合物（碳化物、氮化物、氧化物等）的热力学数据

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| id | INTEGER | 主键 | 1 |
| formula | TEXT | 化学式 | TiC |
| name | TEXT | 化合物名称 | 碳化钛 |
| metal_element | TEXT | 金属元素 | Ti |
| nonmetal_element | TEXT | 非金属元素 | C |
| metal_stoich | INTEGER | 金属计量数 | 1 |
| nonmetal_stoich | INTEGER | 非金属计量数 | 1 |
| delta_gf_A | REAL | ΔG°f = A + B*T 的常数项 (J/mol) | -184000 |
| delta_gf_B | REAL | ΔG°f 的温度系数 (J/mol/K) | 22.0 |
| delta_hf_298 | REAL | 298K标准生成焓 (J/mol) | -184500 |
| s_298 | REAL | 298K标准熵 (J/mol/K) | 24.2 |
| cp_a | REAL | Cp = a + b*T + c*T^2 + d/T^2 的a项 | 48.5 |
| cp_b | REAL | Cp的b项 | 0.005 |
| cp_c | REAL | Cp的c项 | 0 |
| cp_d | REAL | Cp的d项 | -850000 |
| crystal_structure | TEXT | 晶体结构 | NaCl |
| space_group | TEXT | 空间群 | Fm-3m |
| T_min | REAL | 适用温度下限 (K) | 298 |
| T_max | REAL | 适用温度上限 (K) | 3000 |
| reference | TEXT | 参考文献 | SGTE |

**需要添加的化合物数据**：

碳化物：
- TiC, NbC, VC, Fe3C, Cr7C3, Cr23C6, Mo2C, WC, ZrC, HfC, TaC

氮化物：
- TiN, AlN, VN, CrN, BN, Si3N4, ZrN, NbN

氧化物：
- Al2O3, SiO2, MnO, FeO, Fe2O3, TiO2, Cr2O3, MgO, CaO

硫化物：
- MnS, CaS, FeS, MgS

### 2. solubility_product 表（新增 - 优先级：高）
**用途**：存储化合物在金属熔体中的溶解度积实验数据

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| id | INTEGER | 主键 | 1 |
| compound | TEXT | 化合物 | TiC |
| solvent | TEXT | 溶剂 | Fe |
| phase | TEXT | 相态 (LIQUID/SOLID) | LIQUID |
| log_ksp_expression | TEXT | log(Ksp) = f(T) 表达式 | -7000/T-2.75 |
| T_min | REAL | 适用温度下限 (K) | 1773 |
| T_max | REAL | 适用温度上限 (K) | 2073 |
| accuracy_rank | INTEGER | 数据可靠性等级 | A |
| reference | TEXT | 参考文献 | Turkdogan |

**常见溶解度积数据（Fe基）**：

| 化合物 | log(Ksp) 表达式 | 温度范围(K) | 参考文献 |
|--------|-----------------|-------------|----------|
| TiC | -7000/T - 2.75 | 1773-2073 | Turkdogan |
| TiN | -15200/T - 3.82 | 1773-2073 | Turkdogan |
| NbC | -6770/T - 2.26 | 1773-2073 | Turkdogan |
| VC | -6560/T - 3.28 | 1773-1973 | Turkdogan |
| VN | -8700/T - 2.86 | 1773-1973 | Turkdogan |
| AlN | -6770/T - 1.03 | 1773-2073 | SGTE |
| BN | -13970/T - 5.24 | 1773-2073 | SGTE |
| MnS | -9020/T - 2.93 | 1773-1973 | Turkdogan |

### 3. binary_phase_diagram 表（新增 - 优先级：中）
**用途**：存储二元相图实验数据用于验证

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| element_A | TEXT | 元素A |
| element_B | TEXT | 元素B |
| x_B | REAL | B的摩尔分数 |
| T_liquidus | REAL | 液相线温度 (K) |
| T_solidus | REAL | 固相线温度 (K) |
| phase_at_T | TEXT | 稳定相 |
| data_type | TEXT | 数据类型 (experimental/calculated) |
| reference | TEXT | 参考文献 |

### 4. experimental_solubility 表（新增 - 优先级：中）
**用途**：存储实验溶解度数据用于模型验证

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| solvent_alloy | TEXT | 溶剂合金成分 |
| solute | TEXT | 溶质元素 |
| T | REAL | 温度 (K) |
| solubility | REAL | 溶解度 (摩尔分数) |
| phase | TEXT | 相态 |
| reference | TEXT | 参考文献 |

### 5. lattice_stability 表（新增 - 优先级：中）
**用途**：存储元素在不同晶格中的稳定性参数

| 字段 | 类型 | 说明 |
|------|------|------|
| element | TEXT | 元素 |
| stable_phase | TEXT | 稳定相 |
| target_phase | TEXT | 目标相 |
| delta_G_lattice | TEXT | ΔG_lattice = f(T) 表达式 (J/mol) |
| T_min | REAL | 适用温度下限 |
| T_max | REAL | 适用温度上限 |
| reference | TEXT | 参考文献 |

**重要数据（非金属溶于金属相）**：

| 元素 | 稳定相 | 目标相 | ΔG_lattice (J/mol) |
|------|--------|--------|-------------------|
| C | GRAPHITE | FCC_A1 | +77000 |
| C | GRAPHITE | BCC_A2 | +87000 |
| N | GAS | FCC_A1 | +240000 |
| N | GAS | BCC_A2 | +250000 |
| Si | DIAMOND | FCC_A1 | +33000 |
| O | GAS | FCC_A1 | +250000 |

---

## 三、数据库文件结构

```
database/
├── data/
│   ├── DataBase.db           # SQLite主数据库
│   ├── unary50.tdb           # SGTE纯元素TDB数据
│   ├── compound.db           # 化合物热力学数据库（新增）
│   └── experimental.db       # 实验验证数据库（新增）
└── DATABASE_STRUCTURE.md     # 本文档
```

---

## 四、数据添加优先级

### 高优先级（核心功能）
1. **compound_thermodynamics** - 化合物标准生成Gibbs能
   - 碳化物：TiC, NbC, VC, Fe3C, Cr7C3, Cr23C6
   - 氮化物：TiN, AlN, VN, BN
   - 氧化物：Al2O3, SiO2, MnO

2. **solubility_product** - 溶解度积
   - Fe基熔体中的TiC, TiN, NbC, VC, VN, AlN数据

### 中优先级（扩展功能）
3. **lattice_stability** - 晶格稳定性
4. **binary_phase_diagram** - 二元相图验证数据
5. **experimental_solubility** - 溶解度实验数据

### 低优先级（未来扩展）
6. 多元化合物数据
7. 动力学数据
8. 界面能数据

---

## 五、数据来源推荐

1. **SGTE (Scientific Group Thermodata Europe)**
   - 纯元素和化合物的标准热力学数据
   - TDB格式数据库

2. **Turkdogan, E.T. "Fundamentals of Steelmaking"**
   - Fe基熔体中的溶解度积
   - Wagner相互作用系数

3. **Kubaschewski, O. et al. "Materials Thermochemistry"**
   - 化合物标准生成焓
   - 热容数据

4. **NIST-JANAF Thermochemical Tables**
   - 高温热力学数据
   - 热容函数

5. **ASM Handbook Volume 3: Alloy Phase Diagrams**
   - 二元/三元相图数据
   - 实验溶解度数据

---

## 六、SQL建表语句示例

```sql
-- 化合物热力学数据表
CREATE TABLE IF NOT EXISTS compound_thermodynamics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    formula TEXT NOT NULL UNIQUE,
    name TEXT,
    metal_element TEXT NOT NULL,
    nonmetal_element TEXT NOT NULL,
    metal_stoich INTEGER NOT NULL DEFAULT 1,
    nonmetal_stoich INTEGER NOT NULL DEFAULT 1,
    delta_gf_A REAL,
    delta_gf_B REAL,
    delta_hf_298 REAL,
    s_298 REAL,
    cp_a REAL,
    cp_b REAL,
    cp_c REAL,
    cp_d REAL,
    crystal_structure TEXT,
    space_group TEXT,
    T_min REAL DEFAULT 298,
    T_max REAL DEFAULT 3000,
    reference TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 溶解度积表
CREATE TABLE IF NOT EXISTS solubility_product (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compound TEXT NOT NULL,
    solvent TEXT NOT NULL DEFAULT 'Fe',
    phase TEXT NOT NULL DEFAULT 'LIQUID',
    log_ksp_expression TEXT NOT NULL,
    T_min REAL,
    T_max REAL,
    accuracy_rank TEXT DEFAULT 'B',
    reference TEXT,
    UNIQUE(compound, solvent, phase)
);

-- 晶格稳定性表
CREATE TABLE IF NOT EXISTS lattice_stability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    element TEXT NOT NULL,
    stable_phase TEXT NOT NULL,
    target_phase TEXT NOT NULL,
    delta_G_expression TEXT NOT NULL,
    T_min REAL DEFAULT 298,
    T_max REAL DEFAULT 3000,
    reference TEXT,
    UNIQUE(element, stable_phase, target_phase)
);
```

---

**文档版本**: 1.0
**更新日期**: 2024年
**作者**: UEM-Miedema开发团队
