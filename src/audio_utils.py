import os
from datetime import datetime
import scipy.io.wavfile as wav
SAMPLE_RATE = 44100

def save_recording(recording):
    # Create recordings directory if it doesn't exist
    recordings_dir = "recordings"
    os.makedirs(recordings_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recording_{timestamp}.wav"
    filepath = os.path.join(recordings_dir, filename)
    wav.write(filepath, SAMPLE_RATE, recording)
    return filepath
