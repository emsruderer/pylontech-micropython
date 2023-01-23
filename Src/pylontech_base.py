""" Functions to support the Pylontech US2000 and similar Batteries.

    This module provides Classes to communicate over RS-485 to the Pylontech
    Battery. This code is based on the
    "PYLON low voltage Protocol RS485", Version 3.3 (2018/08/21)

    The RS-485 communication ist based on pyserial.
    As hardware, a simple usb-serial rs485 adapter can be used.
    these adapter are able to receive out of the box, sending is possible
    by enabling the transceive pin using the RTS signal.
"""

from machine import UART, Pin
import time

CHKSUM_BYTES = 4
EOI_BYTES = 1


class Rs485Handler:
    """ Handles the serial to RS485 adapter with TE / Transmit Enable on RTS
        provides sending and receiving frames defined by start byte and end byte
        preset for
        - 115200 baud,8n1
        - UART0 as serial device
     """
    sendTime1 = 0
    sendTime2 = 0
    rcvTime1 = 0
    rcvTime2 = 0
    verbose = False

    def __init__(self, device=0, baud=115200, bits=8, parity=None,stop=1):
        self.device=device
        self.baud=baud
        self.bits = bits
        self.parity = parity
        self.stop = stop
        self.connect()
        self.timeout=10.0,
        self.inter_byte_timeout=0.02
        
    def connect(self):
        try:
            # open serial port:
            if self.verbose > 0:
                print(self.device,self.baud,self.bits,self.parity,self.stop)
            self.ser = UART(self.device,self.baud,tx=Pin(0),rx = Pin(1))
            self.ser.init(self.baud, self.bits,self.parity,self.stop)
        except OSError:
            print("UART not found: " + device)
            exit(1)

    def verbose_print(self, data):
        if self.verbose > 0:
            print(data)

    def send(self, data):
        """ send a Frame of binary data
        :param data:  binary data e.g. b'~2002464FC0048520FCB2\r'
        :return:      -
        """
        self.verbose_print("->  " + data.decode())
        self.ser.write(data)
        self.sendTime1 = time.time_ns()
        time.sleep_ms(10)
        self.sendTime2 = time.time_ns() - self.sendTime1

    def receive_frame(self, end_time, start=b'~', end=b'\r'):
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
            if time.time_ns() > end_time:
               print('Timeout waiting for an answer.')
               return None
        char = self.ser.read(1)
        # wait for leading byte / start byte; empty the buffer before the start byte:
        while char != start:
            char = self.ser.read(1)
            if time.time_ns() > end_time:
                print("raise Exception('Timeout waiting for an answer.')")
                return None
        self.rcvTime1 = time.time_ns() - self.sendTime1  # just for Timeout handling
        # receive all until the trialing byte / end byte:
        # and build a complete frame as we throw the start byte...
        frame = start + self.ser.read()  # this uses the inter_byte_timeout on failure.
        # just more timeout handling:
        self.rcvTime2 = time.time_ns() - self.sendTime1  # just for Timeout handling
        # just for debugging:
        self.verbose_print("\r <- " + frame.decode())
        self.verbose_print(" times:{:8d}{:8d}   -{:8d} ".format(
            self.sendTime2 , self.rcvTime1 , self.rcvTime2))
        # return the frame
        return frame

    def reconnect(self):
        """ force reconnect to serial port"""
        self.connect();
       # self.clear_rx_buffer()

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

    def verbose(self, level=0):
        self.verbose = level
        if level >10:
            self.rs485.verbose = level - 10
        else:
            self.rs485.verbose = 0

    def receive(self, timeout_ns=50):
        """
        try to receive a pylontech type packet from the RS-485 serial port.
        checks the packet checksum and returns the packet if the checksum is correct.
        :param timeout:
            timespan until packet has to be received
        :return:
            returns the frame or an empty list
        """
        start_byte = b'~'
        end_byte = b'\r'
        end_time = time.time_ns() + timeout_ns
        data = self.rs485.receive_frame(end_time=end_time, start=start_byte, end=end_byte)
        # check len
        if data is None:
            return None
        if len(data) < 16:
            # smaller then minimal size
            return None
        start = data.index(b'~')
        if start > 0:
            data = data[start:-1]
        # check prefix and suffix
        index = 0
        while (data[index] != 0x7E) and (data[index] not in self.valid_chars):
            index += 1
            if (data[index] == 0x7E) and (data[index] in self.valid_chars):
                data = data[index:len(data)]
                break
        if data[0] != start_byte[0]:  # default: start = 0x7e = '~'
            # pefix missing
            raise ValueError("no Prefix '{}' received:\nreceived:\n{}".format(start_byte, data[0]))
            return None
        if data[-1] != end_byte[0]:   # default: start = 0xd = '\r'
            # suffix missing
            raise ValueError("no suffix '{}' received:\nreceived:\n{}".format(end_byte, data[-1]))
            return None
        data = data[1:-1]  # packet stripped, - without prefix, suffix
        packages = data.split(b'\r~')
        data2 = []
        for package in reversed(packages):
            chksum = self.get_chk_sum(package, len(package))
            chksum_from_pkg = int(package[-4:].decode(),16)
            if chksum == chksum_from_pkg:
                data2.append(package)
            else:
                raise ValueError("crc error;  Soll<->ist: {:04x} --- {:04x}\nPacket:\n{}".format(chksum, chksum_from_pkg, package))
        return data2

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
        sends a pylontech type packet to the RS-485 serial port.
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

