# -*- coding: utf-8 -*-
import os
import shutil
from pathlib import Path

# 定义分子名和根目录
MOL_NAME = "mock_test_mol"
ROOT_DIR_NAME = "mock_workflow_run"

def create_mock_environment():
    current_dir = Path(__file__).parent
    root_dir = current_dir / ROOT_DIR_NAME
    
    # 清理旧数据
    if root_dir.exists(): shutil.rmtree(root_dir)
    root_dir.mkdir()
    print(f"创建测试根目录: {root_dir}")

    # 创建分子目录
    mol_dir = root_dir / MOL_NAME
    mol_dir.mkdir()
    
    # 定义文件夹结构
    dirs = {
        's0_opt':  mol_dir / "01_S0_Opt",
        's0_freq': mol_dir / "02_S0_Freq",
        's1_opt':  mol_dir / "03_S1_Opt",
        's1_freq': mol_dir / "04_S1_Freq",
        't1_opt':  mol_dir / "05_T1_Opt",
        't1_freq': mol_dir / "06_T1_Freq",
        'orca':    mol_dir / "07_ORCA_SOC",
        'kr':      mol_dir / "08_MOMAP_Kr",
        'kisc':    mol_dir / "09_MOMAP_Kisc",
        'kic':     mol_dir / "10_MOMAP_Kic",
    }

    # 创建文件夹并标记 job.done
    for key, folder in dirs.items():
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "job.done").touch() 

    print("正在分发测试文件并伪造中间状态...")

    def copy_from_test_root(filename, target_path):
        src = current_dir / filename
        if src.exists():
            shutil.copy(src, target_path)
        else:
            print(f"⚠️  警告: 源文件 {filename} 不存在")

    def create_dummy_log(path, energy):
        with open(path, 'w') as f:
            f.write(f" SCF Done:  E(RTPSSh) =  {energy:.6f}     A.U. after   11 cycles\n")
            f.write(" Normal termination of Gaussian 16\n")

    # 1. Gaussian Logs
    create_dummy_log(dirs['s0_freq'] / f"{MOL_NAME}_s0_freq.log", energy=-1000.0)
    create_dummy_log(dirs['s1_freq'] / f"{MOL_NAME}_s1_freq.log", energy=-999.988) 
    create_dummy_log(dirs['t1_freq'] / f"{MOL_NAME}_t1_freq.log", energy=-999.999)

    # 2. ORCA Log
    copy_from_test_root("soc.out", dirs['orca'] / f"{MOL_NAME}_orca.out")

    # 3. MOMAP Logs
    copy_from_test_root("spec.tvcf.log", dirs['kr'] / "spec.tvcf.log")
    copy_from_test_root("spec.tvcf.spec.dat", dirs['kr'] / "spec.tvcf.spec.dat")
    copy_from_test_root("isc.tvcf.log", dirs['kisc'] / "isc.tvcf.log")
    copy_from_test_root("ic.tvcf.log", dirs['kic'] / "ic.tvcf.log")

    # === [关键修复] 4. 伪造 EVC 完成状态 ===
    # Kr & Kisc 使用 evc.dint.dat
    for k in ['kr', 'kisc']:
        folder = dirs[k]
        # 拷贝真实文件 (用于后续读取)
        copy_from_test_root("evc.dint.dat", folder / "evc.dint.dat")
        # 创建 evc.done 标记，内容指向使用的文件
        with open(folder / "evc.done", "w") as f:
            f.write("evc.dint.dat")

    # Kic 使用 evc.cart.dat
    folder = dirs['kic']
    # 我们暂时用 evc.dint.dat 冒充 evc.cart.dat (仅为了跑通 Mock)
    src_evc = current_dir / "evc.dint.dat"
    if src_evc.exists():
        shutil.copy(src_evc, folder / "evc.cart.dat")
        shutil.copy(src_evc, folder / "evc.cart.nac") # 还需要 NAC 文件
    
    with open(folder / "evc.done", "w") as f:
        f.write("evc.cart.dat")

    print("\n✅ Mock 环境准备完毕 (已修复 EVC 状态)！")

if __name__ == "__main__":
    create_mock_environment()