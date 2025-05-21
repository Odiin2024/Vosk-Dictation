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

# Path to your model
MODEL_PATH_RELATIVE = "../models/vosk-model-en-us-0.22"
MODEL_PATH_CWD = os.path.join(os.path.dirname(__file__), MODEL_PATH_RELATIVE)
MODEL_PATH = MODEL_PATH_CWD if os.path.exists(MODEL_PATH_CWD) else MODEL_PATH_RELATIVE

class DictationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Dictation Tool")
        self.root.geometry("600x400")
        
        # Setup variables
        self.is_recording = False
        self.text_history = []
        self.history_position = -1
        self.silence_timer = 0
        self.last_speech_time = time.time()
        self.audio_queue = queue.Queue()
        
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
        button_frame = tk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Start/Stop button
        self.toggle_button = tk.Button(button_frame, text="Start Recording", command=self.toggle_recording)
        self.toggle_button.pack(side=tk.LEFT, padx=5)
        
        # Copy to clipboard button
        copy_btn = tk.Button(button_frame, text="Copy to Clipboard", command=self.copy_to_clipboard)
        copy_btn.pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_label = tk.Label(button_frame, text="Idle")
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
        # Use a PanedWindow to hold the main text area and the history area
        self.paned_window = PanedWindow(self.root, orient=VERTICAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Main Text area
        self.text_area = scrolledtext.ScrolledText(self.paned_window, wrap=tk.WORD)
        self.paned_window.add(self.text_area)

        # History Text area
        self.history_area = scrolledtext.ScrolledText(self.paned_window, wrap=tk.WORD, height=5, state=tk.DISABLED)
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
        self.is_recording = True
        self.toggle_button.config(text="Stop Recording")
        self.status_label.config(text="Listening...")
        
        # Save current text to history if not empty
        current_text = self.text_area.get("1.0", tk.END).strip()
        if current_text:
            self.save_to_history(current_text)
            self.text_area.delete("1.0", tk.END)
            
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
                if energy > 100:  # Adjust threshold as needed
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
                        # Auto copy to clipboard
                        pyperclip.copy(current_text)
                        self.save_to_history(current_text)
                        current_text = ""
                        self.text_area.delete("1.0", tk.END)
                
                else:
                    partial_result = json.loads(self.recognizer.PartialResult())
                    if partial_result.get("partial"):
                        current_text = partial_result["partial"]
                        self.update_text(current_text)
                
                # Check if silence exceeds threshold (3-10 seconds)
                silence_duration = silence_counter * (self.samplerate // 10) / self.samplerate
                if silence_duration > 5:  # 5 seconds of silence
                    if current_text:
                        self.save_to_history(current_text)
                        current_text = ""
                        self.text_area.delete("1.0", tk.END)
                    # Reset silence counter
                    silence_counter = 0
            else:
                time.sleep(0.1)
        
        # After loop ends, set status to Idle
        self.root.after(0, lambda: self.status_label.config(text="Idle"))
    
    def update_text(self, text):
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", text)
        
    def save_to_history(self, text):
        if text.strip():  # Only save non-empty text
            self.text_history.append(text)
            # Keep only last 6 entries
            if len(self.text_history) > 6:
                self.text_history.pop(0)
            self.history_position = len(self.text_history) - 1
            self.update_history_display()
        
    def update_history_display(self):
        self.history_area.config(state=tk.NORMAL)
        self.history_area.delete("1.0", tk.END)
        for i, entry in enumerate(self.text_history):
            self.history_area.insert(tk.END, f"{i+1}: {entry}\n")
        self.history_area.config(state=tk.DISABLED)
        self.history_area.see(tk.END)

    def navigate_history_up(self, event=None):
        if self.text_history and self.history_position > 0:
            self.history_position -= 1
            self.update_text(self.text_history[self.history_position])
            
    def navigate_history_down(self, event=None):
        if self.text_history and self.history_position < len(self.text_history) - 1:
            self.history_position += 1
            self.update_text(self.text_history[self.history_position])
    
    def copy_to_clipboard(self):
        text = self.text_area.get("1.0", tk.END).strip()
        if text:
            pyperclip.copy(text)
            self.status_label.config(text="Copied to clipboard!")
            # Reset status after 2 seconds
            self.root.after(2000, lambda: self.status_label.config(text="Idle" if not self.is_recording else "Listening..."))

if __name__ == "__main__":
    root = tk.Tk()
    app = DictationApp(root)
    root.mainloop()
