import logging
#logging.basicConfig(level=logging.DEBUG,filename='pylontech.log')
logger = logging.getLogger("wlan","net.log")
#logger = logging.getLogger("wlan")
logger.setLevel(logging.INFO)

from machine import UART, Pin, RTC, Timer
from machine import reset
import time
import network
import socket
import rp2
import sys
import struct
import ubinascii

SSID = "LocalNetwork"
PASSWORD = "PASSWORD"

LINK_DOWN = 0
LINK_JOIN = 1
LINK_NOIP = 2
LINK_UP = 3
LINK_FAIL = -1
LINK_NONET = -2
LINK_BADAUTH = -3

# set the wlan to your country, here Germany
rp2.country("DE")

HEARTBEAT = False

rtc = RTC()

counter = 0
period = 60
router = "192.168.20.1"

# use onboard LED for a active internet connection
def led_on():
    Pin("LED", Pin.OUT).on()


def led_off():
    Pin("LED", Pin.OUT).off()

# µPing (MicroPing) for MicroPython
# copyright (c) 2018 Shawwwn <shawwwn1@gmail.com>
# License: MIT

# Internet Checksum Algorithm
# Author: Olav Morken
# https://github.com/olavmrk/python-ping/blob/master/ping.py
# @data: bytes
def checksum(data):
    if len(data) & 0x1: # Odd number of bytes
        data += b'\0'
    cs = 0
    for pos in range(0, len(data), 2):
        b1 = data[pos]
        b2 = data[pos + 1]
        cs += (b1 << 8) + b2
    while cs >= 0x10000:
        cs = (cs & 0xffff) + (cs >> 16)
    cs = ~cs & 0xffff
    return cs

def ping(host, count=4, timeout=5000, interval=30, quiet=False, size=64):
    import utime
    import uselect
    import uctypes
    import usocket
    import ustruct
    import urandom

    # prepare packet
    assert size >= 16, "pkt size too small"
    pkt = b'Q'*size
    pkt_desc = {
        "type": uctypes.UINT8 | 0,
        "code": uctypes.UINT8 | 1,
        "checksum": uctypes.UINT16 | 2,
        "id": uctypes.UINT16 | 4,
        "seq": uctypes.INT16 | 6,
        "timestamp": uctypes.UINT64 | 8,
    } # packet header descriptor
    h = uctypes.struct(uctypes.addressof(pkt), pkt_desc, uctypes.BIG_ENDIAN)
    h.type = 8 # ICMP_ECHO_REQUEST
    h.code = 0
    h.checksum = 0
    h.id = urandom.randint(0, 65535)
    h.seq = 1

    # init socket
    sock = usocket.socket(usocket.AF_INET, usocket.SOCK_RAW, 1)
    sock.setblocking(0)
    sock.settimeout(timeout/1000)
    addr = usocket.getaddrinfo(host, 1)[0][-1][0] # ip address
    sock.connect((addr, 1))
    logger.debug("PING %s (%s): %u data bytes" % (host, addr, len(pkt)))

    seqs = list(range(1, count+1)) # [1,2,...,count]
    c = 1
    t = 0
    n_trans = 0
    n_recv = 0
    finish = False
    while t < timeout:
        if t==interval and c<=count:
            # send packet
            h.checksum = 0
            h.seq = c
            h.timestamp = utime.ticks_us()
            h.checksum = checksum(pkt)
            if sock.send(pkt) == size:
                n_trans += 1
                t = 0 # reset timeout
            else:
                seqs.remove(c)
            c += 1

        # recv packet
        while 1:
            socks, _, _ = uselect.select([sock], [], [], 0)
            if socks:
                resp = socks[0].recv(4096)
                resp_mv = memoryview(resp)
                h2 = uctypes.struct(uctypes.addressof(resp_mv[20:]), pkt_desc, uctypes.BIG_ENDIAN)
                # TODO: validate checksum (optional)
                seq = h2.seq
                if h2.type==0 and h2.id==h.id and (seq in seqs): # 0: ICMP_ECHO_REPLY
                    t_elasped = (utime.ticks_us()-h2.timestamp) / 1000
                    ttl = ustruct.unpack('!B', resp_mv[8:9])[0] # time-to-live
                    n_recv += 1
                    logger.debug("%u bytes from %s: icmp_seq=%u, ttl=%u, time=%f ms" % (len(resp), addr, seq, ttl, t_elasped))
                    seqs.remove(seq)
                    if len(seqs) == 0:
                        finish = True
                        break
            else:
                break

        if finish:
            break

        utime.sleep_ms(1)
        t += 1

    # close
    sock.close()
    ret = (n_trans, n_recv)
    logger.info("%u packets transmitted, %u packets received" % (n_trans, n_recv))
    return (n_trans, n_recv)

def set_router(ip):
    global router
    router = ip

""" fuction that test every minute if a connection with the router on the local net exist,
    if not tries to reconnect. Still buggy, do not use it unless trying to make the program more robust
    Not usefull during development of the functionality
"""
start = time.ticks_ms()
def alive(t):
    global start
    global counter
    delta = time.ticks_diff(time.ticks_ms(), start)/1000
    counter += 1
    logger.debug(counter)
    if counter % 60 == 0:
        logger.info(f"alive {delta}")
        freq = ping(router,quiet=False)
        if freq[1]>2: # 3 packets received
            return
        else: 
            led_off()
            status = wlan.get_status()
            if status < 0:
                raise OSError("wifi connection lost")
            elif status < 3:
                wlan.reconnect()
            else:
                raise RuntimeError("Contact with router lost")
    return

class Wifi:
    def __init__(self, ssid=SSID, password=PASSWORD):
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.wlan.config(pm=0xA11140)  # Disable power-save mode
        self.connect(ssid, password)

    def connect(self, ssid, password):
        self.wlan.connect(ssid, password)
        max_wait = 10
        while max_wait > 0:
            if self.wlan.status() < 0 or self.wlan.status() >= 3:
                break
            max_wait -= 1
            led_on()
            logger.info("waiting for connection...")
            time.sleep(1)
            led_off()

        # Handle connection error
        status = self.wlan.status()
        if status != LINK_UP:
            led_off()
            problem = self.link_status(status)
            raise RuntimeError(f"network connection failed {problem}")
        else:
            led_on()
            logger.info("connected")
            self.status = self.wlan.ifconfig()
            self.router = self.status[3]
            for x in range(len(self.status)):
                logger.info("ip = " + self.status[x])
            self.init_rtc()

    def reconnect(self):
        self.wlan.close()
        self.wlan.connect(SSID,PASSWORD)

    def get_ifconfig(self):
        return self.wlan.ifconfig()
    
    def get_router(self):
        return self.get_ifconfig()[3]
        

    def get_status(self):
        return self.wlan.status()

    def link_status(self,status):
        if status == LINK_DOWN:
            return "Link Down"
        elif status == LINK_JOIN:
            return "Joining"
        elif status == LINK_NOIP:
            return "No IP"
        elif status == LINK_UP:
            return "Connected"
        elif status == LINK_FAIL:
            return "Link Failed"
        elif status == LINK_NONET:
            return "No net available"
        elif status == LINK_BADAUTH:
            return "Authentication failed"

    """ This method creates a timer which fires every second a call to alive
        alive checks if a connection to the local net exists.
        Still buggy do not switch it on """
    """ Trying to use the pico watchdog for this in combination with a 'main.py' led to problems.
        I had to nuke the pico to make available/usable again """
    def create_heartbeat(self):
        #set_router(self.get_router())
        if HEARTBEAT:
            self.timer = Timer(period=1000, mode=Timer.PERIODIC, callback=lambda t:alive(t))
            logger.debug('timer created')
        
    def stop_heartbeat(self):
        if HEARTBEAT:
           self.timer.deinit()
    
    def request_time(self, addr="1.de.pool.ntp.org"):
        self.sockaddr = socket.getaddrinfo(addr, 123)[0][-1]
        REF_TIME_1970 = 2208988800  # reference time
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data = b"\x1b" + 47 * b"\0"
        self.client.sendto(self.data, self.sockaddr)
        self.data, self.address = self.client.recvfrom(1024)
        logger.debug(str(self.data) +'-'+str(self.address))
        if self.data:
            t = struct.unpack("!12I", self.data)[10]
            t -= REF_TIME_1970
        logger.debug(t)
        return t

    def init_rtc(self):
        global rtc
        t = self.request_time()
        d = time.localtime(t)
        logger.debug(d)
        tup = (d[0],d[1],d[2],d[6],d[3]+1, d[4], d[5], d[7])
        rtc.datetime(tup)
        logger.info(f"UTC:{d[3]}:{d[4]}:{d[5]} {d[2]}-{d[1]}-{d[0]}; 'day of week':{d[6]}; 'day of year':{d[7]}")

    def disconnect(self):
        self.wlan.active(False)
        self.wlan.disconnect()
        led_off()

#import memory

if __name__ == "__main__":
    try:
        logger.setLevel(logging.DEBUG)
        HEARTBEAT =  True
        wlan = Wifi(SSID, PASSWORD)
        d = time.localtime()
        print(f"{d[3]}:{d[4]}:{d[5]} {d[2]}-{d[1]}-{d[0]} weekday {d[6]} yearday {d[7]}")
        wlan.create_heartbeat()
        #memory.memory_thread()
        while True:
            logger.info('main alive')
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info('KeyboardInterrupt')
        wlan.stop_heartbeat()
        wlan.disconnect()
        sys.exit(1)
    except Exception as ex:
        logger.error('exception ' + str(ex))
    finally :
        wlan.disconnect()
        sys.exit(0)
