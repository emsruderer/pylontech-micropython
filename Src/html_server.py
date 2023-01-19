from machine import UART, Pin
from machine import RTC
import time
import _thread
import network
import socket
import rp2
import sys
import struct
import ubinascii
from wlan import Wifi
from wlan import reset

#from pylontech_base import PylontechRS485
#from pylontech_decode import PylontechDecode
#from pylontech_encode import PylontechEncode
import menu

DEBUG = False
VERBOSE = False

ssid = "SSID"
password = "PASSWORD"

wlan = Wifi(ssid,password)
#rtc = wlan.get_rtc()
#print(rtc.datetime())

def print_dict(d : Dict):
    for key in d:
        print(key,':',d[key])
    print('-----------------------------------')

def make_cell(data):
    return f"<td>{data}</td>"

def make_head(data):
    return "<th>"+data+"</th>"

def make_header(content):#
    row ="<tr>"
    for head_content in content:
        row = row + make_head(head_content)
    return row + "</tr>"   

def make_row(content):#
    row ="<tr>"
    for cell_content in content:
        row = row + make_cell(cell_content)
    return row + "</tr>"   

def make_table(head,table):
    content =  "<table>" + make_header(head)
    for row in table:
       content = content + make_row(row)
    return content + "</table>"

def make_select(options,selected):
    select = '<select id="commands" name="commandlist" form="commandform">'
    for option in options:
        if option == selected:
            select += f'<option selected="selected" value="{option}">{option}</option>'
        else:
            select += f'<option value={option}>{option}</option>'
    return select + '</select>'

def make_html(data, command):
    head = ['Key                       ','Value                     ']
    table = []
    if data and len(data) > 0:
        for key in data:
            table.append([key,data[key]])
            if VERBOSE: print(key,data[key])
    html_b= """<!DOCTYPE html>
    <html>
        <head><title>Pylontech Accus</title>
        <style>
        table, th, td { border: 1px solid; text-align:center;}
        table { border-collapse: collapse; width:50%; }
        </style>
        <meta http-equiv="refresh" content="60"></head>
        <body><h1>Pylontech State</h1>"""    
    html_f = '<form action="/" id="commandform" method="get">'\
             '<label for="commands">Choose a command:</label>'\
             '<input type="submit"></form>'
           
    html_s = make_select(menu.CID,command)
  
    html_t = make_table(head,table)
    
    html_e = "</body></html>"

    return html_b + html_f + html_s + html_t + html_e

try:
    # Open socket
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]

    s = socket.socket()
    s.bind(addr)

    s.listen(1)
except:
    print("socket exception")
    machine.reset()
    s.close()
    sys.exit(1)


# Listen for connections
command = 'analog1'
while True:
    try:
        if VERBOSE: print("listening on", addr)
        cl, addr = s.accept()
        cl_file = cl.makefile("rwb", 0)
        if VERBOSE: print("\r\nclient connected from", addr)
        line = cl_file.readline()
        if VERBOSE: print(line)
        if line.startswith(b'GET') and b'?' in line:
            str1 = str(line,'utf-8')
            tup = str1.split('?')
            str_c = tup[1].split(' ')
            com_2 = str_c[0].split('=')
            if com_2[0] == 'commandlist':
                command = com_2[1]
                if VERBOSE: print(f'{com_2[0]}={command}', type(command))
        while True:
            line = cl_file.readline()
            if VERBOSE: print(f"readline={line}")
            if not line or line == b"\r\n":
                break
        result_dict = menu.process_command(command)
        data_dict = menu.strip_header(result_dict)
        response = make_html(data_dict,command) 
        if VERBOSE : print(response)
        cl.send("HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n")
        cl.send(response)
        #cl.close()
    except KeyboardInterrupt:  # OSError as e:
        STOP = True
        # cl.close()
        s.close()
        wlan.disconnect()
        #sys.exit(1)
        reset()
    finally:
        cl.close()
        if VERBOSE: print("connection closed")
