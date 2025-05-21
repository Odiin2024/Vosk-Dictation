# Project Files Overview

This document provides a summary of the key files in the Vosk speech-to-text project located at `/home/odiin/Programs/Vosk`. It outlines their purpose and current functionality status to facilitate starting a new task with clear context.

- **src/speech_app.py**: 
  - **Purpose**: The original baseline implementation of a speech-to-text application using Vosk for recognition and Sounddevice for audio input. Features a basic Tkinter UI with text display and history.
  - **Status**: Fully functional. Text appears on the screen as spoken, with immediate updates and history saving. No 'Processing' status delay after stopping recording.

- **src/vdic.py**: 
  - **Purpose**: An advanced version of the speech-to-text application with a detailed UI layout (three text areas for history and active text), additional features like edit/save mode, keyboard navigation, and clipboard control.
  - **Status**: Partially functional. UI layout and button functionality are implemented, but speech processing had issues (e.g., text not updating during speech, stuck 'Processing' status). Served as the basis for UI in later files.

- **src/main.py**: 
  - **Purpose**: A staged implementation focusing initially on core speech-to-text functionality from `speech_app.py`, intended to later integrate UI features from `vdic.py`.
  - **Status**: Fully functional. Matches `speech_app.py` behavior with text appearing on screen as spoken. History functionality requires manual scrollbar movement, but otherwise works well.

- **src/main1.py**: 
  - **Purpose**: An updated version of `main.py` with a complete UI overhaul from `vdic.py`, including 6 history slots, visual status indicator, and refined speech processing. Clipboard handling adjusted to update only on 'Stop' button press.
  - **Status**: Functional with updates. UI is improved, speech processing works, and clipboard updates only when recording stops or final result is processed. 'Processing' status delay is present for user feedback during finalization.

- **src/check_tkinter.py**: 
  - **Purpose**: A utility script to test Tkinter functionality, likely used for initial setup or debugging.
  - **Status**: Unknown, not directly related to the main speech-to-text application.

- **src/test_vosk.py**: 
  - **Purpose**: A test script for Vosk speech recognition, likely used to verify Vosk setup or functionality independently of the UI.
  - **Status**: Unknown, not directly related to the main application development.

- **SPEECH_BLUEPRINT.md**: 
  - **Purpose**: A documentation file outlining the approach to resolve speech processing issues in `vdic.py`, detailing steps for audio recording, thread-safe updates, history integration, and status management.
  - **Status**: Reference document, not executable. Provides context for development decisions.

This overview captures the current state of the project files as of the latest updates. You can use this as a starting point for a new task to further refine functionality or address specific issues.
