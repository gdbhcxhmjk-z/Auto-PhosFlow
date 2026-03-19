import math
import scipy
import numpy as np
import scipy.linalg

def output_dat(outfile,k1,D1,S1,k2,D2,S2):
    # k should be a 3n list of frequencies in cm-1
    # D should be a 3n list of shift vector
    # S should be a 3nx3n matrix of Duschinsky rotation
    i = 0
    while i < len(k1):
        j = 0
        while j < len(k1):
            if S1[i,j] > 1:
                S1[i,j] = 1.
            elif S1[i,j] < -1:
                S1[i,j] = -1
            if S2[i,j] > 1:
                S2[i,j] = 1.
            elif S2[i,j] < -1:
                S2[i,j] = -1
            j = j+1
        i = i+1
    
    f = open(outfile,'w')
    f.write('BEGIN_BASIC_INFO\n')
    f.write('{:>4s}'.format('%d' % (len(k1)/3,)))
    f.write('  # num of atoms \n')
    f.write('{:>4s}'.format('%d' % (len(k1),)))
    f.write('  # num of modes \n')
    f.write('''END_BASIC_INFO

BEGIN_DATA_1
  BEGIN_DESCRIPTION_1

                 2         2
                  2       2
                   2     2
               D2  |2   2
                   | 222
                   |  |
                   |  |
              1    |  | 1
               1   |  |1
                1  |  1
                 1 | 1  D1
                  111

    Q1 = S(1 <- 2) Q2 + D2
    Q1 = S2        Q2 + D2
    Q2 = S(2 <- 1) Q1 + D1
    Q2 = S1        Q1 + D1
    n              : index of mode, from 1 to 3n
    m              : index of mode, from 1 to 3n-6
    sym            : irreducible representation
    freq   (cm-1 ) : frequency
    D      (a.u. ) : displacement of mode
    delta  ( 1   ) : dimensionless projection, delta = D * SQRT(freq)
    HR     ( 1   ) : Huang-Rhys factor, HR = 0.5 * delta^2 
    lam    (cm-1 ) : reorganization energy, lam = HR * \\hbar * freq\n''')
    f.write('\tZPE1 (Ground ) :   %.7f cm-1\n' % (sum(k1)/2,))
    f.write('\tZPE2 (Excited) :   %.7f cm-1\n' % (sum(k2)/2,))
    f.write('\tZPE2 - ZPE1    :     %.7f cm-1\n' % (sum(k2)/2 - sum(k1)/2,))
    f.write('''  END_DESCRIPTION_1
  BEGIN_OUTPUT_1
============================================================================================================================================\n''')
    f.write('   n   m sym1   freq1         D1     delta1        HR1       lam1 sym2   freq2         D2     delta2        HR2       lam2    g    e   S(g,e)\n')
    f.write('--------------------------------------------------------------------------------------------------------------------------------------------')
    f.write('\n')
    i = 0
    while i < len(k1):
        f.write('{:>4s}'.format('%d' % (i+1,)))
        if i < 6:
            f.write('{:>4s}'.format('0'))
        else:
            f.write('{:>4s}'.format('%d' % (i-5,)))
        f.write('{:>5s}'.format('A'))
        f.write('{:>8s}'.format('%.2f' % k1[i]))
        f.write('{:>12s}'.format('%.5f' % (D1[i]*80.28178)))
        f.write('{:>10s}'.format('%.5f' % math.sqrt(k1[i]*D1[i]**2*3.7565027*2*4*3.14159265359**2/10000)))
        f.write('{:>11s}'.format('%.5f' % (k1[i]*D1[i]**2*4*3.14159265359**2*3.7565027/10000,)))
        f.write('{:>11s}'.format('%.2f' % (D1[i]**2*k1[i]**2*0.01483008,)))
        f.write('{:>5s}'.format('A'))
        f.write('{:>8s}'.format('%.2f' % k2[i]))
        f.write('{:>12s}'.format('%.5f' % (D2[i]*80.28178)))
        f.write('{:>10s}'.format('%.5f' % math.sqrt(k2[i]*D2[i]**2*3.7565027*2*4*3.14159265359**2/10000)))
        f.write('{:>11s}'.format('%.5f' % (k2[i]*D2[i]**2*4*3.14159265359**2*3.7565027/10000,)))
        f.write('{:>11s}'.format('%.2f' % (D2[i]**2*k2[i]**2*0.01483008,)))
        f.write('{:>5s}'.format('%d' % (i+1,)))
        f.write('{:>5s}'.format('%d' % (i+1,)))
        f.write('{:>9s}'.format('%.4f' % S1[i,i]))
        f.write('\n')
        i = i+1
    f.write('''--------------------------------------------------------------------------------------------------------------------------------------------
  Total reorganization energy      (cm-1):''')
    ener1 = 0
    ener2 = 0
    i = 0
    while i < len(k1):
        ener1 = ener1 + D1[i]**2*k1[i]**2*0.01483008
        ener2 = ener2 + D2[i]**2*k2[i]**2*0.01483008
        i = i+1
    f.write('{:>20s}'.format('%.6f' % ener1))
    f.write('{:>18s}'.format('%.6f' % ener2))
    f.write('''\n--------------------------------------------------------------------------------------------------------------------------------------------
--------------------------------------------------------------------------------------------------------------------------------------------
  END_OUTPUT_1
END_DATA_1
''')
    f.write('''\nBEGIN_DUSH_1     Delta DUSH =   #######
  BEGIN_DUSH_INFORMATION1
  Qg = S(g,e) Qe + Dg
  END_DUSH_INFORMATION1
  BEGIN_DUSH_DATA_1
--------------------------------------------------------------------------------------------------------------------------------------------\n''')
    i = 0
    while i < len(k1):
        f.write('  MODE')
        f.write('{:>8s}'.format('%d' % (i+1,)))
        f.write('\n')
        j = 0
        while j < len(k1):
            f.write('{:>13s}'.format('%e' % S1[i,j]))
            if (j+1) % 10 == 0:
                f.write('\n')
            else:
                f.write(' ')
            j = j+1
        f.write('\n')
        i = i+1
    f.write('''--------------------------------------------------------------------------------------------------------------------------------------------
  END_DUSH_DATA_1
  BEGIN_DUSH_ORTH_TEST EPS =     ###########
  END_DUSH_ORTH_TEST
END_DUSH_1
BEGIN_DUSH_2     Delta DUSH =   ########
  BEGIN_DUSH_INFORMATION2
  Qe = S(e,g) Qg + De
  END_DUSH_INFORMATION2
  BEGIN_DUSH_DATA_2
--------------------------------------------------------------------------------------------------------------------------------------------\n''')
    i = 0
    while i < len(k1):
        f.write('  MODE')
        f.write('{:>8s}'.format('%d' % (i+1,)))
        f.write('\n')
        j = 0
        while j < len(k1):
            f.write('{:>13s}'.format('%e' % S2[i,j]))
            if (j+1) % 10 == 0:
                f.write('\n')
            else:
                f.write(' ')
            j = j+1
        f.write('\n')
        i = i+1
    f.write('''--------------------------------------------------------------------------------------------------------------------------------------------
  END_DUSH_DATA_2
  BEGIN_DUSH_ORTH_TEST EPS =     #########
  END_DUSH_ORTH_TEST
END_DUSH_2
''')
    f.close()
    return


def output_abs(S1,S2):
    # S should be a 3nx3n matrix of Duschinsky rotation
    f = open('D:/testing examples/code/writeout.abs','w')
    f.write('#DUSH1 Qg = S(g,e) Qe + Dg\n')
    n = len(S1)
    i = 0
    j = 0
    while i < n:
        j = 0
        while j < n:
            f.write('{:>11s}'.format('%f' % S1[i,j]))
            j = j+1
        f.write('\n')
        i = i+1
    f.write('#DUSH2 Qe = S(e,g) Qg + De\n')
    i = 0
    j = 0
    while i < n:
        j = 0
        while j < n:
            f.write('{:>11s}'.format('%f' % S2[i,j]))
            j = j+1
        f.write('\n')
        i = i+1

    f.close()
    return


def output_info(coorx_g,coorx_e,Bp_g,Bp_e,Sge,Seg,PIC):
    dr2 = []
    i = 0
    while i < len(coorx_g)/3:
        dra2 = (coorx_g[3*i]-coorx_e[3*i])**2 + (coorx_g[3*i+1]-coorx_e[3*i+1])**2 + (coorx_g[3*i+2]-coorx_e[3*i+2])**2
        dr2.append(dra2)
        i = i+1
    drmax = math.sqrt(max(dr2))
    drrms = math.sqrt(sum(dr2)/len(dr2))

    abn_g = []
    abn_e = []
    i = 0
    j = 0
    while i < len(coorx_g)-6:
        j = 0
        while j < len(coorx_g)-6:
            if abs(Sge[i,j]) > 1:
                abn_g.append(abs(Sge[i,j]))
            if abs(Seg[i,j]) > 1:
                abn_e.append(abs(Seg[i,j]))
            j = j+1
        i = i+1
    
    ug,sg,vgt = scipy.linalg.svd(Bp_g)
    ue,se,vet = scipy.linalg.svd(Bp_e)

    f = open('D:/testing examples/code/writeout.info','w')
    f.write('Internal Coordinates Calculation Information\n\n')
    f.write('The biggest and the RMS atomic displacement between g-structure and e-structure after Eckart rotation:\n')
    f.write('{:>4s}'.format('%.2f' % drmax))
    f.write(' Amstrong       ')
    f.write('{:>4s}'.format('%.2f' % drrms))
    f.write(' Amstrong\n')
    if drmax < 0.1:
        f.write('Rigid')
    elif drmax < 1:
        f.write('Semi-rigid')
    elif drmax < 2:
        f.write('Flexible')
    else:
        f.write('Very flexible')
    f.write('\n')

    f.write('\nNumber of atoms:')
    f.write('%d' % int(len(coorx_g)/3))
    f.write('\nNumber of PICs:')
    f.write('%d' % len(PIC))
    
    f.write('\n\nThe 9 smallest and 3 biggest singular values of Bp_g:\n')
    i = 1
    while i < 10:
        f.write('{:>12s}'.format('%.4e' % sg[-i]))
        i = i+1
    f.write('\n')
    f.write('{:>12s}'.format('%.4e' % sg[0]))
    f.write('{:>12s}'.format('%.4e' % sg[1]))
    f.write('{:>12s}'.format('%.4e' % sg[2]))

    f.write('\nThe 9 smallest and 3 biggest singular values of Bp_e:\n')
    i = 1
    while i < 10:
        f.write('{:>12s}'.format('%.4e' % se[-i]))
        i = i+1
    f.write('\n')
    f.write('{:>12s}'.format('%.4e' % se[0]))
    f.write('{:>12s}'.format('%.4e' % se[1]))
    f.write('{:>12s}'.format('%.4e' % se[2]))

    f.write('\n\nQg = S(g,e) Qe + Dg')
    f.write('\nNumber of items of S(g,e) with absolute value bigger than 1:\n')
    f.write('%d' % len(abn_g))
    f.write('\nThe biggest absolute value of items of S(g,e):\n')
    if len(abn_g) > 0:
        f.write('%.3f' % max(abn_g))
    else:
        f.write('--')

    f.write('\n\nQe = S(e,g) Qg + De')
    f.write('\nNumber of items of S(e,g) with absolute value bigger than 1:\n')
    f.write('%d' % len(abn_e))
    f.write('\nThe biggest absolute value of items of S(e,g):\n')
    if len(abn_e) > 0:
        f.write('%.3f' % max(abn_e))
    else:
        f.write('--')

    f.close()
    return
