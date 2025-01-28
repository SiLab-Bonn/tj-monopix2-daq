import argparse
import socket
import threading
import time
import pyeudaq
import os
import yaml
from tjmonopix2.scans.scan_ext_trigger import ExtTriggerScan
from tjmonopix2.system import logger


def host_reachable(host, port=24, timeout=20):
    try:
        socket.setdefaulttimeout(timeout)
        with socket.create_connection((host, port)):
            return True
    except (socket.timeout, socket.error):
        return False


class EudaqProducerAida(pyeudaq.Producer):
    scan_id = 'eudaq_scan' 

    def __init__(self, name, runctrl):
        pyeudaq.Producer.__init__(self, name, runctrl)
        self.log = logger.setup_derived_logger(self.__class__.__name__)
        self.is_running = 0
        self.scan = None
        self.conf = {}
        self.thread_scan = None
        self.reg_config = {}
        self.init_register_vals = {}
        self.BDAQBoardTimeout = 10

    def __del__(self):
         if self.is_running:
             self.scan.close()

    def DoInitialise(self):
        self.log.info("Initialization completed")

    def DoConfigure(self):
        eudaqConfig = self.GetConfiguration() 
        proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Overwrite DAQ board ip and chip_config_file from eudaq configuration file
        with open(os.path.join(proj_dir, os.path.join("system", "bdaq53.yaml")), "r") as daq_conf_file:
            daq_conf = yaml.safe_load(daq_conf_file)
        daq_conf["transfer_layer"][0]["init"]["ip"] = eudaqConfig.Get("daqboard_ip", "192.168.10.23")
        with open(os.path.join(proj_dir, "testbench.yaml"), "r") as bench_conf_file:
            bench_conf = yaml.safe_load(bench_conf_file)
        bench_conf['modules']['module_0']['chip_0']['chip_config_file'] = eudaqConfig.Get("chip_configfile", None)

        self.log.debug("Probing if DAQ board is up")
        if host_reachable(eudaqConfig.Get("daqboard_ip", "192.168.10.23"), 24, self.BDAQBoardTimeout):
            try:
                self.log.debug("DAQ board is powered up")
                self.scan = ExtTriggerScan(daq_conf=daq_conf, bench_config=bench_conf)
                self.scan.init()
            except Exception as e:
                raise e
            self.SetStatusTag("TriggerN", "0")
            self.log.info("Initialization completed")
        else:
            self.log.error("Initialization failed")
            raise RuntimeError("BDAQ board unreachable")

        eudaqConfig = self.GetConfiguration() 

        self.conf["start_column"] = int(eudaqConfig.Get("START_COLUMN", "0"))
        self.conf["stop_column"] = int(eudaqConfig.Get("STOP_COLUMN", "512"))
        self.conf["start_row"] = int(eudaqConfig.Get("START_ROW", "0")) 
        self.conf["stop_row"] = int(eudaqConfig.Get("STOP_ROW", "512"))
        self.conf["max_triggers"] = int(eudaqConfig.Get("max_triggers", "1000"))
        self.conf["run_nmb_zfill"] = int(eudaqConfig.Get("run_nmb_zfill", "6"))

        # Scan stop conditions, only use one or another
        scan_timeout = eudaqConfig.Get("scan_timeout", None)
        self.scan.scan_config["scan_timeout"] = True if scan_timeout == "true" else False
        self.scan.scan_config["max_triggers"] = int(eudaqConfig.Get("max_triggers", "1000"))

        # Matrix configuration
        self.scan.scan_config["start_column"] = int(eudaqConfig.Get("start_column", "0"))
        self.scan.scan_config["stop_column"] = int(eudaqConfig.Get("stop_column", "512"))
        self.scan.scan_config["start_row"] = int(eudaqConfig.Get("start_row", "0"))
        self.scan.scan_config["stop_row"] = int(eudaqConfig.Get("stop_row", "512"))

        for reg in configurable_regs:
            try:
                self.reg_config[reg] = eudaqConfig.Get(reg, None)
            except:
                pass

        self.scan.scan_config = self.conf
        print(self.reg_config)
        try:
            self.scan.configure()
            self.log.info("Configuration completed")
        except Exception as e:
            raise e

        for reg in self.reg_config.keys():            
            reg_val = self.reg_config[reg]
            reg_val = reg_val.replace(',', '.')
            if reg_val:
                reg_val_int = int(float(reg_val))
                reg_val_float = float(reg_val)

                if (reg_val_float - reg_val_int) > 0.001:
                    print('Contains, ', reg_val, ' in ', reg)
                    self.current_scan_register = reg

                print('After, repl ', reg_val, ' in ', reg)
                self.init_register_vals[reg] = self.scan.chip.registers[reg].read()

                if reg_val:
                    self.scan.chip.registers[reg].write(int(float(reg_val)))

        self.scan.chip.registers['SEL_PULSE_EXT_CONF'].write(0)

    def DoStatus(self):
        if self.scan is not None and self.scan.last_exception is not None:
            exception = self.scan.last_exception[1]
            self.scan.last_exception = None  # Clear exception
            raise exception
        #self.SetStatusTag('DataEventN'  ,'%d'%self.idev)


    def DoStartRun(self):
        try:
            self.scan.fifo_readout   # check if already configured
        except AttributeError:
            self.DoInitialise()
            self.DoConfigure()
        if not self.scan.scan_config["max_triggers"]:
            self.scan.daq.configure_tlu_module(max_triggers=False, aidamode=True)

        self.is_running = True
        self.thread_scan = threading.Thread(target=self.scan.scan)
        self.thread_trigger = threading.Thread(target=self.send_trigger_number)
        self.thread_scan.start()
        self.thread_trigger.start()

    def DoStopRun(self):
        if self.is_running: 
            self.is_running = False
            self.scan.stop_scan.set()
            self.thread_scan.join()
            self.thread_trigger.join()

            # rename output file to include the run number in the file name
            # much more convenient when doing analysis
            origFile = self.scan.output_filename + '.h5'

            self.scan.close()

            run_number = self.GetRunNumber()
            orig_base = os.path.basename(origFile)
            orig_dir = os.path.dirname(origFile)
            newFile = f'{orig_dir}/run{str(run_number).zfill(self.conf["run_nmb_zfill"])}_{orig_base}'
            os.rename(origFile, newFile)
            
            self.scan = None
            self.SetStatusTag("TriggerN", "0")
            self.log.info("Scan was stopped")

    def DoReset(self):
        if self.is_running:
            self.is_running = False
            self.scan.stop_scan.set()
            self.thread_scan.join()
            self.thread_trigger.join()
            self.SetStatusTag("TriggerN", "0")
        if self.scan is not None:
            self.scan.close()
        self.scan = None
        self.log.info("Reset completed")

    def DoTerminate(self):
        if self.is_running:
            self.is_running = False
            self.scan.stop_scan.set()
            self.thread_scan.join()
            self.thread_trigger.join()
            self.scan.close()
        self.scan = None
        self.log.info("Terminated")

    def send_trigger_number(self):
        while self.is_running:
            self.SetStatusTag("TriggerN", str(self.scan.daq.get_trigger_counter()))
            time.sleep(1)


if __name__ == '__main__':
    # Parse program arguments
    parser = argparse.ArgumentParser(prog='EudaqProducerAida',
                                     description='Eudaq Producer Aida',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-r', metavar='address',
                        help='Destination address',
                        default='tcp://localhost:44000')
    parser.add_argument('-n', metavar='name',
                        help='Producer name',
                        default='EudaqProducerAida')

    args = parser.parse_args()

    producer = EudaqProducerAida(args.n, args.r)
    print(f'producer {args.n} connecting to runcontrol in {args.r}')
    producer.Connect()
    time.sleep(2)
    while producer.IsConnected():
        time.sleep(1)
