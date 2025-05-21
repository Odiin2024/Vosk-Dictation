# Speech Processing and History Blueprint for vdic.py

## Current Status

*   The UI layout in `vdic.py` with the three text windows (history above, active speech, history below) and the button panel is considered successful.
*   Button functionality (Edit/Save, Restore, Settings placeholder) is implemented.
*   The "Record" button text correctly toggles to "Stop" when recording starts.
*   **Persistent Issues**:
    *   Text is not being generated in the active speech window *during* speech.
    *   The "Processing..." status gets stuck after stopping recording.
    *   An error "Error during audio recording: too many values to unpack (expected 2)" occurs when starting recording. This indicates an issue with reading audio data from the sound device stream.

## Problem Assessment

The core problem lies in the interaction between the Vosk speech recognition process (running in a background thread) and the Tkinter main thread, specifically how partial and final results from the recognizer are handled and displayed in the `active_text` widget, and how the thread signals completion and status updates back to the main thread.

The `speech_app.py`'s `process_audio` loop, while simpler, successfully updates the text area as speech is recognized. The `vdic.py` structure needs to replicate this behavior while managing the history and the specific UI elements. The stuck "Processing" status indicates the background thread might not be terminating cleanly or the final status update call is not being processed by the Tkinter event loop.

The "too many values to unpack" error in `record_audio` suggests an incorrect way of reading data from the `sounddevice` stream, despite attempts to correct it based on the `speech_app.py` implementation. This needs further investigation to ensure audio data is correctly captured before being put into the queue for processing.

## Fresh Approach Blueprint

This blueprint focuses on ensuring reliable speech processing and history management within the existing `vdic.py` UI, addressing the identified issues.

1.  **Diagnose and Fix Audio Recording Error**:
    *   Re-examine the `record_audio` method and the `sounddevice.InputStream.read()` documentation to understand why the "too many values to unpack" error is occurring.
    *   Implement the correct method for reading audio data into `audio_chunk`.

2.  **Refine `process_audio` Loop and Thread-Safe Updates**:
    *   Ensure the `process_audio` method correctly handles both partial and final Vosk results.
    *   Implement a robust thread-safe mechanism (e.g., using `root.after()` or a dedicated queue for UI updates) to safely update the `active_text` widget with both partial and final results from the background thread.
    *   Ensure the loop correctly exits when `self.is_recording` becomes `False` and the `audio_queue` is empty.

3.  **History Integration**:
    *   When a *final* result is received in `process_audio` (indicating a pause or end of speech segment), call the `save_to_history` method.
    *   The `save_to_history` method will add the finalized text to the `text_history` deque, manage the deque size (max 6 entries), update the `history_position`, and call `update_history_display`.
    *   The `update_history_display` method will correctly populate `history_above_text` and `history_below_text` based on the current `history_position` and the contents of `text_history`, displaying "say something" for empty slots.

4.  **Status Management**:
    *   Update the `status_label` to "Listening..." when recording starts.
    *   Update the `status_label` to "Processing..." briefly when recording stops and the processing thread is finishing up.
    *   Update the `status_label` to "Idle" reliably on the main thread after the `process_audio` thread has completed its final processing and exited.

5.  **Keyboard Navigation**:
    *   Ensure the existing keyboard bindings (`<Up>`, `<Down>`, `<Left>`, `<Right>`) correctly interact with the updated history and text display logic.
    *   Left/Right arrows should navigate the `history_position`, updating `active_text`, `history_above_text`, and `history_below_text`, and the clipboard.
    *   Up/Down arrows should handle line-by-line scrolling within the `active_text` content when it exceeds the visible area (only when not in edit mode).

6.  **Clipboard Control**:
    *   Maintain the logic for the application controlling the clipboard by default and releasing control on external copy actions or focus loss.

## Next Steps (in a New Task)

1.  Start by focusing on resolving the "too many values to unpack" error in the `record_audio` method.
2.  Once audio recording is stable, work on ensuring partial and final results from Vosk are correctly processed and displayed in the `active_text` window dynamically.
3.  Address the "Processing..." status getting stuck by refining the thread termination and status update logic.
4.  Verify history saving and display are working correctly after speech segments are finalized.
5.  Test all interactions, including keyboard navigation and clipboard control.
