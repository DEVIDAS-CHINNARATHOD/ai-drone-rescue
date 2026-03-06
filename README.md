# 🚁 AI Drone Emergency Response System

> **Hackathon Project** — An AI-powered drone dispatch system for emergency response. Users report incidents via Telegram, AI analyzes the situation, drones are dispatched in real-time, and rescue teams monitor everything from a live dashboard.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green?logo=fastapi)
![Streamlit](https://img.shields.io/badge/Streamlit-1.31-red?logo=streamlit)
![Leaflet](https://img.shields.io/badge/Leaflet.js-Map-brightgreen?logo=leaflet)

---

## 🏗️ Architecture

```
Telegram Bot ──► FastAPI Backend ──► AI Analysis
                    │                    │
                    ├── Drone Dispatch ◄─┘
                    │        │
                    │   WebSocket (live positions)
                    │        │
              Leaflet Map ◄──┘
                    │
              Camera Page ──► Image Upload
                    │
           Streamlit Dashboard (Rescue Team)
```

---

## 📁 Project Structure

```
ai-drone-rescue/
├── backend/
│   ├── main.py              # FastAPI server + WebSocket
│   ├── ai_agent.py          # AI image analysis & classification
│   ├── drone_dispatch.py    # Drone fleet & Haversine dispatch
│   ├── drone_simulation.py  # Real-time drone movement simulation
│   ├── telegram_bot.py      # Telegram bot integration
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── index.html           # Landing page
│   ├── map.html             # Live drone map (Leaflet.js)
│   ├── camera.html          # Camera capture page
│   ├── script.js            # Shared JS utilities
│   └── vercel.json          # Vercel deployment config
├── dashboard/
│   └── rescue_dashboard.py  # Streamlit rescue team dashboard
├── images/                  # Uploaded images directory
├── README.md
└── .gitignore
```

---

## 🚀 Quick Start (Local)

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/ai-drone-rescue.git
cd ai-drone-rescue
pip install -r backend/requirements.txt
```

### 2. Configure Environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your Telegram bot token
```

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token from [@BotFather](https://t.me/BotFather) |
| `SERVER_URL` | `http://localhost:10000` (local) or your Render URL |

### 3. Start the Backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 10000 --reload
```

### 4. Open the Frontend

Open `frontend/index.html` in your browser, or serve it:

```bash
cd frontend
python -m http.server 8080
```

Then visit:
- **Landing Page**: http://localhost:8080
- **Live Map**: http://localhost:8080/map.html
- **Camera Page**: http://localhost:8080/camera.html

### 5. Start the Dashboard

```bash
cd dashboard
streamlit run rescue_dashboard.py
```

Dashboard at: http://localhost:8501

---

## 🧪 Test an Incident (without Telegram)

```bash
# Create a test incident via API
curl -X POST http://localhost:10000/incident \
  -F "latitude=17.385044" \
  -F "longitude=78.486671" \
  -F "image=@test_image.jpg"
```

Or use the **Demo** button on the landing page to trigger a simulated incident.

---

## 📱 Telegram Bot Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the token to `backend/.env`
4. Start the backend — the bot runs automatically
5. Send a **photo** and then share your **location** with the bot

---

## ☁️ Deployment

### Backend → Render

1. Push to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your repo, set root directory to `backend/`
4. **Build command**: `pip install -r requirements.txt`
5. **Start command**: `uvicorn main:app --host 0.0.0.0 --port 10000`
6. Add environment variables in Render dashboard
7. Update `SERVER_URL` in `.env` to your Render URL

### Frontend → Vercel

1. Go to [vercel.com](https://vercel.com)
2. Import your GitHub repo
3. Set root directory to `frontend/`
4. Deploy — Vercel auto-detects static files
5. Update `API_BASE_URL` in `script.js` to your Render backend URL

### Dashboard

The Streamlit dashboard can be deployed on [Streamlit Cloud](https://streamlit.io/cloud) or any server.

---

## ✨ Features

| Feature | Status |
|---|---|
| 📸 Telegram incident reporting | ✅ |
| 🤖 AI image analysis & classification | ✅ |
| 🚁 Drone fleet management (3+ drones) | ✅ |
| 📍 Haversine-based nearest drone dispatch | ✅ |
| 🗺️ Real-time drone movement on map | ✅ |
| 📷 Phone camera capture (drone simulation) | ✅ |
| 🏥 Rescue team Streamlit dashboard | ✅ |
| 🔌 WebSocket live updates | ✅ |
| ☁️ Render + Vercel deployment ready | ✅ |

---

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, WebSockets
- **AI**: Rule-based image analysis (hackathon-optimized)
- **Frontend**: HTML, CSS, JavaScript, Leaflet.js
- **Dashboard**: Streamlit
- **Bot**: python-telegram-bot
- **Deployment**: Render (backend), Vercel (frontend)

---

## 📄 License

MIT License — Built for hackathon purposes.
