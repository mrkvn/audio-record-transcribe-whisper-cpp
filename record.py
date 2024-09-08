import sys
import threading
import wave

import pyaudio

# Parameters
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100
CHUNK = 1024
WAVE_OUTPUT_FILENAME = "output.wav"

# Initialize PyAudio
audio = pyaudio.PyAudio()

# List available input devices and find a suitable one
device_index = None
for i in range(audio.get_device_count()):
    device_info = audio.get_device_info_by_index(i)
    if device_info["maxInputChannels"] >= CHANNELS:
        device_index = i
        break

if device_index is None:
    print("No suitable input device found.")
    sys.exit(0)

# Open stream
stream = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    input_device_index=device_index,
    frames_per_buffer=CHUNK,
)

print("Recording... Press Ctrl+C to stop.")

frames = []
recording = True


def record_audio():
    while recording:
        data = stream.read(CHUNK)
        frames.append(data)


# Start recording in a separate thread
recording_thread = threading.Thread(target=record_audio)
recording_thread.start()

try:
    while True:
        pass
except KeyboardInterrupt:
    print("Recording stopped.")
    recording = False
    recording_thread.join()

    # Stop and close the stream
    stream.stop_stream()
    stream.close()
    audio.terminate()

    # Save the recorded data as a WAV file
    wf = wave.open(WAVE_OUTPUT_FILENAME, "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b"".join(frames))
    wf.close()

print("Recording saved to", WAVE_OUTPUT_FILENAME)
