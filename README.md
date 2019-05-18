# rpi_arduino_transcieve_rgb_temp.py

A Python program (tested on a Raspberry Pi 3 Model B) that prompts the user for LED control commands to send to the Arduino using a NRF24L01+ Transceiver. Made possible with the help of [this](https://github.com/BLavery/lib_nrf24) library by BLavery. Credit goes to [BLavery](https://github.com/BLavery) for the _lib_nrf24.py_ file included in this project. The RPi Python script also collects and prints temperature data sent from the Arduino (console print-outs are somewhat iffy at the moment--make sure your console window is large enough for everything to fit on one line).

# arduino_rpi_transcieve_rgb_temp.ino
An Arduino program that waits for an LED control signal, parses/executes the control signal, and reads/sends temperature data.
This program can also be used without the transceiver to control LED light strips (see here: https://github.com/alejandro-n-rivera/arduino_led_rgb_hsv).

# General Info
For information on how to wire NRF24L01+ Transceivers to the Arduino and Raspberry Pi (and a code walkthrough), I suggest [this](https://www.youtube.com/watch?v=_68f-yp63ds) YouTube video. NOTE: I did NOT make this video, nor am I claiming that it's mine or that I have any affiliation with its creator. Credit goes to YouTube user [Alexander Baran-Harper](https://www.youtube.com/channel/UC_aQTJgfrnCb8coPbZ5cgJw).

This project allows for setting colors using the RGB color space ([0..255], [0..255], [0..255]) \
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
