import numpy as np
import math
import scipy.linalg

def deltaR(r1,r2):
    # r1 and r2 should be 1x3n list of Cartesian coordinates(Amstrong as unit)
    i = 0
    deltar = []
    while i < len(r1)/3:
        dri = math.sqrt((r1[3*i]-r2[3*i])**2 + (r1[3*i+1]-r2[3*i+1])**2 + (r1[3*i+2]-r2[3*i+2])**2)
        deltar.append(dri)
        i = i+1
    return max(deltar)
    # The biggest distance of the two locations of the same atom is returned(Amstrong as unit)

def Eckart(r1,r2,fmat1,fmat2,m):
    # r1 and r2 should be 1x3n list of Cartesian coordinates(Amstrong as unit)
    # fmat1 and fmat2 should be 3nx3n matrix of force constants related to r1 and r2, respectively
    # m should be a 1xn matrix of atomic mass(Dalton as unit)
    r = np.mat(r1)
    r = np.reshape(r,(int(len(r1)/3),3))
    r = r.T
    R = np.mat(r2)
    R = np.reshape(R,(int(len(r2)/3),3))
    R = R.T
    mm = np.mat(np.diag(m))
    A = r*mm*R.T
    lam1,u1 = scipy.linalg.eigh(A*A.T)
    u1[:,2] = np.cross(u1[:,0],u1[:,1])
    u1 = np.mat(u1)
    lam2,u2 = scipy.linalg.eigh((A.T)*A)
    u2[:,2] = np.cross(u2[:,0],u2[:,1])
    u2 = np.mat(u2)
    T1 = u2*(u1.T)

    u2[:,1] = -u2[:,1]
    u2[:,2] = -u2[:,2]
    T2 = u2*(u1.T)

    u2[:,0] = -u2[:,0]
    u2[:,2] = -u2[:,2]
    T3 = u2*(u1.T)

    u2[:,1] = -u2[:,1]
    u2[:,2] = -u2[:,2]
    T4 = u2*(u1.T)

    Tr1 = T1*r
    Tr2 = T2*r
    Tr3 = T3*r
    Tr4 = T4*r

    r_1 = np.reshape(Tr1.T,(1,len(r1)))
    r_1 = r_1.tolist()
    r_1 = r_1[0]
    r_2 = np.reshape(Tr2.T,(1,len(r1)))
    r_2 = r_2.tolist()
    r_2 = r_2[0]
    r_3 = np.reshape(Tr3.T,(1,len(r1)))
    r_3 = r_3.tolist()
    r_3 = r_3[0]
    r_4 = np.reshape(Tr4.T,(1,len(r1)))
    r_4 = r_4.tolist()
    r_4 = r_4[0]

    dr = []
    dr.append(deltaR(r_1,r2))
    dr.append(deltaR(r_2,r2))
    dr.append(deltaR(r_3,r2))
    dr.append(deltaR(r_4,r2))
    drmin = min(dr)
    if drmin == dr[0]:
        i = 0
        t = T1
        while i < len(r2)/3-1:
            t = scipy.linalg.block_diag(t,T1)
            i = i+1
        fmat1 = t*fmat1*(t.T)
        return r_1,r2,fmat1,fmat2,T1
    elif drmin == dr[1]:
        i = 0
        t = T2
        while i < len(r2)/3-1:
            t = scipy.linalg.block_diag(t,T2)
            i = i+1
        fmat1 = t*fmat1*(t.T)
        return r_2,r2,fmat1,fmat2,T2
    elif drmin == dr[2]:
        i = 0
        t = T3
        while i < len(r2)/3-1:
            t = scipy.linalg.block_diag(t,T3)
            i = i+1
        fmat1 = t*fmat1*(t.T)
        return r_3,r2,fmat1,fmat2,T3
    elif drmin == dr[3]:
        i = 0
        t = T4
        while i < len(r2)/3-1:
            t = scipy.linalg.block_diag(t,T4)
            i = i+1
        fmat1 = t*fmat1*(t.T)
        return np.array(r_4, dtype=float),np.array(r2, dtype=float),fmat1,fmat2,T4
    # r_i being the rotated r1
    # r2 and fmat2 unchanged
    # fmat1 being the force matrix related to r_i
    # Ti being the Eckart rotation matrix, which rotates r1 and regards r2 as reference conformation