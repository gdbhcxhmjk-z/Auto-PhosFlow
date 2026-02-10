#!/bin/bash
#SBATCH --output="%j.err"
#SBATCH --job-name="g16"
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=56
#SBATCH -n 56
#SBATCH -p planck-cpu01
#SBATCH --exclusive

# username 请修改为自己的名字，随意写，但只能是字母数字，不要加其他符号
export jobname=$1  ##这里xxx换成gjf前缀名字就可以
export username=zgshuai
# 这个id是帅组的id，如果你没加入就没有权限，需要换成自己的id
export project_id=46148

ulimit -s unlimited

# Make a directory in scr and copy .com and .g16 file to there.

export TMP_WORKDIR=/tmp/${username}_${SLURM_JOB_ID}
export GAUSS_SCRDIR=${TMP_WORKDIR}/g16_tmp

if [ ! -a $GAUSS_SCRDIR ]; then
   echo "Scratch directory $GAUSS_SCRDIR created."
   mkdir -p $GAUSS_SCRDIR
fi

echo "using $TMP_WORKDIR for work on node"
echo "Using $GAUSS_SCRDIR for temporary Gaussian 16 files."

cp $SLURM_SUBMIT_DIR/* $TMP_WORKDIR

module load gaussian-shuai/16B 


hostname

echo $SLURM_JOB_NODELIST

cd $TMP_WORKDIR

echo "Starting Gaussian run at" `date`
time g16 $TMP_WORKDIR/${jobname}                      
echo "Finished Gaussian run at" `date`


echo $SLURM_SUBMIT_DIR
cp $TMP_WORKDIR/${jobname}.* $SLURM_SUBMIT_DIR
echo "$TMP_WORKDIR"
echo "move SCRDIR to local dir hidden "
cp -r  $TMP_WORKDIR $SLURM_SUBMIT_DIR/.${username}_$SLURM_JOB_ID

export http_proxy=12.12.12.202:3128
export https_proxy=12.12.12.202:3128

bohr dataset create -n CE-${username}-$SLURM_JOB_ID  -p CE-${username}-$SLURM_JOB_ID  -i ${project_id} -l $TMP_WORKDIR

rm -rf $TMP_WORKDIR


