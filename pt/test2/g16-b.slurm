#!/bin/bash
#SBATCH --output="%j.err"
#SBATCH --job-name="g16-test2"
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=56
#SBATCH -n 56
#SBATCH -p planck-cpu01
#SBATCH --exclusive

# --- 环境设置 ---
export jobname=$1 
export username=zgshuai
ulimit -s unlimited

# 提取文件主体名（例如从 15_1.com 中提取 15_1）
# 这样 cp ${job_base}.* 就能匹配到 15_1.log, 15_1.chk 等
job_base=${jobname%.*}

# --- 目录准备 ---
export TMP_WORKDIR=/tmp/${username}_${SLURM_JOB_ID}
export GAUSS_SCRDIR=${TMP_WORKDIR}/g16_tmp

if [ ! -d "$GAUSS_SCRDIR" ]; then
   echo "Scratch directory $GAUSS_SCRDIR created."
   mkdir -p $GAUSS_SCRDIR
fi

echo "Working directory: $TMP_WORKDIR"
cp $SLURM_SUBMIT_DIR/$jobname $TMP_WORKDIR/

# --- 加载 Gaussian ---
module load gaussian-shuai/16B 
hostname
echo "Nodes: $SLURM_JOB_NODELIST"

# --- 执行运算 ---
cd $TMP_WORKDIR
echo "Starting Gaussian run at $(date)"
# 明确指定输出 log 文件名
time g16 "$jobname"
echo "Finished Gaussian run at $(date)"

# --- 结果回传 ---
echo "Copying result files back to $SLURM_SUBMIT_DIR..."

# 逻辑：只拷贝文件(-type f)，排除 .slurm 和 .err 后缀
find . -maxdepth 1 -type f ! -name "*.slurm" ! -name "*.err" -exec cp {} $SLURM_SUBMIT_DIR/ \;

# 拷贝隐藏备份目录（包含所有中间过程文件）
echo "Moving SCRDIR to local hidden directory..."
cp -r $TMP_WORKDIR $SLURM_SUBMIT_DIR/.${username}_$SLURM_JOB_ID

# --- 清理阶段 ---
# 建议：初次运行先保持注释状态，确认结果文件已回传后再取消注释
rm -rf $TMP_WORKDIR

echo "Job completed."