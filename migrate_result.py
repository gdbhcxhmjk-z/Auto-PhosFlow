# migrate_result.py
import os
import subprocess
from pathlib import Path
import shutil

# ================= 远端服务器配置区 =================
REMOTE_USER = "root"               # 例如: zhangwenjie
REMOTE_HOST = "ercm1428943.bohrium.tech"           # 例如: 192.168.1.100
REMOTE_DIR  = "/share/Pt/fully_completed"   # 远端存放计算结果的绝对路径
# (强烈建议在此前配置好两台服务器的 SSH 密钥免密登录，否则脚本在后台会被卡在要求输入密码的阶段)
# ====================================================

def migrate_completed_tasks():
    print("🚀 Background Migration Started...")
    
    # 1. 扫描状态表，获取所有 COMPLETED 分子名单
    completed_mols = []
    try:
        with open("status_report.csv", "r") as f:
            for line in f:
                if "COMPLETED" in line:
                    completed_mols.append(line.split(",")[0].strip())
    except FileNotFoundError:
        return

    results_dir = Path("results")
    if not results_dir.exists(): return

    # 2. 遍历比对本地文件
    for mol in completed_mols:
        found_dirs = list(results_dir.rglob(mol))
        if not found_dirs:
            continue # 本地已经没了，说明前几轮早就成功送走并删除了

        mol_dir = found_dirs[0]
        round_name = mol_dir.parent.name # 比如 round0 
        
        remote_target = f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}/{round_name}/"
        
        # 提前在远端创建对应的 round 目录，防止 rsync 找不到路径报错
        subprocess.run(["ssh", f"{REMOTE_USER}@{REMOTE_HOST}", f"mkdir -p {REMOTE_DIR}/{round_name}"], check=False)

        # 构建 rsync 断点续传命令
        cmd = ["rsync", "-avz", str(mol_dir), remote_target]
        print(f"  -> Syncing {mol} to remote server...")
        
        # 执行上传
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 3. 严格判定：只有 rsync 状态码为 0 (完全成功无中断)，才敢销毁本地数据
        if result.returncode == 0:
            print(f"  ✅ {mol} perfectly synced. Nuking local copy to free space...")
            try:
                shutil.rmtree(mol_dir)
            except Exception as e:
                print(f"  ❌ Failed to remove local copy {mol_dir}: {e}")
        else:
            print(f"  ⚠️ Rsync for {mol} was interrupted or failed. Will try again next cycle.\nError:\n{result.stderr}")

if __name__ == "__main__":
    migrate_completed_tasks()