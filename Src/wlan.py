from machine import UART, Pin
from machine import RTC
from machine import reset
import time
import network
import socket
import rp2
import sys
import struct
import ubinascii

ssid = "SSID"
password = "PASSWORD"

DEBUG = False
VERBOSE = True

"""
# connect GPIO 22 with RUN (29 with 30) to reset the pico
def reset():
    machine.reset()
    p = Pin(22, Pin.OUT)
    p.off()
    """

# use onboard LED for a active internet connection
def led_on():
    Pin("LED",Pin.OUT).on()
    
def led_off():
    Pin("LED",Pin.OUT).off()
    
# set the wlan to your country, here Germany
rp2.country("DE")

class Wifi:
    def __init__(self, ssid, password):
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.wlan.connect(ssid, password)

        max_wait = 5
        while max_wait > 0:
            if self.wlan.status() < 0 or self.wlan.status() >= 3:
                break
            max_wait -= 1
            led_on()
            if VERBOSE: print("waiting for connection...")
            time.sleep(1)
            led_off()

            # Handle connection error
        status = self.wlan.status()
        if status != 3:
            led_off()
            raise RuntimeError("network connection failed {status}")
        else:
            led_on()
            if VERBOSE: print("connected")
            self.status = self.wlan.ifconfig()
            if VERBOSE: print("ip = " + self.status[0])

    def request_time(self,addr="1.de.pool.ntp.org"):
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
        if VERBOSE: print("GMT: {}:{}:{} {}-{}-{}".format(d[3], d[4], d[5], d[2], d[1], d[0]) )
        return rtc
    
    def disconnect(self):
        self.wlan.active(False)
        self.wlan.disconnect()
        led_off()

if __name__ == '__main__' :
  try:
    wlan = Wifi(ssid,password)
    rtc = wlan.get_rtc()
    d = time.gmtime(wlan.request_time())
    print("GMT: {}:{}:{} {}-{}-{}".format(d[3], d[4], d[5], d[2], d[1], d[0]) )
    wlan.disconnect()
  except:
      system.exit(1)
    # reset()
  