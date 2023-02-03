from machine import UART, Pin, RTC, Timer
from machine import reset
import time
import network
import socket
import rp2
import sys
import struct
import ubinascii
import logging 

SSID = "Localnetwork"
PASSWORD = "Password"

DEBUG = False
VERBOSE = True

LINK_DOWN = 0
LINK_JOIN = 1
LINK_NOIP = 2
LINK_UP = 3
LINK_FAIL = -1
LINK_NONET = -2
LINK_BADAUTH = -3

# use onboard LED for a active internet connection
def led_on():
    Pin("LED", Pin.OUT).on()


def led_off():
    Pin("LED", Pin.OUT).off()


# set the wlan to your country, here Germany
rp2.country("DE")

HEARTBEAT = False
import urequests

counter = 0
period = 60
router = "192.168.20.1"
start = time.ticks_ms() 

rtc = RTC()

def set_router(ip):
    global router
    router = ip
    
""" fuction that test every minute if a connection with the router on the local net exist,
    if not tries to reconnect. Still buggy, do not use it unless trying to make the program more robust
    Not usefull during development of the functionality
"""
def alive():
    global start
    global counter
    delta = time.ticks_diff(time.ticks_ms(), start)/1000
    counter += 1
    logging.info(counter)
    if counter % 60 == 0:
        try:
            logging.info(f"alive {delta}")
            print(counter)
            return
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
                logging.info("waiting for connection...")
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
            logging.info("connected")
            self.status = self.wlan.ifconfig()
            self.router = self.status[3]
            for x in range(len(self.status)):
                logging.info("ip = " + self.status[x])
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
            self.timer = Timer(period=1000, mode=Timer.PERIODIC, callback=lambda t:alive)
            logging.info('timer created')
        
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
        logging.debug(str(self.data) +'-'+str(self.address))
        if self.data:
            t = struct.unpack("!12I", self.data)[10]
            t -= REF_TIME_1970
        logging.debug(t)
        return t

    def init_rtc(self):
        global rtc
        t = self.request_time()
        d = time.localtime(t)
        logging.debug(d)
        tup = (d[0],d[1],d[2],d[6],d[3]+1, d[4], d[5], d[7])
        rtc.datetime(tup)
        logging.info(f"UTC:{d[3]}:{d[4]}:{d[5]} {d[2]}-{d[1]}-{d[0]}; 'day of week':{d[6]}; 'day of year':{d[7]}")

    def disconnect(self):
        self.wlan.active(False)
        self.wlan.disconnect()
        led_off()



if __name__ == "__main__":
    try:
        logging.setLevel(logging.INFO)
        HEARTBEAT =  False
        wlan = Wifi(SSID, PASSWORD)
        d = time.localtime()
        print(f"{d[3]}:{d[4]}:{d[5]} {d[2]}-{d[1]}-{d[0]} weekday {d[6]} yearday {d[7]}")
        #wlan.create_heartbeat()
        while True:
            print('main alive')
            time.sleep(10)
    except KeyboardInterrupt:
        print('KeyboardInterrupt')
       # wlan.stop_heartbeat()
        wlan.disconnect()
        sys.exit(1)
    except Exception as ex:
        logging.error('exception ' + str(ex))
    finally :
        wlan.disconnect()
        sys.exit(0)
