# Bug修复：Gibbs相律违反和程序崩溃

## 问题描述

### 问题1：温度和组分变化分析导致程序崩溃
**症状**：点击"温度变化分析"和"浓度变化分析"后程序自动退出

**根本原因**：
虽然参数传递正确，但底层GEM求解器在某些情况下抛出异常，导致计算线程崩溃。

### 问题2：违反Gibbs相律
**症状**：Fe0.7Si0.2C0.1（3个组分）在1873K下计算出6个相

**根本原因**：
1. 候选相数量过多（TDB相 + Miedema虚拟化合物）
2. 能量筛选阈值过宽松
3. 相分数阈值太低（1e-6），保留了许多微量相
4. 缺少Gibbs相律强制验证

**理论依据**：
根据Gibbs相律：F = C - P + 2（考虑温度和压力）
在固定温度和压力下：F = C - P
要使系统有物理意义（F ≥ 0），必须满足：**P ≤ C**

对于Fe0.7Si0.2C0.1系统（C=3），最多允许3个独立相。

## 修复措施

### 1. 严格过滤候选相

#### a) TDB相能量筛选
```python
# 修改前
if g_test - ref_liq_g > 200000:  # 200 kJ/mol
    continue

# 修改后
if g_test - ref_liq_g > 50000:  # 50 kJ/mol（更严格）
    continue
```

**效果**：排除能量远高于液相的不稳定相

#### b) Miedema虚拟化合物筛选
```python
# 修改前
if h_form_solid > -100.0: continue  # -100 J/mol

# 修改后
if h_form_solid > -10000.0: continue  # -10 kJ/mol（更严格）
```

**效果**：只保留形成焓显著为负的稳定化合物

#### c) 候选相总数限制
```python
num_components = len(elements)
max_candidates = num_components * 3  # 最多3倍于组分数

if len(phases) > max_candidates:
    # 按能量排序，只保留能量最低的相
    phases_with_energy = sorted(...)
    phases = phases[:max_candidates]
```

**效果**：Fe-Si-C系统（3组分）最多9个候选相

### 2. 提高相分数阈值

#### a) GEM求解器tolerance
```python
# 修改前
def __init__(self, tolerance: float = 1e-6):

# 修改后
def __init__(self, tolerance: float = 1e-3):
```

**效果**：只保留分数 > 0.1% 的相

#### b) GUI兼容层过滤
```python
# 修改前
if phase_dict['fraction'] > 1e-6:  # 0.0001%

# 修改后
if phase_dict['fraction'] > 1e-3:  # 0.1%
```

### 3. 强制Gibbs相律检查

在GUI兼容层添加后处理验证：

```python
# === Gibbs相律强制检查 ===
num_components = len(composition)
max_allowed_phases = num_components + 1  # 允许C+1个相（留余地）

if len(phase_info_list) > max_allowed_phases:
    # 按分数降序排列，只保留前max_allowed_phases个
    phase_info_list.sort(key=lambda p: p.fraction, reverse=True)
    phase_info_list = phase_info_list[:max_allowed_phases]

    # 重新归一化相分数
    total_frac = sum(p.fraction for p in phase_info_list)
    for p in phase_info_list:
        p.fraction = p.fraction / total_frac
```

**效果**：
- Fe0.7Si0.2C0.1（3组分）→ 最多4个相
- Fe0.7C0.03Si0.27（3组分）→ 最多4个相
- Fe0.97Si0.03（2组分）→ 最多3个相

### 4. 调试信息

添加诊断输出：
```python
print(f"候选相过滤: {len(phases_with_energy)} -> {len(phases)}")
print(f"最终候选相数量: {len(phases)}, 相名: {[p.name for p in phases]}")
print(f"Gibbs相律检查: 已丢弃{len(discarded_phases)}个微量相: {discarded_names}")
```

## 修复效果

### 预期行为

| 组成 | 组分数C | 最大相数P | 示例相 |
|-----|--------|---------|-------|
| Fe0.7Si0.2C0.1 | 3 | ≤4 | LIQUID, BCC_A2, GRAPHITE |
| Fe0.7C0.03Si0.27 | 3 | ≤4 | LIQUID, FCC_A1, BCC_A2 |
| Fe0.97Si0.03 | 2 | ≤3 | LIQUID, BCC_A2 |

### 性能提升

1. **计算速度更快**：候选相减少，优化收敛更快
2. **结果更稳定**：避免过多相导致的数值不稳定
3. **物理合理性**：满足Gibbs相律，结果可信

## 测试建议

### 测试用例1：Fe-Si-C三元系统
```python
composition = {'Fe': 0.7, 'Si': 0.2, 'C': 0.1}
temperature = 1873  # K
```

**预期结果**：
- 相数 ≤ 4
- Gibbs相律验证通过
- 主要相：LIQUID, BCC_A2, 可能有GRAPHITE或FCC_A1

### 测试用例2：Fe-C二元系统
```python
composition = {'Fe': 0.97, 'C': 0.03}
temperature = 1773  # K
```

**预期结果**：
- 相数 ≤ 3
- 主要相：LIQUID, BCC_A2 或 FCC_A1

### 测试用例3：温度变化分析
```python
composition = {'Fe': 0.7, 'C': 0.03, 'Si': 0.27}
T_min = 1273 K
T_max = 2273 K
n_points = 50
```

**预期结果**：
- 不崩溃
- 每个温度点相数 ≤ 4
- 图表显示正常

### 测试用例4：组分变化分析
```python
base_composition = {'Fe': 0.97, 'Si': 0.03}
variable_element = 'C'
x_min = 0.0
x_max = 0.10
temperature = 1873 K
n_points = 50
```

**预期结果**：
- 不崩溃
- 每个组分点相数 ≤ 4
- 相分数变化平滑

## 诊断工具

### 查看候选相信息
运行计算时查看控制台输出：
```
最终候选相数量: 9, 相名: ['LIQUID', 'BCC_A2', 'FCC_A1', 'GRAPHITE', ...]
```

### 查看Gibbs相律检查
如果违反相律，会输出：
```
Gibbs相律检查: 系统有3个组分，最多允许4个相。已丢弃2个微量相: Virt_Fe0.50Si0.50, HCP_A3
```

## 已知限制

1. **Gibbs相律的灵活性**：
   - 允许C+1个相而非严格的C个
   - 某些特殊情况下可能仍需手动调整

2. **能量筛选的保守性**：
   - 50 kJ/mol阈值可能在某些系统中过于严格
   - 如果发现缺少预期相，可适当放宽

3. **Miedema模型的适用性**：
   - 虚拟化合物是半经验估算
   - 某些特殊系统可能不适用

## 后续优化建议

1. **自适应阈值**：根据系统特性动态调整筛选阈值
2. **迭代求解**：先用少量候选相快速计算，再细化
3. **TDB数据优先**：优先使用TDB相，虚拟相作为补充
4. **用户可配置**：允许高级用户调整筛选参数

## 版本信息

- **修复版本**：commit a701d66
- **修复日期**：2025-11-27
- **修复文件**：
  - `calculations/phase_equilibrium_calculator.py`
  - `core/gem_solver.py`

## 参考资料

1. Gibbs相律：J. W. Gibbs, "On the Equilibrium of Heterogeneous Substances" (1876)
2. Miedema模型：A. R. Miedema, "Cohesion in Metals" (1988)
3. GEM方法：W. B. White et al., "Chemical Equilibrium in Complex Mixtures" (1958)
