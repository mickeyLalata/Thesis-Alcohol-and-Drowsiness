import spidev
import time
import math
import RPi.GPIO as GPIO
import cv2
import dlib
import threading
import queue
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from picamera2 import Picamera2
from scipy.spatial import distance
import numpy as np
import Adafruit_GPIO.SPI as SPI
import Adafruit_MCP3008
import time
import subprocess
import os

#Software SPI
CLK = 17
MISO = 5
MOSI = 6
CS = 23

#Initialize MCP
mcp = Adafruit_MCP3008.MCP3008(clk=CLK, cs=CS, miso=MISO, mosi=MOSI)

# Email credentials
smtp_server = 'smtp.gmail.com'
smtp_port = 587
email_user = '' #Input Sender Email
email_password = '' #Input 2FA Email Token
to_email = '' #Input Receiver Email

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(26, GPIO.OUT)  # Relay control
GPIO.setup(0, GPIO.OUT)   # Buzzer control
GPIO.setup(16, GPIO.OUT)  # Green Light
GPIO.setup(22, GPIO.OUT)  # Red Light
GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Reset wire

GPIO.output(26, GPIO.LOW)  # Relay initially ON
GPIO.output(16, GPIO.HIGH)  # Green Light ON
GPIO.output(22, GPIO.LOW)   # Red Light OFF
GPIO.output(0, GPIO.LOW)    # Buzzer OFF

# Constants
EYE_AR_THRESHOLD = 0.20               
EYE_CLOSED_SECONDS_WARNING = 20
EYE_CLOSED_SECONDS_SHUTDOWN = 30

# Alcohol Sensor (MQ-3 + MCP3008)
VOLTAGE_REF = 3.3
ADC_MAX = 1023
RL = 10
R0 = 60
A = 0.4
B = -1.6
AIR_20_WARNING = 0.10
AIR_35_SHUTDOWN = 0.14  

# Shared variables
frame_queue = queue.Queue(maxsize=5)
alert_queue = queue.Queue()
status = {'eyes_closed_duration': 0, 'shutdown': False, 'alert_sent': False, 'relay_locked': False, 'alcohol_alert': False}

# Initialize Picamera2
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={'size': (320,240)}))
picam2.start()

def shutdown_system():
    GPIO.setup(20, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Shutdown wire
    GPIO.wait_for_edge(20, GPIO.FALLING)
    os.system("sudo shutdown now")

def get_screen_resolution():
    result = subprocess.run(['xrandr'], stdout=subprocess.PIPE)
    for line in result.stdout.decode().split('\n'):
        if '*' in line:
            res = line.split()[0].split('x')
            return int(res[0]), int(res[1])
    return 1920, 1080

# Function to send email alerts
def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_password)
        server.sendmail(email_user, to_email, msg.as_string())
        server.quit()
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Email failed: {e}")

# Function to calculate Eye Aspect Ratio
def detect_eye(eye):
    poi_A = distance.euclidean(eye[1], eye[5])
    poi_B = distance.euclidean(eye[2], eye[4])
    poi_C = distance.euclidean(eye[0], eye[3])
    return (poi_A + poi_B) / (2 * poi_C)
    

# Function to read alcohol sensor (MCP3008)
def read_adc(channel):
    return mcp.read_adc(channel)
    
def read_adc1(channel):
    return mcp.read_adc(channel)

def adc_to_voltage(adc_value):
    return (adc_value * VOLTAGE_REF) / ADC_MAX
def estimate_alcohol_ppm(voltage):
    if voltage == 0:
        return 0
    Rs = ((VOLTAGE_REF - voltage) / voltage) * RL
    ratio = Rs / R0
    return A * (ratio ** B)
def estimate_alcohol_ppm1(voltage):
    Rs = ((VOLTAGE_REF - voltage) / voltage) * RL
    ratio = Rs / R0
    return A * (ratio ** B)

def ppm_to_air_percentage(ppm):
    MAX_AIR_PPM = 5000
    return (ppm / MAX_AIR_PPM) * 100
def ppm_to_air_percentage1(ppm):
    MAX_AIR_PPM = 5000
    return (ppm / MAX_AIR_PPM) * 100
    
def ppm_to_bac(alcohol_percent):
    return alcohol_percent * 0.25
def ppm_to_bac1(alcohol_percent1):
    return alcohol_percent1 * 0.25

# Alcohol Detection Thread
def detect_alcohol():
    while not status['shutdown']:
        adc_value = read_adc(0)
        adc_value1 = read_adc(1)
        voltage = adc_to_voltage(adc_value)
        voltage1 = adc_to_voltage(adc_value1)
        alcohol_ppm = estimate_alcohol_ppm(voltage)
        alcohol_ppm1 = estimate_alcohol_ppm(voltage1)
        alcohol_percent = ppm_to_air_percentage(alcohol_ppm)
        alcohol_percent1 = ppm_to_air_percentage(alcohol_ppm1)
        bac = ppm_to_bac(alcohol_percent)
        bac1 = ppm_to_bac(alcohol_percent1)
        
        print(f"BAC: {bac:.2f} {bac1:.2f} ppm | Air %: {alcohol_percent:.2f}% {alcohol_percent1:.2f}%")
        
        if alcohol_percent >= AIR_35_SHUTDOWN and not status['alcohol_alert']:
            print("🚨 HIGH Alcohol Level! Shutting relay & activating buzzer.")
            GPIO.output(26, GPIO.HIGH)  # Stop relay
            GPIO.output(0, GPIO.HIGH)  # Turn on buzzer
            GPIO.output(16, GPIO.LOW) # Turn off Green Light
            GPIO.output(22, GPIO.HIGH) # Turn on Red Light
            send_email("🚨 Alcohol Alert!", "High alcohol level detected! Engine shutdown.\nName: (input driver name) \nPlate No: (input plate number) \nRoute: (input route)")
            time.sleep(5)
            status['alcohol_alert'] = True
        if alcohol_percent1 >= AIR_35_SHUTDOWN and not status['alcohol_alert']:
            print("🚨 HIGH Alcohol Level! Shutting relay & activating buzzer.")
            GPIO.output(26, GPIO.HIGH)  # Stop relay
            GPIO.output(0, GPIO.HIGH)  # Turn on buzzer
            GPIO.output(16, GPIO.LOW) # Turn off Green Light
            GPIO.output(22, GPIO.HIGH) # Turn on Red Light
            send_email("🚨 Alcohol Alert!", "High alcohol level detected! Engine shutdown.")
            time.sleep(5)
            status['alcohol_alert'] = True
        if alcohol_percent >= AIR_20_WARNING and not status['alcohol_alert']:
            print("⚠️ WARNING: Alcohol Detected!")
            send_email("⚠️ Alcohol Warning", "Alcohol detected! Please check.\nName (input drive name) \nPlate No: (input plate number)\nRoute: (input route)")
        if alcohol_percent1 >= AIR_20_WARNING and not status['alcohol_alert']:
            print("⚠️ WARNING: Alcohol Detected!")
            send_email("⚠️ Alcohol Warning", "Alcohol detected! Please check.")
        time.sleep(1)

# Capture frames thread
def capture_frames():
    while not status['shutdown']:
        frame = picam2.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        if not frame_queue.full():
            frame_queue.put(frame)
# Process frames thread

def process_frames():
    face_detector = dlib.get_frontal_face_detector()
    dlib_facelandmark = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")

    #Get Screen Size and Move Window
    screen_width, screen_height = get_screen_resolution()
    window_width = screen_width // 2
    window_height = screen_height
    cv2.namedWindow("Drowsiness Detection", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Drowsiness Detection", window_width, window_height)
    cv2.moveWindow("Drowsiness Detection", screen_width // 2, 0)
    
    while not status['shutdown']:
        try:
            frame = frame_queue.get(timeout=1)
        except queue.Empty:
            continue
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_detector(gray)
        eyes_closed = False
        
        for face in faces:
            landmarks = dlib_facelandmark(gray, face)
            leftEye = [(landmarks.part(n).x, landmarks.part(n).y) for n in range(36, 42)]
            rightEye = [(landmarks.part(n).x, landmarks.part(n).y) for n in range(42, 48)]
            
            left_EAR = detect_eye(leftEye)
            right_EAR = detect_eye(rightEye)
            global ear
            ear = (left_EAR + right_EAR) / 2
        
            if ear < EYE_AR_THRESHOLD:
                eyes_closed = True
                status['eyes_closed_duration'] += 1
            else:
                status['eyes_closed_duration'] = 0
                status['alert_sent'] = False
        
        if eyes_closed:
            alert_queue.put(status['eyes_closed_duration'])
        
        
        cv2.imshow("Drowsiness Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            status['shutdown'] = True
            break
    
    cv2.destroyAllWindows()
# Handle alerts thread
def handle_alerts():
    while not status['shutdown']:
        try:
            duration = alert_queue.get(timeout=1)
        except queue.Empty:
            continue
            
        print(f"Eye Ratio: {ear:.2f}%")
                
        if status['eyes_closed_duration'] >= EYE_CLOSED_SECONDS_WARNING and not status['alert_sent']:
            print("Drowsiness detected! Buzzer activated.")
            GPIO.output(0, GPIO.HIGH)
            time.sleep(3)
            GPIO.output(0, GPIO.LOW)
            send_email("Drowsiness Alert", "Drowsiness detected!\nName (input drive name) \nPlate No: (input plate number) \nRoute: (input route)")
            status['alert_sent'] = True
        
        if status['eyes_closed_duration']>= EYE_CLOSED_SECONDS_SHUTDOWN and not status['relay_locked']:
            print("Eyes closed too long! Locking relay.")
            time.sleep(5)
            GPIO.output(26, GPIO.HIGH) # Relay Stop
            GPIO.output(16, GPIO.LOW) # Turn off Green Light
            GPIO.output(22, GPIO.HIGH) # Turn on Red Light
            send_email("Eyes closed too long!", "Locking Engine.\nName (input drive name) \nPlate No: (input plate number)\nRoute: (input route)")
            status['relay_locked'] = True
            GPIO.output(0, GPIO.HIGH)  # Keep buzzer ON
            time.sleep(3)
            GPIO.output(0, GPIO.LOW)

# Reset system thread
def reset_system():
    while not status['shutdown']:
        if GPIO.input(27) == GPIO.LOW:
            print("🔄 Reset wire detected! Reactivating system.")
            send_email("Reset Switch Activated", "Unlocking Engine.\nName (input drive name) \nPlate No: (input plate number)\nRoute: (input route)")
            GPIO.output(26, GPIO.LOW)
            GPIO.output(16, GPIO.HIGH)
            GPIO.output(22, GPIO.LOW)
            GPIO.output(0, GPIO.LOW)
            status['eyes_closed_duration'] = 0
            status['alert_sent'] = False
            status['relay_locked'] = False
            status['alcohol_alert'] = False
        time.sleep(1)

# Start threads
threads = [
    threading.Thread(target=capture_frames, daemon=True),
    threading.Thread(target=process_frames, daemon=True),
    threading.Thread(target=handle_alerts, daemon=True),
    threading.Thread(target=reset_system, daemon=True),
    threading.Thread(target=detect_alcohol, daemon=True),
    threading.Thread(target=shutdown_system, daemon=True)
]

for thread in threads:
    thread.start()

try:
    while not status['shutdown']:
        time.sleep(1)
except KeyboardInterrupt:
    status['shutdown'] = True
finally:
    GPIO.cleanup()
