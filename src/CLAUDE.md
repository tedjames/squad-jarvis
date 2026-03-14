# src/CLAUDE.md

Module-level guidance for the `src/` directory.

## AI Model Reference

| Purpose | Model | File | Notes |
|---------|-------|------|-------|
| Transcription | `gpt-4o-transcribe` | `main.py`, `transcribe.py` | Replaced whisper-1. Supports `prompt` parameter for steering. |
| Intent parsing | `gpt-4.1-mini` | `main.py` | Two call sites: `transcribe_and_parse_audio()` and `delete_target()`. Uses `client.chat.completions.parse()` with Pydantic models. |
| Standard TTS | `gpt-4o-mini-tts` | `tts.py` | Has `instructions` param for accent/tone. Uses `with_streaming_response` pattern. |
| Realtime TTS | `gpt-4o-realtime-preview` | `tts.py` | WebSocket-based. Voice instructions go in conversation item text, NOT session.update. |

## Transcription Prompt Pitfalls (main.py)

The Whisper prompt in `transcribe_and_parse_audio()` is critical and easy to break:

- The first number after a phonetic letter is a **grid row (1-26)** and must stay grouped. "eleven" = "11", never "1, 1".
- All subsequent numbers are **keypad digits (1-9)** and should be comma-separated.
- The word "for" should be transcribed as the number "4" (not the preposition).
- If the prompt says "always separate numbers", it will split "11" into "1, 1" -- this was a past bug.

## Coordinate Parsing Prompt Pitfalls (main.py)

The intent parsing prompt must clearly distinguish grid rows from keypad digits:

- Format: `{Letter}{GridRow}K{digit}K{digit}...`
- Grid row is 1-26, NEVER split with K delimiter. "eleven" = `11`, not `K1K1`.
- Each keypad digit is 1-9, separated by K.
- The letter "K" (kilo) is both a valid grid column AND the delimiter -- the prompt needs examples for this edge case (e.g., "kilo 21 4 5" -> `K21K4K5`).

## TTS Implementation Notes (tts.py)

- `text_to_speech()` is the main entry point, branching on `USE_REALTIME_TTS`.
- `start_tts()` wraps it in a thread so TTS doesn't block the main loop.
- Standard TTS writes a temp mp3 file, plays it with pygame, then deletes it.
- Realtime TTS streams PCM audio chunks over WebSocket and plays via sounddevice.
- `USE_CHUNKED_TTS` controls whether realtime audio plays incrementally or waits for the full response.

## State Management (main.py)

All state is module-level globals in `main.py`:
- `input_arty` / `input_target` — current mortar and target positions (tuples from `return_input_from_string`)
- `saved_targets` — dict of named targets with pre-calculated fire solutions
- `calculationHistory` — tracks current and previous fire solutions for display
- `wake_word_detected` / `audio_queue` — shared between main thread and wake word detection thread
