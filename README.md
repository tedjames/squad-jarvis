# Squad AI Mortar Calculator aka JARVIS

## How to use

This is a Python script that uses an OpenAI Whisper and GPT-4o structured outputs to transcribe your voice and convert it into specific commands for a mortar calculator. Run the script and say "Jarvis" followed by a command.

Just say something like,"Hey Jarvis, set mortar position to foxtrot 3 2 1 4" or "Jarvis, fire mission at indigo 11 k 1 3 6" and the script will set the mortar position or fire mission respectively.

Infinite subsets are possible like A1K2K5K7K9K8 but you do not have to subset either, A1K7 is totally fine!

Available commands:

- "Setup mortar position at foxtrot 3 2 1 4" to set the mortar position
- "New fire mission at F2 3 4" to set a mortar target with coordinates F2K3K4

More coming soon!

## How to install

1. Install the dependencies with `poetry install`
2. Set the environment variables
3. Run the script with `poetry run python src/main.py`

## How to setup the environment variables

1. Create a `.env` file in the root directory
2. Copy the content of `.env.example` into the `.env` file
3. Set the env variables to your own API keys from OpenAI & Porcupine

Porcupine is a wake word detection engine. You can get your Porcupine API key [here](https://picovoice.ai/platform/porcupine/).

OpenAI is a large language model provider used to transcribe your voice to text and convert the text input into specific commands using JSON structured outputs. You can get your OpenAI API key [here](https://platform.openai.com/).

## Future improvements

- [ ] Display previous elevation/azimuth values so it's easier to switch between two targets
- [ ] Allow users to provide a primary and secondary target all in one command, like "Fire mission at F2 3 4 and F2 5 2". That way you can quickly switch between two targets.
- [ ] Save the previous primary and secondary target positions so you can say, "Revert to previous fire mission"
- [ ] Allow users to save targets to a list so they can say, "Fire at target 1"
- [ ] Allow users to delete saved targets or delete all saved targets at once
- [ ] Allow users to give a name to each target so they can say, "Fire at Airport" or "Fire at Central Pretrivka"
- [ ] Integrate TTS so the AI can talk back to the user and announce elevation/azimuth
