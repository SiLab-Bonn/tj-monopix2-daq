#! /usr/bin/env python
# load binary lib/pyeudaq.so
import ctypes
import time
from ctypes import c_bool

import pyeudaq


class Monopix2Producer(pyeudaq.Producer):
    def __init__(self, name, runctrl):
        # pyeudaq.Producer.__init__(self, 'PyProducer', name, runctrl)
        pyeudaq.Producer.__init__(self, name, runctrl)
        self.is_running = 0
        print('New instance of Monopix2Producer')

    def DoInitialise(self):
        print('DoInitialise')
        # print 'key_a(init) = ', self.GetInitItem("key_a")

    def DoConfigure(self):
        print('DoConfigure')
        # print 'key_b(conf) = ', self.GetConfigItem("key_b")
        conf = self.GetConfiguration

        print("conf = " + str(conf))

        # print(conf.Get("DUMMY1"))

        isConnected = ctypes.c_bool(self.IsConnected)
        print("connected? " + str(isConnected))

    def DoStartRun(self):
        print('DoStartRun')
        self.is_running = 1

    def DoStopRun(self):
        print('DoStopRun')
        self.is_running = 0

    def DoReset(self):
        print('DoReset')
        self.is_running = 0

    def RunLoop(self):
        print("Start of RunLoop in Monopix2Producer")
        trigger_n = 0
        while (self.is_running):
            ev = pyeudaq.Event("RawEvent", "sub_name")
            ev.SetTriggerN(trigger_n)
            # block = bytes(r'raw_data_string')
            # ev.AddBlock(0, block)
            # print ev
            # Mengqing:
            datastr = 'raw_data_string'
            block = bytes(datastr, 'utf-8')
            ev.AddBlock(0, block)
            print(ev)

            self.SendEvent(ev)
            trigger_n += 1
            time.sleep(1)
        print("End of RunLoop in Monopix2Producer")


if __name__ == "__main__":
    myproducer = Monopix2Producer("monopix2", "tcp://localhost:44000")
    print("connecting to runcontrol in localhost:44000", )
    myproducer.Connect()
    time.sleep(2)
    while myproducer.IsConnected():
        time.sleep(1)
