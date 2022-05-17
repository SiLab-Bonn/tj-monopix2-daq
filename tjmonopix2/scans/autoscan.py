# File intended for automatic parameter sweeps
# 
# so for example to find good values for the DACs
# 


from scan_analog import AnalogScan
import numpy as np
import pathlib

scan_configuration = {
    'n_injections' : 10,
    'start_column': 0,
    'stop_column': 10,
    'start_row': 0,
    'stop_row': 10,
}

register_overrides_default = {
    'ITHR': 50,
    'VL': 30,
    'VH': 150,
}

registers = ['IBIAS', 'ICASN', 'IDB', 'ITUNE', 'ITHR', 'ICOMP', 'IDEL', 'VRESET', 'VCASP', 'VH', 'VL', 'VCLIP', 'VCASC', 'IRAM']

def run_scan(register_overrides=register_overrides_default, basename='autoscan'):
    hist_occ = None
    regs={}
    
    with AnalogScan(scan_config=scan_configuration, register_overrides=register_overrides) as scan:
        scan.start()
        hist_occ = scan.hist_occ
        regs = scan.scan_registers.copy()
    
    n_hits = np.sum(hist_occ, axis=(0,1,2))
    
    n_inj = (scan_configuration['stop_column']-scan_configuration['start_column']) * \
            (scan_configuration['stop_row']-scan_configuration['start_row']) * \
            scan_configuration['n_injections']
    print("Got: {} from {} possible hits ({}%)".format(n_hits, n_inj, n_hits/n_inj*100))
    
    
    cols = regs.copy()
    cols["n_hits"] = n_hits
    cols["n_inj_total"] = n_inj
    cols["n_inj_perpixel"] = scan_configuration['n_injections']
    
    
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
    regs_to_test = ['ITHR', 'IBIAS', 'ICASN', 'IDB', 'ITUNE', 'ICOMP', 'IDEL', 'VRESET', 'VCASP', 'VCLIP', 'VCASC', 'IRAM', 'VH', 'VL']
    for reg in regs_to_test:
        for val in range(0, 256, 5):
            for retries in range(3):
                try:
                    ro = register_overrides_default.copy()
                    ro[reg] = val
                    run_scan(register_overrides=ro, basename="autoscan_"+reg)
                    break
                except:
                    print("Error: retry...")
    



