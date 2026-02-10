# -*- coding: utf-8 -*-
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator
from time import time

# ==================== 美化配置区域 ====================
def set_pub_style():
    """设置科研发表级别的绘图风格"""
    config = {
        # 字体设置
        "font.family": "serif",
        "font.serif": ["Times New Roman"], # 强制使用 Times New Roman
        "font.weight": "bold",             # 全局字体加粗
        "font.size": 14,                   # 基础字号
        
        # 坐标轴标签和标题
        "axes.labelweight": "bold",        # 轴标签加粗
        "axes.linewidth": 2,               # 图框边框加粗
        "axes.titlesize": 16,
        
        # 刻度设置
        "xtick.top": True,                 # 上方显示刻度
        "ytick.right": True,               # 右侧显示刻度
        "xtick.direction": "in",           # 刻度向内
        "ytick.direction": "in",
        "xtick.major.width": 2,            # 主刻度线加粗
        "ytick.major.width": 2,
        "xtick.minor.width": 1.5,          # 次刻度线加粗
        "ytick.minor.width": 1.5,
        "xtick.major.size": 6,             # 刻度线长度
        "ytick.major.size": 6,
        
        # 图例
        "legend.fontsize": 12,
        "legend.frameon": False,           # 去掉图例的边框，看起来更现代
        "legend.loc": "upper left",
    }
    plt.rcParams.update(config)

# ==================== 功能函数区域 ====================

def find_FWHM(FC_emi, wn, wl):
    # 找到强度大于 0.5 的区域
    where_res = np.where(FC_emi > 0.5)[0]
    
    if len(where_res) == 0:
        return 0, 0, 0, 0
        
    FWHM_wn = abs(wn[where_res[-1]] - wn[where_res[0]])
    FWHM_wl = abs(wl[where_res[0]] - wl[where_res[-1]])

    # 修正后的找峰值逻辑
    max_idx = np.argmax(FC_emi) 
    peak_wn = wn[max_idx]
    peak_wl = wl[max_idx]
    
    return peak_wn, peak_wl, FWHM_wn, FWHM_wl

def plot_spec_beautiful(file_spec, flag_save=True, plt_name='spectrum.png'):
    print(f'Processing: {file_spec}')
    time0 = time()
    
    # 1. 应用美化风格
    set_pub_style()

    # 2. 读取数据
    try:
        with open(file_spec, 'r') as fi_spec:
            lines = fi_spec.readlines()[2:]
            dat = np.array([[float(f) for f in line.split()] for line in lines])
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    wn = dat[:, 2]
    wl = dat[:, 3]
    FC_abs = dat[:, 4]
    FC_emi = dat[:, 5]

    # 计算峰值（用于自动确定范围）
    peak_wn, peak_wl, FWHM_wn, FWHM_wl = find_FWHM(FC_emi, wn, wl)

    # 自动确定 X 轴范围 (以发射峰为中心，左右各扩展 200nm)
    # 你也可以手动写死：wl_min, wl_max = 300, 800
    wl_min = max(250, peak_wl - 200) 
    wl_max = peak_wl + 250
    
    # 数据切片与排序
    mask = (wl >= wl_min) & (wl <= wl_max)
    wl_plot = wl[mask]
    FC_emi_plot = FC_emi[mask]
    FC_abs_plot = FC_abs[mask]

    sort_idx = np.argsort(wl_plot)
    wl_plot = wl_plot[sort_idx]
    FC_emi_plot = FC_emi_plot[sort_idx]
    FC_abs_plot = FC_abs_plot[sort_idx]

    # 3. 开始绘图
    fig, ax = plt.subplots(figsize=(8, 6), dpi=300) # dpi=300 保证高清

    # --- 绘制吸收谱 (紫色) ---
    # 使用 fill_between 填充颜色，看起来更有质感
    ax.plot(wl_plot, FC_abs_plot, color='#6A0DAD', linewidth=2.5, label='Absorption') # 2.5 线宽
    ax.fill_between(wl_plot, 0, FC_abs_plot, color='#6A0DAD', alpha=0.15) # 0.15 透明度填充

    # --- 绘制发射谱 (橙色) ---
    ax.plot(wl_plot, FC_emi_plot, color='#FF8C00', linewidth=2.5, label='Fluorescence')
    ax.fill_between(wl_plot, 0, FC_emi_plot, color='#FF8C00', alpha=0.25)

    # 4. 坐标轴调整
    ax.set_xlabel('Wavelength (nm)', fontweight='bold')
    ax.set_ylabel('Normalized Intensity', fontweight='bold')
    
    ax.set_xlim(wl_min, wl_max)
    ax.set_ylim(0, 1.05) # 留一点顶部空间

    # 刻度设置
    ax.xaxis.set_major_locator(MultipleLocator(100)) # 主刻度间隔 100
    ax.xaxis.set_minor_locator(AutoMinorLocator(5))  # 次刻度自动分5份
    ax.yaxis.set_major_locator(MultipleLocator(0.2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))

    # 所有的 Tick label (数字) 也会因为 rcParams 自动加粗并使用 Times New Roman

    # 图例
    ax.legend(prop={'weight':'bold', 'size':12})

    # 5. 保存
    plt.tight_layout() # 自动紧凑布局，防止标签被切掉
    
    if flag_save:
        plt.savefig(plt_name, transparent=False)
        print(f'Saved high-res plot to: {plt_name}')
    
    plt.close()
    print(f'Plot time = {time() - time0:.5f} s')
    
    return peak_wn, peak_wl, FWHM_wn, FWHM_wl

# 测试用例 (需要确保目录下有文件)
if __name__ == "__main__":
    # 假设当前目录下有这个文件
    plot_spec_beautiful("spec_tvcf.dat")