import vosk
import json
import sounddevice as sd
import numpy as np

# Path to your model
MODEL_PATH = "../models/vosk-model-en-us-0.22"

def main():
    # Set up the model
    model = vosk.Model(MODEL_PATH)
    samplerate = 16000
    
    # Create a recognizer
    rec = vosk.KaldiRecognizer(model, samplerate)
    
    # Start audio recording
    print("Listening... (press Ctrl+C to stop)")
    with sd.InputStream(samplerate=samplerate, channels=1, dtype='int16') as stream:
        while True:
            audio_chunk = stream.read(samplerate // 10)[0]  # Smaller chunks for faster processing
            if rec.AcceptWaveform(audio_chunk.tobytes()):
                result = json.loads(rec.Result())
                if result["text"]:
                    print(f"You said: {result['text']}")
            else:
                # Print partial results too
                partial = json.loads(rec.PartialResult())
                if partial.get("partial") and partial["partial"]:
                    print(f"Partial: {partial['partial']}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user")
