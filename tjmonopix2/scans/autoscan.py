# File intended for automatic parameter sweeps
# 
# so for example to find good values for the DACs
# 
# you need to copy autoscan-yaml.default to autoscan.yaml for custom modicications (autoscan.yaml is in .gitignore)

from scan_analog import AnalogScan
import numpy as np
import pathlib
import traceback
import time
import yaml
import os
from tqdm import tqdm
import logging



with open('autoscan.yaml', 'r') as file:
    register_config = yaml.safe_load(file)

# values here will be overridden by autoscan.yaml
register_overrides_default = {
    'n_injections' : 50,
}

register_overrides_default.update(register_config['register-overrides'])

scan_configuration = {
    'start_column': 0,
    'stop_column': 512,
    'start_row': 10,
    'stop_row': 11,
}


# This function looks for processes containing monopix2_producer.py
# If it finds one, it stalls the scan until it goes away...
def check_availability():
    while int(os.popen('ps aux | grep -c "monopix2_producer\.py"').read()) > 0:
        print("monopix2_producer.py is running - sending SIGUSR1 and waiting for it to be finished")
        pid = os.popen('ps aux | grep "monopix2_producer\.py"| grep -o "^[a-zA-Z0-9]*\ *[0-9]*"|grep -o "[0-9]*"').read()
        print(pid)
        os.popen('kill -USR1 '+pid).read()
        time.sleep(60)

registers = ['IBIAS', 'VH', 'ICASN', 'IDB', 'ITUNE', 'ITHR', 'ICOMP', 'IDEL', 'VRESET', 'VCASP', 'VL', 'VCLIP', 'VCASC', 'IRAM']

def run_scan(register_overrides=register_overrides_default, basename='autoscan'):
    hist_occ = None
    hist_tot = None
    regs={}
    
    with AnalogScan(scan_config=scan_configuration, register_overrides=register_overrides) as scan:
        scan.start()
        hist_occ = scan.hist_occ
        hist_tot = scan.hist_tot
        regs = scan.scan_registers.copy()
     
    n_inj_12 = 224 * \
            (scan_configuration['stop_row']-scan_configuration['start_row']) * \
            register_overrides.get('n_injections', 50)
            
    n_inj_34 = 32 * \
            (scan_configuration['stop_row']-scan_configuration['start_row']) * \
            register_overrides.get('n_injections', 50)
            
    
    mean_tot = np.zeros((512,512))
    bins = np.linspace(1,127,128)
    for col in range(512):
        for row in range(512):
            heights = hist_tot[col][row][0]
            if np.sum(heights) > 0:
                mean_tot[col][row] = np.dot(bins,heights)/(np.sum(heights))
            else:
                mean_tot[col][row] = 0
    
    
    
    cols = regs.copy()
    cols["n_hits_1"] = np.sum(hist_occ[0:224, :], axis=(0,1,2))
    tots = mean_tot[0:244, scan_configuration['start_row']:scan_configuration['stop_row']]
    cols["avg_tot_1"] = tots[np.nonzero(tots)].mean()
    cols["n_inj_1"] = n_inj_12
    
    cols["n_hits_2"] = np.sum(hist_occ[224:448, :], axis=(0,1,2))
    tots = mean_tot[244:488, scan_configuration['start_row']:scan_configuration['stop_row']]
    cols["avg_tot_2"] = tots[np.nonzero(tots)].mean()
    cols["n_inj_2"] = n_inj_12
    
    cols["n_hits_3"] = np.sum(hist_occ[448:480, :], axis=(0,1,2))
    tots = mean_tot[448:480, scan_configuration['start_row']:scan_configuration['stop_row']]
    cols["avg_tot_3"] = tots[np.nonzero(tots)].mean()
    cols["n_inj_3"] = n_inj_34
    
    cols["n_hits_4"] = np.sum(hist_occ[480:512, :], axis=(0,1,2))
    tots = mean_tot[480:512, scan_configuration['start_row']:scan_configuration['stop_row']]
    cols["avg_tot_4"] = tots[np.nonzero(tots)].mean()
    cols["n_inj_4"] = n_inj_34
    
    cols["n_inj_perpixel"] = register_overrides.get('n_injections', 50)
    
    
    path = "output_data/{}.dat".format(basename)
    existing = pathlib.Path(path).exists()
    file1 = open(path, 'a')
    if not existing:
        for e in cols:
            file1.write(e + " ")
        file1.write("\n")
    # Opening a file
    
    for k in cols:
        file1.write(str(cols[k])+ " ")
    file1.write("\n")
    
    file1.flush()
    file1.close()

    return hist_occ[:, scan_configuration['start_row']:scan_configuration['stop_row']], hist_tot[:, scan_configuration['start_row']:scan_configuration['stop_row']]


if __name__ == "__main__":
    
    for conf in register_config['1d-scans']:
        reg = conf['register']
        default_enabled = register_config.get('enable_default', True)
        
        if conf.get('enabled', default_enabled):
            rng = range(conf.get('min', 0), conf.get('max', 256), conf.get('step', 5))
            pixogram = np.zeros((513, len(rng)))
            for index, val in enumerate(tqdm(rng)):
                for retries in range(3):
                    check_availability()
                    try:
                        ro = register_overrides_default.copy()
                        ro[reg] = val
                        occ, tot = run_scan(register_overrides=ro, basename="autoscan_"+reg)
                        pixogram[0:-1, index] = occ.flatten()
                        pixogram[-1, index] = val
                        break
                    except KeyboardInterrupt:
                        exit(0)
                    except:
                        traceback.print_exc()
                        print("Error: retry in 10 secs...")
                        time.sleep(10)
                        print("that has passed: now again ;)")
            np.save("output_data/pixogram_"+reg+".npy", pixogram)


