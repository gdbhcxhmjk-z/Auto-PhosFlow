# lib/analysis_handler.py
import re
import math
import numpy as np
import matplotlib
# 强制使用非交互式后端，防止在集群上报错 "no display name"
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator
from pathlib import Path

# --- 常量 ---
KB_HARTREE = 3.1668114e-6  # Boltzmann constant in Hartree/K

# ==================== 速率提取区域 ====================

def extract_rates_from_logs(kr_log, kisc_log, kic_log):
    # 强制类型转换，防止报错
    kr_log = Path(kr_log)
    kisc_log = Path(kisc_log)
    kic_log = Path(kic_log)
    
    kr = 0.0
    kisc = 0.0
    kic = 0.0
    
    # 1. 提取 Kr (保持原逻辑，正则匹配非常稳定)
    if kr_log.exists():
        with open(kr_log, 'r') as f: content = f.read()
        match = re.search(r"radiative rate\s+\(\d+\):.*?([\d\.E\+\-]+)\s+/s", content)
        if match: kr = float(match.group(1))
    
    # 2. 提取 Kisc (保持原逻辑)
    if kisc_log.exists():
        with open(kisc_log, 'r') as f: content = f.read()
        match = re.search(r"Intersystem crossing Ead is.*?rate is\s+([\d\.E\+\-]+)\s+s-1", content)
        if match: kisc = float(match.group(1))
            
    # 3. 提取 Kic (新逻辑：基于表头锚定)
    if kic_log.exists():
        with open(kic_log, 'r') as f:
            lines = f.readlines()
            
        found_header = False
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # --- 阶段 1: 寻找表头 ---
            # 目标: #1Energy(Hartree) ... 6kic(s^{-1}) ...
            if "1Energy" in line and "6kic" in line:
                found_header = True
                continue # 跳过表头本身，进入下一行
            
            # --- 阶段 2: 解析数据 ---
            if found_header:
                # 忽略可能的注释行或分隔线
                if line.startswith('#') or line.startswith('-'):
                    continue
                
                parts = line.split()
                # 确保列数足够 (至少6列)
                if len(parts) >= 6:
                    try:
                        # 再次验证第一列是否为数字 (能量)，确保万无一失
                        float(parts[0]) 
                        
                        # 提取第 6 列 (index 5)
                        kic = float(parts[5])
                        break # 成功提取，任务结束
                    except ValueError:
                        # 如果转换失败，说明可能读到了奇怪的行，继续往下找
                        continue

    print(f"  [Rates] Kr={kr:.2e}, Kisc={kisc:.2e}, Kic={kic:.2e}")
    return kr, kisc, kic

def calculate_plqy(kr, kisc, kic, delta_E_hartree, Temp=300):
    """
    计算 PLQY 和 占据数比例。
    PLQY = kr / (kr + kisc + kic * ratio)
    Ratio n(S1)/n(T1) = exp(- dE / kT)
    注意: dE 必须是 S1 - T1 (如果是正值，说明 S1 > T1，ratio < 1)
    """
    # 占据数比例 (S1 / T1)
    # 假设 delta_E 是正值 (S1能量高于T1)
    if delta_E_hartree < 0:
        print(f"  [Warn] Delta E ({delta_E_hartree}) < 0. Is S1 lower than T1?")
    
    kt = KB_HARTREE * Temp
    # 防止指数溢出
    try:
        ratio = math.exp(-delta_E_hartree / kt)
    except OverflowError:
        ratio = 0.0

    # 有效总速率 k_tot
    k_tot = kr + kisc + (kic * ratio)
    
    if k_tot == 0:
        plqy = 0.0
    else:
        plqy = kr / k_tot
        
    return plqy, ratio

# ==================== 绘图区域 (基于你的脚本) ====================

def set_pub_style():
    """设置科研发表级别的绘图风格"""
    config = {
        "font.family": "serif",
        "font.serif": ["Times New Roman"],
        "font.weight": "bold",
        "font.size": 14,
        "axes.labelweight": "bold",
        "axes.linewidth": 2,
        "xtick.top": True,
        "ytick.right": True,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.major.width": 2,
        "ytick.major.width": 2,
        "legend.fontsize": 12,
        "legend.frameon": False,
    }
    plt.rcParams.update(config)

def find_FWHM(FC_emi, wn, wl):
    # 鲁棒性修改：不假设数据已归一化，使用 max/2 作为阈值
    max_val = np.max(FC_emi)
    if max_val == 0: return 0,0,0,0
    
    threshold = max_val / 2.0
    where_res = np.where(FC_emi > threshold)[0]
    
    if len(where_res) == 0:
        return 0, 0, 0, 0
        
    FWHM_wn = abs(wn[where_res[-1]] - wn[where_res[0]])
    FWHM_wl = abs(wl[where_res[0]] - wl[where_res[-1]])

    max_idx = np.argmax(FC_emi) 
    peak_wn = wn[max_idx]
    peak_wl = wl[max_idx]
    
    return peak_wn, peak_wl, FWHM_wn, FWHM_wl

def plot_spectrum_analysis(file_spec, output_dir):
    """
    读取光谱文件，绘图，并返回峰值数据。
    """
    file_spec = Path(file_spec)
    output_dir = Path(output_dir)
    plt_name = output_dir / f"{file_spec.stem}.png"
    
    if not file_spec.exists():
        print(f"  [Error] Spectrum file not found: {file_spec}")
        return None

    # 1. 读取数据
    try:
        with open(file_spec, 'r') as f:
            lines = f.readlines()[2:] # 跳过头两行
            dat = np.array([[float(v) for v in line.split()] for line in lines if line.strip()])
    except Exception as e:
        print(f"  [Error] Failed to read spec: {e}")
        return None

    if dat.shape[0] == 0:
        return None

    wn = dat[:, 2]
    wl = dat[:, 3]
    FC_abs = dat[:, 4]
    FC_emi = dat[:, 5] # 发射谱通常是第6列

    # 2. 计算峰值
    peak_wn, peak_wl, FWHM_wn, FWHM_wl = find_FWHM(FC_emi, wn, wl)

    # 3. 绘图
    set_pub_style()
    
    # 自动范围
    wl_min = max(250, peak_wl - 200) 
    wl_max = peak_wl + 250
    mask = (wl >= wl_min) & (wl <= wl_max)
    
    if not np.any(mask): # 防止空切片
        mask = np.ones_like(wl, dtype=bool)

    wl_plot = wl[mask]
    FC_emi_plot = FC_emi[mask]
    FC_abs_plot = FC_abs[mask]
    
    # 排序
    sort_idx = np.argsort(wl_plot)
    wl_plot = wl_plot[sort_idx]
    FC_emi_plot = FC_emi_plot[sort_idx]
    FC_abs_plot = FC_abs_plot[sort_idx]

    fig, ax = plt.subplots(figsize=(8, 6), dpi=300)
    
    # 归一化用于绘图美观 (可选)
    abs_max = np.max(FC_abs_plot) if np.max(FC_abs_plot) > 0 else 1
    emi_max = np.max(FC_emi_plot) if np.max(FC_emi_plot) > 0 else 1
    
    ax.plot(wl_plot, FC_abs_plot/abs_max, color='#6A0DAD', linewidth=2.5, label='Absorption')
    ax.fill_between(wl_plot, 0, FC_abs_plot/abs_max, color='#6A0DAD', alpha=0.15)
    
    ax.plot(wl_plot, FC_emi_plot/emi_max, color='#FF8C00', linewidth=2.5, label='Fluorescence')
    ax.fill_between(wl_plot, 0, FC_emi_plot/emi_max, color='#FF8C00', alpha=0.25)

    ax.set_xlabel('Wavelength (nm)', fontweight='bold')
    ax.set_ylabel('Normalized Intensity', fontweight='bold')
    ax.set_xlim(wl_min, wl_max)
    ax.set_ylim(0, 1.05)
    
    ax.xaxis.set_major_locator(MultipleLocator(100))
    ax.xaxis.set_minor_locator(AutoMinorLocator(5))
    ax.yaxis.set_major_locator(MultipleLocator(0.2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax.legend(prop={'weight':'bold', 'size':12})
    
    plt.tight_layout()
    plt.savefig(plt_name, transparent=False)
    plt.close()
    
    print(f"  [Plot] Saved spectrum to {plt_name}")
    return peak_wl, FWHM_wl