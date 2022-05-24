
import numpy as np
import os, glob, re
import pandas as pd
import matplotlib.pyplot as plt
import yaml



sample="W8R3"
basepath="output_data"

commit="Commit: " + os.popen('git log --pretty=format:"%h" -n 1').read()   # gets current commit-id for documentation


with open('autoscan.yaml', 'r') as file:
    register_config = yaml.safe_load(file)


register_text = ''
cnt = 0
for reg in register_config['register-overrides']:
    cnt += 1
    register_text = "{}{}: {}, ".format(register_text, reg, register_config['register-overrides'][reg])
    if cnt > 3:
        cnt = 0
        register_text += '\n'
        

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

files = glob.glob(os.path.join(basepath,'autoscan_*.dat'))
for f in files:
    reg = re.findall("_.*_(.*?)\.", f)[0]  # extract register name (precisely: part between second '_' and '.')
    print('autoscan: ', reg)
    
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
     
    ax[1].text(0.1, -0.15, register_text, size=6,
     horizontalalignment='center',
     verticalalignment='top',
     transform = ax[1].transAxes)
     
    
    ax[0].text(x=defaults[reg], y=0.3, s="default value", rotation=90, size=8, color='green',horizontalalignment='right',)
    
    plt.savefig(os.path.join(basepath,"hiteff_"+reg+".png"))
    
    #print(df)
    
    
    
    
    
files = glob.glob(os.path.join(basepath,'pixogram*.npy'))
for f in files:
    reg = re.findall("_.*_(.*?)\.", f)[0]  # extract register name (precisely: part between second '_' and '.')
    print('pixoplot: ', reg)
    
    pxg = np.load(f)
    
    if len(pxg[:,0]) == 512:
        extent = (50, 255, 511, 0)
    else:  # extra column with register information
        extent = (np.min(pxg[-1,:]), np.max(pxg[-1,:]), 511, 0)
    xvalues = pxg[-1,:]
    pxg[0:512, :][pxg[0:512, :] > 50] = None
    
    # multiple 1D plots overlayed
    fig, ax= plt.subplots()
    fig.suptitle(sample+": DAC Parameter scan per Pixel: "+reg)
    
    slices = [0, 224, 448, 480, 512]
    ylabels = 'Normal FE (1)', 'Cascode FE (2)', 'HV Casc. FE', 'HV FE', 
    
    prop_cycle = plt.rcParams['axes.prop_cycle']
    colors = prop_cycle.by_key()['color'] 
    
    for i in range(4):
        for col in range(slices[i], slices[i+1]):
            if col%30 == 0:
                ax.plot(xvalues, pxg[col,:], '-+', linewidth=0.5, color=colors[i], alpha=0.5)
    
    ax.grid()
    ax.set_ylabel("Injected hits")
    
    ax.text(0.9, -0.15, commit,
     horizontalalignment='center',
     verticalalignment='top',
     transform = ax.transAxes)
     
    ax.text(0.1, -0.15, register_text, size=6,
     horizontalalignment='center',
     verticalalignment='top',
     transform = ax.transAxes)
    
    ax.set_xlabel(reg + " / LSBs")
    plt.tight_layout()
    
    
    plt.savefig(os.path.join(basepath,"pixoplot_"+reg+".png"))
    
    
plt.rcParams['figure.figsize'] = 7, 12
for f in files:
    reg = re.findall("_.*_(.*?)\.", f)[0]  # extract register name (precisely: part between second '_' and '.')
    print('pixogram: ', reg)
    
    pxg = np.load(f)
    
    if len(pxg[:,0]) == 512:
        extent = (50, 255, 511, 0)
    else:  # extra column with register information
        extent = (np.min(pxg[-1,:]), np.max(pxg[-1,:]), 511, 0)
    xvalues = pxg[-1,:]
    pxg[0:512, :][pxg[0:512, :] > 50] = None
    
    
    # the 2D plot with color-code:
    fig, ax= plt.subplots(5, 1, gridspec_kw={'height_ratios': [224, 224, 32, 32, 5]})
    fig.suptitle(sample+": DAC Parameter scan per Pixel: "+reg)
    slices = [0, 224, 448, 480, 512]
    ylabels = 'Normal FE (1)', 'Cascode FE (2)', 'HV Casc. FE', 'HV FE', 
    for i in range(4):
        im=ax[i].imshow(pxg, interpolation='none', aspect='auto', vmin=0, vmax=50, extent=extent)
        ax[i].set_ylim(slices[i], slices[i+1])
        
        ax[i].set_ylabel("colum:\n"+ylabels[i])
        ax[i].invert_yaxis()
        ax[i].set_xlabel(reg + " / LSBs")
        
    fig.subplots_adjust(right=0.8)

    cbar = fig.colorbar(im, cax=ax[4],orientation='horizontal')
    cbar.set_label('number of hits')
    
    plt.tight_layout()
    
    ax[3].text(0.9, -4, commit,
     horizontalalignment='center',
     verticalalignment='top',
     transform = ax[4].transAxes)
     
    ax[3].text(0.1, -4, register_text, size=6,
     horizontalalignment='center',
     verticalalignment='top',
     transform = ax[4].transAxes)
    
    plt.savefig(os.path.join(basepath,"pixogram_"+reg+".png"))
    
    
    
    
    

