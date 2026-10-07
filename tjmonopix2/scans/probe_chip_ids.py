#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

'''
    Find out which hardware chip ID each connected chip answers to.

    For every chip ID a register read command is sent on the shared command line and the
    FIFO is checked for register replies on every receiver defined in the testbench.
    The reply shows up on the receiver of the chip that has this hardware ID.
    Read-only apart from the standard chip init/configure steps of ScanBase.
'''

import time

import numpy as np

from tjmonopix2.system.scan_base import ScanBase

scan_configuration = {
    'address': 0,  # Register address to read (0 = IBIAS/ITHR)
    'chip_ids': list(range(32)),  # IDs >= 16 have the broadcast bit set
    'wait': 0.2,  # Seconds to collect replies per ID
}


class ProbeChipIds(ScanBase):
    scan_id = 'probe_chip_ids'
    is_parallel_scan = True  # Enables all receivers during _scan

    def _configure(self, **_):
        pass

    def _scan(self, address=0, chip_ids=list(range(32)), wait=0.2, **_):
        chips = [c.chip for c in self.chips.values()]
        sender = chips[0]
        original_id = sender.chip_id

        results = {}
        try:
            for chip_id in chip_ids:
                self.daq['FIFO'].get_data()  # Drain FIFO
                sender.chip_id = chip_id
                sender._read_register(address)
                sender.write_command(sender.write_sync(write=False) * 10)

                data = []
                start = time.time()
                while time.time() - start < wait:
                    if self.daq['FIFO'].get_FIFO_SIZE() > 0:
                        data.append(self.daq['FIFO'].get_data())
                    else:
                        sender.write_command(sender.write_sync(write=False) * 10)
                data = np.concatenate(data) if data else np.array([], dtype=np.uint32)

                results[chip_id] = {}
                for chip in chips:
                    _, reg = chip.interpret_data(data)
                    results[chip_id][chip.chip_sn] = [hex(v) for v in reg['value']]
        finally:
            sender.chip_id = original_id

        header = 'ID  ' + ''.join('{0:>24}'.format('{0} ({1})'.format(c.chip_sn, c.receiver)) for c in chips)
        self.log.success(header)
        for chip_id, replies in results.items():
            line = '{0:<4}'.format(chip_id) + ''.join('{0:>24}'.format(','.join(replies[c.chip_sn]) or '-') for c in chips)
            if any(replies.values()):
                self.log.success(line)
            else:
                self.log.info(line)


if __name__ == '__main__':
    with ProbeChipIds(scan_config=scan_configuration) as scan:
        scan.configure()
        scan.scan()
