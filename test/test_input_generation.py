# -*- coding: utf-8 -*-
import sys
import os
import shutil
from pathlib import Path

# 挂载 lib 和 config
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

try:
    from lib.orca_handler import write_orca_inp
    from lib.momap_handler import write_momap_inp
    from lib.slurm_utils import write_orca_slurm, write_momap_slurm
    from config import MOMAP_PARAMS # <--- 关键：导入你的配置
    print(f"✅ 成功加载核心库与配置")
except ImportError as e:
    print(f"❌ 加载失败: {e}")
    sys.exit(1)

# 创建一个临时的输出目录
TEST_OUT = Path("test_gen_output")
if TEST_OUT.exists(): shutil.rmtree(TEST_OUT)
TEST_OUT.mkdir()

def check_content(file_path, keywords_exist=[], keywords_missing=[]):
    """检查文件内容"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    all_pass = True
    for kw in keywords_exist:
        if kw not in content:
            print(f"  ❌ 缺失关键内容: '{kw}'")
            all_pass = False
    
    for kw in keywords_missing:
        if kw in content:
            print(f"  ❌ 包含错误内容: '{kw}'")
            all_pass = False
            
    if all_pass:
        print(f"  ✅ 文件 {file_path.name} 内容检查通过")

def test_orca_generation():
    print("\n=== Test 1: ORCA 输入文件生成 ===")
    folder = TEST_OUT / "orca"
    folder.mkdir()
    
    dummy_coords = "Pt 0.0 0.0 0.0\nC 1.0 0.0 0.0"
    
    inp_path = write_orca_inp(folder, "test_job", dummy_coords, nproc=56, mem_per_core=8000)
    
    check_content(inp_path, 
        keywords_exist=[
            "NewGTO Pt", "SARC-DKH-TZVP",
            "! TPSSh", "RIJCOSX",
            "* xyz 0 1"
        ],
        keywords_missing=["NewGTO C"]
    )
    
    write_orca_slurm(folder, "test_job", "orca.inp", nproc=56)

def test_momap_generation():
    print("\n=== Test 2: MOMAP 输入文件生成 (动态验证 Config) ===")
    folder = TEST_OUT / "momap"
    folder.mkdir()
    
    # 辅助函数：从 config 中获取预期值，如果没有定义则取默认值
    def get_cfg(mode, key, default):
        # 优先级: Specific Mode > Common
        val = MOMAP_PARAMS.get(mode, {}).get(key)
        if val is None:
            val = MOMAP_PARAMS['common'].get(key, default)
        return val

    # --- Case A: Kr ---
    print(">> 正在生成 Kr 输入...")
    write_momap_inp(folder, mode='kr', config_params=MOMAP_PARAMS, 
                    Ead=0.1, EDME=0.5, DSFile="evc.cart.dat")
    
    # 获取 Config 中的预期值
    exp_dushin = get_cfg('kr', 'DUSHIN', '.f.')
    exp_bf = get_cfg('kr', 'Broadenfunc', 'frequency')
    
    # 重命名方便查看
    (folder / "momap.inp").rename(folder / "momap_kr.inp")
    
    check_content(folder / "momap_kr.inp",
        keywords_exist=[
            f"DUSHIN        = {exp_dushin}",       # 动态检查
            f"Broadenfunc   = \"{exp_bf}\"",       # 动态检查
            "EDME          = 0.5"                  # 运行时参数
        ]
    )

    # --- Case B: Kic ---
    print(">> 正在生成 Kic 输入...")
    write_momap_inp(folder, mode='kic', config_params=MOMAP_PARAMS,
                    Ead=0.1, DSFile="evc.cart.dat", CoulFile="evc.cart.nac")
    
    exp_dushin_kic = get_cfg('kic', 'DUSHIN', '.t.')
    exp_fwhm_kic = get_cfg('kic', 'FWHM', 500)
    
    (folder / "momap.inp").rename(folder / "momap_kic.inp")
    
    check_content(folder / "momap_kic.inp",
        keywords_exist=[
            f"DUSHIN        = {exp_dushin_kic}",
            f"FWHM          = {exp_fwhm_kic}",
            "CoulFile      = \"evc.cart.nac\""
        ]
    )
    
    # --- Case C: Kisc ---
    print(">> 正在生成 Kisc 输入...")
    write_momap_inp(folder, mode='kisc', config_params=MOMAP_PARAMS,
                    Ead=0.1, Hso=0.89, DSFile="evc.dint.dat")

    exp_bf_kisc = get_cfg('kisc', 'Broadenfunc', 'time') # 这里会读取你 config 里的 frequency
    
    check_content(folder / "momap.inp",
        keywords_exist=[
            "&isc_tvcf",
            "Hso           = 0.89",
            f"Broadenfunc   = \"{exp_bf_kisc}\"" # <--- 现在这里会自适应你的 config
        ]
    )

if __name__ == "__main__":
    test_orca_generation()
    test_momap_generation()
    print("\n测试完成。")