import serial
import time

# Change COM3 to your Arduino port
arduino = serial.Serial("COM12",9600)

time.sleep(2)

while True:

    reply = input("Friday Reply: ")

    arduino.write((reply + "\n").encode())