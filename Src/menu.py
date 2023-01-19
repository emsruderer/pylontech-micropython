#import sys
#sys.path.insert(0, "../../")

# PylontechRS485 handles send & receive and Prefix/suffix/checksum and timeout handling.
from pylontech_base import PylontechRS485
from pylontech_decode import PylontechDecode
from pylontech_encode import PylontechEncode
from wlan import Wifi

def print_dict(d : Dict):
    for key, value  in d.items():
        print(key,':', value)
    print('-----------------------------------')

CID = ['protocol',
       'manufactory',
       'analog1',
       'analog2',
       'alarm1',
       'alarm2',
       'discharge1',
       'discharge2',
       'serialnumber1',
       'serialnumber2',
       'systemparameter',
       'unknown']

def strip_header(data):
    if data:
        del data['ID']
        del data['PAYLOAD']
        if 'CommandValue' in list(data): del data['CommandValue']
        if 'InfoFlag' in list(data): del data['InfoFlag']
        del data['RTN']
        del data['LENGTH']
        del data['VER']
        del data['ADR']
    return data

def process_command(key):
        #print(f"process={key}", type(key))
        if key == 'protocol':
            pylon.send(e.getProtocolVersion())
            raws = pylon.receive()
            d.decode_header(raws[0])
            return (d.decodePotocolVersion())
        elif key == 'manufactory':
           pylon.send(e.getManufacturerInfo())
           raws = pylon.receive()
           d.decode_header(raws[0])
           return (d.decodeManufacturerInfo())
        elif key == 'alarm1':
           pylon.send(e.getAlarmInfo(0))
           raws = pylon.receive()
           d.decode_header(raws[0])
           return (d.decodeAlarmInfo()) 
        elif key == 'alarm2':
            pylon.send(e.getAlarmInfo(1))
            raws = pylon.receive()
            d.decode_header(raws[0])
            return (d.decodeAlarmInfo()) 
        elif key == 'discharge1':
            pylon.send(e.getChargeDischargeManagement(0))
            raws = pylon.receive()
            d.decode_header(raws[0])
            return (d.decodeChargeDischargeManagementInfo()) 
        elif key == 'discharge2':
            pylon.send(e.getChargeDischargeManagement(1))
            raws = pylon.receive()
            d.decode_header(raws[0])
            return (d.decodeChargeDischargeManagementInfo()) 
        elif key == 'analog1':
            pylon.send(e.getAnalogValue(0))
            raws = pylon.receive()
            d.decode_header(raws[0])
            return (d.decodeAnalogValue()) 
        elif key == 'analog2':
            pylon.send(e.getAnalogValue(1))
            raws = pylon.receive()
            d.decode_header(raws[0])
            return (d.decodeAnalogValue())
        elif key == 'serialnumber1':
            pylon.send(e.getSerialNumber(0))
            raws = pylon.receive()
            d.decode_header(raws[0])
            return (d.decodeSerialNumber())
        elif key == 'serialnumber2':
            pylon.send(e.getSerialNumber(1))
            raws = pylon.receive()
            d.decode_header(raws[0])
            return (d.decodeSerialNumber())
        elif key == 'systemparameter':
            pylon.send(e.getSystemParameter())
            raws = pylon.receive()
            d.decode_header(raws[0])
            return (d.decodeSystemParameter())
        else:
            print('Invalid process command')
            raise RuntimeError('Invalid process command')

pylon = PylontechRS485(0, baud=115200)
e = PylontechEncode()
d = PylontechDecode()

if __name__ == '__main__':
    STOP = False
    while not STOP:
        n= 0
        for key in CID:
            print(n,key)
            n += 1
        command = int(input("\r\n Geef opdracht:"))
        key = CID[command]
        print('\r\n',key)
        data = process_command(key)
        data = strip_header(data)
        print_dict(data)
