# migrate_result.py
import csv
import shutil
import subprocess
from pathlib import Path

# ================= 远端服务器配置区 =================
REMOTE_USER = "root"
REMOTE_HOST = "ercm1428943.bohrium.tech"
REMOTE_DIR  = "/share/Pt/fully_completed"
# ====================================================


def has_valid_file(path, min_size=100):
    path = Path(path)
    return path.exists() and path.is_file() and path.stat().st_size >= min_size


def is_truly_completed_dir(mol_dir):
    """
    与 batch_manager 中保持一致的最终完成判定。
    即使 CSV 写着 COMPLETED，本地产物不全也不允许迁移。
    """
    mol_dir = Path(mol_dir)

    if not mol_dir.exists():
        return False

    if (mol_dir / "FATAL_ERROR.txt").exists():
        return False

    required_exists = [
        mol_dir / "REPORT_PLQY.txt",

        mol_dir / "08_MOMAP_Kr" / "job.done",
        mol_dir / "08_MOMAP_Kr" / "spec.tvcf.log",
        mol_dir / "08_MOMAP_Kr" / "spec.tvcf.spec.dat",

        mol_dir / "09_MOMAP_Kisc" / "job.done",
        mol_dir / "09_MOMAP_Kisc" / "isc.tvcf.log",

        mol_dir / "10_MOMAP_Kic" / "job.done",
        mol_dir / "10_MOMAP_Kic" / "ic.tvcf.log",
    ]

    if not all(p.exists() for p in required_exists):
        return False

    required_nonempty = [
        mol_dir / "REPORT_PLQY.txt",
        mol_dir / "08_MOMAP_Kr" / "spec.tvcf.log",
        mol_dir / "08_MOMAP_Kr" / "spec.tvcf.spec.dat",
        mol_dir / "09_MOMAP_Kisc" / "isc.tvcf.log",
        mol_dir / "10_MOMAP_Kic" / "ic.tvcf.log",
    ]

    return all(has_valid_file(p, min_size=100) for p in required_nonempty)


def load_completed_molecules(status_csv="status_report.csv"):
    """
    严格读取 CSV 的 Status 列：
    只接受 Status == COMPLETED
    不再用 '整行包含 COMPLETED' 这种危险写法。
    """
    completed_mols = []

    csv_path = Path(status_csv)
    if not csv_path.exists():
        return completed_mols

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = row.get("Status", "").strip()
            name = row.get("Name", "").strip()

            if status == "COMPLETED" and name:
                completed_mols.append(name)

    return completed_mols


def migrate_completed_tasks():
    print("🚀 Background Migration Started...")

    completed_mols = load_completed_molecules("status_report.csv")
    if not completed_mols:
        print("  [Info] No COMPLETED molecules found in status_report.csv")
        return

    results_dir = Path("results")
    if not results_dir.exists():
        return

    for mol in completed_mols:
        found_dirs = list(results_dir.rglob(mol))
        if not found_dirs:
            continue  # 本地已不存在，通常代表之前已成功迁移并删除

        mol_dir = found_dirs[0]

        # 关键修补：
        # 即使 CSV 说它 COMPLETED，也必须检查本地关键产物确实齐全
        if not is_truly_completed_dir(mol_dir):
            print(f"  [Skip] {mol} is marked COMPLETED, but final artifacts are incomplete. Skip migration.")
            continue

        round_name = mol_dir.parent.name
        remote_target = f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}/{round_name}/"

        subprocess.run(
            ["ssh", f"{REMOTE_USER}@{REMOTE_HOST}", f"mkdir -p {REMOTE_DIR}/{round_name}"],
            check=False
        )

        cmd = ["rsync", "-avz", str(mol_dir), remote_target]
        print(f"  -> Syncing {mol} to remote server...")

        result = subprocess.run(cmd, capture_output=True, text=True)

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