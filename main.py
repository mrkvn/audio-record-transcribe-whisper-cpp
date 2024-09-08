import multiprocessing
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import wave
from datetime import datetime

import numpy as np
import pyaudio

recordings_dir = "recordings"
os.makedirs(recordings_dir, exist_ok=True)
processed_dir = "processed"
os.makedirs(processed_dir, exist_ok=True)

# Parameters
FORMAT = pyaudio.paInt16  # Audio format (16-bit PCM)
CHANNELS = 2  # Number of channels (stereo)
# RATE = 44100  # Sampling rate (samples per second)
RATE = 16000  # Sampling rate (samples per second)
CHUNK = 1024  # Buffer size
THRESHOLD = 2  # Lowered audio threshold for starting the recording
SILENCE_DURATION = 3  # Duration of silence (in seconds) to stop recording
RECORDING_INTERVAL = 3  # Interval to save recordings in seconds

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
        output_full_path = f"{recordings_dir}/{output_filename}"
        wf = wave.open(output_full_path, "wb")
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
        wf.close()
        print(f"Recording saved to {output_filename}")
        return output_full_path


def process_audio(file_path):
    print("processing audio", file_path)
    command = [
        "/Users/mrkvn/code/repo/github/whisper.cpp/main",  # whisper cpp main path
        "-m",
        "/Users/mrkvn/code/repo/github/whisper.cpp/models/ggml-medium.en.bin",  # whisper cpp model path
        "-f",
        file_path,
        "-otxt",
    ]
    # subprocess.run(command, capture_output=True, text=True)
    subprocess.run(command, capture_output=True, text=True)
    shutil.move(file_path, f"processed/{file_path.split('/')[-1]}")  # Move processed file to processed directory


def save_and_process_recording(frames, start_time):
    output_full_path = save_recording(frames, start_time)
    if output_full_path:
        process = multiprocessing.Process(target=process_audio, args=(output_full_path,))
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


def process_transcription():
    while True:
        for file in sorted(os.listdir(recordings_dir)):
            if file.endswith(".txt"):
                transcription = ""
                with open(f"{recordings_dir}/{file}", "r") as f:
                    for line in f:
                        if line.strip().startswith("["):
                            continue
                        transcription += line.strip() + "\n"
                with open("transcription.txt", "a") as tf:
                    tf.write(transcription)
                    tf.flush()
                os.remove(f"{recordings_dir}/{file}")


def accumulate_transcription():
    p = multiprocessing.Process(target=process_transcription)
    p.start()


def main():
    global silence_start_time, start_time, frames, recording_started
    accumulate_transcription()

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
                    if time.time() - start_timestamp >= RECORDING_INTERVAL:
                        save_recording_thread(frames, start_time)
                        recording_started = False
                        frames = []
                        silence_start_time = None
            elif recording_started:  # silence while recording
                frames.append(data)
                if time.time() - start_timestamp >= RECORDING_INTERVAL:
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
