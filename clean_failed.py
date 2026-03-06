#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import shutil
from pathlib import Path

# ================= 配置区域 =================
STATUS_FILE = Path("status_report.csv")
RESULTS_DIR = Path("results")
MOLECULES_DIR = Path("molecules")
ABANDONED_DIR = Path("abandoned_molecules") # 废弃分子存放的专属目录
# ===========================================

def get_failed_molecules():
    """从 CSV 中读取状态为 FAILED 的分子列表"""
    failed_mols = []
    if not STATUS_FILE.exists():
        print(f"[错误] 找不到状态文件: {STATUS_FILE}")
        return failed_mols
        
    with open(STATUS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Status') == 'FAILED':
                failed_mols.append(row['Name'])
    return failed_mols

def clean_and_archive():
    print("🔍 正在读取状态数据库...")
    failed_mols = get_failed_molecules()
    
    if not failed_mols:
        print("🎉 没有发现任何 FAILED 状态的分子，系统非常健康！")
        return

    print(f"🗑️ 发现 {len(failed_mols)} 个被标记为 FAILED 的分子。")
    print("\n==================================================")
    print("即将在以下目录中执行搜索与清理：")
    print(f"  1. 彻底删除 {RESULTS_DIR}/[round]/[分子名] 的计算结果")
    print(f"  2. 移动 {MOLECULES_DIR}/[round]/[分子名].xyz 到 {ABANDONED_DIR}/[round]/")
    print("==================================================\n")
    
    # 安全确认
    confirm = input(f"⚠️ 确定要清理这 {len(failed_mols)} 个分子吗？此操作将删除计算结果！(y/n): ").strip().lower()
    if confirm != 'y':
        print("👋 已取消清理操作。")
        return

    # 确保废弃文件夹根目录存在
    ABANDONED_DIR.mkdir(parents=True, exist_ok=True)
    
    results_deleted = 0
    molecules_moved = 0
    
    print("\n🧹 开始执行清理...")
    
    for mol in failed_mols:
        # ---------------------------------------------------------
        # 1. 穿透搜索并删除 Results 下的文件夹
        # ---------------------------------------------------------
        # 查找所有名字刚好等于 mol 且是文件夹的路径 (过滤掉近似名字)
        result_paths = [p for p in RESULTS_DIR.rglob(mol) if p.is_dir() and p.name == mol]
        
        for rp in result_paths:
            try:
                shutil.rmtree(rp)
                print(f"  [删除] 已移除计算结果: {rp}")
                results_deleted += 1
            except Exception as e:
                print(f"  [失败] 无法删除目录 {rp}: {e}")

        # ---------------------------------------------------------
        # 2. 穿透搜索并移动 Molecules 下的 .xyz 文件
        # ---------------------------------------------------------
        xyz_name = f"{mol}.xyz"
        xyz_paths = [p for p in MOLECULES_DIR.rglob(xyz_name) if p.is_file() and p.name == xyz_name]
        
        for xp in xyz_paths:
            try:
                # 提取它所属的 round 文件夹名称 (例如 'round0')
                round_name = xp.parent.name
                
                # 在废弃区创建对应的 round 文件夹
                target_dir = ABANDONED_DIR / round_name
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # 移动文件
                target_path = target_dir / xyz_name
                shutil.move(str(xp), str(target_path))
                print(f"  [归档] 已移动分子结构: {xp} -> {target_path}")
                molecules_moved += 1
            except Exception as e:
                print(f"  [失败] 无法移动文件 {xp}: {e}")

    print("\n==================================================")
    print("✅ 清理完成！")
    print(f"📊 统计: 删除了 {results_deleted} 个结果文件夹，归档了 {molecules_moved} 个分子结构。")
    print(f"💡 提示：这些分子在 status_report.csv 中的 FAILED 记录已被保留作为历史追溯。")

if __name__ == "__main__":
    clean_and_archive()