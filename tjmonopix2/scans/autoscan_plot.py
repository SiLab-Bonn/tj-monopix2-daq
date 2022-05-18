
import numpy as np
import os, glob, re
import pandas as pd
import matplotlib.pyplot as plt




sample="W8R3"
basepath="output_data"

commit="Commit: " + os.popen('git log --pretty=format:"%h" -n 1').read()   # gets current commit-id for documentation
files = hist_occ_files = glob.glob(basepath+'/*.dat')

defaults = {'IBIAS': 50,
            'ICASN': 0,
            'IDB': 100,
            'ITUNE': 53,
            'ITHR': 50,
            'ICOMP': 80,
            'IDEL': 88,
            'VRESET': 143,
            'VCASP': 93,
            'VH': 150,
            'VL': 30,
            'VCLIP': 255,
            'VCASC': 228,
            'IRAM': 50,}


for f in files:
    reg = re.findall("_.*_(.*?)\.", f)[0]  # extract register name (precisely: part between first '_' and '.')
    print(reg)
    
    df = pd.read_csv(f, delimiter=' ')
    df['Normal FE (1)'] = df['n_hits_1'] / df['n_inj_1']
    df['Cascode FE (2)'] = df['n_hits_2'] / df['n_inj_2']
    df['HV Casc. FE (3)'] = df['n_hits_3'] / df['n_inj_3']
    df['HV FE (4)'] = df['n_hits_4'] / df['n_inj_4']
    
    
    fig, ax= plt.subplots()

    ax.set_ylabel("Injection Efficiency")
    
    ys = ['Normal FE (1)', 'Cascode FE (2)', 'HV Casc. FE (3)', 'HV FE (4)', ]
    df.plot(x=reg, y=ys, style='-+')
    plt.hlines(y=1, xmin=min(df[reg]), xmax=max(df[reg]), colors='red')
    plt.vlines(x=defaults[reg], ymin=0, ymax=1, colors='green')
    plt.grid()
    plt.xlabel(reg + " / LSBs")
    plt.ylabel("Fraction of received over injected")
    plt.text(0.9, -0.08, commit,
     horizontalalignment='center',
     verticalalignment='top',
     transform = ax.transAxes)
    plt.title(sample+": DAC Parameter scan: "+reg)
    plt.text(x=defaults[reg]-9, y=0.5, s="default value", rotation=90, size=12, color='green')
    
    plt.savefig(basepath+"/hiteff_"+reg+".png")
    
    #print(df)
    


