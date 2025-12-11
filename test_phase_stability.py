# -*- coding: utf-8 -*-
"""
测试相稳定性计算
验证液固相线温度和平衡相判断是否合理
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calculations.phase_equilibrium import PhaseEquilibriumCalculator

def test_phase_stability():
    """测试不同合金在不同温度下的相稳定性"""

    calculator = PhaseEquilibriumCalculator()

    # 测试合金组成
    test_alloys = [
        # 纯铁
        {'name': '纯铁 Fe',
         'composition': {'Fe': 1.0},
         'expected_melting': 1811},  # 纯铁熔点 1811K

        # Fe-3%C (wt%) ≈ Fe-12%C (at%) - 实际约 Fe0.88C0.12
        # 但用户例子是 Fe0.95C0.03Si0.02
        {'name': 'Fe-0.03C-0.02Si (摩尔分数)',
         'composition': {'Fe': 0.95, 'C': 0.03, 'Si': 0.02},
         'expected_melting': 1770},  # 约1770K

        # Fe-1%C (at%)
        {'name': 'Fe-0.01C (摩尔分数)',
         'composition': {'Fe': 0.99, 'C': 0.01},
         'expected_melting': 1800},  # 约1800K

        # Fe-5%C (at%) - 接近共晶成分
        {'name': 'Fe-0.05C (摩尔分数)',
         'composition': {'Fe': 0.95, 'C': 0.05},
         'expected_melting': 1420},  # 共晶温度约1420K (1147°C)

        # Fe-2%Ni
        {'name': 'Fe-0.02Ni (摩尔分数)',
         'composition': {'Fe': 0.98, 'Ni': 0.02},
         'expected_melting': 1800},
    ]

    # 测试温度范围
    temperatures = [1200, 1300, 1400, 1450, 1500, 1550, 1600, 1700, 1800, 1873]

    print("=" * 80)
    print("相稳定性测试")
    print("=" * 80)

    for alloy in test_alloys:
        print(f"\n{'─' * 80}")
        print(f"合金: {alloy['name']}")
        print(f"组成: {alloy['composition']}")
        print(f"预期熔点: ~{alloy['expected_melting']}K")
        print(f"{'─' * 80}")
        print(f"{'温度(K)':<12} {'稳定相':<15} {'说明'}")
        print(f"{'─' * 40}")

        prev_phase = None
        transition_temp = None

        for T in temperatures:
            phase = calculator._find_lowest_energy_phase(alloy['composition'], T)

            # 检测相变
            if prev_phase is not None and phase != prev_phase:
                if prev_phase != 'LIQUID' and phase == 'LIQUID':
                    transition_temp = T
                    note = f"<-- 熔化! (从{prev_phase}到{phase})"
                elif prev_phase == 'LIQUID' and phase != 'LIQUID':
                    note = f"<-- 凝固! (从{prev_phase}到{phase})"
                else:
                    note = f"<-- 相变 (从{prev_phase}到{phase})"
            else:
                note = ""

            print(f"{T:<12} {phase:<15} {note}")
            prev_phase = phase

        if transition_temp:
            diff = transition_temp - alloy['expected_melting']
            print(f"\n计算熔化温度: ~{transition_temp}K (与预期差: {diff:+d}K)")
        else:
            print(f"\n在测试温度范围内未发生固-液转变")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

def test_detailed_gibbs_energy():
    """测试详细的Gibbs能计算，用于调试"""

    calculator = PhaseEquilibriumCalculator()

    composition = {'Fe': 0.95, 'C': 0.03, 'Si': 0.02}
    temperatures = [1400, 1500, 1600, 1700, 1800]

    print("\n" + "=" * 80)
    print("详细Gibbs能计算 (Fe0.95C0.03Si0.02)")
    print("=" * 80)

    # 间隙元素溶解能
    INTERSTITIAL_DISSOLUTION_ENERGY = {
        'C': {'LIQUID': 22000, 'FCC_A1': 42000, 'BCC_A2': 90000, 'HCP_A3': 50000},
    }

    R = 8.314
    phases = ['LIQUID', 'FCC_A1', 'BCC_A2']

    for T in temperatures:
        print(f"\n温度: {T}K")
        print(f"{'相':<12} {'G_ref(Fe)':<15} {'G_ref(C)':<15} {'G_ref(Si)':<15} {'G_混合':<15} {'G_总':<15}")
        print("-" * 90)

        g_values = {}

        for phase in phases:
            try:
                # Fe的Gibbs能
                g_fe = calculator.tdb_parser.get_gibbs_energy('FE', phase, T)
                if g_fe is None:
                    if phase == 'LIQUID':
                        g_fe = calculator.tdb_parser.get_gibbs_energy('FE', 'SER', T)
                    else:
                        g_fe = calculator._estimate_lattice_stability('FE', phase, T)

                # C的Gibbs能 (使用溶解能)
                g_c = INTERSTITIAL_DISSOLUTION_ENERGY['C'].get(phase, 50000)

                # Si的Gibbs能
                g_si = calculator.tdb_parser.get_gibbs_energy('SI', phase, T)
                if g_si is None:
                    if phase == 'LIQUID':
                        g_si = calculator.tdb_parser.get_gibbs_energy('SI', 'SER', T)
                    else:
                        g_si = calculator._estimate_lattice_stability('SI', phase, T)

                # 加权平均
                g_ref = 0.95 * (g_fe or 0) + 0.03 * g_c + 0.02 * (g_si or 0)

                # 混合熵
                g_mix = R * T * (0.95 * (-0.0513) + 0.03 * (-3.507) + 0.02 * (-3.912))
                # ln(0.95)=-0.0513, ln(0.03)=-3.507, ln(0.02)=-3.912

                g_total = g_ref + g_mix
                g_values[phase] = g_total

                print(f"{phase:<12} {g_fe or 0:<15.0f} {g_c:<15.0f} {g_si or 0:<15.0f} {g_mix:<15.0f} {g_total:<15.0f}")

            except Exception as e:
                print(f"{phase:<12} Error: {e}")

        # 找最低能量相
        if g_values:
            min_phase = min(g_values.items(), key=lambda x: x[1])
            print(f"\n最稳定相: {min_phase[0]} (G = {min_phase[1]:.0f} J/mol)")

if __name__ == '__main__':
    test_phase_stability()
    print("\n" * 2)
    test_detailed_gibbs_energy()
