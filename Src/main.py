import time
import network
import socket
from machine import UART, Pin
from machine import RTC
from wlan import Wifi
from wlan import reset
import menu

DEBUG = False
VERBOSE = False

#ssid = "LS22Box"
#password = "00829806627728286690"

wlan = Wifi()
#rtc = wlan.get_rtc()
#print(rtc.datetime())137

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

def make_command_select(options,selected):
    select = '<select id="commands" name="command" form="choiceform">'
    for option in options:
        if option == selected:
            select += f'<option selected="selected" value="{option}">{option}</option>'
        else:
            select += f'<option value={option}>{option}</option>'
    return select + '</select>'

def make_battery_select(modules,selected):
    select = '<select id="commands" name="battery" form="choiceform">'
    select_str = str(selected+1)
    for module in range(modules):
        option = str(module+1)
        if option == select_str:
            select += f'<option selected="selected" value="{option}">{option}</option>'
        else:
            select += f'<option value={option}>{option}</option>'
    return select + '</select>'

def make_html(data, command, battery):
    head = ['Parameter','Value']
    table = []
    if data and len(data) > 0:
        for key in data:
            table.append([key,data[key]])
            if DEBUG: print(key,data[key])
    html_b= """<!DOCTYPE html>
    <html>
        <head><title>Pylontech Modules</title>
        <style>
        table, th, td { border: 1px solid; text-align:left;}
        table { border-collapse: collapse; width:50%; }
        table td:nth-child(2) { text-align: end; }
        </style>
        <meta http-equiv="refresh" content="15"></head>
        <body><h1>Pylontech Module State</h1>"""    
    html_form = '<form action="/" id="choiceform" method="get">'\
             '<label>Choose a command and battery:</label>'\
             '<input type="submit" value="Request"></form>'
           
    html_com = make_command_select(menu.CID,command)
    html_bat = make_battery_select(menu.pylon_stack.get_module_count(),battery)
  
    html_table = make_table(head,table)
    
    html_e = "</body></html>"

    return html_b + html_form + html_com + html_bat + html_table + html_e

try:
    # Open socket
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]

    s = socket.socket()
    s.bind(addr)

    s.listen(1)
except:
    print("socket exception")
    s.close()
    #sys.exit(1)
    machine.reset()


# Listen for connections
STOP = False
command = 'status'
battery = 1
command_dict = {}
wlan.create_timer()
while not STOP:
    try:
        if VERBOSE: print("listening on", addr)
        cl, addr_cl = s.accept()
        cl_file = cl.makefile("rwb", 0)
        if VERBOSE: print("\r\nclient connected from", addr_cl)
        line = cl_file.readline()
        #if VERBOSE: print(line)
        if line.startswith(b'GET') and b'?' in line:
            str1 = str(line,'utf-8')
            result = str1.split()[1].split('?')
            if len(result) > 1:
                requests = result[1].split('&')
                for el in requests:
                    spl = (el.split('='))
                    if DEBUG: print(spl, len(spl))
                    command_dict[spl[0]] = spl[1]
                    if 'command' in command_dict:
                        command = command_dict['command']
                    if 'battery' in command_dict:
                        battery = int(command_dict['battery'])-1
            if VERBOSE:
                print(f'command={command}&battery={battery}',type(command),type(battery))
        while True:
            line = cl_file.readline()
            if DEBUG: print(f"readline={line}")
            if not line or line == b"\r\n":
                break
        result_dict = menu.process_command(command, battery)
        #data_dict = menu.strip_header(result_dict)
        response = make_html(result_dict,command, battery) 
        #if VERBOSE : print(response)
        cl.send("HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n")
        cl.send(response)
    except OSError as e:
        print('OSError')
        cl.close()
        print('connection closed')
    except KeyboardInterrupt:
        print("Keyboard Interrupt")
        STOP = True
        s.close()
        wlan.deinit_timer()
        wlan.disconnect()
        #sys.exit(1)
        reset()
    finally:
        cl.close()
        if VERBOSE: print("connection closed")