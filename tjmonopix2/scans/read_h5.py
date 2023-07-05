import tables as tb
import numpy as np
import logging
from argparse import ArgumentParser
import os


def parse_args():
    """Parse command line arguments."""
    parser = ArgumentParser(
             description='Create reports of background analysis')
    add_arg = parser.add_argument
    add_arg('-f', '--file', type=str, default="", help='Path to h5 file')
    add_arg('-o', '--object', type=str, default="", help='Object name from h5 file like Dut, HistOcc, configuration_in/chip/registers')

    return parser.parse_args()


class readh5():
    '''
    Read h5 files and convert them to accessible data types.

    Usage:
    dut, registers = h5toDat.readh5(<h5 file>,['Dut','registers']).run()

    Parameters
    ----------
    filePath : str
        Path to h5 file.
    objectName : list of str, default []
        List of objects in h5 file.

    Returns
    -------
    list of str or np.array
        Returns objects in order of ObjectName. Type given in readh5.dataType.
    '''
    dataType = {'Dut': 'Table -> np.array',
                'HistOcc': 'carray -> np.array',
                'HistTot': 'carray -> np.array',
                'TDC': 'Table -> dict',
                'TLU': 'Table -> dict',
                'analysis': 'Table -> dict',
                'general': 'Table -> dict',
                'module': 'Table -> dict',
                'registers': 'Table -> dict',
                'settings': 'Table -> dict',
                'use_pixel': 'carray -> np.array',
                'run_config': 'Table -> dict',
                'scan_config': 'Table -> dict',
                'scan_params': 'Table -> np.array',
                'enable': 'carray -> np.array',
                'injection': 'carray -> np.array',
                'tdac': 'carray -> np.array'
                }

    def __init__(self, filePath, objectName=[]) -> None:

        self.filePath = None
        self.objectName = []
        self.objectBaseName = []
        self.h5file = None
        self.configuration = None

        if filePath:
            self.filePath = filePath
        else:
            logging.error('No filepath given')
            return

        if objectName:
            for name in objectName:
                self.objectName.append(name.replace("/", "."))

        for name in self.objectName:
            self.objectBaseName.append(name.split(".")[0])

        try:
            self.h5file = tb.open_file(self.filePath, mode="r", title='DUT')
            self.configuration = self.h5file.root.configuration_out
        except Exception:
            logging.error('Cannot open h5')
            return

    def run(self):

        self.readObject = []
        self.out = []

        for name in self.objectBaseName:
            self.readObject.append(getattr(self, "read%s" % name.replace(" ", "")))

        for read in self.readObject:
            out = read()
            self.out.append(out)

        return self.out

    def readDut(self):
        arr = None
        try:
            arr = np.asarray(self.h5file.root.Dut[:])
        except Exception:
            logging.warning("no dut")
            return
        return arr

    def readHistTot(self):
        arr = None
        try:
            arr = np.asarray(self.h5file.root.HistTot[:])
        except Exception:
            logging.warning("no dut")
            return
        return arr

    def readHistOcc(self):
        arr = None
        try:
            arr = np.asarray(self.h5file.root.HistOcc[:])
        except Exception:
            logging.warning("no dut")
            return
        return arr

    def readmodule(self):

        dictionary = {}
        try:
            registers = self.configuration.chip.module
        except Exception:
            logging.warning('no registers')
        for x in registers.iterrows():
            dictionary[x['attribute']] = x['value']
        return dictionary

    def readregisters(self):
        dictionary = {}
        try:
            registers = self.configuration.chip.registers
        except Exception:
            logging.warning('no registers')
        for x in registers.iterrows():
            dictionary[x['register'].decode("utf-8") ] = x['value'].decode("utf-8") 
        return dictionary

    def readuse_pixel(self):
        arr = None
        try:
            arr = np.asarray(self.configuration.chip.use_pixel[:])
        except Exception:
            logging.warning("no dut")
            return
        return arr

    def readsettings(self):
        dictionary = {}
        try:
            registers = self.configuration.chip.settings
        except Exception:
            logging.warning('no registers')
        for x in registers.iterrows():
            dictionary[x['attribute'].decode("utf-8") ] = x['value'].decode("utf-8") 
        return dictionary

    def readinjection(self):
        arr = None
        try:
            arr = np.asarray(self.configuration.chip.masks.injection[:])
        except Exception:
            logging.warning("no dut")
            return
        return arr

    def readenable(self):
        arr = None
        try:
            arr = np.asarray(self.configuration.chip.masks.enable[:])
        except Exception:
            logging.warning("no dut")
            return
        return arr

    def readtdac(self):
        arr = None
        try:
            arr = np.asarray(self.configuration.chip.masks.tdac[:])
        except Exception:
            logging.warning("no dut")
            return
        return arr

    def readscan_params(self):
        arr = None
        try:
            arr = np.asarray(self.configuration.scan.scan_params[:])
        except Exception:
            logging.warning("no scan_params")
            return
        return arr

    def readscan_config(self):

        dictionary = {}
        try:
            registers = self.configuration.scan.scan_config
        except Exception:
            logging.warning('no scan_config')
        for x in registers.iterrows():
            dictionary[x['attribute'].decode("utf-8")] = x['value'].decode("utf-8")
        return dictionary

    def readrun_config(self):
        dictionary = {}
        try:
            registers = self.configuration.scan.run_config
        except Exception:
            logging.warning('no run_config')
        for x in registers.iterrows():
            dictionary[x['attribute'].decode("utf-8")] = x['value'].decode("utf-8")
        return dictionary

    def readanalysis(self):
        dictionary = {}
        try:
            registers = self.configuration.bench.analysis
        except Exception:
            logging.warning('no analysis')
        for x in registers.iterrows():
            dictionary[x['attribute']] = x['value']
        return dictionary

    def readTDC(self):
        dictionary = {}
        try:
            registers = self.configuration.bench.TDC
        except Exception:
            logging.warning('no TDC')
        for x in registers.iterrows():
            dictionary[x['attribute']] = x['value']
        return dictionary

    def readTLU(self):
        dictionary = {}
        try:
            registers = self.configuration.bench.TLU
        except Exception:
            logging.warning('no TLU')
        for x in registers.iterrows():
            dictionary[x['attribute']] = x['value']
        return dictionary

    def readgeneral(self):
        dictionary = {}
        try:
            registers = self.configuration.bench.general
        except Exception:
            logging.warning('no general')
        for x in registers.iterrows():
            dictionary[x['attribute']] = x['value']
        return dictionary


if __name__ == '__main__':

    args = parse_args()
    readh5(args.file, args.object).readFile()
