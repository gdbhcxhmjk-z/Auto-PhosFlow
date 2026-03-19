# This file reads .log and .fchk files from Gaussian. opt and freq job should be done simutaneously, giving one .log file and one .fchk file for each electronic state.

import sys
sys.path.append('./cx_code')

import numpy as np
import math
import scipy.linalg
import atomass
import elements


def readfloat(x):                         # Change strings with " " and "\n" into a list of float
    L = len(x)
    i = 0
    j = 0
    numx = []
    while i < L:
        while i < L and (x[i] == ' ' or x[i] == '\n'):
            i = i+1
        j = i
        if i >= L:
            break
        while i < L and (x[i] != ' ' and x[i] != '\n'):
            i = i+1
        numx.append(float(x[j:i]))
    return numx



def readin_g(logfile,fchkfile):             # Read atomic numbers, atomic mass, cartesian coordinates and force constants from .log and .fchk file
    #logfile should be the file name of the Gaussian .log file, and fchkfile be like
    f = open(logfile,'r')
    ff = f.read()
    f.close()
    fstart = -1
    find_so = 0
    while ff.find('Standard orientation',fstart+1) != -1:
        fstart = ff.find('Standard orientation',fstart+1)
        find_so = find_so + 1
    if find_so == 0:
        while ff.find('Input orientation:',fstart+1) != -1:
            fstart = ff.find('Input orientation:',fstart+1)

    fstart = ff.find('Atomic',fstart+1,len(ff))
    fstart = ff.find('\n',fstart,len(ff))
    fstart = ff.find('\n',fstart+1,len(ff))
    fstart = ff.find('\n',fstart+1,len(ff))
    fstop = ff.find('----',fstart,len(ff))

    fff = ff[fstart+1:fstop]
    fff = readfloat(fff)
    atomic_num = []
    k = 1
    while k < len(fff):
        atomic_num.append(int(fff[k]))
        k = k+6
    
    coorx = []
    k = 3
    while k < len(fff):
        coorx.append(fff[k])
        coorx.append(fff[k+1])
        coorx.append(fff[k+2])
        k = k+6
    
    # atomic_mass = atomass.num2mass(atomic_num)                                 
    atomic_mass = [elements.MASSES[n] for n in atomic_num]
    mol_mass = sum(atomic_mass)                     # To move to mass center coordinate
    i = 0
    centerx = [0,0,0]
    while i < len(atomic_mass):
        centerx[0] = centerx[0] + atomic_mass[i]*coorx[3*i]
        centerx[1] = centerx[1] + atomic_mass[i]*coorx[3*i+1]
        centerx[2] = centerx[2] + atomic_mass[i]*coorx[3*i+2]
        i = i+1
    centerx[0] = centerx[0]/mol_mass
    centerx[1] = centerx[1]/mol_mass
    centerx[2] = centerx[2]/mol_mass
    i = 0
    while i < len(atomic_mass):
        coorx[3*i] = coorx[3*i] - centerx[0]
        coorx[3*i+1] = coorx[3*i+1] - centerx[1]
        coorx[3*i+2] = coorx[3*i+2] - centerx[2]
        i = i+1

    f = open(fchkfile,'r')
    ff = f.read()
    f.close()
    fstart = ff.find('Cartesian Force Constants',0,len(ff))
    fstart = ff.find('\n',fstart,len(ff))
    fstop = ff.find('Nonadiabatic coupling',fstart,len(ff))
    fff = ff[fstart+1:fstop]
    force_constants = readfloat(fff)
    force_matrix = np.mat(np.zeros((len(atomic_num)*3,len(atomic_num)*3)))
    i = 0
    j = 0
    k = 0
    while i < len(atomic_num)*3:
        while j <= i:
            force_matrix[i,j]=force_constants[k]
            force_matrix[j,i]=force_matrix[i,j]
            k = k+1
            j = j+1
        j = 0
        i = i+1
    
    Ee_eV = 0
    natom = len(atomic_num)
    nacm_y = np.zeros([natom, 3], dtype=float)
    with open(logfile, 'r') as f_nac:
        f_line = f_nac.readlines()
        for l in range(len(f_line)):
            if ' Center     Atomic                Nonadiabatic Coup. (Bohr^-1)' in f_line[l]:
                  for a in range(natom):
                        nacm_y[a] = np.array(f_line[l+3+a].split()[-3:], dtype=float)
            if ' Excited State   1:' in f_line[l]:
                  Ee_eV = float(f_line[l].split()[4])
        f_nac.close()

    return atomic_num, atomic_mass, coorx, force_matrix, Ee_eV, nacm_y
    # Function "readin" returns:
    #   atomic_num: atomic numbers as an 1xn list of integer
    #   atomic_mass: atomic mass as an 1xn list of float (C = 12.0)
    #   coorx: cartesian coordinates as an 1x3n list of float (x1,y1,z1,x2,y2,z2...) (Angstrom as unit)
    #   force_matrix: force constants as a 3nx3n matrxi of float (in atomic unit, 1.5569E+03 N/m)
