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
import pvporcupine
import struct
import threading
from queue import Queue
import keyboard
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
import torch
from scipy import signal  # For resampling
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
WAKE_WORD = "jarvis"  # Custom wake word

## Available wake words:
# grapefruit, alexa, ok google, picovoice, americano, computer, hey barista, hey siri, porcupine, hey google, blueberry, terminator, jarvis, pico clock, bumblebee, grasshopper

# Add near the top with other constants
DEBUG_MODE = False  # Toggle this to enable/disable debug output
# Add this with other constants at the top
USE_VAD = True  # Toggle this to enable/disable VAD
# Add this with other constants at the top
USE_WAKE_WORD = True  # Toggle this to enable/disable wake word detection
# Add this with other constants at the top
calculationHistory = {
    'current': {
        'distance': None,
        'angle': None,
        'click': None,
        'target': None
    },
    'previous': {
        'distance': None,
        'angle': None,
        'click': None,
        'target': None
    }
}

# Saved targets example:
# saved_targets = {
#     'target_name': {
#         'distance': None,
#         'angle': None,
#         'click': None,
#         'target': None
#     }
# }

# Add this with other constants at the top
saved_targets = {}  # Global dictionary to store saved targets

########################################
# Functions                            #
########################################
def clear():
    # For Windows
    if os.name == 'nt':
        os.system('cls')
    # For Unix/Linux/MacOS
    else:
        os.system('clear')
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


def record_audio_with_silero_vad():
    if not USE_VAD:
        print("\nRecording for 5 seconds...")
        recording = sd.rec(int(RECORDING_DURATION * SAMPLE_RATE), 
                         samplerate=SAMPLE_RATE, 
                         channels=CHANNELS,
                         dtype=np.int16)
        sd.wait()
        print("\nProcessing your command...")
        return recording
        
    # print("\nRecording with Silero VAD...")
    model = load_silero_vad()
    recording = []
    silence_duration = 0
    speech_detected = False
    
    # Constants
    SILENCE_THRESHOLD = 1.0
    SPEECH_THRESHOLD = 0.5
    VAD_SAMPLE_RATE = 16000
    WHISPER_SAMPLE_RATE = 44100
    VAD_FRAME_LENGTH = 512  # Minimum chunk size for Silero VAD
    CHUNK_SIZE = 2048  # Larger recording chunk for better quality
    MIN_RECORDING_LENGTH = WHISPER_SAMPLE_RATE * 0.5

    try:
        with sd.InputStream(
            samplerate=WHISPER_SAMPLE_RATE,
            channels=CHANNELS, 
            dtype=np.int16,
            blocksize=CHUNK_SIZE
        ) as stream:
            print("\nListening... (speak now)")
            audio_buffer = np.array([], dtype=np.float32)
            
            while True:
                audio_chunk, _ = stream.read(CHUNK_SIZE)
                recording.append(audio_chunk)
                
                # Downsample chunk for VAD processing
                downsampled_chunk = signal.resample(
                    audio_chunk, 
                    int(len(audio_chunk) * VAD_SAMPLE_RATE / WHISPER_SAMPLE_RATE)
                )
                
                # Add to buffer
                audio_buffer = np.append(audio_buffer, downsampled_chunk)
                
                # Process complete VAD frames
                while len(audio_buffer) >= VAD_FRAME_LENGTH:
                    # Extract frame and convert to tensor
                    vad_frame = audio_buffer[:VAD_FRAME_LENGTH]
                    audio_buffer = audio_buffer[VAD_FRAME_LENGTH:]
                    
                    # Normalize and convert to tensor
                    audio_tensor = torch.FloatTensor(vad_frame) / 32768.0
                    
                    # Check if speech is present
                    speech_prob = model(audio_tensor, VAD_SAMPLE_RATE).item()
                    
                    if speech_prob > SPEECH_THRESHOLD:
                        speech_detected = True
                        silence_duration = 0
                    else:
                        silence_duration += VAD_FRAME_LENGTH / VAD_SAMPLE_RATE

                # Stop conditions
                total_audio_length = len(np.concatenate(recording))
                if speech_detected and silence_duration >= SILENCE_THRESHOLD and total_audio_length > MIN_RECORDING_LENGTH:
                    break
                elif total_audio_length > WHISPER_SAMPLE_RATE * 30:
                    print("\nMaximum recording length reached")
                    break

        # Process final recording
        recorded_audio = np.concatenate(recording)
        if not speech_detected or len(recorded_audio) < MIN_RECORDING_LENGTH:
            print("\nNo speech detected or recording too short")
            return None
            
        print("\nProcessing your command...")
        return recorded_audio

    except Exception as e:
        print(f"\nError recording audio: {str(e)}")
        print("Please check your microphone settings and permissions.")
        return None

def save_recording(recording):
    # Create recordings directory if it doesn't exist
    recordings_dir = "recordings"
    os.makedirs(recordings_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recording_{timestamp}.wav"
    filepath = os.path.join(recordings_dir, filename)
    wav.write(filepath, SAMPLE_RATE, recording)
    return filepath

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
    try:
        # Define a Pydantic model for the response
        class VoiceCommand(BaseModel):
            intent: str
            coordinates: str | None
            target_name: str | None

        # Load environment variables
        load_dotenv()
        client = OpenAI()
        
        # First transcribe the audio
        with open(audio_file, "rb") as file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                prompt="""
                When transcribing, numbers must always be seperated and not grouped together.
                So if the user says, "New fire mission at foxtrot 5 7 2 1", the transcription should be "New fire mission at foxtrot 5, 7, 2, 1".
                The transcription should never combine all the numbers into one number like "New fire mission at foxtrot 5721".
                Always seperate numbers with commas and spaces.
                After transcribing a phonetic alphabet word like "kilo" or "foxtrot", the rest of the transcriptions should be numbers. So 'for' should be the number '4'
                """,
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
                    If they are trying to save a target, classify as "save_target", extract the "target_name" and do not return coordinates.
                    If they are trying to delete a target, classify as "delete_target", extract the "target_name" and do not return coordinates.
                    If they are trying to set up a mortar position, classify as "setup_mortars" and extract the coordinates.
                    If they are calling in coordinates for a fire mission, classify as "fire_mission" and extract the coordinates.
                    Extract any grid coordinates mentioned (e.g. "A1K5K4K2").
                    So if the user says "New fire mission at foxtrot 5, 7, 2, 1", the coordinates should be "F5K7K2K1".
                    If the user says "Set target for indigo 11 k 1 3 6", the coordinates should be "I11K1K3K6".
                    NEVER return coordinates without the K delimiter! So if the user says "Set target for kilo 241", the coordinates should NOT be "K241".
                    If the user says "Set target for kilo 241", the coordinates SHOULD be "K2K4K1".
                    If the user says "New fire mission on kilo 11 3 2", the coordinates SHOULD be "K11K3K2".
                    """
                },
                {"role": "user", "content": transcription}
            ],
            response_format=VoiceCommand
        )
        
        return completion.choices[0].message.parsed, transcription
    finally:
        # Clean up the audio file
        if os.path.exists(audio_file):
            os.remove(audio_file)

def audio_callback(indata, frames, time, status):
    """Callback for audio stream to process chunks"""
    global audio_queue
    if status:
        print(f"Error: {status}")
    audio_queue.put(bytes(indata))

# At top level
wake_word_detected = False
audio_queue = Queue()

def process_audio_stream(porcupine, audio_queue):
    """Process audio stream for wake word detection"""
    global wake_word_detected
    
    try:
        while not wake_word_detected:
            audio_chunk = audio_queue.get()
            if audio_chunk is None:
                break
                
            pcm = struct.unpack_from("h" * porcupine.frame_length, audio_chunk)
            keyword_index = porcupine.process(pcm)
            
            if keyword_index >= 0:
                # print("\nWake word detected!")
                wake_word_detected = True
                return
                
    except Exception as e:
        print(f"Error in audio processing: {e}")

def calculate_fire_mission(input_arty, input_target):
    """Calculate fire mission parameters and update history"""
    global calculationHistory
    
    x1, y1 = convert_input_to_coordiantes(input_arty)
    x2, y2 = convert_input_to_coordiantes(input_target)
    angle = round(get_angle(x1, y1, x2, y2), 1)
    distance = int(get_vektor(x1, y1, x2, y2))
    click = calcElevation(distance)
    current_target = input_target[-1].replace(' ', '')

    # If we have a new target and existing calculations
    if current_target != calculationHistory['current']['target'] and calculationHistory['current']['distance'] is not None:
        calculationHistory['previous'] = calculationHistory['current'].copy()
        
    # Update current calculations
    calculationHistory['current'] = {
        'distance': distance,
        'angle': angle,
        'click': click,
        'target': current_target
    }
    
    return distance, angle, click, current_target

def save_target(input_arty, input_target, target_name):
    """Save target calculations to saved_targets"""
    global saved_targets
    
    if not input_arty or not input_target:
        print("\nError: Cannot save target without mortar and target positions")
        return False
        
    distance, angle, click, coords = calculate_fire_mission(input_arty, input_target)
    
    saved_targets[target_name.lower()] = {
        'distance': distance,
        'angle': angle,
        'click': click,
        'coords': coords
    }
    return True

def delete_target(target_name):
    """Delete a saved target using OpenAI to determine which targets to remove"""
    global saved_targets
    
    class DeleteResponse(BaseModel):
        targets_to_delete: list[str]

    try:
        client = OpenAI()
        
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "system", 
                    "content": """You are managing a list of saved mortar targets.
                    Return a JSON response with:
                    1. 'targets_to_delete': array of target names (strings)that should be removed
                    
                    If asked to delete a specific target, return that target name if it exists.
                    If asked to delete 'all' targets, return all target names.
                    If target doesn't exist, return empty array.
                    """
                },
                {
                    "role": "user", 
                    "content": f"Current targets: {list(saved_targets.keys())}\nDelete target name/command: {target_name}"
                }
            ],
            response_format=DeleteResponse
        )

        # Parse the response
        print(f"\nResponse from OpenAI: \n{completion.choices[0].message.content}\n")

        response = DeleteResponse.model_validate_json(completion.choices[0].message.content)
        
        # Delete the specified targets
        targets_deleted = False
        for target in response.targets_to_delete:
            if target.lower() in saved_targets:
                del saved_targets[target.lower()]
                targets_deleted = True
        
        print(f"\n{response.message}")
        return targets_deleted

    except Exception as e:
        print(f"\nError processing target deletion: {e}")
        return False

def handle_voice_command(is_wake_word=False):
    clear()
    if not is_wake_word:
        print("\nPress Enter to start recording...")
        input()
    
    recording = record_audio_with_silero_vad()
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
    
    return None

def display_status(input_arty=None, input_target=None, debug_info=None):
    """Display current calculator status and results"""
    if not DEBUG_MODE:
        clear()
    print("\n###########################################")
    print("        Squad AI Mortar Calculator      ")
    print("       by Miyamoto, Maggiefix, XXPX1    ")
    print("###########################################\n")
    
    # Add debug output section
    if DEBUG_MODE and debug_info:
        print("\n--- Debug Information ---")
        print(f"Last Transcription: {debug_info.get('transcription', '')}")
        print(f"Parsed Command: {debug_info.get('parsed_command', '')}")
        print("------------------------\n")

    if not input_arty and not input_target:
        print("> Jarvis is ONLINE and READY for your command! (Ctrl+C to quit)")
        print("\nJust say 'Hey Jarvis, set mortar position to foxtrot 3 2 1 4'")
        print("or 'Jarvis, fire mission at indigo 11 k 1 3 6'")
        print("\nInfinite subset possible like A1K2K5K7K9K8")
        print("You do not have to subset, A1K7 is totally fine!")
        print("\n> To begin, please tell me your current mortar location...\n")
 
    if input_arty and input_target:
        print(f"\n\nCurrent Mortar Position: {input_arty[-1].replace(' ', '')}")
        print("\n###########################################")
        # print(f"Current Target Position: {input_target[-1].replace(' ', '')}")
    if input_target and not input_arty:
        print(f"\n> Fire mission set to {input_target[-1].replace(' ', '')}. Awaiting current mortar positions...")
    if not input_target and input_arty:
        print(f"\n> Current mortar position set to {input_arty[-1].replace(' ', '')}. Awaiting fire mission...")
    
    if input_arty and input_target:
        # Calculate new fire mission
        distance, angle, click, current_target = calculate_fire_mission(input_arty, input_target)
        
        print(f"\nCurrent Target ({current_target}):")
        print(f"         Distance  = {distance} m")
        print(f"         Azimuth   = {angle} °")
        print(f"         Elevation = {click} mil")
        print("\n###########################################")
        
        # Display previous calculations if they exist
        if calculationHistory['previous']['distance'] is not None:
            print(f"\nPrevious Target ({calculationHistory['previous']['target']}):")
            print(f"         Distance  = {calculationHistory['previous']['distance']} m")
            print(f"         Azimuth   = {calculationHistory['previous']['angle']} °")
            print(f"         Elevation = {calculationHistory['previous']['click']} mil")
            print("\n###########################################")
        
        # Add saved targets section
        if saved_targets:
            print("\nSaved Targets:")
            print("--------------")
            for name, data in saved_targets.items():
                print(f"{name}:")
                print(f"         Coords    = {data['coords']}")
                print(f"         Distance  = {data['distance']} m")
                print(f"         Azimuth   = {data['angle']} °")
                print(f"         Elevation = {data['click']} mil")
            print("\n###########################################")
        print("\n> Ready for new fire mission...")

def target_loop():
    global wake_word_detected, audio_queue
    
    # Initialize variables
    input_arty = None
    input_target = None
    processing_thread = None
    audio_stream = None
    porcupine = None
    debug_info = {}

    try:
        load_dotenv()
        if USE_WAKE_WORD:
            porcupine_key = os.getenv('PORCUPINE_ACCESS_KEY')
            if not porcupine_key:
                print("Error: PORCUPINE_ACCESS_KEY not found in environment variables")
                return
                
            porcupine = pvporcupine.create(
                access_key=porcupine_key,
                keywords=[WAKE_WORD]
            )
        
        while True:
            try:
                if USE_WAKE_WORD:
                    # Create new audio stream for each iteration
                    audio_stream = sd.InputStream(
                        channels=1,
                        samplerate=porcupine.sample_rate,
                        dtype=np.int16,
                        blocksize=porcupine.frame_length,
                        callback=audio_callback
                    )
                    
                    with audio_stream:
                        display_status(input_arty, input_target, debug_info)
                        audio_stream.start()
                        
                        # Start wake word detection thread
                        wake_word_detected = False
                        audio_queue = Queue()
                        processing_thread = threading.Thread(
                            target=process_audio_stream,
                            args=(porcupine, audio_queue)
                        )
                        processing_thread.start()
                        
                        # Wait for wake word detection
                        while not wake_word_detected:
                            time.sleep(0.1)
                            if not processing_thread.is_alive():
                                break
                else:
                    # Replace keyboard detection with simple input
                    display_status(input_arty, input_target, debug_info)
                    print("\nPress Enter to start voice command, or 'q' to quit...")
                    user_input = input()
                    if user_input.lower() == 'q':
                        break
                    wake_word_detected = True
                
                if wake_word_detected:
                    # Clean up current audio stream if using wake word
                    if USE_WAKE_WORD:
                        audio_stream.stop()
                        audio_queue.queue.clear()
                        if processing_thread.is_alive():
                            processing_thread.join(timeout=1.0)
                    
                    # print("\nProcessing voice command...")
                    recording = record_audio_with_silero_vad()
                    
                    if recording is not None:
                        audio_file = save_recording(recording)
                        parsed_command, transcription = transcribe_and_parse_audio(audio_file)
                        
                        # Store debug information
                        if DEBUG_MODE:
                            debug_info = {
                                'transcription': transcription,
                                'parsed_command': parsed_command
                            }
                        
                        print(f"\nTranscribed: '{transcription}'")
                        print(f"Parsed Command: {parsed_command}")
                        
                        if parsed_command.coordinates:
                            coordinates_input = parsed_command.coordinates.strip().upper()
                            
                            if parsed_command.intent == "setup_mortars":
                                result = return_input_from_string(coordinates_input, description_2)
                                if result and result[0] in letter_list:
                                    input_arty = result
                                    print("\nMortar position updated!")
                            elif parsed_command.intent == "fire_mission":
                                result = return_input_from_string(coordinates_input, description_3)
                                if result and result[0] in letter_list:
                                    input_target = result
                                    print("\nTarget position updated!")
                
                # Reset wake word detection
                wake_word_detected = False
                
            except KeyboardInterrupt:
                print("\nQuitting...")
                break

            if parsed_command.intent == "save_target" and parsed_command.target_name:
                if save_target(input_arty, input_target, parsed_command.target_name):
                    print(f"\nTarget saved as '{parsed_command.target_name}'")
                else:
                    print("\nFailed to save target")
                    
            elif parsed_command.intent == "delete_target" and parsed_command.target_name:
                if delete_target(parsed_command.target_name):
                    print(f"\nTarget '{parsed_command.target_name}' deleted")
                else:
                    print(f"\nTarget '{parsed_command.target_name}' not found")

    except Exception as e:
        print(f"\nError in main loop: {e}")
        
    finally:
        print("\nCleaning up...")
        if audio_stream is not None:
            audio_stream.stop()
        if audio_queue is not None:
            audio_queue.put(None)
        if processing_thread is not None and processing_thread.is_alive():
            processing_thread.join()
        if porcupine is not None:
            porcupine.delete()


target_loop()

