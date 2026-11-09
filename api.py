
from flask import Flask, jsonify
from flask_cors import CORS

import main as assistant
import re
import threading


app = Flask(__name__)
CORS(app)


# ============================================================
# GLOBAL API STATE
# ============================================================

current_status = "ready"

status_lock = threading.Lock()
generation_lock = threading.Lock()

current_command_id = 0


# ============================================================
# COMMAND GENERATION MANAGEMENT
# ============================================================

def get_command_id():
    with generation_lock:
        return current_command_id


def is_current(command_id):
    with generation_lock:
        return command_id == current_command_id


def update_status(status, command_id=None):
    global current_status

    with status_lock:

        if command_id is not None and not is_current(command_id):
            return

        current_status = status


def interrupt_current_command():
    global current_command_id

    with generation_lock:
        current_command_id += 1
        new_id = current_command_id

    # Invalidate previous speech and commands
    assistant.set_speech_generation(new_id)

    # Stop currently running speech
    assistant.stop_speaking()

    update_status("ready", new_id)

    print("[INTERRUPT] Previous command cancelled:", new_id)

    return new_id


# ============================================================
# BACKGROUND SPEECH
# ============================================================

def speak_in_background(response, command_id):

    def speak():

        if not is_current(command_id):
            return

        assistant.set_speech_context(command_id)

        if not is_current(command_id):
            return

        assistant.speak(response)

    threading.Thread(
        target=speak,
        daemon=True,
        name=f"speech-{command_id}"
    ).start()


# ============================================================
# PROCESS COMMAND
# ============================================================

def process_command(command, command_id):

    cmd = command.lower().strip()

    if not cmd:
        return "Please speak a command.", "empty", None

    if not is_current(command_id):
        return None, None, None

    # Suppress internal speak() calls from main.py functions.
    # The final response will be spoken by speak_in_background().
    assistant.set_speech_context(-1)

    response = None
    intent = "fallback_ai"
    metadata = None

    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    if "time" in cmd:

        response = assistant.get_time()
        intent = "time"

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    elif "date" in cmd:

        response = assistant.get_date()
        intent = "date"

    # --------------------------------------------------------
    # STOP ALARM
    # --------------------------------------------------------

    elif any(x in cmd for x in (
        "stop alarm",
        "alarm stop",
        "turn off alarm",
        "stop ringing"
    )):

        assistant.stop_alarm()

        response = "Alarm stopped."
        intent = "alarm_stop"

    # --------------------------------------------------------
    # SET ALARM
    # --------------------------------------------------------

    elif "alarm" in cmd or "wake me" in cmd:

        alarm_time = assistant.parse_alarm_time(cmd)

        if alarm_time:

            assistant.set_alarm(alarm_time)

            response = "Your alarm has been set."

        else:

            response = (
                "Please specify a valid alarm time, "
                "for example 7:30 am."
            )

        intent = "alarm"

    # --------------------------------------------------------
    # WEATHER
    # --------------------------------------------------------

    elif "weather" in cmd or "temperature" in cmd:

        city = re.sub(
            r"\b(what's|what is|weather|in|the|today|"
            r"tell me|show me|please|current|temperature|"
            r"how|is|it|like|outside|of|now)\b",
            "",
            cmd
        ).strip()

        city = re.sub(r"\s+", " ", city).strip()

        if city:

            print("[WEATHER]", city)

            response = assistant.get_weather(city)

            metadata = {"city": city}

        else:

            response = (
                "Please specify a city name, "
                "for example Delhi or Mumbai."
            )

        intent = "weather"

    # --------------------------------------------------------
    # NEWS
    # --------------------------------------------------------

    elif any(x in cmd for x in (
        "news",
        "headline",
        "headlines"
    )):

        location = re.sub(
            r"\b(what's|what is|the|give me|"
            r"tell me|show me|latest|today|top|news|"
            r"headline|headlines|in|from)\b",
            "",
            cmd
        ).strip()

        response = assistant.get_news(location or None)

        intent = "news"

        metadata = {
            "location": location or "India"
        }

    # --------------------------------------------------------
    # STOP MUSIC
    # --------------------------------------------------------

    elif "stop music" in cmd or "pause music" in cmd:

        response = assistant.stop_apple_music()

        intent = "music_stop"

    # --------------------------------------------------------
    # YOUTUBE SONG
    # --------------------------------------------------------

    elif "play" in cmd and "youtube" in cmd:

        song = re.sub(
            r"\b(play|on youtube|youtube)\b",
            "",
            cmd
        ).strip()

        if song:
            response = assistant.youtube_player.play(song)
        else:
            response = "Please specify a song name."

        intent = "youtube_song"

    # --------------------------------------------------------
    # APPLE MUSIC
    # --------------------------------------------------------

    elif "apple music" in cmd:

        song = re.sub(
            r"\b(play|on apple music|on apple)\b",
            "",
            cmd
        ).strip()

        if song:

            response = assistant.play_apple_music_song(song)

        else:

            assistant.play_random_music()

            response = (
                "Playing a random song from your "
                "Apple Music library."
            )

        intent = "apple_music"

    # --------------------------------------------------------
    # RANDOM MUSIC
    # --------------------------------------------------------

    elif cmd in (
        "music",
        "play music",
        "play some music"
    ):

        assistant.play_random_music()

        response = (
            "Playing a random song from your "
            "Apple Music library."
        )

        intent = "music"

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------

    elif any(x in cmd for x in (
        "calculator",
        "calc",
        "youtube",
        "google",
        "chrome",
        "whatsapp",
        "notepad",
        "editor",
        "textedit"
    )):

        handled = assistant.open_app(cmd)

        response = (
            "Your application command was executed."
            if handled
            else "Could not execute application command."
        )

        intent = "open_app"

    # --------------------------------------------------------
    # AI QUESTION
    # --------------------------------------------------------

    else:

        response = assistant.ask_gpt(command)

        intent = "ai_question"

    if response is None:

        response = "Command could not be processed."

    # --------------------------------------------------------
    # CHECK CANCELLATION BEFORE LOGGING
    # --------------------------------------------------------

    if not is_current(command_id):

        print("[IGNORED] Stale command processing result")

        return None, None, None

    # --------------------------------------------------------
    # DATABASE LOGGING
    # --------------------------------------------------------

    assistant.log_interaction(
        command,
        intent,
        str(response),
        metadata
    )

    return str(response), intent, metadata


# ============================================================
# HOME ROUTE
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "success": True,
        "message": "Voice Assistant API is running"
    })


# ============================================================
# STATUS ROUTE
# ============================================================

@app.route("/api/status", methods=["GET"])
def get_status():

    with status_lock:

        return jsonify({
            "status": current_status
        })


# ============================================================
# INTERRUPT ROUTE
# ============================================================

@app.route("/api/interrupt", methods=["POST"])
def interrupt():

    new_id = interrupt_current_command()

    return jsonify({
        "success": True,
        "command_id": new_id,
        "message": "Previous command interrupted."
    })


# ============================================================
# VOICE COMMAND ROUTE
# ============================================================

@app.route("/api/voice-command", methods=["POST"])
def handle_command():

    global current_command_id

    # Start a new command generation
    with generation_lock:

        current_command_id += 1

        command_id = current_command_id

    # Invalidate previous speech
    assistant.set_speech_generation(command_id)

    # Stop previous TTS
    assistant.stop_speaking()

    try:

        update_status("listening", command_id)

        # Listen without wake word
        command = assistant.listen(
            command_id=command_id
        )

        # Check cancellation
        if not is_current(command_id):

            return jsonify({
                "success": False,
                "cancelled": True
            }), 409

        if not command or command == "network_error":

            update_status("error", command_id)

            return jsonify({
                "success": False,
                "error": (
                    "Could not recognize your voice. "
                    "Please try again."
                )
            }), 400

        print("[You]", command)

        update_status("processing", command_id)

        # Process command
        response, intent, metadata = process_command(
            command,
            command_id
        )

        # Check whether a newer command started
        if not is_current(command_id):

            print("[IGNORED] Old command response")

            return jsonify({
                "success": False,
                "cancelled": True
            }), 409

        if response is None:

            return jsonify({
                "success": False,
                "cancelled": True
            }), 409

        print("[Assistant]", response)

        update_status("response", command_id)

        # Speak response in background
        speak_in_background(
            response,
            command_id
        )

        return jsonify({
            "success": True,
            "transcript": command,
            "response": response,
            "intent": intent,
            "metadata": metadata
        })

    except Exception as e:

        assistant.log_error(str(e))

        print("[ERROR]", e)

        if is_current(command_id):

            update_status("error", command_id)

            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

        return jsonify({
            "success": False,
            "cancelled": True
        }), 409


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True
    )
