#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import logging

from basil.HL.HardwareLayer import HardwareLayer
from basil.RL.StdRegister import StdRegister

logger = logging.getLogger(__name__)


class adg728(HardwareLayer):
    def __init__(self, intf, conf):
        adg728_reg = {
            "name": "ADG728",
            "type": "StdRegister",
            "driver": "none",
            "size": 48,
            "fields": [
            ],
        }
        super(adg728, self).__init__(intf, conf)
        self._base_addr = conf["base_addr"]
        self._reg = StdRegister(driver=None, conf=adg728_reg)

    def init(self):
        super(adg728, self).init()

    def reset(self):
        self._intf.write(0x4C, [0])
        RECALL = self._intf.read(0x4C, 1)
        self._intf.write(0x4CA, [135] + [RECALL[0] | 0b1])

    def _read(self):
        self._intf.write(0x4C, [1])

class tca9555(HardwareLayer):
    def __init__(self, intf, conf):
        tca9555_reg = {
            "name": "TCA9555",
            "type": "StdRegister",
            "driver": "none",
            "size": 48,
            "fields": [
            ],
        }
        super(tca9555, self).__init__(intf, conf)
        self._base_addr = conf["base_addr"]
        self._reg = StdRegister(driver=None, conf=tca9555_reg)

    def init(self):
        super(tca9555, self).init()

    def enable_pins(self, pins: list):
        self._write_register(0x06, 0x00)
        res = 0
        for pin in pins:
            if pin > 7:
                raise ValueError("pins has to be smaller than 7")
            res = res + (1 << pin)
        self._write_register(0x02, res)

    def disable_all_pins(self):
        self._write_register(0x06, 0x00)
        self._write_register(0x02, 0)

    def _read_register(self, reg: int) -> int:
        self._intf.write(self._base_addr, [reg])
        return self._intf.read(self._base_addr, 3)

    def _write_register(self, reg: int, val: int) -> None:
        self._intf.write(self._base_addr, [reg, val])
