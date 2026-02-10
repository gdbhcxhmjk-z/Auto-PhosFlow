#!/bin/bash
#SBATCH --output="%j.err"
#SBATCH --job-name="soc"
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=56
#SBATCH -n 56
#SBATCH -p planck-cpu01
#SBATCH --exclusive


# Define variable "INPUT"

export jobname=$1 
INPUT=${jobname%.*}


ulimit -s unlimited

# Define running command variable, need full path!
EXEC=/home/gongcunxi/public/software/orca_6_0_1_linux_x86-64_shared_openmpi416/orca

# Define MPI

module purge
module load gcc/8.3.0

# mpi 
export PATH=$PATH:/home/gongcunxi/public/software/openmpi-4.1.6/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/home/gongcunxi/public/software/openmpi-4.1.6/lib

# orca
export PATH=$PATH:/home/gongcunxi/public/software/orca_6_0_1_linux_x86-64_shared_openmpi416
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/home/gongcunxi/public/software/orca_6_0_1_linux_x86-64_shared_openmpi416

# Make a scratch directory if it doesn't already exist.

# we have ib and small disk on node
SCRDIR=/home/gongcunxi/scratch/${username}_$SLURM_JOB_ID
if [ ! -a $SCRDIR ]; then
   echo "Scratch directory $SCRDIR created."
   mkdir -p $SCRDIR
fi
export SCRDIR
echo "Using $SCRDIR for temporary ORCA files."

# go to work dir
cd $SLURM_SUBMIT_DIR

cp $SLURM_SUBMIT_DIR/* $SCRDIR
cd $SCRDIR
srun hostname -s | sort -n > hosts

echo "ORCA job start at" `date`
cat hosts

# edit .inp for parallel

#NP=`cat hosts|wc -l`
echo "Numbers of Processors:  $SLURM_NPROCS"
sed -i "1i end" ${INPUT}.inp
sed -i "1i %pal nprocs $SLURM_NPROCS" ${INPUT}.inp

# run program

time ${EXEC} ${INPUT}.inp > ${INPUT}.out

rm ${SCRDIR}/${INPUT}.inp
rm ${SCRDIR}/stdout.txt
mv ${SCRDIR}/* $SLURM_SUBMIT_DIR

echo "ORCA job finished at" `date`
echo "Work Directory is $SLURM_SUBMIT_DIR"

rm -rf $SCRDIR

