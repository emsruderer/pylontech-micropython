from machine import UART, Pin, RTC, Timer
from machine import reset
import time
import network
import socket
import rp2
import sys
import struct
import ubinascii

SSID = "SSID"
PASSWORD = "PASSWORD"

DEBUG = False
VERBOSE = True

LINK_DOWN = 0
LINK_JOIN = 1
LINK_NOIP = 2
LINK_UP = 3
LINK_FAIL = -1
LINK_NONET = -2
LINK_BADAUTH = -3

"""
# connect GPIO 22 with RUN (29 with 30) to reset the pico
def reset():
    machine.reset()
    p = Pin(22, Pin.OUT)
    p.off()
    """

# use onboard LED for a active internet connection
def led_on():
    Pin("LED", Pin.OUT).on()


def led_off():
    Pin("LED", Pin.OUT).off()


# set the wlan to your country, here Germany
rp2.country("DE")
counter = 0
period = 60
router = "192.168.20.1"
start = time.ticks_ms() 
import urequests

def alive(c):
    global start
    delta = time.ticks_diff(time.ticks_ms(), start)/1000
    global counter
    counter += 1
    #if VERBOSE: print(counter)
    if counter % 60 == 0:
        try:
            print(f"alive {delta}")
            print(counter)
            r = urequests.get(f"http://{router}")
            if r:
                print('get',r.text)
                return
        except OSError:
            led_off()
            status = wlan.get_status()
            if status < 0:
                raise RuntimeError
            elif status < 3:
                wlan.reconnect()

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
            if VERBOSE:
                print("waiting for connection...")
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
            if VERBOSE:
                print("connected")
            self.status = self.wlan.ifconfig()
            self.router = self.status[3]
            if VERBOSE:
                for x in range(len(self.status)):
                    print("ip = " + self.status[x])

    def reconnect(self):
        self.wlan.close()
        self.wlan.connect(SSID,PASSWORD)

    def get_ifconfig(self):
        return self.wlan.ifconfig()

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
        
    def create_timer(self):
        self.timer = Timer(period=1000, mode=Timer.PERIODIC, callback=lambda counter: alive(0))
        print('timer created')
        
    def deinit_timer(self):
        self.timer.deinit()
        
    
    def request_time(self, addr="1.de.pool.ntp.org"):
        self.sockaddr = socket.getaddrinfo(addr, 123)[0][-1]
        REF_TIME_1970 = 2208988800  # reference time
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data = b"\x1b" + 47 * b"\0"
        self.client.sendto(self.data, self.sockaddr)
        self.data, self.address = self.client.recvfrom(1024)
        # print(data, address)
        if self.data:
            t = struct.unpack("!12I", self.data)[10]
            t -= REF_TIME_1970
        return t

    def get_rtc(self):
        rtc = RTC()
        d = time.gmtime(self.request_time())
        rtc.datetime((d[0], d[1], d[2], d[6], d[3], d[4], d[5], 0))
        if VERBOSE:
            print("GMT: {}:{}:{} {}-{}-{}".format(d[3], d[4], d[5], d[2], d[1], d[0]))
        return rtc

    def disconnect(self):
        self.wlan.active(False)
        self.wlan.disconnect()
        led_off()



if __name__ == "__main__":
    try:
        wlan = Wifi(SSID, PASSWORD)
        rtc = wlan.get_rtc()
        d = time.gmtime(wlan.request_time())
        print("GMT: {}:{}:{} {}-{}-{}".format(d[3], d[4], d[5], d[2], d[1], d[0]))
        wlan.create_timer()
        while True:
            #r = urequests.get(f"http://{router}")
            print('main alive')
            time.sleep(10)

        wlan.create_timer()
        wlan.disconnect()

        # sys.exit(0)
    except KeyboardInterrupt:
        print('KeyboardInterrupt')
        wlan.deinit_timer()
        wlan.disconnect()
        sys.exit(1)
    # reset()
