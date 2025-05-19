# Vosk Speech-to-Text Dictation Assistant

A desktop application that provides real-time speech recognition with editing capabilities and clipboard integration. This tool helps reduce keyboard usage by converting your speech to editable text.

## Features

- **Real-time Speech Recognition**: Uses Vosk for offline speech-to-text conversion
- **Automatic Recording Control**: Starts/stops recording based on voice detection
- **Smart Pause Detection**: Auto-pauses after 3-10 seconds of silence
- **Text History**: Stores up to 12 previous text entries
- **Clipboard Integration**: One-click copy to system clipboard
- **Editable Interface**: Review and modify transcribed text before using it
- **Keyboard Shortcuts**: Navigate history with Ctrl+Up/Down

## Prerequisites

- Python 3.6 or higher
- Linux Mint (or other Linux distribution)

## Installation

1. Clone this repository or download the source code:
   ```bash
   git clone https://github.com/yourusername/vosk-dictation.git
   cd vosk-dictation
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the required packages:
   ```bash
   pip install vosk sounddevice numpy pyperclip
   ```

4. Install Tkinter if not already available:
   ```bash
   sudo apt-get update
   sudo apt-get install python3-tk
   ```

5. Download a Vosk model:
   ```bash
   mkdir -p models
   cd models
   wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
   unzip vosk-model-small-en-us-0.15.zip
   # For better accuracy (but larger download):
   # wget https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
   # unzip vosk-model-en-us-0.22.zip
   ```

## Usage

1. Activate the virtual environment (if not already activated):
   ```bash
   source venv/bin/activate
   ```

2. Run the application:
   ```bash
   python src/dictation_app.py
   ```

3. Use the controls:
   - Click **Start Recording** to begin dictation
   - Speak clearly into your microphone
   - The application will automatically pause after 3-10 seconds of silence
   - Edit the text as needed in the text area
   - Click **Copy to Clipboard** to copy the text
   - Use **Ctrl+Up/Down** to navigate through your dictation history

## Directory Structure

```
~/Programs/Vosk/
├── venv/                   # Virtual environment
├── models/                 # Speech recognition models
│   └── vosk-model-small-en-us-0.15/
├── src/                    # Source code
│   ├── dictation_app.py    # Main application
│   └── test_vosk.py        # Test script
└── README.md               # This file
```

## Configuration

You can modify the following parameters in the source code:

- `SILENCE_THRESHOLD`: Level at which audio is considered silence
- `MAX_SILENCE_DURATION`: Time in seconds before pausing after silence
- `MAX_HISTORY_ENTRIES`: Number of history entries to keep

## Troubleshooting

- **No audio input detected**: Check your microphone settings and permissions
- **Slow transcription**: Consider using a smaller Vosk model or upgrading your hardware
- **Import errors**: Ensure all dependencies are installed in your virtual environment

## Future Improvements

- [ ] Customizable keyboard shortcuts
- [ ] Improved punctuation in transcription
- [ ] Export/import of dictation history
- [ ] Specialized vocabulary training
- [ ] Multiple language support

## License

[MIT License](LICENSE)

## Acknowledgements

- [Vosk Speech Recognition Toolkit](https://alphacephei.com/vosk/)
- [Python SoundDevice Library](https://python-sounddevice.readthedocs.io/)
- [Tkinter Documentation](https://docs.python.org/3/library/tkinter.html)
