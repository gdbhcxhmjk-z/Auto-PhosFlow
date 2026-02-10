import os
import shutil
import sys
import math

# ================= 配置区域 (在这里修改文件名会真正生效) =================
# KIC 计算参数配置
param = {
    "DUSHIN": ".t.",
    "tmax": 3000,          
    "dt": 0.01,
    "isgauss": ".t.",
    "BroadenType": "gaussian",  # gaussian / lorentzian
    "Broadenfunc": "frequency",        # frequency / time
    "FWHM": "500",
    "NScale": 20,          
}

slurm_name = "momap.slurm"
nprocs = "56"

# 输入文件定义 (如果您的文件名不同，请在此处修改)
FILE_S0_LOG = "s0.log"
FILE_S1_LOG = "s1.log"
FILE_EVC_DAT = "evc.cart.dat"     # 对应 momap.inp 中的 DSFile
FILE_EVC_NAC = "evc.cart.nac"     # 对应 momap.inp 中的 CoulFile

# ================= 功能函数 =================

def try_copy(start, end):
    try:
        shutil.copy(start, end)
    except IOError as e:
        print(f"Unable to copy file {start}: {e}")
    except:
        print(f"Unexpected error copying {start}", sys.exc_info())

def create_dirs(file_path):
    if os.path.exists(file_path) is False:
        os.makedirs(file_path)

def create_kic_inp(file, DUSHIN, Ead, ds_file_name, coul_file_name, 
                   tmax=3000, dt=0.001, isgauss=".f.", 
                   BroadenType="gaussian", Broadenfunc="frequency", FWHM=500):
    """
    生成 KIC 输入文件
    ds_file_name: 对应 DSFile (通常是 evc.cart.dat)
    coul_file_name: 对应 CoulFile (通常是 evc.cart.nac)
    """
    file_data = f"""do_ic_tvcf_ft   = 1
do_ic_tvcf_spec = 1

&ic_tvcf
  DUSHIN        = {DUSHIN}
  Temp          = 300 K
  tmax          = {tmax} fs
  dt            = {dt} fs
  Ead           = {Ead}  au
  DSFile        = "{ds_file_name}"
  CoulFile      = "{coul_file_name}"
  isgauss       = {isgauss}
  BroadenType   = "{BroadenType}"
  Broadenfunc   = "{Broadenfunc}"
  FWHM          = {FWHM} cm-1
  GFile         = "spec.tvcf.gauss.dat"
  NScale        = {param["NScale"]}
  Emax          =  0.3 au
  logFile       = "ic.tvcf.log"
  FtFile        = "ic.tvcf.ft.dat"
  FoFile        = "ic.tvcf.fo.dat"
/
"""
    with open(file, 'w') as f:
        f.writelines(file_data)

def create_momap_slurm(slurm_filename, job_name):
    file_data = f"""#!/bin/bash
#SBATCH --time=1000:00:00
#SBATCH --job-name=kic_{job_name}
#SBATCH --output="momap.err"
#SBATCH --nodes=1
#SBATCH --ntasks-per-node={nprocs}
#SBATCH -n {nprocs}
#SBATCH -p planck-cpu01
#SBATCH --exclusive

#========================================================
source /home/software/momap/2024a/env.sh
srun hostname -s | sort -n > hosts

#========================================================
momap.py -i momap.inp -n {nprocs}  -f  hosts
"""
    with open(slurm_filename, 'w') as f:
        f.writelines(file_data)

def get_energy_from_log(log_file):
    energy = 0
    if os.path.isfile(log_file):
        with open(log_file) as f:
            lines = f.readlines()
        scf_energy = 0
        tot_energy = 0
        
        for l in lines:
            if "SCF Done" in l:
                scf_energy = float(l.split()[4])
            if "Total Energy" in l:
                tot_energy = float(l.split()[-1])
        
        if tot_energy != 0:
            energy = tot_energy
        elif scf_energy != 0:
            energy = scf_energy
    else:
        print(f"Warning: {log_file} not found!")
    return energy

def get_Ead_energy(s1, s0):
    if s1 == 0 or s0 == 0:
        print("Error: Energy is 0, cannot calculate Ead.")
        return 0
    diff = s1 - s0
    # ev = diff * 27.2114
    
    # if ev < 0: 
    #     print(f"Warning: S1 energy ({s1}) is lower than S0 ({s0})? using abs value.")
    #     ev = abs(ev)
        
    # corrected = 1240 / (1240 / ev * 1.1794 + 28.9285)
    # au = corrected / 27.2114
    return diff

def get_kic_dirname(parameters):
    name = "Dushin_" + ("on" if parameters["DUSHIN"] == ".t." else "off")
    name += "-" + "tmax_" + str(parameters["tmax"])
    name += "-" + "type_" + parameters["BroadenType"]
    name += "-" + "FWHM_" + str(parameters["FWHM"])
    return name

def run_kic_single():
    current_dir = os.getcwd()
    molecule_name = os.path.basename(current_dir)
    
    print(f"Processing KIC for directory: {current_dir}")

    # 1. 检查必要文件 (使用变量)
    if not os.path.exists(FILE_EVC_NAC):
        print(f"Error: {FILE_EVC_NAC} is missing! KIC calculation requires NAC file.")
        return
    if not os.path.exists(FILE_EVC_DAT):
        print(f"Error: {FILE_EVC_DAT} is missing!")
        return

    # 2. 计算 Ead
    s0_en = get_energy_from_log(FILE_S0_LOG)
    s1_en = get_energy_from_log(FILE_S1_LOG)
    
    print(f"S0 Energy: {s0_en}")
    print(f"S1 Energy: {s1_en}")

    if s0_en == 0 or s1_en == 0:
        print("Error: Could not extract energies. Exiting.")
        return

    Ead = get_Ead_energy(s1_en, s0_en)
    print(f"Calculated Ead (au): {Ead:.6f}")

    # 3. 创建 KIC 文件夹
    kic_subdir_name = get_kic_dirname(param)
    work_dir = os.path.join(current_dir, kic_subdir_name)
    create_dirs(work_dir)
    print(f"Work dir created: {work_dir}")

    # 4. 复制文件 (使用变量指定源文件)
    # 目的目录是文件夹，文件名保持不变
    try_copy(FILE_EVC_DAT, work_dir)
    try_copy(FILE_EVC_NAC, work_dir)
    
    # 5. 生成输入文件并提交
    os.chdir(work_dir)
    
    # 关键修改：在这里将文件名变量传给函数
    create_kic_inp("momap.inp", 
                   param["DUSHIN"], Ead,
                   ds_file_name=FILE_EVC_DAT,     # 传入 evc.cart.dat 变量
                   coul_file_name=FILE_EVC_NAC,   # 传入 evc.cart.nac 变量
                   tmax=param["tmax"], 
                   dt=param["dt"], 
                   isgauss=param["isgauss"], 
                   BroadenType=param["BroadenType"], 
                   Broadenfunc=param["Broadenfunc"], 
                   FWHM=param["FWHM"])
    
    create_momap_slurm(slurm_name, molecule_name)
    
    print(f"Submitting KIC job in {work_dir}...")
    os.system(f"sbatch {slurm_name}")
    
    os.chdir(current_dir)
    print("KIC Job Setup Done.")

if __name__ == "__main__":
    run_kic_single()