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
FG_COLOR = "#CCCCCC"  # Light grey foreground for visibility
BUTTON_BG = "#555555"
BUTTON_FG = "#E0B0FF"
STATUS_FG = "#90EE90"  # Light green for status
PLACEHOLDER_FG = "#888888"  # Lighter grey to simulate 60% transparency for placeholders

# Constants
MAX_ARCHIVE_ENTRIES = 6
SILENCE_THRESHOLD = 100  # Adjust threshold as needed
MAX_SILENCE_DURATION = 4  # Silence duration in seconds

class DictationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Dictation Tool")
        self.root.geometry("650x520")  # Fixed size to fit dimensions
        self.root.resizable(False, False)  # Prevent resizing of the main window
        self.root.configure(bg=BG_COLOR)
        
        # Setup variables
        self.is_recording = False
        self.vdic_history = list()  # Unlimited entries for vdicHistory1 to vdicHistoryn
        self.archive = deque(maxlen=MAX_ARCHIVE_ENTRIES)  # Archive entries limited to 6 (archive1 to archive6)
        self.history_position = -1  # -1 means not showing history
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
        
        # Toggle Record/Stop button
        self.toggle_button = tk.Button(button_frame, text="Record", command=self.toggle_recording, bg=BUTTON_BG, fg=BUTTON_FG)
        self.toggle_button.pack(side=tk.LEFT, padx=5)
        
        # Edit button
        self.edit_button = tk.Button(button_frame, text="Edit", command=self.toggle_edit_mode, bg=BUTTON_BG, fg=BUTTON_FG)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_label = tk.Label(button_frame, text="Idle", bg=BG_COLOR, fg=STATUS_FG)
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
        # Use a Frame to hold vertical layout for text areas with proper alignment
        text_frame = tk.Frame(self.root, bg=BG_COLOR)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)  # Adjusted padding to prevent left push
        
        # Archive1 Text area (top, aspect ratio 13:4)
        self.archive1_area = tk.Text(text_frame, wrap=tk.WORD, height=4, state=tk.DISABLED, bg=BG_COLOR, fg=FG_COLOR)
        self.archive1_area.pack(fill=tk.X, pady=2)
        self.archive1_area.config(state=tk.NORMAL)
        self.archive1_area.insert("2.0", "\n<< -- Archive Entry 1 -- >>")
        self.archive1_area.tag_configure("center", justify='center')
        self.archive1_area.tag_configure("placeholder", foreground=PLACEHOLDER_FG)
        self.archive1_area.tag_add("center", "2.0", "2.end")
        self.archive1_area.tag_add("placeholder", "2.0", "2.end")
        self.archive1_area.config(state=tk.DISABLED)
        
        # Spacer frame between Archive1 and vdicHistory
        spacer1 = tk.Frame(text_frame, height=5, bg=BG_COLOR)
        spacer1.pack(fill=tk.X)
        
        # vdicHistory Text area (middle, aspect ratio 13:8)
        self.history_area = tk.Text(text_frame, wrap=tk.WORD, height=8, state=tk.DISABLED, bg=BG_COLOR, fg=FG_COLOR)
        self.history_area.pack(fill=tk.X, pady=2)
        
        # Spacer frame between vdicHistory and Archive6
        spacer2 = tk.Frame(text_frame, height=5, bg=BG_COLOR)
        spacer2.pack(fill=tk.X)
        
        # Archive6 Text area (bottom, aspect ratio 13:4)
        self.archive6_area = tk.Text(text_frame, wrap=tk.WORD, height=4, state=tk.DISABLED, bg=BG_COLOR, fg=FG_COLOR)
        self.archive6_area.pack(fill=tk.X, pady=2)
        self.archive6_area.config(state=tk.NORMAL)
        self.archive6_area.insert("2.0", "\n<< -- Archive Entry 6 -- >>")
        self.archive6_area.tag_configure("center", justify='center')
        self.archive6_area.tag_configure("placeholder", foreground=PLACEHOLDER_FG)
        self.archive6_area.tag_add("center", "2.0", "2.end")
        self.archive6_area.tag_add("placeholder", "2.0", "2.end")
        self.archive6_area.config(state=tk.DISABLED)

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
        self.toggle_button.config(text="Stop")
        self.status_label.config(text="Listening...")
        
        # Push current vdicHistory content to archive if there is input
        if self.vdic_history:
            self.push_to_archive()
            
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
        self.toggle_button.config(text="Record")
        self.status_label.config(text="Processing...")
        
        # Safeguard to remove 'the' if it's the only text generated
        if self.vdic_history:
            last_entry = self.vdic_history[-1].strip().lower()
            # Check if the last entry is only 'the' or multiple instances of 'the'
            if last_entry and last_entry.replace('the', '').replace(' ', '') == '':
                self.vdic_history.pop()
                self.history_position = len(self.vdic_history) - 1 if self.vdic_history else -1
                self.update_history_display()
        
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
                        # Auto save to vdicHistory on final result
                        self.save_to_vdic_history(current_text)
                        current_text = ""
                
                else:
                    partial_result = json.loads(self.recognizer.PartialResult())
                    if partial_result.get("partial"):
                        current_text = partial_result["partial"]
                
                # Check if silence exceeds threshold
                silence_duration = silence_counter * (self.samplerate // 10) / self.samplerate
                if silence_duration > MAX_SILENCE_DURATION:
                    if current_text:
                        self.save_to_vdic_history(current_text)
                        current_text = ""
                    # Reset silence counter
                    silence_counter = 0
            else:
                time.sleep(0.1)
        
        # After loop ends, save any remaining text to vdicHistory
        if current_text:
            self.save_to_vdic_history(current_text)
            
        # Set status to Idle
        self.root.after(0, lambda: self.status_label.config(text="Idle"))
    
    def save_to_vdic_history(self, text):
        if text.strip():  # Only save non-empty text
            # Ignore if the text is only 'the' or multiple instances of 'the'
            if text.strip().lower().replace('the', '').replace(' ', '') == '':
                return
            # Add new text as the last entry (most recent at bottom)
            self.vdic_history.append(text)
            self.history_position = len(self.vdic_history) - 1  # Set position to the last entry
            # Update clipboard with the latest entry, removing trailing 'the'
            clipboard_text = text.rstrip()
            if clipboard_text.lower().endswith(' the'):
                clipboard_text = clipboard_text[:-4].rstrip()
            pyperclip.copy(clipboard_text if clipboard_text else text)
            self.update_history_display()
        
    def update_history_display(self):
        # Update vdicHistory area
        self.history_area.config(state=tk.NORMAL)
        self.history_area.delete("1.0", tk.END)
        # Display vdicHistory entries without numbering as a contiguous block
        for entry in self.vdic_history:
            self.history_area.insert(tk.END, f"{entry}\n")
        self.history_area.config(state=tk.DISABLED)

        # Update Archive1 area
        self.archive1_area.config(state=tk.NORMAL)
        self.archive1_area.delete("1.0", tk.END)
        if len(self.archive) > 0:
            self.archive1_area.insert(tk.END, self.archive[0])
        else:
            self.archive1_area.insert("2.0", "\n<< -- Archive Entry 1 -- >>")
            self.archive1_area.tag_configure("center", justify='center')
            self.archive1_area.tag_configure("placeholder", foreground=PLACEHOLDER_FG)
            self.archive1_area.tag_add("center", "2.0", "2.end")
            self.archive1_area.tag_add("placeholder", "2.0", "2.end")
        self.archive1_area.config(state=tk.DISABLED)

        # Update Archive6 area
        self.archive6_area.config(state=tk.NORMAL)
        self.archive6_area.delete("1.0", tk.END)
        if len(self.archive) == MAX_ARCHIVE_ENTRIES:
            self.archive6_area.insert(tk.END, self.archive[-1])
        else:
            self.archive6_area.insert("2.0", "\n<< -- Archive Entry 6 -- >>")
            self.archive6_area.tag_configure("center", justify='center')
            self.archive6_area.tag_configure("placeholder", foreground=PLACEHOLDER_FG)
            self.archive6_area.tag_add("center", "2.0", "2.end")
            self.archive6_area.tag_add("placeholder", "2.0", "2.end")
        self.archive6_area.config(state=tk.DISABLED)

    def navigate_history_up(self, event=None):
        if self.vdic_history and self.history_position > 0:
            self.history_position -= 1
            # No UI update since Active Speech Window is removed, but conceptually moving up to older entries
        
    def navigate_history_down(self, event=None):
        if self.vdic_history and self.history_position < len(self.vdic_history) - 1:
            self.history_position += 1
            # No UI update since Active Speech Window is removed, but conceptually moving down to newer entries
    
    def toggle_edit_mode(self):
        if not self.edit_mode:
            # Enter Edit Mode, load the latest vdicHistory entry if available
            if self.vdic_history:
                self.edit_mode = True
                self.edit_button.config(text="Save")
                self.history_area.config(state=tk.NORMAL)
                self.history_position = len(self.vdic_history) - 1  # Set to the latest entry
                self.status_label.config(text="Editing...")
            else:
                self.status_label.config(text="No history to edit")
                self.root.after(2000, lambda: self.status_label.config(text="Idle" if not self.is_recording else "Listening..."))
        else:
            # Exit Edit Mode, save changes to vdicHistory
            self.edit_mode = False
            self.edit_button.config(text="Edit")
            current_text = self.history_area.get("1.0", tk.END).strip()
            if current_text and self.history_position >= 0 and self.history_position < len(self.vdic_history):
                # Update the history entry with edited text
                self.vdic_history[self.history_position] = current_text
                # Update clipboard, removing trailing 'the'
                clipboard_text = current_text.rstrip()
                if clipboard_text.lower().endswith(' the'):
                    clipboard_text = clipboard_text[:-4].rstrip()
                pyperclip.copy(clipboard_text if clipboard_text else current_text)
                self.update_history_display()
            self.history_area.config(state=tk.DISABLED)
            self.status_label.config(text="Saved")
            self.root.after(2000, lambda: self.status_label.config(text="Idle" if not self.is_recording else "Listening..."))

    def push_to_archive(self):
        if self.vdic_history:
            # Push the latest vdicHistory content to archive1 only if there is text
            archive_content = "\n".join(self.vdic_history)  # Combine all current history entries as one archive entry
            if archive_content.strip():
                self.archive.appendleft(archive_content)
            # Clear vdicHistory for new recording
            self.vdic_history = []
            self.history_position = -1
            self.update_history_display()

if __name__ == "__main__":
    root = tk.Tk()
    app = DictationApp(root)
    root.mainloop()
