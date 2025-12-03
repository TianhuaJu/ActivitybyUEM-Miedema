# AlloyThermolCal Pro (合金热力学计算专业版)

基于UEM-Miedema模型的专业合金热力学计算软件。

## 功能特点

### 1. 活度计算
- **单点活度计算**: 计算指定温度和成分下的活度系数
- **活度随温度变化**: 分析活度系数与温度的关系
- **活度随浓度变化**: 分析活度系数与成分的关系
- **合金添加模拟**: 模拟向合金中添加元素的效果

### 2. 热力学性质
- **混合焓/熵/Gibbs能**: 计算合金混合的热力学量
- **相互作用系数**: Wagner一阶相互作用系数
- **二阶相互作用系数**: 高阶相互作用参数

### 3. 相图与相平衡
- **二元相图**: 计算并绘制二元合金相图
- **多相平衡**: 计算多元合金的多相平衡

### 4. 溶解度与析出
- **化合物溶解度积**: 计算碳化物、氮化物等化合物的溶解度积
- **析出温度**: 预测溶质析出的临界温度
- **过饱和度分析**: 判断合金的析出倾向

## 项目结构

```
ActivitybyUEM-Miedema/
├── Main.py                     # 程序入口
├── __init__.py                 # 包初始化
├── README.md                   # 项目说明
│
├── calculations/               # 核心计算模块
│   ├── __init__.py
│   ├── thermodynamic_properties.py    # 热力学性质基础
│   ├── activity_calculator.py         # 活度系数计算
│   ├── phase_diagram.py               # 相图计算
│   ├── phase_equilibrium_calculator.py # 相平衡计算
│   ├── PhaseEquilibriumCalculator.py  # 相平衡计算(化合物优先版)
│   ├── compound_solubility.py         # 化合物溶解度积
│   ├── solubility_corrected.py        # 修正版溶解度
│   ├── precipitation_temperature.py   # 析出温度计算
│   ├── parallel_solubility.py         # 并行溶解度计算
│   ├── global_process_pool.py         # 全局进程池
│   └── process_pool_init.py           # 进程池初始化
│
├── core/                       # 核心工具模块
│   ├── __init__.py
│   ├── constants.py            # 物理常量和元素数据
│   ├── element.py              # 元素类定义
│   ├── database_handler.py     # 数据库处理
│   ├── tdb_parser.py           # TDB文件解析
│   └── utils.py                # 通用工具
│
├── database/                   # 数据库模块
│   ├── __init__.py
│   ├── compound_database.py    # 化合物数据库管理
│   └── data/
│       ├── DataBase.db         # 元素参数数据库
│       ├── compounds.db        # 化合物热力学数据库
│       └── unary50.tdb         # SGTE单元系数据
│
├── docs/                       # 文档
│   ├── BUILD_GUIDE.md          # 构建指南
│   ├── THREAD_CANCEL_FIX.md    # 线程取消修复说明
│   ├── DATABASE_STRUCTURE.md   # 数据库结构文档
│   ├── phase_equilibrium_feature_guide.md
│   └── phase_equilibrium_implementation_summary.md
│
├── gui/                        # 图形界面模块
│   ├── __init__.py
│   ├── Alloyact_GUI_Pro.py     # 主窗口
│   ├── alloyact_gui.py         # 传统GUI
│   ├── data_ui.py              # 数据库管理界面
│   │
│   │   # 活度计算组件
│   ├── ActivityCalculationWidget.py
│   ├── ActivityVaryTemperatureWidget.py
│   ├── ActivityVaryConcentrationWidget.py
│   ├── ActivityVaryConcentrationWidget2.py
│   │
│   │   # 热力学性质组件
│   ├── ThermodynamicPropertiesWidget.py
│   ├── InteractionCoefficientWidget.py
│   ├── SecondOrderCoefficientWidget.py
│   │
│   │   # 相图与相平衡组件
│   ├── PhaseDiagramWidget.py
│   ├── PhaseEquilibriumWidget.py
│   │
│   │   # 溶解度与析出组件
│   ├── SolubilityWidget.py
│   ├── PrecipitationTemperatureWidget.py
│   │
│   └── UnitConversionWidget.py  # 单位转换
│
├── hooks/                      # 构建钩子
│   ├── __init__.py
│   ├── hook-matplotlib.py
│   └── runtime_optimize.py
│
├── models/                     # 热力学模型
│   ├── __init__.py
│   ├── miedema_model.py        # Miedema模型
│   ├── extrapolation_models.py # 外推模型(UEM1等)
│   └── activity_interaction_parameters.py
│
└── utils/                      # 辅助工具
    ├── __init__.py
    └── DataLogger.py           # 数据日志
```

## 安装依赖

```bash
pip install numpy scipy matplotlib PyQt5
```

## 运行程序

```bash
python Main.py
```

## 热力学原理

### UEM-Miedema模型
基于Miedema半经验模型计算二元合金的混合焓，并通过UEM (Universal Extrapolation Model) 方法外推到多元系统。

### 溶解度积
对于化合物 MₘXₙ 在溶液中的溶解平衡：
```
MₘXₙ(s) ⇌ m·M(溶解) + n·X(溶解)
Ksp = aₘᵐ · aₓⁿ = (γₘ·xₘ)ᵐ · (γₓ·xₓ)ⁿ
```

### 析出温度
析出温度T*满足：
```
μ_溶质(溶液, T*) = G°_析出相(T*)
```

## 数据来源

- SGTE纯物质热力学数据库
- Turkdogan, Physical Chemistry of High Temperature Technology
- Barin, Thermochemical Data of Pure Substances
- Miedema原始参数

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！
