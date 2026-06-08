# =========================
# FRIDAY AI ASSISTANT
# Ollama + Memory + Coqui TTS
# =========================

import os
import json
import time
import queue
import vosk
import sounddevice as sd
import requests

from dotenv import load_dotenv
from TTS.api import TTS

# =========================
# LOAD ENV
# =========================

load_dotenv()

# =========================
# SETTINGS
# =========================

WAKE_WORD = "hey friday"
MEMORY_FILE = "memory.json"
MODEL_PATH = "vosk-model-small-en-us-0.15"

# =========================
# LOAD VOSK
# =========================

print("Loading Vosk model...")

model = vosk.Model(MODEL_PATH)
recognizer = vosk.KaldiRecognizer(model, 16000)

print("Vosk loaded!")

# =========================
# LOAD COQUI TTS
# =========================

print("Loading FRIDAY voice...")

tts = TTS(
    model_name="tts_models/en/ljspeech/tacotron2-DDC",
    progress_bar=True
)

print("Voice model loaded!")

# =========================
# AUDIO QUEUE
# =========================

audio_queue = queue.Queue()

def callback(indata, frames, time_info, status):
    audio_queue.put(bytes(indata))

# =========================
# MEMORY FUNCTIONS
# =========================

MAX_MEMORY_ITEMS = 50

def load_memory():

    if not os.path.exists(MEMORY_FILE):
        return []

    try:

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except (json.JSONDecodeError, ValueError):

        return []

def save_memory(memory):

    trimmed = memory[-MAX_MEMORY_ITEMS:]

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, indent=2)

def add_memory(user_text, friday_text):

    memory = load_memory()

    memory.append({
        "user": user_text,
        "friday": friday_text,
        "timestamp": int(time.time())
    })

    save_memory(memory)

def clear_memory():
    save_memory([])

def summarize_memory():

    memory = load_memory()

    if not memory:
        return "I have no saved memories yet."

    items = [
        f"{entry['user']} — {entry['friday']}"
        for entry in memory[-5:]
    ]

    return " ; ".join(items)

def handle_memory_command(command):

    if (
        "clear memory" in command
        or "forget everything" in command
        or "forget memory" in command
    ):

        clear_memory()

        return "Memory cleared, sir."

    if (
        "show memory" in command
        or "what do you remember" in command
        or "recall memory" in command
    ):

        return summarize_memory()

    return None

# =========================
# COQUI SPEAK
# =========================

def speak(text):

    try:

        text = text.replace(",", "...")
        text = text.replace("sir.", "sir...")

        print(f"\nFRIDAY: {text}\n")

        wav = tts.tts(text=text)

        sd.play(wav, samplerate=22050)
        sd.wait()

    except Exception as e:

        print("TTS Error:", e)

# =========================
# AI RESPONSE (OLLAMA)
# =========================

def ask_ollama(prompt):

    memory = load_memory()
    recent_memory = memory[-5:]

    memory_text = ""

    for item in recent_memory:

        memory_text += f"""
User: {item['user']}
FRIDAY: {item['friday']}
"""

    system_prompt = f"""
You are FRIDAY from Iron Man.

Your personality:
- calm
- intelligent
- futuristic
- concise
- loyal assistant

Rules:
- Keep responses short
- Under 15 words whenever possible
- Speak naturally like FRIDAY
- Avoid long explanations
- Sound like an AI assistant

Previous conversations:
{memory_text}

User: {prompt}
"""

    try:

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "gemma:2b",
                "prompt": system_prompt,
                "stream": False
            }
        )

        data = response.json()

        print("Ollama raw:", data)

        if "response" in data:
            return data["response"].strip()

        return "Local systems are responding abnormally, sir."

    except Exception as e:

        print("Ollama Error:", e)

        return "Local AI systems are currently offline, sir."

# =========================
# WAKE WORD LISTENER
# =========================

def listen_for_wake_word():

    print(f"Listening for '{WAKE_WORD}'...")

    while True:

        data = audio_queue.get()

        if recognizer.AcceptWaveform(data):

            result = json.loads(recognizer.Result())

            text = result.get("text", "").lower()

            if text:

                print("Heard:", text)

                if (
                    "hey friday" in text
                    or "hi friday" in text
                    or "hello friday" in text
                    or ("hey" in text and "friday" in text)
                ):

                    speak("Yes sir?")

                    return

# =========================
# COMMAND LISTENER
# =========================

def listen_for_command(timeout=25):

    print("Awaiting command...")

    start_time = time.time()

    while time.time() - start_time < timeout:

        data = audio_queue.get()

        if recognizer.AcceptWaveform(data):

            result = json.loads(recognizer.Result())

            text = result.get("text", "").lower()

            if text:

                print("Command:", text)

                return text

    return None

# =========================
# MAIN
# =========================

def main():

    speak("FRIDAY systems online.")

    # permanent microphone stream
    with sd.RawInputStream(
        samplerate=16000,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=callback
    ):

        while True:

            # wait for wake word
            listen_for_wake_word()

            conversation_active = True

            # conversation mode
            while conversation_active:

                command = listen_for_command()

                # timeout
                if not command:

                    speak("Returning to standby mode, sir.")

                    conversation_active = False

                    break

                # shutdown
                if "shutdown" in command:

                    speak("Shutting down systems. Goodbye, sir.")

                    return

                # memory commands
                memory_response = handle_memory_command(command)

                if memory_response is not None:

                    speak(memory_response)

                    continue

                # AI response
                reply = ask_ollama(command)

                add_memory(command, reply)

                speak(reply)

                time.sleep(0.5)

# =========================
# START
# =========================

if __name__ == "__main__":

    main()