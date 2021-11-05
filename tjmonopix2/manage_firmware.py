#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

''' Module to manage firmware download, compilation and flashing using vivado.
    Mainly for CI runner but also useful during headless session (e.g. test beams)
'''

import os
import argparse
import pexpect
from sys import platform

import tjmonopix2
from tjmonopix2.system import logger

log = logger.setup_derived_logger('FirmwareManager')

tjmonopix2_path = os.path.dirname(tjmonopix2.__file__)



def compile_firmware(name):
    ''' Compile firmware using vivado in tcl mode
    '''

    def get_return_string(timeout=1):
        ''' Helper function to get full return string.

            This complexity needed here since Xilinx does multi line returns
        '''
        flushed = bytearray()
        try:
            while not vivado.expect(r'.+', timeout=timeout):
                flushed += vivado.match.group(0)
        except (pexpect.exceptions.TIMEOUT, pexpect.exceptions.EOF):
            pass
        return flushed.decode('utf-8')

    supported_firmwares = ['BDAQ53', 'MIO3']
    if name not in supported_firmwares:
        log.error('Can only compile firmwares: %s', ','.join(supported_firmwares))
        return

    log.info('Compile firmware %s', name)

    vivado_tcl = os.path.join(tjmonopix2_path, '..', 'firmware/vivado')

    # Use mappings from run.tcl
    fpga_types = {'BDAQ53': 'xc7k160tffg676-2',
                  'MIO3': 'xc7k160tfbg676-1'}
    constrains_files = {'BDAQ53': '../src/bdaq53.xdc',
                        'MIO3': '../src/mio3.xdc'}
    flash_sizes = {'BDAQ53': '64',
                   'MIO3': '64'}

    for k, v in fpga_types.items():
        if k in name:
            fpga_type = v
            constrain_files = constrains_files[k]
            flash_size = flash_sizes[k]
            board_name = k

    command_args = fpga_type + ' ' + board_name + ' ' + constrain_files + ' ' + flash_size
    command = 'vivado -mode tcl -source run.tcl -tclargs %s' % command_args
    log.info('Compiling firmware. Takes about 10 minutes!')
    try:
        vivado = pexpect.spawn(command, cwd=vivado_tcl, timeout=10)
        vivado.expect('Vivado', timeout=5)
    except pexpect.exceptions.ExceptionPexpect:
        log.error('Cannot execute vivado command %d.\nMaybe paid version is missing that is needed for compilation?', command)
        return

    import time
    timeout = 100  # 500 seconds with no new print to screen
    t = 0
    while t < timeout:
        r = get_return_string()
        if r:
            if 'write_cfgmem completed successfully' in r:
                break
            print('.', end='', flush=True)
            t = 0
        else:
            time.sleep(5)
            t += 1
    else:
        raise RuntimeError('Timeout during compilation, check vivado.log')

    # Move firmware to current folder
    log.info('SUCCESS! Firmware can be found in firmware/bit folder')


def flash_firmware(name):
    ''' Flash firmware using vivado in tcl mode
    '''

    def get_return_string(timeout=1):
        ''' Helper function to get full return string.

            This complexity needed here since Xilinx does multi line returns
        '''
        flushed = bytearray()
        try:
            while not vivado.expect(r'.+', timeout=timeout):
                flushed += vivado.match.group(0)
        except pexpect.exceptions.TIMEOUT:
            pass
        return flushed.decode('utf-8')

    def write_flash_memory(name):
        vivado.sendline('set_property PROGRAM.ADDRESS_RANGE {use_file} [get_property PROGRAM.HW_CFGMEM [current_hw_device]]')
        vivado.sendline('set_property PROGRAM.FILES {%s} [get_property PROGRAM.HW_CFGMEM [current_hw_device]]' % name)
        vivado.sendline('set_property PROGRAM.BLANK_CHECK 0 [ get_property PROGRAM.HW_CFGMEM [current_hw_device]]')
        vivado.sendline('set_property PROGRAM.ERASE 1 [get_property PROGRAM.HW_CFGMEM [current_hw_device]]')
        vivado.sendline('set_property PROGRAM.CFG_PROGRAM 1 [get_property PROGRAM.HW_CFGMEM [current_hw_device]]')
        vivado.sendline('set_property PROGRAM.VERIFY 1 [get_property PROGRAM.HW_CFGMEM [current_hw_device]]')

        vivado.sendline('create_hw_bitstream -hw_device [current_hw_device] [get_property PROGRAM.HW_CFGMEM_BITFILE [current_hw_device]]')
        vivado.sendline('program_hw_devices [current_hw_device]')
        vivado.expect('End of startup status: HIGH', timeout=10)

        vivado.sendline('program_hw_cfgmem -hw_cfgmem [ get_property PROGRAM.HW_CFGMEM [current_hw_device]]')
        vivado.expect('Flash programming completed successfully', timeout=2 * 60)  # Generous timeout
        return get_return_string()

    try:
        vivado = pexpect.spawn('vivado_lab -mode tcl', timeout=10)  # try lab version
        vivado.expect('Vivado', timeout=5)
    except pexpect.exceptions.ExceptionPexpect:
        try:
            vivado = pexpect.spawn('vivado -mode tcl', timeout=10)  # try full version
            vivado.expect('Vivado', timeout=5)
        except pexpect.exceptions.ExceptionPexpect:
            log.error('Cannot execute vivado / vivado_lab commend')
            return
    vivado.expect(['vivado_lab%', 'Vivado%'])  # Booted up when showing prompt

    log.info('Connecting to JTAG interface')

    vivado.sendline('open_hw_manager')
    vivado.expect(['vivado_lab%', 'Vivado%'])  # Command finished when showing prompt

    vivado.sendline('connect_hw_server')
    vivado.expect('localhost')  # Printed when successful
    get_return_string()

    vivado.sendline('current_hw_target')
    ret = get_return_string()
    log.info('Connected to FPGA: %s', ret)
    if 'WARNING' in ret:
        log.error('Cannot find programmer hardware, Xilinx warning:\n%s', ret)
        vivado.sendline('exit')
        vivado.expect('Exiting')
        return

    vivado.sendline('open_hw_target')
    vivado.expect('Opening hw_target')  # Printed when programmer found

    vivado.sendline('current_hw_device [lindex [get_hw_devices] 0]')
    vivado.expect(['vivado_lab%', 'Vivado%'])  # Printed when finished
    ret = get_return_string()

    if 'xc7k160t' in ret and 'bdaq' not in name and 'mio3' not in name:
        log.error('The selected bitfile \'%s\' does not match the connected FPGA type \'xc7k160t\'', name)
        vivado.sendline('exit')
        vivado.expect('Exiting')
        return

    if '.bit' in name or '.bin' in name:
        log.info('Writing only to FPGA, not to FLASH memory. Config lost after power cycle!')

        vivado.sendline('set devPart [get_property PART [current_hw_device]]')
        vivado.expect(['vivado_lab%', 'Vivado%'])  # Printed when finished

        vivado.sendline('set_property PROGRAM.FILE {%s} [current_hw_device]' % name)
        vivado.expect(['vivado_lab%', 'Vivado%'])  # Printed when finished

        log.info('Writing firmware %s', name)

        vivado.sendline('program_hw_devices [current_hw_device]')
        vivado.expect('End of startup status: HIGH')  # firmware upload successful
    elif '.mcs' in name:
        log.info('Writing to the FLASH memory. Config kept even after power cycle.')

        flash_chip = 's25fl512s-spi-x1_x2_x4'  # Flash memory for KX2 and newer revisions of KX1
        try:
            vivado.sendline('create_hw_cfgmem -hw_device [current_hw_device] [lindex [get_cfgmem_parts {%s}] 0]' % flash_chip)
            ret = write_flash_memory(name)
        except:
            log.warning("Configuration with memory type s25fl512s-spi-x1_x2_x4 failed, trying mt25ql256-spi-x1_x2_x4")
            flash_chip = 'mt25ql256-spi-x1_x2_x4'  # Try flash memory of earlier revisions
            vivado.sendline('create_hw_cfgmem -hw_device [current_hw_device] [lindex [get_cfgmem_parts {%s}] 0]' % flash_chip)
            ret = write_flash_memory(name)

        log.info(ret)

        vivado.sendline('boot_hw_device [current_hw_device]')
        vivado.expect('Done pin status: HIGH')

    vivado.sendline('close_hw_target')
    vivado.expect('Closing')
    vivado.sendline('exit')
    vivado.expect('Exiting')

    log.success('All done!')


def find_vivado(path):
    ''' Search in std. installation paths for vivado(_lab) binary
    '''

    if platform == "linux" or platform == "linux2":
        linux_install_path = '/opt/' if not path else path
        # Try vivado full install
        paths = where(name='vivado', path=linux_install_path)
        for path in paths:
            if 'bin' in path:
                return os.path.dirname(os.path.realpath(path))
        # Try vivado lab install
        paths = where(name='vivado_lab', path=linux_install_path)
        for path in paths:
            if 'bin' in path:
                return os.path.dirname(os.path.realpath(path))
    else:
        raise NotImplementedError('Only Linux supported')


def where(name, path, flags=os.F_OK):
    result = []
    paths = [path]
    for outerpath in paths:
        for innerpath, _, _ in os.walk(outerpath):
            path = os.path.join(innerpath, name)
            if os.access(path, flags):
                result.append(os.path.normpath(path))
    return result



def run(name, path=None, create=False, target='flash'):
    ''' Steps to download/compile/flash matching firmware to FPGA

        name: str
            Firmware name:
                If name has .bit suffix try to flash from local file
                If not available find suitable firmware online, download, extract, and flash
        compile: boolean
            Compile firmware
    '''

    # TODO: For now assume vivado binary is added to current PATH
    # vivado_path = find_vivado(path)
    # if vivado_path:
    #     log.debug('Found vivado binary at %s', vivado_path)
    #     os.environ["PATH"] += os.pathsep + vivado_path
    # else:
    #     if path:
    #         log.error('Cannot find vivado installation in %s', path)
    #     else:
    #         log.error('Cannot find vivado installation!')
    #         if not create:
    #             log.error('Install vivado lab from here:\nhttps://www.xilinx.com/support/download.html')
    #         else:
    #             log.error('Install vivado paid version to be able to compile firmware')
    #     return

    if not create:
        if os.path.isfile(name):
            if '.mcs' in name:
                log.info('Found existing local configuration memory file')
                mcs_file = name
            elif '.bit' in name:
                log.info('Found existing local bit file')
                bit_file = name
        # TODO: For now assume repository is properly installed and up to date
        # else:
        #     if not name.endswith('.tar.gz'):
        #         name += '.tar.gz'
        #     stable_firmware = True  # std. setting: use stable (tag) firmware
        #     version = pkg_resources.get_distribution("tjmonopix2").version
        #     if not os.getenv('CI'):
        #         try:
        #             import git
        #             try:
        #                 repo = git.Repo(search_parent_directories=True, path=bdaq53_path)
        #                 active_branch = repo.active_branch
        #                 if active_branch != 'master':
        #                     stable_firmware = False  # use development firmware
        #             except git.InvalidGitRepositoryError:  # no github repo --> use stable firmware
        #                 pass
        #         except ImportError:  # git not available
        #             log.warning('Git not properly installed, assume software release %s', version)
        #             pass
        #         if stable_firmware:
        #             tag_list = get_tag_list(firmware_url)
        #             matches = [i for i in range(len(tag_list)) if version in tag_list[i]]
        #             if not matches:
        #                 raise RuntimeError('Cannot find tag version %s at %s', version, firmware_url)
        #             tag_url = firmware_url + '/' + tag_list[matches[0]]
        #             log.info('Download stable firmware version %s', version)
        #             archiv_name = download_firmware(name, tag_url)
        #         else:
        #             log.info('Download development firmware')
        #             archiv_name = download_firmware(name, firmware_dev_url + '.md')
        #     else:  # always use development version for CI runner
        #         archiv_name = download_firmware(name, firmware_dev_url + '.md')
        #     if not archiv_name:
        #         return
        #     bit_file, mcs_file = unpack_files(archiv_name)
        if target == 'flash':
            flash_firmware(mcs_file)
        elif target == 'fpga':
            flash_firmware(bit_file)
        else:
            log.error('No JTAG target (fpga, flash) specified')
    else:
        # get_si_tcp()  # get missing SiTCP sources
        compile_firmware(name)


def main():
    parser = argparse.ArgumentParser(description='TJ-Monopix2 firmware manager', formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('--firmware',
                        nargs=1,
                        help='Firmware file name or platform to build firmware for',)

    parser.add_argument('--vivado_path',
                        default=[None],
                        nargs=1,
                        help='Path of vivado installation',)

    parser.add_argument('-c', '--compile',
                        action='store_true',
                        help='Compiles firmware. Set platform name with --firmware, BDAQ53 and MIO3 are supported',)

    parser.add_argument('--target',
                        default='fpga',
                        help='Selects firmware target:\n  fpga: firmware is written to the FPGA and lost after power-cycle (useful for debugging)\n  flash: firmware is written to the persistent flash memory and loaded after power-cycle',)

    args = parser.parse_args()

    # if args.firmware is None:
    #     log.info('Available development firmware versions:')
    #     for link in find_links(firmware_dev_url + '.md'):
    #         print(link[:-7])
    # else:
    #     run(args.firmware[0], path=args.vivado_path[0], create=args.compile, target=args.target)
    if args.firmware is not None:
        run(args.firmware[0], path=args.vivado_path[0], create=args.compile, target=args.target)


if __name__ == '__main__':
    main()
