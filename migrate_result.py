#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import shutil
import subprocess
from pathlib import Path

# ================= 配置区域 =================
STATUS_FILE = Path("status_report.csv")
RESULTS_DIR = Path("results")

# 云服务器配置 (通过 SSH/SCP/RSYNC)
REMOTE_USER = "your_username"        # 云端用户名
REMOTE_HOST = "192.168.1.100"        # 云端IP或域名
REMOTE_BASE_DIR = "/path/to/cloud/storage" # 云端存放数据的根目录

# 迁移模式
USE_RSYNC = True    # 推荐为True，支持断点续传。若云端无rsync，可改为False使用scp
DELETE_AFTER_MIGRATE = True # 传输成功后是否立刻删除本地文件夹以释放空间
# ===========================================

def get_completed_molecules():
    """解析 CSV，将完成的分子分为全完结和半完结两组"""
    full_completed = []
    kr_only_completed = []
    
    if not STATUS_FILE.exists():
        print(f"❌ 找不到状态文件: {STATUS_FILE}")
        return full_completed, kr_only_completed
        
    with open(STATUS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Status') == 'COMPLETED':
                name = row['Name']
                remark = row.get('Remark', '')
                
                # 根据 Remark 区分
                if 'Partial Completed' in remark or 'Kr' in remark:
                    kr_only_completed.append(name)
                else:
                    full_completed.append(name)
                    
    return full_completed, kr_only_completed

def run_transfer(source_path, target_type, round_name):
    """
    执行文件传输
    source_path: 本地文件夹路径 (如 results/round0/idx_123)
    target_type: "fully_completed" 或 "kr_only_completed"
    """
    # 构造云端目标路径：/云端目录/分类/roundX/
    remote_target_dir = f"{REMOTE_BASE_DIR}/{target_type}/{round_name}/"
    remote_full_path = f"{REMOTE_USER}@{REMOTE_HOST}:{remote_target_dir}"
    
    # 第一步：在云端创建对应目录
    mkdir_cmd = f"ssh {REMOTE_USER}@{REMOTE_HOST} 'mkdir -p {remote_target_dir}'"
    subprocess.run(mkdir_cmd, shell=True, stderr=subprocess.DEVNULL)
    
    # 第二步：传输数据
    if USE_RSYNC:
        # rsync -avz 
        # a: 归档模式(保留权限时间), v: 详细输出, z: 传输时压缩
        cmd = f"rsync -avz '{source_path}' {remote_full_path}"
    else:
        # scp -r
        cmd = f"scp -r '{source_path}' {remote_full_path}"
        
    print(f"  ⬆️  正在传输: {source_path.name} -> {target_type} ...")
    res = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    
    if res.returncode == 0:
        return True
    else:
        print(f"  ❌ 传输失败: {res.stderr.strip()}")
        return False

def migrate():
    print("🔍 正在扫描已完成的计算任务...")
    full_mols, kr_mols = get_completed_molecules()
    
    total_mols = len(full_mols) + len(kr_mols)
    if total_mols == 0:
        print("✅ 当前没有处于 COMPLETED 状态的分子需要迁移。")
        return
        
    print(f"📦 发现 {total_mols} 个可迁移分子：")
    print(f"   - 🏅 完全算完 (含PLQY报告): {len(full_mols)} 个")
    print(f"   - 🥈 仅完成 Kr (等待后续计算): {len(kr_mols)} 个")
    
    confirm = input("\n⚠️ 是否开始向云端迁移并释放本地空间？(y/n): ").strip().lower()
    if confirm != 'y':
        print("👋 迁移取消。")
        return
        
    success_count = 0
    freed_mols = 0
    
    # 合并处理清单 (分子名, 目标分类)
    tasks = [(mol, "fully_completed") for mol in full_mols] + \
            [(mol, "kr_only_completed") for mol in kr_mols]
            
    for mol, target_type in tasks:
        # 穿透搜索找到实际路径 (适配 roundX)
        found_dirs = list(RESULTS_DIR.rglob(mol))
        if not found_dirs:
            print(f"  [跳过] 找不到分子 {mol} 的结果文件夹。可能已被清理。")
            continue
            
        source_path = found_dirs[0]
        if not source_path.is_dir(): continue
        
        round_name = source_path.parent.name
        
        # 执行传输
        is_success = run_transfer(source_path, target_type, round_name)
        
        # 如果传输成功且开启了删除选项，释放本地空间
        if is_success:
            success_count += 1
            if DELETE_AFTER_MIGRATE:
                try:
                    shutil.rmtree(source_path)
                    print(f"  🗑️  已删除本地文件夹释放空间: {source_path}")
                    freed_mols += 1
                except Exception as e:
                    print(f"  ⚠️ 删除本地文件夹失败: {e}")

    print("\n==================================================")
    print(f"✅ 迁移任务结束！")
    print(f"📊 统计: 成功传输 {success_count}/{total_mols} 个分子。")
    if DELETE_AFTER_MIGRATE:
        print(f"🧹 空间释放: 成功清理 {freed_mols} 个本地文件夹。")
    print("==================================================")

if __name__ == "__main__":
    migrate()