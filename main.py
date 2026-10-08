
import datetime
import json
import os
import platform
import random
import re
import shutil
import signal
from dotenv import load_dotenv
import sqlite3
import subprocess
import threading
import time
import webbrowser
import mysql.connector
import requests
import speech_recognition as sr
from groq import Groq
load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MUSIC_FOLDER = os.path.expanduser("~/Music")
ALARM_TONE = "/System/Library/Sounds/Glass.aiff"

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE", "assistant_logs"),
    "autocommit": True
}


SYSTEM = platform.system().lower()

client = Groq(api_key=GROQ_API_KEY)


# ============================================================
# GLOBAL STATE
# ============================================================

USE_MYSQL = True

speech_lock = threading.Lock()
speech_process = None

player_lock = threading.Lock()
player_process = None
audio_playing = False

alarm_process_global = None
alarm_stop_flag = False


# ============================================================
# DATABASE
# ============================================================

def get_db_conn():
    global USE_MYSQL

    if USE_MYSQL:
        try:
            return mysql.connector.connect(**DB_CONFIG), "mysql"

        except Exception as e:
            print(
                "[DB] MySQL connection failed. "
                "Using SQLite fallback:",
                e
            )
            USE_MYSQL = False

    return sqlite3.connect(
        "assistant_fallback.db",
        check_same_thread=False
    ), "sqlite"


def ensure_tables():
    conn, kind = get_db_conn()
    cur = conn.cursor()

    if kind == "mysql":

        cur.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                command_text TEXT NOT NULL,
                intent VARCHAR(100) NOT NULL,
                response_text TEXT,
                metadata JSON
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INT AUTO_INCREMENT PRIMARY KEY,
                error_message TEXT NOT NULL
            )
        """)

    else:

        cur.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                command_text TEXT,
                intent TEXT,
                response_text TEXT,
                metadata TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                error_message TEXT
            )
        """)

    conn.commit()
    cur.close()
    conn.close()


def log_interaction(
    command,
    intent,
    response,
    metadata=None
):
    try:
        conn, kind = get_db_conn()
        cur = conn.cursor()

        meta_json = (
            json.dumps(metadata)
            if metadata
            else None
        )

        if kind == "mysql":

            cur.execute(
                """
                INSERT INTO interactions
                (command_text, intent, response_text, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    command,
                    intent,
                    response,
                    meta_json
                )
            )

        else:

            cur.execute(
                """
                INSERT INTO interactions
                (timestamp, command_text, intent,
                 response_text, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(datetime.datetime.now()),
                    command,
                    intent,
                    response,
                    meta_json
                )
            )

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print("[LOG ERROR]", e)


def log_error(message):
    try:
        conn, kind = get_db_conn()
        cur = conn.cursor()

        if kind == "mysql":

            cur.execute(
                """
                INSERT INTO errors (error_message)
                VALUES (%s)
                """,
                (message,)
            )

        else:

            cur.execute(
                """
                INSERT INTO errors
                (timestamp, error_message)
                VALUES (?, ?)
                """,
                (
                    str(datetime.datetime.now()),
                    message
                )
            )

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print("[LOG ERROR]", e)


ensure_tables()


# ============================================================
# TEXT TO SPEECH
# ============================================================

def stop_speaking():
    global speech_process

    with speech_lock:
        process = speech_process
        speech_process = None

    if process and process.poll() is None:
        try:
            process.terminate()
            print("[Speech] Stopped.")
        except Exception as e:
            print("[TTS STOP ERROR]", e)


def speak(text):
    global speech_process

    clean = re.sub(
        r"(\*\*|\*|__|`)",
        "",
        str(text)
    )

    clean = re.sub(
        r"\s{2,}",
        " ",
        clean
    ).strip()

    if not clean:
        return

    print("[Assistant]", clean)

    try:
        with speech_lock:

            if (
                speech_process
                and speech_process.poll() is None
            ):
                speech_process.wait()

            speech_process = subprocess.Popen(
                [
                    "say",
                    "-v",
                    "Samantha",
                    "-r",
                    "190",
                    clean
                ]
            )

        speech_process.wait()

        with speech_lock:
            speech_process = None

    except Exception as e:
        print("[TTS ERROR]", e)
        log_error(f"TTS error: {e}")


# ============================================================
# SPEECH RECOGNITION
# ============================================================

def listen(language=None):
    recognizer = sr.Recognizer()

    recognizer.pause_threshold = 1.0
    recognizer.phrase_threshold = 0.3
    recognizer.non_speaking_duration = 0.5

    try:
        with sr.Microphone() as source:

            print(
                "Listening...",
                datetime.datetime.now().strftime("%H:%M:%S")
            )

            audio = recognizer.listen(
                source,
                phrase_time_limit=10
            )

        if language:

            text = recognizer.recognize_google(
                audio,
                language=language
            )

        else:

            text = recognizer.recognize_google(audio)

        print("[You]", text)

        return text.lower()

    except sr.UnknownValueError:
        return None

    except sr.RequestError as e:
        print("[STT Network Error]", e)
        return "network_error"

    except Exception as e:
        print("[STT Error]", e)
        return None


# ============================================================
# WEATHER
# ============================================================

def get_weather(city):
    try:
        url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?q={city}"
            f"&appid={WEATHER_API_KEY}"
            "&units=metric"
        )

        response = requests.get(
            url,
            timeout=8
        )

        data = response.json()

        if data.get("cod") != 200:
            return "City not found."

        temperature = data["main"]["temp"]
        description = data["weather"][0]["description"]

        return (
            f"The temperature in {city} is "
            f"{temperature}°C with {description}."
        )

    except Exception as e:
        log_error(f"Weather error: {e}")
        return "Error fetching weather."


# ============================================================
# NEWS
# ============================================================

def get_news(location=None):
    try:

        if not location:

            url = (
                "https://gnews.io/api/v4/top-headlines"
                "?country=in"
                "&lang=en"
                "&max=5"
                f"&apikey={GNEWS_API_KEY}"
            )

        else:

            url = (
                "https://gnews.io/api/v4/search"
                f"?q={requests.utils.quote(location)}"
                "&lang=en"
                "&max=5"
                "&sortby=publishedAt"
                f"&apikey={GNEWS_API_KEY}"
            )

        response = requests.get(
            url,
            timeout=8
        )

        print("[NEWS STATUS]", response.status_code)

        data = response.json()

        if "errors" in data:

            error_message = data["errors"][0].get(
                "message",
                "Unknown GNews error."
            )

            print("[GNEWS API ERROR]", error_message)

            return f"GNews Error: {error_message}"

        articles = data.get("articles", [])

        if not articles:

            if location:
                return (
                    f"No news found for "
                    f"{location} right now."
                )

            return "No news found right now."

        headlines = []

        for article in articles[:5]:

            title = article.get(
                "title",
                "No title"
            )

            headlines.append(title)

        if location:

            return (
                f"Latest news for {location}: "
                + " | ".join(headlines)
            )

        return (
            "Top headlines: "
            + " | ".join(headlines)
        )

    except requests.exceptions.RequestException as e:

        print("[NEWS REQUEST ERROR]", e)

        log_error(
            f"News request error: {e}"
        )

        return "Could not connect to the news service."

    except Exception as e:

        print("[NEWS ERROR]", e)

        log_error(
            f"News error: {e}"
        )

        return "Error fetching news."


# ============================================================
# AI / GROQ
# ============================================================

def ask_gpt(question):
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful voice assistant. "
                        "Answer directly and clearly. "
                        "Give short, simple answers suitable "
                        "for voice conversation. "
                        "Usually answer in 1 to 3 sentences. "
                        "If the user asks for code or a detailed "
                        "explanation, provide only what is necessary. "
                        "Do not ask unnecessary questions."
                    )
                },
                {
                    "role": "user",
                    "content": question
                }
            ]
        )

        return response.choices[0].message.content

    except Exception as e:

        print("[AI ERROR]", e)

        log_error(
            f"AI error: {e}"
        )

        return (
            "Sorry, I couldn't get an "
            "answer from AI right now."
        )


# ============================================================
# MUSIC PLAYER
# ============================================================

def _start_local_player(path):
    global player_process
    global audio_playing

    try:

        with player_lock:

            if (
                player_process
                and player_process.poll() is None
            ):

                try:

                    os.killpg(
                        os.getpgid(player_process.pid),
                        signal.SIGTERM
                    )

                except Exception:

                    try:
                        player_process.terminate()
                    except Exception:
                        pass

                player_process = None

            audio_playing = True

            if shutil.which("mpv"):

                player_process = subprocess.Popen(
                    [
                        "mpv",
                        "--no-terminal",
                        "--really-quiet",
                        path
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp
                )

            elif shutil.which("paplay"):

                player_process = subprocess.Popen(
                    [
                        "paplay",
                        path
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp
                )

            else:

                print(
                    f"Cannot play {path}. "
                    "Install mpv or paplay."
                )

                audio_playing = False
                return None

            def monitor(process):

                global player_process
                global audio_playing

                try:
                    process.wait()
                except Exception:
                    pass

                with player_lock:
                    player_process = None
                    audio_playing = False

            threading.Thread(
                target=monitor,
                args=(player_process,),
                daemon=True
            ).start()

            return player_process

    except Exception as e:

        log_error(
            f"Local player error: {e}"
        )

        audio_playing = False
        return None


def play_local_music():
    try:

        files = [
            file
            for file in os.listdir(MUSIC_FOLDER)
            if file.lower().endswith(
                (
                    ".mp3",
                    ".wav",
                    ".ogg",
                    ".m4a",
                    ".flac"
                )
            )
        ]

        if not files:
            return "No music found in your music folder."

        song = random.choice(files)

        path = os.path.join(
            MUSIC_FOLDER,
            song
        )

        process = _start_local_player(path)

        if process:
            return f"Playing local music: {song}"

        return "Failed to start local player."

    except Exception as e:

        log_error(
            f"Local music error: {e}"
        )

        return "Error playing local music."


def play_specific_local(path):

    if not os.path.exists(path):
        return "File not found."

    process = _start_local_player(path)

    if process:
        return f"Playing: {os.path.basename(path)}"

    return "Failed to start local player."


def pause_music():
    try:

        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "Music" to pause'
            ],
            check=False
        )

        return "Music paused."

    except Exception as e:

        log_error(
            f"Pause music error: {e}"
        )

        return "Could not pause music."


def resume_music():
    try:

        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "Music" to play'
            ],
            check=False
        )

        return "Music resumed."

    except Exception as e:

        log_error(
            f"Resume music error: {e}"
        )

        return "Could not resume music."


def stop_apple_music():
    try:

        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "Music" to stop'
            ],
            check=False
        )

        return "Music stopped."

    except Exception as e:

        log_error(
            f"Stop music error: {e}"
        )

        return "Could not stop music."
def play_apple_music_song(song):

    if SYSTEM != "darwin":
        return "Apple Music is available only on macOS."

    try:

        safe_song = (
            song
            .replace("\\", "\\\\")
            .replace('"', '\\"')
        )

        script = f'''
        tell application "Music"
            activate

            set allTracks to every track of library playlist 1
            set foundTrack to missing value

            repeat with currentTrack in allTracks

                try
                    set trackName to name of currentTrack

                    if trackName contains "{safe_song}" then
                        set foundTrack to contents of currentTrack
                        exit repeat
                    end if

                end try

            end repeat

            if foundTrack is not missing value then
                play foundTrack
                return "Playing {safe_song} on Apple Music."
            else
                return "Song not found in Apple Music library."
            end if

        end tell
        '''

        result = subprocess.run(
            [
                "osascript",
                "-e",
                script
            ],
            capture_output=True,
            text=True,
            check=False
        )

        output = result.stdout.strip()

        if result.returncode != 0:

            print(
                "[APPLE MUSIC ERROR]",
                result.stderr
            )

            return "Could not play the song on Apple Music."

        if output == "Song not found in Apple Music library.":

            return (
                f"I could not find {song} "
                "in your Apple Music library."
            )

        if output:
            return output

        return f"Playing {song} on Apple Music."

    except Exception as e:

        print("[APPLE MUSIC ERROR]", e)

        log_error(
            f"Apple Music error: {e}"
        )

        return "Could not play the song on Apple Music."

def play_random_music():

    script = '''
    tell application "Music"
        activate

        set songList to every track of library playlist 1

        if (count of songList) > 0 then
            set randomTrack to some item of songList
            play randomTrack
            return "Playing a random song from your Apple Music library."
        else
            return "Your Apple Music library is empty."
        end if
    end tell
    '''

    try:

        result = subprocess.run(
            [
                "osascript",
                "-e",
                script
            ],
            capture_output=True,
            text=True,
            check=False
        )

        output = result.stdout.strip()

        if output:
            print("[APPLE MUSIC]", output)
            speak(output)
        else:
            print(
                "[APPLE MUSIC ERROR]",
                result.stderr
            )
            speak("Could not play music.")

    except Exception as e:

        print("[MUSIC ERROR]", e)

        log_error(
            f"Music play error: {e}"
        )

        speak("Could not play music.")


# ============================================================
# YOUTUBE
# ============================================================

class YouTubeMiniPlayer:

    def __init__(self):
        self.current_url = None

    def play(self, query=None):

        if query:
            self.current_url = (
                "https://www.youtube.com/results"
                f"?search_query={query.replace(' ', '+')}"
            )

        if not self.current_url:
            return "No song specified."

        webbrowser.open(self.current_url)

        return f"Playing {query} on YouTube."

    def stop(self):

        self.current_url = None

        return (
            "Stopped YouTube playback "
            "(close browser tab manually)."
        )


youtube_player = YouTubeMiniPlayer()


# ============================================================
# APPLICATION CONTROL
# ============================================================

def close_calculator():

    try:

        if SYSTEM == "darwin":

            subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "Calculator" to quit'
                ],
                check=False
            )

            return "Closed Calculator."

        return "Calculator close not supported on this OS."

    except Exception as e:

        log_error(
            f"Close calculator error: {e}"
        )

        return "Could not close Calculator."


def open_app(command):

    try:

        cmd = command.lower()

        # Calculator
        if "calculator" in cmd or "calc" in cmd:

            if any(
                word in cmd
                for word in ("close", "exit", "quit")
            ):

                speak(close_calculator())
                return True

            speak("Opening calculator.")

            if SYSTEM == "darwin":

                subprocess.Popen(
                    [
                        "open",
                        "-a",
                        "Calculator"
                    ]
                )

            else:

                calc_path = "/usr/bin/gnome-calculator"

                if os.path.exists(calc_path):
                    subprocess.Popen([calc_path])
                else:
                    speak("Calculator app not found.")

            return True

        # YouTube
        if "youtube" in cmd:

            if any(
                word in cmd
                for word in ("close", "exit", "quit")
            ):

                if SYSTEM == "darwin":

                    subprocess.run(
                        [
                            "osascript",
                            "-e",
                            '''
                            tell application "Google Chrome"
                                repeat with w in windows
                                    repeat with t in tabs of w
                                        if URL of t contains "youtube.com" then
                                            close t
                                            return
                                        end if
                                    end repeat
                                end repeat
                            end tell
                            '''
                        ]
                    )

                speak("Closed YouTube.")
                return True

            webbrowser.open("https://youtube.com")
            speak("Opening YouTube.")
            return True
        # Google / Chrome
        if "google" in cmd or "chrome" in cmd:

            if any(
                word in cmd
                for word in ("close", "exit", "quit")
            ):

                if SYSTEM == "darwin":

                    subprocess.run(
                        [
                            "osascript",
                            "-e",
                            '''
                            tell application "Google Chrome"
                                repeat with w in windows
                                    repeat with t in tabs of w
                                        if URL of t contains "google.com" then
                                            close t
                                            return
                                        end if
                                    end repeat
                                end repeat
                            end tell
                            '''
                        ]
                    )

                speak("Closed Google.")
                return True

            chrome_path = (
                shutil.which("google-chrome")
                or shutil.which("chromium")
            )

            if chrome_path:
                subprocess.Popen([chrome_path])
            else:
                webbrowser.open("https://google.com")

            speak("Opening Google.")
            return True

        # WhatsApp
        if "whatsapp" in cmd:

            if any(
                word in cmd
                for word in ("close", "exit", "quit")
            ):

                if SYSTEM == "darwin":

                    subprocess.run(
                        [
                            "osascript",
                            "-e",
                            '''
                            tell application "Google Chrome"
                                repeat with w in windows
                                    repeat with t in tabs of w
                                        if URL of t contains "web.whatsapp.com" then
                                            close t
                                            return
                                        end if
                                    end repeat
                                end repeat
                            end tell
                            '''
                        ]
                    )

                speak("Closed WhatsApp.")
                return True

            webbrowser.open(
                "https://web.whatsapp.com"
            )

            speak("Opening WhatsApp Web.")
            return True

        # Text editor
        if any(
            word in cmd
            for word in (
                "notepad",
                "editor",
                "text editor",
                "textedit"
            )
        ):

            if any(
                word in cmd
                for word in ("close", "exit", "quit")
            ):

                if SYSTEM == "darwin":

                    subprocess.run(
                        [
                            "osascript",
                            "-e",
                            'tell application "TextEdit" to quit'
                        ]
                    )

                speak("Closed text editor.")
                return True

            speak("Opening text editor.")

            if SYSTEM == "darwin":

                subprocess.Popen(
                    [
                        "open",
                        "-a",
                        "TextEdit"
                    ]
                )

            else:

                editor_path = (
                    shutil.which("gedit")
                    or shutil.which("nano")
                )

                if editor_path:
                    subprocess.Popen([editor_path])
                else:
                    speak("No text editor found.")

            return True

    except Exception as e:

        log_error(
            f"Open application error: {e}"
        )

        speak("Failed to open application.")

    return False


# ============================================================
# ALARM
# ============================================================

def stop_alarm():

    global alarm_stop_flag
    global alarm_process_global

    alarm_stop_flag = True

    try:

        if alarm_process_global:

            if alarm_process_global.poll() is None:
                alarm_process_global.terminate()

            alarm_process_global = None

    except Exception as e:

        log_error(
            f"Stop alarm error: {e}"
        )

    subprocess.run(
        ["pkill", "-9", "afplay"],
        check=False
    )

    subprocess.run(
        ["pkill", "-9", "mpv"],
        check=False
    )

    print("[Alarm] Stopped.")

    speak("Alarm stopped.")


def parse_alarm_time(text):

    if not text:
        return None

    text = text.lower().strip()

    # Relative time: minutes
    match = re.search(
        r"(?:in|after|for)\s+(\d+)\s*"
        r"(?:minute|minutes|min|mins)\b",
        text
    )

    if match:

        minutes = int(match.group(1))

        alarm_time = (
            datetime.datetime.now()
            + datetime.timedelta(minutes=minutes)
        )

        return alarm_time.strftime("%H:%M")

    # Relative time: hours
    match = re.search(
        r"(?:in|after|for)\s+(\d+)\s*"
        r"(?:hour|hours|hr|hrs)\b",
        text
    )

    if match:

        hours = int(match.group(1))

        alarm_time = (
            datetime.datetime.now()
            + datetime.timedelta(hours=hours)
        )

        return alarm_time.strftime("%H:%M")

    # Specific clock time
    match = re.search(
        r"(\d{1,2})(?::|\.| )?(\d{2})?"
        r"\s*(a\.?m\.?|p\.?m\.?)?",
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    hour = int(match.group(1))

    minute = (
        int(match.group(2))
        if match.group(2)
        else 0
    )

    ampm = match.group(3)

    if ampm:
        ampm = (
            ampm
            .replace(".", "")
            .lower()
        )

    if ampm == "pm" and hour != 12:
        hour += 12

    if ampm == "am" and hour == 12:
        hour = 0

    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"

    return None


def _alarm_thread(
    alarm_time_str,
    alarm_file=None
):

    global alarm_stop_flag
    global alarm_process_global

    alarm_stop_flag = False

    hour, minute = map(
        int,
        alarm_time_str.split(":")
    )

    now = datetime.datetime.now()

    alarm_time = now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )

    if alarm_time <= now:
        alarm_time += datetime.timedelta(days=1)

    while not alarm_stop_flag:

        now = datetime.datetime.now()

        if now >= alarm_time:

            print("RINGING!")

            sound_file = (
                alarm_file
                if alarm_file
                else ALARM_TONE
            )

            try:

                if shutil.which("afplay"):

                    while not alarm_stop_flag:

                        alarm_process_global = (
                            subprocess.Popen(
                                [
                                    "afplay",
                                    sound_file
                                ],
                                start_new_session=True
                            )
                        )

                        while (
                            alarm_process_global.poll() is None
                            and not alarm_stop_flag
                        ):
                            time.sleep(0.1)

                else:
                    print("[ERROR] afplay not found.")

            except Exception as e:

                print(
                    "[ERROR] Cannot play sound:",
                    e
                )

            break

        time.sleep(0.5)


def set_alarm(
    alarm_time,
    alarm_file=None
):

    hhmm = parse_alarm_time(alarm_time)

    if not hhmm:

        speak(
            "Invalid time format. "
            "Say for example 7:30 am or 19:45."
        )

        return

    threading.Thread(
        target=_alarm_thread,
        args=(hhmm, alarm_file),
        daemon=True
    ).start()

    alarm_datetime = datetime.datetime.strptime(
        hhmm,
        "%H:%M"
    )

    display_time = (
        alarm_datetime
        .strftime("%I:%M %p")
        .lstrip("0")
    )

    speak(
        f"Your alarm has been set for {display_time}."
    )


# ============================================================
# TIME AND DATE
# ============================================================

def get_time():

    return datetime.datetime.now().strftime(
        "The time is %I:%M %p"
    )


def get_date():

    return datetime.datetime.now().strftime(
        "Today's date is %d %B %Y"
    )


def play_beep():

    try:

        subprocess.Popen(
            [
                "afplay",
                ALARM_TONE
            ]
        )

    except Exception as e:

        print("[BEEP ERROR]", e)


def assistant_prompt():

    speak("Anything else?")


# ============================================================
# MAIN ASSISTANT LOOP
# ============================================================

def main():

    speak(
        "Hello. I am your voice assistant. "
        "How can I assist you?"
    )

    while True:

        cmd = listen()

        if not cmd:

            time.sleep(0.5)
            continue

        cmd = cmd.lower().strip()

        # Wake word
        if cmd.startswith("hey buddy "):

            stop_speaking()

            cmd = cmd.replace(
                "hey buddy",
                "",
                1
            ).strip()

        else:

            continue

        # Speech recognition network error
        if cmd == "network_error":

            speak(
                "Network error while recognizing "
                "speech. Check your internet."
            )

            assistant_prompt()
            continue

        # Exit
        if cmd in (
            "exit",
            "quit",
            "goodbye"
        ):

            speak("Goodbye.")
            break

        # Time
        if "time" in cmd:

            response = get_time()

            speak(response)

            log_interaction(
                cmd,
                "time",
                response
            )

            assistant_prompt()
            continue

        # Date
        if "date" in cmd:

            response = get_date()

            speak(response)

            log_interaction(
                cmd,
                "date",
                response
            )

            assistant_prompt()
            continue

        # Stop alarm
        if (
            "stop alarm" in cmd
            or "alarm stop" in cmd
            or "turn off alarm" in cmd
            or "stop ringing" in cmd
        ):

            stop_alarm()

            log_interaction(
                cmd,
                "alarm_stop",
                "Alarm stopped."
            )

            assistant_prompt()
            continue

        # Alarm
        if (
            "alarm" in cmd
            or "set alarm" in cmd
            or "wake me" in cmd
        ):

            alarm_time = parse_alarm_time(cmd)

            if not alarm_time:

                speak(
                    "Sure, at what time should "
                    "I set the alarm?"
                )

                user_time = listen()

                alarm_time = parse_alarm_time(
                    user_time
                )

                if not alarm_time:

                    speak(
                        "I could not understand "
                        "the time. Say for example "
                        "5:00 pm or 17:30."
                    )

                    assistant_prompt()
                    continue

            print(
                "[DEBUG] Alarm time recognized:",
                alarm_time
            )

            play_beep()

            set_alarm(
                alarm_time,
                ALARM_TONE
            )

            assistant_prompt()
            continue

        # Music controls
        if (
            "music" in cmd
            or cmd.startswith("play ")
        ):

            if (
                "stop music" in cmd
                or "stop the music" in cmd
                or "pause music" in cmd
            ):

                response = stop_apple_music()

                speak(response)

                log_interaction(
                    cmd,
                    "music_stop",
                    response
                )

                assistant_prompt()
                continue

            # Apple Music
            if (
                "on apple music" in cmd
                or "on apple" in cmd
            ):

                song = re.sub(
                    r"\bon apple music\b",
                    "",
                    cmd
                )

                song = re.sub(
                    r"\bon apple\b",
                    "",
                    song
                )

                song = song.replace(
                    "play",
                    "",
                    1
                ).strip()

                if song:

                    response = (
                        play_apple_music_song(song)
                    )

                    speak(response)

                    log_interaction(
                        cmd,
                        "apple_music_play",
                        response
                    )

                else:

                    speak(
                        "Please tell me the song name."
                    )

                assistant_prompt()
                continue

            # YouTube
            if "on youtube" in cmd:

                song = re.sub(
                    r"\bon youtube\b",
                    "",
                    cmd
                )

                song = song.replace(
                    "play",
                    "",
                    1
                ).strip()

                if song:

                    response = youtube_player.play(
                        song
                    )

                    speak(response)

                    log_interaction(
                        cmd,
                        "youtube_song",
                        song
                    )

                else:

                    response = youtube_player.play(
                        "popular songs"
                    )

                    speak(response)

                assistant_prompt()
                continue

            # Random Apple Music
            if cmd in (
                "music",
                "play music",
                "play some music"
            ):

                play_random_music()

                log_interaction(
                    cmd,
                    "apple_music_random",
                    "Playing random Apple Music song"
                )

                assistant_prompt()
                continue

            # Specific song on YouTube
            if cmd.startswith("play "):

                song = cmd.replace(
                    "play ",
                    "",
                    1
                ).strip()

                response = youtube_player.play(song)

                speak(response)

                log_interaction(
                    cmd,
                    "music_youtube",
                    song
                )

                assistant_prompt()
                continue

        # Applications
        if open_app(cmd):

            log_interaction(
                cmd,
                "open_app",
                "Application command executed."
            )

            assistant_prompt()
            continue

        # Weather
        if "weather" in cmd:

            speak("Which city?")

            city = listen()

            if city:

                response = get_weather(city)

                speak(response)

                log_interaction(
                    cmd,
                    "weather",
                    response,
                    {"city": city}
                )

            assistant_prompt()
            continue

        # News
        if (
            "news" in cmd
            or "headline" in cmd
            or "headlines" in cmd
        ):

            location = re.sub(
                r"\b(hey buddy|give me|tell me|show me|"
                r"latest|today|today's|news|headline|headlines)\b",
                "",
                cmd,
                flags=re.IGNORECASE
            ).strip()

            location = re.sub(
                r"^(in|from)\s+",
                "",
                location,
                flags=re.IGNORECASE
            ).strip()

            location = re.sub(
                r"\s+(in|from)$",
                "",
                location,
                flags=re.IGNORECASE
            ).strip()

            if location:
                response = get_news(location)
            else:
                response = get_news()

            speak(response)

            log_interaction(
                cmd,
                "news",
                response,
                {
                    "location": (
                        location
                        if location
                        else "India"
                    )
                }
            )

            assistant_prompt()
            continue

        # AI Questions
        if (
            cmd.startswith(
                (
                    "ask ",
                    "question "
                )
            )
            or cmd.endswith("?")
            or cmd.startswith(
                (
                    "what ",
                    "who ",
                    "how ",
                    "why ",
                    "when ",
                    "where ",
                    "which ",
                    "can ",
                    "is ",
                    "are ",
                    "do ",
                    "does "
                )
            )
        ):

            question = cmd

            if question.strip() in (
                "ask",
                "question"
            ):

                speak(
                    "What are you asking about?"
                )

                follow_up = listen()

                if not follow_up:

                    speak(
                        "I did not catch the question."
                    )

                    assistant_prompt()
                    continue

                question = follow_up

                if len(question.split()) <= 4:

                    question = (
                        "Please explain "
                        + question
                        + " briefly."
                    )

            response = ask_gpt(question)

            speak(response)

            log_interaction(
                cmd,
                "ai_question",
                response
            )

            assistant_prompt()
            continue

        # General AI fallback
        response = ask_gpt(cmd)

        speak(response)

        log_interaction(
            cmd,
            "fallback_ai",
            response
        )

        assistant_prompt()


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:

        print("Exiting...")

    except Exception as e:

        log_error(
            f"Fatal error: {e}"
        )

        print(
            "Fatal error:",
            e
        )
