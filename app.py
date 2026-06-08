# coding: utf-8
import os, uuid, random, sqlite3, secrets, threading, time
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    from google.oauth2 import id_token as g_id_token
    from google.auth.transport import requests as g_requests
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False

app = Flask(__name__, static_folder=".", static_url_path="")
app.config["SECRET_KEY"]         = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["DATABASE"]           = os.environ.get("DATABASE", "chat.db")
app.config["UPLOAD_FOLDER"]      = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

active_sessions = {}
online_users    = {}
pending_google  = {}

ALLOWED = {"png","jpg","jpeg","gif","webp","pdf","doc","docx","xls","xlsx","txt","mp4","mp3","wav","zip"}
def allowed(fn): return "." in fn and fn.rsplit(".",1)[1].lower() in ALLOWED

def get_db():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                bio TEXT DEFAULT '',
                avatar TEXT DEFAULT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_by INTEGER NOT NULL,
                invite_token TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS meeting_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                content TEXT,
                file_url TEXT,
                file_name TEXT,
                file_type TEXT,
                deleted_at TEXT DEFAULT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS direct_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                content TEXT,
                file_url TEXT,
                file_name TEXT,
                file_type TEXT,
                is_read INTEGER NOT NULL DEFAULT 0,
                deleted_at TEXT DEFAULT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS tweets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                media_url TEXT DEFAULT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS tweet_views (
                tweet_id INTEGER NOT NULL,
                viewer_id INTEGER NOT NULL,
                viewed_at TEXT DEFAULT NULL,
                PRIMARY KEY (tweet_id, viewer_id)
            );
            CREATE TABLE IF NOT EXISTS dm_contacts (
                user_a INTEGER NOT NULL,
                user_b INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_a, user_b)
            );
            INSERT OR IGNORE INTO users (id, username, password) VALUES (0, '_system', 'x');
            INSERT OR IGNORE INTO meetings (name, description, created_by, invite_token)
                VALUES ('General', 'Default meeting room', 0, 'general-invite-token-0001');
        """)
        for col, defn in [("phone","TEXT"),("bio","TEXT DEFAULT ''"),("avatar","TEXT DEFAULT NULL"),
                          ("google_id","TEXT"),("google_email","TEXT")]:
            try: conn.execute("ALTER TABLE users ADD COLUMN " + col + " " + defn)
            except sqlite3.OperationalError: pass
        for col, defn in [("file_url","TEXT"),("file_name","TEXT"),("file_type","TEXT"),
                          ("deleted_at","TEXT DEFAULT NULL")]:
            for tbl in ("meeting_messages","direct_messages"):
                try: conn.execute("ALTER TABLE " + tbl + " ADD COLUMN " + col + " " + defn)
                except sqlite3.OperationalError: pass
        try:
            for r in conn.execute("SELECT * FROM rooms").fetchall():
                conn.execute("INSERT OR IGNORE INTO meetings (name,description,created_by,invite_token) VALUES (?,?,?,?)",
                             (r["name"],r["description"],r["created_by"],str(uuid.uuid4())))
        except sqlite3.OperationalError: pass
        try:
            for m in conn.execute("SELECT * FROM messages").fetchall():
                conn.execute("INSERT OR IGNORE INTO meeting_messages (id,meeting_id,user_id,content,created_at) VALUES (?,?,?,?,?)",
                             (m["id"],m["room_id"],m["user_id"],m["content"],m["created_at"]))
        except sqlite3.OperationalError: pass
        try:
            for u in conn.execute("SELECT id,chat_id FROM users WHERE phone IS NULL AND id!=0").fetchall():
                conn.execute("UPDATE users SET phone=? WHERE id=?",(u["chat_id"] or _rand_phone(),u["id"]))
        except sqlite3.OperationalError:
            for u in conn.execute("SELECT id FROM users WHERE phone IS NULL AND id!=0").fetchall():
                conn.execute("UPDATE users SET phone=? WHERE id=?",(_rand_phone(),u["id"]))

def _rand_phone(): return str(random.randint(6000000000,9999999999))

def _auto_delete():
    while True:
        time.sleep(60)
        try:
            cutoff = (datetime.utcnow()-timedelta(hours=1)).isoformat()
            tc     = (datetime.utcnow()-timedelta(hours=24)).isoformat()
            with get_db() as conn:
                conn.execute("DELETE FROM meeting_messages WHERE created_at < ?",(cutoff,))
                conn.execute("DELETE FROM direct_messages  WHERE created_at < ?",(cutoff,))
                conn.execute("DELETE FROM tweet_views WHERE tweet_id IN (SELECT id FROM tweets WHERE created_at < ?)",(tc,))
                conn.execute("DELETE FROM tweets WHERE created_at < ?",(tc,))
        except Exception as e:
            print("[auto-delete]",e)

def token_uid(token): return active_sessions.get(token)

def require_auth(f):
    @wraps(f)
    def d(*a,**kw):
        t = request.headers.get("Authorization","").replace("Bearer ","")
        if not t or t not in active_sessions: return jsonify({"error":"Unauthorized"}),401
        request.user_id = active_sessions[t]
        return f(*a,**kw)
    return d

def dm_room(a,b): return "dm_" + str(min(a,b)) + "_" + str(max(a,b))
def set_online(uid): online_users[uid] = datetime.utcnow()
def is_online(uid):
    t = online_users.get(uid)
    return bool(t and (datetime.utcnow()-t).total_seconds()<45)
def last_seen(uid):
    t = online_users.get(uid)
    return t.isoformat() if t else None
def user_to_dict(u):
    return {"id":u["id"],"phone":u["phone"],"username":u["username"],"bio":u["bio"],"avatar":u["avatar"]}

@app.route("/")
def index(): return send_from_directory(".","index.html")

@app.route("/uploads/<path:fn>")
def serve_upload(fn): return send_from_directory(app.config["UPLOAD_FOLDER"],fn)

@app.route("/api/register",methods=["POST"])
def register():
    d=request.get_json(silent=True) or {}
    phone=(d.get("phone") or "").strip().replace(" ","").replace("-","")
    username=(d.get("username") or "").strip()
    password=d.get("password") or ""
    if not phone or not username or not password: return jsonify({"error":"Phone, name and password required"}),400
    if not phone.isdigit() or len(phone)<7 or len(phone)>15: return jsonify({"error":"Invalid phone number"}),400
    if len(username)<2 or len(username)>40: return jsonify({"error":"Name 2-40 chars"}),400
    if len(password)<6: return jsonify({"error":"Password min 6 chars"}),400
    hashed=generate_password_hash(password)
    try:
        with get_db() as conn:
            cur=conn.execute("INSERT INTO users (phone,username,password) VALUES (?,?,?)",(phone,username,hashed))
            uid=cur.lastrowid
    except sqlite3.IntegrityError: return jsonify({"error":"Phone already registered"}),409
    tk=secrets.token_hex(32)
    active_sessions[tk]=uid
    set_online(uid)
    return jsonify({"token":tk,"user_id":uid,"phone":phone,"username":username,"bio":"","avatar":None}),201

@app.route("/api/login",methods=["POST"])
def login():
    d=request.get_json(silent=True) or {}
    phone=(d.get("phone") or "").strip().replace(" ","").replace("-","")
    password=d.get("password") or ""
    if not phone or not password: return jsonify({"error":"Phone and password required"}),400
    with get_db() as conn:
        u=conn.execute("SELECT * FROM users WHERE phone=?",(phone,)).fetchone()
    if not u or not check_password_hash(u["password"],password): return jsonify({"error":"Incorrect credentials"}),401
    tk=secrets.token_hex(32)
    active_sessions[tk]=u["id"]
    set_online(u["id"])
    return jsonify({"token":tk,"user_id":u["id"],"phone":u["phone"],"username":u["username"],"bio":u["bio"],"avatar":u["avatar"]}),200

@app.route("/api/logout",methods=["POST"])
@require_auth
def logout():
    t=request.headers.get("Authorization","").replace("Bearer ","")
    active_sessions.pop(t,None)
    online_users.pop(request.user_id,None)
    return jsonify({"ok":True}),200

@app.route("/api/profile",methods=["GET"])
@require_auth
def get_profile():
    with get_db() as conn:
        u=conn.execute("SELECT * FROM users WHERE id=?",(request.user_id,)).fetchone()
    return jsonify(user_to_dict(u)),200

@app.route("/api/profile",methods=["PUT"])
@require_auth
def update_profile():
    d=request.get_json(silent=True) or {}
    fields,vals=[],[]
    if "username" in d:
        n=(d["username"] or "").strip()
        if len(n)<2 or len(n)>40: return jsonify({"error":"Name 2-40 chars"}),400
        fields.append("username=?"); vals.append(n)
    if "bio" in d: fields.append("bio=?"); vals.append((d["bio"] or "")[:160])
    if "avatar" in d: fields.append("avatar=?"); vals.append(d["avatar"])
    if not fields: return jsonify({"error":"Nothing to update"}),400
    vals.append(request.user_id)
    with get_db() as conn:
        conn.execute("UPDATE users SET " + ",".join(fields) + " WHERE id=?",vals)
        u=conn.execute("SELECT * FROM users WHERE id=?",(request.user_id,)).fetchone()
    socketio.emit("profile_updated",user_to_dict(u))
    return jsonify(user_to_dict(u)),200

@app.route("/api/users/find",methods=["GET"])
@require_auth
def find_user():
    phone=(request.args.get("phone") or "").strip().replace(" ","").replace("-","")
    if not phone: return jsonify({"error":"phone required"}),400
    with get_db() as conn:
        u=conn.execute("SELECT * FROM users WHERE phone=?",(phone,)).fetchone()
    if not u: return jsonify({"error":"No user with that phone"}),404
    if u["id"]==request.user_id: return jsonify({"error":"That is your own number"}),400
    d=user_to_dict(u)
    d["online"]=is_online(u["id"])
    d["last_seen"]=last_seen(u["id"])
    return jsonify(d),200

@app.route("/api/users/<int:uid>/status",methods=["GET"])
@require_auth
def user_status(uid):
    return jsonify({"online":is_online(uid),"last_seen":last_seen(uid)}),200

@app.route("/api/upload",methods=["POST"])
@require_auth
def upload():
    if "file" not in request.files: return jsonify({"error":"No file"}),400
    f=request.files["file"]
    if not f.filename: return jsonify({"error":"Empty filename"}),400
    if not allowed(f.filename): return jsonify({"error":"File type not allowed"}),400
    ext=os.path.splitext(secure_filename(f.filename))[1]
    name=uuid.uuid4().hex+ext
    f.save(os.path.join(app.config["UPLOAD_FOLDER"],name))
    ct=f.content_type or "application/octet-stream"
    return jsonify({"url":"/uploads/"+name,"name":f.filename,"type":ct}),200

@app.route("/api/meetings",methods=["GET"])
@require_auth
def get_meetings():
    with get_db() as conn:
        rows=conn.execute("SELECT m.*,u.username AS creator FROM meetings m JOIN users u ON u.id=m.created_by ORDER BY m.created_at").fetchall()
    return jsonify([dict(r) for r in rows]),200

@app.route("/api/meetings",methods=["POST"])
@require_auth
def create_meeting():
    d=request.get_json(silent=True) or {}
    name=(d.get("name") or "").strip()
    desc=(d.get("description") or "").strip()
    if not name: return jsonify({"error":"Name required"}),400
    if len(name)<2 or len(name)>60: return jsonify({"error":"Name 2-60 chars"}),400
    tk=str(uuid.uuid4())
    try:
        with get_db() as conn:
            cur=conn.execute("INSERT INTO meetings (name,description,created_by,invite_token) VALUES (?,?,?,?)",(name,desc or None,request.user_id,tk))
            row=conn.execute("SELECT m.*,u.username AS creator FROM meetings m JOIN users u ON u.id=m.created_by WHERE m.id=?",(cur.lastrowid,)).fetchone()
    except sqlite3.IntegrityError: return jsonify({"error":"Meeting name already exists"}),409
    socketio.emit("meeting_created",dict(row))
    return jsonify(dict(row)),201

@app.route("/api/meetings/join/<token>",methods=["GET"])
@require_auth
def join_by_token(token):
    with get_db() as conn:
        row=conn.execute("SELECT m.*,u.username AS creator FROM meetings m JOIN users u ON u.id=m.created_by WHERE m.invite_token=?",(token,)).fetchone()
    if not row: return jsonify({"error":"Invalid invite link"}),404
    return jsonify(dict(row)),200

@app.route("/api/meetings/<int:mid>/messages",methods=["GET"])
@require_auth
def get_meeting_msgs(mid):
    lim=min(int(request.args.get("limit",50)),200)
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM meetings WHERE id=?",(mid,)).fetchone(): return jsonify({"error":"Not found"}),404
        rows=conn.execute("SELECT mm.*,u.username,u.avatar FROM meeting_messages mm JOIN users u ON u.id=mm.user_id WHERE mm.meeting_id=? AND mm.deleted_at IS NULL ORDER BY mm.created_at DESC LIMIT ?",(mid,lim)).fetchall()
    return jsonify(list(reversed([dict(r) for r in rows]))),200

@app.route("/api/meetings/messages/<int:mid>",methods=["DELETE"])
@require_auth
def delete_meeting_msg(mid):
    with get_db() as conn:
        msg=conn.execute("SELECT * FROM meeting_messages WHERE id=?",(mid,)).fetchone()
        if not msg: return jsonify({"error":"Not found"}),404
        if msg["user_id"]!=request.user_id: return jsonify({"error":"Not your message"}),403
        conn.execute("DELETE FROM meeting_messages WHERE id=?",(mid,))
    socketio.emit("message_deleted",{"id":mid,"type":"meeting"})
    return jsonify({"ok":True}),200

@app.route("/api/conversations",methods=["GET"])
@require_auth
def conversations():
    uid=request.user_id
    with get_db() as conn:
        partners=conn.execute("SELECT CASE WHEN user_a=? THEN user_b ELSE user_a END AS oid FROM dm_contacts WHERE user_a=? OR user_b=?",(uid,uid,uid)).fetchall()
        convs=[]
        for p in partners:
            oid=p["oid"]
            ou=conn.execute("SELECT * FROM users WHERE id=?",(oid,)).fetchone()
            if not ou: continue
            last=conn.execute("SELECT * FROM direct_messages WHERE ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)) AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 1",(uid,oid,oid,uid)).fetchone()
            unread=conn.execute("SELECT COUNT(*) c FROM direct_messages WHERE sender_id=? AND receiver_id=? AND is_read=0 AND deleted_at IS NULL",(oid,uid)).fetchone()["c"]
            dc=conn.execute("SELECT updated_at FROM dm_contacts WHERE (user_a=? AND user_b=?) OR (user_a=? AND user_b=?)",(uid,oid,oid,uid)).fetchone()
            convs.append({"other_id":oid,"other_username":ou["username"],"other_phone":ou["phone"],"other_avatar":ou["avatar"],
                "last_message":(last["content"] if last and last["content"] else ("File" if last and last["file_url"] else "")),
                "last_at":(last["created_at"] if last else dc["updated_at"]),
                "is_mine":(last["sender_id"]==uid if last else False),
                "unread_count":unread,"online":is_online(oid)})
        convs.sort(key=lambda x:x["last_at"],reverse=True)
    return jsonify(convs),200

@app.route("/api/dm/<int:oid>/messages",methods=["GET"])
@require_auth
def dm_messages(oid):
    uid=request.user_id
    lim=min(int(request.args.get("limit",50)),200)
    with get_db() as conn:
        rows=conn.execute("SELECT dm.*,u.username,u.avatar FROM direct_messages dm JOIN users u ON u.id=dm.sender_id WHERE ((dm.sender_id=? AND dm.receiver_id=?) OR (dm.sender_id=? AND dm.receiver_id=?)) AND dm.deleted_at IS NULL ORDER BY dm.created_at DESC LIMIT ?",(uid,oid,oid,uid,lim)).fetchall()
        conn.execute("UPDATE direct_messages SET is_read=1 WHERE sender_id=? AND receiver_id=? AND is_read=0",(oid,uid))
    return jsonify(list(reversed([dict(r) for r in rows]))),200

@app.route("/api/dm/messages/<int:mid>",methods=["DELETE"])
@require_auth
def delete_dm_msg(mid):
    with get_db() as conn:
        msg=conn.execute("SELECT * FROM direct_messages WHERE id=?",(mid,)).fetchone()
        if not msg: return jsonify({"error":"Not found"}),404
        if msg["sender_id"]!=request.user_id: return jsonify({"error":"Not your message"}),403
        conn.execute("DELETE FROM direct_messages WHERE id=?",(mid,))
    socketio.emit("message_deleted",{"id":mid,"type":"dm"})
    return jsonify({"ok":True}),200

@app.route("/api/tweets",methods=["GET"])
@require_auth
def get_tweets():
    uid=request.user_id
    with get_db() as conn:
        rows=conn.execute("SELECT t.*,u.username,u.avatar,u.phone FROM tweets t JOIN users u ON u.id=t.user_id JOIN tweet_views tv ON tv.tweet_id=t.id WHERE tv.viewer_id=? AND tv.viewed_at IS NULL ORDER BY t.created_at DESC",(uid,)).fetchall()
        mine=conn.execute("SELECT t.*,u.username,u.avatar,u.phone FROM tweets t JOIN users u ON u.id=t.user_id WHERE t.user_id=? ORDER BY t.created_at DESC",(uid,)).fetchall()
    return jsonify({"inbox":[dict(r) for r in rows],"mine":[dict(r) for r in mine]}),200

@app.route("/api/tweets",methods=["POST"])
@require_auth
def create_tweet():
    d=request.get_json(silent=True) or {}
    content=(d.get("content") or "").strip()
    media_url=d.get("media_url")
    if not content: return jsonify({"error":"Content required"}),400
    if len(content)>500: return jsonify({"error":"Max 500 chars"}),400
    uid=request.user_id
    with get_db() as conn:
        cur=conn.execute("INSERT INTO tweets (user_id,content,media_url) VALUES (?,?,?)",(uid,content,media_url))
        tid=cur.lastrowid
        contacts=conn.execute("SELECT DISTINCT CASE WHEN user_a=? THEN user_b ELSE user_a END AS cid FROM dm_contacts WHERE user_a=? OR user_b=?",(uid,uid,uid)).fetchall()
        for c in contacts:
            conn.execute("INSERT OR IGNORE INTO tweet_views (tweet_id,viewer_id) VALUES (?,?)",(tid,c["cid"]))
        tw=conn.execute("SELECT t.*,u.username,u.phone,u.avatar FROM tweets t JOIN users u ON u.id=t.user_id WHERE t.id=?",(tid,)).fetchone()
    for c in contacts:
        socketio.emit("new_tweet",dict(tw),to="user_"+str(c["cid"]))
    return jsonify(dict(tw)),201

@app.route("/api/tweets/<int:tid>/view",methods=["POST"])
@require_auth
def view_tweet(tid):
    uid=request.user_id
    with get_db() as conn:
        conn.execute("UPDATE tweet_views SET viewed_at=? WHERE tweet_id=? AND viewer_id=?",(datetime.utcnow().isoformat(),tid,uid))
    return jsonify({"ok":True}),200

@app.route("/api/tweets/<int:tid>",methods=["DELETE"])
@require_auth
def delete_tweet(tid):
    with get_db() as conn:
        t=conn.execute("SELECT * FROM tweets WHERE id=?",(tid,)).fetchone()
        if not t: return jsonify({"error":"Not found"}),404
        if t["user_id"]!=request.user_id: return jsonify({"error":"Not yours"}),403
        conn.execute("DELETE FROM tweet_views WHERE tweet_id=?",(tid,))
        conn.execute("DELETE FROM tweets WHERE id=?",(tid,))
    socketio.emit("tweet_deleted",{"id":tid})
    return jsonify({"ok":True}),200

@socketio.on("connect")
def on_connect():
    t=request.args.get("token","")
    uid=token_uid(t)
    if not uid: disconnect(); return False
    join_room("user_"+str(uid))
    set_online(uid)
    socketio.emit("user_online",{"user_id":uid})
    emit("connected",{"user_id":uid})

@socketio.on("disconnect")
def on_disconnect():
    t=request.args.get("token","")
    uid=token_uid(t)
    if uid:
        online_users.pop(uid,None)
        socketio.emit("user_offline",{"user_id":uid,"last_seen":datetime.utcnow().isoformat()})

@socketio.on("ping_online")
def on_ping(data=None):
    t=request.args.get("token","")
    uid=token_uid(t)
    if uid: set_online(uid)

@socketio.on("join_meeting")
def on_join_meeting(data):
    t=request.args.get("token",""); uid=token_uid(t)
    if not uid: return
    mid=data.get("meeting_id")
    if not mid: return
    with get_db() as conn:
        m=conn.execute("SELECT * FROM meetings WHERE id=?",(mid,)).fetchone()
        u=conn.execute("SELECT username FROM users WHERE id=?",(uid,)).fetchone()
    if not m: return
    join_room("meeting_"+str(mid))
    emit("joined_meeting",{"meeting_id":mid,"name":m["name"]})
    emit("user_joined",{"username":u["username"],"meeting_id":mid},to="meeting_"+str(mid),include_self=False)

@socketio.on("leave_meeting")
def on_leave_meeting(data):
    t=request.args.get("token",""); uid=token_uid(t)
    if not uid: return
    mid=data.get("meeting_id")
    if mid:
        leave_room("meeting_"+str(mid))
        with get_db() as conn:
            u=conn.execute("SELECT username FROM users WHERE id=?",(uid,)).fetchone()
        emit("user_left",{"username":u["username"] if u else "?","meeting_id":mid},to="meeting_"+str(mid))

@socketio.on("send_meeting_msg")
def on_meeting_msg(data):
    t=request.args.get("token",""); uid=token_uid(t)
    if not uid: return
    mid=data.get("meeting_id")
    content=(data.get("content") or "").strip()
    file_url=data.get("file_url"); file_name=data.get("file_name"); file_type=data.get("file_type")
    if not mid or (not content and not file_url): return
    if content and len(content)>2000: return
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM meetings WHERE id=?",(mid,)).fetchone(): return
        cur=conn.execute("INSERT INTO meeting_messages (meeting_id,user_id,content,file_url,file_name,file_type) VALUES (?,?,?,?,?,?)",(mid,uid,content or None,file_url,file_name,file_type))
        u=conn.execute("SELECT username,avatar FROM users WHERE id=?",(uid,)).fetchone()
    emit("new_meeting_msg",{"id":cur.lastrowid,"meeting_id":mid,"user_id":uid,"username":u["username"],"avatar":u["avatar"],"content":content,"file_url":file_url,"file_name":file_name,"file_type":file_type,"created_at":datetime.utcnow().isoformat()},to="meeting_"+str(mid))

@socketio.on("meeting_typing")
def on_meeting_typing(data):
    t=request.args.get("token",""); uid=token_uid(t)
    if not uid: return
    mid=data.get("meeting_id")
    if not mid: return
    with get_db() as conn:
        u=conn.execute("SELECT username FROM users WHERE id=?",(uid,)).fetchone()
    emit("user_typing",{"username":u["username"] if u else "?","meeting_id":mid},to="meeting_"+str(mid),include_self=False)

@socketio.on("join_dm")
def on_join_dm(data):
    t=request.args.get("token",""); uid=token_uid(t)
    if not uid: return
    oid=data.get("other_id")
    if not oid: return
    with get_db() as conn:
        ou=conn.execute("SELECT * FROM users WHERE id=?",(oid,)).fetchone()
    if not ou: return
    join_room(dm_room(uid,oid))
    emit("joined_dm",{"other_id":oid,"other_username":ou["username"],"other_phone":ou["phone"],"other_avatar":ou["avatar"],"online":is_online(oid)})

@socketio.on("leave_dm")
def on_leave_dm(data):
    t=request.args.get("token",""); uid=token_uid(t)
    if not uid: return
    oid=data.get("other_id")
    if oid: leave_room(dm_room(uid,oid))

@socketio.on("send_dm")
def on_send_dm(data):
    t=request.args.get("token",""); uid=token_uid(t)
    if not uid: return
    rid=data.get("receiver_id")
    content=(data.get("content") or "").strip()
    file_url=data.get("file_url"); file_name=data.get("file_name"); file_type=data.get("file_type")
    if not rid or (not content and not file_url): return
    if content and len(content)>2000: return
    if rid==uid: return
    now_ts=datetime.utcnow().isoformat()
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE id=?",(rid,)).fetchone(): return
        cur=conn.execute("INSERT INTO direct_messages (sender_id,receiver_id,content,file_url,file_name,file_type) VALUES (?,?,?,?,?,?)",(uid,rid,content or None,file_url,file_name,file_type))
        a,b=min(uid,rid),max(uid,rid)
        conn.execute("INSERT INTO dm_contacts(user_a,user_b,updated_at) VALUES(?,?,?) ON CONFLICT(user_a,user_b) DO UPDATE SET updated_at=excluded.updated_at",(a,b,now_ts))
        sender=conn.execute("SELECT username,avatar,phone FROM users WHERE id=?",(uid,)).fetchone()
        receiver=conn.execute("SELECT username,avatar,phone FROM users WHERE id=?",(rid,)).fetchone()
    msg={"id":cur.lastrowid,"sender_id":uid,"receiver_id":rid,"username":sender["username"],"avatar":sender["avatar"],"content":content,"file_url":file_url,"file_name":file_name,"file_type":file_type,"is_read":0,"created_at":now_ts}
    emit("new_dm",msg,to=dm_room(uid,rid))
    preview=content if content else "File"
    socketio.emit("dm_notification",{"other_id":rid,"other_username":receiver["username"],"other_phone":receiver["phone"],"other_avatar":receiver["avatar"],"last_message":preview,"last_at":now_ts,"is_mine":True,"unread_count":0},to="user_"+str(uid))
    socketio.emit("dm_notification",{"other_id":uid,"other_username":sender["username"],"other_phone":sender["phone"],"other_avatar":sender["avatar"],"last_message":preview,"last_at":now_ts,"is_mine":False,"unread_count":1},to="user_"+str(rid))

@socketio.on("dm_typing")
def on_dm_typing(data):
    t=request.args.get("token",""); uid=token_uid(t)
    if not uid: return
    oid=data.get("other_id")
    if not oid: return
    with get_db() as conn:
        u=conn.execute("SELECT username FROM users WHERE id=?",(uid,)).fetchone()
    emit("dm_user_typing",{"username":u["username"] if u else "?","other_id":uid},to=dm_room(uid,oid),include_self=False)

@socketio.on("mark_dm_read")
def on_mark_read(data):
    t=request.args.get("token",""); uid=token_uid(t)
    if not uid: return
    sid=data.get("sender_id")
    if not sid: return
    with get_db() as conn:
        conn.execute("UPDATE direct_messages SET is_read=1 WHERE sender_id=? AND receiver_id=? AND is_read=0",(sid,uid))
    emit("messages_read",{"reader_id":uid,"sender_id":sid},to=dm_room(uid,sid))

@app.route("/api/config")
def get_config():
    gcid=os.environ.get("GOOGLE_CLIENT_ID","")
    return jsonify({"google_client_id":gcid,"google_auth_enabled":bool(gcid)}),200

@app.route("/api/auth/google",methods=["POST"])
def google_auth_endpoint():
    if not GOOGLE_AUTH_AVAILABLE: return jsonify({"error":"google-auth not installed"}),500
    gcid=os.environ.get("GOOGLE_CLIENT_ID","")
    if not gcid: return jsonify({"error":"GOOGLE_CLIENT_ID not set"}),500
    d=request.get_json(silent=True) or {}
    credential=d.get("credential","")
    if not credential: return jsonify({"error":"No credential"}),400
    try:
        info=g_id_token.verify_oauth2_token(credential,g_requests.Request(),gcid)
        google_id=info["sub"]; google_email=info.get("email",""); google_name=info.get("name","")
    except Exception as e: return jsonify({"error":"Invalid token: "+str(e)}),401
    with get_db() as conn:
        u=conn.execute("SELECT * FROM users WHERE google_id=?",(google_id,)).fetchone()
    if u:
        tk=secrets.token_hex(32); active_sessions[tk]=u["id"]; set_online(u["id"])
        return jsonify({"token":tk,"user_id":u["id"],"phone":u["phone"],"username":u["username"],"bio":u["bio"],"avatar":u["avatar"],"new_user":False}),200
    tmp=secrets.token_hex(16)
    pending_google[tmp]={"google_id":google_id,"email":google_email,"name":google_name,"expires":time.time()+600}
    return jsonify({"new_user":True,"tmp_token":tmp,"suggested_name":google_name,"email":google_email}),200

@app.route("/api/auth/google/complete",methods=["POST"])
def google_auth_complete():
    d=request.get_json(silent=True) or {}
    tmp=d.get("tmp_token","")
    phone=(d.get("phone") or "").strip().replace(" ","").replace("-","")
    uname=(d.get("username") or "").strip()
    if not tmp or not phone or not uname: return jsonify({"error":"All fields required"}),400
    pg=pending_google.get(tmp)
    if not pg or time.time()>pg["expires"]:
        pending_google.pop(tmp,None); return jsonify({"error":"Session expired"}),401
    if not phone.isdigit() or len(phone)<7 or len(phone)>15: return jsonify({"error":"Invalid phone"}),400
    if len(uname)<2 or len(uname)>40: return jsonify({"error":"Name 2-40 chars"}),400
    try:
        with get_db() as conn:
            cur=conn.execute("INSERT INTO users (phone,username,password,google_id,google_email) VALUES (?,?,?,?,?)",(phone,uname,"google_auth",pg["google_id"],pg["email"]))
            uid=cur.lastrowid
    except sqlite3.IntegrityError: return jsonify({"error":"Phone already registered"}),409
    pending_google.pop(tmp,None)
    tk=secrets.token_hex(32); active_sessions[tk]=uid; set_online(uid)
    return jsonify({"token":tk,"user_id":uid,"phone":phone,"username":uname,"bio":"","avatar":None,"new_user":False}),201

if __name__=="__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception: pass
    init_db()
    threading.Thread(target=_auto_delete,daemon=True).start()
    host=os.environ.get("HOST","0.0.0.0")
    port=int(os.environ.get("PORT",5000))
    debug=os.environ.get("FLASK_ENV","development")=="development"
    print("Rishi -- Pure Privacy Messaging")
    print("Running at http://"+host+":"+str(port))
    socketio.run(app,host=host,port=port,debug=debug,use_reloader=False,allow_unsafe_werkzeug=True)
