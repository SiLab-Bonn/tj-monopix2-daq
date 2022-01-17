#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#


from tjmonopix2.tests.test_hardware import utils


def test_register_rw(device) -> None:
    device.registers["VL"].write(38)
    reg = device.registers["VL"].read()
    device.write_command(device.write_sync(write=False), repetitions=8)
    assert reg == 38


def test_rx(device) -> None:
    device.registers["SEL_PULSE_EXT_CONF"].write(0)  # Use internal injection

    # Activate pixel (1, 128)
    device.masks['enable'][1, 128] = True
    device.masks['tdac'][1, 128] = 0b100
    device.masks['injection'][1, 128] = True
    device.masks.update()

    device.daq.reset_fifo()
    device.inject(PulseStartCnfg=0, PulseStopCnfg=8, repetitions=5)
    utils.wait_for_sim(device, repetitions=16)
    data = device.daq["FIFO"].get_data()
    hit, _ = device.interpret_data(data)
    tot = (hit['te'] - hit['le']) & 0x7F
    assert hit['col'].tolist() ==  [1] * 5
    assert hit['row'].tolist() == [128] * 5
    assert tot.tolist() == [1] * 5
