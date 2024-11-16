#!/usr/bin/python
 # -*- coding: utf-8 -*-
# Squad-Jarvis - AI Military Operations Assistant for Squad
# Manages mortar missions with customizable AI voice commands
# Original mortar calculator by /u/Maggiefix, [GER] Maggiefix and XXPX1
# Voice activated AI assistant by Miyamoto

########################################
# Packages                             #
########################################
import os
import sounddevice as sd
import numpy as np
import time
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
import pvporcupine
import threading
from queue import Queue
import warnings
import sys
import struct

from src.mortar_calc import (
    return_input_from_string,
    calculate_fire_mission,
    letter_list,
    description_2,
    description_3
)
from src.recording import (
    record_audio_with_silero_vad,
)
from src.utils import (
    format_coordinates,
    clear
)
from src.audio_utils import (
    save_recording
)
from src.tts import (
    start_tts
)



# Ignore DeprecationWarning (hides annoying openai warning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

########################################
# Constants                           #
########################################
SAMPLE_RATE = 44100
CHANNELS = 1

# Load environment variables early
load_dotenv()

# Voice and Speech Features
WAKE_WORD = os.getenv('WAKE_WORD', 'jarvis')
DEBUG_MODE = os.getenv('DEBUG_MODE', 'true').lower() == 'true'
USE_VAD = os.getenv('USE_VAD', 'true').lower() == 'true'
USE_WAKE_WORD = os.getenv('USE_WAKE_WORD', 'true').lower() == 'true'
WELCOME_TTS = os.getenv('WELCOME_TTS', 'false').lower() == 'true'

# Validate required API keys
if USE_WAKE_WORD and not os.getenv('PORCUPINE_ACCESS_KEY'):
    print("Error: PORCUPINE_ACCESS_KEY not found in environment variables")
    sys.exit(1)

if not os.getenv('OPENAI_API_KEY'):
    print("Error: OPENAI_API_KEY not found in environment variables")
    sys.exit(1)

# instantiate global state variables
current_tts_thread = None
wake_word_detected = False
audio_queue = Queue()

saved_targets = {} 
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
def transcribe_and_parse_audio(audio_file):
    try:
        # Define a Pydantic model for the response
        class VoiceCommand(BaseModel):
            intent: str
            coordinates: str | None
            target_name: str | None
            message: str | None

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
                    "content": """Extract the user's intent from their voice command for a mortar calculator / AI military operations assistant tool.
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

def save_target(input_arty, input_target, target_name):
    """Save target calculations to saved_targets"""
    global saved_targets
    
    if not input_arty or not input_target:
        print("\nError: Cannot save target without mortar and target positions")
        return False
        
    distance, angle, click, coords = calculate_fire_mission(input_arty, input_target, calculationHistory)
    
    saved_targets[target_name.lower()] = {
        'distance': distance,
        'angle': angle,
        'click': click,
        'coords': coords
    }
    speech_text = f"Copy that! Target named, {target_name} has been saved! Over..."
    start_tts(speech_text)
        
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
        if DEBUG_MODE:
            print(f"\nResponse from OpenAI: \n{completion.choices[0].message.content}\n")

        response = DeleteResponse.model_validate_json(completion.choices[0].message.content)
        
        # Delete the specified targets
        targets_deleted = False
        for target in response.targets_to_delete:
            if target.lower() in saved_targets:
                del saved_targets[target.lower()]
                targets_deleted = True

        # Convert array of deleted targets to comma-separated string
        deleted_targets_str = ", ".join(response.targets_to_delete[:-1]) + " and " + response.targets_to_delete[-1] if len(response.targets_to_delete) > 1 else response.targets_to_delete[0] if response.targets_to_delete else ""
        
        if DEBUG_MODE:
            print(f"\n{response.message}")
        speech_text = f"Copy that! {'Target' if len(response.targets_to_delete) == 1 else 'Targets'}, {deleted_targets_str} {'has' if len(response.targets_to_delete) == 1 else 'have'} been deleted! Over..."
        start_tts(speech_text)
        return targets_deleted

    except Exception as e:
        print(f"\nError processing target deletion: {e}")
        return False

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
        if WELCOME_TTS: 
            start_tts("Jarvis is ONLINE and READY for your command! Over...")
 

    if input_target and not input_arty:
        status_text = f"Fire mission set to {format_coordinates(input_target)}. Awaiting current mortar positions! Over..."
        print(f"\n> {status_text}")
        status_text_phonetic = f"Fire mission set to {format_coordinates(input_target, convert_to_phonetic=True)}. Awaiting current mortar positions! Over..."
        start_tts(status_text_phonetic)
    if not input_target and input_arty:
        status_text = f"Current mortar position set to {format_coordinates(input_arty)}. Awaiting fire mission! Over..."
        print(f"\n> {status_text}")
        status_text_phonetic = f"Current mortar position set to {format_coordinates(input_arty, convert_to_phonetic=True)}. Awaiting fire mission! Over..."
        start_tts(status_text_phonetic)
    
    if input_arty and input_target:
        print(f"\n\nCurrent Mortar Position: {format_coordinates(input_arty)}")
        print("\n###########################################")

        # Calculate new fire mission
        distance, angle, click, current_target = calculate_fire_mission(input_arty, input_target, calculationHistory)
      
        print(f"\nCurrent Target ({current_target}):")
        print(f"         Distance  = {distance} m")
        print(f"         Azimuth   = {angle} °")
        print(f"         Elevation = {click} mil")
        print("\n###########################################")

        # Generate speech for new calculations only if not handling save/delete commands
        if debug_info and debug_info.get('parsed_command'):
            parsed_command = debug_info['parsed_command']
            if parsed_command.intent not in ['save_target', 'delete_target']:
                # Convert float to string with one decimal place, then split into individual digits
                angle_str = str(round(angle, 1)).replace('.', ' point ')
                click_str = ", ".join(str(click))
                speech_text = f"mortars are out of range by {int(distance - 1250)} meters!" if "Out of Range" in str(click) else f"Fire mission set! Azimuth {angle_str}. Elevation {click_str}. I repeat, azimuth {angle_str}. Elevation {click_str}."
                start_tts(speech_text)
        
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
                        debug_info = {
                            'transcription': transcription,
                            'parsed_command': parsed_command
                        }
                        
                        print(f"\nTranscribed: '{transcription}'")
                        print(f"Parsed Command: {parsed_command}")

                        # if parsed_command.intent == "insult":
                        #     if DEBUG_MODE:
                        #         print(f"\nInsult: {parsed_command.message}")
                        #     start_tts(parsed_command.message)
                        #     continue
                        
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

