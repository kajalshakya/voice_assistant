# Voice-Based Personal Assistant

A Python-based voice assistant that uses speech recognition, text-to-speech, APIs, and AI to perform common tasks through voice commands.

## Features

* Voice command recognition using SpeechRecognition
* Wake phrase support: **"Hey Buddy"**
* AI-powered responses using **Groq API**
* Answers general knowledge and conversational questions using AI
* Weather information using OpenWeather API
* News headlines using GNews API
* Voice-based alarm with stop functionality
* Apple Music control
* Local music playback
* YouTube search and playback
* Google search
* WhatsApp Web opening
* Basic application control
* Current time and date
* Calculator and TextEdit support
* MySQL database logging with SQLite fallback
* Error handling and graceful fallback

## Tech Stack

* Python
* SpeechRecognition
* PyAudio
* Groq API
* OpenWeather API
* GNews API
* MySQL
* SQLite
* python-dotenv
* macOS system utilities

## Project Structure

```text
voice_assistant/
│
├── main.py
├── README.md
├── requirements.txt
├── .env.example
└── .gitignore
```

## Requirements

* Python 3
* macOS
* Microphone
* Internet connection
* API keys for:

  * Groq
  * OpenWeather
  * GNews
* MySQL (optional; SQLite fallback is available)

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/kajalshakya/voice_assistant.git
cd voice_assistant
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
```

### 3. Activate the Virtual Environment

```bash
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Open `.env` and add your own API keys and database credentials:

```env
WEATHER_API_KEY=
GNEWS_API_KEY=
GROQ_API_KEY=

MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=assistant_logs
```

Do not commit `.env` to GitHub.

### 6. Run the Assistant

```bash
python3 main.py
```

## Example Voice Commands

### General Commands

```text
Hey Buddy, what's the time?
Hey Buddy, what's the date?
Hey Buddy, what's the weather?
Hey Buddy, what's the news?
```

### AI Questions

```text
Hey Buddy, what is artificial intelligence?
Hey Buddy, explain machine learning.
Hey Buddy, what is the difference between AI and machine learning?
Hey Buddy, explain cloud computing.
Hey Buddy, what is Python?
```

The assistant uses the **Groq API** to generate AI-based responses for general knowledge and conversational questions.

### Music and Media

```text
Hey Buddy, play music
Hey Buddy, play [song name]
Hey Buddy, stop music
Hey Buddy, open YouTube
```

### Other Commands

```text
Hey Buddy, set an alarm
Hey Buddy, search Google
Hey Buddy, open WhatsApp
Hey Buddy, open calculator
Hey Buddy, open TextEdit
```

## Error Handling

The assistant handles common errors such as:

* Speech recognition failures
* API request failures
* Invalid city names
* Database connection failures
* Missing or unavailable services

If MySQL is unavailable, the assistant can fall back to SQLite for local logging.

## Security

* API keys and database passwords are stored in environment variables.
* `.env` is excluded from version control using `.gitignore`.
* `.env.example` is provided as a safe configuration template.
* Secret credentials are not stored directly in the source code.

## Future Improvements

The project can be further enhanced with the following features:

* **Offline voice recognition** to allow basic commands without an internet connection.
* **Multilingual voice support** for interacting with the assistant in multiple languages.
* **Personalized responses** based on user preferences and previous interactions.
* **Machine learning-based intent detection** for better understanding of natural language commands.
* **Context-aware conversations** so the assistant can understand follow-up questions.
* **Voice authentication** to identify authorized users.
* **IoT integration** to control smart home devices using voice commands.
* **Personal task management** including reminders, calendar events, and to-do lists.
* **More system automation** such as controlling applications, files, and system settings.
* **Improved security and privacy** with better local processing and secure credential management.
* **Web-based interface** for monitoring assistant activity and managing settings.
* **Expanded API integrations** for services such as maps, email, and other productivity tools.

## Author

**Kajal Shakya**

MCA — Indira Gandhi Delhi Technical University for Women (IGDTUW)

