import speech_recognition as sr
from gtts import gTTS
import requests
import datetime
import time
import os
import webbrowser
import platform
import google.generativeai as genai
import mysql.connector
import json
import re
import threading
import random
import sqlite3
import shutil
import subprocess
import tempfile
import signal


# ---------------------------
# CONFIGURATION
# ---------------------------
WEATHER_API_KEY = "b04b96faae18877d8d516c148525dd9f"
NEWS_API_KEY = "3012dfd6249ecfa0712cb6a8c39f4543"
YOUR_GEMINI_KEY = "AIzaSyCGdAWbx6RRZWYghInfQwJXGsSJuHNlmJA"

MUSIC_FOLDER = os.path.expanduser("/home/rohitshakya/Music")
ALARM_TONE = "/home/rohitshakya/Music/rock.mp3"

player_lock = threading.Lock()
player_process = None
audio_playing = False

# Alarm process handle
alarm_process_global = None

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "database": "assistant_logs",
    "autocommit": True
}

genai.configure(api_key=YOUR_GEMINI_KEY)
SYSTEM = platform.system().lower()

# ---------------------------
# DATABASE SETUP (MySQL with SQLite fallback)
# ---------------------------
USE_MYSQL = True

def get_db_conn():
    global USE_MYSQL
    if USE_MYSQL:
        try:
            return mysql.connector.connect(**DB_CONFIG), "mysql"
        except Exception as e:
            print("[DB] MySQL connect failed, falling back to SQLite:", e)
            USE_MYSQL = False
    return sqlite3.connect("assistant_fallback.db", check_same_thread=False), "sqlite"

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
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INT AUTO_INCREMENT PRIMARY KEY,
                error_message TEXT NOT NULL
            )""")
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                command_text TEXT,
                intent TEXT,
                response_text TEXT,
                metadata TEXT
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                error_message TEXT
            )""")
    conn.commit()
    cur.close()
    conn.close()

def log_interaction(command, intent, response, metadata=None):
    try:
        conn, kind = get_db_conn()
        cur = conn.cursor()
        meta_json = json.dumps(metadata) if metadata else None
        if kind == "mysql":
            cur.execute("INSERT INTO interactions (command_text,intent,response_text,metadata) VALUES (%s,%s,%s,%s)",
                        (command, intent, response, meta_json))
        else:
            cur.execute("INSERT INTO interactions (timestamp,command_text,intent,response_text,metadata) VALUES (?,?,?,?,?)",
                        (str(datetime.datetime.now()), command, intent, response, meta_json))
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
            cur.execute("INSERT INTO errors (error_message) VALUES (%s)", (message,))
        else:
            cur.execute("INSERT INTO errors (timestamp,error_message) VALUES (?,?)", (str(datetime.datetime.now()), message))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("[LOG ERROR]", e)

ensure_tables()

# ---------------------------
# TEXT-TO-SPEECH
# ---------------------------
current_speech_process = None
speech_lock = threading.Lock()

def speak(text, lang='en'):
    """Speak text using gTTS + mpv at faster speed"""
    global current_speech_process

    def _speak_thread(msg, lang_code):
        global current_speech_process
        try:
            clean = re.sub(r"(\*\*|\*|__|`)", "", str(msg))
            clean = re.sub(r"\s{2,}", " ", clean).strip()
            print("[Assistant]", clean)

            with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as fp:
                tts = gTTS(clean, lang=lang_code, slow=False)
                tts.save(fp.name)

                with speech_lock:
                    if current_speech_process and current_speech_process.poll() is None:
                        current_speech_process.terminate()
                    current_speech_process = subprocess.Popen(
                        ["mpv", "--no-terminal", "--speed=1.5", fp.name],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    current_speech_process.wait()
        except Exception as e:
            print("[TTS Error]", e)

    t = threading.Thread(target=_speak_thread, args=(text, lang), daemon=True)
    t.start()
    t.join()


# ---------------------------
# SPEECH-TO-TEXT
# ---------------------------
def listen(language=None):
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        try:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, phrase_time_limit=6)
        except Exception as e:
            print("[Mic Error]", e)
            return None

    try:
        if language:
            text = r.recognize_google(audio, language=language)
        else:
            text = r.recognize_google(audio)
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



# ---------------------------
# AI (Gemini)
# ---------------------------
def ask_gpt(question):
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        ans = model.generate_content(question)
        return ans.text
    except Exception as e:
        log_error(f"ask_gpt error: {e}")
        return "Sorry, I couldn't get an answer from AI."

# ---------------------------
# WEATHER & NEWS
# ---------------------------
def get_weather(city):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        data = requests.get(url, timeout=8).json()
        if data.get("cod") != 200:
            return "City not found."
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"]
        return f"The temperature in {city} is {temp}°C with {desc}."
    except Exception as e:
        log_error(f"weather error: {e}")
        return "Error fetching weather."

def get_news():
    try:
        url = f"https://gnews.io/api/v4/top-headlines?country=in&apikey={NEWS_API_KEY}"
        data = requests.get(url, timeout=8).json()

        if "errors" in data:
            return f"GNews Error: {data['errors'][0]['message']}"

        articles = data.get("articles", [])
        if not articles:
            return "No news found right now."

        headlines = [a.get("title", "No title") for a in articles[:5]]
        return "Top headlines: " + " | ".join(headlines)
    except Exception as e:
        log_error(f"news error: {e}")
        return "Error fetching news."



# ---------------------------
# MUSIC CONTROL
# ---------------------------
# player_lock = threading.Lock()
# player_process = None

def _start_local_player(path):
    """Start a local player and keep a handle to control pause/resume/stop.
       Uses mpv if available, otherwise paplay (paplay doesn't support pause/resume).
       Spawns a monitor thread to clear global state when playback ends.
    """
    global player_process, audio_playing
    try:
        with player_lock:
            # terminate any existing local player first
            if player_process and player_process.poll() is None:
                try:
                    os.killpg(os.getpgid(player_process.pid), signal.SIGTERM)
                except Exception:
                    try:
                        player_process.terminate()
                    except Exception:
                        pass
                player_process = None

            audio_playing = True

            if shutil.which("mpv"):
                player_process = subprocess.Popen(
                    ["mpv", "--no-terminal", "--really-quiet", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp
                )
            elif shutil.which("paplay"):
                player_process = subprocess.Popen(
                    ["paplay", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp
                )
            else:
                print(f"Cannot play {path}. Install mpv or paplay.")
                audio_playing = False
                return None

            # Monitor thread to clear state once process exits
            def _monitor(p):
                global player_process, audio_playing
                try:
                    p.wait()
                except Exception:
                    pass
                with player_lock:
                    player_process = None
                    audio_playing = False

            t = threading.Thread(target=_monitor, args=(player_process,), daemon=True)
            t.start()

            return player_process
    except Exception as e:
        log_error(f"_start_local_player error: {e}")
        audio_playing = False
        return None


def play_local_music():
    try:
        files = [f for f in os.listdir(MUSIC_FOLDER) if f.lower().endswith((".mp3", ".wav", ".ogg", ".m4a", ".flac"))]
        if not files:
            return "No music found in your music folder."
        song = random.choice(files)
        path = os.path.join(MUSIC_FOLDER, song)
        proc = _start_local_player(path)
        if proc:
            return f"Playing local music: {song}"
        else:
            return "Failed to start local player."
    except Exception as e:
        log_error(f"play_local_music error: {e}")
        return "Error playing local music."

def play_specific_local(path):
    if os.path.exists(path):
        proc = _start_local_player(path)
        if proc:
            return f"Playing: {os.path.basename(path)}"
        else:
            return "Failed to start local player."
    else:
        return "File not found."
    
def pause_music():
    """Pause local player using SIGSTOP (Linux)."""
    global player_process, audio_playing
    with player_lock:
        if player_process and player_process.poll() is None:
            try:
                os.killpg(os.getpgid(player_process.pid), signal.SIGSTOP)
                return "Music paused."
            except Exception as e:
                log_error(f"pause_music error: {e}")
                return "Could not pause music."
        return "No music is playing."

def resume_music():
    """Resume local player using SIGCONT (Linux)."""
    global player_process, audio_playing
    with player_lock:
        if player_process and player_process.poll() is None:
            try:
                os.killpg(os.getpgid(player_process.pid), signal.SIGCONT)
                return "Music resumed."
            except Exception as e:
                log_error(f"resume_music error: {e}")
                return "Could not resume music."
        return "No music to resume."

def stop_music():
    """Stop local player and clear state."""
    global player_process, audio_playing
    with player_lock:
        if player_process and player_process.poll() is None:
            try:
                os.killpg(os.getpgid(player_process.pid), signal.SIGTERM)
            except Exception:
                try:
                    player_process.terminate()
                except Exception:
                    pass
            player_process = None
            audio_playing = False
            return "Stopped music."
        # As a fallback, try to kill any stray mpv process (useful if mpv was started outside code)
        try:
            subprocess.run(["pkill", "-9", "mpv"], check=False)
        except Exception:
            pass
        player_process = None
        audio_playing = False
        return "No music was playing."




# ---------------------------
# YouTube Mini Player
# ---------------------------
class YouTubeMiniPlayer:
    def __init__(self):
        self.current_url = None

    def play(self, query=None):
        if query:
            self.current_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        if self.current_url:
            webbrowser.open(self.current_url)
            return f"Playing {query} on YouTube."
        else:
            return "No song specified."

    def stop(self):
        self.current_url = None
        return "Stopped YouTube playback (close browser tab manually)."

player = YouTubeMiniPlayer()

# ---------------------------
# OPEN APPLICATIONS
# ---------------------------
def open_app(command):
    try:
        cmd = command.lower()
        if "calculator" in cmd or "calc" in cmd:
            calc_path = "/usr/bin/gnome-calculator"
            if os.path.exists(calc_path):
                subprocess.Popen([calc_path])
                speak("Opening calculator.")
            else:
                speak("Calculator app not found.")
            return True

        if "youtube" in cmd:
            webbrowser.open("https://youtube.com")
            speak("Opening YouTube.")
            return True
        if "google" in cmd or "chrome" in cmd:
            chrome_path = shutil.which("google-chrome") or shutil.which("chromium")
            if chrome_path:
                subprocess.Popen([chrome_path])
            else:
                webbrowser.open("https://google.com")
            speak("Opening Google.")
            return True
        if "whatsapp" in cmd:
            webbrowser.open("https://web.whatsapp.com")
            speak("Opening WhatsApp Web.")
            return True
        if "notepad" in cmd or "editor" in cmd:
            editor_path = shutil.which("gedit") or shutil.which("nano")
            if editor_path:
                subprocess.Popen([editor_path])
            speak("Opening text editor.")
            return True
        if "play music" in cmd or cmd.strip() == "music":
            res = play_local_music()
            speak(res)
            return True
    except Exception as e:
        log_error(f"open_app error: {e}")
        speak("Failed to open application.")
    return False

# ---------------------------
# ALARM FUNCTIONS (UPDATED)
# ---------------------------
alarm_stop_flag = False
alarm_process_global = None


def stop_alarm():
    global alarm_stop_flag, alarm_process_global
    alarm_stop_flag = True

    try:
        if alarm_process_global and alarm_process_global.poll() is None:
            try:
                os.killpg(os.getpgid(alarm_process_global.pid), signal.SIGTERM)
            except Exception:
                alarm_process_global.terminate()
        alarm_process_global = None
    except Exception as e:
        log_error(f"stop_alarm kill error: {e}")

    # double safety
    try:
        subprocess.run(["pkill", "-9", "mpv"], check=False)
    except:
        pass

    speak("Alarm stopped.")


# ---------------------------
# FIXED TIME PARSER (AM/PM PERFECT)
# ---------------------------
def parse_alarm_time(text: str) -> str | None:
    if not text:
        return None

    text = text.lower().replace(".", "").replace(";", ":").strip()
    m = re.search(r"(\d{1,2})(?:[: ]?(\d{2}))?\s*(am|pm)?", text)

    if not m:
        return None

    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    ampm = m.group(3)

    # AM/PM conversion
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    # validation
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"

    return None


# ---------------------------
# ALARM THREAD
# ---------------------------
def _alarm_thread(alarm_time_str: str, alarm_file: str = None):
    global alarm_stop_flag, alarm_process_global
    alarm_stop_flag = False

    hh, mm = map(int, alarm_time_str.split(":"))
    now = datetime.datetime.now()

    alarm_time = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if alarm_time <= now:
        alarm_time += datetime.timedelta(days=1)

    try:
        while not alarm_stop_flag:
            now = datetime.datetime.now()

            if now >= alarm_time:
                # PLAY ALARM
                if alarm_file and os.path.exists(alarm_file):
                    try:
                        # mpv preferred
                        if shutil.which("mpv"):
                            alarm_process_global = subprocess.Popen(
                                ["mpv", "--no-terminal", "--loop", alarm_file],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                preexec_fn=os.setpgrp
                            )
                        elif shutil.which("paplay"):
                            alarm_process_global = subprocess.Popen(
                                ["paplay", alarm_file],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                preexec_fn=os.setpgrp
                            )
                        else:
                            alarm_process_global = None
                    except Exception as e:
                        log_error(f"alarm play error: {e}")
                        alarm_process_global = None

                    # wait for stop
                    while not alarm_stop_flag:
                        time.sleep(0.4)

                else:
                    # fallback sound
                    while not alarm_stop_flag:
                        speak("Your alarm is ringing.")
                        time.sleep(1)

                break

            time.sleep(0.4)

    except Exception as e:
        log_error(f"Alarm thread error: {e}")

    finally:
        alarm_stop_flag = False
        alarm_process_global = None


# ---------------------------
# SET ALARM
# ---------------------------
def set_alarm(alarm_time: str, alarm_file: str = None):
    hhmm = parse_alarm_time(alarm_time)

    if not hhmm:
        speak("Invalid time. Please say something like 7:30 am or 2:45 pm.")
        return

    threading.Thread(target=_alarm_thread, args=(hhmm, alarm_file), daemon=True).start()
    speak(f"Your alarm has been set for {hhmm}.")

# ---------------------------
# TIME & DATE
# ---------------------------
def get_time():
    return datetime.datetime.now().strftime("The time is %H:%M")

def get_date():
    return datetime.datetime.now().strftime("Today's date is %d %B %Y")

# ---------------------------
# MAIN LOOP
# ---------------------------
def assistant_prompt():
    speak("Anything else?")

def main():
    speak("Hello. I am your voice assistant. How can I assist you?")

    while True:
        cmd = listen()
        if not cmd:
            time.sleep(0.5)
            continue
        cmd = cmd.lower().strip()

        if cmd == "network_error":
            speak("Network error while recognizing speech. Check your internet.")
            assistant_prompt()
            continue

        if cmd in ("exit", "quit", "goodbye"):
            speak("Goodbye.")
            break

        # TIME
        if "time" in cmd:
            ans = get_time()
            speak(ans)
            log_interaction(cmd, "time", ans)
            assistant_prompt()
            continue

        # DATE
        if "date" in cmd:
            ans = get_date()
            speak(ans)
            log_interaction(cmd, "date", ans)
            assistant_prompt()
            continue

        # -------------------------------------------
        # ALARM SECTION (UPDATED & FIXED)
        # -------------------------------------------

        # SET ALARM
        if ("set alarm" in cmd) or ("alarm" in cmd and "stop" not in cmd) or ("wake me" in cmd):
            
            # 1. Try direct time detection from same command
            m = re.search(r"(\d{1,2}(?::\d{2})?)\s*(am|pm)?", cmd)
            
            if m:
                raw_time = m.group(1)              # e.g. "2:27"
                ampm = m.group(2)                  # am/pm or None

                # Combine for parsing
                if ampm:
                    user_time = f"{raw_time} {ampm}"
                else:
                    user_time = raw_time

                hhmm = parse_alarm_time(user_time)

            else:
                # 2. Ask user separately
                speak("Sure, what time should I set the alarm for?")
                user_input = listen().lower().strip()

                hhmm = parse_alarm_time(user_input)

                if not hhmm:
                    speak("I could not understand the time. Please say something like 5:00 pm or 7 am.")
                    assistant_prompt()
                    continue

            # If parsed successfully
            print("[DEBUG] Alarm time recognized:", hhmm)
            set_alarm(hhmm, ALARM_TONE)
            assistant_prompt()
            continue


        # STOP ALARM
        # STOP ALARM
        if "stop alarm" in cmd or cmd.strip() == "stop":
            stop_alarm()
            assistant_prompt()
            continue



        # MUSIC
        if "play music" in cmd or cmd == "music":
            res = play_local_music()
            if "No music found" in res or "Error" in res:
                res = player.play("popular songs")
            speak(res)
            log_interaction(cmd, "music_play", res)
            assistant_prompt()
            continue

        if cmd.startswith("play "):
            song = cmd.replace("play ", "", 1).strip()
            local_candidates = [os.path.join(MUSIC_FOLDER, song + ext) 
                                for ext in ["", ".mp3", ".wav", ".ogg", ".m4a", ".flac"]]
            for c in local_candidates:
                if os.path.exists(c):
                    speak(play_specific_local(c))
                    log_interaction(cmd, "music_local_specific", c)
                    assistant_prompt()
                    break
            else:
                res = player.play(song)
                speak(res)
                log_interaction(cmd, "music_youtube", song)
                assistant_prompt()
            continue

        if "pause music" in cmd or cmd == "pause":
            res = pause_music()
            speak(res)
            log_interaction(cmd, "music_pause", res)
            assistant_prompt()
            continue

        if "resume music" in cmd or cmd == "resume":
            res = resume_music()
            speak(res)
            log_interaction(cmd, "music_resume", res)
            assistant_prompt()
            continue

        if "stop music" in cmd or cmd == "stop":
            res = stop_music()
            speak(res)
            log_interaction(cmd, "music_stop", res)
            assistant_prompt()
            continue


        # OPEN APP
        if open_app(cmd):
            log_interaction(cmd, "open_app", "opened")
            assistant_prompt()
            continue

        # WEATHER
        if "weather" in cmd:
            speak("Which city?")
            city = listen()
            if city:
                report = get_weather(city)
                speak(report)
                log_interaction(cmd, "weather", report)
            assistant_prompt()
            continue

        # NEWS
        if "news" in cmd:
            report = get_news()
            speak(report)
            assistant_prompt()
            continue



                # QUESTIONS
        if cmd.startswith(("ask ", "question ")) or cmd.endswith("?") or cmd.startswith(("what ", "who ", "how ")):
            question = cmd

            if question.strip() in ("ask", "question"):
                speak("What is your question?")
                q2 = listen()
                if not q2:
                    speak("I did not catch the question.")
                    assistant_prompt()
                    continue
                question = q2

            ans = ask_gpt(question)
            speak(ans)
            log_interaction(cmd, "ai_question", ans)
            assistant_prompt()
            continue

        # FALLBACK AI
        ans = ask_gpt(cmd)
        speak(ans)
        log_interaction(cmd, "fallback_ai", ans)
        assistant_prompt()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Exiting...")
    except Exception as e:
        log_error(f"fatal error: {e}")
        print("Fatal error:", e)

