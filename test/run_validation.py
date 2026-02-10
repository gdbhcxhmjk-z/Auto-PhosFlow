# -*- coding: utf-8 -*-
import sys
import os
import math
from pathlib import Path

# --- 1. 环境配置：挂载上级目录以引用 lib ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

try:
    from lib.analysis_handler import extract_rates_from_logs, calculate_plqy
    from lib.momap_handler import check_evc_reorg, extract_orca_soc, extract_orca_edme, get_gaussian_energy
    from lib.g16_handler import check_imaginary_frequencies
    print(f"✅ 成功加载核心库: {parent_dir}/lib")
except ImportError as e:
    print(f"❌ 无法导入 lib 库，请检查目录结构。\n错误信息: {e}")
    sys.exit(1)

# =========================================================
# 📝 用户输入区域：Ground Truth (在此填入你的期望值)
# =========================================================
MANUAL_DATA = {
    # --- 1. 速率文件 ---
    "files_rates": {
        "kr_log":   "spec.tvcf.log",
        "kisc_log": "isc.tvcf.log",
        "kic_log":  "ic.tvcf.log"
    },
    "expect_rates": {
        "Kr":   7.39465268E+04,
        "Kisc": 1.20620332E+00,
        "Kic":  7.06490755E+09
    },

    # --- 2. 能量文件 (S0, S1, T1) ---
    # 如果你有真实的 log 文件，请修改这里的文件名
    "files_energy": {
        "s0_log": "s0.log", 
        "s1_log": "s1.log",
        "t1_log": "t1.log"
    },
    # 期望的能量值 (Hartree)，用于验证读取是否准确
    "expect_energies": {
        "S0": -1339.42085306, 
        "S1": -1339.29715975,  # S1 > T1
        "T1": -1339.31771336 # T1 > S0
        # 这里只是示例值，后面 Mock 生成器会写入这些值
    },

    # --- 3. 虚频检查文件 ---
    "file_freq_check": "s1.log", # 通常检查优化或频率文件
    "expect_imaginary": False,        # 期望无虚频

    # --- 4. EVC & ORCA ---
    "file_evc": "evc.dint.dat",
    "expect_reorg_max": 5000,
    "file_orca": "soc.out",
    "expect_orca": {
        "Hso":  0.89131,
        "EDME": 0.1808
    }
}

# =========================================================
# 🛠️ 辅助工具：生成 Mock 数据 (如果文件不存在)
# =========================================================
def generate_mock_gaussian_logs():
    """生成模拟的 Gaussian log 用于测试能量读取和虚频检查"""
    # S0: 基态能量
    if not os.path.exists("mock_s0.log"):
        with open("mock_s0.log", "w") as f:
            f.write(f"""
 SCF Done:  E(RTPSSh) =  {MANUAL_DATA['expect_energies']['S0']:.6f}     A.U. after   11 cycles
 Normal termination of Gaussian 16
            """)

    # S1: 激发态能量 (比 S0 高, 比 T1 高)
    if not os.path.exists("mock_s1.log"):
        with open("mock_s1.log", "w") as f:
            f.write(f"""
 SCF Done:  E(RTPSSh) =  {MANUAL_DATA['expect_energies']['S1']:.6f}     A.U. after   11 cycles
 Harmonic frequencies (cm**-1), IR intensities (KM/Mole), Raman scattering activities
 Frequencies --    10.50                 23.40                  50.10
 Normal termination of Gaussian 16
            """)

    # T1: 三重态能量
    if not os.path.exists("mock_t1.log"):
        with open("mock_t1.log", "w") as f:
            f.write(f"""
 SCF Done:  E(RTPSSh) =  {MANUAL_DATA['expect_energies']['T1']:.6f}     A.U. after   11 cycles
 Normal termination of Gaussian 16
            """)
    print("ℹ️  已生成 Mock Gaussian Log 文件 (若真实文件不存在)")

# =========================================================
# ⚙️ 验证函数
# =========================================================
def check_val(name, calc, expect, tol_percent=1.0):
    if expect == 0:
        passed = abs(calc - expect) < 1e-6
    else:
        diff_p = abs((calc - expect) / expect) * 100
        passed = diff_p < tol_percent
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {name:<15} | 提取值: {calc:.6e} | 期望值: {expect:.6e} | 误差: {diff_p:.2f}%")

# =========================================================
# 🚀 执行测试
# =========================================================
def run_tests():
    # 0. 准备环境
    generate_mock_gaussian_logs()
    
    print("\n" + "="*50)
    print("🧪 开始全模块集成测试")
    print("="*50)

    # --- Test 1: 能量读取 & Delta E ---
    print("\n[Test 1] 能量读取 (Gaussian Logs)")
    f_eng = MANUAL_DATA["files_energy"]
    
    e_s0 = get_gaussian_energy(f_eng["s0_log"])
    e_s1 = get_gaussian_energy(f_eng["s1_log"])
    e_t1 = get_gaussian_energy(f_eng["t1_log"])
    
    check_val("E(S0)", e_s0, MANUAL_DATA["expect_energies"]["S0"])
    check_val("E(S1)", e_s1, MANUAL_DATA["expect_energies"]["S1"])
    check_val("E(T1)", e_t1, MANUAL_DATA["expect_energies"]["T1"])
    
    # 自动计算能级差
    delta_E = e_s1 - e_t1 # Hartree
    dE_eV = delta_E * 27.2114
    print(f"ℹ️  计算得 Delta E (S1 - T1): {delta_E:.6f} Ha ({dE_eV:.3f} eV)")
    
    if delta_E < 0:
        print("⚠️  警告: S1 能量低于 T1，这在普通磷光分子中不常见，请确认态顺序。")

    # --- Test 2: 虚频检测 ---
    print("\n[Test 2] 虚频检测")
    f_freq = MANUAL_DATA["file_freq_check"]
    if os.path.exists(f_freq):
        has_imag, freqs = check_imaginary_frequencies(f_freq)
        expect_imag = MANUAL_DATA["expect_imaginary"]
        
        status = "✅ PASS" if has_imag == expect_imag else "❌ FAIL"
        res_str = f"有虚频 {freqs}" if has_imag else "无虚频"
        print(f"{status} | 文件: {f_freq} | 检测结果: {res_str}")
    else:
        print(f"❌ 跳过: 文件不存在 {f_freq}")

    # --- Test 3: MOMAP 速率提取 ---
    print("\n[Test 3] 速率日志读取")
    f_rate = MANUAL_DATA["files_rates"]
    if all(os.path.exists(f) for f in f_rate.values()):
        kr, kisc, kic = extract_rates_from_logs(f_rate["kr_log"], f_rate["kisc_log"], f_rate["kic_log"])
        ex = MANUAL_DATA["expect_rates"]
        check_val("Kr", kr, ex["Kr"])
        check_val("Kisc", kisc, ex["Kisc"])
        check_val("Kic", kic, ex["Kic"])
    else:
        print("❌ 跳过: 速率 Log 文件缺失")
        kr, kisc, kic = 0, 0, 0

    # --- Test 4: ORCA & EVC (简略) ---
    print("\n[Test 4] ORCA & EVC (快速检查)")
    # 这里仅做存在性检查和简单调用，详细值见 MANUAL_DATA 配置
    if os.path.exists(MANUAL_DATA["file_orca"]):
        hso = extract_orca_soc(MANUAL_DATA["file_orca"])
        print(f"ℹ️  ORCA Hso 提取: {hso:.5f} cm-1")
    
    if os.path.exists(MANUAL_DATA["file_evc"]):
        passed, _ = check_evc_reorg(".")
        print(f"ℹ️  EVC 检查通过: {passed}")

    # --- Test 5: PLQY 综合计算 (使用自动计算的 dE) ---
    print("\n[Test 5] PLQY 最终计算 (使用提取的速率 + 计算的 dE)")
    if kr > 0 and delta_E != 0:
        plqy, ratio = calculate_plqy(kr, kisc, kic, delta_E, Temp=300)
        
        print(f"输入参数:")
        print(f"  Kr={kr:.2e}, Kisc={kisc:.2e}, Kic={kic:.2e}")
        print(f"  dE={delta_E:.6f} Ha, Temp=300K")
        print("-" * 30)
        print(f"计算结果:")
        print(f"  Boltzmann Ratio n(S1)/n(T1) = {ratio:.4e}")
        print(f"  PLQY = {plqy:.2%} ({plqy:.6f})")
    else:
        print("❌ 无法计算 PLQY: 缺少速率或能级数据")

    print("\n" + "="*50)
    print("测试结束")

if __name__ == "__main__":
    run_tests()