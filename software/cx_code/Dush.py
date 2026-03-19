import math
import numpy as np
import scipy.linalg

def Reimers(sp1,sp2,L1,L2,Bp1,Bp2,M_2):
    # reference: Reimers, 2001, 10.1063/1.1412875
    # sp should be a list of PIC values for each structure
    # L should be a 3nx3n matrix of Cartesian normal modes
    # Bp should be a Npicx3n matrix of Wilson B matrix
    # M_2 should be a 3nx3n diagonal matrix of atomic mass(dalton as unit)
    N = len(M_2)
    sp1 = np.mat(sp1)
    sp1 = sp1.T
    sp2 = np.mat(sp2)
    sp2 = sp2.T
    G1 = Bp1*M_2*M_2*Bp1.T
    G2 = Bp2*M_2*M_2*Bp2.T

    g1full, a1full = scipy.linalg.eigh(G1)
    g1_2 = []
    for i in g1full:
        g1_2.append(math.sqrt(abs(i)))
    g1_2 = g1_2[6-N:]
    g1_2 = np.mat(np.diag(g1_2))
    g1_2 = g1_2.I
    a1 = np.mat(a1full[:,6-N:])

    g2full, a2full = scipy.linalg.eigh(G2)
    g2_2 = []
    for i in g2full:
        g2_2.append(math.sqrt(abs(i)))
    g2_2 = g2_2[6-N:]
    g2_2 = np.mat(np.diag(g2_2))
    g2_2 = g2_2.I
    a2 = np.mat(a2full[:,6-N:])

    LL1 = L1[:,6:]
    LL2 = L2[:,6:]

    # Q1 = J1*Q2 + K1
    J1 = LL1.T * M_2 * Bp1.T * a1 * g1_2 * g1_2 * a1.T * Bp2 * M_2 * LL2
    K1 = LL1.T * M_2 * Bp1.T * a1 * g1_2 * g1_2 * a1.T * (sp2 - sp1)

    # Q2 = J2*Q1 + K2
    J2 = LL2.T * M_2 * Bp2.T * a2 * g2_2 * g2_2 * a2.T * Bp1 * M_2 * LL1
    K2 = LL2.T * M_2 * Bp2.T * a2 * g2_2 * g2_2 * a2.T * (sp1 - sp2)

    return J1, J2, K1, K2
    # J is a 3n-6 x 3n-6 matrix of Duschinsky rotation
    # K is a 3n-6 x 1 array of shift vector


def chenxiao(sp1,sp2,L1,L2,Bp1,Bp2,M_2):
    # All the input being the same as Reimers(...)
    N = len(M_2)
    sp1 = np.mat(sp1)
    sp1 = sp1.T
    sp2 = np.mat(sp2)
    sp2 = sp2.T
    l1full, u1full = scipy.linalg.eigh(Bp1*Bp1.T)
    u1 = u1full[:,6-N:]
    u1 = np.mat(u1)
    u1 = u1.T
    l2full, u2full = scipy.linalg.eigh(Bp2*Bp2.T)
    u2 = u2full[:,6-N:]
    u2 = np.mat(u2)
    u2 = u2.T
    LL1 = L1[:,6:]
    LL2 = L2[:,6:]

    # Q1 = J1*Q2 + K1
    J1 = (u1 * Bp1 * M_2 * LL1).I * u1 * u2.T * (u2 * Bp2 * M_2 * LL2)
    K1 = (u1 * Bp1 * M_2 * LL1).I * u1 * (sp2 - sp1)

    # Q2 = J2*Q1 + K2
    J2 = (u2 * Bp2 * M_2 * LL2).I * u2 * u1.T * (u1 * Bp1 * M_2 * LL1)
    K2 = (u2 * Bp2 * M_2 * LL2).I * u2 * (sp1 - sp2)

    return J1, J2, K1, K2
    # All the output being the same as Reimers(...)


def Barone(sp1,sp2,L1,L2,Bp1,Bp2,M_2):
    # reference: A. Baiardi, J. Bloino and V. Barone, 2016, 10.1063/1.4942165
    # All the input being the same as Reimers(...)
    N = len(M_2)
    sp1 = np.mat(sp1)
    sp1 = sp1.T
    sp2 = np.mat(sp2)
    sp2 = sp2.T
    l1full, u1full = scipy.linalg.eigh(Bp1*Bp1.T)
    u1 = u1full[:,6-N:]
    u1 = np.mat(u1)
    u1 = u1.T
    l2full, u2full = scipy.linalg.eigh(Bp2*Bp2.T)
    u2 = u2full[:,6-N:]
    u2 = np.mat(u2)
    u2 = u2.T
    Bd1 = u1 * Bp1
    Bd2 = u2 * Bp2
    LL1 = L1[:,6:]
    LL2 = L2[:,6:]

    # Q1 = J1*Q2 + K1
    J1 = LL1.T * M_2.I * Bd1.T * (Bd1 * Bd1.T).I * Bd2 * M_2 * LL2
    K1 = LL1.T * M_2.I * Bd1.T * (Bd1 * Bd1.T).I * u1 * (sp2 - sp1)

    # Q2 = J2*Q1 + K2
    J2 = LL2.T * M_2.I * Bd2.T * (Bd2 * Bd2.T).I * Bd1 * M_2 * LL1
    K2 = LL2.T * M_2.I * Bd2.T * (Bd2 * Bd2.T).I * u2 * (sp1 - sp2)

    return J1, J2, K1, K2
    # All the output being the same as Reimers(...)