# WizType

WizType is a local typing assistant built into Whiztant. It uses Ollama on `localhost:11434` to offer:

- autocorrect suggestions while you pause on a word
- next-word suggestions after spaces and line breaks
- local model install/remove from the settings UI
- no cloud API requirement for typing assistance

## Models

The current WizType model options are:

- `llama3.2:1b`
- `phi3.5`
- `smolvlm`

## Setup

1. Install and run Ollama.
2. Open Whiztant settings.
3. Go to the `WizType` tab.
4. Choose a model.
5. Click `Install Selected` if the model is not already present.
6. Enable WizType.

## Usage

- Pause while typing a word to get a correction suggestion.
- Pause after a space or enter to get a next-word suggestion.
- Press `Tab` to accept the current suggestion.
- Press `Escape` to dismiss it.

## Notes

- WizType stores its config in `data/wiztype_config.json`.
- If `httpx` or `pynput` are not installed, the rest of Whiztant still runs, but WizType will stay inactive until dependencies are installed.
- Suggestions depend on Ollama model availability and local performance.
