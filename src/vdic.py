import vosk
import json
import sounddevice as sd
import numpy as np
import pyperclip
import tkinter as tk
from tkinter import scrolledtext, PanedWindow, VERTICAL, HORIZONTAL
import threading
import time
import queue
import os
from collections import deque

# Path to your model
# Check if the model path exists relative to the script or the current working directory
MODEL_PATH_RELATIVE = "../models/vosk-model-en-us-0.22"
MODEL_PATH_CWD = os.path.join(os.path.dirname(__file__), MODEL_PATH_RELATIVE)

MODEL_PATH = MODEL_PATH_CWD if os.path.exists(MODEL_PATH_CWD) else MODEL_PATH_RELATIVE

# Styling
BG_COLOR = "#333333" # Dark grey background
FG_COLOR = "#E0B0FF" # Mauve foreground
BUTTON_BG = "#555555"
BUTTON_FG = "#E0B0FF"
STATUS_FG = "#90EE90" # Light green for status
EMPTY_TEXT_COLOR = "#888888" # Grey for "say something"

# Constants
MAX_HISTORY_ENTRIES = 6
SILENCE_THRESHOLD = 100 # Adjust threshold as needed
MAX_SILENCE_DURATION = 3 # Seconds of silence before saving to history

class DictationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Dictation Tool")
        self.root.geometry("800x600") # Adjusted size for layout
        self.root.configure(bg=BG_COLOR)

        # Setup variables
        self.is_recording = False
        self.text_history = deque(maxlen=MAX_HISTORY_ENTRIES)
        self.history_position = -1 # Index in deque, -1 means active_text is not from history
        self.silence_timer = 0
        self.last_speech_time = time.time()
        self.audio_queue = queue.Queue()
        self.edit_mode = False
        self.restore_text = ""
        self.clipboard_controlled_by_app = True # Flag to manage clipboard control

        # Create UI
        self.create_widgets()

        # Setup Vosk
        try:
            if not os.path.exists(MODEL_PATH):
                 raise FileNotFoundError(f"Vosk model not found at {MODEL_PATH}")
            self.model = vosk.Model(MODEL_PATH)
        except Exception as e:
            print(f"Error loading Vosk model: {e}")
            print(f"Please ensure the model is downloaded and the path is correct: {MODEL_PATH}")
            self.status_label.config(text=f"Error: {e}", fg="red")
            # Disable buttons if model fails to load
            self.toggle_button.config(state=tk.DISABLED)
            self.edit_save_button.config(state=tk.DISABLED)
            self.settings_button.config(state=tk.DISABLED) # Settings button initially visible
            return

        self.samplerate = 16000
        self.recognizer = vosk.KaldiRecognizer(self.model, self.samplerate)

        # Start audio processing thread
        self.processing_thread = threading.Thread(target=self.process_audio)
        self.processing_thread.daemon = True
        self.processing_thread.start()

        # Bind keyboard shortcuts and focus events
        self.active_text.bind('<FocusIn>', self.on_active_text_focus)
        self.active_text.bind('<FocusOut>', self.on_active_text_unfocus)
        self.active_text.bind('<Up>', self.scroll_active_text_up)
        self.active_text.bind('<Down>', self.scroll_active_text_down)
        self.active_text.bind('<Left>', self.navigate_history_left)
        self.active_text.bind('<Right>', self.navigate_history_right)
        self.active_text.bind('<Control-c>', self.on_external_copy) # Detect Ctrl+C
        self.active_text.bind('<Button-3>', self.on_external_copy) # Detect Right Click (for paste context menu)

        # Initial state
        self.update_history_display() # Display "say something" initially
        self.set_active_text_editable(False) # Start in non-edit mode

    def create_widgets(self):
        # Use a PanedWindow for the main left/right split
        main_paned_window = PanedWindow(self.root, orient=HORIZONTAL, bg=BG_COLOR, sashrelief=tk.RAISED)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left Frame for Text Areas
        text_frame = tk.Frame(main_paned_window, bg=BG_COLOR)
        main_paned_window.add(text_frame, stretch="always")

        # Use a PanedWindow for the three text areas vertically
        text_paned_window = PanedWindow(text_frame, orient=VERTICAL, bg=BG_COLOR, sashrelief=tk.RAISED)
        text_paned_window.pack(fill=tk.BOTH, expand=True)

        # History Above Text area
        self.history_above_text = tk.Text(text_paned_window, wrap=tk.WORD, height=3, state=tk.DISABLED, bg=BG_COLOR, fg=FG_COLOR, selectbackground=BUTTON_BG, selectforeground="white", font=("TkDefaultFont", 11))
        text_paned_window.add(self.history_above_text, stretch="always")

        # Active Text area
        self.active_text = tk.Text(text_paned_window, wrap=tk.WORD, height=6, bg=BG_COLOR, fg=FG_COLOR, insertbackground=FG_COLOR, selectbackground=BUTTON_BG, selectforeground="white", font=("TkDefaultFont", 14))
        text_paned_window.add(self.active_text, stretch="always")

        # History Below Text area
        self.history_below_text = tk.Text(text_paned_window, wrap=tk.WORD, height=3, state=tk.DISABLED, bg=BG_COLOR, fg=FG_COLOR, selectbackground=BUTTON_BG, selectforeground="white", font=("TkDefaultFont", 11))
        text_paned_window.add(self.history_below_text, stretch="always")

        # Right Frame for Buttons
        button_frame = tk.Frame(main_paned_window, bg=BG_COLOR)
        main_paned_window.add(button_frame, width=150, stretch="never") # Fixed width for buttons

        # Arrange buttons vertically
        button_frame.pack_propagate(False) # Prevent frame from resizing to buttons
        button_frame.grid_columnconfigure(0, weight=1) # Center buttons

        # Status label
        self.status_label = tk.Label(button_frame, text="Idle", bg=BG_COLOR, fg=STATUS_FG, font=("TkDefaultFont", 12))
        self.status_label.grid(row=0, column=0, pady=(10, 20), sticky="ew")

        # Record/Stop button
        self.toggle_button = tk.Button(button_frame, text="Record", command=self.toggle_recording, bg=BUTTON_BG, fg=BUTTON_FG, activebackground=BUTTON_BG, activeforeground=BUTTON_FG, font=("TkDefaultFont", 12))
        self.toggle_button.grid(row=1, column=0, pady=10, sticky="ew")

        # Edit/Save button
        self.edit_save_button = tk.Button(button_frame, text="Edit", command=self.toggle_edit_mode, bg=BUTTON_BG, fg=BUTTON_FG, activebackground=BUTTON_BG, activeforeground=BUTTON_FG, font=("TkDefaultFont", 12))
        self.edit_save_button.grid(row=2, column=0, pady=10, sticky="ew")

        # Settings button (initially visible)
        self.settings_button = tk.Button(button_frame, text="Settings", command=self.open_settings, bg=BUTTON_BG, fg=BUTTON_FG, activebackground=BUTTON_BG, activeforeground=BUTTON_FG, font=("TkDefaultFont", 12))
        self.settings_button.grid(row=3, column=0, pady=10, sticky="ew")

        # Restore button (initially hidden)
        self.restore_button = tk.Button(button_frame, text="Restore", command=self.restore_text_content, bg=BUTTON_BG, fg=BUTTON_FG, activebackground=BUTTON_BG, activeforeground=BUTTON_FG, font=("TkDefaultFont", 12))
        # Don't grid it initially, will grid when edit mode is active

    def toggle_recording(self):
        if not hasattr(self, 'model'): # Check if model loaded successfully
            print("Vosk model not loaded. Cannot start recording.")
            return

        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        if self.edit_mode:
            self.toggle_edit_mode() # Exit edit mode if active

        self.is_recording = True
        self.toggle_button.config(text="Stop") # Change button text to Stop
        self.status_label.config(text="Listening...", fg=STATUS_FG)

        # Clear active text and reset history position if not already at the end
        current_active_text = self.active_text.get("1.0", tk.END).strip()
        if current_active_text and (self.history_position == -1 or current_active_text != self.text_history[self.history_position]):
             # If active text is not the current history entry, clear it for new recording
             self.active_text.delete("1.0", tk.END)

        self.history_position = len(self.text_history) # Set position to end for new entry

        # Start recording thread
        self.recording_thread = threading.Thread(target=self.record_audio)
        self.recording_thread.daemon = True
        self.recording_thread.start()

    def stop_recording(self):
        self.is_recording = False
        self.toggle_button.config(text="Record") # Change button text back to Record
        self.status_label.config(text="Processing...", fg=STATUS_FG) # Indicate processing might still happen

        # Put a sentinel value in the queue to signal the processing thread to stop
        self.audio_queue.put(None)

    def record_audio(self):
        try:
            with sd.InputStream(samplerate=self.samplerate, channels=1, dtype='int16') as stream:
                while self.is_recording:
                    audio_chunk = stream.read(self.samplerate // 10)[0] # Read audio chunk (correct unpacking)
                    self.audio_queue.put(audio_chunk)
        except Exception as e:
            print(f"Error during audio recording: {e}")
            self.status_label.config(text=f"Recording Error: {e}", fg="red")
            self.stop_recording() # Stop recording on error

    def process_audio(self):
        current_text = ""
        silence_counter = 0

        while True:
            try:
                # Get audio chunk with a small timeout
                audio_chunk = self.audio_queue.get(timeout=0.1)
                if audio_chunk is None: # Check for sentinel value
                    break # Exit the loop if sentinel is received
            except queue.Empty:
                # If queue is empty, continue waiting unless recording has stopped
                if not self.is_recording:
                    # If recording has stopped and queue is empty, break the loop
                    break
                time.sleep(0.05) # Small sleep if queue is empty but still recording
                continue # Continue loop to check queue again

            # Process the audio
            if self.recognizer.AcceptWaveform(audio_chunk.tobytes()):
                # Final result received
                result = json.loads(self.recognizer.Result())
                if result["text"]:
                    current_text = result["text"]
                    self.save_to_history(current_text) # Save to history and update active text/clipboard
                    current_text = "" # Clear current text for next segment
                # Reset silence counter after a final result
                silence_counter = 0
            else:
                # Partial result received
                partial_result = json.loads(self.recognizer.PartialResult())
                if partial_result["partial"]:
                    current_text = partial_result["partial"]
                    # Update active text thread-safely
                    self.root.after(0, lambda text=current_text: self.update_active_text_display_only(text))

                # Check if there's speech in this chunk (for silence detection)
                energy = np.mean(np.abs(audio_chunk))
                if energy > SILENCE_THRESHOLD:
                    silence_counter = 0
                    self.last_speech_time = time.time()
                else:
                    silence_counter += 1

                # Check if silence exceeds threshold (only after processing partial results)
                silence_duration = silence_counter * (self.samplerate // 10) / self.samplerate
                if silence_duration > MAX_SILENCE_DURATION:
                    if current_text:
                        # If there's partial text and silence threshold is met, finalize it
                        self.save_to_history(current_text)
                        current_text = "" # Clear current text after saving
                    # Reset silence counter
                    silence_counter = 0


        # After recording stops and queue is empty, process any final result
        final_result = json.loads(self.recognizer.FinalResult())
        if final_result["text"] and final_result["text"] != current_text:
             self.save_to_history(final_result["text"])

        # Ensure status is set to Idle after processing finishes
        self.root.after(0, lambda: self.status_label.config(text="Idle", fg=STATUS_FG))

    def update_active_text_display_only(self, text):
         # Update active text display without affecting clipboard or history position
         self.active_text.config(state=tk.NORMAL)
         self.active_text.delete("1.0", tk.END)
         self.active_text.insert("1.0", text)
         if not self.edit_mode:
              self.active_text.config(state=tk.DISABLED)


    def update_active_text(self, text):
        # This method is called when navigating history or saving a final result
        self.active_text.config(state=tk.NORMAL)
        self.active_text.delete("1.0", tk.END)
        self.active_text.insert("1.0", text)
        if self.clipboard_controlled_by_app:
             pyperclip.copy(text)
        if not self.edit_mode:
             self.active_text.config(state=tk.DISABLED)


    def save_to_history(self, text):
        if text.strip(): # Only save non-empty text after stripping whitespace
            # If we were viewing a history entry, and new text was transcribed,
            # the new text replaces the active_text but is a new entry.
            # If we were at the end of history or a fresh start, just append.
            if self.history_position == len(self.text_history):
                 self.text_history.append(text.strip())
            elif self.history_position != -1:
                 # If editing a history entry and saved, replace it
                 self.text_history[self.history_position] = text.strip()
                 # After saving an edit, we stay at that history position
            else:
                 # This case should ideally not happen if start_recording clears active_text
                 # and sets history_position correctly, but as a fallback:
                 self.text_history.append(text.strip())
                 self.history_position = len(self.text_history) - 1 # Move to the new end

            # Ensure history size is maintained
            while len(self.text_history) > MAX_HISTORY_ENTRIES:
                self.text_history.popleft()

            # After saving a new entry, the active text is the last one
            self.history_position = len(self.text_history) - 1

            self.update_history_display() # Update the history display widgets
            self.update_active_text(self.text_history[self.history_position]) # Ensure active text is the saved one

    def update_history_display(self):
        # Update history_above_text
        self.history_above_text.config(state=tk.NORMAL)
        self.history_above_text.delete("1.0", tk.END)
        above_index = self.history_position - 1
        if 0 <= above_index < len(self.text_history):
            self.history_above_text.insert(tk.END, self.text_history[above_index])
            self.history_above_text.config(fg=FG_COLOR)
        else:
            self.history_above_text.insert("1.0", "say something") # Insert at 1.0 to avoid newline
            self.history_above_text.config(fg=EMPTY_TEXT_COLOR)
        self.history_above_text.config(state=tk.DISABLED)

        # Update history_below_text
        self.history_below_text.config(state=tk.NORMAL)
        self.history_below_text.delete("1.0", tk.END)
        below_index = self.history_position + 1
        if 0 <= below_index < len(self.text_history):
            self.history_below_text.insert(tk.END, self.text_history[below_index])
            self.history_below_text.config(fg=FG_COLOR)
        elif len(self.text_history) == MAX_HISTORY_ENTRIES and self.history_position == MAX_HISTORY_ENTRIES - 1:
             # If at the end of a full history, show the oldest entry below
             self.history_below_text.insert("1.0", self.text_history[0]) # Insert at 1.0 to avoid newline
             self.history_below_text.config(fg=FG_COLOR)
        else:
            self.history_below_text.insert("1.0", "say something") # Insert at 1.0 to avoid newline
            self.history_below_text.config(fg=EMPTY_TEXT_COLOR)
        self.history_below_text.config(state=tk.DISABLED)

    def navigate_history_left(self, event=None):
        # Left arrow navigates back in history (towards older entries)
        if self.edit_mode: return "break" # Prevent navigation in edit mode
        if self.history_position > 0:
            self.history_position -= 1
            self.update_active_text(self.text_history[self.history_position])
            self.update_history_display()
        return "break" # Prevent default arrow key behavior

    def navigate_history_right(self, event=None):
        # Right arrow navigates forward in history (towards newer entries)
        if self.edit_mode: return "break" # Prevent navigation in edit mode
        if self.history_position < len(self.text_history) - 1:
            self.history_position += 1
            self.update_active_text(self.text_history[self.history_position])
            self.update_history_display()
        elif self.history_position == len(self.text_history) - 1 and len(self.text_history) == MAX_HISTORY_ENTRIES:
             # If at the end of a full history, wrap around to the oldest entry
             self.history_position = 0
             self.update_active_text(self.text_history[self.history_position])
             self.update_history_display()
        return "break" # Prevent default arrow key behavior

    def scroll_active_text_up(self, event=None):
        # Custom scroll up for active_text (line by line)
        if self.edit_mode: return # Allow default behavior in edit mode
        self.active_text.yview_scroll(-1, "units")
        return "break" # Prevent default arrow key behavior

    def scroll_active_text_down(self, event=None):
        # Custom scroll down for active_text (line by line)
        if self.edit_mode: return # Allow default behavior in edit mode
        self.active_text.yview_scroll(1, "units")
        return "break" # Prevent default arrow key behavior

    def toggle_edit_mode(self):
        if not self.edit_mode:
            # Enter Edit Mode
            self.edit_mode = True
            self.edit_save_button.config(text="Save")
            self.set_active_text_editable(True)
            self.restore_text = self.active_text.get("1.0", tk.END).strip() # Save current text for restore
            self.settings_button.grid_forget() # Hide settings
            self.restore_button.grid(row=3, column=0, pady=10, sticky="ew") # Show restore
            self.status_label.config(text="Editing...", fg="yellow")
        else:
            # Exit Edit Mode (Save)
            self.edit_mode = False
            self.edit_save_button.config(text="Edit")
            self.set_active_text_editable(False)
            current_text = self.active_text.get("1.0", tk.END).strip()
            if current_text != self.restore_text:
                 # Text was changed, save the updated text to history
                 if self.history_position != -1 and 0 <= self.history_position < len(self.text_history):
                      self.text_history[self.history_position] = current_text # Replace in history
                 elif current_text: # If it's new text not from history, add it
                      self.save_to_history(current_text) # This will also update history_position and display
                 self.update_history_display() # Ensure history display reflects changes
                 self.update_active_text(current_text) # Update clipboard with saved text
                 self.status_label.config(text="Saved.", fg=STATUS_FG)
                 self.root.after(2000, lambda: self.status_label.config(text="Idle" if not self.is_recording else "Listening...", fg=STATUS_FG))
            else:
                 # Text was not changed, functionally just exit edit mode
                 self.status_label.config(text="Idle" if not self.is_recording else "Listening...", fg=STATUS_FG)

            self.restore_button.grid_forget() # Hide restore
            self.settings_button.grid(row=3, column=0, pady=10, sticky="ew") # Show settings

    def restore_text_content(self):
        if self.edit_mode:
            self.update_active_text(self.restore_text)
            self.status_label.config(text="Restored.", fg=STATUS_FG)
            self.root.after(2000, lambda: self.status_label.config(text="Editing...", fg="yellow"))

    def set_active_text_editable(self, editable):
        if editable:
            self.active_text.config(state=tk.NORMAL)
            self.active_text.config(insertbackground=FG_COLOR) # Show cursor
        else:
            self.active_text.config(state=tk.DISABLED)
            self.active_text.config(insertbackground=BG_COLOR) # Hide cursor (set to background color)

    def on_active_text_focus(self, event=None):
        # When active_text gets focus, application regains clipboard control
        self.clipboard_controlled_by_app = True
        # Ensure clipboard is updated with current active text
        current_text = self.active_text.get("1.0", tk.END).strip()
        if current_text:
             pyperclip.copy(current_text)

    def on_active_text_unfocus(self, event=None):
        # When active_text loses focus, application releases clipboard control
        self.clipboard_controlled_by_app = False

    def on_external_copy(self, event=None):
        # When Ctrl+C or Right Click happens in active_text,
        # assume user is doing an external copy.
        # Temporarily release clipboard control.
        self.clipboard_controlled_by_app = False
        # Allow the default copy event to proceed
        return

    def open_settings(self):
        # Placeholder for settings window
        print("Settings button clicked (placeholder)")
        # TODO: Implement settings window for mic selection, visual effects, theme

if __name__ == "__main__":
    root = tk.Tk()
    app = DictationApp(root)
    root.mainloop()
