import struct

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
