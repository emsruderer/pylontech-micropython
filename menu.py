# PylontechRS485 handles send & receive and Prefix/suffix/checksum and timeout handling.
import time
from pylontech_base import PylontechRS485
from pylontech_decode import PylontechDecode
from pylontech_encode import PylontechEncode

VERBOSE = False

def print_dict(d : Dict):
    for key, value  in d.items():
        print(key,':', value)
    print('-----------------------------------')

CID = ['protocol',
       'manufactory',
       'analog',
       'alarm',
       'discharge',
       'serialnumber',
       'systemparameter',
       'status',
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

class PylontechStack:
    """! Whole battery stack abstraction layer.
    This class provides an easy-to-use interface to poll all batteries and get
    a ready calculated overall status for te battery stack.
    All Data polled is attached as raw result lists as well.
    """

    def __init__(self, rs485, encode, decode, manualBattcountLimit=15, group=0):
        """! The class initializer.
        @param device  RS485 device number 0/1.
        @param baud  RS485 baud rate. Usually 9500 or 115200 for 
        @param manualBattcountLimit  Class probes for the number of batteries in stack which takes some time.
        @param group Group number if more than one battery groups are configured

        @return  An instance of the Sensor class initialized with the specified name.
        """
        self.pylon = rs485
        self.encode = encode
        self.decode = decode
        self.pylonData = {}
        self.group = group

        serialList = []
        for batt in range(0, manualBattcountLimit, 1):
            decoded = self.poll_serial_number(batt)
            if decoded == None:
                break
            serialList.append(decoded['ModuleSerialNumber'])
        self.pylonData['SerialNumbers'] = serialList
        self.battcount = len(serialList)
        print(f'batteries: {self.battcount} {serialList}')
        self.pylonData['Calculated'] = {}

    def poll_serial_number(self, batt, retries=2):
            retryCount = 0
            packet_data = self.encode.getSerialNumber(battNumber=batt, group=self.group)
            self.pylon.send(packet_data)
            raws = self.pylon.receive(100)  # serial number should provide a fast answer.
            if raws is not None:
                self.decode.decode_header(raws[0])
                try:
                    decoded = self.decode.decodeSerialNumber()
                    return decoded
                except Exception as e:
                    print("Pylontech decode exception ", e.args)
            return None
 
    def update(self):
        """! Stack polling function.
        @return  A dict with all collected Information.
        """
        starttime=time.time()
        if VERBOSE : print("start update")
        analoglList = []
        chargeDischargeManagementList = []
        alarmInfoList = []

        totalCapacity = 0
        remainCapacity = 0
        power = 0
        for batt in range(0, self.battcount):
            try:
                self.pylon.send(self.encode.getAnalogValue(battNumber=batt, group=self.group))
                raws = self.pylon.receive()
                self.decode.decode_header(raws[0])
                decoded = self.decode.decodeAnalogValue()
                strip_header(decoded)
                analoglList.append(decoded)
                remainCapacity = remainCapacity + decoded['RemainCapacity']
                totalCapacity = totalCapacity + decoded['ModuleTotalCapacity']
                power = power + (decoded['Voltage'] * decoded['Current'])

                self.pylon.send(self.encode.getChargeDischargeManagement(battNumber=batt, group=self.group))
                raws = self.pylon.receive()
                self.decode.decode_header(raws[0])
                decoded = self.decode.decodeChargeDischargeManagementInfo()
                strip_header(decoded)
                chargeDischargeManagementList.append(decoded)

                self.pylon.send(self.encode.getAlarmInfo(battNumber=batt, group=self.group))
                raws = self.pylon.receive()
                self.decode.decode_header(raws[0])
                decoded = self.decode.decodeAlarmInfo()
                strip_header(decoded)
                alarmInfoList.append(decoded)
            except Exception as e:
                self.pylon.reconnect()
                raise Exception('Pylontech update error') from e
            except ValueError as e:
                self.pylon.reconnect()
                raise Exception('Pylontech update error') from e

        self.pylonData['AnaloglList'] = analoglList
        self.pylonData['ChargeDischargeManagementList'] = chargeDischargeManagementList
        self.pylonData['AlarmInfoList'] = alarmInfoList

        try:
            self.pylon.send(self.encode.getSystemParameter())
            raws = self.pylon.receive()
            self.decode.decode_header(raws[0])
            decoded = self.decode.decodeSystemParameter()
            self.pylonData['SystemParameter'] = strip_header(decoded)
        except Exception as e:
            self.pylon.reconnect()
            raise Exception('Pylontech update error') from e
        except ValueError as e:
            self.pylon.reconnect()
            raise Exception('Pylontech update error') from e

        self.pylonData['Calculated']['TotalCapacity_Ah'] = totalCapacity
        self.pylonData['Calculated']['RemainCapacity_Ah'] = remainCapacity
        self.pylonData['Calculated']['Remain_Percent'] = round((remainCapacity / totalCapacity) * 100, 0)

        self.pylonData['Calculated']['Power_W'] = round(power, 3)
        if self.pylonData['Calculated']['Power_W'] > 0:
            self.pylonData['Calculated']['ChargePower_W'] = self.pylonData['Calculated']['Power_W']
            self.pylonData['Calculated']['DischargePower_W'] = 0
        else:
            self.pylonData['Calculated']['ChargePower_W'] = 0
            self.pylonData['Calculated']['DischargePower_W'] = -1.0 * self.pylonData['Calculated']['Power_W']
        if VERBOSE : print("end update: ", time.time()-starttime)
        return self.pylonData

pylon = PylontechRS485(0, baud=115200)
e = PylontechEncode()
d = PylontechDecode()

def process_command(key, batt=0):
        if key == 'protocol':
            pylon.send(e.getProtocolVersion())
            raws = pylon.receive()
            if raws:
                d.decode_header(raws[0])
                decoded_p = d.decodePotocolVersion()
                return strip_header(decoded_p)
            else:
                return None
        elif key == 'manufactory':
           pylon.send(e.getManufacturerInfo())
           raws = pylon.receive()
           if raws:
               d.decode_header(raws[0])
               decoded_m = d.decodeManufacturerInfo()
               return strip_header(decoded_m)
           else:
                return None
        elif key == 'alarm':
           pylon.send(e.getAlarmInfo(batt))
           raws = pylon.receive()
           if raws:
                d.decode_header(raws[0])
                return strip_header(d.decodeAlarmInfo())
           else:
                return None
        elif key == 'discharge':
            pylon.send(e.getChargeDischargeManagement(batt))
            raws = pylon.receive()
            if raws:
                d.decode_header(raws[0])
                return strip_header(d.decodeChargeDischargeManagementInfo())
            else:
                return None
        elif key == 'analog':
            pylon.send(e.getAnalogValue(batt))
            raws = pylon.receive()
            if raws:
                d.decode_header(raws[0])
                return strip_header(d.decodeAnalogValue())
            else:
                return None
        elif key == 'serialnumber':
            pylon.send(e.getSerialNumber(batt))
            raws = pylon.receive()
            if raws:
                d.decode_header(raws[0])
                return strip_header(d.decodeSerialNumber())
            else:
                return None
        elif key == 'systemparameter':
            pylon.send(e.getSystemParameter())
            raws = pylon.receive()
            if raws:
                d.decode_header(raws[0])
                return strip_header(d.decodeSystemParameter())
            else:
                return None
        elif key == 'status' :
            pylon1 = PylontechStack(pylon,e,d, manualBattcountLimit=3, group=0)
            stackResult = pylon1.update()
            if VERBOSE :
                results = list(stackResult)
                for it in results :
                    print('\n\r', it, '\n\r')
                    if it == 'Calculated' or it == 'SystemParameter' or it == 'SerialNumbers':
                        print_dict(stackResult['Calculated'])
                    else:
                        print_dict(stackResult[it][0])
            return stackResult['Calculated']
        else:
            raise RuntimeError('Invalid process command')

if __name__ == '__main__':
    STOP = False
    while not STOP:
        n= 0
        for key in CID:
            print(n,key)
            n += 1
        command_input = input("\r\n Command nummer, battery number:")
        command = command_input.split(',')
        print(command, type(command))
        key = CID[int(command[0])]
        if len(command) == 2:
            bat = int(command[1])-1
        else:
            bat = 0
        print(f'\r\nCommand {key}, battery: {bat}')
        data = process_command(key , bat )
        print_dict(data)
