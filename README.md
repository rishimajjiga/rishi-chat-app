# Rishi - Pure Privacy Messaging

> No data accumulation = Ultimate privacy

A WhatsApp-style private messaging app where messages auto-delete after 1 hour.

## Features

- Phone number as Chat ID (like WhatsApp)
- One-to-one private DMs
- Meeting rooms with invite links
- Updates — ephemeral posts visible to contacts only, disappear after seen
- Green double-tick read receipts
- Online / last seen status
- Messages auto-delete after 1 hour
- Manual message delete
- File and image sharing
- Emoji picker
- Push notifications
- Google Sign-In support
- Fully mobile responsive

## Run Locally

**Windows** — double-click `start.bat`

Or manually:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## Deploy Live (free) on Render

1. Push this repo to GitHub
2. Go to https://render.com and click New > Web Service
3. Connect your GitHub repo
4. Render detects render.yaml automatically — click Deploy
5. Live URL: https://rishi-chatting-app.onrender.com

## Tech Stack

- Backend: Python, Flask, Flask-SocketIO
- Database: SQLite (WAL mode)
- Frontend: Vanilla JS, Socket.IO
- Auth: Phone + password or Google Sign-In
