
def num2mass(atonum):                           # To get atomic mass from atomic numbers
    # atonum should be a list of int
    atomass = []                                 # Only valid for C, H, O, N, Si, S
    k = 0
    while k < len(atonum):
        if atonum[k]==1:
            atomass.append(1.00782504)
        elif atonum[k]==5:
            atomass.append(11.0093)
        elif atonum[k]==6:
            atomass.append(12.0)
        elif atonum[k]==7:
            atomass.append(14.0030740)
        elif atonum[k]==8:
            atomass.append(15.9949146)
        elif atonum[k]==14:
            atomass.append(27.9769284)
        elif atonum[k]==16:
            atomass.append(31.9720718)
        k = k+1
    return atomass
    # atomass is a list of atomic mass( dalton as unit)

def name2num(atoname):                          # To get atomic number from name
    ato_num = []
    for i in atoname:
        if i == 'h' or i == 'H':
            ato_num.append(1)
        elif i == 'b' or i == 'B':
            ato_num.append(5)
        elif i == 'c' or i == 'C':
            ato_num.append(6)
        elif i == 'n' or i == 'N':
            ato_num.append(7)
        elif i == 'o' or i == 'O':
            ato_num.append(8)
        elif i == 'si' or i == 'Si':
            ato_num.append(14)
        elif i == 's' or i == 'S':
            ato_num.append(16)
    return ato_num

def num2radii(atonum):                      # To get covalent radius from atomic numbers, Amstrong as unit
    radii = []
    for i in atonum:
        if i == 1:
            radii.append(0.32)
        elif i == 5:
            radii.append(0.82)
        elif i == 6:
            radii.append(0.77)
        elif i == 7:
            radii.append(0.71)
        elif i == 8:
            radii.append(0.66)
        elif i == 14:
            radii.append(1.13)
        elif i == 16:
            radii.append(1.02)
    return radii