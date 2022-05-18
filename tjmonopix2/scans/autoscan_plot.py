
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
    
    
    df['ToT Normal FE (1)'] = df['avg_tot_1']
    df['ToT Cascode FE (2)'] = df['avg_tot_2']
    df['ToT HV Casc. FE (3)'] = df['avg_tot_3']
    df['ToT HV FE (4)'] = df['avg_tot_4']
    
    
    fig, ax= plt.subplots(2, 1, sharex=True)
    fig.suptitle(sample+": DAC Parameter scan: "+reg)
    
    ys = ['Normal FE (1)', 'Cascode FE (2)', 'HV Casc. FE (3)', 'HV FE (4)', ]
    ytots = ['ToT Normal FE (1)', 'ToT Cascode FE (2)', 'ToT HV Casc. FE (3)', 'ToT HV FE (4)', ]
    df.plot(ax=ax[0], x=reg, y=ys, style='-+')
    
    
    ax[0].hlines(y=1, xmin=min(df[reg]), xmax=max(df[reg]), colors='red')
    ax[0].vlines(x=defaults[reg], ymin=0, ymax=1, colors='green')
    ax[0].grid()
    
    ax[0].set_ylabel("Injection efficiency")
    
    df.plot(ax=ax[1], x=reg, y=ytots, style='-+')
    
    ax[1].set_ylabel("Average ToT / LSBs")
    ax[1].grid()
    ax[1].set_xlabel(reg + " / LSBs")
    
    
    
    ax[1].text(0.9, -0.15, commit,
     horizontalalignment='center',
     verticalalignment='top',
     transform = ax[1].transAxes)
    
    ax[0].text(x=defaults[reg], y=0.3, s="default value", rotation=90, size=8, color='green',horizontalalignment='right',)
    
    plt.savefig(basepath+"/hiteff_"+reg+".png")
    
    #print(df)
    


