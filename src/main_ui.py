import streamlit as st
from src.mortar_calc import (
    return_input_from_string,
    calculate_fire_mission,
    letter_list
)
from src.utils import format_coordinates
import sounddevice as sd
import numpy as np
import pvporcupine
import threading
from queue import Queue
import struct
from openai import OpenAI
from pydantic import BaseModel
from src.recording import record_audio_with_silero_vad
from src.audio_utils import save_recording
from src.tts import start_tts
import os

# Add these constants at the top after imports
WAKE_WORD = os.getenv('WAKE_WORD', 'jarvis')
USE_WAKE_WORD = os.getenv('USE_WAKE_WORD', 'true').lower() == 'true'

def init_session_state():
    if 'input_arty' not in st.session_state:
        st.session_state.input_arty = None
    if 'input_target' not in st.session_state:
        st.session_state.input_target = None
    if 'saved_targets' not in st.session_state:
        st.session_state.saved_targets = {}
    if 'calculation_history' not in st.session_state:
        st.session_state.calculation_history = {
            'current': {'distance': None, 'angle': None, 'click': None, 'target': None},
            'previous': {'distance': None, 'angle': None, 'click': None, 'target': None}
        }
    if 'wake_word_detected' not in st.session_state:
        st.session_state.wake_word_detected = False
    if 'is_listening' not in st.session_state:
        st.session_state.is_listening = False
    if 'audio_queue' not in st.session_state:
        st.session_state.audio_queue = Queue()

def process_audio_stream(porcupine, audio_queue):
    """Process audio stream for wake word detection"""
    try:
        while not st.session_state.wake_word_detected:
            audio_chunk = audio_queue.get()
            if audio_chunk is None:
                break
                
            pcm = struct.unpack_from("h" * porcupine.frame_length, audio_chunk)
            keyword_index = porcupine.process(pcm)
            
            if keyword_index >= 0:
                st.session_state.wake_word_detected = True
                return
                
    except Exception as e:
        st.error(f"Error in audio processing: {e}")

def audio_callback(indata, frames, time, status):
    """Callback for audio stream to process chunks"""
    if status:
        st.error(f"Error: {status}")
    st.session_state.audio_queue.put(bytes(indata))

def handle_voice_command():
    """Handle voice command recording and processing"""
    try:
        recording = record_audio_with_silero_vad()
        if recording is not None:
            audio_file = save_recording(recording)
            parsed_command, transcription = transcribe_and_parse_audio(audio_file)
            
            st.info(f"Transcribed: '{transcription}'")
            
            if parsed_command.coordinates:
                coordinates_input = parsed_command.coordinates.strip().upper()
                
                if parsed_command.intent == "setup_mortars":
                    result = return_input_from_string(coordinates_input, "mortar")
                    if result and result[0] in letter_list:
                        st.session_state.input_arty = result
                        st.success(f"Mortar position set to: {format_coordinates(result)}")
                        
                elif parsed_command.intent == "fire_mission":
                    result = return_input_from_string(coordinates_input, "target")
                    if result and result[0] in letter_list:
                        st.session_state.input_target = result
                        st.success(f"Target position set to: {format_coordinates(result)}")
                        
    except Exception as e:
        st.error(f"Error processing voice command: {e}")

def main():
    st.set_page_config(page_title="Squad-Jarvis Mortar Calculator", layout="wide")
    init_session_state()

    st.title("Squad-Jarvis Mortar Calculator")
    st.subheader("by Miyamoto, Maggiefix, XXPX1")

    # Create two columns for input
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Mortar Position")
        mortar_pos = st.text_input(
            "Enter mortar coordinates (e.g., F3K2K1K4)",
            key="mortar_input"
        ).upper()

        if mortar_pos:
            result = return_input_from_string(mortar_pos, "mortar")
            if result and result[0] in letter_list:
                st.session_state.input_arty = result
                st.success(f"Mortar position set to: {format_coordinates(result)}")
            else:
                st.error("Invalid mortar coordinates")

    with col2:
        st.subheader("Target Position")
        target_pos = st.text_input(
            "Enter target coordinates (e.g., I11K1K3K6)",
            key="target_input"
        ).upper()

        if target_pos:
            result = return_input_from_string(target_pos, "target")
            if result and result[0] in letter_list:
                st.session_state.input_target = result
                st.success(f"Target position set to: {format_coordinates(result)}")
            else:
                st.error("Invalid target coordinates")

    # Calculate and display results
    if st.session_state.input_arty and st.session_state.input_target:
        st.divider()
        st.subheader("Fire Mission Results")

        distance, angle, click, current_target = calculate_fire_mission(
            st.session_state.input_arty,
            st.session_state.input_target,
            st.session_state.calculation_history
        )

        # Display current calculations
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Distance", f"{distance} m")
        with col2:
            st.metric("Azimuth", f"{angle}°")
        with col3:
            st.metric("Elevation", f"{click} mil")

        # Save target section
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Save Target")
            target_name = st.text_input("Target name").lower()
            if st.button("Save Target") and target_name:
                st.session_state.saved_targets[target_name] = {
                    'distance': distance,
                    'angle': angle,
                    'click': click,
                    'coords': current_target
                }
                st.success(f"Target '{target_name}' saved!")

        # Display saved targets
        if st.session_state.saved_targets:
            with col2:
                st.subheader("Saved Targets")
                target_to_delete = st.selectbox(
                    "Select target to delete",
                    options=list(st.session_state.saved_targets.keys())
                )
                if st.button("Delete Target") and target_to_delete:
                    del st.session_state.saved_targets[target_to_delete]
                    st.success(f"Target '{target_to_delete}' deleted!")

            st.divider()
            st.subheader("Saved Targets List")
            for name, data in st.session_state.saved_targets.items():
                with st.expander(f"Target: {name}"):
                    st.write(f"Coordinates: {data['coords']}")
                    st.write(f"Distance: {data['distance']} m")
                    st.write(f"Azimuth: {data['angle']}°")
                    st.write(f"Elevation: {data['click']} mil")

    # Add voice command section
    st.divider()
    st.subheader("Voice Commands")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Listening"):
            st.session_state.is_listening = True
            
    with col2:
        if st.button("Stop Listening"):
            st.session_state.is_listening = False
            
    if st.session_state.is_listening:
        st.info("Listening for voice commands... Say 'Hey Jarvis' to activate")
        
        if USE_WAKE_WORD:
            porcupine = pvporcupine.create(
                access_key=os.getenv('PORCUPINE_ACCESS_KEY'),
                keywords=[WAKE_WORD]
            )
            
            audio_stream = sd.InputStream(
                channels=1,
                samplerate=porcupine.sample_rate,
                dtype=np.int16,
                blocksize=porcupine.frame_length,
                callback=audio_callback
            )
            
            with audio_stream:
                if st.session_state.wake_word_detected:
                    handle_voice_command()
                    st.session_state.wake_word_detected = False

if __name__ == "__main__":
    main()