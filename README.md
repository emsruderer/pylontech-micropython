# pylontech-micropython
Project to communicate to Pylontech Batteries using RS-485 serial communication
Based on the Pylontech-Python library of Tomcat42

It consist of 2 Pylontech batteries (5000 and 3000) connected with a RJ45 plug (pin6 GND, pin7 A, pin8 B) to a
Waveshare 2-Channel RS485 Module for Raspberry Pi Pico, SP3485 Transceiver, UART to RS485.
The Raspberry Pico W is programmed with a Raspberry 400 with Thonny in micropython.

The program consists of:
- pylontech_base that communicates with the UART0 of the pico via channel 0 of the RS485 module
- the pylontech_encode and _decode implement the RS485 Pylontech protocol
- menu.py is an interface for the communication and has a primitive terminal interface to test the functionality
- wlan.py connect the pico to the local network, it needs the local SSID and Password
- html_server.py is the main program to interact with the batteries with a webbrowser
 
 
Installation by copying the files to the pico:

run by starting the html_server.py or renaming it to main.py
