#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import subprocess
from pathlib import Path

def get_active_slurm_submit_dirs():
    """获取当前用户在 Slurm 中所有活跃任务的提交目录"""
    try:
        user = os.environ.get('USER')
        cmd = f"squeue -u {user} -h -o '%Z'"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if res.returncode != 0:
            print(f"[警告] squeue 命令执行失败: {res.stderr}")
            return set()

        dirs = set()
        for line in res.stdout.splitlines():
            line = line.strip()
            if line:
                dirs.add(str(Path(line).resolve()))
        return dirs

    except Exception as e:
        print(f"[错误] 无法获取 Slurm 队列信息: {e}")
        return set()

def extract_job_name(slurm_script):
    """从 run.slurm 文件中提取 #SBATCH --job-name 的值"""
    try:
        with open(slurm_script, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith("#SBATCH --job-name="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None

def get_running_molecules(csv_file="status_report.csv"):
    """从 CSV 中读取状态为 RUNNING 的分子"""
    running_mols = []
    if not os.path.exists(csv_file):
        print(f"[错误] 找不到状态文件: {csv_file}")
        return running_mols
        
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Status') == 'RUNNING':
                running_mols.append(row['Name'])
    return running_mols

def find_and_clean_zombies():
    print("🔍 正在扫描 Slurm 队列...")
    active_submit_dirs = get_active_slurm_submit_dirs()
    print(f"📊 当前队列中共有 {len(active_submit_dirs)} 个活跃任务目录。\n")

    print("📁 正在读取 status_report.csv 状态...")
    running_mols = get_running_molecules()
    if not running_mols:
        print("✅ 数据库中没有标记为 RUNNING 的分子，无需诊断。")
        return

    print(f"🏃 数据库中标记为 RUNNING 的分子有 {len(running_mols)} 个。\n")

    results_dir = Path("results")
    zombies = set()   # 用 set 去重，元素是 step_dir(Path)

    print("🧟 正在对 RUNNING 状态的分子进行僵尸靶向诊断...")
    for mol in running_mols:
        # 只找目录，避免误匹配到同名文件
        found_dirs = [p for p in results_dir.rglob(mol) if p.is_dir()]
        if not found_dirs:
            print(f"  [跳过] 未找到分子目录: {mol}")
            continue

        # 正常应只会有一个；若有多个，先取第一个并提示
        if len(found_dirs) > 1:
            print(f"  [警告] 发现多个同名分子目录，默认使用第一个: {found_dirs[0]}")

        mol_dir = found_dirs[0].resolve()

        # 只遍历当前 RUNNING 分子下的 run.slurm
        for slurm_file in mol_dir.rglob("run.slurm"):
            step_dir = slurm_file.parent.resolve()
            job_done = step_dir / "job.done"

            # 已完成的步骤不可能是 zombie
            if job_done.exists():
                continue

            # 核心判断：
            # 如果该步骤目录不在当前 Slurm 活跃任务的提交目录列表中，
            # 则说明这个步骤的旧 run.slurm 只是残骸，属于 zombie
            if str(step_dir) not in active_submit_dirs:
                zombies.add(step_dir)

    zombies = sorted(zombies)

    if not zombies:
        print("🎉 太棒了！处于 RUNNING 状态的分子一切正常，没有发现僵尸任务。")
        return

    print(f"\n🚨 警告：发现了 {len(zombies)} 个僵尸任务！(占用着 RUNNING 名额但已停止运行)")
    for i, z in enumerate(zombies, 1):
        print(f"  [{i}] {z}")

    print("\n==================================================")
    print("🛠️  你想如何处理这些僵尸任务？")
    print("  [1] 一键复活 (删除僵尸脚本，batch_manager 轮询时会自动重跑)")
    print("  [2] 彻底放弃 (打上 FATAL_ERROR 标记，batch_manager 会将其置为 FAILED 并释放名额)")
    print("  [0] 暂不处理 (退出程序)")

    choice = input("\n请输入你的选择 (0/1/2): ").strip()

    if choice == '1':
        count = 0
        for z in zombies:
            try:
                slurm_file = z / "run.slurm"
                if slurm_file.exists():
                    slurm_file.unlink()
                    count += 1

                # 可选：顺手清理一些明显的僵尸残留，不动输入和上游结果
                for stale_name in ["hosts", "stdout.txt"]:
                    stale_file = z / stale_name
                    if stale_file.exists():
                        try:
                            stale_file.unlink()
                        except Exception:
                            pass

            except Exception as e:
                print(f"  [失败] 无法清理 {z}: {e}")

        print(f"✅ 成功清理了 {count} 个僵尸步骤的 run.slurm。等待 batch_manager 重新拉起计算。")

    elif choice == '2':
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 按“分子根目录”去重，而不是按步骤目录去重
        mol_roots = sorted({z.parent.resolve() for z in zombies})
        count = 0

        for mol_root in mol_roots:
            fatal_file = mol_root / "FATAL_ERROR.txt"
            try:
                with open(fatal_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{now}] FATAL ERROR: Molecule abandoned manually via Hunter script (Zombie state).\n")
                count += 1
            except Exception as e:
                print(f"  [失败] 无法标记 {mol_root}: {e}")

        print(f"✅ 成功为 {count} 个分子打上了放弃标记，名额将在下次轮询时释放。")

    else:
        print("👋 已取消操作。")

if __name__ == "__main__":
    find_and_clean_zombies()