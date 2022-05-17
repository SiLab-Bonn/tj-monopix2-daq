
import numpy as np
import os, glob, re
import pandas as pd
import matplotlib.pyplot as plt

sample="output_data"
files = hist_occ_files = glob.glob(sample+'/*.dat')

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
    df['efficiency'] = df['n_hits'] / df['n_inj_total']
    
    
    fig, ax= plt.subplots()

    ax.set_ylabel("Efficiency")
    
    df.plot(x=reg, y="efficiency", style='-+', legend=None)
    plt.hlines(y=1, xmin=0, xmax=255, colors='red')
    plt.vlines(x=defaults[reg], ymin=0, ymax=1, colors='green')
    plt.grid()
    plt.xlabel(reg + " / LSBs")
    plt.ylabel("Fraction of received over injected")
    plt.title(sample+": DAC Parameter scan: "+reg)
    plt.text(x=defaults[reg]-9, y=0.5, s="default value", rotation=90, size=12, color='green')
    
    plt.savefig(sample+"/hiteff_"+reg+".png")
    
    


