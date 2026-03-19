import numpy as np
import math
import scipy.linalg

def Normfreq(M_2,fmat):
    # M_2 = M^(-1/2)
    # fmat being the 3nx3n force matrix in atomic unit(1.5569E+03 N/m)
    Lam, Lnorm = scipy.linalg.eigh(M_2*fmat*M_2)
    Lnorm = np.mat(Lnorm)
    Omega = []
    for i in Lam:
        if i > 0:
            Omega.append(math.sqrt(1.5569*1000*i))
        else:
            Omega.append(0.)
    freq_cm = []
    for i in Omega:
        freq_cm.append(i*10**5*(math.sqrt(6.02214076)/(2*3.1415926535898*2.99792458*100)))
    return freq_cm, Lnorm
    # freq_cm being a 3n list of normal frequncies in cm-1
    # Lnorm being the 3nx3n normal mode matrix