import time
import spidev
import textwrap
import datetime
import RPi.GPIO as GPIO
from multiprocessing import Process
from colorama import Fore, Back, Style
from lib_nrf24 import NRF24 # https://github.com/BLavery/lib_nrf24
"""
IMPORTANT NOTE: Add "self.spidev.max_speed_hz = 4000000" after line 373 ("self.spidev.open(0, csn_pin)")
in lib_nrf24.py from the library obtained from above to get it working with newer RPis (as of May 2019)
"""

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

readPipeAddr = [0xe7, 0xe7, 0xe7, 0xe7, 0xe7]
writePipeAddr = [0xc2, 0xc2, 0xc2, 0xc2, 0xc2]

radio = NRF24(GPIO, spidev.SpiDev())
radio.begin(0, 17) # GPIO values passed in

radio.setPayloadSize(32)
radio.setChannel(76)
radio.setDataRate(NRF24.BR_1MBPS)
radio.setPALevel(NRF24.PA_MAX)

radio.setAutoAck(True)
radio.enableDynamicPayloads()
radio.enableAckPayload() # Sends back 'message received'-type message

radio.openReadingPipe(1, readPipeAddr)
radio.openWritingPipe(writePipeAddr)
# radio.printDetails()

ACK_TIMEOUT = 50 # The amount of time (in ms) that should be spent waiting for an ACK from the Arduino
transceive_process = None # Child daemon process used to transceive with the Arduino

# Convenience color name variables
OFF = 0
RED = 1
ORANGE = 2
YELLOW = 3
GREEN = 4
BLUE = 5
PURPLE = 6
CYAN = 7
PINK = 8
WHITE = 9
    
def start_new_transceive_process(b0, b1, b2, b3):
    global transceive_process
    # If a previous transceive process is running, terminate/join process
    if transceive_process is not None and transceive_process.is_alive():
        transceive_process.terminate()
        transceive_process.join()
    transceive_process = Process(target=transceive, args=(b0,b1,b2,b3,))
    transceive_process.daemon = True
    transceive_process.start()      

def transceive(b0, b1, b2, b3):
    ACK_rcvd = False # Flag for tracking whether or not [b0, b1, b2, b3] was confirmed as received by the Arduino
    radio.stopListening() # In case previously running transcieve process was listening
    
    # Continuously send the instruction message
    while True:
        send_message(b0, b1, b2, b3)
        ACK_rcvd = wait_for_ACK(b0, b1, b2, b3) # Wait <ACK_TIMEOUT> ms for an ACK, update the <ACK_rcvd> flag accordingly
        if ACK_rcvd: # If ACK received, then break out of the while loop
            break
        
    # Once out of the while loop, this process is done sending messages. Now it just listens for messages (in this case, temperature values).
    indefinitely_listen_for_messages()
            
def send_message(b0, b1, b2, b3):
    radio.write(bytes([b0, b1, b2, b3]))
    
def wait_for_ACK(b0, b1, b2, b3):
    radio.startListening()
    start = int(time.time()*1000)
    while int(time.time()*1000) - start <= ACK_TIMEOUT:
        while not radio.available(0):
            time.sleep(1/1000.0)
        received_message = []
        radio.read(received_message, radio.getDynamicPayloadSize())
        if received_message == [b0, b1, b2, b3]: # If the Arduino replies with the same instruction, it has confirmed receipt. Return True.
            radio.stopListening()
            return True
    
    # If <ACK_TIMEOUT> is reached without confirmation from the Arduino, return False.
    radio.stopListening()
    return False

def indefinitely_listen_for_messages():
    # Now we're indefinitely listening for temperature values from the Arduino
    # This will end only if the main program is exited, or if the user enters a new instruction--prompting the current daemon process to be killed.
    radio.startListening()
    while True:
        while not radio.available(0):
            time.sleep(1/1000.0)
        received_message = []
        radio.read(received_message, radio.getDynamicPayloadSize())
        # Temperature is always sent in two bytes with value range [0, 1023]
        # If the received_message is two bytes, assume it's a temperature value (and therefore not a four-byte instruction ACK)
        if len(received_message) == 2:
            print_rcvd_temperature(received_message)

def print_rcvd_temperature(rcvd_temperature_bytes):
    raw_val = int.from_bytes(rcvd_temperature_bytes, byteorder="little")
    if raw_val in range(1024): # If raw_val in range [0, 1023], then it's a valid Arduino raw analog measurement value
        degC = raw_val * 0.217226044 - 61.1111111 # Convert raw value to degrees C (formula: https://forum.arduino.cc/index.php?topic=152280.0)
        degF = (degC * 9.0) / 5.0 + 32.0; # Convert degrees C to degrees F
        #string_to_print = style_string("-"*40, WHITE)+"\n"
        #string_to_print = string_to_print+style_string("Temperature received at "+str(datetime.datetime.now())+":", RED)+"\n"
        #string_to_print = string_to_print+style_string(str(rcvd_temperature_bytes), BLUE)+"\n"
        string_to_print = "    [Temperature received at "+style_string(str(datetime.datetime.now()), YELLOW)+": %.1f°C (%.1f°F)]" % (degC, degF)
        print(string_to_print, end="\r", flush=True)
    else:
        print(style_string("    [Received invalid temperature measurement: raw value not in range [0, 1023]]", RED), end="\r", flush=True)
        
def style_string(string, style):
    """
    Available colorama formatting constants are:
        Fore: BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, RESET.
        Back: BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, RESET.
        Style: DIM, NORMAL, BRIGHT, RESET_ALL
    """
    switch = {
        RED:    Fore.RED+string+Style.RESET_ALL, 
        GREEN:  Fore.GREEN+string+Style.RESET_ALL,
        BLUE:   Fore.BLUE+string+Style.RESET_ALL,
        WHITE:  Fore.WHITE+string+Style.RESET_ALL,
        YELLOW: Fore.YELLOW+string+Style.RESET_ALL,
        PINK:   Fore.MAGENTA+string+Style.RESET_ALL,
        CYAN:   Fore.CYAN+string+Style.RESET_ALL,
    }
    return switch.get(style, string) # Return string with chosen style or original string if style wasn't recognized
        
def print_invalid_choice():
    print("Invalid choice entered. Please enter an integer choice from the list, or enter a four-byte code (separated by spaces). Try again.")
    
def set_LED_off():
    start_new_transceive_process(0, 255, 255, 255)
    
def set_LED_RGB():
    while True:
        try:
            r = int(input("\nWhat value for "+style_string("RED", RED)+"   [0-255]? "))
            if r not in range(256): # [0, 255]
                raise ValueError
            g = int(input("What value for "+style_string("GREEN", GREEN)+" [0-255]? "))
            if g not in range(256): # [0, 255]
                raise ValueError
            b = int(input("What value for "+style_string("BLUE", BLUE)+"  [0-255]? "))
            if b not in range(256): # [0, 255]
                raise ValueError
            break
        except ValueError:
            print("\nPlease enter only integer values from 0 to 255. Try again.")
            continue
    
    start_new_transceive_process(1, r, g, b)
    
def set_LED_HSV():
    while True:
        try:
            h = int(input("\nWhat value for "+style_string("HUE", YELLOW)+" [0-359]? "))
            if h not in range(360): # [0, 359]
                raise ValueError
            s = int(input("What value for "+style_string("SATURATION", PINK)+" [0-100]? "))
            if s not in range(101): # [0, 100]
                raise ValueError
            v = int(input("What value for "+style_string("VALUE (BRIGHTNESS)", CYAN)+" [0-100]? "))
            if v not in range(101): # [0, 100]
                raise ValueError
            break
        except ValueError:
            print("\nPlease enter only integer values from 0 to 359 for "+style_string("HUE", YELLOW)+" and from 0 to 100 for "+style_string("SATURATION", PINK)+" and "+style_string("VALUE (BRIGHTNESS)", CYAN)+". Try again.")
            continue
        
    if h < 104: # h: [0, 103] => b0: [151, 254], b1: DON'T_CARE
       start_new_transceive_process(h+151, 0, s, v)
    else: # h: [104, 359] => b0: 255, b1: [0, 255]
       start_new_transceive_process(255, h-104, s, v)
    
def cycle_HSV():
    start_new_transceive_process(2, 20, 100, 100)
    
def go_gata():
    start_new_transceive_process(3, 0, 0, 0)
    
def test_color_names():
    start_new_transceive_process(4, 0, 0, 0)
    
def blink_HSV():
    start_new_transceive_process(5, 0, 0, 0)
    
def main():
    while True:
        main_menu = """
        Choose an option:
        [0] Turn off LEDs
        [1] Set RGB values
        [2] Set HSV values
        [3] Cycle through HSV Hues
        [4] GoGata
        [5] Test color names
        [6] Blink HSV colors at 60-degree Hue intervals
        Or you can enter a four-byte code (separated by spaces). Press Ctrl+C to exit.\n
        """
        choice = input(textwrap.dedent(main_menu))
        try:
            choice = int(choice)
            switch = {
                0: set_LED_off,
                1: set_LED_RGB,
                2: set_LED_HSV,
                3: cycle_HSV,
                4: go_gata,
                5: test_color_names,
                6: blink_HSV,
            }
            func = switch.get(choice, print_invalid_choice)
            func()
        except ValueError:
            try:
                if len(choice.split()) == 4:
                    choice = [int(b) for b in choice.split()]
                    for b in choice:
                        if b not in range(256):
                            raise ValueError
                    start_new_transceive_process(choice[0], choice[1], choice[2], choice[3])
                else:
                    raise ValueError
            except ValueError:
                print_invalid_choice()
        
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nNow exiting.")
        exit(0)
