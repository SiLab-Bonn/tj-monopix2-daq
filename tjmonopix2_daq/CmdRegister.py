#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import array

from basil.RL.RegisterLayer import RegisterLayer
from basil.utils.BitLogic import BitLogic
from basil.utils import utils
from six import integer_types
from bitarray import bitarray


class CmdRegister(RegisterLayer):
    def __init__(self, driver, conf):
        super(CmdRegister, self).__init__(driver, conf)
        self._size = conf['size']
        self._fields = dict()
        self._bv = None
        self._fields_conf = dict()

        if 'fields' in self._conf:
            for field in self._conf['fields']:
                
                if field['offset'] + 1 < field['size']:
                    raise ValueError("Register " + self._conf['name'] + ":" + field['name'] + ": Invalid offset value. Specify MSB position.")

                if 'repeat' in field:
                    reg_list = []
                    for _ in range(field['repeat']):
                        reg = CmdRegister(None, field)
                        reg_list.append(reg)
                    self._fields[field['name']] = reg_list
                else:
                    bv = BitLogic(field['size'])
                    self._fields[field['name']] = bv

                self._fields_conf[field['name']] = field
                # set default
                if "default" in field:
                    self[field['name']] = field['default']
        self._bv = BitLogic(self._conf['size'])
        ##self._reg_buf = utils.bitarray_to_byte_array(self._construct_reg)

    def init(self):
        super(CmdRegister, self).init()
        self.set_configuration(self._init)

    def __getitem__(self, items):
        if isinstance(items, str):
            return self._fields[items]
        elif isinstance(items, slice):
            reg = self._construct_reg()
            return reg.__getitem__(items)
        else:
            raise TypeError("Invalid argument type.")

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            reg = self._construct_reg()
            reg[key.start:key.stop] = value
            self._deconstruct_reg(reg)
        elif isinstance(key, str):
            self._fields[key][len(self._fields[key]) - 1:0] = value
            if 'bit_order' in self._get_field_config(key):
                new_val = BitLogic(len(self._fields[key]))
                for i, bit in enumerate(self._get_field_config(key)['bit_order']):
                    new_val[len(self._fields[key]) - 1 - i] = self._fields[key][bit]
                print("=====sim=====",new_val)
                self._fields[key] = new_val
        elif isinstance(key, integer_types):
            reg = self._construct_reg()
            reg[key] = value
            self._deconstruct_reg(reg)
        else:
            raise TypeError("Invalid argument type.")

    def __len__(self):
        return self._conf['size']

    def __str__(self):
        fields = dict()
        full = dict()

        reg = self._construct_reg()
        full[self._conf['name']] = str(len(reg)) + 'b' + str(reg[:])

        for field in self._fields:
            if 'repeat' in self._get_field_config(field):
                for i, sub_reg in enumerate(self._fields[field]):
                    fields[str(field) + '[' + str(i) + ']'] = str(sub_reg)
            else:
                fields[field] = str(len(self._fields[field])) + 'b' + str(self._fields[field][:])

        if self._fields:
            return str([full, fields])
        else:
            return str(full)

    def set(self, value):
        self[:] = value

    def write(self, field, chip_id=16, write=True):
        if isinstance(field, str):
            address = self._fields_conf[field]['address']
            reg = self._construct_reg()
            indata = []
            for i in range((self._fields_conf[field]['size']-1) // 16 + 1):
                data = reg[(address+i + 1) * 16 - 1:(address+i) * 16]
                print("======sim=====CmdReg", address+i, hex(data.tovalue()))
                indata += self._drv.write_register(address+i, data.tovalue(), chip_id=chip_id, write=False)
            if write:
                self._drv.write_command(indata)
        #else:
        #    reg = self._construct_reg()
        #    tmp = utils.bitarray_to_byte_array(reg)
        #    addr_list = np.argwhere(self._reg_buf != tmp )
        #    for i in addr_list:
        #        data = reg[(i + 1) * 16 - 1: i * 16]
        #        print("======sim=====CmdReg", address+i, hex(data.tovalue()))
        #        indata += self._drv.write_register(address+i, data.tovalue(), chip_id=chip_id, write=False)
        #    self._reg_buf = tmp
        return indata

    def read(self, field, chip_id=16, write=True):
        indata = []
        for i in range((self._fields_conf[field]['size']-1) // 16 + 1):
            a = self._fields_conf[field]['address'] + i
            print("======sim=====CmdReg read", a)
            indata += self._drv.read_register(a, chip_id=chip_id, write=False)
        if write:
            self._drv.write_command(indata)
        return indata

    def update(self, address, value):
        reg = self._construct_reg()
        print("======sim=====CmdReg update", address, hex(value),
            len(reg[(address + 1) * 16-1:address * 16]),
            len(bitarray("{0:016b}".format(value)[::-1])))

        reg[(address + 1) * 16-1:address * 16] = bitarray("{0:016b}".format(value)[::-1])
        self._deconstruct_reg(reg)

    def _construct_reg(self):
        for field in self._fields:
            offs = self._fields_conf[field]['address']*16 + self._fields_conf[field]['offset']

            if 'repeat' in self._fields_conf[field]:
                for i, sub_field in enumerate(self._fields[field]):
                    bvstart = offs - i * self._get_field_config(field)['size']
                    bvstop = bvstart - len(sub_field._construct_reg()) + 1
#                     self._bv[bvstart:bvstop] = sub_field._construct_reg()
                    self._bv.set_slice_ba(bvstart, bvstop, sub_field._construct_reg())
            else:
                bvsize = len(self._fields[field])
                bvstart = offs
                bvstop = offs - bvsize + 1
#                 self._bv[bvstart:bvstop] = self._fields[field]
                self._bv.set_slice_ba(bvstart, bvstop, self._fields[field])
        return self._bv

    def _deconstruct_reg(self, reg):
        for field in self._fields:
            offs = self._fields_conf[field]['address']*16 + self._get_field_config(field)['offset']
            bvsize = self._get_field_config(field)['size']
            bvstart = offs
            bvstop = offs - bvsize + 1
            if 'repeat' in self._get_field_config(field):
                size = self._get_field_config(field)['size']
                for i, ifield in enumerate(self._fields[field]):
                    ifield.set(reg[bvstart - size * i:bvstop - size * i])
            else:
                self._fields[field] = reg[bvstart:bvstop]

    def _get_field_config(self, field):
        return self._fields_conf[field]

    def tobytes(self):
        reg = self._construct_reg()
        return utils.bitarray_to_byte_array(reg)

    def setall(self, value):
        reg = self._construct_reg()
        reg.setall(value)
        self._deconstruct_reg(reg)

    def frombytes(self, value):
        bl_value = BitLogic()
        bl_value.frombytes(utils.tobytes(array.array('B', value)[::-1]))
        self._deconstruct_reg(bl_value[self._conf['size']:])

    def get_configuration(self):
        fields = dict()

        reg = self._construct_reg()

        for field in self._fields:
            if 'repeat' in self._get_field_config(field):
                rep_field = []
                for sub_reg in self._fields[field]:
                    rep_field.append(sub_reg.get_configuration())

                fields[field] = rep_field
            else:
                fields[field] = str(self._fields[field][:])

        if self._fields:
            return fields
        else:
            return str(reg[:])

    def set_configuration(self, conf):
        for name, value in conf.items():
            if name in self._fields:
                if 'repeat' in self._fields_conf[name]:
                    for i, rep_val_dict in enumerate(value):
                        for rep_name, rep_value in rep_val_dict.items():
                            self[name][i][rep_name] = rep_value
                else:
                    #print("=====sim=====", name, value)
                    self[name] = value
            else:
                raise ValueError("Register %s does not exist." % name)
