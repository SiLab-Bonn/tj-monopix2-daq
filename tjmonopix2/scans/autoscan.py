# File intended for automatic parameter sweeps
# 
# so for example to find good values for the DACs
# 


from scan_analog import AnalogScan
import numpy as np
import pathlib

#regs_to_test = ['ITHR', 'IBIAS', 'ICASN', 'IDB', 'ITUNE', 'ICOMP', 'IDEL', 'VRESET', 'VCASP', 'VCLIP', 'VCASC', 'IRAM', 'VH', 'VL']
register_config = {
    'ITHR': {
        'enabled': True,
        'min': 0,
        'max': 60,
        'step': 2,
    },
    'VRESET': {
        'enabled': True,
        'min': 0,
        'max': 170,
        'step': 5,
    },
    'VCASC': {  # causes unrecoverable sof_error
        'enabled': False,
        'min': 30,
        'max': 150,
        'step': 5,
    },
    'VCASP': {
        'min': 0,
        'max': 160,
        'step': 5,
    },
    'HV': {
        'min': 120,
        'max': 256,
        'step': 5,
    },
    
    'IBIAS': {
        'min': 0,
        'max': 256,
        'step': 10,
    },
    'ICASN': {
        'min': 0,
        'max': 100,
        'step': 2,
    },
    'ICOMP': {
        'min': 0,
        'max': 256,
        'step': 20,
    },
    'IDB': {
        'min': 0,
        'max': 256,
        'step': 10,
    },
    'IDEL': {
        'min': 0,
        'max': 256,
        'step': 20,
    },
    'IRAM': {
        'min': 0,
        'max': 256,
        'step': 20,
    },
    'ITUNE': {
        'min': 0,
        'max': 256,
        'step': 20,
    },
}





scan_configuration = {
    'start_column': 0,
    'stop_column': 512,
    'start_row': 10,
    'stop_row': 11,
}

register_overrides_default = {
    'n_injections' : 50,
    'ITHR': 50,
    'VL': 30,
    'VH': 150,
}

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
            
    
    #print("Got: {} from {} possible hits ({}%)".format(n_hits, n_inj, n_hits/n_inj*100))
    
    cols = regs.copy()
    cols["n_hits_1"] = np.sum(hist_occ[0:224, :], axis=(0,1,2))
    tots = hist_tot[0:244, 10]
    cols["avg_tot_1"] = tots[np.nonzero(tots)].mean()
    cols["n_inj_1"] = n_inj_12
    
    cols["n_hits_2"] = np.sum(hist_occ[224:448, :], axis=(0,1,2))
    tots = hist_tot[244:488, 10]
    cols["avg_tot_2"] = tots[np.nonzero(tots)].mean()
    cols["n_inj_2"] = n_inj_12
    
    cols["n_hits_3"] = np.sum(hist_occ[448:480, :], axis=(0,1,2))
    tots = hist_tot[448:480, 10]
    cols["avg_tot_3"] = tots[np.nonzero(tots)].mean()
    cols["n_inj_3"] = n_inj_34
    
    cols["n_hits_4"] = np.sum(hist_occ[480:512, :], axis=(0,1,2))
    tots = hist_tot[480:512, 10]
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

if __name__ == "__main__":
    
    for reg in register_config:
        conf = register_config[reg]
        if conf.get('enabled', True):
            for val in range(conf.get('min', 0), conf.get('max', 256), conf.get('step', 5)):
                for retries in range(3):
                    try:
                        ro = register_overrides_default.copy()
                        ro[reg] = val
                        run_scan(register_overrides=ro, basename="autoscan_"+reg)
                        break
                    except KeyboardInterrupt:
                        exit(0)
                    except:
                        print("Error: retry...")
    



