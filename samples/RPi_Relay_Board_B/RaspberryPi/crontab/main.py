#!/usr/bin/python
# -*- coding:UTF:8 -*-
import RPi.GPIO as GPIO

Relay_Pin = [5, 6, 13, 16, 19, 20, 21, 26]
Relay_status = [0, 0, 0, 0, 0, 0, 0, 0, 0]

dir = "/home/pi/RPi_Relay_Board_B/crontab/Relay_status.txt"

fd = open(dir, "r")

for i in range(8):
    fd.seek(7,1)
    Relay_status[i] = int(fd.read(1))
    fd.seek(1,1)

fd.close()

Relay_value = 0

#GPIO init
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

for i in range(8):   
    GPIO.setup(Relay_Pin[i], GPIO.OUT)
    GPIO.output(Relay_Pin[i], Relay_status[i])
    Relay_value = Relay_value| (Relay_status[i]<<i)

print Relay_value
if Relay_status[7] == 1:
    Relay_value = Relay_value << 1 
else:
    Relay_value = (Relay_value << 1) + 1
print Relay_value
for i in range(8):
    Relay_status[i] = (Relay_value >> i) & 0x01
    GPIO.output(Relay_Pin[i], Relay_status[i])

fd = open(dir, "r+")

for i in range(8):
    fd.seek(7,1)
    fd.write(str(Relay_status[i]))
    fd.seek(1,1)

fd.close()

