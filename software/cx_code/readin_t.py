# This file reads outfile and hessianfile from Turbomole.

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


def readin_t(outfile,hessianfile):                  # To read files of Turbomole
    # outfile should be the output of aoforce
    # hessianfile should include the hessian of the molecule
    bohr2A = 0.52917721
    # In Turbomole files, energy in Hartree and length in bohr. 1 bohr = 0.52917721 Angstrom
    f = open(outfile,'r')
    ff = f.read()
    f.close()
    fstart = -1
    fstart = ff.find('Atomic coordinate,',0,len(ff))

    fstart = ff.find('atomic coordinates',fstart+1,len(ff))
    fstart = ff.find('\n',fstart,len(ff))
    fstart = fstart + 1
    fstop = ff.find('center',fstart,len(ff))

    linestart = []
    while fstart != -1:
        linestart.append(fstart)
        fstart = ff.find('         ',fstart+1,fstop)
        
    linestart.append(fstop)
    coorx = []
    atomic_num = []
    atoname = []
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
        atoco = readfloat(aline[0:datastart[3]])
        coorx.append(atoco[0]*bohr2A)
        coorx.append(atoco[1]*bohr2A)
        coorx.append(atoco[2]*bohr2A)
        if aline[datastart[3]+1] == ' ':
            atoname.append(aline[datastart[3]])
        else:
            atoname.append(''.join([aline[datastart[3]],aline[datastart[3]+1]]))
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
            
    f = open(hessianfile,'r')
    ff = f.read()
    f.close()
    hessian = []
    linestart = []
    fstart = ff.find('$hessian (projected)',0,len(ff))
    fstart = ff.find('\n',fstart,len(ff))
    fstop = ff.find('$end',0,len(ff))
    while fstart != -1:
        linestart.append(fstart+1)
        fstart = ff.find('\n',fstart+1,fstop)
    i = 0
    while i < len(linestart)-1:
        aline = ff[linestart[i]:linestart[i+1]]
        i = i+1
        linedata = readfloat(aline[7:])
        for j in linedata:
            hessian.append(j)                           # why not j/bohr**2 ?
    force_matrix = np.mat(hessian)
    force_matrix = np.reshape(force_matrix,(len(coorx),len(coorx)))

    return atomic_num,atomic_mass,coorx,force_matrix
    # Function "readin" returns:
    #   atomic_num: atomic numbers as an 1xn list of integer
    #   atomic_mass: atomic mass as an 1xn list of float (C = 12.0)
    #   coorx: cartesian coordinates as an 1x3n list of float (x1,y1,z1,x2,y2,z2...) (Angstrom as unit)
    #   force_matrix: force constants as a 3nx3n matrxi of float (in atomic unit, 1.5569E+03 N/m)