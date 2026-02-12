# lib/slurm_utils.py
import os
from config import ENV_PATHS

def write_g16_slurm(folder, job_name, nproc=56, partition="planck-cpu01"):
    """
    生成 Gaussian 提交脚本 (基于你的 g16 模板)
    使用本地 /tmp 加速 I/O
    """
    script_path = folder / "run.slurm"
    username = ENV_PATHS['username']
    
    content = f"""#!/bin/bash
#SBATCH --output="%j.err"
#SBATCH --job-name="{job_name}"
#SBATCH --nodes=1
#SBATCH --ntasks-per-node={nproc}
#SBATCH -n {nproc}
#SBATCH -p {partition}
#SBATCH --exclusive

# --- 变量设置 ---
export jobname="{job_name}.gjf"
export username="{username}"
ulimit -s unlimited

# 提取文件主体
job_base=${{jobname%.*}}

# --- 目录准备 (/tmp) ---
export TMP_WORKDIR=/tmp/${{username}}_${{SLURM_JOB_ID}}
export GAUSS_SCRDIR=${{TMP_WORKDIR}}/g16_tmp

if [ ! -d "$GAUSS_SCRDIR" ]; then
   echo "Scratch directory $GAUSS_SCRDIR created."
   mkdir -p $GAUSS_SCRDIR
fi

echo "Working directory: $TMP_WORKDIR"
# 注意：此时我们已经在 Python 创建的 step 目录中，所以使用 $SLURM_SUBMIT_DIR
cp $SLURM_SUBMIT_DIR/$jobname $TMP_WORKDIR/
# 如果有旧的 chk 也拷贝过去
if [ -f "$SLURM_SUBMIT_DIR/$job_base.chk" ]; then
    cp $SLURM_SUBMIT_DIR/$job_base.chk $TMP_WORKDIR/
fi

# --- 环境加载 ---
module load gaussian-shuai/16B 
hostname

# --- 执行 ---
cd $TMP_WORKDIR
echo "Starting Gaussian run at $(date)"

# 运行 G16
time g16 "$jobname"
run_status=$?

echo "Finished Gaussian run at $(date)"

if [ $run_status -eq 0 ] && [ -f "$job_base.chk" ]; then
    echo "Generating fchk file from $job_base.chk ..."
    formchk "$job_base.chk" "$job_base.fchk"
fi

# --- 回传 ---
echo "Copying result files back..."
# 排除 slurm 脚本和 err 日志，防止覆盖
find . -maxdepth 1 -type f ! -name "*.slurm" ! -name "*.err" -exec cp {{}} $SLURM_SUBMIT_DIR/ \\;

# 备份隐藏目录 (可选，如果磁盘空间紧张可注释)
# cp -r $TMP_WORKDIR $SLURM_SUBMIT_DIR/.${{username}}_${{SLURM_JOB_ID}}

# --- 标记完成与清理 ---
if [ $run_status -eq 0 ]; then
    cd $SLURM_SUBMIT_DIR
    touch job.done
fi

rm -rf $TMP_WORKDIR
echo "Job completed."
"""
    with open(script_path, 'w') as f:
        f.write(content)
    return script_path

def write_orca_slurm(folder, job_name, input_file="orca.inp", nproc=56, partition="planck-cpu01"):
    """
    生成 ORCA 提交脚本 (基于你的 ORCA 模板)
    使用 Scratch 目录
    """
    script_path = folder / "run.slurm"
    username = ENV_PATHS['username']
    scratch_root = ENV_PATHS['scratch_root']
    
    content = f"""#!/bin/bash
#SBATCH --output="%j.err"
#SBATCH --job-name="{job_name}"
#SBATCH --nodes=1
#SBATCH --ntasks-per-node={nproc}
#SBATCH -n {nproc}
#SBATCH -p {partition}
#SBATCH --exclusive

# --- 变量设置 ---
export jobname="{input_file}"
INPUT=${{jobname%.*}}
ulimit -s unlimited

# --- 路径配置 (来自 config.py) ---
EXEC="{ENV_PATHS['orca_exec']}"

module purge
module load gcc/8.3.0
export PATH=$PATH:{ENV_PATHS['orca_mpi_bin']}
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:{ENV_PATHS['orca_mpi_lib']}
export PATH=$PATH:{ENV_PATHS['orca_lib']}
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:{ENV_PATHS['orca_lib']}

# --- Scratch 准备 ---
# 使用你在 config 中定义的 scratch 路径
SCRDIR={scratch_root}/${{username}}_${{SLURM_JOB_ID}}

if [ ! -d "$SCRDIR" ]; then
   echo "Scratch directory $SCRDIR created."
   mkdir -p $SCRDIR
fi
export SCRDIR
echo "Using $SCRDIR"

# 拷贝输入文件
cp $SLURM_SUBMIT_DIR/* $SCRDIR/

cd $SCRDIR
srun hostname -s | sort -n > hosts

# --- 动态修改 inp 文件 (保留你的 sed 逻辑) ---
# 插入并行设置
# 注意：如果 Python 生成 inp 时已经写了 %pal，这里可能会重复，建议只用一种方式。
# 这里为了兼容你的脚本习惯，保留 sed，但请确保 inp 模板里没有写 %pal
sed -i "1i end" ${{INPUT}}.inp
sed -i "1i %pal nprocs {nproc}" ${{INPUT}}.inp

# --- 执行 ---
echo "ORCA start at $(date)"
time ${{EXEC}} ${{INPUT}}.inp > ${{INPUT}}.out
run_status=$?
echo "ORCA finished at $(date)"

# --- 回传与清理 ---
# 删除不必要的文件
rm -f ${{SCRDIR}}/${{INPUT}}.inp
rm -f ${{SCRDIR}}/stdout.txt
# 回传所有结果 (因为我们在独立的子目录下，全拷回来没问题)
mv ${{SCRDIR}}/* $SLURM_SUBMIT_DIR/

# --- 标记完成 ---
if [ $run_status -eq 0 ]; then
    cd $SLURM_SUBMIT_DIR
    touch job.done
fi

rm -rf $SCRDIR
"""
    with open(script_path, 'w') as f:
        f.write(content)
    return script_path

def write_momap_slurm(folder, job_name, input_file="momap.inp", nproc=56, partition="planck-cpu01"):
    """
    生成 MOMAP 提交脚本
    直接在当前目录运行 (无需临时文件夹)
    """
    script_path = folder / "run.slurm"
    
    content = f"""#!/bin/bash
#SBATCH --time=1000:00:00
#SBATCH --job-name="{job_name}"
#SBATCH --output="momap.err"
#SBATCH --nodes=1
#SBATCH --ntasks-per-node={nproc}
#SBATCH -n {nproc}
#SBATCH -p {partition}
#SBATCH --exclusive

# --- 环境 ---
source {ENV_PATHS['momap_env']}
srun hostname -s | sort -n > hosts

# --- 执行 ---
# 注意：使用 python 生成的 input 文件名
momap.py -i {input_file} -n {nproc} -f hosts

if [ $? -eq 0 ]; then
    touch job.done
fi
"""
    with open(script_path, 'w') as f:
        f.write(content)
    return script_path