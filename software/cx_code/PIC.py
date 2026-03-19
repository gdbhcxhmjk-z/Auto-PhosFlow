import math
import numpy as np
import atomass
import radii


BOHR = 0.52917721092
PI = 3.14159265359
def PICvalue(xcoor,pic):                # To get PIC values given Cartesian coordinates and a PIC set
    # xcoor should be a 3n list of Cartesian coordinates
    # pic should be a list of lists, representing PICs including bond lengths, bond angles, dihedrals and some special cases
    # The serial numbers of atoms should start at 0
    pcoor = []
    for i in pic:
        if len(i) == 2:     # Bond length
            bondlen = math.sqrt((xcoor[3*i[0]]-xcoor[3*i[1]])**2 + (xcoor[3*i[0]+1]-xcoor[3*i[1]+1])**2 + (xcoor[3*i[0]+2]-xcoor[3*i[1]+2])**2)
            pcoor.append(bondlen)
        elif len(i) == 3:       # bond angle
            r01 = [xcoor[3*i[1]]-xcoor[3*i[0]],xcoor[3*i[1]+1]-xcoor[3*i[0]+1],xcoor[3*i[1]+2]-xcoor[3*i[0]+2]]
            r12 = [xcoor[3*i[2]]-xcoor[3*i[1]],xcoor[3*i[2]+1]-xcoor[3*i[1]+1],xcoor[3*i[2]+2]-xcoor[3*i[1]+2]]
            ang = np.dot(r01,r12)/math.sqrt(np.dot(r01,r01)*np.dot(r12,r12))
            if ang > 1:
                ang = 1
            elif ang < -1:
                ang = -1
            pcoor.append(PI - math.acos(ang))
        elif len(i) == 5:       # dihedral
            r01 = [xcoor[3*i[1]]-xcoor[3*i[0]],xcoor[3*i[1]+1]-xcoor[3*i[0]+1],xcoor[3*i[1]+2]-xcoor[3*i[0]+2]]
            r12 = [xcoor[3*i[2]]-xcoor[3*i[1]],xcoor[3*i[2]+1]-xcoor[3*i[1]+1],xcoor[3*i[2]+2]-xcoor[3*i[1]+2]]
            r23 = [xcoor[3*i[3]]-xcoor[3*i[2]],xcoor[3*i[3]+1]-xcoor[3*i[2]+1],xcoor[3*i[3]+2]-xcoor[3*i[2]+2]]
            n012 = np.cross(r01,r12)
            n123 = np.cross(r12,r23)
            j = 0
            r0 = []
            r3 = []
            while j < 3:
                r0.append(r01[j]-np.dot(r01,r12)*r12[j]/np.dot(r12,r12))
                r3.append(r23[j]-np.dot(r23,r12)*r12[j]/np.dot(r12,r12))
                j = j+1
            if i[4] == -2:
                dih = -np.dot(r0,r3)/math.sqrt(np.dot(r0,r0)*np.dot(r3,r3))
                if dih > 1:
                    dih = 1
                elif dih < -1:
                    dih = -1
                dih = math.acos(dih)
                if np.dot(r12,np.cross(r0,r3)) > 0:
                    dih = -dih
            elif i[4] == -3:
                dih = -np.dot(r0,r3)/math.sqrt(np.dot(r0,r0)*np.dot(r3,r3))
                if dih > 1:
                    dih = 1
                elif dih < -1:
                    dih = -1
                dih = math.acos(dih)
                if np.dot(r12,np.cross(r0,r3)) > 0:
                    dih =2*PI - dih
            pcoor.append(dih)
        elif len(i) == 4:       # special case
            r01 = [xcoor[3*i[1]]-xcoor[3*i[0]],xcoor[3*i[1]+1]-xcoor[3*i[0]+1],xcoor[3*i[1]+2]-xcoor[3*i[0]+2]]
            r12 = [xcoor[3*i[2]]-xcoor[3*i[1]],xcoor[3*i[2]+1]-xcoor[3*i[1]+1],xcoor[3*i[2]+2]-xcoor[3*i[1]+2]]
            r23 = [xcoor[3*i[3]]-xcoor[3*i[2]],xcoor[3*i[3]+1]-xcoor[3*i[2]+1],xcoor[3*i[3]+2]-xcoor[3*i[2]+2]]
            n012 = np.cross(r01,r12)
            dihh = np.dot(n012,r23)/math.sqrt(np.dot(n012,n012)*np.dot(r23,r23))
            dihh = math.acos(dihh)
            pcoor.append(dihh)
    
    return pcoor
    # pcoor is a list of floats being the values of the PICs

                
def PICset(x1,x2,anum):             # To provide a PIC set given Cartesian coordinates in two structures. Structure x1 is mainly used, while x2 only used in dihedrals.
    # x1 and x2 should be 2 lists of Cartesian coordinates
    # anum should be a list of atomic numbers
    tor = 1.3
    # tor is a parameter used to judge whether two atoms are bonded
    # rcov = atomass.num2radii(anum)
    rcov = [radii.COVALENT[a]*BOHR for a in anum]
    n = len(anum)
    Bondmat = np.mat(np.zeros((n,n)))
    pic = []
    i = 0
    j = 0
    while i < n:
        j = i+1
        while j < n:
            r = (x1[3*i]-x1[3*j])**2 + (x1[3*i+1]-x1[3*j+1])**2 + (x1[3*i+2]-x1[3*j+2])**2
            r = math.sqrt(r)
            if r < tor*(rcov[i]+rcov[j]):
                Bondmat[i,j] = 1
                Bondmat[j,i] = 1
                pic.append([i,j])                 # Bond length
            j = j+1
        i = i+1

    i = 0
    j = 0
    k = 0
    while i < n:
        j = 0
        while j < n:
            if Bondmat[i,j] == 1:
                k = j+1
                while k < n:
                    if Bondmat[i,k] == 1:
                        aa = PICvalue(x1,[[j,i,k]])
                        if aa[0] < PI*170/180:
                            pic.append([j,i,k])         # Bond angle
                    k = k+1
            j = j+1
        i = i+1
    
    i = 0
    j = 0
    k = 0
    m = 0
    while i < n:
        j = 0
        while j < n:
            if Bondmat[i,j] == 1:
                k = 0
                while k < n:
                    if Bondmat[i,k] == 1 and k != j:
                        m = 0
                        while m < n:
                            if Bondmat[j,m] == 1 and m != i and m != k:
                                aa = PICvalue(x1,[[k,i,j],[i,j,m]])
                                if aa[0] > PI*170/180:
                                    pic.append([k,j,m])
                                    pic.append([m,j,i,k])
                                elif aa[1] > PI*170/180:
                                    pic.append([m,i,k])
                                    pic.append([k,i,j,m])
                                else:
                                    aa = PICvalue(x1,[[k,i,j,m,-2]])
                                    bb = PICvalue(x2,[[k,i,j,m,-2]])
                                    if abs(aa[0]) + abs(bb[0]) > PI:
                                        pic.append([k,i,j,m,-3])            # Dihedral
                                    else:
                                        pic.append([k,i,j,m,-2])            # Dihedral
                            m = m+1
                    k = k+1
            j = j+1
        i = i+1
    
    return pic
    # pic is a list of lists representing PIC chosen


def Bpic(xcoor,pic):            # To get B matrix between PIC and Cartesian
    # xcoor should be a 3n list of Cartesian coordinates
    # pic should be a list of PICs
    Bp = np.mat(np.zeros((len(pic),len(xcoor))))
    pic0 = PICvalue(xcoor,pic)
    d_x = 0.0001
    i = 0
    while i < len(xcoor):
        XX = xcoor[:]
        XX[i] = XX[i] + d_x
        deltapic = PICvalue(XX,pic)
        j = 0
        while j < len(pic):
            Bp[j,i] = (deltapic[j]-pic0[j])/d_x
            j = j+1
        i = i+1
    return Bp
    # Bp is a Npic x 3n matrix