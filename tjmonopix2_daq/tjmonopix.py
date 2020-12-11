#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import yaml
import logging
import os
import time
import numpy as np
import pkg_resources
from bitarray import bitarray

from basil.dut import Dut
from basil.utils.BitLogic import BitLogic

# Directory for log file. Create if it does not exist
DATDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output_data")
if not os.path.exists(DATDIR):
    os.makedirs(DATDIR)

VERSION = pkg_resources.get_distribution("tjmonopix2_daq").version

''' Set up main logger '''
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.getLogger('basil.HL.RegisterHardwareLayer').setLevel(logging.WARNING)

logging.basicConfig(
    format="%(asctime)s [%(levelname)-5.5s] (%(threadName)-10s) %(message)s")
logger = logging.getLogger('TJMONOPIX')
logger.setLevel(logging.INFO)

fileHandler = logging.FileHandler(os.path.join(DATDIR, time.strftime("%Y%m%d-%H%M%S.log")))
logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s] (%(threadName)-10s) %(message)s")
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)


def gray2bin(gray):
    b6 = gray & 0x40
    b5 = (gray & 0x20) ^ (b6 >> 1)
    b4 = (gray & 0x10) ^ (b5 >> 1)
    b3 = (gray & 0x08) ^ (b4 >> 1)
    b2 = (gray & 0x04) ^ (b3 >> 1)
    b1 = (gray & 0x02) ^ (b2 >> 1)
    b0 = (gray & 0x01) ^ (b1 >> 1)
    return b6 + b5 + b4 + b3 + b2 + b1 + b0


class TJMonoPix(Dut):

    """ Map hardware IDs for board identification """
    hw_map = {
        0: 'SIMULATION',
        1: 'MIO2',
    }

    cmd_data_map = {
        0: 0b01101010,
        1: 0b01101100,
        2: 0b01110001,
        3: 0b01110010,
        4: 0b01110100,
        5: 0b10001011,
        6: 0b10001101,
        7: 0b10001110,
        8: 0b10010011,
        9: 0b10010101,
        10: 0b10010110,
        11: 0b10011001,
        12: 0b10011010,
        13: 0b10011100,
        14: 0b10100011,
        15: 0b10100101,
        16: 0b10100110,
        17: 0b10101001,
        18: 0b01011001,
        19: 0b10101100,
        20: 0b10110001,
        21: 0b10110010,
        22: 0b10110100,
        23: 0b11000011,
        24: 0b11000101,
        25: 0b11000110,
        26: 0b11001001,
        27: 0b11001010,
        28: 0b11001100,
        29: 0b11010001,
        30: 0b11010010,
        31: 0b11010100
    }

    CMD_SYNC = [0b10000001, 0b01111110]  # 0x(817E)
    # CMD_PLL_LOCK = [0b01010101, 0b01010101]
    # CMD_READ_TRIGGER = 0b01101001
    CMD_CLEAR = 0b01011010
    CMD_GLOBAL_PULSE = 0b01011100
    CMD_CAL = 0b0110_0011 # 0x63
    CMD_REGISTER = 0b01100110
    CMD_RDREG = 0b01100101

    register_name_map = {
        'ibias': 0,
        'ithr': 1,
        'icasn': 2,
        'idb': 3,
        'itune': 4,
        'icomp': 5,
        'idel': 6,
        'iram': 7,
        'imonitors': 8,
        'ioverrides': 9,
        'vmonitors': 10,
        'voverrides': 11,
        'vreset': 6,
        'vcasp': 6,
        'vcasg': 7,
        'vclip': 7,
        'vl': 8,
        'vh': 8,
        #'swcntl': 18,
        'rst': 19,
        'pix_portal': 16,
        'row_sel': 17,
        'colgroup_sel': 17,
        'ro_portal': 23,
        'dcolgroup_sel': 24,
        'hor_row_sel': 25,
        'anamon_sfp': 26,
        'anamon_sfn': 27,
        'anamonin_sfn1': 28,
        'anamonin_sfp': 29,
        'anamonin_sfn2': 30,   
        'pulse_anamon': 31,
        'lvds0': 12,
        'lvds1': 13,
        'lvds2': 14,
        'gpio': 15,
        'ch_sync': 16,
        'internalRO_stop': 148,
        'internalRO_readstart': 149,
        'internalRO_readstop': 150,
        'internalRO_freezestart': 151,
        'internalRO_freezestop': 152,
        'internalRO_load': 153,
        'readout': 154,
        'directRO_delay': 146,
        'status': 220,
        'lock_loss_cnt': 221, 
        'trigger_cnt': 222,
        'err_cnt': 223, 
        'bit_flip_wng_cnt': 224, 
        'bit_flip_err_cnt': 225
    }

    def __init__(self, conf=None):
        if not conf:
            proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            conf = os.path.join(proj_dir, 'tjmonopix2_daq' + os.sep + 'tjmonopix.yaml')

        self.ROW = 512
        self.COL = 512

        logger.debug("Loading configuration file from {}".format(conf))

        super(TJMonoPix, self).__init__(conf)
        self.chip_id = 0
        self.SET = {'VDDA': None, 'VDDP': None, 'VDDA_DAC': None, 'VDDD': None,
                    'VPC': None}
        self.pixel_conf = 7 * np.ones((512, 512), dtype=np.uint8)
        self.injection_conf = np.zeros((512, 512), dtype=np.bool)
        self.debug = 0

    def get_daq_version(self):
        ret = self['intf'].read(0x0000, 2)
        fw_version = str('%s.%s' % (ret[1], ret[0]))

        ret = self['intf'].read(0x0002, 2)
        board_version = ret[0] + (ret[1] << 8)

        return fw_version, board_version

    def init(self):
        super(TJMonoPix, self).init()
        self['CONF']['RESET_EXT'] = 1
        self['CONF']['GPIO_MODE'] = 0x0
        self['CONF']['CHIP_ID'] = self.chip_id
        self['CONF']['SEL_DIRECT'] = 1
        self['CONF'].write()
        self['cmd'].set_chip_type(1)  # ITkpixV1-like
        self.fw_version, self.board_version = self.get_daq_version()
        logger.info('Found board %s running firmware version %s' % (self.board_version, self.fw_version))

        #power on
        self.power_on()
        # start clk before release reset
        self['CONF']['EN_LVDS_IN'] = 1
        self['CONF'].write()
        #reset OFF and send sync 32 times
        self['CONF']['RESET_EXT'] = 0
        self['CONF'].write()

        #### sync 4(defalt value) times
        self.write_command(self.write_sync(write=False) * 4)

        logging.info(str(self.get_power_status()))

    def load_config(self, filename):
        with open(filename) as f:
            conf = yaml.load(f)
        # self.default_conf()
        self.write_conf()
        time.sleep(0.1)  # mabe not needed?

        # maybe update power here also?

        self.set_all_mask(mask=conf['CONF_SR'])
        self.write_conf()
        time.sleep(0.1)  # mabe not needed?

        # update gloable setting
        # TODO !!
        self.write_conf()

    def power_on(self, VDDA=1.8, VDDP=1.8, VDDA_DAC=1.8, VDDD=1.8, VPCSWSF=0.5, VPC=1.3, BiasSF=100, INJ_LO=0.2, INJ_HI=3.6):
        # Set power
        # Sense resistor is 0.1Ohm, so 300mA=60mA*5
        self['VDDD'].set_current_limit(60, unit='mA')

        self['VPC'].set_voltage(VPC, unit='V')
        self.SET["VPC"] = VPC

        self['VDDA_DAC'].set_voltage(VDDA_DAC, unit='V')
        self['VDDA_DAC'].set_enable(True)
        self.SET["VDDA_DAC"] = VDDA_DAC

        self['VDDA'].set_voltage(VDDA, unit='V')
        self['VDDA'].set_enable(True)
        self.SET["VDDA"] = VDDA

        self['VDDD'].set_voltage(VDDD, unit='V')
        self['VDDD'].set_enable(True)
        self.SET["VDDD"] = VDDD

    def power_off(self):
        self['VPC'].set_voltage(0, unit='V')
        self.SET["VPC"] = 0
        # Deactivate all
        for pwr in ['VDDD', 'VDDA', 'VDDA_DAC']:
            self[pwr].set_enable(False)

    def get_power_status(self):
        status = {}

        for pwr in ['VDDD', 'VDDA', 'VDDA_DAC', 'VPC']:
            status[pwr + ' [V]'] = self[pwr].get_voltage(unit='V')
            status[pwr + ' [mA]'] = 5 * self[pwr].get_current(unit='mA') if pwr in [
                "VDDD", "VDDA", "VDDA_DAC"] else self[pwr].get_current(unit='mA')

        return status

    def interpret_direct_hit(self, raw_data):
        hit_dtype = np.dtype(
            [("col", "<u2"), ("row", "<u2"), ("le", "<u1"), ("te", "<u1"), ("noise", "<u1")])
        hit_data_leterow = raw_data[(raw_data & 0xF0000000) == 0]
        hit_data_col = raw_data[(raw_data & 0xF0000000) == 0x10000000]
        if len(hit_data_leterow) == len(hit_data_col):
            pass
        elif len(hit_data_leterow) == len(hit_data_col)+1:
            hit_data_leterow = hit_data_leterow[:-1]
        elif len(hit_data_leterow)+1 == len(hit_data_col):
            hit_data_col = hit_data_col[1:]
        else:
            print("ERROR:interpret_direct_hit:brokendata",len(hit_data_leterow),len(hit_data_col))
            return 
        hit = np.empty(hit_data_leterow.shape[0], dtype=hit_dtype)
        print("=====sim=====direct_hit raw", end=" ")
        for r in raw_data:
            print(hex(r), end=" ")
        print()
        hit['row'] = (hit_data_leterow & 0x1FF)
        hit['col'] = (hit_data_col & 0x1FF)

        hit['te'] = (hit_data_leterow & 0x00FE00) >> 9
        hit['le'] = (hit_data_leterow & 0x7F0000) >> 16
        hit['noise'] = (hit_data_leterow & 0x800000) >> 23
        print("=====sim=====direct_hit", hit)
        return hit

    def interpret_ts(self, raw_data):
        print("=====sim=====ts", end=" ")
        for r in raw_data:
            print(hex(r), end=" ")
        hit_dtype = np.dtype([("le", "<u8"), ("te", "<u8")])
        hit_le0 = raw_data[(raw_data & 0xFF000000) == 0x61000000] & 0xFFFFFF
        hit_le1 = raw_data[(raw_data & 0xFF000000) == 0x62000000] & 0xFFFFFF
        hit_le2 = raw_data[(raw_data & 0xFF000000) == 0x63000000] & 0xFFFFFF
        hit_te0 = raw_data[(raw_data & 0xFF000000) == 0x65000000] & 0xFFFFFF
        hit_te1 = raw_data[(raw_data & 0xFF000000) == 0x66000000] & 0xFFFFFF
        hit_te2 = raw_data[(raw_data & 0xFF000000) == 0x67000000] & 0xFFFFFF
        hit = np.empty(len(hit_le0), dtype=hit_dtype)
        hit['le'] = hit_le0 | (hit_le1 << 24) | (hit_le2 << 48) 
        #print(len(hit_le0),hit_le0, hit_le0 | (hit_le1 << 24) | (hit_le2 << 48), hit['le'])
        hit['te'] = hit_te0 | (hit_te1 << 24) | (hit_te2 << 48) 
        return hit

    def interpret_no8b10b(self, raw_data):
        hit_dtype = np.dtype(
            [("col", "<u2"), ("row", "<u2"), ("le", "<u1"), ("te", "<u1"), ("token_id", "<i8")])
        r = raw_data[(raw_data & 0xF8000000) == 0x40000000]
        r0 = (r & 0x7FC0000) >> 18
        r1 = (r & 0x003FE00) >> 9
        r2 = (r & 0x00001FF)
        for i in range(len(r)):
            print("=====sim=====", i, hex(r0[i]), hex(r1[i]), hex(r2[i]))
        rx_data = np.reshape(np.vstack((r0, r1, r2)), -1, order="F")
        hit = np.empty(len(rx_data) // 4 + 10, dtype=hit_dtype)
        i=0
        ii = 0
        while i < len(rx_data):
            if rx_data[i] == 0x13C:
                i = i +1
            elif i+3< len(rx_data):
                #print("=====sim=====",ii, i, hex(rx_data[i]), hex(rx_data[i+1]), hex(rx_data[i+2]), hex(rx_data[i+3]))
                hit[ii]['col'] = (rx_data[i]<<1)+((rx_data[i+2]&0x2)>>1)
                hit[ii]['row'] = ((rx_data[i+2]&0x1)<<9 )+rx_data[i+3]
                hit[ii]['le'] = gray2bin((rx_data[i+1]>>1))
                hit[ii]['te'] = gray2bin(((rx_data[i+1]&0x1)<<6)+((rx_data[i+2]&0xFC)>>2))
                hit[ii]['token_id'] = 0
                ii = ii +1
                i = i +4
            else:
                print(i, hex(rx_data[i]))
                i=i+1
        return hit[:ii]

    def interpret_data(self, raw_data):
        hit_dtype = np.dtype(
            [("col", "<u2"), ("row", "<u2"), ("le", "<u1"), ("te", "<u1"), ("token_id", "<i8")])
        reg_dtype = np.dtype([("addr", "<u1"), ("val", "<u2")])
        r = raw_data[(raw_data & 0xF8000000) == 0x40000000]
        r0 = (r & 0x7FC0000) >> 18
        r1 = (r & 0x003FE00) >> 9
        r2 = (r & 0x00001FF)
        for i in range(len(r)):
            print("=====sim=====", i, hex(r0[i]), hex(r1[i]), hex(r2[i]))
        rx_data = np.reshape(np.vstack((r0, r1, r2)), -1, order="F")
        hit = np.empty(len(rx_data) // 4 + 10, dtype=hit_dtype)
        reg = np.empty(len(rx_data) // 5 + 10, dtype=reg_dtype)
        h_i = 0
        r_i = 0
        idx = 0
        token_id = 0
        flg = 0
        while idx < len(rx_data):
            if rx_data[idx] == 0x1fc:
                if len(rx_data) > idx+5 and rx_data[idx+4] == 0x15c: #reg data
                    reg[r_i]['addr'] = (rx_data[idx+1] & 0x0FF)
                    reg[r_i]['val'] = ((rx_data[idx+2] & 0x0FF) << 8) + (rx_data[idx+3] & 0x0FF)
                    # print ("reg",reg[r_i]['addr'],hex(reg[r_i]['val']))
                    r_i = r_i + 1
                    idx = idx + 5
                else:
                   print("interpret_data: broken reg data", idx)
                   idx = idx +1
            elif rx_data[idx] == 0x1bc:  # sof
                idx=idx+1
                if flg!=0:
                    print("interpret_data: eof is missing")
                flg = 1
            elif rx_data[idx] == 0x17c:  # eof
                if flg!=1:
                    print("interpret_data: eof before sof", idx, hex(rx_data[idx]))
                flg = 0
                idx = idx + 1
                token_id = token_id + 1
            elif rx_data[idx] == 0x13c: ## idle (dummy data)
                idx = idx + 1
            else:
                if flg != 1:
                    print("interpret_data: sof is missing", idx, hex(rx_data[idx]))
                if len(rx_data) < idx + 4 :
                    print("interpret_data: incomplete data")
                    break
                hit[h_i]['token_id'] = token_id
                hit[h_i]['le'] = (rx_data[idx+1] & 0xFE) >> 1 
                hit[h_i]['te'] = (rx_data[idx+1] & 0x01) << 6 | ((rx_data[idx+2] & 0xFC) >> 2)
                hit[h_i]['row'] = ((rx_data[idx+2] & 0x1) << 8) | (rx_data[idx+3] & 0xFF)
                hit[h_i]['col'] = ((rx_data[idx] & 0xFF) << 1) + ((rx_data[idx+2] & 0x2) >> 1)
                idx = idx+4
                h_i = h_i+1
        print("=====sim=====reg",r_i)
        hit = hit[:h_i]
        reg = reg[:r_i]
        #print("=====sim=====gray", hit['le'], hit['te'])
        hit['le'] = gray2bin(np.copy(hit['le']))
        hit['te'] = gray2bin(np.copy(hit['te']))
        #print("=====sim=====lete", hit['le'], hit['te'])
        return hit, reg

    def prepare_injection_mask(self, start_col=0, stop_col=112, step_col=56, start_row=0, stop_row=224, step_row=4):
        raise NotImplementedError("Not implemented")

    # SET BIAS CURRENTS AND VOLTAGES
    def set_ibias(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

    def set_ithr(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

    def set_icasn(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

    def set_idb(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

    def set_itune(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

    def set_icomp(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

    def set_idel(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

    def set_iram(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

    def set_vreset(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

    def set_vh(self, dacunits, print_en=False):
        raise NotImplementedError("Not implemented")

    def get_vh(self):
        raise NotImplementedError("Not implemented")

    def set_vl(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

    def get_vl(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

    def set_vcasn_dac(self, dacunits, printen=False):
        raise NotImplementedError("Not implemented")

############################## SET data readout ##############################

    def cleanup_fifo(self, n=5):
        for _ in range(n):
            time.sleep(0.1)
            self['fifo'].reset()

    def set_tlu(self, tlu_delay=8):
        self["tlu"]["RESET"] = 1
        self["tlu"]["TRIGGER_MODE"] = 3
        self["tlu"]["EN_TLU_VETO"] = 0
        self["tlu"]["MAX_TRIGGERS"] = 0
        self["tlu"]["TRIGGER_COUNTER"] = 0
        self["tlu"]["TRIGGER_LOW_TIMEOUT"] = 0
        self["tlu"]["TRIGGER_VETO_SELECT"] = 0
        self["tlu"]["TRIGGER_THRESHOLD"] = 0
        self["tlu"]["DATA_FORMAT"] = 2
        self["tlu"]["TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES"] = 20
        self["tlu"]["TRIGGER_DATA_DELAY"] = tlu_delay
        self["tlu"]["TRIGGER_SELECT"] = 0
        self["timestamp_tlu"]["RESET"] = 1
        self["timestamp_tlu"]["EXT_TIMESTAMP"] = 1
        self["timestamp_tlu"]["ENABLE_TOT"] = 0
        logging.info("set_tlu: tlu_delay=%d" % tlu_delay)

        self["timestamp_tlu"]["ENABLE_EXTERN"] = 1
        self["tlu"]["TRIGGER_ENABLE"] = 1

    def stop_tlu(self):
        self["tlu"]["TRIGGER_ENABLE"] = 0
        self["timestamp_tlu"]["ENABLE_EXTERN"] = 0
        lost_cnt = self["timestamp_tlu"]["LOST_COUNT"]
        if lost_cnt != 0:
            logging.warn("stop_tlu: error cnt=%d" % lost_cnt)

    def set_timestamp(self, src="rx1"):
        self["timestamp_{}".format(src)].reset()
        self["timestamp_{}".format(src)]["EXT_TIMESTAMP"] = True
        if src == "rx1":
            self["timestamp_rx1"]["ENABLE_TRAILING"] = 0
            self["timestamp_rx1"]["ENABLE"] = 1
        elif src == "hitor":
            self["timestamp_hitor"]["ENABLE_TRAILING"] = 1
            self["timestamp_hitor"]["ENABLE"] = 1
        elif src == "inj":
            self["timestamp_inj"]["ENABLE"] = 1
        elif src == "tlu":
            self["timestamp_tlu"]["ENABLE_TRAILING"] = 0
            self["timestamp_tlu"]["ENABLE_EXTERN"] = 1

        logging.info("Set timestamp: src={}".format(src))

    def stop_timestamp(self, src="rx1"):
        self["timestamp_{}".format(src)]["ENABLE"] = 0
        lost_cnt = self["timestamp_{}".format(src)]["LOST_COUNT"]
        if lost_cnt != 0:
            logging.warn("Stop timestamp: src={} lost_cnt={:d}".format(src, lost_cnt))
        return lost_cnt

    def set_monoread(self, start_freeze=57, start_read=60, stop_read=62, stop_freeze=95, stop=100, en=True):
        self.cleanup_fifo(2)
        self['rx'].set_en(en)

    def stop_monoread(self):
        self['rx'].set_en(False)
        lost_cnt = self["rx"]["LOST_COUNT"]
        if lost_cnt != 0:
            logging.warn("stop_monoread: error cnt=%d" % lost_cnt)

    def set_direct_read(self, start_freeze=57, start_read=60, stop_read=62, stop_freeze=95, stop=100, en=True):
        #self['direct_rx'].CONF_START_FREEZE = start_freeze  # default 57
        #self['direct_rx'].CONF_STOP_FREEZE = stop_freeze  # default 95
        #self['direct_rx'].CONF_START_READ = start_read  # default 60
        #self['direct_rx'].CONF_STOP_READ = stop_read  # default 62
        #self['direct_rx'].CONF_STOP = stop  # default 100
        self.cleanup_fifo(2)
        self['direct_rx'].set_en(en)

    def stop_direct_read(self):
        self['direct_rx'].set_en(False)
        lost_cnt = self["direct_rx"]["LOST_COUNT"]
        if lost_cnt != 0:
            logging.warn("stop_monoread: error cnt=%d" % lost_cnt)

    def stop_all(self):
        self.stop_tlu()
        self.stop_monoread()
        self.stop_direct_monoread()
        #self.stop_timestamp("rx1")
        #self.stop_timestamp("inj")
        self.stop_timestamp("hit_or")

########################## pcb components #####################################
    def get_temperature(self, n=10):
        # TODO: Why is this needed? Should be handled by basil probably
        vol = self["NTC"].get_voltage()
        if not (vol > 0.5 and vol < 1.5):
            for i in np.arange(2, 200, 2):
                self["NTC"].set_current(i, unit="uA")
                time.sleep(0.1)
                vol = self["NTC"].get_voltage()
                if self.debug != 0:
                    print("temperature() set_curr=", i, "vol=", vol)
                if vol > 0.7 and vol < 1.3:
                    break
            if abs(i) > 190:
                logging.warn("temperature() NTC error")

        temp = np.empty(n)
        for i in range(len(temp)):
            temp[i] = self["NTC"].get_temperature("C")
        return np.average(temp[temp != float("nan")])

    def save_config(self, filename=None):
        if filename is None:
            filename = os.path.join(DATDIR, time.strftime("config_%Y%m%d-%H%M%S.yaml"))
        conf = self.get_configuration()
        conf["SET"] = self.SET
        with open(filename, "w") as f:
            yaml.dump(conf, f)
        logging.info("save_config filename: %s" % filename)
        return filename

    def get_pixel_status(self, maskV=None, maskH=None, maskD=None):
        raise NotImplementedError("Not implemented")     

    # New functions

    def enable_hitor(self, col, row, write=True):
        '''
            Enable HitOr for one column/row

            Parameters:
            ----------
                col : int
                    Between 0 and 511
                row : int
                    Between 0 and 511
        '''
        col_reg_addr = 47 + col // 16  # 47 is start address of HOR_COL_EN register
        col_reg_value = 1 << (col % 16)
        row_reg_addr = 79 + row // 16  # 79 is start address of HOR_ROW_EN register
        row_reg_value =  1 << (row % 16)

        indata = self.write_register(col_reg_addr, col_reg_value, write=False)
        indata += self.write_register(row_reg_addr, row_reg_value, write=False)

        if write:
            self.write_command(indata)
        return indata

    def enable_injection(self, col, row, write=True):
        '''
            Enable injection for one column/row

            Parameters:
            ----------
                col : int
                    Between 0 and 511
                row : int
                    Between 0 and 511
        '''
        col_conf = np.any(self.injection_conf, axis=1)
        row_conf = np.any(self.injection_conf, axis=0)

        col_conf = col_conf[16 * (col // 16): 16 + 16 * (col // 16)]
        col_conf = int("0b" + "".join([hex(i)[2:] for i in col_conf.astype(np.uint8)[::-1]]), 2)
        row_conf = row_conf[16 * (row // 16): 16 + 16 * (row // 16)]
        row_conf = int("0b" + "".join([hex(i)[2:] for i in row_conf.astype(np.uint8)[::-1]]), 2)

        col_reg_addr = 82 + col // 16  # 111 is start address of INJ_COL_EN register
        col_reg_value = col_conf | (1 << (col % 16))
        row_reg_addr = 114 + row // 16  # 143 is start address of INJ_ROW_EN register
        row_reg_value = row_conf | (1 << (row % 16))

        self.injection_conf[col, row] = True

        indata = self.write_register(col_reg_addr, col_reg_value, write=False)
        indata += self.write_register(row_reg_addr, row_reg_value, write=False)

        if write:
            self.write_command(indata)
        return indata

    def write_pixel_conf(self, colgroup, row, conf, write=True):
        '''
            Write pixel configuration for one column group (4 adjacent pixels)

            Parameters:
            ----------
                colgroup : int
                    Between 0 and 127
                row : int
                    Between 0 and 511
                conf : int
                    Configuration (4 * 4 bits)
        '''
        indata = self.write_register('row_sel', row, write=False)
        indata += self.write_register('colgroup_sel', colgroup, write=False)
        indata += self.write_register('pix_portal', conf, write=False)

        if write:
            self.write_command(indata)
        return indata

    # COMMAND DECODER
    def write_command(self, data, repetitions=1, wait_for_done=True, wait_for_ready=False):
        '''
            Write data to the command encoder.

            Parameters:
            ----------
                data : list
                    Up to [get_cmd_size()] bytes
                repetitions : integer
                    Sets repetitions of the current request. 1...2^16-1. Default value = 1.
                wait_for_done : boolean
                    Wait for completion after sending the command. Not advisable in case of repetition mode.
                wait_for_ready : boolean
                    Wait for completion of preceding commands before sending the command.
        '''
        if isinstance(data[0], list):
            for indata in data:
                self.write_command(indata, repetitions, wait_for_done)
            return

        assert (0 < repetitions < 65536), "Repetition value must be 0<n<2^16"

        if wait_for_ready:
            while (not self['cmd'].is_done()):
                pass

        self['cmd'].set_data(data)
        self['cmd'].set_size(len(data))
        if repetitions > 1:
            logging.debug("Repeating command %i times." % (repetitions))
            self['cmd'].set_repetitions(repetitions)
        self['cmd'].start()

        if wait_for_done:
            while (not self['cmd'].is_done()):
                pass

        if repetitions > 1:
            self['cmd'].set_repetitions(1)

    def write_sync(self, write=True):
        indata = self.CMD_SYNC
        if write:
            self.write_command(indata)
        return indata

    def write_ecr(self, write=True):
        indata = [self.CMD_CLEAR]
        indata += [self.cmd_data_map[self.chip_id]]
        #indata += [self.CMD_CLEAR]
        #indata += [self.cmd_data_map[self.chip_id]]
        if write:
            self.write_command(indata)
        return indata

    def write_glr(self, write=True):
        indata = [self.CMD_GLOBAL_PULSE]
        indata += [self.cmd_data_map[self.chip_id]]
        if write:
            self.write_command(indata)
        return indata

    def write_register(self, address, data, write=True):
        '''
            Sends write command to register with data

            Parameters:
            ----------
                address : int or str
                    Address or name of the register to be written to
                data : int
                    Value to write into register

            Returns:
            ----------
                indata : binarray
                    Boolean representation of register write command.
        '''
        if type(address) == str:
            address = self.register_name_map[address]

        indata = [self.CMD_REGISTER]  # Write Command
        indata += [self.cmd_data_map[self.chip_id]]
        indata += [self.cmd_data_map[address >> 5]]  # Write mode + first 4 bits of address
        indata += [self.cmd_data_map[address & 0x1f]]  # Last 5 bits of address
        print("=====sim=====data >> 11",hex(data), hex(data >> 11))
        indata += [self.cmd_data_map[data >> 11]]  # First 5 bits of data
        indata += [self.cmd_data_map[(data >> 6) & 0x1f]]  # Middle 5 bits of data
        indata += [self.cmd_data_map[(data >> 1) & 0x1f]]  # Middle 5 bits of data
        indata += [self.cmd_data_map[(data & 0x1) << 4]]  # Last bit of data
        if write:
            self.write_command(indata)

        return indata

    def read_register(self, address, write=True):
        '''
            Sends read command to register with data

            Parameters:
            ----------
                address : int or str
                    Address or name of the register to be written to

            Returns:
            ----------
                indata : binarray
                    Boolean representation of register write command.
        '''
        if type(address) == str:
            address = self.register_name_map[address]

        indata = [self.CMD_RDREG]
        indata += [self.cmd_data_map[self.chip_id]]
        indata += [self.cmd_data_map[address >> 5]]  # first 4 bits of address
        indata += [self.cmd_data_map[address & 0x1f]]  # last 5 bits of address

        if write:
            self.write_command(indata)
        return indata

    def write_cal(self, PulseStartCnfg=1, PulseStopCnfg=10, write=True):
        '''
            Command to send a digital or analog injection to the chip.
            Digital or analog injection is selected globally via the INJECTION_SELECT register.

            For digital injection, only CAL_edge signal is relevant:
                - CAL_edge_mode switches between step (0) and pulse (1) mode
                - CAL_edge_dly is counted in bunch crossings. It sets the delay before the rising edge of the signal
                - CAL_edge_width is the duration of the pulse (only in pulse mode) and is counted in cycles of the 160MHz clock
            For analog injection, the CAL_aux signal is used as well:
                - CAL_aux_value is the value of the CAL_aux signal
                - CAL_aux_dly is counted in cycles of the 160MHz clock and sets the delay before the edge of the signal
            {Cal,ChipId[4:0]}-{PulseStartCnfg[5:1]},{PulseStartCnfg[0], PulseStopCnfg[13:10]}}-{{PulseStopCnfg[9:0]} [Cal +DD +DD]
        '''
        indata = [self.CMD_CAL]
        indata += [self.cmd_data_map[self.chip_id]]
        indata += [self.cmd_data_map[(PulseStartCnfg & 0b11_1110) >> 1]]
        indata += [self.cmd_data_map[( (PulseStartCnfg << 4) & 0b10000 ) + ( ( PulseStopCnfg >> 10 ) & 0b1111 )]]
        indata += [self.cmd_data_map[( ( PulseStopCnfg >> 5 ) & 0b11111 )]]
        indata += [self.cmd_data_map[ PulseStopCnfg & 0b11111 ]]

        if write:
            self.write_command(indata)

        return indata

    def inject(self, PulseStartCnfg=1, PulseStopCnfg=10, repetitions=1, write=True):
        """TODO repetitions != 1 is not supported
        """ 
        indata = [self.write_sync(write=False) * 32]   ## is this needed?
        indata += [self.write_cal(PulseStartCnfg=1, PulseStopCnfg=10, write=False)]  # Injection
        self.write_command(indata, repetitions=repetitions)

    def get_GCR(self, reg_name):
        for i in range((self['GCR']._fields_conf[reg_name]['size']-1) // 16 + 1):
            a = self['GCR']._fields_conf[reg_name]['address'] + i
            self['GCR']._drv.read_register(a, chip_id=self.chip_id, write=True)
            raw_data = self['fifo'].get_data()
            for _ in range(10):
                if len(raw_data) == 2:
                    break
                raw_data = np.append(raw_data, self['fifo'].get_data())
            print("=====sim=====len", len(raw_data))
            _, reg_data = self.interpret_data(raw_data)
            print("=====sim=====reg", a, reg_data[0]["addr"], hex(reg_data[0]["val"]))
            self["GCR"].update(reg_data[0]["addr"], reg_data[0]["val"])

    def set_RO(self, EnROCnfg="all", EnBcidCnfg="all", EnRORstBCnfg="all"):
        pass


if __name__ == '__main__':
    chip = TJMonoPix()
    chip.init()
