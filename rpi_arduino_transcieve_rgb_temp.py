import os
import sys
import time
import spidev
import textwrap
import datetime
import threading
import RPi.GPIO as GPIO
from ctypes import c_bool
from lib_nrf24 import NRF24 # https://github.com/BLavery/lib_nrf24
from contextlib import contextmanager
from colorama import Fore, Back, Style
from multiprocessing import Process, Value
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
radio.setChannel(125) # Channel possibilities: [0, 125] => [2.400, 2.525] GHz
radio.setDataRate(NRF24.BR_1MBPS)
radio.setPALevel(NRF24.PA_MAX)

radio.setAutoAck(True)
radio.enableDynamicPayloads()
radio.enableAckPayload() # Sends back 'message received'-type message

radio.openReadingPipe(1, readPipeAddr)
radio.openWritingPipe(writePipeAddr)
# radio.printDetails()

ACK_TIMEOUT = 100 # The amount of time (in ms) that should be spent waiting for an ACK from the Arduino
transceive_process = None # Child daemon process used to transceive with the Arduino
pattern_thread = None # Thread used for running multiple transceive_process calls in order to make patterns (ALPHA)
suppress_daemon_output = Value(c_bool, False) # Used as a flag for the daemon process to know when to suppress its output (e.g., when the main process isn't in the main menu)
stop_pattern_thread = None # Used for signaling the pattern_thread to stop

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
    global transceive_process, suppress_daemon_output
    # If a previous transceive process is running, terminate/join process
    if transceive_process is not None and transceive_process.is_alive():
        transceive_process.terminate()
        transceive_process.join()
    transceive_process = Process(target=transceive, args=(b0,b1,b2,b3,suppress_daemon_output,))
    transceive_process.daemon = True
    transceive_process.start()      

def transceive(b0, b1, b2, b3, suppress_output):
    ACK_rcvd = False # Flag for tracking whether or not [b0, b1, b2, b3] was confirmed as received by the Arduino
    radio.stopListening() # In case previously running transcieve process was listening
    
    # Continuously send the instruction message
    while True:
        send_message(b0, b1, b2, b3)
        ACK_rcvd = wait_for_ACK(b0, b1, b2, b3) # Wait <ACK_TIMEOUT> ms for an ACK, update the <ACK_rcvd> flag accordingly
        if ACK_rcvd: # If ACK received, then break out of the while loop
            break
        
    # Once out of the while loop, this process is done sending messages. Now it just listens for messages (in this case, temperature values).
    indefinitely_listen_for_messages(suppress_output)
            
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

def indefinitely_listen_for_messages(suppress_output):
    # Now we're indefinitely listening for temperature values from the Arduino
    # This will end only if the main program is exited, or if the user enters a new non-pattern instruction--prompting the current daemon process to be killed.
    try:
        radio.startListening()
        while True:
            while not radio.available(0):
                time.sleep(1/1000.0)
            received_message = []
            radio.read(received_message, radio.getDynamicPayloadSize())
            # Temperature is always sent in two bytes with value range [0, 1023]
            # If the received_message is two bytes, assume it's a temperature value (and therefore not a four-byte instruction ACK)
            #print(suppress_output.value)
            if len(received_message) == 2 and not suppress_output.value: # Print the message to console if output is not suppressed
                print_rcvd_temperature(received_message)
    except KeyboardInterrupt:
        print("\nCtrl+C press detected.")

def print_rcvd_temperature(rcvd_temperature_bytes):
    raw_val = int.from_bytes(rcvd_temperature_bytes, byteorder="little") - 10
    if raw_val in range(1024): # If raw_val in range [0, 1023], then it's a valid Arduino raw analog measurement value
        degC = raw_val * 0.217226044 - 61.1111111 # Convert raw value to degrees C (formula: https://forum.arduino.cc/index.php?topic=152280.0)
        degF = (degC * 9.0) / 5.0 + 32.0; # Convert degrees C to degrees F
        string_to_print = "    [Temperature received at "+style_string(str(datetime.datetime.now()), YELLOW)+(": %.1f°C (%.1f°F)]" % (degC, degF))
        print(string_to_print, end="\r", flush=True) # Prints in place instead of multiple lines (flush=True)
    else:
        print(style_string("    [Received invalid raw temperature value (Not in range [0, 1023])", RED), end="\r", flush=True)
        
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
    return switch.get(style, string) # Return string with chosen style (or original string if style wasn't recognized)
        
def print_invalid_choice():
    print("\nInvalid choice entered. Please enter an integer choice from the list. Try again.")
    
def signal_check_delay(s):
    # Function used in place of time.sleep() for pattern threads that checks whether or not we should stop
    global stop_pattern_thread
    start = time.time()
    timeout = s
    while(time.time() - start < timeout):
        if stop_pattern_thread:
            return True
    return False
    
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
            string_to_print = "\nPlease enter only integer values from 0 to 359 for "+style_string("HUE", YELLOW)
            string_to_print += " and from 0 to 100 for "+style_string("SATURATION", PINK)+" and "+style_string("VALUE (BRIGHTNESS)", CYAN)+". Try again."
            print(string_to_print)
            continue
        
    if h < 104: # h: [0, 103] => b0: [151, 254], b1: DON'T_CARE
       start_new_transceive_process(h+151, 0, s, v)
    else: # h: [104, 359] => b0: 255, b1: [0, 255]
       start_new_transceive_process(255, h-104, s, v)
    
def cycle_HSV():
    while True:
        try:
            d = int(input("\nWhat value for "+style_string("DELAY (in ms)", PINK)+" [0-255]? "))
            if d not in range(256): # [0, 255]
                raise ValueError
            v = int(input("What value for "+style_string("VALUE (BRIGHTNESS)", CYAN)+" [0-100]? "))
            if v not in range(101): # [0, 100]
                raise ValueError
            break
        except ValueError:
            string_to_print = "\nPlease enter only integer values from 0 to 255 for "+style_string("DELAY (in ms)", PINK)
            string_to_print += " and from 0 to 100 for "+style_string("VALUE (BRIGHTNESS)", CYAN)+". Try again."
            print(string_to_print)
            continue
    start_new_transceive_process(2, d, 100, v)
    
def go_gata():
    start_new_transceive_process(3, 0, 0, 0)
    
def test_color_names():
    start_new_transceive_process(4, 0, 0, 0)
    
def blink_HSV():
    start_new_transceive_process(5, 0, 0, 0)
    
def christmas_colors():
    global pattern_thread
    pattern_thread = threading.Thread(target=christmas_colors_thread)
    pattern_thread.start()

def christmas_colors_thread():
    while True:
        start_new_transceive_process(1, 255, 0, 0) # red
        if signal_check_delay(0.5):
            break
        start_new_transceive_process(1, 0, 255, 0) # green
        if signal_check_delay(0.5):
            break
        start_new_transceive_process(1, 255, 255, 255) # white
        if signal_check_delay(0.5):
            break
    
def main():
    global suppress_daemon_output, pattern_thread, stop_pattern_thread
    main_menu = """
        Choose an option:
        [0] Turn off LEDs
        [1] Set RGB values
        [2] Set HSV values
        [3] Cycle through HSV Hues
        [4] GoGata
        [5] Test color names
        [6] Blink HSV colors at 60-degree Hue intervals
        [7] Christmas Colors (ALPHA)
        Press Ctrl+C to exit.\n
        """
    while True:
        suppress_daemon_output.value = False # If we're back in the main menu, the daemon process (if it's running) should be allowed to print
        choice = input(textwrap.dedent(main_menu))
        try:
            choice = int(choice) # Will throw ValueError if it's not an int
            switch = {
                0: set_LED_off,
                1: set_LED_RGB,
                2: set_LED_HSV,
                3: cycle_HSV,
                4: go_gata,
                5: test_color_names,
                6: blink_HSV,
                7: christmas_colors,
            }
            func = switch.get(choice, print_invalid_choice) # If <choice> isn't in the menu, print invalid choice statement
            suppress_daemon_output.value = True # If a valid function is chosen, suppress daemon output until we're back in the main menu
            
            # If there's a pattern thread running, terminate it before executing the next choice (as long as the choice was valid)
            if func != print_invalid_choice and pattern_thread is not None and pattern_thread.is_alive():
                stop_pattern_thread = True
                pattern_thread.join()
                stop_pattern_thread = False
            
            func() # Run the corresponding function obtained from <switch> dictionary
        except ValueError:
            print_invalid_choice()
        
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nNow exiting.")
        # If there's a pattern thread running, terminate it
        if pattern_thread is not None and pattern_thread.is_alive():
            stop_pattern_thread = True
            pattern_thread.join()
        # If there's a transceive process is running, terminate/join process
        if transceive_process is not None and transceive_process.is_alive():
            transceive_process.terminate()
            transceive_process.join()
        exit(0)
