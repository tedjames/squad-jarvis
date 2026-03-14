# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Squad-Jarvis is a voice-activated AI assistant for the PC game "Squad." It calculates mortar firing solutions (azimuth, elevation, distance) from grid coordinates given via voice commands. It uses Picovoice Porcupine for wake word detection, OpenAI gpt-4o-transcribe for speech-to-text, GPT-4.1-mini structured outputs for intent parsing, and OpenAI TTS (gpt-4o-mini-tts or gpt-4o-realtime-preview via WebSockets) for speech responses.

## Commands

```bash
# Install dependencies
poetry install

# Run the CLI app (must use -m to resolve src.* imports)
poetry run python -m src.main

# Run the Streamlit UI
poetry run streamlit run src/main_ui.py
```

**Important:** Always run with `python -m src.main`, NOT `python src/main.py`. The latter causes `ModuleNotFoundError: No module named 'src'` because the `from src.*` imports require the module to be on the Python path.

System dependencies (macOS): `brew install sox ffmpeg` (required for VAD)

## Architecture

### Two entry points
- **`src/main.py`** — CLI-based main loop (`target_loop()`). Listens for wake word -> records audio with VAD -> transcribes with gpt-4o-transcribe -> parses intent with GPT-4.1-mini structured outputs -> executes command (setup mortars, fire mission, save/delete target) -> speaks result via TTS. All state (mortar position, target position, saved targets, calculation history) is held in module-level globals.
- **`src/main_ui.py`** — Streamlit web UI. Same core logic but uses `st.session_state` for state management. Supports both text input and voice commands.

### Core modules
- **`mortar_calc.py`** — Pure math. Converts grid coordinates (e.g., `F5K7K2K1`) to x/y positions using a 300m grid with recursive 3x3 keypad subdivision, then calculates distance, azimuth angle, and elevation (milliradians) via interpolation from the game's distance/mils lookup tables. The `K` delimiter separates sub-keypad digits.
- **`recording.py`** — Audio capture using `sounddevice`. Supports two modes: fixed 5-second recording (VAD off) or Silero VAD-based recording that stops after 1 second of silence. Records at 44100Hz, downsamples to 16000Hz for VAD processing.
- **`tts.py`** — Two TTS backends toggled by `USE_REALTIME_TTS` env var:
  - **Standard** (`false`): `gpt-4o-mini-tts` via `audio.speech.create` with streaming response. Supports `instructions` parameter for accent/tone control.
  - **Realtime** (`true`): `gpt-4o-realtime-preview` via WebSocket. Voice instructions passed inline in conversation item text (session.update instructions don't reliably control speech style).
- **`transcribe.py`** — Standalone transcription helper using gpt-4o-transcribe.
- **`audio_utils.py`** — Saves recordings as WAV files to a `recordings/` directory.
- **`utils.py`** — Coordinate formatting and NATO phonetic alphabet conversion.
- **`wakeword.py`** — Wake word detection helper (duplicated in main.py).

### Configuration
All feature flags and settings are in `.env` (see `.env.example`):
- `OPENAI_API_KEY`, `PORCUPINE_ACCESS_KEY` — required API keys
- `USE_VAD`, `USE_WAKE_WORD`, `USE_TTS`, `USE_REALTIME_TTS` — feature toggles
- `ACCENT`, `VOICE` — TTS personality settings
- `ENABLE_VOICE_INSTRUCTIONS` — toggles accent/yelling instructions (default: `false`)
- `WAKE_WORD` — configurable wake word (default: "jarvis")

### Coordinate format
Grid coordinates follow the pattern `{Letter}{Number}K{digit}K{digit}...` (e.g., `F5K7K2K1`). The letter is the X-axis column (A-Z), the number is the Y-axis row (1-26), and each K-delimited digit is a sub-keypad position (1-9, arranged like a numpad). Infinite nesting depth is supported.

### Intent classification
Voice commands are parsed into four intents via GPT-4.1-mini structured outputs (Pydantic `VoiceCommand` model):
- `setup_mortars` — set mortar position
- `fire_mission` — calculate firing solution to target
- `save_target` — save current target with a name
- `delete_target` — delete saved target(s), uses a second GPT-4.1-mini call to determine which targets to remove

## Known Issues and Gotchas

### Multi-digit grid rows in transcription
The Whisper/transcribe prompt must explicitly tell the model to keep the first number after the phonetic letter as a single number (1-26). Without this, "alpha eleven" gets transcribed as "alpha 1, 1" which parses into `A1K1` instead of `A11`. The current prompt in `main.py` handles this, but be careful if modifying the transcription prompt.

### Voice instructions unreliability
AI TTS models (both standard and realtime) often refuse or inconsistently follow accent/yelling/impersonation instructions. This is why `ENABLE_VOICE_INSTRUCTIONS` defaults to `false`. The two TTS paths handle instructions differently:
- **Standard TTS** (`gpt-4o-mini-tts`): Uses the official `instructions` parameter on `audio.speech.create` -- this is the proper API-supported approach.
- **Realtime TTS** (`gpt-4o-realtime-preview`): Must embed instructions in the conversation item text. The `session.update` `instructions` field does NOT reliably control speech style for this model -- it's designed for conversational behavior, not TTS style.

### OpenAI SDK versioning
The project uses openai SDK `^2.26.0`. Key differences from v1:
- Structured outputs: `client.chat.completions.parse()` (NOT `client.beta.chat.completions.parse`)
- TTS streaming: `client.audio.speech.with_streaming_response.create()` (NOT `response.stream_to_file()` directly on the response object)

### Running the app
- Must use `python -m src.main` not `python src/main.py` (import resolution)
- `.env` file is required with valid API keys -- the app exits immediately without them
- The `poetry install` warning about "current project could not be installed" is harmless -- all dependencies install correctly
