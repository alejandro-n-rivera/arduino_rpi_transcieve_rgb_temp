/* GitHub: alejandro-n-rivera 
 * By default uses first three PWM (~) pins on the Arduino Uno
 * Go to Sketch > Include Library > Manage Libraries... and install RF24 by TMRh20 (can also be found at https://github.com/nRF24/RF24)

 * This program waits for an instruction (sent by a RPi as four bytes over a NRF24L01+ Transceiver), ACKs the instruction, and parses it. It uses delay time to listen for an updated instruction. 
 * At the end of each loop(), it reads in a raw value [0, 1023] from Pin A0 (in this case a 3-pin temperature sensor) and sends this value as two bytes over a NRF24L01+ Transceiver. 
 * The last LED control instruction is also stored in EEPROM[0..3] by default and restored upon power up.
 */

#include <SPI.h>
#include <RF24.h>
#include <EEPROM.h>

#define RED_PIN 3
#define GREEN_PIN 5
#define BLUE_PIN 6

// Color names supported: (e.g., setLEDColor(RED);)
#define OFF 0
#define RED 1
#define ORANGE 2
#define YELLOW 3
#define GREEN 4
#define BLUE 5
#define PURPLE 6
#define CYAN 7
#define PINK 8
#define WHITE 9

#define DEF_TIMEOUT 50 // Default radio listening timeout (in ms)
#define ACK_TIMEOUT 25 // The amount of time (in ms) that should be spent sending an ACK (i.e., the instruction that was received) back to the RPi

RF24 radio(9, 10); // (CE, CSN) on NRF24L01+ chip

unsigned long lastTempSend; // For measuring how long it's been since the temperature value was last sent
unsigned long startTime; // For measuring timeouts
uint32_t tempSensorVal; // Analog read value [0, 1023]
uint32_t firstByteAddr = 0; // EEPROM address of first instruction byte stored in memory -- initialized to 0

// Initialize <instruction> to whatever is in EEPROM[firstByteAddr..firstByteAddr+3] and <prevInstruction> to OFF (in case the EEPROM contains an invalid LED control instruction)
byte instruction[4] = {EEPROM.read(firstByteAddr), EEPROM.read(firstByteAddr+1), EEPROM.read(firstByteAddr+2), EEPROM.read(firstByteAddr+3)}; // Instruction (e.g., [MODE, X, X, X], [1, R, G, B], [H_0, H_1, S, V])
byte prevInstruction[4] = {0, 255, 255, 255}; // Previous instruction

// Red, Green, Blue ranges: R: [0, 255], G: [0, 255], B: [0, 255] (e.g., setLEDRGB(255, 125, 0);)
// Hue, Saturation, Value (Brightness) ranges: H: [0, 359], S: [0.00, 1.00], V: [0.00, 1.00] (e.g., setLEDHSV(270, 0.50, 1.00);)

void setup()
{
  // Setup the NRF24L01+ Transceiver
  radio.begin();
  radio.setPALevel(RF24_PA_MAX);
  radio.setChannel(76);
  radio.openReadingPipe(0, 0xC2C2C2C2C2);
  radio.openWritingPipe(0xE7E7E7E7E7);
  radio.enableDynamicPayloads();
  radio.powerUp();
}

void loop()
{
  // Parse the LED control instruction currently in <instruction> (on first run since powerup, this is obtained from EEPROM)
  parseInstruction();

  // Listen for a new instruction for up to <DEF_TIMEOUT> ms with the NRF24L01+ chip
  listenForInstruction(DEF_TIMEOUT); // This function is also used as a replacement for delay() for the delay time between colors for some LED animation modes (e.g., cycleHSV)

  // After listening for an instruction, read/send temperature to the RPi NRF24L01+ chip before parsing the current <instruction> on the next loop() iteration
  readAndSendTemperature();
}

void parseInstruction()
{
  // MODE: setHSV (Value: [H_0, H_1, S, V] -- H_0: [151, 255], H_1: [0, 255], S: [0, 100], V: [0, 100])
  if(instruction[0] > 150) // Then we know we want to set HSV -- this byte will serve as H_0
  {
     // For H_0 (instruction[0]): [151, 255] corresponds to [0, 104)
     // For H_1 (instruction[1]): [0, 255] corresponds to [104, 359]
    if(instruction[0] < 255) // Then we know that H value is less than 104
    {
      // [151, 254] => H: [0, 103]
      setLEDHSV(instruction[0] - 151, instruction[2]/100.0, instruction[3]/100.0);
    }
    else // Else, we know that H value is greater than or equal to 104
    {
      // [0, 255] => H: [104, 359]
      setLEDHSV(instruction[1] + 104, instruction[2]/100.0, instruction[3]/100.0);
    }
  }

  // Else, this byte serves as MODE -- 0: OFF, 1: setRGB, 2: cycleHSV, etc. up to 150
  else
  {
    switch(instruction[0])
    {
      // MODE: OFF (Value: [0, 255, 255, 255])
      case 0:
        // First check to make sure that the instruction received was [0, 255, 255, 255] -- the proper instruction for OFF
        // (The reason OFF isn't [0, 0, 0, 0] is because this is often received when the signal is weak)
        if(instruction[1] + instruction[2] + instruction[3] != 765) // If the sum isn't 255+255+255=765, then fall back to the previous instruction.
        {
          memcpy(instruction, prevInstruction, sizeof(prevInstruction)); // copy <prevInstruction> values into <instruction>
        }
        else // Else, OFF signal is correct. Set the LED color to OFF.
        {
          setLEDColor(OFF);
        }
        break;

      // MODE: setRGB (Value: [1, R, G, B] -- R: [0, 255], G: [0, 255], B: [0, 255])  
      case 1:
        setLEDRGB(instruction[1], instruction[2], instruction[3]);
        break;

      // MODE: cycleHSV (Value: [2, D, S, V] -- D: [0, 255], S: [0, 100], V: [0, 100])  
      case 2:
        cycleHSV(instruction[1], instruction[2]/100.0, instruction[3]/100.0); // Delay between each color (in ms), Saturation, and Brightness
        break;

      // MODE: goGators (Value: [3, X, X, X] -- X: DON'T_CARE)
      case 3:
        goGators();
        break;

      // MODE: testColorNames (Value: [4, X, X, X] -- X: DON'T_CARE)
      case 4:
        testColorNames();
        break;

      // MODE: blinkHSV (Value: [5, X, X, X] -- X: DON'T_CARE)
      case 5:
        blinkHSV();
        break;

      // We've received an unrecognized MODE, fall back to the previous instruction
      default:
        memcpy(instruction, prevInstruction, sizeof(prevInstruction)); // copy <prevInstruction> values into <instruction>
        break;
    }

    // After <instruction> has been parsed, if the instruction isn't the same as the previous instruction,
    // copy the <instruction> values into EEPROM and <prevInstruction> before moving on to the next instruction
    if(memcmp(instruction, prevInstruction, sizeof(instruction)) != 0)
    {
      EEPROM.write(firstByteAddr, instruction[0]);
      EEPROM.write(firstByteAddr+1, instruction[1]);
      EEPROM.write(firstByteAddr+2, instruction[2]);
      EEPROM.write(firstByteAddr+3, instruction[3]);
      memcpy(prevInstruction, instruction, sizeof(instruction)); 
    }
  }
}

bool listenForInstruction(int timeout)
{
  radio.startListening();
  startTime = millis();
  while(millis() - startTime <= timeout) // Listen until <timeout> (in ms) is reached
  {
    if(radio.available()) // A new instruction was received
    {
      radio.read(&instruction, sizeof(instruction)); // Read the received message into <instruction>

      // If we received [0, 0, 0, 0], that usually indicates a weak signal
      // Ignore this instruction and continue listening until <timeout> is reached
      if(instruction[0]+instruction[1]+instruction[2]+instruction[3] == 0)
      {
        memcpy(instruction, prevInstruction, sizeof(prevInstruction)); // copy <prevInstruction> values into <instruction>
        continue;
      }

      // Else, we received a non-zero instruction code. Stop listening and send an ACK back.
      else
      {
        radio.stopListening();
        // Acknowledge (ACK) instruction -- RPi will wait up to 50 ms (or whatever its <ACK_TIMEOUT> is set to) 
        startTime = millis();
        while(millis() - startTime <= ACK_TIMEOUT)
        {
          // We're sending the instruction that we just received back to the RPi for confirmation.
          // If the ACK is sent successfully to RPi, it won't send the same instruction again.
          // If the received instruction was incorrect (or the ACK was incorrect on the way back),
          // then the RPi will resend the instruction (or a new instruction if it has one ready)
          radio.write(&instruction, sizeof(instruction));
        }
        return true; // Return true since we have received a new instruction
      }
    }
  }
  // If the while loop <timeout> is reached, then instruction isn't updated. Stop listening and return false.
  radio.stopListening();
  return false;
}

void readAndSendTemperature()
{
  // If it's been at least 1 second since temperature data was last sent, send it (avoids sending a bunch of temp data per second if the current LED instruction has a very short loop()
  if(millis() - lastTempSend >= 1000)
  {
    tempSensorVal = analogRead(A0); // Read temperature -- always in range [0, 1023]
    radio.write(&tempSensorVal, 2); // Send temperature -- only need two bytes
    lastTempSend = millis(); // Update lastTempSend time with current time
  }

  /* The code below converts the tempSensorVal into degrees C and degrees F. I have offloaded this to the RPi instead to keep time used for this function to a minimum. */
  
//  Serial.println(tempSensorVal);
//  float degC = tempSensorVal * 0.217226044 - 61.1111111; // Convert raw voltage to degrees C (formula: https://forum.arduino.cc/index.php?topic=152280.0)
//  float degF = (degC*9.0)/5.0 + 32.0; // Convert degrees C to degrees F
//
//  // Format temperatures into strings and then format message using those strings
//  char cStr[6], fStr[6], message[100];
//  dtostrf(degC, 4, 1, cStr);
//  dtostrf(degF, 4, 1, fStr);
//  sprintf(message, "Temperature: %s°C (%s°F)", cStr, fStr);
//  Serial.println(message);
}

void setLEDRGB(byte r, byte g, byte b)
{
  analogWrite(RED_PIN, r);
  analogWrite(GREEN_PIN, g);
  analogWrite(BLUE_PIN, b);
}

void setLEDHSV(int h, float s, float v)
{
  /* Formula used (Alternative): https://en.wikipedia.org/wiki/HSL_and_HSV#HSV_to_RGB */
  
  float r, g, b;

  // Convert HSV to RGB using Alternative Wikipedia formula
  r = v - (v * s * max(min(fmod(5.0+(h/60.0), 6.0), min(4.0-(fmod(5.0+(h/60.0), 6.0)), 1.0)), 0.0));
  g = v - (v * s * max(min(fmod(3.0+(h/60.0), 6.0), min(4.0-(fmod(3.0+(h/60.0), 6.0)), 1.0)), 0.0));
  b = v - (v * s * max(min(fmod(1.0+(h/60.0), 6.0), min(4.0-(fmod(1.0+(h/60.0), 6.0)), 1.0)), 0.0));

  setLEDRGB(r * 255, g * 255, b * 255); // Multiply r, g, b, each by 255 to convert ranges from [0.00, 1.00] to [0, 255]
}

void setLEDColor(int color)
{
  // Set LED color by name (HSV versions of same color in comments)
  switch(color)
  {
    case OFF:
      setLEDRGB(0, 0, 0);
      // setLEDHSV(0, 0.00, 0.00);
      break;
    case RED:
      setLEDRGB(255, 0, 0);
      // setLEDHSV(0, 1.00, 1.00);
      break;
    case ORANGE:
      setLEDRGB(255, 25, 0);
      // setLEDHSV(6, 1.00, 1.00);
      break;
    case YELLOW:
      setLEDRGB(255, 255, 0);
      // setLEDHSV(60, 1.00, 1.00);
      break;
    case GREEN:
      setLEDRGB(0, 255, 0);
      // setLEDHSV(120, 1.00, 1.00);
      break;
    case BLUE:
      setLEDRGB(0, 0, 255);
      // setLEDHSV(240, 1.00, 1.00);
      break;
    case PURPLE:
      setLEDRGB(255, 0, 255);
      // setLEDHSV(300, 1.00, 1.00);
      break;
    case CYAN:
      setLEDRGB(0, 255, 255);
      // setLEDHSV(180, 1.00, 1.00);
      break;
    case PINK:
      setLEDRGB(255, 0, 144);
      // setLEDHSV(326, 1.00, 1.00);
      break;
    case WHITE:
      setLEDRGB(255, 255, 255);
      // setLEDHSV(0, 0.00, 1.00);
      break;
  }
}

void cycleHSV(int d, float s, float v) // d: [0, 255], s: [0.00, 1.00], v: [0.00, 1.00]
{
  // Cycle through all the Hues [0..359] at chosen Delay, Saturation, and Brightness
  for(int i = 0; i < 360; i++)
  {
    setLEDHSV(i, s, v); // Set LED Hue, Saturation, and Brightness (Value)
    if(listenForInstruction(d)) return; // If a new instruction is received while delaying, return to main loop(). (Else, continue.)
  }
}

void goGators()
{
  setLEDColor(ORANGE);
  if(listenForInstruction(1000)) return; // If a new instruction is received while delaying for 1000 ms, return to main loop(). (Else, continue.)
  setLEDColor(BLUE);
  if(listenForInstruction(1000)) return; // If a new instruction is received while delaying for 1000 ms, return to main loop(). (Else, continue.)
}

void testColorNames()
{
  byte color[10] = {RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, CYAN, PINK, WHITE, OFF};
  for(byte i = 0; i < sizeof(color); i++)
  {
    setLEDColor(color[i]);
    if(listenForInstruction(1000)) return; // If a new instruction is received while delaying for 1000 ms, return to main loop(). (Else, continue.)
  }
}

void blinkHSV()
{
  // Jumps to the six main HSV colors
  // Set Hue to: 0, 60, 120, 180, 240, 300
  for(int i = 0; i < 6; i++)
  {
    setLEDHSV(i*60, 1.00, 1.00);
    if(listenForInstruction(1000)) return; // If a new instruction is received while delaying for 1000 ms, return to main loop(). (Else, continue.)
  }
}
