# PylontechRS485 handles send & receive and Prefix/suffix/checksum and timeout handling.
import time
import machine
import sys
from collections import OrderedDict as Dict
from pylontech_base import PylontechRS485
from pylontech_decode import PylontechDecode
from pylontech_encode import PylontechEncode
import logging 

DEBUG = False

def print_dict(d : Dict):
    for key in d:
        print(key,':', str(d[key]))
    print('-----------------------------------')

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

class PylontechMenu:
    """! Whole battery stack abstraction layer.
    This class provides an easy-to-use interface to poll all batteries and get
    a ready calculated overall status for te battery stack.
    All Data polled is attached as raw result lists as well.
    """

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

    def __init__(self, manualBattcountLimit=15, group=0):
        """! The class initializer.
        @param device  RS485 device number 0/1.
        @param baud  RS485 baud rate. Usually 9500 or 115200 for 
        @param manualBattcountLimit  Class probes for the number of batteries in stack which takes some time.
        @param group Group number if more than one battery groups are configured

        @return  An instance of the Sensor class initialized with the specified name.
        """
        self.pylon = PylontechRS485(0, baud=115200)
        self.encode = PylontechEncode()
        self.decode =  PylontechDecode()
        self.pylonData = Dict()
        self.group = group

        serialList = []
        for batt in range(0, manualBattcountLimit, 1):
            decoded = self.poll_serial_number(batt)
            if decoded == None:
                break
            serialList.append(decoded['ModuleSerialNumber'])
        self.pylonData['SerialNumbers'] = serialList
        self.battcount = len(serialList)
        logging.info(f'batteries: {self.battcount} {serialList}')
        self.pylonData['Calculated'] = Dict()
    
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
                logging.info("Pylontech decode exception ", e.args)
        return None
 
    def update(self):
        """! Stack polling function.
        @return  A dict with all collected Information.
        """
        starttime=time.time()
        logging.debug("start update")
        analogList = []
        chargeDischargeManagementList = []
        alarmInfoList = []
        systemParameterList = []
        
        totalCapacity = 0
        remainCapacity = 0
        totalCurrent = 0
        total_power = 0
        minimum_cell_voltage = 4.0
        maximum_cell_voltage = 2.0
        minimum_temperature = 60.0
        maximum_temperature = -10.0

        module_voltage = True
        discharge_current = True
        charge_current = True
        temperature = True
        cell_alarm = True

        for batt in range(0, self.battcount):
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
            total_power = total_power + (decoded['Voltage'] * decoded['Current'])
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
            temperaturesList = decoded['Temperature']
            for temp_ok in temperaturesList:
                temperature = temperature and temp_ok
            discharge_current = discharge_current and decoded['DischargeCurrent']
            charge_current = charge_current and decoded['ChargeCurrent']
            module_voltage = module_voltage and decoded['ModuleVoltage']
            cellList = decoded['CellAlarm']
            for cell in cellList:
                cell_alarm = cell_alarm and cell
                
            self.pylon.send(self.encode.getSystemParameter())
            raws = self.pylon.receive()
            self.decode.decode_header(raws)
            decoded = self.decode.decodeSystemParameter()
            strip_header(decoded)
            systemParameterList.append(decoded)
            
        self.pylonData['AnalogList'] = analogList
        self.pylonData['ChargeDischargeManagementList'] = chargeDischargeManagementList
        self.pylonData['AlarmInfoList'] = alarmInfoList
        self.pylonData['SystemParameterList']= systemParameterList
         
        if totalCapacity > 0:
            self.pylonData['Calculated']['Remaining_%'] = round((remainCapacity / totalCapacity) * 100, 1)
        else:
            self.pylonData['Calculated']['Remaining_%'] = 0
        self.pylonData['Calculated']['RemainingEnergy_kWh'] = round(48 * remainCapacity /1000, 3)
        self.pylonData['Calculated']['Capacity_kWh'] = round(48 * totalCapacity/1000,3)
        self.pylonData['Calculated']['RemainingCapacity_Ah'] = round(remainCapacity,1)
        self.pylonData['Calculated']['TotalCapacity_Ah'] = round(totalCapacity,1)
        self.pylonData['Calculated']['Charging_Watt'] = round(total_power, 1)
        self.pylonData['Calculated']['Current_Amp'] = round(totalCurrent,1)
        self.pylonData['Calculated']['ChargeCurrent'] = charge_current
        self.pylonData['Calculated']['DischargeCurrent'] = discharge_current
        self.pylonData['Calculated']['ModuleVoltage'] = module_voltage
        self.pylonData['Calculated']['MinimumCellVoltage'] = round(minimum_cell_voltage,2)
        self.pylonData['Calculated']['MaximumCellVoltage'] = round(maximum_cell_voltage,2)
        self.pylonData['Calculated']['CellAlarm'] = cell_alarm
        self.pylonData['Calculated']['MinimumTemperature'] = round(minimum_temperature,1)
        self.pylonData['Calculated']['MaximumTemperature'] = round(maximum_temperature,1)
        self.pylonData['Calculated']['Temperature'] = temperature
        logging.debug("end update: ", time.time()-starttime)
        return self.pylonData


    def recover(self):
        n = 0
        try:
          while n < 10:
            n += 1
            self.pylon.send(self.encode.getProtocolVersion())
            raws = self.pylon.receive()
            self.pylon.send(self.encode.getProtocolVersion())
            raws = self.pylon.receive()
            break
        except:
            pass               


    def process_command(self, key, batt=0):
      """ while loop to repeat the request in case of exceptions"""
      SUCCESS = False
      while not SUCCESS:
        try:
            if key == 'protocol':
                self.pylon.send(self.encode.getProtocolVersion())
                raws =self.pylon.receive()
                if raws:
                    self.decode.decode_header(raws)
                    decoded_p = self.decode.decodePotocolVersion()
                    return strip_header(decoded_p)
                else:
                    return None
            elif key == 'manufactory':
               self.pylon.send(self.encode.getManufacturerInfo())
               raws =self.pylon.receive()
               if raws:
                   self.decode.decode_header(raws)
                   decoded_m = self.decode.decodeManufacturerInfo()
                   return strip_header(decoded_m)
               else:
                    return None
            elif key == 'alarm':
               self.pylon.send(self.encode.getAlarmInfo(batt))
               raws =self.pylon.receive()
               if raws:
                    self.decode.decode_header(raws)
                    return strip_header(self.decode.decodeAlarmInfo())
               else:
                    return None
            elif key == 'charging':
                self.pylon.send(self.encode.getChargeDischargeManagement(batt))
                raws =self.pylon.receive()
                if raws:
                    self.decode.decode_header(raws)
                    return strip_header(self.decode.decodeChargeDischargeManagementInfo())
                else:
                    return None
            elif key == 'analog':
                self.pylon.send(self.encode.getAnalogValue(batt))
                raws =self.pylon.receive()
                if raws:
                    self.decode.decode_header(raws)
                    return strip_header(self.decode.decodeAnalogValue())
                else:
                    return None
            elif key == 'serialnumber':
                self.pylon.send(self.encode.getSerialNumber(batt))
                raws =self.pylon.receive()
                if raws:
                    self.decode.decode_header(raws)
                    return strip_header(self.decode.decodeSerialNumber())
                else:
                    return None
            elif key == 'systemparameter':
                self.pylon.send(self.encode.getSystemParameter())
                raws =self.pylon.receive()
                if raws:
                    self.decode.decode_header(raws)
                    return strip_header(self.decode.decodeSystemParameter())
                else:
                    return None
            elif key == 'status' :
                stackResult = self.update()
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
                machine.soft_reset()
            else:
                logging.debug('Invalid process command')
                raise SystemExit('Invalid process command')
            SUCCESS = True
 
            """ if the battries start to give wrong answers we ask the simplest questions
                until we get correct answers again """
        except ValueError as ex:
            logging.warning('Pylontech Value Error ' + str(ex))
            self.recover()
            continue
        except KeyboardInterrupt as ex:
            sys.exit(1)
            raise SystemExit
        except Exception as ex:
            logging.warning('Pylontech Exception ' + str(ex))
            self.recover()
            continue
        except UnicodeError as ex:
            logging.warning('UnicodeError ' + str(ex))



if __name__ == '__main__':
    pylon_menu = PylontechMenu(manualBattcountLimit=3, group=0)
    STOP = False
    while not STOP:
        n= 0
        for key in pylon_menu.CID:
            print(n,key)
            n += 1
        command_input = input("\r\n Command nummer, battery number:")
        command = command_input.split(',')
        key = pylon_menu.CID[int(command[0])]
        #print(key,type(key))
        if len(command) == 2:
            bat = int(command[1])-1
        else:
            bat = 0
        print(f'\r\nCommand {key}, battery: {bat}')
        data = pylon_menu.process_command(key , bat )
        #print(data)
        print_dict(data)
