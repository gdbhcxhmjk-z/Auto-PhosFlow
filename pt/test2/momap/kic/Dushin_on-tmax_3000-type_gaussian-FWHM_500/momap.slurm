#!/bin/bash
#SBATCH --time=1000:00:00
#SBATCH --job-name=kic_kic
#SBATCH --output="momap.err"
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=56
#SBATCH -n 56
#SBATCH -p planck-cpu01
#SBATCH --exclusive

#========================================================
source /home/software/momap/2024a/env.sh
srun hostname -s | sort -n > hosts

#========================================================
momap.py -i momap.inp -n 56  -f  hosts
