# lib/orca_handler.py
import os
from pathlib import Path

# 定义重金属列表，用于触发特殊基组
HEAVY_METALS = ["Pt", "Ir", "Os", "Ru", "Rh", "Re"]

def write_orca_inp(folder, job_name, coords_str, nproc=56, mem_per_core=4000):
    """
    生成 ORCA 输入文件 (.inp)
    
    Args:
        folder (Path): 目标文件夹
        job_name (str): 任务名
        coords_str (str): 原子坐标字符串 (格式: Atom X Y Z)
        nproc (int): 并行核数
        mem_per_core (int): 单核内存 (MB)
    """
    inp_path = folder / "orca.inp"
    
    # 1. 分析坐标中的元素，判断是否需要特殊基组
    elements = set()
    lines = coords_str.strip().split('\n')
    for line in lines:
        parts = line.split()
        if parts:
            elements.add(parts[0]) # 假设第一列是元素符号
            
    # 检测重金属 (取交集)
    found_heavy_metals = list(elements.intersection(HEAVY_METALS))
    
    # 2. 构建内容
    content = []
    
    # --- 并行控制 (虽然提交脚本里有 sed 插入，但这里写上也无妨，作为默认值) ---
    # content.append(f"%pal nprocs {nproc} end") 
    # 为了兼容你的 sed 逻辑，这里先不写 %pal，留给 run.slurm 去插入
    
    # --- 路由行 (Keywords) ---
    # 注意：RIJCOSX 和 defgrid3 是加速关键
    content.append("! TPSSh DKH2 DKH-def2-tzvp RIJCOSX SARC/J CPCM(DCM) miniprint TightSCF defgrid3")
    content.append("")
    
    # --- 内存设置 ---
    content.append(f"%maxcore {mem_per_core}")
    content.append("")
    
    # --- 基组特殊定义 (如果存在重金属) ---
    if found_heavy_metals:
        content.append("%basis")
        for metal in found_heavy_metals:
            # 你的模版是用 SARC-DKH-TZVP
            content.append(f'NewGTO {metal} "SARC-DKH-TZVP" end')
        content.append("end")
        content.append("")
    
    # --- TD-DFT 设置 (SOC 计算核心) ---
    content.append("%tddft")
    content.append("nroots      50         # no of roots to determine")
    content.append("DoSOC       true")
    content.append("PrintLevel  3")
    content.append("TDA         false      # Tamm-Dancoff approx")
    content.append("triplets    true")
    content.append("end")
    content.append("")
    
    # --- 坐标块 ---
    # 注意：T1 态通常是 Triplet，但 ORCA 计算 SOC 时通常基于当前结构算激发的 Singlet 和 Triplet
    # 这里的电荷和自旋：
    # 如果是基于 T1 结构算 SOC，通常基态设为 0 1 (闭壳层 Singlet 参考态) 或者是 T1 参考态？
    # *重要*: ORCA 的 TD-DFT 模块通常从闭壳层 Singlet (0 1) 参考态出发计算激发态。
    # 即使结构是 T1 优化的，计算本身通常以此结构作为 "Ground State Geometry" 进行垂直激发计算。
    # 所以这里写 * xyz 0 1 是正确的（代表电荷0，自旋1的参考态）。
    content.append("* xyz 0 1")
    content.append(coords_str.strip())
    content.append("*")
    
    # 写入文件
    with open(inp_path, 'w') as f:
        f.write("\n".join(content))
    
    print(f"  [Gen] ORCA input generated: {inp_path}")
    return inp_path