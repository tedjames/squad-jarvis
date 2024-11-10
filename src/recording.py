from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
import sounddevice as sd
from scipy import signal  # For resampling
import numpy as np
import torch
import os

RECORDING_DURATION = 5
SAMPLE_RATE = 44100
CHANNELS = 1
USE_VAD = os.getenv('USE_VAD', 'true').lower() == 'true'


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
