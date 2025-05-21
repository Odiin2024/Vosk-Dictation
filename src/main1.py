import vosk
import json
import sounddevice as sd
import numpy as np
import pyperclip
import tkinter as tk
from tkinter import scrolledtext, PanedWindow, VERTICAL
import threading
import time
import queue
import os
from collections import deque

# Path to your model
MODEL_PATH_RELATIVE = "../models/vosk-model-en-us-0.22"
MODEL_PATH_CWD = os.path.join(os.path.dirname(__file__), MODEL_PATH_RELATIVE)
MODEL_PATH = MODEL_PATH_CWD if os.path.exists(MODEL_PATH_CWD) else MODEL_PATH_RELATIVE

# Styling for Dark Mode
BG_COLOR = "#333333"  # Dark grey background
FG_COLOR = "#E0B0FF"  # Mauve foreground
BUTTON_BG = "#555555"
BUTTON_FG = "#E0B0FF"
STATUS_FG = "#90EE90"  # Light green for status

# Constants
MAX_HISTORY_ENTRIES = 6
SILENCE_THRESHOLD = 100  # Adjust threshold as needed
MAX_SILENCE_DURATION = 4  # Silence duration in seconds

class DictationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Dictation Tool")
        self.root.geometry("600x400")
        self.root.configure(bg=BG_COLOR)
        
        # Setup variables
        self.is_recording = False
        self.vdic_history = deque(maxlen=MAX_HISTORY_ENTRIES)  # History entries as vdicHistory1 to vdicHistory6
        self.history_position = -1  # -1 means Active Speech Window is not showing history
        self.silence_timer = 0
        self.last_speech_time = time.time()
        self.audio_queue = queue.Queue()
        self.edit_mode = False
        
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
            self.root.destroy()  # Close the application if model loading fails
            return

        self.samplerate = 16000
        self.recognizer = vosk.KaldiRecognizer(self.model, self.samplerate)
        
        # Bind keyboard shortcuts
        self.root.bind('<Control-Up>', self.navigate_history_up)
        self.root.bind('<Control-Down>', self.navigate_history_down)
        
    def create_widgets(self):
        # Top frame for buttons
        button_frame = tk.Frame(self.root, bg=BG_COLOR)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Start/Stop button
        self.toggle_button = tk.Button(button_frame, text="Start Recording", command=self.toggle_recording, bg=BUTTON_BG, fg=BUTTON_FG)
        self.toggle_button.pack(side=tk.LEFT, padx=5)
        
        # Edit button
        self.edit_button = tk.Button(button_frame, text="Edit", command=self.toggle_edit_mode, bg=BUTTON_BG, fg=BUTTON_FG)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_label = tk.Label(button_frame, text="Idle", bg=BG_COLOR, fg=STATUS_FG)
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
        # Use a PanedWindow to hold the Active Speech Window and the vdicHistory area
        self.paned_window = PanedWindow(self.root, orient=VERTICAL, bg=BG_COLOR)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Active Speech Window (mainHistory accumulation)
        self.active_speech_window = scrolledtext.ScrolledText(self.paned_window, wrap=tk.WORD, bg=BG_COLOR, fg=FG_COLOR)
        self.paned_window.add(self.active_speech_window)

        # vdicHistory Text area
        self.history_area = scrolledtext.ScrolledText(self.paned_window, wrap=tk.WORD, height=5, state=tk.DISABLED, bg=BG_COLOR, fg=FG_COLOR)
        self.paned_window.add(self.history_area)

    def toggle_recording(self):
        if not hasattr(self, 'model'):  # Check if model loaded successfully
            print("Vosk model not loaded. Cannot start recording.")
            return

        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
            
    def start_recording(self):
        if self.edit_mode:
            self.toggle_edit_mode()  # Exit edit mode if active
            
        self.is_recording = True
        self.toggle_button.config(text="Stop Recording")
        self.status_label.config(text="Listening...")
        
        # Clear Active Speech Window for new recording if not in history
        if self.history_position == -1:
            self.active_speech_window.delete("1.0", tk.END)
            
        # Start recording thread
        self.recording_thread = threading.Thread(target=self.record_audio)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self.process_audio)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
    def stop_recording(self):
        self.is_recording = False
        self.toggle_button.config(text="Start Recording")
        self.status_label.config(text="Processing...")
        
    def record_audio(self):
        with sd.InputStream(samplerate=self.samplerate, channels=1, dtype='int16') as stream:
            while self.is_recording:
                audio_chunk = stream.read(self.samplerate // 10)[0]
                self.audio_queue.put(audio_chunk)
        
    def process_audio(self):
        current_text = ""
        silence_counter = 0
        
        while self.is_recording or not self.audio_queue.empty():
            if not self.audio_queue.empty():
                audio_chunk = self.audio_queue.get()
                
                # Check if there's speech in this chunk
                energy = np.mean(np.abs(audio_chunk))
                if energy > SILENCE_THRESHOLD:  # Adjust threshold as needed
                    silence_counter = 0
                    self.last_speech_time = time.time()
                else:
                    silence_counter += 1
                
                # Process the audio
                if self.recognizer.AcceptWaveform(audio_chunk.tobytes()):
                    result = json.loads(self.recognizer.Result())
                    if result.get("text"):
                        current_text = result["text"]
                        self.update_text(current_text)
                        # Auto save to vdicHistory on final result
                        self.save_to_vdic_history(current_text)
                        current_text = ""
                        self.active_speech_window.delete("1.0", tk.END)
                
                else:
                    partial_result = json.loads(self.recognizer.PartialResult())
                    if partial_result.get("partial"):
                        current_text = partial_result["partial"]
                        self.update_text(current_text)
                
                # Check if silence exceeds threshold
                silence_duration = silence_counter * (self.samplerate // 10) / self.samplerate
                if silence_duration > MAX_SILENCE_DURATION:
                    if current_text:
                        self.save_to_vdic_history(current_text)
                        current_text = ""
                        self.active_speech_window.delete("1.0", tk.END)
                    # Reset silence counter
                    silence_counter = 0
            else:
                time.sleep(0.1)
        
        # After loop ends, save any remaining text to vdicHistory
        if current_text:
            self.save_to_vdic_history(current_text)
            self.active_speech_window.delete("1.0", tk.END)
            
        # Set status to Idle
        self.root.after(0, lambda: self.status_label.config(text="Idle"))
    
    def update_text(self, text):
        self.active_speech_window.delete("1.0", tk.END)
        self.active_speech_window.insert("1.0", text)
        
    def save_to_vdic_history(self, text):
        if text.strip():  # Only save non-empty text
            # Add new text as vdicHistory1 (most recent entry)
            self.vdic_history.appendleft(text)
            self.history_position = 0  # Set position to vdicHistory1
            # Update clipboard with vdicHistory1
            pyperclip.copy(text)
            self.update_history_display()
        
    def update_history_display(self):
        self.history_area.config(state=tk.NORMAL)
        self.history_area.delete("1.0", tk.END)
        # Display vdicHistory entries without numbering as a contiguous block
        for entry in self.vdic_history:
            self.history_area.insert(tk.END, f"{entry}\n")
        self.history_area.config(state=tk.DISABLED)
        self.history_area.see(tk.END)

    def navigate_history_up(self, event=None):
        if self.vdic_history and self.history_position > 0:
            self.history_position -= 1
            self.update_text(list(self.vdic_history)[self.history_position])
            
    def navigate_history_down(self, event=None):
        if self.vdic_history and self.history_position < len(self.vdic_history) - 1:
            self.history_position += 1
            self.update_text(list(self.vdic_history)[self.history_position])
    
    def toggle_edit_mode(self):
        if not self.edit_mode:
            # Enter Edit Mode, load vdicHistory1 if available
            if self.vdic_history:
                self.edit_mode = True
                self.edit_button.config(text="Save")
                self.active_speech_window.config(state=tk.NORMAL)
                self.history_position = 0  # Set to vdicHistory1
                self.update_text(list(self.vdic_history)[0])
                self.status_label.config(text="Editing...")
            else:
                self.status_label.config(text="No history to edit")
                self.root.after(2000, lambda: self.status_label.config(text="Idle" if not self.is_recording else "Listening..."))
        else:
            # Exit Edit Mode, save changes to vdicHistory
            self.edit_mode = False
            self.edit_button.config(text="Edit")
            current_text = self.active_speech_window.get("1.0", tk.END).strip()
            if current_text and self.history_position >= 0 and self.history_position < len(self.vdic_history):
                # Update the history entry with edited text
                history_list = list(self.vdic_history)
                history_list[self.history_position] = current_text
                self.vdic_history = deque(history_list, maxlen=MAX_HISTORY_ENTRIES)
                pyperclip.copy(current_text)  # Update clipboard
                self.update_history_display()
            self.active_speech_window.config(state=tk.DISABLED)
            self.status_label.config(text="Saved")
            self.root.after(2000, lambda: self.status_label.config(text="Idle" if not self.is_recording else "Listening..."))

if __name__ == "__main__":
    root = tk.Tk()
    app = DictationApp(root)
    root.mainloop()
