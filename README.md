# rpi_arduino_transcieve_rgb_temp.py

A python program that prompts the user for RGB commands to send to the Arduino using a NRF24L01+ Transceiver. This script also collects temperature data from the Arduino (temporarily commented out the print statements for the received temperature).

# arduino_rpi_transcieve_rgb_temp.ino
An Arduino program that reads and sends temperature data, waits for an RGB control signal, and parses/executes the control signal.
This program can also be used without the transceiver to control RGB LED lights (see here: https://github.com/alejandro-n-rivera/arduino_led_rgb_hsv).

# General Info

Allows for setting colors using the RGB color space ([0..255], [0..255], [0..255]) \
and the HSV (a.k.a. HSB) color space ([0..359], [0.00..1.00], [0.00..1.00])

The HSV color space is useful for controlling LED brightness (V) apart from hue (H) and saturation (S).

This program includes definitions for color names (based on my own 5V RGB LED strips, YMMV).

Features include:
- Setting LED colors based on RGB values
- Setting LED colors based on HSV values
- Displaying six main HSV colors with a 1 second delay
- Smoothly cycling through HSV hues

Below is the wiring diagram (made with [Fritzing](http://fritzing.org/)) for the Arduino - LED strip connection. \
I used three [ZVN3310A](https://www.diodes.com/assets/Datasheets/ZVN3310A.pdf) N-channel MOSFETs, however many general-purpose transistors should work. In my case, the pin arrangement (according to the ZVN3310A doc linked above) was: \
**D:** [R, G, or B on the LED strip] \
**G:** [Pin 3, 5, or 6 on the Arduino] \
**S:** GND on the Arduino

You may have to reference the documentation for the pinout of your own transistors as it may differ from mine.

My 5V LED strips are only about 1 meter in total length, so I felt safe powering them using a USB 3.1 port on my computer (plus many modern USB ports have current/voltage protection). However, using an external power supply would be your safest option to avoid damage due to too much current draw on your USB port.

![Wiring diagram](https://github.com/alejandro-n-rivera/arduino_led_rgb_hsv/blob/master/wiring_diagram.png)

Feel free to use (at your own risk), modify, and share.
