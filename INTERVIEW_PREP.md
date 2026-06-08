# 🎤 RealChat — Interview Preparation Guide

Use this guide to confidently discuss the project in technical interviews.

---

## 30-Second Project Overview

> "I built RealChat — a full-stack real-time chat application using Python Flask and Socket.IO on the backend, with a vanilla JavaScript frontend in a single HTML file. It supports multiple chat rooms, real-time messaging via WebSockets, user authentication with hashed passwords, and typing indicators. I containerized it with Docker and made it Heroku-deployable. I built it to demonstrate WebSocket architecture, REST API design, and authentication from scratch."

---

## Architecture Discussion

### Why Flask + Socket.IO?

Flask is lightweight and easy to reason about — it doesn't hide what it's doing. Flask-SocketIO sits on top of Flask and adds WebSocket support with minimal configuration. This combination lets you clearly see the boundary between HTTP and WebSocket concerns, which is good for an interview.

### Why SQLite?

SQLite requires zero infrastructure — it's a file on disk. For a portfolio project or demo, this is ideal: anyone can clone and run it in under 5 minutes without installing a database server. In production you'd swap in PostgreSQL; the Python `sqlite3` API is largely compatible with `psycopg2`.

### Why a single index.html?

No build toolchain means no Webpack, no npm, no transpiling. Anyone can open the file, read it, and understand it immediately. It's intentionally simple to show that you understand what frameworks abstract — not that you can't live without them.

### How does real-time work?

1. On page load, the browser opens a **persistent WebSocket connection** to the Flask-SocketIO server (falling back to HTTP long-polling if WebSockets are blocked).
2. When a user sends a message, the client emits a `send_message` event over the socket.
3. The server receives it, writes to SQLite, and **broadcasts** a `new_message` event to all clients subscribed to that room.
4. Each subscribed client appends the message to the DOM — no polling, no page refresh.

---

## Q&A — Common Interview Questions

**Q: Walk me through the authentication flow.**

> When a user registers, the password is hashed with Werkzeug's PBKDF2-SHA256 (the same algorithm used by Django). The hash is stored in SQLite. On login, `check_password_hash` compares the submitted password against the stored hash — the plain-text password is never stored or logged. On success, the server generates a cryptographically random 64-character token (via `secrets.token_hex(32)`) and stores it in an in-memory dictionary mapping token → user_id. Every subsequent API request and WebSocket connection passes this token in the Authorization header or query string. To log out, the token is deleted from the dictionary.

**Q: How do you handle WebSocket authentication?**

> Socket.IO passes query parameters on the initial handshake. The client sends `?token=<token>` when connecting. On the `connect` event, the server looks the token up in `active_sessions`. If it's not found, `disconnect()` is called immediately and `False` is returned — Flask-SocketIO rejects the connection before any events can be processed.

**Q: How would you scale this to 10,000 concurrent users?**

> The current in-memory session store and SQLite database are the two bottlenecks. For scale:
> 1. Replace SQLite with PostgreSQL and add connection pooling.
> 2. Replace the in-memory token store with Redis, so multiple server processes share session state.
> 3. Run multiple Gunicorn workers behind a load balancer (e.g., Nginx). With Redis as the Socket.IO message queue, events broadcast from one worker reach clients connected to other workers.
> 4. Add a CDN to serve static assets.

**Q: What security measures did you implement?**

> - Password hashing (PBKDF2-SHA256) — no plain-text storage
> - Random token auth — tokens are 256-bit entropy, not sequential or guessable
> - Input validation on both client and server — username length/format, message length cap (2000 chars), room name length
> - HTML escaping on all user-generated content — prevents XSS
> - CORS configured to API routes only
> - WebSocket connections rejected if token is missing or invalid
> - SQLite WAL mode for safe concurrent access

**Q: What would you do differently in production?**

> - JWT tokens with expiry instead of the in-memory dictionary (stateless, scales horizontally)
> - PostgreSQL instead of SQLite
> - Redis pub/sub for Socket.IO message queue
> - Rate limiting on the message endpoint (e.g., Flask-Limiter)
> - HTTPS/WSS (TLS termination at load balancer)
> - Message pagination with cursor-based pagination instead of LIMIT
> - Automated tests (pytest for backend, Playwright for E2E)

**Q: How do typing indicators work?**

> When a user presses a key in the input box, the client emits a `typing` event with the `room_id`. The server re-broadcasts a `user_typing` event to all other sockets in that room (excluding the sender via `include_self=False`). On the receiving client, a timer clears the indicator after 3 seconds if no further typing events arrive. This is "fire and forget" — if a typing event is dropped, it just expires naturally.

**Q: Explain the database schema design.**

> Three tables with foreign key relationships:
> - `users` — stores credentials; `username` has a UNIQUE constraint
> - `rooms` — stores room metadata; `created_by` references `users.id`
> - `messages` — each row is one message; `room_id` and `user_id` are foreign keys
>
> This normalized design avoids data duplication. To get messages with author names, one JOIN suffices. Message history is ordered by `created_at ASC` so the oldest appears first in the chat.

**Q: Why eventlet? What is it?**

> Flask-SocketIO needs an async-capable server to handle many concurrent WebSocket connections efficiently. Eventlet provides cooperative multitasking using greenlets — lightweight coroutines. Without it, each WebSocket would block a thread, and you'd run out of threads fast. Eventlet monkey-patches Python's standard library so existing synchronous code (like `sqlite3`) works in the async context without changes.

**Q: How do rooms work in Socket.IO?**

> Socket.IO has a built-in concept of "rooms" — named groups of socket connections. When a user clicks a room, the client emits `join_room`. The server calls `join_room(str(room_id))`, which adds that socket to the Socket.IO room. When a message is sent, `emit('new_message', data, to=str(room_id))` delivers it only to sockets in that room — not everyone connected to the server.

---

## Quick Reference Numbers

| Metric | Value |
|--------|-------|
| REST endpoints | 6 |
| WebSocket events (client→server) | 4 |
| WebSocket events (server→client) | 7 |
| Database tables | 3 |
| Token entropy | 256 bits |
| Message max length | 2,000 chars |
| History loaded per room | 50 messages |
| Lines of backend code | ~300 |
| Lines of frontend code | ~400 |

---

## Interview Day Tips

1. **Draw the architecture first.** A quick box diagram (Browser ↔ Flask ↔ SQLite) anchors the conversation.
2. **Explain your choices, not just what you built.** "I chose SQLite because…" is more impressive than "I used SQLite."
3. **Know your tradeoffs.** Every technology choice has a downside — acknowledge them and explain how you'd address them at scale.
4. **Be ready to live-code a change.** Common asks: add an endpoint, fix a bug, write a test. Know the codebase well enough to navigate it quickly.
5. **Mention what you'd add next.** JWT auth, message pagination, and PostgreSQL are natural next steps that show architectural thinking.
