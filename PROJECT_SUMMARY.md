# RealChat — Project Summary

## What Is This?

RealChat is a full-stack real-time chat application built as a portfolio project. It demonstrates WebSocket-based real-time communication, REST API design, user authentication, and deployment readiness — all in clean, readable code.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10 + Flask 2.3 |
| Real-time | Flask-SocketIO (Socket.IO v4) |
| Database | SQLite (via Python `sqlite3`) |
| Frontend | Vanilla JS + HTML + CSS (single file) |
| Server | Gunicorn + Eventlet |
| Deployment | Docker / Heroku / Railway |

## Features at a Glance

- Register and log in with hashed passwords
- Create and join multiple chat rooms
- Real-time messages via WebSockets
- Typing indicators
- Message history (last 50 per room)
- Join/leave notifications
- Dark theme UI, no dependencies

## 5-Minute Setup

```bash
# macOS/Linux
chmod +x start.sh && ./start.sh

# Windows
start.bat

# Docker
docker-compose up --build
```

Then open **http://localhost:5000**.

## File Guide

| File | Purpose |
|------|---------|
| `app.py` | Flask backend — all server logic |
| `index.html` | Complete frontend — HTML + CSS + JS |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |
| `Procfile` | Heroku deployment config |
| `Dockerfile` | Docker image config |
| `docker-compose.yml` | Local Docker Compose |
| `start.sh` | One-command setup (macOS/Linux) |
| `start.bat` | One-command setup (Windows) |
| `README.md` | Full documentation |
| `INTERVIEW_PREP.md` | Technical interview Q&A |

## Key Technical Decisions

**Why WebSockets?** HTTP is request-response — the server can't push to the client without a persistent connection. WebSockets maintain an open bidirectional channel, which is essential for real-time chat.

**Why SQLite?** Zero infrastructure. Clone and run — no database server required. Swap to PostgreSQL for production.

**Why a single HTML file?** No build toolchain. Anyone can read the entire frontend in one file and understand it immediately.

## Portfolio Talking Points

- Full-stack: designed and built both backend API and frontend UI
- Real-time: WebSocket architecture, not polling
- Auth: password hashing, token-based sessions
- Database: normalized schema with foreign keys
- Deployment: Dockerized, Heroku/Railway ready
- Security: input validation, XSS prevention, CORS
