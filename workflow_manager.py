#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import shutil
import re
import subprocess
from pathlib import Path
from datetime import datetime

# 引入配置和库
from config import G16_PARAMS, MOMAP_PARAMS
from lib.g16_handler import (
    write_gjf, 
    read_xyz_coords, 
    extract_geom_with_obabel, 
    check_imaginary_frequencies,
    check_job_elapsed_time, 
    check_g16_termination,
    check_g16_error
)
from lib.momap_handler import (
    write_momap_inp, 
    check_evc_reorg, 
    get_gaussian_energy,
    check_evc_err_file, 
    extract_orca_edme,
    extract_orca_soc
)
from lib.analysis_handler import extract_rates_from_logs, calculate_plqy, plot_spectrum_analysis
from lib.slurm_utils import write_g16_slurm, write_orca_slurm, write_momap_slurm

class MoleculeFlow:
    def __init__(self, name, xyz_file, root_dir):
        self.name = name
        self.xyz_file = Path(xyz_file)
        self.root = Path(root_dir) / name
        
        # 自动创建分子根目录
        self.root.mkdir(parents=True, exist_ok=True)
        
        # 目录映射
        self.dirs = {
            # Gaussian 步骤
            's0_opt':  self.root / "01_S0_Opt",
            's0_freq': self.root / "02_S0_Freq",
            's1_opt':  self.root / "03_S1_Opt",
            's1_freq': self.root / "04_S1_Freq",
            't1_opt':  self.root / "05_T1_Opt",
            't1_freq': self.root / "06_T1_Freq",
            't1_td':   self.root / "06b_T1_TD",
            # 后处理步骤
            'orca':    self.root / "07_ORCA_SOC",
            'evc_t1':  self.root / "07b_EVC_T1",   # <--- 新增: 专供 S0-T1
            'evc_s1':  self.root / "07c_EVC_S1",   # <--- 新增: 专供 S0-S1
            'kr':      self.root / "08_MOMAP_Kr",
            'kisc':    self.root / "09_MOMAP_Kisc",
            'kic':     self.root / "10_MOMAP_Kic",
        }
        
        # 错误标记文件
        self.error_file = self.root / "FATAL_ERROR.txt"

    def _mark_fatal_error(self, message):
        """标记致命错误并停止流程"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = f"[{timestamp}] FATAL ERROR:\n{message}\n"
        
        with open(self.error_file, 'a') as f:
            f.write(content)
            
        print(f"  \033[91m[STOP] {self.name} encountered fatal error: {message}\033[0m")

    def _is_failed(self):
        """检查当前分子是否已标记为失败"""
        return self.error_file.exists()

    def process(self, silent=True):
        """
        主流程控制
        silent=True: 静默模式，只打印关键动作(提交/报错/修复)，不打印重复的检查通过信息
        """
        # [修改] 只有非静默模式才打印标题
        if not silent:
            print(f"\n--- Processing {self.name} ---")
        
        # 0. 熔断检查
        if self._is_failed():
            if not silent:
                print(f"  [Skip] Molecule marked as failed. See {self.error_file}")
            return

        # --- 1. S0 State Cycle ---
        # [修改] 传递 silent 参数
        s0_ok = self._handle_gaussian_cycle('s0', 'xyz', self.xyz_file, 0, 1, silent)
        if not s0_ok: return

        s0_log = self.dirs['s0_opt'] / f"{self.name}_s0_opt.log"

        # --- 2. S1 State Cycle [恢复完整流程] ---
        s1_ok = self._handle_gaussian_cycle('s1', 'log', s0_log, 0, 1, silent)
        if not s1_ok: return

        # --- 3. T1 State Cycle [保留] ---
        t1_ok = self._handle_gaussian_cycle('t1', 'log', s0_log, 0, 3, silent)
        if not t1_ok: return
        
        # --- 3.5 T1 TD 计算 [新增] ---
        # 注意：使用 S0 闭壳层基态参考系计算激发态，因此 spin 填 1
        t1_td_ok = self._handle_td_step('t1_td', 't1_opt', charge=0, spin=1)
        if not t1_td_ok: return
        
        if not silent:
            print(f"  [Info] Gaussian stages completed. Ready for ORCA/MOMAP.")
        
        # --- 4. ORCA SOC Calculation [保留] ---
        self._handle_orca_step()
        
        # --- 5. MOMAP Logic (物理隔离的 EVC) ---
        s0_done = self._check_done(self.dirs['s0_freq'])
        s1_done = self._check_done(self.dirs['s1_freq'])
        t1_done = self._check_done(self.dirs['t1_freq'])
        orca_done = self._check_done(self.dirs['orca'])
        
        # 1. 独立执行 S0-T1 和 S0-S1 的 EVC
        evc_t1_ok = False
        if s0_done and t1_done:
            evc_t1_ok = self._handle_evc_t1()
            
        evc_s1_ok = False
        if s0_done and s1_done:
            evc_s1_ok = self._handle_evc_s1()

        # 2. 只有 EVC 就位后，才流转到对应的速率计算
        if evc_t1_ok and orca_done:
            self._handle_momap_kr()
            self._handle_momap_kisc()
            
        if evc_s1_ok:
            self._handle_momap_kic()

        # --- 6. Analysis (接入 T1 TD 能量) ---    
        kr_done = (self.dirs['kr'] / "job.done").exists()
        kisc_done = (self.dirs['kisc'] / "job.done").exists()
        kic_done = (self.dirs['kic'] / "job.done").exists()
        
        if kr_done and kisc_done and kic_done and t1_td_ok:
            self._run_final_analysis()

    # =========================================================================
    # 核心逻辑：高斯计算循环 (Opt + Freq + Imag Check + Retry)
    # =========================================================================
    def _handle_gaussian_cycle(self, state_label, source_type, source_file, charge, spin, silent=True):
        opt_key = f"{state_label}_opt"
        freq_key = f"{state_label}_freq"
        opt_dir = self.dirs[opt_key]
        freq_dir = self.dirs[freq_key]
        
        # --- 1. 检查 Opt 步骤 ---
        opt_log = opt_dir / f"{self.name}_{opt_key}.log"
        # ==========================================================
        # 优先检查 Gaussian Opt 是否直接报错退出
        has_err, err_msg = check_g16_error(opt_log)
        if has_err:
            self._mark_fatal_error(f"{opt_key} 崩溃退出: {err_msg}")
            return False
        # ==========================================================
        
        # 如果 Opt 没完成 (没有 job.done)
        if not self._check_done(opt_dir):
            keywords = G16_PARAMS[opt_key]
            is_retry = (opt_dir / "RETRY_CALCALL").exists()
            
            # [Action] 重试是动作，强制打印
            if is_retry:
                print(f"  [Repair] Resubmitting {opt_key} using opt=calcall...")
                if "opt=" in keywords:
                    keywords = keywords.replace("opt=", "opt=(calcall,")
                    if ")" not in keywords: keywords += ")"
                else:
                    keywords = keywords.replace("opt", "opt=calcall")
            
            self._run_opt_step(opt_key, source_type, source_file, charge, spin, custom_keywords=keywords)
            return False 
        
        # [Error] 异常结束是错误，强制打印
        elif not check_g16_termination(opt_log):
            self._mark_fatal_error(f"{opt_key} 异常结束 (Error Termination)。请检查 Log: {opt_log}")
            return False

        # --- 2. 检查 Freq 步骤 ---
        freq_log = freq_dir / f"{self.name}_{freq_key}.log"
        # ==========================================================
        # [新增] 优先检查 Gaussian Freq 是否直接报错退出
        has_err, err_msg = check_g16_error(freq_log)
        if has_err:
            self._mark_fatal_error(f"{freq_key} 崩溃退出: {err_msg}")
            return False
        # ==========================================================
        if not self._check_done(freq_dir):
            self._run_freq_step(freq_key, opt_key, charge, spin)
            return False
            
        elif not check_g16_termination(freq_log):
            self._mark_fatal_error(f"{freq_key} 异常结束 (Error Termination)。请检查 Log: {freq_log}")
            return False

        # --- 3. 虚频检查与决策 ---
        has_imag, imag_vals = check_imaginary_frequencies(freq_log)

        if not has_imag:
            # [Check] 检查通过，如果是 silent 模式则保持沉默
            if not silent:
                print(f"  [Check] {freq_key} passed frequency check.")
            return True
        else:
            # [Warning] 虚频警告，强制打印
            print(f"  [Warning] Imaginary frequencies found in {freq_key}: {imag_vals}")
            
            if (opt_dir / "RETRY_CALCALL").exists():
                print(f"  [Fail] {state_label} still has imaginary freqs after opt=calcall.")
                self._mark_fatal_error(f"{state_label} failed convergence (Imaginary Freq after Retry).")
                return False

            elapsed_hours = check_job_elapsed_time(freq_log)
            print(f"  [Time] Freq calculation took {elapsed_hours:.2f} hours.")

            if elapsed_hours < 8.0:
                print(f"  [Action] Time < 8h. Triggering re-optimization with opt=calcall.")
                self._trigger_retry(opt_dir, freq_dir)
                return False
            else:
                print(f"  [Fail] Time > 8h ({elapsed_hours:.2f}h). Too expensive to retry calcall.")
                self._mark_fatal_error(f"{state_label} imaginary freq (time > 8h).")
                return False

    # =========================================================================
    # 任务提交的具体实现 (Opt & Freq)
    # =========================================================================
    def _run_opt_step(self, step_key, source_type, source_file, charge, spin, custom_keywords=None):
        folder = self.dirs[step_key]
        job_name = f"{self.name}_{step_key}"
        
        if (folder / "run.slurm").exists() and not (folder / "job.done").exists():
            return

        print(f"  [Step] Preparing {job_name} ...")
        folder.mkdir(parents=True, exist_ok=True)

        # 1. 获取坐标
        coords = ""
        try:
            if source_type == 'xyz':
                coords = read_xyz_coords(source_file)
            elif source_type == 'log' or source_type == 'chk':
                coords = extract_geom_with_obabel(source_file, temp_dir=folder)
        except Exception as e:
            self._mark_fatal_error(f"Failed to extract coords for {step_key}: {e}")
            return

        # 2. 生成 Gaussian 输入文件
        keywords = custom_keywords if custom_keywords else G16_PARAMS[step_key]
        mem_val = G16_PARAMS.get('mem_opt', G16_PARAMS.get('mem', '256GB'))
        
        write_gjf(
            folder=folder,
            job_name=job_name,
            coords=coords,
            charge=charge,
            spin=spin,
            keywords=keywords,
            nproc=G16_PARAMS['nproc'],
            mem=mem_val  
        )

        # 3. 生成并提交 Slurm
        write_g16_slurm(folder, job_name, nproc=G16_PARAMS['nproc'])
        self._submit_to_queue(folder)
    
    def _handle_td_step(self, step_key, prev_opt_key, charge, spin):
        folder = self.dirs[step_key]
        job_name = f"{self.name}_{step_key}"
        sp_log = folder / f"{job_name}.log"
        
        if self._check_done(folder):
            if not check_g16_termination(sp_log):
                self._mark_fatal_error(f"{step_key} 异常结束 (Error Termination)。")
                return False
            return True
            
        if (folder / "run.slurm").exists(): return False

        print(f"  [Step] Preparing {job_name} (TD Energy Calculation)...")
        folder.mkdir(parents=True, exist_ok=True)
        
        # 提取优化好的坐标
        prev_opt_log = self.dirs[prev_opt_key] / f"{self.name}_{prev_opt_key}.log"
        try:
            coords = extract_geom_with_obabel(prev_opt_log, temp_dir=folder)
        except Exception as e:
            self._mark_fatal_error(f"TD Failed to extract coords from {prev_opt_key}: {e}")
            return False

        keywords = G16_PARAMS[step_key]
        write_gjf(
            folder=folder, job_name=job_name, coords=coords,
            charge=charge, spin=spin, keywords=keywords,
            nproc=G16_PARAMS['nproc'], mem=G16_PARAMS.get('mem', '256GB')
        )
        write_g16_slurm(folder, job_name, nproc=G16_PARAMS['nproc'])
        self._submit_to_queue(folder)
        return False

    def _run_freq_step(self, step_key, prev_opt_key, charge, spin):
        folder = self.dirs[step_key]
        job_name = f"{self.name}_{step_key}"
        
        if (folder / "run.slurm").exists() and not (folder / "job.done").exists():
            return

        print(f"  [Step] Preparing {job_name} ...")
        folder.mkdir(parents=True, exist_ok=True)
        
        # 1. 拷贝 Opt 产生的 chk 文件 
        opt_chk = self.dirs[prev_opt_key] / f"{self.name}_{prev_opt_key}.chk"
        freq_chk = folder / f"{job_name}.chk"
        
        if opt_chk.exists():
            shutil.copy(opt_chk, freq_chk)
        else:
            print(f"  [Wait] Opt Checkpoint not found: {opt_chk}")
            return

        # 2. 从上一步 Log 提取坐标
        prev_opt_log = self.dirs[prev_opt_key] / f"{self.name}_{prev_opt_key}.log"
        
        if not prev_opt_log.exists():
            print(f"  [Wait] Previous Opt Log not found: {prev_opt_log}")
            return

        try:
            coords = extract_geom_with_obabel(prev_opt_log, temp_dir=folder)
        except Exception as e:
            self._mark_fatal_error(f"Failed to extract coords from {prev_opt_key}: {e}")
            return

        # 3. 处理关键词
        raw_keywords = G16_PARAMS[step_key]
        keywords = raw_keywords.replace("geom=allcheck", "").replace("geom=check", "")
        
        mem_val = G16_PARAMS.get('mem_freq', G16_PARAMS.get('mem', '256GB'))

        # 5. 生成输入文件 (修正：移除了 old_chk 参数)
        write_gjf(
            folder=folder,
            job_name=job_name,
            coords=coords,
            charge=charge,
            spin=spin,
            keywords=keywords,
            nproc=G16_PARAMS['nproc'],
            mem=mem_val
        )

        # 6. 提交
        write_g16_slurm(folder, job_name, nproc=G16_PARAMS['nproc'])
        self._submit_to_queue(folder)

    # =========================================================================
    # ORCA 处理逻辑
    # =========================================================================                
    def _handle_orca_step(self):
        step_key = 'orca'
        folder = self.dirs[step_key]
        job_name = f"{self.name}_orca"
        
        if (folder / "job.done").exists(): return
        if (folder / "run.slurm").exists(): return

        print(f"  [Step] Preparing ORCA SOC calculation...")
        # [Fix] 提前创建文件夹，防止 OpenBabel 报错
        folder.mkdir(parents=True, exist_ok=True)
        
        t1_log = self.dirs['t1_opt'] / f"{self.name}_t1_opt.log"
        if not t1_log.exists(): return 
            
        try:
            coords = extract_geom_with_obabel(t1_log, temp_dir=folder)
        except Exception as e:
            print(f"  [Error] Failed to extract T1 geom for ORCA: {e}")
            return

        from lib.orca_handler import write_orca_inp 
        write_orca_inp(folder, job_name, coords, nproc=56, mem_per_core=8000)
        
        write_orca_slurm(folder, job_name, input_file="orca.inp", nproc=56)
        self._submit_to_queue(folder)

    # =========================================================================
    # EVC 处理逻辑 (S0-T1 和 S0-S1 分开处理)
    # =========================================================================
    def _handle_evc_t1(self):
        """处理 S0-T1 的 EVC (Kr, Kisc 专属)，不计算 NAC"""
        folder = self.dirs['evc_t1']
        if self._check_done(folder): return True

        print(f"  [Step] Running MOMAP EVC (S0-T1) for {self.name}...")
        folder.mkdir(parents=True, exist_ok=True)

        s0_log_src = self.dirs['s0_freq'] / f"{self.name}_s0_freq.log"
        t1_log_src = self.dirs['t1_freq'] / f"{self.name}_t1_freq.log"
        
        # [修复] 提取对应的 .fchk 文件
        s0_fchk_src = self.dirs['s0_freq'] / f"{self.name}_s0_freq.fchk"
        t1_fchk_src = self.dirs['t1_freq'] / f"{self.name}_t1_freq.fchk"

        if not s0_log_src.exists() or not t1_log_src.exists() or not s0_fchk_src or not t1_fchk_src:
            self._mark_fatal_error("MOMAP EVC (S0-T1) Failed: Missing .log or .fchk files.")
            return False

        shutil.copy(s0_log_src, folder / "s0.log")
        shutil.copy(t1_log_src, folder / "t1.log")
        # [修复] 复制 .fchk 到当前目录
        shutil.copy(s0_fchk_src, folder / "s0.fchk")
        shutil.copy(t1_fchk_src, folder / "t1.fchk")

        from lib.momap_handler import write_momap_inp
        import subprocess
        import sys

        # 生成给新模块用的 evc.inp
        write_momap_inp(folder, 'evc', use_cartesian=False, inp_filename="momap_evc.inp", s0_log="s0.log", t1_log="t1.log")

        print("    -> Running DINT Module for S0-T1 EVC...")
        dint_main_path = "/home/zhangwenjie/work/workflow_pt/software/dint_main.py"
        
        try:
            res = subprocess.run(f"{sys.executable} {dint_main_path}", shell=True, cwd=folder, check=True, capture_output=True)
            (folder / "dint_t1.log").write_bytes(res.stdout + res.stderr)
        except subprocess.CalledProcessError as e:
            (folder / "dint_t1.log").write_bytes(e.stdout + e.stderr)
            self._mark_fatal_error(f"DINT Module Failed (S0-T1). Please check dint_t1.log for details.")
            return False

        dat_file = folder / "evc.chenxiao.dat"
        if dat_file.exists() and dat_file.stat().st_size > 100:
            (folder / "job.done").touch()
            print("    -> EVC (S0-T1) successfully completed and validated!")
            return True
        else:
            self._mark_fatal_error("EVC (S0-T1) failed validation: .dat file is missing or exceptionally small.")
            return False


    def _handle_evc_s1(self):
        """处理 S0-S1 的 EVC (Kic 专属)，需调用原生 MOMAP 计算 NAC"""
        folder = self.dirs['evc_s1']
        if self._check_done(folder): return True

        print(f"  [Step] Running MOMAP EVC (S0-S1) for {self.name}...")
        folder.mkdir(parents=True, exist_ok=True)

        s0_log_src = self.dirs['s0_freq'] / f"{self.name}_s0_freq.log"
        s1_log_src = self.dirs['s1_freq'] / f"{self.name}_s1_freq.log"
        
        s0_fchk_src = self.dirs['s0_freq'] / f"{self.name}_s0_freq.fchk"
        s1_fchk_src = self.dirs['s1_freq'] / f"{self.name}_s1_freq.fchk"

        if not s0_log_src.exists() or not s1_log_src.exists() or not s0_fchk_src or not s1_fchk_src:
            self._mark_fatal_error("MOMAP EVC (S0-S1) Failed: Missing .log or .fchk files.")
            return False

        shutil.copy(s0_log_src, folder / "s0.log")
        shutil.copy(s1_log_src, folder / "s1.log")
        shutil.copy(s0_fchk_src, folder / "s0.fchk")
        shutil.copy(s1_fchk_src, folder / "s1.fchk")

        from lib.momap_handler import write_momap_inp
        import subprocess
        import sys

        # 1. 严格使用原生 MOMAP 提取 S1 激发态 NAC
        write_momap_inp(folder, 'evc', use_cartesian=True, inp_filename="momap_cart.inp", s0_log="s0.log", t1_log="s1.log", fnacme="s1.log")
        # 2. 给新模块使用的 inp
        write_momap_inp(folder, 'evc', use_cartesian=False, inp_filename="momap_evc.inp", s0_log="s0.log", t1_log="s1.log")

        print("    -> Running Native MOMAP for S0-S1 NAC...")
        
        # [精准修复] 直接 source 你们专属的环境变量脚本
        run_native_script = folder / "run_native.sh"
        script_content = "#!/bin/bash\n" \
                         "source /home/software/momap/2024a/env.sh\n" \
                         "momap -i momap_cart.inp\n"
        run_native_script.write_text(script_content)
        run_native_script.chmod(0o755)

        try:
            # 此时普通的 bash 运行即可，它会自然执行 source
            res_native = subprocess.run("bash run_native.sh", shell=True, cwd=folder, check=True, capture_output=True)
            (folder / "native_momap_s1.log").write_bytes(res_native.stdout + res_native.stderr)
        except subprocess.CalledProcessError as e:
            (folder / "native_momap_s1.log").write_bytes(e.stdout + e.stderr)
            self._mark_fatal_error(f"Native MOMAP Failed (S0-S1). Please check native_momap_s1.log for details.")
            return False

        print("    -> Running DINT Module for S0-S1 EVC...")
        dint_main_path = "/home/zhangwenjie/work/workflow_pt/software/dint_main.py"
        try:
            res_dint = subprocess.run(f"{sys.executable} {dint_main_path}", shell=True, cwd=folder, check=True, capture_output=True)
            (folder / "dint_s1.log").write_bytes(res_dint.stdout + res_dint.stderr)
        except subprocess.CalledProcessError as e:
            (folder / "dint_s1.log").write_bytes(e.stdout + e.stderr)
            self._mark_fatal_error(f"DINT Module Failed (S0-S1). Please check dint_s1.log for details.")
            return False

        dat_file = folder / "evc.chenxiao.dat"
        nac_file = folder / "evc.cart.nac"
        
        if dat_file.exists() and dat_file.stat().st_size > 100 and nac_file.exists() and nac_file.stat().st_size > 100:
            (folder / "job.done").touch()
            print("    -> EVC (S0-S1) perfectly completed and validated!")
            return True
        else:
            self._mark_fatal_error("EVC (S0-S1) failed validation: target files (.dat or .nac) are missing or exceptionally small.")
            return False

    # =========================================================================
    # MOMAP Kr 处理
    # =========================================================================   
    def _handle_momap_kr(self):
        folder = self.dirs['kr']
        if self._check_done(folder): return True
        if (folder / "run.slurm").exists(): return False

        print(f"  [Step] Preparing MOMAP Kr for {self.name}...")
        folder.mkdir(parents=True, exist_ok=True)
        
        # [精准提取] 从 evc_t1 拿 .dat，不需要 .nac
        evc_dat = self.dirs['evc_t1'] / "evc.chenxiao.dat"
        orca_out = self.dirs['orca'] / f"{self.name}_orca.out"
        if not evc_dat.exists() or not orca_out.exists(): return False

        shutil.copy(evc_dat, folder / "evc.chenxiao.dat")

        from lib.momap_handler import write_momap_inp, get_gaussian_energy
        from lib.slurm_utils import write_momap_slurm
        from lib.orca_handler import read_edme
        edme_val = read_edme(edme_file)
        
        s0_log = self.dirs['s0_freq'] / f"{self.name}_s0_freq.log"
        t1_log = self.dirs['t1_freq'] / f"{self.name}_t1_freq.log"
        ead_val = get_gaussian_energy(t1_log) - get_gaussian_energy(s0_log)

        # 命名为标准 momap.inp
        write_momap_inp(folder, 'kr', config_params=MOMAP_PARAMS, inp_filename="momap.inp",
                        DSFile="evc.chenxiao.dat", EDME=edme_val, Ead=ead_val)
        write_momap_slurm(folder, "kr", nproc=G16_PARAMS['nproc'])
        self._submit_to_queue(folder)
        return False

    # =========================================================================
    # MOMAP Kisc 处理
    # =========================================================================       
    def _handle_momap_kisc(self):
        folder = self.dirs['kisc']
        if self._check_done(folder): return True
        if (folder / "run.slurm").exists(): return False

        print(f"  [Step] Preparing MOMAP Kisc for {self.name}...")
        folder.mkdir(parents=True, exist_ok=True)
        
        # [精准提取] 从 evc_t1 拿 .dat，不需要 .nac
        evc_dat = self.dirs['evc_t1'] / "evc.chenxiao.dat"
        orca_out = self.dirs['orca'] / f"{self.name}_orca.out"
        if not evc_dat.exists() or not orca_out.exists(): return False

        shutil.copy(evc_dat, folder / "evc.chenxiao.dat")

        from lib.momap_handler import write_momap_inp, get_gaussian_energy
        from lib.slurm_utils import write_momap_slurm
        from lib.orca_handler import read_soc

        hso_val = read_soc(orca_out)

        s0_log = self.dirs['s0_freq'] / f"{self.name}_s0_freq.log"
        t1_log = self.dirs['t1_freq'] / f"{self.name}_t1_freq.log"
        ead_val = get_gaussian_energy(t1_log) - get_gaussian_energy(s0_log)

        write_momap_inp(folder, 'kisc', config_params=MOMAP_PARAMS, inp_filename="momap.inp",
                        DSFile="evc.chenxiao.dat", Hso=hso_val, Ead=ead_val)
        write_momap_slurm(folder, "kisc", nproc=G16_PARAMS['nproc'])
        self._submit_to_queue(folder)
        return False

    # =========================================================================
    # MOMAP Kic 处理
    # =========================================================================       
    def _handle_momap_kic(self):
        folder = self.dirs['kic']
        if self._check_done(folder): return True
        if (folder / "run.slurm").exists(): return False

        print(f"  [Step] Preparing MOMAP Kic for {self.name}...")
        folder.mkdir(parents=True, exist_ok=True)
        
        # [精准提取] 从 evc_s1 拿 .dat 和 原生的 .nac
        evc_dat = self.dirs['evc_s1'] / "evc.chenxiao.dat"
        nac_file = self.dirs['evc_s1'] / "evc.cart.nac"
        if not evc_dat.exists() or not nac_file.exists(): return False

        shutil.copy(evc_dat, folder / "evc.chenxiao.dat")
        shutil.copy(nac_file, folder / "evc.cart.nac")

        from lib.momap_handler import write_momap_inp, get_gaussian_energy
        from lib.slurm_utils import write_momap_slurm
        
        s0_log = self.dirs['s0_freq'] / f"{self.name}_s0_freq.log"
        s1_log = self.dirs['s1_freq'] / f"{self.name}_s1_freq.log"
        ead_val = get_gaussian_energy(s1_log) - get_gaussian_energy(s0_log)

        # 同时向 momap.inp 提供 DSFile 和 CoulFile
        write_momap_inp(folder, 'kic', config_params=MOMAP_PARAMS, inp_filename="momap.inp",
                        DSFile="evc.chenxiao.dat", CoulFile="evc.cart.nac", Ead=ead_val)
        write_momap_slurm(folder, "ic", nproc=G16_PARAMS['nproc'])
        self._submit_to_queue(folder)
        return False

    # =========================================================================
    # 结果分析 (请直接替换原来的 _run_final_analysis)
    # =========================================================================       
    def _run_final_analysis(self):
        report_file = self.root / "REPORT_PLQY.txt"
        if report_file.exists(): return 

        print(f"--- Running Final Analysis for {self.name} ---")
        
        kr_log = self.dirs['kr'] / "spec.tvcf.log"
        kisc_log = self.dirs['kisc'] / "isc.tvcf.log"
        kic_log = self.dirs['kic'] / "ic.tvcf.log"
        
        kr, kisc, kic = extract_rates_from_logs(kr_log, kisc_log, kic_log)
        
        # 能量提取逻辑变更：s1 用 freq(SCF)，t1 用 td
        s1_log = self.dirs['s1_freq'] / f"{self.name}_s1_freq.log"
        t1_td_log = self.dirs['t1_td'] / f"{self.name}_t1_td.log"
        
        e_s1 = get_gaussian_energy(s1_log)
        e_t1 = extract_td_energy(t1_td_log, state_type="Triplet")
        delta_E = e_s1 - e_t1 
        
        temp = 300 
        plqy, ratio = calculate_plqy(kr, kisc, kic, delta_E, Temp=temp)
        
        spec_dat = self.dirs['kr'] / "spec.tvcf.spec.dat"
        peak_wl, fwhm_wl = 0.0, 0.0
        
        res = plot_spectrum_analysis(spec_dat, self.root)
        if res:
            peak_wl, fwhm_wl = res
            
        content = f"""
==================================================
Analysis Report for {self.name}
==================================================
1. Energies (Hartree)
   E(S1) [from SCF]: {e_s1:.6f}
   E(T1) [from TD] : {e_t1:.6f}
   dE(S1-T1): {delta_E:.6f} Ha ({delta_E * 27.2114:.3f} eV)
   Boltzmann Ratio n(S1)/n(T1): {ratio:.4e} (at {temp} K)

2. Rates (s^-1)
   Kr   (Rad): {kr:.4e}
   Kisc (ISC): {kisc:.4e}
   Kic  (IC) : {kic:.4e}

3. PLQY Calculation
   Formula: Kr / (Kr + Kisc + Kic * Ratio)
   PLQY: {plqy:.2%} ({plqy:.4f})

4. Spectrum Properties
   Peak Wavelength: {peak_wl:.1f} nm
   FWHM: {fwhm_wl:.1f} nm
==================================================
"""
        with open(report_file, 'w') as f:
            f.write(content.strip())
            
        print(content)
        print(f"  [Done] Report generated: {report_file}")

    # --- 辅助操作 ---
    def _trigger_retry(self, opt_dir, freq_dir):
        import shutil
        (opt_dir / "RETRY_CALCALL").touch()
        print(f"  [Reset] Flagged {opt_dir.name} for RETRY with opt=calcall.")
        
        for d in [opt_dir, freq_dir]:
            if not d.exists(): continue
            job_done = d / "job.done"
            if job_done.exists(): job_done.unlink()
            
            for log_file in d.glob(f"{self.name}_*.log"):
                bak_file = log_file.with_suffix(".log.bak")
                try:
                    if bak_file.exists(): bak_file.unlink()
                    shutil.move(log_file, bak_file)
                except Exception as e:
                    print(f"  [Warn] Failed to backup log {log_file.name}: {e}")

            for chk_file in d.glob("*.chk"):
                try:
                    chk_file.unlink()
                except Exception as e:
                    print(f"  [Warn] Failed to delete chk {chk_file.name}: {e}")

    def _is_step_perfect(self, folder, log_name):
        if not (folder / "job.done").exists():
            return False
        has_imag, _ = check_imaginary_frequencies(folder / log_name)
        return not has_imag

    def _check_done(self, folder):
        return (folder / "job.done").exists()

    def _submit_to_queue(self, folder):
        print(f"  [Submit] Submitting task in {folder}")
        # [Fix] 使用 subprocess.run
        subprocess.run("sbatch run.slurm", shell=True, cwd=folder)

# # --- 测试模式 ---
# if __name__ == "__main__":
#     from pathlib import Path
    
#     # 1. Mock 目录
#     root_dir = Path("test/mock_workflow_run") 
#     mol_name = "mock_test_mol" 
    
#     flow = MoleculeFlow(mol_name, "dummy.xyz", root_dir)
#     print("🚀 启动 Mock Workflow 测试...")
#     flow.process()

# =========================================================================
# 正式运行入口
# =========================================================================
if __name__ == "__main__":
    import glob
    import time
    
    # 1. 配置路径
    # 存放待算分子 .xyz 文件的目录
    SOURCE_DIR = Path("molecules") 
    # 计算结果存放的根目录
    RESULTS_DIR = Path("results")
    
    # 确保目录存在
    SOURCE_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    
    print("="*60)
    print(f"🚀 启动 Auto-PhosFlow 正式计算流程")
    print(f"📂 分子源目录: {SOURCE_DIR.resolve()}")
    print(f"📂 结果根目录: {RESULTS_DIR.resolve()}")
    print("="*60)

    # 2. 获取所有 .xyz 文件
    # 你可以根据需要修改这里。比如改成 while True 来做成守护进程，不断扫描新文件
    xyz_files = sorted(list(SOURCE_DIR.glob("*.xyz")))
    
    if not xyz_files:
        print("⚠️  未找到任何 .xyz 文件。请将分子结构放入 molecules/ 文件夹。")
    else:
        print(f"发现 {len(xyz_files)} 个待处理分子: {[f.stem for f in xyz_files]}")
        print("-" * 60)

        for i, xyz_path in enumerate(xyz_files, 1):
            mol_name = xyz_path.stem
            print(f"\n>>> [{i}/{len(xyz_files)}] 正在处理分子: {mol_name}")
            
            try:
                # 初始化工作流
                flow = MoleculeFlow(mol_name, xyz_path, RESULTS_DIR)
                
                # 执行流程
                # 注意：process() 内部是非阻塞提交任务的。
                # 这意味着它会快速把当前能做的步骤做完（或提交Slurm），然后就返回了。
                # 如果你想让脚本一直挂着监控这个分子直到彻底算完，你需要修改 process 逻辑
                # 或者，我们可以简单地让脚本对每个分子都跑一遍 process，
                # 然后利用 Crontab 或 循环 让这个脚本每隔一小时运行一次。
                
                flow.process()
                
            except Exception as e:
                print(f"❌ [Error] 处理 {mol_name} 时发生未捕获异常: {e}")
                import traceback
                traceback.print_exc()

    print("\n✅ 本轮扫描结束。")

    