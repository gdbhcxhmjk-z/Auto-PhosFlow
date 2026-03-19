# This file reads optfile and freqfile from Qchem.

import numpy as np
import math
import scipy.linalg
import atomass

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

def readin_q(optfile,freqfile):                              # To read files of Q-Chem
    # optfile should be the opt file
    # freqfile should be the freq file
    f = open(optfile,'r')
    ff = f.read()
    f.close()
    fstart = ff.find('OPTIMIZATION CONVERGED',0,len(ff))
    fstart = ff.find('Coordinates',fstart,len(ff))
    fstart = ff.find('\n',fstart+1,len(ff))
    fstart = ff.find('\n',fstart+1,len(ff))
    fstop = ff.find('\n\n',fstart+1,len(ff))

    atomic_num = []
    coorx = []
    linestart = []
    atoname = []
    while fstart != -1:
        linestart.append(fstart+1)
        fstart = ff.find('\n',fstart+1,fstop+1)
    i = 0
    while i < len(linestart)-1:
        aline = ff[linestart[i]:linestart[i+1]]
        i = i+1
        datastart = []
        j = 0
        while j < len(aline)-1:
            if aline[j] == ' ' and aline[j+1] != ' ':
                datastart.append(j+1)
            j = j+1
        if aline[datastart[1]+1] != ' ':
            atoname.append(''.join(aline[datastart[1]],aline[datastart[1]+1]))
        else:
            atoname.append(aline[datastart[1]])
        atoco = readfloat(aline[datastart[2]:])
        coorx.append(atoco[0])
        coorx.append(atoco[1])
        coorx.append(atoco[2])
    atomic_num = atomass.name2num(atoname)
    atomic_mass = atomass.num2mass(atomic_num)

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

    f = open(freqfile,'r')
    ff = f.read()
    f.close()
    fstart = ff.find('Final Hessian',0,len(ff))
    fstart = ff.find('\n',fstart,len(ff))
    fstart = ff.find('\n',fstart+1,len(ff))
    fstop = ff.find('------------------',fstart+1,len(ff))
    linestart = []
    while fstart != -1:
        linestart.append(fstart+1)
        fstart = ff.find('\n',fstart+1,fstop)
    i = 0
    datafr = []
    while i < len(linestart)-1:
        aline = readfloat(ff[linestart[i]:linestart[i+1]])
        datafr.append(aline)
        i = i+1
    hessian = []
    while len(linestart) > 1:
        i = 0
        hcol = []
        while i < len(datafr[0])-1:
            hcol.append([])
            i = i+1
        j = 0
        while j < len(coorx):
            i = 0
            while i < len(hcol):
                hcol[i].append(datafr[j][i+1])
                i = i+1
            j = j+1
        linestart = linestart[len(coorx)+1:]
        datafr = datafr[len(coorx)+1:]
        i = 0
        while i < len(hcol):
            hessian.append(hcol[i])
            i = i+1
    force_matrix = np.mat(hessian)

    return atomic_num,atomic_mass,coorx,force_matrix
    # Function "readin" returns:
    #   atomic_num: atomic numbers as an 1xn list of integer
    #   atomic_mass: atomic mass as an 1xn list of float (C = 12.0)
    #   coorx: cartesian coordinates as an 1x3n list of float (x1,y1,z1,x2,y2,z2...) (Angstrom as unit)
    #   force_matrix: force constants as a 3nx3n matrxi of float (in atomic unit, 1.5569E+03 N/m)