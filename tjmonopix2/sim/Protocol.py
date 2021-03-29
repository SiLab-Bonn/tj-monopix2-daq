#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#
# Initial version by Chris Higgs <chris.higgs@potentialventures.com>
#

"""
These classes are pickled and sent over a socket to communicate with the sim
Protocol is very simple, simply prefix the pickled data with a 4-byte length
"""
import pickle
import struct
import socket


class ProtocolBase(object):
    pass


class WriteRequest(ProtocolBase):

    def __init__(self, address, data):
        self.address = address
        self.data = data

    def __str__(self):
        return "WriteRequest: 0x%04x <- %s" % (self.address, self.data)


class ReadRequest(ProtocolBase):

    def __init__(self, address, size):
        self.address = address
        self.size = size

    def __str__(self):
        return "ReadRequest: 0x%04x (size %d)" % (self.address, self.size)


class ReadRequestStr(ProtocolBase):

    def __init__(self, address, size):
        self.address = address
        self.size = size

    def __str__(self):
        return "ReadRequestStr: 0x%04x (size %d)" % (self.address, self.size)


class ReadResponse(ProtocolBase):
    def __init__(self, data):
        self.data = data

    def __str__(self):
        return "ReadResponse: %s" % str(self.data)


class PickleInterface(ProtocolBase):

    def __init__(self, sock):
        self.sock = sock

    def send(self, obj):
        """Prepend a 4-byte length to the string"""
        assert isinstance(obj, ProtocolBase)
        string = pickle.dumps(obj)
        length = len(string)
        #print ("=====sim=====",length)
        #print ("=====sim=====",repr(struct.pack("<I", length)))
        #print("=====sim=====string",repr(string))
        self.sock.sendall(struct.pack("<I", length) + string)

    def recv(self, blocking=True):
        """Receive the next object from the socket"""
        dat=self.sock.recv(4)
        #print("=====sim===== Protocol.recv",repr(dat))
        length = struct.unpack("<I", dat)[0]
        return self._get_next_obj(length)

    def try_recv(self):
        """Return None immediately if nothing is waiting"""
        try:
            lenstr = self.sock.recv(4, socket.MSG_DONTWAIT)
        except socket.error:
            return None
        if len(lenstr) < 4:
            raise EOFError("Socket closed")
        length = struct.unpack("<I", lenstr)[0]
        return self._get_next_obj(length)

    def _get_next_obj(self, length):
        """Assumes we've already read the object length"""
        data = b''
        while len(data) < length:
            data += self.sock.recv(length - len(data))

        return pickle.loads(data)
