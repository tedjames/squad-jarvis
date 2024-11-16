from openai import OpenAI
import os
import pygame
import asyncio
from datetime import datetime
from pathlib import Path
import numpy as np
import sounddevice as sd
import base64
import json
import websockets
import threading
from dotenv import load_dotenv

load_dotenv()

# TTS Configuration
USE_TTS = os.getenv('USE_TTS', 'true').lower() == 'true'
USE_REALTIME_TTS = os.getenv('USE_REALTIME_TTS', 'true').lower() == 'true'
ACCENT = os.getenv('ACCENT', 'Chinese')
VOICE = os.getenv('VOICE', 'ash')
USE_CHUNKED_TTS = os.getenv('USE_CHUNKED_TTS', 'false').lower() == 'true'


def text_to_speech(text: str):
    """
    Convert text to speech using either regular or realtime TTS API
    """
    if USE_REALTIME_TTS:
        print("Using realtime TTS")
        asyncio.run(realtime_tts(text))
    else:
        try:
            # Create TTS directory if it doesn't exist
            tts_dir = Path(__file__).parent / "tts"
            tts_dir.mkdir(exist_ok=True)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            speech_file = tts_dir / f"speech_{timestamp}.mp3"
            
            # Generate speech file
            client = OpenAI()
            response = client.audio.speech.create(
                model="tts-1",
                voice="fable",
                input=text
            )
            response.stream_to_file(str(speech_file)) # ignore deprecation warning
            
            # Initialize pygame mixer
            os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
            pygame.mixer.init()
            pygame.mixer.music.load(str(speech_file))
            pygame.mixer.music.play()
            
            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
                
            # Cleanup
            pygame.mixer.quit()
            speech_file.unlink()
            
        except Exception as e:
            print(f"TTS Error: {str(e)}")


async def realtime_tts(text: str):
    """
    Send text to OpenAI's realtime API for TTS via websockets
    Args:
        text: Text to convert to speech
    """
    try:
        url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "OpenAI-Beta": "realtime=v1"
        }

        # Buffer to store audio chunks
        audio_chunks = []
        CHUNKS_TO_PLAY = 5  # Number of chunks to accumulate before playing

        async with websockets.connect(url, extra_headers=headers) as ws:
            # Send initial conversation event
            event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user", 
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"Loudly and quickly yell the following text in English with a HEAVY {ACCENT} accent. <START TEXT TO BE SPOKEN> {text} <END TEXT TO BE SPOKEN> Remember to speak in English with a HEAVY {ACCENT} accent and speak fast!"
                        }
                    ]
                }
            }

            session_update_event = {
                "type": "session.update",
                "session": {
                    "voice": f"{VOICE}",
                }
            }
            
            # event = {
            #     "type": "response.create",
            #     "response": {
            #         "modalities": ["text", "audio"],
            #         "instructions": f"Loudly and quickly yell the following text in English with a {ACCENT} accent. <START TEXT TO BE SPOKEN> {text} <END TEXT TO BE SPOKEN> Remember to speak in English with a {ACCENT} accent!",
            #         "voice": "alloy",
            #         'output_audio_format': "pcm_16",
            #         "max_output_tokens": 2000,
            #         "temperature": 0.7,
            #     },
            # }
            # print(event)
            await ws.send(json.dumps(session_update_event))
            await ws.send(json.dumps(event))
            await ws.send(json.dumps({"type": "response.create"}))

            def play_chunks(chunks_to_play):
                if not chunks_to_play:
                    return
                combined_audio = np.concatenate(chunks_to_play)
                sd.play(combined_audio, samplerate=24000)
                sd.wait()

            while True:
                response = await ws.recv()
                event = json.loads(response)

                if event["type"] == "response.audio.delta":
                    audio_chunk = base64.b64decode(event["delta"])
                    chunk_data = np.frombuffer(audio_chunk, dtype=np.int16)
                    audio_chunks.append(chunk_data)

                    # Play chunks when we have accumulated enough (only if use_chunks is True)
                    if USE_CHUNKED_TTS and len(audio_chunks) >= CHUNKS_TO_PLAY:
                        chunks_to_play = audio_chunks[:CHUNKS_TO_PLAY]
                        audio_chunks = audio_chunks[CHUNKS_TO_PLAY:]
                        play_chunks(chunks_to_play)

                elif event["type"] == "response.audio.done":
                    # Play all remaining chunks at once
                    play_chunks(audio_chunks)
                    break

    except Exception as e:
        print(f"Realtime TTS Error: {str(e)}")

def start_tts(text: str):
    """Helper function to start a new TTS thread"""
    if USE_TTS: 
        current_tts_thread = threading.Thread(target=text_to_speech, args=(text,))
        current_tts_thread.start()
