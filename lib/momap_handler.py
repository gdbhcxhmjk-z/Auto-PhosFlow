# lib/momap_handler.py
import os
import re
import shutil
import math
from pathlib import Path

# --- 1. 能量提取 (Gaussian) ---
def get_gaussian_energy(log_file):
    """
    从 Gaussian log 文件提取能量 (Hartree/au)。
    优先读取 Total Energy (MP2/CC等), 其次读取 SCF Done (DFT)。
    """
    energy = 0.0
    scf_energy = 0.0
    tot_energy = 0.0
    
    if not os.path.isfile(log_file):
        print(f"  [Error] Log file not found: {log_file}")
        return 0.0

    with open(log_file, 'r', errors='ignore') as f:
        # 为了效率，可以只读取最后几百行，但为了保险读取全文
        lines = f.readlines()

    for l in lines:
        if "SCF Done" in l:
            # E(RTPSSh) = -123.456789 A.U. ...
            try:
                parts = l.split()
                # find index of 'A.U.' or 'cycles'
                # typically: " SCF Done:  E(RTPSSh) =  -1342.39281928     A.U. after   11 cycles"
                # energy is usually at index 4
                scf_energy = float(parts[4])
            except:
                pass
        if "Total Energy" in l:
            # For some methods or MOMAP specific outputs
            try:
                tot_energy = float(l.split()[-1])
            except:
                pass
    
    if tot_energy != 0:
        energy = tot_energy
    elif scf_energy != 0:
        energy = scf_energy
        
    return energy

# --- 2. EDME 提取 (ORCA) ---
def extract_orca_edme(orca_out):
    """
    从 ORCA soc.out 中提取前三个态的 D2，计算 EDME。
    逻辑: 
      1. 找到 "SOC CORRECTED ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS" 表。
         注意：该表头可能出现两次，取包含数据的那个（通常是最后一次出现的，或者根据内容判断）。
      2. 提取前三行数据 (0-1.0A -> 1-3.0A, etc.) 的 D2 列。
      3. EDME = sqrt(mean(D2)) * 2.5417
    """
    if not os.path.isfile(orca_out):
        print(f"  [Error] ORCA out not found: {orca_out}")
        return 1.0 # Default fallback

    with open(orca_out, 'r', errors='ignore') as f:
        content = f.read()

    # 寻找特定的表头
    header = "SOC CORRECTED ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS"
    # 分割，可能找到多个块
    blocks = content.split(header)
    if len(blocks) < 2:
        print("  [Error] EDME table not found in ORCA output.")
        return 1.0

    # 我们通常需要最后一个块，或者检查块内是否有 "0-1.0A"
    target_block = None
    for block in reversed(blocks[1:]):
        if "0-1.0A" in block and "D2" in block:
            target_block = block
            break
    
    if not target_block:
        print("  [Error] Valid EDME data block not found.")
        return 1.0

    # 解析数据行
    # 格式示例:
    # 0-1.0A  ->  1-3.0A    2.272258   18327.0   545.6    0.000505493    0.00908    0.09528 ...
    lines = target_block.split('\n')
    d2_values = []
    
    # 正则匹配数据行: start with space or digit, contain ->
    # pattern: state_A -> state_B ... D2_val ...
    count = 0
    for line in lines:
        if "->" in line and "0-1.0A" in line:
            parts = line.split()
            # Column mapping based on header:
            # Transition (0-1.0A -> 1-3.0A) take 3 cols
            # Energy(eV), Energy(cm-1), Wavelength, fosc, D2
            # usually D2 is at index 8 (0-based) ? 
            # Let's count: 0:0-1.0A, 1:->, 2:1-3.0A, 3:eV, 4:cm-1, 5:nm, 6:fosc, 7:D2
            try:
                # 寻找 D2 的位置，通常是第 8 列 (index 7) 或者动态识别
                # 简单方法：parts[7]
                d2 = float(parts[7])
                d2_values.append(d2)
                count += 1
                if count == 3:
                    break
            except (ValueError, IndexError):
                continue
    
    if len(d2_values) < 3:
        print(f"  [Warning] Found less than 3 states for EDME: {d2_values}")
        if len(d2_values) == 0: return 1.0
    
    # 计算 EDME
    d2_avg = sum(d2_values) / len(d2_values)
    edme = math.sqrt(d2_avg) * 2.5417
    print(f"  [Data] Extracted D2: {d2_values}, Avg: {d2_avg:.6f}, EDME: {edme:.4f} Debye")
    
    return edme

# --- 3. 重整能检查 (EVC Check) ---
def check_evc_reorg(folder):
    """
    检查 evc.dint.dat 和 evc.cart.dat。
    返回: (passed (bool), best_file_name (str))
    """
    files = ["evc.dint.dat", "evc.cart.dat"]
    results = {} # filename -> mean_reorg

    folder = Path(folder)
    
    for fname in files:
        fpath = folder / fname
        if not fpath.exists():
            continue
            
        try:
            with open(fpath, 'r') as f:
                content = f.read()
            
            # 匹配 "Total reorganization energy"
            # 格式: Total reorganization energy       (cm-1):          2198.610902        1892.476760
            match = re.search(r"Total reorganization energy.*:\s+([\d\.]+)\s+([\d\.]+)", content)
            if match:
                re1 = float(match.group(1))
                re2 = float(match.group(2))
                
                # 检查阈值 5000
                if re1 > 5000 or re2 > 5000:
                    print(f"  [Fail] {fname}: Reorg energy ({re1}, {re2}) > 5000 cm-1")
                    return False, None
                
                mean_re = (re1 + re2) / 2.0
                results[fname] = mean_re
                print(f"  [Check] {fname}: Reorg ({re1:.1f}, {re2:.1f}), Mean: {mean_re:.1f}")
                
        except Exception as e:
            print(f"  [Error] reading {fname}: {e}")

    if not results:
        print("  [Fail] No valid EVC dat files found.")
        return False, None

    # 选择均值最小的文件
    best_file = min(results, key=results.get)
    print(f"  [Select] Best file for Kr: {best_file}")
    return True, best_file

def extract_orca_soc(orca_out):
    """
    从 ORCA 输出中提取 T1 和 S0 之间的 SOC 常数 (Hso)。
    逻辑:
      1. 寻找 "CALCULATED SOCME BETWEEN TRIPLETS AND SINGLETS" 表头。
      2. 确保该表包含 X, Y, Z 分量 (通过检查表头下方是否有 X, Y, Z 字样)。
      3. 找到 T=1, S=0 的行: 1      0     ( Re, Im )    ( Re, Im )    ( Re, Im )
      4. 计算 RMS: sqrt( sum(Re^2 + Im^2) / 3 )
    """
    if not os.path.isfile(orca_out):
        print(f"  [Error] ORCA out not found: {orca_out}")
        return 0.0

    with open(orca_out, 'r', errors='ignore') as f:
        content = f.read()

    # 1. 定位正确的表格
    # ORCA 可能输出多个 SOCME 表，我们需要包含 X, Y, Z 分量的那个
    # 策略：找到表头，然后往后读几行，看是否包含 "X" 和 "Y"
    
    header = "CALCULATED SOCME BETWEEN TRIPLETS AND SINGLETS"
    blocks = content.split(header)
    
    target_block = None
    for block in blocks[1:]: # 跳过第一个split前的部分
        # 检查前 10 行内是否有 "X" 和 "Y" 和 "Z" (区分于 scalar SOC)
        lines = block.split('\n')
        header_check = "".join(lines[:10])
        if "X" in header_check and "Y" in header_check and "Z" in header_check:
            target_block = block
            break
    
    if not target_block:
        print("  [Error] SOCME (X,Y,Z) table not found in ORCA output.")
        return 0.0

    # 2. 解析数据行 T=1, S=0
    # 格式示例:
    # 1      0     (   0.00 ,    0.06 )    (   0.00 ,    1.26 )    (  -0.00 ,   -0.89 )
    # 正则匹配： 1 空格 0 空格 ( f, f ) ( f, f ) ( f, f )
    
    # 构造正则：匹配 6 个浮点数
    # \s*1\s+0 匹配 T=1 S=0
    # 后面跟三个括号组
    pattern = re.compile(
        r"^\s*1\s+0\s+"
        r"\(\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\)\s+"  # Z (Re, Im)
        r"\(\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\)\s+"  # X (Re, Im)
        r"\(\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\)"     # Y (Re, Im)
    , re.MULTILINE)
    
    match = pattern.search(target_block)
    
    if match:
        vals = [float(x) for x in match.groups()] # 拿到6个数
        # 计算平方和
        sq_sum = sum(v**2 for v in vals)
        # 均方根 (除以3后开根号)
        hso = math.sqrt(sq_sum / 3.0)
        print(f"  [Data] Extracted SOC components: {vals}")
        print(f"  [Data] Calculated Hso (RMS): {hso:.5f} cm-1")
        return hso
    else:
        print("  [Error] Could not find '1 0' transition in SOC table.")
        return 0.0

# --- 更新: 输入文件生成器 (支持 kisc) ---
def write_momap_inp(folder, mode, config_params=None, **runtime_kwargs):
    """
    Args:
        mode: 'evc', 'kr', 'kisc', 'kic'
        runtime_kwargs for evc: s0_log, t1_log (or s1_log), fnacme
        runtime_kwargs for others: Ead, Hso, CoulFile, DSFile...
    """
    if config_params is None: config_params = {}
    
    inp_path = folder / "momap.inp"
    content = ""

    # --- EVC 模式 ---
    if mode == 'evc':
        # 兼容处理：ffreq(2) 可能是 t1.log 也可能是 s1.log，由调用者传入 'log2' 或 't1_log'
        log1 = runtime_kwargs.get('s0_log', 's0.log')
        log2 = runtime_kwargs.get('log2', runtime_kwargs.get('t1_log', 't1.log'))
        
        nac_line = ""
        if 'fnacme' in runtime_kwargs:
            nac_line = f' fnacme   = "{runtime_kwargs["fnacme"]}"'
            
        content = f"""do_evc = 1
&evc
 ffreq(1) = "{log1}"
 ffreq(2) = "{log2}"
{nac_line}
/
"""

    # --- Rate / Spectrum 模式 ---
    elif mode in ['kr', 'kisc', 'kic']:
        # 参数合并
        p = config_params.get('common', {}).copy()
        if mode in config_params:
            p.update(config_params[mode])
        p.update(runtime_kwargs)
        
        # 提取通用参数用于 f-string
        # 注意：使用 .get() 设定默认值防止 KeyError
        
        # --- Kisc ---
        if mode == 'kisc':
            content = f"""do_isc_tvcf_ft   = 1
do_isc_tvcf_spec = 1

&isc_tvcf
 DUSHIN        = {p.get('DUSHIN', '.f.')}
 HERZ          = {p.get('HERZ', '.f.')}
 Temp          = {p.get('Temp', 300)} K
 tmax          = {p.get('tmax', 3000)} fs
 dt            = {p.get('dt', 0.01)} fs
 Ead           = {p.get('Ead', 0.0):.8f} au
 Hso           = {p.get('Hso', 0.0):.5f} cm-1
 FreqScale     = {p.get('FreqScale', 1.0)}
 DSFile        = "{p.get('DSFile', 'evc.dint.dat')}"
 isgauss       = {p.get('isgauss', '.t.')}
 BroadenType   = "{p.get('BroadenType', 'gaussian')}"
 Broadenfunc   = "{p.get('Broadenfunc', 'time')}"
 FWHM          = {p.get('FWHM', 20)} cm-1
 GFile         = "spec.tvcf.gauss.dat"
 NScale        = {p.get('NScale', 10)}
 Emin          = {p.get('Emin', -0.3)} au
 Emax          = {p.get('Emax', 0.3)} au
 dE            = {p.get('dE', 0.00001)} au
 logFile       = "isc.tvcf.log"
 FoFile        = "isc.tvcf.fo.dat"
 FtFile        = "isc.tvcf.ft.dat"
 FoSFile       = "isc.tvcf.spec.dat"
 spectra0      = {p.get('spectra0', '.f.')}
 IntEmin       = 0.0 au
 IntEmax       = 0.09 au
/
"""
        # --- Kic (新增) ---
        elif mode == 'kic':
            # Kic 使用 &ic_tvcf
            content = f"""do_ic_tvcf_ft   = 1
do_ic_tvcf_spec = 1

&ic_tvcf
 DUSHIN        = {p.get('DUSHIN', '.t.')}
 Temp          = {p.get('Temp', 300)} K
 tmax          = {p.get('tmax', 3000)} fs
 dt            = {p.get('dt', 0.01)} fs
 Ead           = {p.get('Ead', 0.0):.8f} au
 DSFile        = "{p.get('DSFile', 'evc.cart.dat')}"
 CoulFile      = "{p.get('CoulFile', 'evc.cart.nac')}"
 isgauss       = {p.get('isgauss', '.t.')}
 BroadenType   = "{p.get('BroadenType', 'gaussian')}"
 Broadenfunc   = "{p.get('Broadenfunc', 'frequency')}"
 FWHM          = {p.get('FWHM', 500)} cm-1
 GFile         = "spec.tvcf.gauss.dat"
 NScale        = {p.get('NScale', 20)}
 Emax          = {p.get('Emax', 0.3)} au
 logFile       = "ic.tvcf.log"
 FtFile        = "ic.tvcf.ft.dat"
 FoFile        = "ic.tvcf.fo.dat"
/
"""
        
        # --- Kr ---
        else:
            # Kr 模板 (保持不变)
            content = f"""do_spec_tvcf_ft   = 1
do_spec_tvcf_spec = 1

&spec_tvcf
 DUSHIN        = {p.get('DUSHIN', '.f.')}
 HERZ          = {p.get('HERZ', '.f.')}
 Temp          = {p.get('Temp', 300)} K
 tmax          = {p.get('tmax', 3000)} fs
 dt            = {p.get('dt', 0.01)} fs
 Ead           = {p.get('Ead', 0.0):.8f} au
 EDMA          = {p.get('EDMA', 1.0)} debye
 EDME          = {p.get('EDME', 0.0):.8f} debye
 FreqScale     = {p.get('FreqScale', 1.0)}
 DSFile        = "{p.get('DSFile', 'evc.cart.dat')}"
 isgauss       = {p.get('isgauss', '.t.')}
 BroadenType   = "{p.get('BroadenType', 'gaussian')}"
 Broadenfunc   = "{p.get('Broadenfunc', 'frequency')}"
 FWHM          = {p.get('FWHM', 20)} cm-1
 GFile         = "spec.tvcf.gauss.dat"
 NScale        = {p.get('NScale', 10)}
 Emin          = {p.get('Emin', -0.3)} au
 Emax          = {p.get('Emax', 0.3)} au
 dE            = {p.get('dE', 0.00001)} au
 logFile       = "spec.tvcf.log"
 FoFile        = "spec.tvcf.fo.dat"
 FtFile        = "spec.tvcf.ft.dat"
 FoSFile       = "spec.tvcf.spec.dat"
 spectra0      = {p.get('spectra0', '.f.')}
 IntEmin       = 0.0 au
 IntEmax       = 0.09 au
/
"""
        
    with open(inp_path, 'w') as f:
        f.write(content)
    return inp_path