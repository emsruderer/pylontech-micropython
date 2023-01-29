# PylontechRS485 handles send & receive and Prefix/suffix/checksum and timeout handling.
import time
import machine
from pylontech_base import PylontechRS485
from pylontech_decode import PylontechDecode
from pylontech_encode import PylontechEncode

DEBUG = False
VERBOSE = False

def print_dict(d : Dict):
    for key, value  in d.items():
        print(key,':', value)
    print('-----------------------------------')

CID = ['protocol',
       'manufactory',
       'analog',
       'alarm',
       'charging',
       'serialnumber',
       'systemparameter',
       'status',
       'reboot',
       'undefined']

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
    
    def get_module_count(self):
        return self.battcount

    def poll_serial_number(self, batt, retries=2):
        retryCount = 0
        packet_data = self.encode.getSerialNumber(battNumber=batt, group=self.group)
        self.pylon.send(packet_data)
        raws = self.pylon.receive(20000)  # serial number should provide a fast answer.
        if raws is not None:
            self.decode.decode_header(raws)
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
        analogList = []
        chargeDischargeManagementList = []
        alarmInfoList = []
        systemParameterList = []
        
        totalCapacity = 0
        remainCapacity = 0
        totalCurrent = 0
        power = 0
        minimum_cell_voltage = 4.0
        maximum_cell_voltage = 2.0
        minimum_temperature = 60.0
        maximum_temperature = -10.0
        for batt in range(0, self.battcount):
            try:
                self.pylon.send(self.encode.getAnalogValue(battNumber=batt, group=self.group))
                raws = self.pylon.receive()
                self.decode.decode_header(raws)
                decoded = self.decode.decodeAnalogValue()
                strip_header(decoded)
                analogList.append(decoded)

                cellVoltageList = decoded['CellVoltages']
                for voltage in cellVoltageList:
                    if voltage > maximum_cell_voltage:
                        maximum_cell_voltage = voltage
                    elif voltage < minimum_cell_voltage:
                        minimum_cell_voltage= voltage

                temperaturesList = decoded['Temperatures']
                for temperature in temperaturesList:
                    if temperature > maximum_temperature:
                        maximum_temperature = temperature
                    elif temperature < minimum_temperature:
                        minimum_temperature = temperature
                
                remainCapacity = remainCapacity + decoded['RemainingCapacity']
                totalCapacity = totalCapacity + decoded['ModuleCapacity']
                totalCurrent = totalCurrent + decoded['Current']
                power = power + (decoded['Voltage'] * decoded['Current'])
                #print('charging') 
                self.pylon.send(self.encode.getChargeDischargeManagement(battNumber=batt, group=self.group))
                raws = self.pylon.receive()
                self.decode.decode_header(raws)
                decoded = self.decode.decodeChargeDischargeManagementInfo()
                strip_header(decoded)
                chargeDischargeManagementList.append(decoded)
                #print('AlarmInfo')
                self.pylon.send(self.encode.getAlarmInfo())
                raws = self.pylon.receive()
                self.decode.decode_header(raws)
                decoded = self.decode.decodeAlarmInfo()
                strip_header(decoded)
                alarmInfoList.append(decoded)

                self.pylon.send(self.encode.getSystemParameter())
                raws = self.pylon.receive()
                self.decode.decode_header(raws)
                decoded = self.decode.decodeSystemParameter()
                strip_header(decoded)
                systemParameterList.append(decoded)
            except ValueError as e:
                print("Exception('Pylontech Value Error')"+str(e))
            except Exception as e:
                #self.pylon.reconnect()
                print("Exception('Pylontech Update Error')")

        self.pylonData['AnalogList'] = analogList
        self.pylonData['ChargeDischargeManagementList'] = chargeDischargeManagementList
        self.pylonData['AlarmInfoList'] = alarmInfoList
        self.pylonData['SystemParameterList']= systemParameterList
         
        self.pylonData['Calculated']['TotalCapacity_Ah'] = round(totalCapacity,1)
        self.pylonData['Calculated']['Capacity_kWh'] = round(50 * totalCapacity/1000,3)
        self.pylonData['Calculated']['RemainingCapacity_Ah'] = round(remainCapacity,1)
        self.pylonData['Calculated']['RemainingEnergy_kWh'] = round(50 * remainCapacity /1000, 3)
        if totalCapacity > 0:
            self.pylonData['Calculated']['Remaining_%'] = round((remainCapacity / totalCapacity) * 100, 1)
        else:
            self.pylonData['Calculated']['Remaining_%'] = 0
        self.pylonData['Calculated']['Current_Amp'] = round(totalCurrent,1)
        self.pylonData['Calculated']['Charging_Watt'] = round(power, 1)
        self.pylonData['Calculated']['MinimumCellVoltage'] = round(minimum_cell_voltage,2)
        self.pylonData['Calculated']['MaximumCellVoltage'] = round(maximum_cell_voltage,2)
        self.pylonData['Calculated']['MinimumTemperature'] = round(minimum_temperature,1)
        self.pylonData['Calculated']['MaximumTemperature'] = round(maximum_temperature,1)
        if VERBOSE : print("end update: ", time.time()-starttime)
        return self.pylonData

pylon = PylontechRS485(0, baud=115200)
e = PylontechEncode()
d = PylontechDecode()
pylon_stack = PylontechStack(pylon,e,d, manualBattcountLimit=3, group=0)

def process_command(key, batt=0):
        if key == 'protocol':
            pylon.send(e.getProtocolVersion())
            raws = pylon.receive()
            if raws:
                d.decode_header(raws)
                decoded_p = d.decodePotocolVersion()
                return strip_header(decoded_p)
            else:
                return None
        elif key == 'manufactory':
           pylon.send(e.getManufacturerInfo())
           raws = pylon.receive()
           if raws:
               d.decode_header(raws)
               decoded_m = d.decodeManufacturerInfo()
               return strip_header(decoded_m)
           else:
                return None
        elif key == 'alarm':
           pylon.send(e.getAlarmInfo(batt))
           raws = pylon.receive()
           if raws:
                d.decode_header(raws)
                return strip_header(d.decodeAlarmInfo())
           else:
                return None
        elif key == 'charging':
            pylon.send(e.getChargeDischargeManagement(batt))
            raws = pylon.receive()
            if raws:
                d.decode_header(raws)
                return strip_header(d.decodeChargeDischargeManagementInfo())
            else:
                return None
        elif key == 'analog':
            pylon.send(e.getAnalogValue(batt))
            raws = pylon.receive()
            if raws:
                d.decode_header(raws)
                return strip_header(d.decodeAnalogValue())
            else:
                return None
        elif key == 'serialnumber':
            pylon.send(e.getSerialNumber(batt))
            raws = pylon.receive()
            if raws:
                d.decode_header(raws)
                return strip_header(d.decodeSerialNumber())
            else:
                return None
        elif key == 'systemparameter':
            pylon.send(e.getSystemParameter())
            raws = pylon.receive()
            if raws:
                d.decode_header(raws)
                return strip_header(d.decodeSystemParameter())
            else:
                return None
        elif key == 'status' :
            stackResult = pylon_stack.update()
            if DEBUG :
                results = list(stackResult)
                for it in results :
                    print('\n\r', it, '\n\r')
                    if it == 'Calculated' or it == 'SystemParameter' or it == 'SerialNumbers':
                        print_dict(stackResult['Calculated'])
                    else:
                        print_dict(stackResult[it][0])
            return stackResult['Calculated']
        elif key == 'reboot':
            print('rebooting')
            machine.soft_reset()
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
        key = CID[int(command[0])]
        if len(command) == 2:
            bat = int(command[1])-1
        else:
            bat = 0
        print(f'\r\nCommand {key}, battery: {bat}')
        data = process_command(key , bat )
        print_dict(data)
