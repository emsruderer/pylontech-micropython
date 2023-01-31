class PylontechDecode:
    def __init__(self):
        self.data = {}
        pass

    def on_off(self, on):
        if on:
            return 'on'
        else:
            return 'off'
        
    def yes_no(self, yes):
        if yes:
            return 'yes'
        else:
            return 'no'
        
    def twosComplement_hex(self, hexstr):
        bits = 16  # Number of bits in a hexadecimal number format
        val = int(hexstr, 16)
        if val & (1 << (bits - 1)):
            val -= 1 << bits
        return val

    def cellVoltage(self, hexstr):  # signed int
        return self.twosComplement_hex(hexstr) / 1000.0

    def alarm(self, hexstr):  # signed int
        temp = self.twosComplement_hex(hexstr)
        if temp == 0:
            return 'Ok'
        if temp == 1:
            return 'BelowLimit'
        if temp == 2:
            return 'AboveLimit'
        return 'OtherError'

    def moduleVoltage(self, hexstr):  # unsigned int
        return int(hexstr, 16) / 1000.0

    def moduleCurrent(self, hexstr):  # signed int (charge +)
        return self.twosComplement_hex(hexstr) / 10.0

    def capacity(self, hexstr):  # unsigned int
        return int(hexstr, 16) / 1000.0

    def systemParameter(self, hexstr):  # signed int
        return self.twosComplement_hex(hexstr)

    def temperature(self, hexstr):  # signed int
        temp = self.twosComplement_hex(hexstr)
        return (temp - 2731) / 10.0

    def decode_header(self, rawdata):
        header = {}
        if rawdata:
            header['VER'] = int(rawdata[0:2], 16)
            header['ADR'] = int(rawdata[2:4], 16)
            header['ID'] = int(rawdata[4:6], 16)
            header['RTN'] = int(rawdata[6:8], 16)
            header['LENGTH'] = int(rawdata[8:12], 16) & 0x0fff
            header['PAYLOAD'] = rawdata[12:12 + header['LENGTH']]
        #print('Len: ', header['LENGTH'] ,  "RTN: ", header['RTN'] )
        self.data = header
        return header

    def decodePotocolVersion(self):
        if self.data['ID'] == 0x46:
            pass  # no payload, Version info is in VER field of header
        else:
            print('wrong decoder selected')
        return self.data

    def decodeManufacturerInfo(self):
        if self.data['ID'] == 0x46:
            payload = self.data['PAYLOAD']
            #print(payload[0:20].decode("ASCII"))
            self.data['BatteryName'] = bytes.fromhex(payload[0:20].decode("ASCII")).decode("ASCII").rstrip('\x00')
            self.data['SoftwareVersion'] = int(payload[20:24], 16)
            self.data['ManufacturerName'] = bytes.fromhex(payload[24:64].decode("ASCII")).decode("ASCII").rstrip('\x00')
        else:
            print('wrong decoder selected')
        return self.data

    def decodeChargeDischargeManagementInfo(self):
        payload = self.data['PAYLOAD']
        if (self.data['ID'] == 0x46) and (len(payload) == 20):
            payload = self.data['PAYLOAD']
            self.data['CommandValue'] = int(payload[0:2], 16)
            self.data['ChargeVoltageLimit'] = self.moduleVoltage(payload[2:6])
            self.data['DischargeVoltageLimit'] = self.moduleVoltage(payload[6:10])
            self.data['MaxChargeCurrent'] = self.moduleCurrent(payload[10:14])
            self.data['MaxDischargeCurrent'] = self.moduleCurrent(payload[14:18])
            self.data['ChargeEnable'] = self.on_off(bool(int(payload[18:20], 16) & 0x80))
            self.data['DischargeEnable'] = self.on_off(bool(int(payload[18:20], 16) & 0x40))
            self.data['ChargeImmediately1'] = self.on_off(bool(int(payload[18:20], 16) & 0x20))
            self.data['ChargeImmediately2'] = self.on_off(bool(int(payload[18:20], 16) & 0x10))
            self.data['FullChargeRequired'] = self.on_off(bool(int(payload[18:20], 16) & 0x08))
        else:
            self.data['CommandValue'] = None
            self.data['ChargeVoltageLimit'] = None
            self.data['DischargeVoltageLimit'] = None
            self.data['MaxChargeCurrent'] = None
            self.data['MaxDischargeCurrent'] = None
            self.data['ChargeEnable'] = None
            self.data['DischargeEnable'] = None
            self.data['ChargeImmediately1'] = None
            self.data['ChargeImmediately2'] = None
            self.data['FullChargeRequired'] = None
            raise Exception('format error')
        return self.data

    def decodeAlarmInfo(self):
        if self.data['ID'] == 0x46:
            # No size check - variable size possible
            payload = self.data['PAYLOAD']
            i = 0
            self.data['InfoFlag'] = int(payload[i:i + 2], 16)
            i = i + 2
            self.data['CommandValue'] = int(payload[i:i + 2], 16)
            i = i + 2
            self.data['CellCount'] = int(payload[i:i + 2], 16)
            i = i + 2
            cellAlarm = []
            for c in range(0, self.data['CellCount']):
                cellAlarm.append(self.alarm(payload[i:i + 2]))
                i = i + 2
            self.data['CellAlarm'] = cellAlarm
            self.data['TemperatureCount'] = int(payload[i:i + 2], 16)
            i = i + 2
            temperatureAlarm = []
            for c in range(0, self.data['TemperatureCount']):
                temperatureAlarm.append(self.alarm(payload[i:i + 2]))
                i = i + 2
            self.data['Temperature'] = temperatureAlarm

            self.data['ChargeCurrent'] = self.alarm(payload[i:i + 2])
            i = i + 2
            self.data['ModuleVoltage'] = self.alarm(payload[i:i + 2])
            i = i + 2
            self.data['DischargeCurrent'] = self.alarm(payload[i:i + 2])
            i = i + 2
            self.data['Status1'] = int(payload[i:i + 2], 16)
            i = i + 2
            self.data['Status2'] = int(payload[i:i + 2], 16)
            i = i + 2
            self.data['Status3'] = int(payload[i:i + 2], 16)
            i = i + 2
            self.data['Status4'] = int(payload[i:i + 2], 16)
            i = i + 2
            self.data['Status5'] = int(payload[i:i + 2], 16)
            i = i + 2
        else:
            print('wrong decoder selected')
        return self.data


    def decodeSystemParameter(self):
        payload = self.data['PAYLOAD']
        if (self.data['ID'] == 0x46) and (len(payload) == 50):
            i = 2
            self.data['CellUpperVoltageLimit'] = self.cellVoltage(payload[i:i+4])
            i += 4
            self.data['CellLowVoltageLimit'] = self.cellVoltage(payload[i:i+4])
            i += 4
            self.data['CellUnderVoltageThreshold'] = self.cellVoltage(payload[i:i+4])
            i += 4
            self.data['ChargeUpperTemperatureLimit'] = self.temperature(payload[i:i+4])
            i += 4
            self.data['ChargeLowerTemperatureLimit'] = self.temperature(payload[i:i+4])
            i += 4
            self.data['ChargeCurrentLimit'] = self.moduleCurrent(payload[i:i+4])
            i += 4
            self.data['UpperVoltageLimit'] = self.moduleVoltage(payload[i:i+4])
            i += 4
            self.data['LowerVoltageLimit'] = self.moduleVoltage(payload[i:i+4])
            i += 4
            self.data['UnderVoltageLimit'] = self.moduleVoltage(payload[i:i+4])
            i += 4
            self.data['DischargeUpperTemperatureLimit'] = self.temperature(payload[i:i+4])
            i += 4
            self.data['DischargeLowerTemperatureLimit'] = self.temperature(payload[i:i+4])
            i += 4
            self.data['DischargeCurrentLimit'] = self.moduleCurrent(payload[i:i+4])
        else:
            self.data['UnitCellVoltage'] = None
            self.data['UnitCellLowVoltageThreshold'] = None
            self.data['UnitCellHighVoltageThreshold'] = None
            self.data['ChargeUpperLimitTemperature'] = None
            self.data['ChargeLowerLimitTemperature'] = None
            self.data['ChargeLowerLimitCurrent'] = None
            self.data['UpperLimitOfTotalVoltage'] = None
            self.data['LowerLimitOfTotalVoltage'] = None
            self.data['UnderVoltageOfTotalVoltage'] = None
            self.data['DischargeUpperLimitTemperature'] = None
            self.data['DischargeLowerLimitTemperature'] = None
            self.data['DischargeLowerLimitCurrent'] = None
            payload_lgt = len(payload)
            raise Exception(f"format error SystemParameter, payload length: {payload_lgt}")
        return self.data

    def decodeAnalogValue(self):
        if self.data['ID'] == 0x46:
            # No size check - variable size possible
            payload = self.data['PAYLOAD']
            i = 0
            self.data['InfoFlag'] = int(payload[i:i + 2], 16)
            i = i + 2
            self.data['CommandValue'] = int(payload[i:i + 2], 16)
            i = i + 2
            self.data['CellCount'] = int(payload[i:i + 2], 16)
            i = i + 2
            cellVoltages = []
            for c in range(0, self.data['CellCount']):
                cellVoltages.append(self.cellVoltage(payload[i:i + 4]))
                i = i + 4
            self.data['CellVoltages'] = cellVoltages
            self.data['TemperatureCount'] = int(payload[i:i + 2], 16)
            i = i + 2
            temperatures = []
            for c in range(0, self.data['TemperatureCount']):
                temperatures.append(self.temperature(payload[i:i + 4]))
                i = i + 4
            self.data['Temperatures'] = temperatures
            self.data['Current'] = self.moduleCurrent(payload[i:i + 4])
            i = i + 4
            self.data['Voltage'] = self.moduleVoltage(payload[i:i + 4])
            i = i + 4
            self.data['RemainingCapacity'] = int(payload[i:i + 4], 16) / 1000.0
            i = i + 4
            if int(payload[i:i + 2], 16) == 4:
                self.data['DetectedCapacity'] = '>65Ah'
            else:
                self.data['DetectedCapacity'] = '<=65Ah'
            i = i + 2
            self.data['ModuleCapacity'] = int(payload[i:i + 4], 16) / 1000.0
            i = i + 4
            self.data['CycleNumber'] = int(payload[i:i + 4], 16)
            i = i + 4
            if self.data['DetectedCapacity'] == '>65Ah':
                self.data['RemainingCapacity'] = self.capacity(payload[i:i + 6])
                i = i + 6
                self.data['ModuleCapacity'] = self.capacity(payload[i:i + 6])
                i = i + 6
        else:
            print('wrong decoder selected')
        return self.data

    def decodeSerialNumber(self):
        payload = self.data['PAYLOAD']
        if (self.data['ID'] == 0x46) and (len(payload) == 34):
            self.data['CommandValue'] = bytes.fromhex(payload[0:2].decode("ASCII")).decode("ASCII").rstrip('\x00')
            self.data['ModuleSerialNumber'] = bytes.fromhex(payload[2:34].decode("ASCII")).decode("ASCII").rstrip(
                '\x00')
        else:
            print('Format Error')
            self.data['ModuleSerialNumber'] = None
            self.data['CommandValue'] = None
        return self.data

if __name__ == '__main__':
    d = PylontechDecode()
    print(d.cellVoltage('0AF0'))
    pass
