# ------------------------------------------------------------
# TJ-Monopix2: Hardware test for digital parts of the chip (registers only for now)
# 
# to get more information about arguments:
# 
# > python3 test_digital.py --help
#
# ------------------------------------------------------------
#

import os
import yaml
import numpy as np
import argparse
from tqdm import tqdm
from time import sleep
from tjmonopix2.system.bdaq53 import BDAQ53
from tjmonopix2.system.tjmonopix2 import TJMonoPix2
from datetime import date

import tjmonopix2.scan.report_to_elog

# those registers somehot winterfere eg diable transmission or

# 147: CHSYNC_THR_HIGH_CONF&LOW, value changes on its own - probably read only
# 154: multiple bits, eg CMOS_TX_EN_CONF - writing 1 causes Read timeout
skip = [12, 13, 14, 15, 147, 154]

# 153: LOAD_CONF
skip.extend([153, ]) # work on W5R12 but not on W8R3

regs_safe = [x for x in range(146, 218) if x not in skip]

# analog parts and so on
regs_dangerous = range(0, 4)

# ================    Argument parsing    ================
parser = argparse.ArgumentParser(description='Writes data into the configuration registers of the DUT (TJ-Monopix2) and reads it back in. Severl runs with different patterns and random data are sent by default')
parser.add_argument('-q', '--quick', action='store_true', help='Quick test: only one run of random pattern')
parser.add_argument('-D', '--dangerous', action='store_true', help='Also test registers that potentially damage the chip: like DAC registers, but probably they don\'t anyway')

args = parser.parse_args()

quick = args.quick
if args.dangerous:
    regs_to_test = regs_safe
    regs_to_test.extend(regs_dangerous)
else:
    regs_to_test = regs_safe

# ================        BDAQ init        ================
with open(os.path.join('..', 'tjmonopix2', 'system', 'bdaq53.yaml'), 'r') as f:
    cnfg = yaml.full_load(f)

daq = BDAQ53(cnfg)
daq.init()

chip = TJMonoPix2(daq)
chip.init()




# ================        Testing loops        ================


def reload():
    daq.rx_channels["rx0"].set_en(True)  # Enable RX module in firmware

    daq.reset_fifo()  # Clear FIFO before reading data
    raw_data = daq["FIFO"].get_data()  # Get FIFO contents
    hit_data, reg_data = chip.interpret_data(raw_data)  # Interpret data


def set_register(reg, value):
    if type(reg) == int:
        #print("integer: ", reg, " to 0x{:04X}".format(value))
        chip._write_register(reg, value)
        
    else:
        #print("str: ", reg, " to 0x{:04X}".format(value))
        chip.registers[reg].write(value)
        

def check_register(reg, value):
    value = int(value)
    if type(reg) == int:
        read = chip._get_register_value(reg)
    else:
        read = chip.registers[reg].read()
    if read != value:
        print("Error: data mismatch on register {}: Should be {:04x}, was: {:04x}".format(reg, value, read))
        return 1
    return 0

def run_test(regs, data, description):
    print("Writing {}".format(description))
    for i in tqdm(range(len(regs))):
        set_register(regs[i], data[i])
        #sleep(2)
        
    sleep(0.5)
    reload()
    
    print("Reading {}".format(description))
    ret = 0
    for i in tqdm(range(len(regs))):
        ret += check_register(regs[i], data[i])
        
    return ret
    
errors = 0
l = len(regs_to_test)

if quick:
    data = np.random.randint(0, 2**16, size=l)
    errors += run_test(regs_to_test, data, "1/1: random data")
else:
    data = np.zeros(l, dtype = int)
    errors += run_test(regs_to_test, data, "1/6: all zeros")

    data = np.ones(l, dtype = int)*(2**16-1)
    errors += run_test(regs_to_test, data, "2/6: all ones")

    data = np.ones(l, dtype = int)*0x5555
    errors += run_test(regs_to_test, data, "3/6: 0101 pattern")

    data = np.ones(l, dtype = int)*0xAAAA
    errors += run_test(regs_to_test, data, "4/6: 1010 pattern")

    data = np.random.randint(0, 2**16, size=l)
    errors += run_test(regs_to_test, data, "5/6: random data 1")

    np.random.seed(783)
    data = np.random.randint(0, 2**16, size=l)
    errors += run_test(regs_to_test, data, "6/6: random data 2")



if errors == 0:
    print("SUCCESS: All registers seem good!")
    done=True
else:
    print("ERROR: some registers failed to write/read back: errors on {} registers/attempts".format(errors))
    done=False

# Closing
daq.close()

attachments = [glob.(os.path.join('/home/bellevtx01/vtx/tj-monopix2-daq/tjmonopix2/scans', "hist_tot_map.png"))]
print(attachments)
# Should guarantee fixed order of attachments in eLog entry
#attachments = sorted(attachments)

# Upload reports to the elog
year = date.today().year
month=date.today().month
day=date.today().day
if done==True :
    success_elog = report_to_elog.elog(
        year,
        month,
        day,
        'digital',
        postMessageOfReport=False,
        attachments=attachments,
        credFileElog='cred.txt',
        credFileb2rc='cred.txt'
    ).uploadToElog()
    if success_elog:
        logging.info("Uploaded reports: \n" + ", ".join(attachments))
        logging.info("Link to eLog: {}".format("https://elog.belle2.org/elog/VTX+Upgrade/"))
    else:
        logging.info('No upload to eLog')
        logging.info("Created reports: \n" + ", ".join(attachments))
else:
    logging.info("Created reports: \n" + ", ".join(attachments))








