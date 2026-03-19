#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time
import csv
import subprocess
from pathlib import Path

STATUS_FILE = Path("status_report.csv")
RESULTS_DIR = Path("results")

def get_active_slurm_jobs():
    """获取真实在超算运行/排队的任务名"""
    try:
        user = os.environ.get('USER')
        # 使用 %.100j 防止名字截断
        cmd = f"squeue -u {user} -h -o '%.100j'"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            return set(res.stdout.strip().split())
        return set()
    except:
        return set()

def get_running_mols():
    """从数据库获取标记为 RUNNING 的分子"""
    running = []
    if not STATUS_FILE.exists(): return running
    with open(STATUS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Status') == 'RUNNING':
                running.append((row['Name'], row.get('Current_Stage', 'Unknown')))
    return running

def get_tail_log(log_path, lines=3):
    """读取日志文件的最后几行"""
    if not log_path.exists():
        return "[无 workflow.log 文件]"
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read().strip().splitlines()
            if not content: return "[workflow.log 为空]"
            # 过滤掉每次循环开头的标志位，只取有用的信息
            useful_lines = [l for l in content if ">>> Cycle Start <<<" not in l]
            return "\n".join([f"      | {l}" for l in useful_lines[-lines:]])
    except Exception as e:
        return f"[读取日志失败: {e}]"

def diagnose():
    print("==================================================")
    print(" 🏥 Auto-PhosFlow 工作流健康全景诊断")
    print("==================================================\n")

    print("🔍 1. 正在同步 Slurm 队列与本地数据库...")
    active_jobs = get_active_slurm_jobs()
    db_running = get_running_mols()
    
    print(f"   - 数据库中 RUNNING 占用名额: {len(db_running)} 个")
    print(f"   - Slurm 实际活跃相关任务数 : {len(active_jobs)} 个\n")

    healthy_mols = []
    zombie_mols = []
    limbo_mols = []
    transition_mols = [] # [新增] 过渡状态分子

    print("🔬 2. 正在跨层级靶向诊断每一个 RUNNING 分子...")
    for mol, stage in db_running:
        found_dirs = list(RESULTS_DIR.rglob(mol))
        if not found_dirs:
            limbo_mols.append((mol, "本地 Results 文件夹彻底丢失", stage))
            continue
            
        mol_dir = found_dirs[0]
        
        # 诊断维度 A：是否报错了但没被抓住？
        fatal_err = mol_dir / "FATAL_ERROR.txt"
        if fatal_err.exists():
            limbo_mols.append((mol, "已存在 FATAL_ERROR 但未释放名额", stage))
            continue

        # 诊断维度 B：寻找僵尸 (有 slurm 脚本但没在跑)
        is_zombie = False
        active_scripts = []
        for slurm_file in mol_dir.rglob("run.slurm"):
            step_dir = slurm_file.parent
            job_done = step_dir / "job.done"
            
            if not job_done.exists():
                active_scripts.append(step_dir.name)
                job_name_in_script = None
                try:
                    with open(slurm_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.startswith("#SBATCH --job-name="):
                                job_name_in_script = line.split("=", 1)[1].strip().strip('"').strip("'")
                                break
                except: pass
                
                if job_name_in_script and job_name_in_script not in active_jobs:
                    is_zombie = True
                    break

        if is_zombie:
            zombie_mols.append((mol, f"卡在步骤: {active_scripts[0]} (生成了脚本但没排队)", stage))
            continue
            
        # 诊断维度 C：健康 vs 过渡 vs 卡死
        is_healthy = False
        for slurm_file in mol_dir.rglob("run.slurm"):
             if not (slurm_file.parent / "job.done").exists():
                 is_healthy = True
                 break
                 
        if is_healthy:
            healthy_mols.append(mol)
        else:
            # [升级逻辑] 提取目录下所有文件的最后修改时间
            try:
                latest_mtime = max(f.stat().st_mtime for f in mol_dir.rglob('*') if f.is_file())
                minutes_since_active = (time.time() - latest_mtime) / 60
            except ValueError:
                minutes_since_active = 9999
                
            if minutes_since_active < 10:
                # 10分钟内有文件变动，说明只是算完了在等 batch_manager 轮询
                transition_mols.append((mol, f"上一步刚完成 {minutes_since_active:.1f} 分钟前，等待下一轮提交", stage))
            else:
                # 超过10分钟没动静，确诊为卡死
                wf_log = mol_dir / "workflow.log"
                last_logs = get_tail_log(wf_log)
                limbo_mols.append((mol, f"已停滞 {minutes_since_active:.1f} 分钟 (未生成下一步脚本)", stage, last_logs))

    # ================= 输出报告 =================
    print("\n================ 📋 诊断报告 📋 ================")
    print(f"🟢 健康运行中 (在排队或计算): {len(healthy_mols)} 个")
    
    print(f"\n🔵 正在过渡中 (刚算完等待主程序轮询流转): {len(transition_mols)} 个")
    for m, reason, stage in transition_mols:
        print(f"  - {m} | {reason} | 当前阶段: {stage}")

    print(f"\n🔴 僵尸任务 (生成了脚本但超算里没在跑): {len(zombie_mols)} 个")
    for m, reason, stage in zombie_mols:
        print(f"  - {m} | {reason}")

    print(f"\n🟡 幽灵死锁状态 (真实卡死 / 霸占名额): {len(limbo_mols)} 个")
    for item in limbo_mols:
        if len(item) == 4:
            m, reason, stage, logs = item
            print(f"  - {m} | 当前阶段: {stage}")
            print(f"      [状态] {reason}")
            print(f"      [Log 遗言]:\n{logs}")
            print(f"      [建议] 检查遗言。无法修复请 touch FATAL_ERROR.txt。")
        else:
            m, reason, stage = item
            print(f"  - {m} | {reason} | 阶段: {stage}")
            
    print("==================================================")

if __name__ == "__main__":
    diagnose()