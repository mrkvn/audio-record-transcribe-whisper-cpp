import multiprocessing
import signal
import sys
import threading
import time
import wave
from datetime import datetime

import numpy as np
import pyaudio

# Parameters
FORMAT = pyaudio.paInt16  # Audio format (16-bit PCM)
CHANNELS = 2  # Number of channels (stereo)
# RATE = 44100  # Sampling rate (samples per second)
RATE = 16000  # Sampling rate (samples per second)
CHUNK = 1024  # Buffer size
THRESHOLD = 2  # Lowered audio threshold for starting the recording
SILENCE_DURATION = 3  # Duration of silence (in seconds) to stop recording

# Initialize PyAudio
audio = pyaudio.PyAudio()

# List available input devices and find a suitable one
device_index = None
for i in range(audio.get_device_count()):
    device_info = audio.get_device_info_by_index(i)
    if device_info["maxInputChannels"] >= CHANNELS:
        device_index = i
        print(f"Using device {i}: {device_info['name']}")
        break

if device_index is None:
    print("No suitable input device found.")
    exit()

# Open stream
stream = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    input_device_index=device_index,
    frames_per_buffer=CHUNK,
)

silence_start_time = None
start_time = None
frames = []
recording_started = False


def save_recording(frames, start_time):
    if frames:
        output_filename = start_time.strftime("%Y-%m-%d-%H%M%S") + ".wav"
        wf = wave.open(output_filename, "wb")
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
        wf.close()
        print(f"Recording saved to {output_filename}")
        return output_filename


def process_audio(file_path):
    # Placeholder function for audio processing
    print(f"Processing {file_path}")
    # Implement your audio processing logic here


def save_and_process_recording(frames, start_time):
    output_filename = save_recording(frames, start_time)
    if output_filename:
        process = multiprocessing.Process(target=process_audio, args=(output_filename,))
        process.start()


def save_recording_thread(frames, start_time):
    thread = threading.Thread(target=save_and_process_recording, args=(frames, start_time))
    thread.start()


# Handle termination gracefully
def signal_handler(sig, frame):
    print("Terminating recording...")
    if recording_started:
        save_recording(frames, start_time)
    stream.stop_stream()
    stream.close()
    audio.terminate()
    sys.exit(0)


def main():
    global silence_start_time, start_time, frames, recording_started

    print("Monitoring for audio... Press CTRL-C to stop.")
    signal.signal(signal.SIGINT, signal_handler)

    # Monitor audio input for a threshold
    while True:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)

            # Ensure audio_data contains valid values
            if len(audio_data) == 0:
                continue

            # Calculate RMS and ensure it's valid
            rms = np.sqrt(np.mean(audio_data**2))

            if rms > THRESHOLD:  # not silent
                silence_start_time = None
                frames.append(data)
                if not recording_started:
                    start_time = datetime.now()
                    start_timestamp = time.time()
                    print(f"Audio detected, starting recording at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    recording_started = True
                    frames = []  # Reset frames for new recording
                else:
                    if time.time() - start_timestamp >= 3:
                        save_recording_thread(frames, start_time)
                        recording_started = False
                        frames = []
                        silence_start_time = None
            elif recording_started:  # silence while recording
                frames.append(data)
                if time.time() - start_timestamp >= 3:
                    save_recording_thread(frames, start_time)
                    recording_started = False
                    frames = []
                    silence_start_time = None
                elif silence_start_time is None:
                    silence_start_time = time.time()
                elif time.time() - silence_start_time >= SILENCE_DURATION:
                    print(f"Silence detected, stopping recording at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    save_recording_thread(frames, start_time)
                    recording_started = False
                    frames = []
                    silence_start_time = None
            else:
                silence_start_time = None

        except Exception as e:
            print(f"An error occurred: {e}")
            break

    # Clean up
    signal_handler(None, None)


if __name__ == "__main__":
    main()
