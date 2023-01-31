""" Functions to support the Pylontech US3000 and similar Batteries.

    This module provides Classes to communicate over RS-485 to the Pylontech
    Battery. This code is based on the
    "PYLON low voltage Protocol RS485", Version 3.3 (2018/08/21)

    The RS-485 communication ist based on waveshare 2-Channel RS485 Module for Raspberry
    Pi Pico as hardware 
"""

from machine import UART, Pin
import time

VERBOSE = False

CHKSUM_BYTES = 4
EOI_BYTES = 1


class Rs485Handler:
    """ Handles the serial to RS485 adapter provides sending and receiving
        frames defined by start byte and end byte preset for
        - 115200 baud,8n1
        - UART0 as serial device
    """
    VERBOSE_1 = False
    
    def __init__(self, device=0, baud=115200, bits=8, parity=None,stop=1):
        self.device=device
        self.baud=baud
        self.bits = bits
        self.parity = parity
        self.stop = stop
        self.connect()
        
    def connect(self):
        try:
            # open serial port:
            if self.VERBOSE_1:
                print(self.device,self.baud,self.bits,self.parity,self.stop)
            self.ser = UART(self.device,self.baud,tx=Pin(0),rx = Pin(1))
            self.ser.init(self.baud, self.bits,self.parity,self.stop)
        except OSError:
            print("UART not found: " + device)
            exit(1)

    def verbose_print(self, data):
        if self.VERBOSE_1 :
            print(data)

    def send(self, data):
        """ send a Frame of binary data
        :param data:  binary data e.g. b'~2002464FC0048520FCB2\r'
        :return:      -
        """
        #self.verbose_print("->  " + data.decode())
        self.send_start_time = time.ticks_us()
        self.ser.write(data)
        while self.ser.flush():
            time.sleep_us(10) # 10
        self.send_duration = time.ticks_us() - self.send_start_time

    def receive_frame(self, end_wait_time, start=b'~', end=b'\r'):
        """ receives a frame defined by a start byte/prefix and end byte/suffix
        :param end_time:
            we expect receiving the last character before this timestamp
        :param start:
            the start byte, e.g. b'~'
        :param end:
            the end byte, e.g. b'\r'
        :return:
            the frame as binary data,
            e.g. b'~200246000000FDB2\r'
            returns after the first end byte.
        """
        while self.ser.any() == 0:
            time.sleep_us(10)
            if time.ticks_us() > end_wait_time:
               print('Timeout waiting for an answer.')
               return None
        char = self.ser.read(1)
        # wait for leading byte / start byte
        while char != start:
            char = self.ser.read(1)
            if time.ticks_us() > end_wait_time:
                raise Exception('Timeout waiting for start byte.')
                #return None
        self.receive_start_time = time.ticks_us()  # just for Timeout handling
        # receive the whole transmission with the trialing byte / end bytes:
        frame = start + self.ser.read()  # this uses the inter_byte_timeout on failure.
        self.receive_duration = time.ticks_us() - self.receive_start_time  # just for Timeout handling
        frame_lgt = len(frame)
        #self.verbose_print("\r <- " + frame.decode())
        self.verbose_print(f"send    duration:{self.send_duration:6d} us;\r\nreceive duration {self.receive_duration:6d} us")
        self.verbose_print(f"frame lgt: {frame_lgt}")
        return frame

    def reconnect(self):
        """ force reinit of UART"""
        self.ser.init(self.baud, self.bits,self.parity,self.stop)

    def close(self):
        """ force close serial connection"""
        self.close()


class PylontechRS485:
    """ pylontech rs485 protocol handler
        can send and receive using a RS-485 adapter
        - checks the packet checksum for received packets.
        - adapts the packet checksum and adds prefix and suffix for packets to be sent.
    """
    valid_chars = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F']
    verbose = 0

    def __init__(self, device=0, baud=115200, bits=8, parity=None, stop=1):
        """ init function of the pylontech rs485 protocol handler
            UART0 == 0, UART1 == 1
        :param baud:
            valid baud rate, identical to the setting at the Battery,
            e.g. 9600 or 115200
        """
        self.rs485 = Rs485Handler(device, baud, bits=8, parity=None, stop=1)

    def verbose(self, level):
        self.verbose = level
        self.rs485.verbose = level
 
    def receive(self, timeout_us=20000):
        """
        try to receive a pylontech type packet from the pico UART.
        checks the packet checksum and returns the packet if the checksum is correct.
        :param timeout:
            timespan until packet has to be received
        :return:
            returns the frame or an empty list
        """
        start_byte = b'~'
        end_byte = b'\r'
        end_waiting_time = time.ticks_us() + timeout_us
        data = self.rs485.receive_frame(end_waiting_time, start=start_byte, end=end_byte)
        # check len
        if data is None:
            return None
        if len(data) < 16: # smaller then minimal size
            return None
        start = data.index(b'~')   # check prefix and suffix
        if start > 0:
            data = data[start:-1]
        if data[0] != start_byte[0]:  # default: start = 0x7e = '~', pefix missing
            raise ValueError("no Prefix '{}' received:\nreceived:\n{}".format(start_byte, data[0]))
        if data[-1] != end_byte[0]:   # default: end = 0xd = '\r', suffix missing
            raise ValueError("no suffix '{}' received:\nreceived:\n{}".format(end_byte, data[-1]))
        package = data[1:-1]  # packet stripped, - without prefix, suffix
        chksum = self.get_chk_sum(package, len(package))
        chksum_from_pkg = int(package[-4:].decode(),16)
        if chksum == chksum_from_pkg:
            return package
        else:
            print('checksum error')
            raise ValueError(f"crc error;  Soll<->ist: {chksum:04x} --- {chksum_from_pkg:04x}")
        
    @staticmethod
    def get_chk_sum(data, size):
        sum = 0
        for byte in data[0:size - CHKSUM_BYTES]:
            sum += byte
        sum = ~sum
        sum &= 0xFFFF
        sum += 1
        return sum

    def send(self, data):
        """
        sends a pylontech type packet to the RS-485 UART.
        :param data: packet as binary string
                     - checksum will be calculated and written,
                     - prefix/suffix will be added.
                     e.g. given b'2002464FC0048520' will be sent as b'~2002464FC0048520....\r'
        :return:     -
        """
        chksum = self.get_chk_sum(data, len(data) + CHKSUM_BYTES)
        package = ("~" + data.decode() + "{:04X}".format(chksum) + "\r").encode()
        self.rs485.send(package)

    def reconnect(self):
        """ force reconnect to serial port"""
        self.rs485.reconnect()

    def close(self):
        """ force close serial connection"""
        self.rs485.close()

if __name__ == '__main__':
    handler = PylontechRS485(0,115200)
    handler.verbose(11)
    frame = b'2002464FC0048520'  # get protocol version
    handler.send(frame)
    raw = handler.receive()
    print('raw', raw)

