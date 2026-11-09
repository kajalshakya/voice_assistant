# Voice-Based Personal Assistant

A smart voice-based personal assistant developed using **Python, React, Flask, Artificial Intelligence, and Natural Language Processing (NLP)**. The assistant allows users to perform everyday tasks, control applications, access information, and interact with an AI-powered system through voice commands.

The project combines speech recognition, natural language processing, AI-generated responses, and voice automation to provide an interactive and user-friendly experience through a modern web interface.

## Features

- **Voice Interaction:** Interact with the assistant using voice commands.
- **Wake Word Detection:** Activate the assistant using the predefined wake word "Hey Buddy".
- **AI-Powered Responses:** Generate intelligent responses using Groq AI powered by the GPT-OSS-120B model.
- **Multilingual Voice Interaction:** Understand and respond to voice commands in multiple languages.
- **Speech Recognition:** Convert spoken commands into text for processing.
- **Text-to-Speech:** Convert assistant responses into speech for natural voice interaction.
- **Application Control:** Open and close desktop applications such as WhatsApp, Calculator, and Text Editor using voice commands.
- **Web Browser Control:** Open and close websites and web services such as Google and YouTube through voice commands.
- **YouTube Music Playback:** Play music on YouTube using voice commands.
- **Local Media Control:** Play and control local media files through voice commands.
- **Weather Updates:** Retrieve weather information using a weather API.
- **Latest News:** Fetch the latest news updates using the GNews API.
- **Command Interruption:** Interrupt ongoing voice interactions when required.
- **Real-Time Status Updates:** Display listening, processing, and response states through the web interface.
- **Database Logging:** Store assistant interaction logs using MySQL, with SQLite fallback support.
- **Interactive Web Interface:** Provide a modern React-based interface for voice interaction.

## Tech Stack

| Category | Technologies |
|---|---|
| Programming Languages | Python, JavaScript |
| Frontend | React.js, HTML5, CSS3 |
| Backend | Flask |
| AI Integration | Groq AI, GPT-OSS-120B |
| Natural Language Processing | NLP |
| Speech Recognition | SpeechRecognition, PyAudio |
| Text-to-Speech | Python-based TTS |
| Database | MySQL, SQLite (fallback) |
| API Integration | Weather API, GNews API |
| Frontend Icons | Lucide React |
| Communication | Flask REST API |
| Build Tool | Vite |
| Version Control | Git, GitHub |

## Project Structure

```text
voice_assistant/
│
├── frontend/
│   ├── public/
│   │   └── mic.png
│   │
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx
│   │   │   ├── ResponseBox.jsx
│   │   │   ├── StatusIndicator.jsx
│   │   │   └── VoiceAssistant.jsx
│   │   │
│   │   ├── services/
│   │   │   └── assistantApi.js
│   │   │
│   │   ├── App.css
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   │
│   ├── .gitignore
│   ├── eslint.config.js
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
│
├── api.py
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/kajalshakya/voice_assistant.git

cd voice_assistant
```

### 2. Create a Python Virtual Environment

```bash
python3 -m venv venv
```

Activate the virtual environment.

**For macOS/Linux:**

```bash
source venv/bin/activate
```

**For Windows:**

```bash
venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory.

Use `.env.example` as a reference and configure the following variables:

```ini
WEATHER_API_KEY=your_weather_api_key
GNEWS_API_KEY=your_gnews_api_key
GROQ_API_KEY=your_groq_api_key

MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=assistant_logs
```

Replace the placeholder values with your actual API keys and database credentials.

### 5. Configure MySQL Database

Make sure MySQL is installed and running on your system.

Create the database:

```sql
CREATE DATABASE assistant_logs;
```

The application uses MySQL to maintain assistant interaction logs. SQLite fallback support is also available.

### 6. Start the Python Voice Assistant

Open a terminal in the project root, activate the virtual environment, and run:

```bash
python main.py
```

### 7. Start the Flask Backend

Open another terminal in the project root.

Activate the virtual environment and run:

```bash
python api.py
```

The Flask backend runs at:

```text
http://127.0.0.1:5000
```

### 8. Start the React Frontend

Open another terminal:

```bash
cd frontend
```

Install frontend dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Open the local development URL displayed in the terminal to access the assistant interface.

## API Endpoints

The Flask backend provides the following API endpoints:

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/voice-command` | Initiates voice command processing |
| GET | `/api/status` | Retrieves the current assistant status |
| POST | `/api/interrupt` | Interrupts an ongoing voice command |

## Application Workflow

1. The user activates the assistant using the wake word "Hey Buddy" or the microphone button.
2. The speech recognition module captures the user's voice.
3. The recognized command is processed by the Python backend.
4. The assistant identifies the requested task using command processing and NLP.
5. For AI-based queries, Groq AI generates an appropriate response using the GPT-OSS-120B model.
6. For specific commands, the assistant performs the corresponding operation, such as opening applications, playing media, or retrieving weather and news information.
7. The response is converted into speech using text-to-speech functionality.
8. The React frontend displays the assistant response and real-time status updates.
9. Interaction logs are maintained using MySQL, with SQLite fallback support.

## Environment Variables and Security

- API keys and sensitive credentials are stored in environment variables.
- The `.env` file is excluded from version control.
- The `.env.example` file provides a template for required environment variables.
- Database credentials are not hardcoded into the application.
- Virtual environments and Node.js dependencies are excluded from version control.
- Sensitive configuration files should never be uploaded to a public GitHub repository.

## Future Enhancements

- Improve speech recognition accuracy.
- Enhance multilingual conversation capabilities.
- Add more desktop application integrations.
- Improve AI response speed and efficiency.
- Introduce personalized user preferences.
- Expand voice-based automation capabilities.
- Enhance the overall user interface and experience.

## Developer

**Kajal Shakya**

MCA Student  
Indira Gandhi Delhi Technical University for Women (IGDTUW), New Delhi

GitHub: [kajalshakya](https://github.com/kajalshakya)

## License

This project is developed for educational and personal learning purposes.
