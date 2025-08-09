# Thesis-Alcohol-and-Drowsiness
this is a thesis project in PUP for alcohol and drowsiness for PUJ and this contains not optimized system but working (I also made the whole hardware and software of this system)

this project is used in a 24v traditional jeepney in Philippines

This projects uses the following:
- **Raspberry pi**
- **3.5 TouchScreen TFT**
- **24v Bosch relay**
- **2N2222 Transistor**
- **4N35 Octocupler**
- **MCP3008 ADC Converter**
- **2pin Tactile Switch**
- **Breadboard**
- **Jumper Wires**
- **Python**
- **Buzzer**
- **Engine Shutoff Solenoid (for diesel engine)**
- **Night Vision Camera**
- **MQ-3 Sensor**

This Project works when the system detects alcohol or drowsiness the system automatically shutoffs the engine and sends email about the information. 

## Improvements

- **Make the system detects only on startup**: to avoid closing the system during high speed run.
- **much better sensor**: upgrade to much better sensor for better accuracy.
- **GPS Module**: for realtime location.

## How to use
- power up the system and run the python file (much better if you set it up during boot)
- adjust the camera to driver seat and also the MQ-3 sensor
- setup the 24v engine shutoff solenoid to the jeepney 
- connect the relay to the transistor
- (optional) if the octocupler doesn't work then it's fine just remove it and make a common ground (raspi and jeepney ground connected to work but expect some glitch).

## Credits
Used the shape_predictor_68_face_landmarks.dat for eye detection
