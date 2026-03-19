import numpy as np
from itertools import product

from cx_code.readin_g import readin_g
from cx_code.Norm import Normfreq
from cx_code import PIC
from cx_code import Dush
from cx_code.writeout import output_dat


s0_logfile = ''
s0_fchkfile = ''
s1_logfile = ''
s1_fchkfile = ''
with open("momap_evc.inp", 'r') as f_inp:
    read_line = f_inp.readlines()
    for l in range(len(read_line)):
        if len(read_line[l]) > 1:
            line = read_line[l].split()
            if line[0] == 'ffreq(1)':
                    s0_logfile = line[-1].split('.')[0][1:]+'.log'
                    s0_fchkfile = line[-1].split('.')[0][1:]+'.fchk'
            elif line[0] == 'ffreq(2)':
                    s1_logfile = line[-1].split('.')[0][1:]+'.log'
                    s1_fchkfile = line[-1].split('.')[0][1:]+'.fchk'

    f_inp.close()

print(s0_logfile, s0_fchkfile, s1_logfile, s1_fchkfile)


s0_atomic_num, s0_atomic_mass, s0_coorx, s0_force_matrix, Ee_eV, nacm_y = readin_g(s0_logfile, s0_fchkfile)
s1_atomic_num, s1_atomic_mass, s1_coorx, s1_force_matrix, Ee_eV, nacm_y = readin_g(s1_logfile, s1_fchkfile)


M_x = list(zip(*product(s0_atomic_mass, [1, 1, 1])))[0]
M_2 = np.diag(np.array(M_x)**(-1/2))



s0_freq_cm, s0_Lnorm = Normfreq(M_2, s0_force_matrix)
s1_freq_cm, s1_Lnorm = Normfreq(M_2, s1_force_matrix)




pic = PIC.PICset(s0_coorx, s1_coorx, s0_atomic_num)



Bpic_s0 = PIC.Bpic(s0_coorx, pic)
Bpic_s1 = PIC.Bpic(s1_coorx, pic)



pcoor_s0 = PIC.PICvalue(s0_coorx, pic)
pcoor_s1 = PIC.PICvalue(s1_coorx, pic)


natom = len(s0_atomic_num)
nx = natom*3
D1 = np.zeros([nx, 1], dtype=float)
S1 = np.zeros([nx, nx], dtype=float)
D2 = np.zeros([nx, 1], dtype=float)
S2 = np.zeros([nx, nx], dtype=float)



S1[6:, 6:], S2[6:, 6:], D1[6:], D2[6:] = Dush.Reimers(pcoor_s0, pcoor_s1, s0_Lnorm, s1_Lnorm, Bpic_s0, Bpic_s1, M_2)
output_dat('evc.Reimers.dat', s0_freq_cm, D1, S1, s1_freq_cm, D2, S2)


S1[6:, 6:], S2[6:, 6:], D1[6:], D2[6:] = Dush.chenxiao(pcoor_s0, pcoor_s1, s0_Lnorm, s1_Lnorm, Bpic_s0, Bpic_s1, M_2)
output_dat('evc.chenxiao.dat', s0_freq_cm, D1, S1, s1_freq_cm, D2, S2)


M_2 = np.mat(M_2)
S1[6:, 6:], S2[6:, 6:], D1[6:], D2[6:] = Dush.Barone(pcoor_s0, pcoor_s1, s0_Lnorm, s1_Lnorm, Bpic_s0, Bpic_s1, M_2)
output_dat('evc.Barone.dat', s0_freq_cm, D1, S1, s1_freq_cm, D2, S2)



def read_Es0(file_log):
    with open(file_log, 'r') as f_log:
        log_lines = f_log.readlines()
        f_log.close()
    Es0 = 0.
    for line in log_lines:
        if 'SCF Done' in line:
            Es0 = float(line.split()[4])
    return Es0

def read_Ead(file_log_s0, file_log_t1):
    Es0 = read_Es0(file_log_s0)
    Et1 = read_Es0(file_log_t1)
    Ead = Et1-Es0
    return Ead
Ead = read_Ead(s0_logfile, s1_logfile)
#print("{:.8f}".format(Ead))
