#!/bin/bash
#SBATCH --output="momap.err"
#SBATCH --job-name="momap"
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=56
#SBATCH -n 56
#SBATCH -p planck-cpu01
#SBATCH --exclusive


source /home/software/momap/2024a/env.sh
srun hostname -s | sort -n > hosts
momap -i  momap.inp  -f  hosts
