# AI Drone Emergency Response System

An autonomous drone dispatch platform for real-time emergency response.  
Built for **DRONExHACK 2026**.

---

## Overview

This system allows users to report emergencies via a **Telegram bot** by sending
a photo and GPS location. The backend uses **Google Gemini** (with Groq as
fallback) to analyze incident images, classify the emergency type, and
automatically dispatch the nearest available drone using a Haversine-based
algorithm. Drone movements are simulated in real time and broadcast over
WebSocket to an interactive map frontend and a rescue-team dashboard.

---

## Architecture

```
Telegram Bot  ──►  FastAPI Backend  ──►  AI Vision (Gemini / Groq)
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  Drone Fleet      WebSocket       Streamlit
  Dispatch         Broadcast       Dashboard
        │               │
        ▼               ▼
  Movement         Map Frontend
  Simulation       (Mappls SDK)
```

---

## Tech Stack

| Layer       | Technology                                      |
|-------------|------------------------------------------------|
| Backend     | Python, FastAPI, Uvicorn                        |
| AI Vision   | Google Gemini API, Groq API (fallback)          |
| Bot         | python-telegram-bot                             |
| Frontend    | HTML/CSS/JS, Mappls Map SDK v3.0                |
| Dashboard   | Streamlit                                       |
| Real-time   | WebSocket (native FastAPI)                      |
| Dispatch    | Haversine formula, greedy nearest-drone         |

---

## Project Structure

```
ai-drone-rescue/
├── run.py                      # Unified launcher (backend + dashboard)
├── backend/
│   ├── main.py                 # FastAPI server, routes, WebSocket
│   ├── ai_agent.py             # Gemini / Groq vision analysis
│   ├── drone_dispatch.py       # Fleet management, Haversine dispatch
│   ├── drone_simulation.py     # Drone movement simulation, WS broadcast
│   ├── telegram_bot.py         # Telegram bot integration
│   ├── requirements.txt        # Python dependencies
│   └── .env                    # API keys (not committed)
├── dashboard/
│   └── rescue_dashboard.py     # Streamlit rescue-team dashboard
├── frontend/
│   ├── index.html              # Landing page
│   ├── map.html                # Live drone tracking map
│   ├── script.js               # Shared JS utilities & WebSocket
│   └── vercel.json             # Vercel deployment config
└── images/                     # Uploaded incident / drone images
```

---

## Prerequisites

- Python 3.10 or later
- A Google Gemini API key
- A Groq API key (optional, used as fallback)
- A Telegram Bot token (obtain from @BotFather)

---

## Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/<your-username>/ai-drone-rescue.git
   cd ai-drone-rescue
   ```

2. **Install dependencies**

   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Configure environment variables**

   Create `backend/.env`:

   ```
   GEMINI_API_KEY=your_gemini_api_key
   GROQ_API_KEY=your_groq_api_key
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ```

4. **Run the system**

   ```bash
   python run.py
   ```

   This starts:
   - FastAPI backend on `http://localhost:10000`
   - Streamlit dashboard on `http://localhost:8501`

5. **Open the map**

   Open `frontend/map.html` in a browser (or serve via any HTTP server).

---

## Usage

### Report an Emergency (Telegram)

1. Open your Telegram bot.
2. Send `/start` to see instructions.
3. Send a **photo** of the incident.
4. Share your **GPS location**.
5. The AI analyzes the image and dispatches the nearest drone automatically.

### Monitor (Dashboard)

Open `http://localhost:8501` to view:
- Active incidents with AI analysis reports
- Drone fleet status and positions
- Uploaded incident and drone images

### Track Drones (Map)

Open `frontend/map.html` to see:
- Live drone positions updated via WebSocket
- Incident markers with priority indicators
- User location marker

---

## API Endpoints

| Method | Endpoint                  | Description                        |
|--------|---------------------------|------------------------------------|
| POST   | `/incident`               | Create a new incident              |
| GET    | `/incidents`              | List all incidents                 |
| GET    | `/incidents/{id}`         | Get incident details               |
| GET    | `/drones`                 | List drone fleet status            |
| POST   | `/upload-image/{id}`      | Upload drone camera image          |
| GET    | `/images/{filename}`      | Serve an uploaded image            |
| WS     | `/ws`                     | WebSocket for real-time updates    |

---


AI analysis uses a dual-provider approach:
1. **Google Gemini** — primary vision model
2. **Groq** — fallback if Gemini is unavailable
3. **Safety fallback** — returns a default emergency report if both fail

---

## License

MIT
