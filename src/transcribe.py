from dotenv import load_dotenv
from openai import OpenAI

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
