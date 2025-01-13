import time
import argparse
import pyeudaq
import socket
import threading
from tjmonopix2.scans.scan_ext_trigger import ExtTriggerScan
from tjmonopix2.system import logger


def IsHostReachable(host="192.168.10.23",port=24,timeout=20) -> bool:
        try:
            socket.setdefaulttimeout(timeout)
            with socket.create_connection((host, port)):
                return True
        except (socket.timeout, socket.error):
            return False
        


class EudaqProducerAida(pyeudaq.Producer):
    scan_id = 'ext_trigger_scan_producer' 

    def __init__(self, name, runctrl):
        pyeudaq.Producer.__init__(self, name, runctrl)
        self.log = logger.setup_derived_logger(self.__class__.__name__)
        self.is_running = 0
        self.ini = None
        self.scan = None
        self.conf = {}
        self.thread_scan = None


    def __del__(self):
         if self.is_running:
             self.scan.close()

    def DoInitialise(self):
        #self.ini = self.GetInitConfiguration()
        """
            if IsHostReachable("192.168.10.23",24,self.BDAQBoardTimeout):
            try:
                self.scan = ExtTriggerScan() 
                self.scan.init()    
            except Exception as e:
                raise e
            self.SetStatusTag("TriggerN", "0")
            self.log.info("Initialization completed")
        else:
            self.log.error("Initialization failed")
            raise RuntimeError("BDAQ board unreachable")
        """
        self.log.info("Initialization completed")

    def DoConfigure(self):
        self.log.info("Probing if power is up")
        time.sleep(2)
        if IsHostReachable("192.168.10.23",24,self.BDAQBoardTimeout):
            try:
                self.log.info("Power is up")
                self.scan = ExtTriggerScan() 
                self.scan.init()    
            except Exception as e:
                raise e
            self.SetStatusTag("TriggerN", "0")
            self.log.info("Initialization completed")
        else:
            self.log.error("Initialization failed")
            raise RuntimeError("BDAQ board unreachable")
        
        """
        if self.scan==None:  # check if already initialized, if not DoInitialize
            self.DoInitialise()
        """
        eudaqConfig = self.GetConfiguration() 

        self.conf["start_column"]=int(eudaqConfig.Get("start_column","0"))

        self.conf["stop_column"]=int(eudaqConfig.Get("stop_column","512"))

        self.conf["start_row"]=int(eudaqConfig.Get("start_row","0")) 

        self.conf["stop_row"]=int(eudaqConfig.Get("stop_row","512"))

        self.conf["max_triggers"]=int(eudaqConfig.Get("max_triggers","1000")) 

        if eudaqConfig.Get("scan_timeout").lower() == "false":
            self.conf["scan_timeout"]=False
        elif eudaqConfig.Get("scan_timeout").lower() == "true":
            self.conf["scan_timeout"]=True
        
        if eudaqConfig.Get("tot_calib_file").lower()=="none":
            self.conf["tot_calib_file"]=None
        else:
            self.conf["tot_calib_file"]=eudaqConfig.Get("tot_calib_file")

        self.scan.scan_config=self.conf
        #print(self.conf)
        try:
            self.scan.configure()
            self.log.info("Configuration completed")
        except Exception as e:
            raise e


    def DoStartRun(self):
        try:
            self.scan.fifo_readout   # check if already configured
        except AttributeError:
            self.DoInitialise()
            self.DoConfigure()
        if not self.scan.scan_config["max_triggers"]:
            self.scan.daq.configure_tlu_module(max_triggers=False, aidamode=True)
            
        self.is_running = 1
        self.thread_scan = threading.Thread(target=self.scan.scan)
        self.thread_trigger = threading.Thread(target=self.SendTriggerNumber)
        self.thread_scan.start()
        self.thread_trigger.start()
        
       

    def DoStopRun(self):
        if self.is_running: 
            self.is_running = 0                    
            self.scan.stop_scan.set()
            self.thread_scan.join()
            self.thread_trigger.join()
            self.scan.close()
            self.scan = None
            self.SetStatusTag("TriggerN", "0")
            self.log.info("Scan was stopped")


    def DoReset(self):
        if self.is_running:
            self.is_running=0
            self.scan.stop_scan.set()
            self.thread_scan.join()
            self.thread_trigger.join()
            self.SetStatusTag("TriggerN", "0")
        if self.scan is not None:
            self.scan.close()
        self.scan=None
        self.log.info("Reset completed")
        


    def DoTerminate(self):
        if self.is_running:
            self.is_running=0
            self.scan.stop_scan.set()
            self.thread_scan.join()
            self.thread_trigger.join()
            self.scan.close()
        self.scan=None
        self.log.info("Terminated")
        
    def SendTriggerNumber(self):
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
        
        