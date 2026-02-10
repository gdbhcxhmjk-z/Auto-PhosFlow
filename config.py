# config.py
ENV_PATHS = {
    # ORCA 相关
    'orca_exec': "/home/gongcunxi/public/software/orca_6_0_1_linux_x86-64_shared_openmpi416/orca",
    'orca_mpi_bin': "/home/gongcunxi/public/software/openmpi-4.1.6/bin",
    'orca_mpi_lib': "/home/gongcunxi/public/software/openmpi-4.1.6/lib",
    'orca_lib': "/home/gongcunxi/public/software/orca_6_0_1_linux_x86-64_shared_openmpi416",
    
    # MOMAP 相关
    'momap_env': "/home/software/momap/2024a/env.sh",
    
    # 你的用户名 (用于 Scratch 路径)
    'username': "zgshuai", # 或者使用 os.getenv('USER')
    
    # Scratch 根目录
    'scratch_root': "/home/gongcunxi/scratch"
}

G16_PARAMS = {
    # --- 资源设置 ---
    'nproc': 56,
    'mem_opt': "256GB",   # 优化步骤内存
    'mem_freq': "256GB", # 频率步骤内存建议大一点

    # --- S0 态 ---
    # 1. S0 结构优化
    's0_opt': "#p opt TPSSh/def2svp scrf=solvent=CH2Cl2 empiricaldispersion=gd3bj IOp(3/174=1000000,3/175=2238200,3/177=452900,3/178=4655000) nosymm",
    # 2. S0 频率 (读取 s0_opt.chk)
    's0_freq': "#p freq TPSSh/def2svp scrf=solvent=CH2Cl2 empiricaldispersion=gd3bj IOp(3/174=1000000,3/175=2238200,3/177=452900,3/178=4655000) nosymm",

    # --- S1 态 (Singlet) ---
    # 3. S1 结构优化 (基于 S0 结构，使用 TD-DFT)
    's1_opt': "#p td(singlet,nstate=10) opt TPSSh/def2svp scrf=solvent=CH2Cl2 empiricaldispersion=gd3bj IOp(3/174=1000000,3/175=2238200,3/177=452900,3/178=4655000) nosymm",
    # 4. S1 频率 (读取 s1_opt.chk)
    's1_freq': "#p td(singlet,nstate=10) freq TPSSh/def2svp scrf=solvent=CH2Cl2 empiricaldispersion=gd3bj IOp(3/174=1000000,3/175=2238200,3/177=452900,3/178=4655000) nosymm",

    # --- T1 态 (Triplet) ---
    # 5. T1 结构优化 (基于 S0 结构，使用 Unrestricted DFT，Spin=3)
    't1_opt': "#p opt TPSSh/def2svp scrf=solvent=CH2Cl2 empiricaldispersion=gd3bj IOp(3/174=1000000,3/175=2238200,3/177=452900,3/178=4655000) nosymm",
    # 6. T1 频率 (读取 t1_opt.chk)
    't1_freq': "#p freq TPSSh/def2svp scrf=solvent=CH2Cl2 empiricaldispersion=gd3bj IOp(3/174=1000000,3/175=2238200,3/177=452900,3/178=4655000) nosymm"
}

# --- MOMAP 参数配置 ---
# config.py

# config.py

MOMAP_PARAMS = {
    # --- Common ---
    'common': {
        'Temp': 300,
        'tmax': 3000,
        'dt': 0.01,
        'NScale': 10,
        'Emin': -0.3, 'Emax': 0.3, 'dE': 0.00001,
        'DUSHIN': '.f.', 'HERZ': '.f.',
    },
    
    # --- Specific ---
    'kr': {
        'DUSHIN': '.f.', 'HERZ': '.f.', 'spectra0': '.f.',
        'isgauss': '.f.', 'BroadenType': 'gaussian', 'Broadenfunc': 'frequency',
        'FWHM': 20, 'EDMA': 1.0,
    },
    
    'kisc': {
        'DUSHIN': '.f.', 'HERZ': '.f.', 'spectra0': '.f.',
        'isgauss': '.f.', 'BroadenType': 'gaussian', 'Broadenfunc': 'frequency',
        'FWHM': 50,
    },
    
    # Kic: 内转换
    'kic': {
        'DUSHIN': '.t.',       # 必须开启
        'HERZ': '.f.',
        'spectra0': '.f.',     # 通常算速率不需要全谱
        
        # 展宽设置 (根据你的 snippet 调整)
        'isgauss': '.t.',
        'BroadenType': 'gaussian',
        'Broadenfunc': 'frequency', # 你 snippet 里是 frequency
        'FWHM': 500,           # <--- 调整为 500
        'NScale': 20,          # <--- 调整为 20
    }
}