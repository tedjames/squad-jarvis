#!/usr/bin/python
 # -*- coding: utf-8 -*-
# Squad Mortar Calculator-Script
# by /u/Maggiefix | [GER] Maggiefix
# with ideas and code from: XXPX1
########################################
# Packages                             #
########################################
import math
import os
import sounddevice as sd
import scipy.io.wavfile as wav
import numpy as np
from datetime import datetime
import time
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
########################################
# Constantes                           #
########################################
# Letters for X-axis
letter_list = ["No", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
# Numbers for Y-axis
number_list = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]
# Distances from mortar interface
DISTANCES = (50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 950, 1000, 1050, 1100, 1150,1200, 1250)
# Milliradians from mortar interface
MILS = (1579, 1558, 1538, 1517, 1496, 1475, 1453, 1431, 1409, 1387, 1364, 1341, 1317, 1292, 1267, 1240, 1212, 1183, 1152, 1118,1081, 1039, 988, 918, 800)
# Map scale
GRID_SIZE = 300
DELIMITER = "K"
description_1   = " Big-Grid-Scale  : "
description_2   = " Mortar Position : "
description_3   = " Target Position : "
# Add these constants
SAMPLE_RATE = 44100
CHANNELS = 1
RECORDING_DURATION = 5
########################################
# Functions                            #
########################################
clear = lambda: os.system('cls')
def return_input_from_string(u_input, description):
    keypad_list = []
    # control the user inputs
    try:
        # Read x-axis
        x_value = u_input[0]

        # Read remaining string split by K
        zerlegt = list(map(int,u_input[1:].split(DELIMITER)))
        # Read y-axis
        y_value = int(zerlegt.pop(0))

        # Checks if inputs are valid
        # Checkl a-value
        if x_value not in letter_list:

            raise
        # Check y-value
        if y_value not in number_list:

            raise
        # Check keypad values
        for item in zerlegt:

            if int(item) > 9 or int(item) < 0:
               raise
            else:
                keypad_list.append(item)
        return x_value, y_value, keypad_list, u_input
    except:
        print(" Wrong input, use A1K1 or A10K9 or A1K1K5!")
        u_input = str(input(description)).upper()
        return return_input_from_string(u_input,description)
def convert_input_to_coordiantes(input_tuple):
  # Unpack input_tuple
  x,y,keypad_list,string_input = input_tuple

  x = int(ord(x.lower())-ord("a"))*GRID_SIZE
  y = (y-1) * GRID_SIZE

  # If no keypad is given
  if not keypad_list:
    x += GRID_SIZE / 2;
    y += GRID_SIZE / 2;

  # Get Keypad offsets
  else:
    keypadSize = GRID_SIZE
    for element in keypad_list:
      keypadSize /= 3 # Shrink keypad size by factor of 3
      keypad = int(element)

      # Add X Component of (Sub)Keypad\
      if keypad == 2 or keypad == 5 or keypad == 8:
        x += keypadSize
      elif keypad == 3 or keypad == 6 or keypad == 9:
        x += 2*keypadSize

      # Add Y Component of (Sub)Keypad
      if keypad == 4 or keypad == 5 or keypad == 6:
        y += keypadSize
      elif keypad == 1 or keypad == 2 or keypad == 3:
        y += 2*keypadSize

    # Center point in (Sub)Keypad
    x += keypadSize / 2
    y += keypadSize / 2

  #print stringInput + " (" + str(int(round(x))) + ", " + str(int(round(y))) + ")"
  return (x,y);
def get_vektor(x1,y1,x2,y2):
    #Verbindungsvektor berechnen
    x_bind_vek = x1 - x2
    y_bind_vek = y1 - y2
    #Länge des Verktors berechnen
    distance = math.sqrt(x_bind_vek**2 + y_bind_vek**2)
    return distance
def get_angle(x1,y1,x2,y2):
    #Build north vektor on arty-position
    nv_x = x1 - x1
    nv_y = (y1-1) - y1
    abs_nv = math.sqrt((nv_x ** 2) + (nv_y ** 2))
    #Build Targetvektor
    tv_x = x2 - x1
    tv_y = y2 - y1
    abs_tv = math.sqrt((tv_x ** 2) + (tv_y ** 2))
    #Skalar between nv and tv
    skalar = nv_x * tv_x + nv_y * tv_y

    if x1 != x2 or y1 !=y2:
        angle = math.degrees(math.acos(skalar/(abs_nv*abs_tv)))
    # Shoot NE - QI
    if x2 > x1 and y2 < y1:
        angle = angle
        #print("q1")
    # Shoot NW - QII
    elif x2 < x1 and y2 < y1:
        angle = 360 - angle
        #print("q2")
    # Shoot SW - QIII
    elif x2 < x1 and y2 > y1:
        angle = 360 - angle
        #print("q3")
    # Shoot SE - QIV
    elif x2 > x1 and y2 > y1:
        angle = angle
        #print("q4")
    # Schoot direct North
    elif x2 == x1 and y2 < y1:
        angle = 0
    # Schoot direct South
    elif x2 == x1 and y2 > y1:
        angle = 180
    # Schoot direct East
    elif x2 > x1 and y2 == y1:
        angle = 90
    # Schoot direct West
    elif x2 < x1 and y2 == y1:
        angle = 270
    # Fail
    else:
        angle = 666
    return angle
def calcElevation(distance):
    # by XXPX1
    if distance < DISTANCES[0]:
        return "Out of Range (<" + str(DISTANCES[0]) + "m)"
    elif distance > DISTANCES[-1]:
        return "Out of Range (>" + str(DISTANCES[-1]) + "m)"
    else:
        for i, value in enumerate(DISTANCES):
            # print str(i) + "\t" + str(value) + "\t" + str(MILS[i])
            if distance == value:
                return str(MILS[i])
            elif distance < value:
                m = (MILS[i] - MILS[i - 1]) / (DISTANCES[i] - DISTANCES[i - 1]);
                return str(int(m * (distance - DISTANCES[i]) + MILS[i]))


def record_audio():
    print("\nRecording for 5 seconds...")
    try:
        recording = sd.rec(
            int(RECORDING_DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.float32
        )
        sd.wait()
        return recording
    except Exception as e:
        print(f"\nError recording audio: {str(e)}")
        print("Please check your microphone settings and permissions.")
        time.sleep(2)
        return None

def save_recording(recording):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recording_{timestamp}.wav"
    wav.write(filename, SAMPLE_RATE, recording)
    return filename

def transcribe_audio(audio_file):
    # Load environment variables
    load_dotenv()

    # OpenAI client will automatically use OPENAI_API_KEY from environment
    client = OpenAI()
    
    with open(audio_file, "rb") as file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=file,
            response_format="text"
        )
    return transcription

def transcribe_and_parse_audio(audio_file):
    # Define a Pydantic model for the response
    class VoiceCommand(BaseModel):
        intent: str
        coordinates: str | None

    # Load environment variables
    load_dotenv()
    client = OpenAI()
    
    # First transcribe the audio
    with open(audio_file, "rb") as file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=file,
            response_format="text"
        )
    
    # Then parse the transcription for intent
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "system", 
                "content": """Extract the user's intent from their voice command for a mortar calculator.
                If they are trying to set up a mortar position, classify as "setup_mortars".
                If they are calling in coordinates for a fire mission, classify as "fire_mission".
                Extract any grid coordinates mentioned (e.g. "A1K5K4K2").
                So if the user says "New fire mission at foxtrot 5, 7, 2, 1", the coordinates should be "F5K7K2K1".
                """
            },
            {"role": "user", "content": transcription}
        ],
        response_format=VoiceCommand
    )
    
    return completion.choices[0].message.parsed, transcription

def handle_voice_command():
    clear()
    recording = record_audio()
    if recording is None:
        return None, None
        
    audio_file = save_recording(recording)
    print("\nTranscribing...")
    parsed_command, transcription = transcribe_and_parse_audio(audio_file)
    print(f"\nTranscribed text: {transcription}")
    print(f"Detected intent: {parsed_command.intent}")
    
    if parsed_command.coordinates:
        print(f"Detected coordinates: {parsed_command.coordinates}")
        coordinates_input = parsed_command.coordinates.strip().upper()
        
        if parsed_command.intent == "setup_mortars":
            return return_input_from_string(coordinates_input, description_2)
        elif parsed_command.intent == "fire_mission":
            return return_input_from_string(coordinates_input, description_3)
    
    time.sleep(2)
    return None

def target_loop():
    input_arty = None
    input_target = None
    
    while True:
        clear()
        print("###########################################")
        print("#              Command Menu              #")
        print("###########################################")
        print("-> S: Setup New Mortar Position")
        print("-> D: New Fire Mission")
        print("-> F: Record Voice Command")
        print("-> Q: Quit")
        print("###########################################")
        
        # Show current positions if they exist
        if input_arty:
            print(f"\nCurrent Mortar Position: {input_arty[-1].replace(' ', '')}")
        if input_target:
            print(f"Current Target Position: {input_target[-1].replace(' ', '')}")
        
        # If both positions are set, show calculations
        if input_arty and input_target:
            x1, y1 = convert_input_to_coordiantes(input_arty)
            x2, y2 = convert_input_to_coordiantes(input_target)
            angle = round(get_angle(x1, y1, x2, y2), 1)
            distance = int(get_vektor(x1, y1, x2, y2))
            click = calcElevation(distance)
            
            print("\n###########################################")
            print(f"         Distance  = {distance} m")
            print(f"         Azimuth   = {angle} °")
            print(f"         Elevation = {click} mil")
            print("###########################################")
        
        command = input("\nEnter command - S (Setup) / D (New Target) / F (Voice Command) / Q (Quit): ").lower()
        
        if command == 's':
            input_arty = return_input_from_string(input(description_2).upper(), description_2)
        elif command == 'd':
            if not input_arty:
                print("\nPlease set mortar position first!")
                time.sleep(2)
                continue
            input_target = return_input_from_string(input(description_3).upper(), description_3)
        elif command == 'f':
            result = handle_voice_command()
            if result:
                if result[0] in letter_list:  # Valid coordinate input received
                    if input_arty is None:
                        input_arty = result
                        print("\nMortar position set!")
                    else:
                        input_target = result
                        print("\nTarget position set!")
                    time.sleep(2)
        elif command == 'q':
            print("Exiting...")
            return

########################################
# Inputs                               #
########################################
# User console-inputs
print("####################################################")
print("#             Squad AI Mortar Calculator           #")
print("#                 by Miyamoto                    #")
print("####################################################")
print("# Input upper or lowercase like: A8K1 or c10k1k9   #")
print("# Subset keypads with KX (X = 1 to 9) at the end.  #")
print("# Infinite subset possible like A1K2K5K7K9K8       #")
print("# You do not have to subset, A1K7 is totally fine! #")
print("####################################################")
target_loop()

