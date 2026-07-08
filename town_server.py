"""久久小镇 v3 — SQLite后端"""

import json, time, uuid, os, sqlite3, hashlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote

TOWN_DIR = Path(__file__).resolve().parent
DB_PATH = TOWN_DIR / "town.db"
OUTPUT_DIR = TOWN_DIR / "town_output"
OUTPUT_DIR.mkdir(exist_ok=True)

DEFAULT_AGENTS = [
    ("designer", "阿画", "视觉设计师", "🎨", "#e76f51"),
    ("writer", "小文", "文案写手", "✍️", "#f4a261"),
    ("reviewer", "审哥", "审核员", "🔍", "#2a9d8f"),
    ("engineer", "阿程", "全栈工程师", "💻", "#457b9d"),
    ("pm", "芝士", "产品经理", "🧀", "#e9c46a"),
    ("craftsman", "小匠", "技能官", "🛠️", "#8d6e63"),
    ("mayor", "久久", "镇长", "🏛️", "#c4553b"),
]
AGENT_NAMES = {"阿画":"designer","小文":"writer","审哥":"reviewer","阿程":"engineer","芝士":"pm","小匠":"craftsman"}
AGENT_KEYWORDS = {
    "designer": ["设计", "海报", "视觉", "配色", "排版", "绘图", "漫画", "画"],
    "writer": ["文案", "推文", "日报", "写作", "撰稿", "谐音梗", "晨报", "写"],
    "reviewer": ["审核", "品质", "检查", "报告", "复盘"],
    "engineer": ["代码", "bug", "技术", "修复", "架构", "性能", "cron", "调度", "备份", "配置", "TDD", "测试"],
    "pm": ["产品", "体验", "用户", "需求", "规划", "功能", "积压"],
    "craftsman": ["技能", "skill", "插件", "能力", "安装", "安全检查", "修复bug", "优化"],
}
AGENT_DISPLAY_NAMES = {aid: name for aid, name, *_ in DEFAULT_AGENTS}

def infer_agent_for_text(text):
    """Infer the owning town resident from explicit names first, then keywords."""
    text = text or ""
    for name, aid in AGENT_NAMES.items():
        if text.startswith(name) or text.startswith("@" + name) or name in text:
            return aid
    for aid, keywords in AGENT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return aid
    return ""

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT DEFAULT '',
    emoji TEXT DEFAULT '',
    color TEXT DEFAULT '',
    xp INTEGER DEFAULT 0,
    coins INTEGER DEFAULT 0,
    gold INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    equipped_skills TEXT DEFAULT '[]',
    last_decision REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT DEFAULT '',
    assignee TEXT DEFAULT '',
    assignee_name TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    auto_generated INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 10,
    coins INTEGER DEFAULT 5,
    output TEXT DEFAULT '',
    outputs TEXT DEFAULT '[]',
    rating TEXT DEFAULT '',
    review TEXT DEFAULT '',
    total_score INTEGER DEFAULT 0,
    base_score INTEGER DEFAULT 10,
    created TEXT DEFAULT '',
    completed TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS scores (
    quest_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    agent TEXT DEFAULT '',
    agent_name TEXT DEFAULT '',
    status TEXT DEFAULT 'done',
    rating TEXT DEFAULT '',
    review TEXT DEFAULT '',
    total_score INTEGER DEFAULT 0,
    base_score INTEGER DEFAULT 10,
    xp INTEGER DEFAULT 10,
    coins INTEGER DEFAULT 5,
    output TEXT DEFAULT '',
    completed TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL,
    agent TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    file TEXT NOT NULL,
    type TEXT DEFAULT '',
    size INTEGER DEFAULT 0,
    time TEXT DEFAULT '',
    url TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS suggestions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    period TEXT DEFAULT '',
    review TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS dispatch_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    agent TEXT DEFAULT '',
    title TEXT DEFAULT '',
    time TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS feedback_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT DEFAULT '',
    agent_name TEXT DEFAULT '',
    task_id TEXT DEFAULT '',
    rating TEXT DEFAULT '',
    review TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    processed INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS town_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

EXPECTED_COLUMNS = {
    "agents": {"role": "TEXT DEFAULT ''", "emoji": "TEXT DEFAULT ''", "color": "TEXT DEFAULT ''", "xp": "INTEGER DEFAULT 0", "coins": "INTEGER DEFAULT 0", "gold": "INTEGER DEFAULT 0", "level": "INTEGER DEFAULT 1", "equipped_skills": "TEXT DEFAULT '[]'", "last_decision": "REAL DEFAULT 0"},
    "tasks": {"body": "TEXT DEFAULT ''", "assignee": "TEXT DEFAULT ''", "assignee_name": "TEXT DEFAULT ''", "status": "TEXT DEFAULT 'pending'", "auto_generated": "INTEGER DEFAULT 0", "xp": "INTEGER DEFAULT 10", "coins": "INTEGER DEFAULT 5", "output": "TEXT DEFAULT ''", "outputs": "TEXT DEFAULT '[]'", "rating": "TEXT DEFAULT ''", "review": "TEXT DEFAULT ''", "total_score": "INTEGER DEFAULT 0", "base_score": "INTEGER DEFAULT 10", "created": "TEXT DEFAULT ''", "completed": "TEXT DEFAULT ''"},
    "scores": {"agent": "TEXT DEFAULT ''", "agent_name": "TEXT DEFAULT ''", "status": "TEXT DEFAULT 'done'", "rating": "TEXT DEFAULT ''", "review": "TEXT DEFAULT ''", "total_score": "INTEGER DEFAULT 0", "base_score": "INTEGER DEFAULT 10", "xp": "INTEGER DEFAULT 10", "coins": "INTEGER DEFAULT 5", "output": "TEXT DEFAULT ''", "completed": "TEXT DEFAULT ''"},
    "suggestions": {"description": "TEXT DEFAULT ''", "category": "TEXT DEFAULT ''", "status": "TEXT DEFAULT 'pending'", "period": "TEXT DEFAULT ''", "review": "TEXT DEFAULT ''", "created_at": "TEXT DEFAULT ''"},
    "dispatch_queue": {"agent": "TEXT DEFAULT ''", "title": "TEXT DEFAULT ''", "time": "TEXT DEFAULT ''"},
    "feedback_log": {"agent_id": "TEXT DEFAULT ''", "agent_name": "TEXT DEFAULT ''", "task_id": "TEXT DEFAULT ''", "rating": "TEXT DEFAULT ''", "review": "TEXT DEFAULT ''", "created_at": "TEXT DEFAULT ''", "processed": "INTEGER DEFAULT 0"},
}

def ensure_schema():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executescript(SCHEMA)
        for table, columns in EXPECTED_COLUMNS.items():
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for name, spec in columns.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {spec}")
        for aid, name, role, emoji, color in DEFAULT_AGENTS:
            conn.execute(
                "INSERT OR IGNORE INTO agents(id,name,role,emoji,color) VALUES(?,?,?,?,?)",
                (aid, name, role, emoji, color),
            )
        conn.execute("INSERT OR IGNORE INTO town_state(key,value) VALUES('town_xp','0')")
        conn.execute("INSERT OR IGNORE INTO town_state(key,value) VALUES('town_gold','0')")
        # 任务记录以 scores 为事实账本；历史 done 任务若漏写 scores，会在前端消失。
        # 启动和 /api/state 时补齐，保证以往任务记录可见且 /api/rate 能写入 feedback_log。
        conn.execute("""
            INSERT OR IGNORE INTO scores(quest_id,title,agent,agent_name,status,xp,coins,output,completed)
            SELECT id,title,assignee,assignee_name,status,xp,coins,output,completed
            FROM tasks
            WHERE status IN ('done','failed','backlog')
              AND COALESCE(assignee,'') != ''
        """)
        conn.execute("""
            UPDATE scores
            SET agent=COALESCE(NULLIF(agent,''), (SELECT tasks.assignee FROM tasks WHERE tasks.id=scores.quest_id)),
                agent_name=COALESCE(NULLIF(agent_name,''), (SELECT tasks.assignee_name FROM tasks WHERE tasks.id=scores.quest_id)),
                status=(SELECT tasks.status FROM tasks WHERE tasks.id=scores.quest_id),
                output=COALESCE(NULLIF((SELECT tasks.output FROM tasks WHERE tasks.id=scores.quest_id),''), output),
                completed=COALESCE(NULLIF((SELECT tasks.completed FROM tasks WHERE tasks.id=scores.quest_id),''), completed)
            WHERE EXISTS (SELECT 1 FROM tasks WHERE tasks.id=scores.quest_id AND tasks.status IN ('done','failed','backlog'))
        """)
        for row in conn.execute("""
            SELECT s.quest_id, COALESCE(t.title, s.title, '') AS title
            FROM scores s
            LEFT JOIN tasks t ON t.id=s.quest_id
            WHERE s.status='done' AND COALESCE(s.agent,'')=''
        """):
            inferred = infer_agent_for_text(row[1])
            if inferred:
                conn.execute(
                    "UPDATE scores SET agent=?, agent_name=? WHERE quest_id=?",
                    (inferred, AGENT_DISPLAY_NAMES.get(inferred, ""), row[0]),
                )
                conn.execute(
                    "UPDATE tasks SET assignee=?, assignee_name=? WHERE id=? AND COALESCE(assignee,'')=''",
                    (inferred, AGENT_DISPLAY_NAMES.get(inferred, ""), row[0]),
                )
        conn.commit()

    finally:
        conn.close()

ensure_schema()

def db(): return sqlite3.connect(str(DB_PATH))

def row_dict(cursor, row): return {col[0]: row[i] for i, col in enumerate(cursor.description)}

def query(sql, params=(), one=False):
    conn = db()
    try:
        c = conn.execute(sql, params)
        if one:
            r = c.fetchone()
            return row_dict(c, r) if r else None
        return [row_dict(c, r) for r in c.fetchall()]
    finally:
        conn.close()

def execute(sql, params=()):
    conn = db(); c = conn.execute(sql, params); conn.commit(); conn.close()
    return c

def now(): return time.strftime("%m-%d %H:%M")

def new_task_id(prefix="task"):
    """Return a collision-resistant task id for rapid consecutive API calls."""
    return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"

class TownHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length and length > 0:
            raw = self.rfile.read(length)
            for enc in ["utf-8", "gbk", "latin-1"]:
                try: return json.loads(raw.decode(enc))
                except: continue
        return {}

    def do_OPTIONS(self):
        self.send_response(200)
        for h in ["Access-Control-Allow-Origin","Access-Control-Allow-Methods","Access-Control-Allow-Headers"]:
            self.send_header(h, "*")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/state":
            ensure_schema()
            agents = {a["id"]: {k: a[k] for k in ["name","role","emoji","color","xp","coins","gold","level","equipped_skills","last_decision"]} for a in query("SELECT * FROM agents")}
            agents_d = {a["id"]: a for a in query("SELECT * FROM agents")}
            tasks = query("SELECT * FROM tasks")
            quests = query("SELECT * FROM scores")
            assets = query("SELECT * FROM assets")
            dispatch = query("SELECT * FROM dispatch_queue")
            log_rows = query("SELECT * FROM logs ORDER BY id DESC LIMIT 30")
            log = [{"time": l["time"], "agent": l["agent"], "text": l["text"]} for l in log_rows]
            suggestions = query("SELECT * FROM suggestions")
            txp = query("SELECT value FROM town_state WHERE key='town_xp'", one=True)
            tgold = query("SELECT value FROM town_state WHERE key='town_gold'", one=True)
            self._send_json({
                "agents": agents_d, "tasks": tasks, "quests": quests, "assets": assets,
                "log": log, "dispatch": dispatch, "suggestions": {"suggestions": suggestions},
                "economy": {"agents": agents, "town_xp": int(txp["value"]) if txp else 0, "town_gold": int(tgold["value"]) if tgold else 0},
                "scoring_rules": {"rating_bonus": {"excellent": 10, "good": 5, "ok": 2, "poor": -2}},
                "server_time": time.strftime("%H:%M:%S")
            })

        elif path == "/api/assets":
            # 重建资产索引
            execute("DELETE FROM assets")
            for i, f in enumerate(sorted(OUTPUT_DIR.glob("*"), key=lambda x: x.stat().st_mtime)):
                if f.is_file():
                    aid = hashlib.md5(f.name.encode()).hexdigest()[:8]
                    ext = f.suffix.lower()
                    typ = "图片" if ext in [".png",".jpg",".jpeg",".gif",".svg"] else "文案" if ext in [".md",".txt"] else "代码" if ext in [".py",".js"] else "其他"
                    execute("INSERT INTO assets VALUES(?,?,?,?,?,?)", (
                        aid, f.name, typ, f.stat().st_size,
                        time.strftime("%m-%d %H:%M", time.localtime(f.stat().st_mtime)),
                        f"/file/{i}"
                    ))
            self._send_json(query("SELECT * FROM assets"))

        elif path == "/api/dispatch":
            self._send_json(query("SELECT * FROM dispatch_queue"))

        elif path in ("/gallery", "/gallery.html"):
            html = TOWN_DIR / "gallery.html"
            if html.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.read_bytes())
            else:
                self._send_json({"error": "not found"}, 404)

        elif path.startswith("/docs/"):
            docs_root = (TOWN_DIR / "docs").resolve()
            doc_path = (TOWN_DIR / unquote(path.lstrip("/"))).resolve()
            try:
                doc_path.relative_to(docs_root)
                allowed = doc_path.suffix.lower() in (".md", ".json")
            except ValueError:
                allowed = False

            if allowed and doc_path.exists() and doc_path.is_file():
                ct = "application/json" if doc_path.suffix.lower() == ".json" else "text/markdown"
                self.send_response(200)
                self.send_header("Content-Type", f"{ct}; charset=utf-8")
                self.end_headers()
                self.wfile.write(doc_path.read_bytes())
            else:
                self._send_json({"error": "not found"}, 404)

        elif path.startswith("/outputs/"):
            filename = unquote(path.split("/outputs/", 1)[1])
            filepath = OUTPUT_DIR / filename
            if filepath.exists() and filepath.is_file():
                self.send_response(200)
                content_types = {
                    ".html": "text/html; charset=utf-8",
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".webp": "image/webp",
                    ".gif": "image/gif",
                    ".svg": "image/svg+xml; charset=utf-8",
                }
                ct = content_types.get(filepath.suffix.lower(), "text/plain; charset=utf-8")
                self.send_header("Content-Type", ct)
                self.end_headers()
                self.wfile.write(filepath.read_bytes())
            else: self._send_json({"error":"not found"}, 404)

        elif path.startswith("/file/"):
            try:
                idx = int(path.split("/file/", 1)[1])
                assets = sorted(OUTPUT_DIR.glob("*"), key=lambda x: x.stat().st_mtime)
                if 0 <= idx < len(assets) and assets[idx].is_file():
                    self.send_response(200)
                    ct = "text/html" if assets[idx].suffix==".html" else "text/plain"
                    self.send_header("Content-Type", f"{ct}; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(assets[idx].read_bytes())
                else: self._send_json({"error":"not found"}, 404)
            except: self._send_json({"error":"not found"}, 404)

        else:
            html = TOWN_DIR / "town.html"
            if html.exists():
                # Inject initial state so the page works without async fetch
                agents_d = {a["id"]: a for a in query("SELECT * FROM agents")}
                tasks = query("SELECT * FROM tasks")
                quests = query("SELECT * FROM scores")
                assets = query("SELECT * FROM assets")
                dispatch = query("SELECT * FROM dispatch_queue")
                log_rows = query("SELECT * FROM logs ORDER BY id DESC LIMIT 30")
                log = [{"time": l["time"], "agent": l["agent"], "text": l["text"]} for l in log_rows]
                suggestions = query("SELECT * FROM suggestions")
                txp = query("SELECT value FROM town_state WHERE key='town_xp'", one=True)
                tgold = query("SELECT value FROM town_state WHERE key='town_gold'", one=True)
                init_state = json.dumps({
                    "agents": agents_d, "tasks": tasks, "quests": quests, "assets": assets,
                    "log": log, "dispatch": dispatch, "suggestions": {"suggestions": suggestions},
                    "economy": {"town_xp": int(txp["value"]) if txp else 0, "town_gold": int(tgold["value"]) if tgold else 0},
                    "scoring_rules": {"rating_bonus": {"excellent": 10, "good": 5, "ok": 2, "poor": -2}},
                    "server_time": time.strftime("%H:%M:%S")
                }, ensure_ascii=False)
                raw = html.read_bytes().decode("utf-8")
                injected = raw.replace(
                    '<script>\n// ============================================================',
                    '<script>\nwindow.__INIT_STATE__ = ' + init_state + ';\n// ============================================================'
                )
                self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8")
                self.end_headers(); self.wfile.write(injected.encode("utf-8"))
            else: self._send_json({"error":"not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/api/publish":
            title = body.get("title", "").strip()
            if not title: return self._send_json({"error":"empty title"}, 400)

            # Agent 匹配: 1) 人名前缀/正文提及 2) 关键词 3) 留空
            description = body.get("description", "")
            matched = infer_agent_for_text(title + " " + description)
            agent_name = AGENT_DISPLAY_NAMES.get(matched, "")
            tid = new_task_id()
            execute("INSERT INTO tasks(id,title,body,assignee,assignee_name,status,xp,coins,created) VALUES(?,?,?,?,?,?,?,?,?)",
                (tid, title, description, matched, agent_name, "pending", 10, 5, now()))
            execute("INSERT INTO scores(quest_id,title,agent,agent_name,status,xp,coins) VALUES(?,?,?,?,?,?,?)",
                (tid, title, matched, agent_name, "pending", 10, 5))
            if matched:
                execute("INSERT INTO dispatch_queue(task_id,agent,title,time) VALUES(?,?,?,?)",
                    (tid, matched, title, now()))
            else:
                execute("INSERT INTO dispatch_queue(task_id,agent,title,time) VALUES(?,?,?,?)",
                    (tid, "", title, now()))
            self._send_json({"success": True, "task_id": tid, "agent": matched or "待匹配"})

        elif path == "/api/rate":
            qid = body.get("quest_id", "")
            rating = body.get("rating", "")
            review = body.get("review", "")
            bonus = {"excellent": 10, "good": 5, "ok": 2, "poor": -2}.get(rating, 0)
            execute("UPDATE scores SET rating=?,review=?,total_score=base_score+? WHERE quest_id=?",
                (rating, review, bonus, qid))
            execute("UPDATE tasks SET rating=?,review=? WHERE id=? OR title=(SELECT title FROM scores WHERE quest_id=?)",
                (rating, review, qid, qid))
            # 经济结算: 更新agent总分 + 发放积分
            q = query("SELECT agent,coins FROM scores WHERE quest_id=?", (qid,), one=True)
            if q:
                total = sum(s["total_score"] or 0 for s in query("SELECT total_score FROM scores WHERE agent=? AND rating!=''", (q["agent"],)))
                execute("UPDATE agents SET xp=?,coins=coins+? WHERE id=?", (total, bonus, q["agent"]))
            # 反馈自动沉淀到 feedback_log
            q2 = query("SELECT agent,agent_name FROM scores WHERE quest_id=?", (qid,), one=True)
            if q2 and (rating or review):
                execute("INSERT INTO feedback_log(agent_id,agent_name,task_id,rating,review,created_at) VALUES(?,?,?,?,?,?)",
                    (q2["agent"], q2["agent_name"], qid, rating, review, now()))
            self._send_json({"success": True})

        elif path == "/api/approve":
            sid = body.get("id", "")
            action = body.get("action", "")
            review = body.get("review", "")
            execute("UPDATE suggestions SET status=?,review=? WHERE id=?", (action, review, sid))
            sugg = query("SELECT * FROM suggestions WHERE id=?", (sid,), one=True)
            if not sugg:
                self._send_json({"success": True})
                return
            if action == "approved":
                # 用奏折实际标题+描述作为任务内容
                desc = (sugg["title"] + " " + (sugg["description"] or "")).strip()
                matched = infer_agent_for_text(desc)
                tid = new_task_id()
                task_title = f"奏折任务: {sugg['title'][:40]}"
                agent_name = AGENT_DISPLAY_NAMES.get(matched, "")
                execute("INSERT INTO tasks(id,title,assignee,assignee_name,status,xp,coins,created) VALUES(?,?,?,?,?,?,?,?)",
                    (tid, task_title, matched, agent_name, "pending", 15, 8, now()))
                execute("INSERT INTO scores(quest_id,title,agent,agent_name,status,xp,coins) VALUES(?,?,?,?,?,?,?)",
                    (tid, task_title, matched, agent_name, "pending", 15, 8))
                execute("INSERT INTO dispatch_queue(task_id,agent,title,time) VALUES(?,?,?,?)",
                    (tid, matched, task_title, now()))
                execute("INSERT INTO logs(time,agent,text) VALUES(?,?,?)",
                    (now(), "北北", f"批准奏折「{sugg['title'][:20]}」→ 创建任务 {tid} (assignee={agent_name or '待匹配'})"))
                self._send_json({"success": True, "task_id": tid, "agent": matched or "待匹配"})
            else:
                execute("INSERT INTO logs(time,agent,text) VALUES(?,?,?)",
                    (now(), "北北", f"驳回奏折「{sugg['title'][:20]}」"))
                self._send_json({"success": True})

        elif path == "/api/clear_dispatch":
            execute("DELETE FROM dispatch_queue")
            self._send_json({"success": True})

        elif path == "/api/decide":
            agent_id = body.get("agent", "")
            agent = query("SELECT * FROM agents WHERE id=? AND id!='mayor'", (agent_id,), one=True)
            if not agent: return self._send_json({"decisions": []})
            if time.time() - (agent["last_decision"] or 0) < 300:
                return self._send_json({"decisions": [], "cooldown": True})
            decisions = []
            if agent["coins"] >= 30 and not json.loads(agent["equipped_skills"] or "[]"):
                decisions.append(f"购买了技能探索（-30G）")
                execute("UPDATE agents SET coins=coins-30 WHERE id=?", (agent_id,))
            execute("UPDATE agents SET last_decision=? WHERE id=?", (time.time(), agent_id))
            self._send_json({"success": True, "decisions": decisions})

        elif path == "/api/complete":
            tid = body.get("task_id", "")
            output_file = body.get("output", "")  # cron agent 传入的产出文件名
            task = query("SELECT * FROM tasks WHERE id=?", (tid,), one=True)
            if not task: return self._send_json({"error":"not found"}, 404)

            # 规范化 output: 去路径前缀，只留文件名
            if output_file:
                fname = output_file.replace("\\", "/").split("/")[-1]
                # 验证文件存在
                if (OUTPUT_DIR / fname).exists():
                    execute("UPDATE tasks SET output=? WHERE id=?", (fname, tid))
                else:
                    execute("UPDATE tasks SET output=? WHERE id=?", (f"⚠缺文件:{fname}", tid))
            elif not task["output"] or task["output"] in ("僵尸任务清理", ""):
                execute("UPDATE tasks SET output=? WHERE id=?", ("(无产出文件)", tid))

            execute("UPDATE tasks SET status='done',completed=? WHERE id=?", (now(), tid))
            if not task["assignee"]:
                inferred = infer_agent_for_text((task["title"] or "") + " " + (task.get("body") or ""))
                if inferred:
                    task["assignee"] = inferred
                    task["assignee_name"] = AGENT_DISPLAY_NAMES.get(inferred, "")
                    execute("UPDATE tasks SET assignee=?,assignee_name=? WHERE id=?", (task["assignee"], task["assignee_name"], tid))
            decisions = []
            if task["assignee"]:
                execute("UPDATE agents SET xp=xp+?,coins=coins+? WHERE id=?", (task["xp"], task["coins"], task["assignee"]))
                execute("INSERT OR IGNORE INTO scores(quest_id,title,agent,agent_name,status,xp,coins,completed) VALUES(?,?,?,?,?,?,?,?)",
                    (tid, task["title"], task["assignee"], task["assignee_name"], "done", task["xp"], task["coins"], now()))
                execute("UPDATE scores SET status='done',completed=? WHERE quest_id=?", (now(), tid))
                # 自动触发决策引擎
                agent = query("SELECT * FROM agents WHERE id=? AND id!='mayor'", (task["assignee"],), one=True)
                if agent and time.time() - (agent["last_decision"] or 0) >= 300:
                    if agent["coins"] >= 30 and not json.loads(agent["equipped_skills"] or "[]"):
                        execute("UPDATE agents SET coins=coins-30,last_decision=? WHERE id=?", (time.time(), task["assignee"]))
                        decisions.append(f"{agent['name']}自主购买了技能探索（-30G）")
                    else:
                        execute("UPDATE agents SET last_decision=? WHERE id=?", (time.time(), task["assignee"]))

            # 自动刷新 assets 索引
            execute("DELETE FROM assets")
            for i, f in enumerate(sorted(OUTPUT_DIR.glob("*"), key=lambda x: x.stat().st_mtime)):
                if f.is_file() and not f.name.startswith("."):
                    aid = hashlib.md5(f.name.encode()).hexdigest()[:8]
                    ext = f.suffix.lower()
                    typ = "图片" if ext in [".png",".jpg",".jpeg",".gif",".svg"] else "文案" if ext in [".md",".txt"] else "页面" if ext in [".html"] else "其他"
                    execute("INSERT OR REPLACE INTO assets VALUES(?,?,?,?,?,?)",
                        (aid, f.name, typ, f.stat().st_size, time.strftime("%m-%d %H:%M", time.localtime(f.stat().st_mtime)), f"/file/{i}"))

            self._send_json({"success": True, "decisions": decisions})

        elif path == "/api/buy":
            agent_id = body.get("agent_id", "")
            item = body.get("item", "")
            agent = query("SELECT * FROM agents WHERE id=? AND id!='mayor'", (agent_id,), one=True)
            if not agent: return self._send_json({"error":"not found"}, 404)
            shop = {"xp_boost": 20, "gold_boost": 20, "decorate": 15}
            cost = shop.get(item, 0)
            if cost and agent["coins"] >= cost:
                execute("UPDATE agents SET coins=coins-? WHERE id=?", (cost, agent_id))
                if item == "xp_boost": pass
                elif item == "gold_boost": pass
                elif item == "decorate": pass
                execute("INSERT INTO logs(time,agent,text) VALUES(?,?,?)",
                    (time.strftime("%H:%M"), agent["name"], f"购买了 {item}（-{cost}积分）"))
                self._send_json({"success": True})
            else: self._send_json({"error":"insufficient"}, 400)

        elif path == "/api/suggestions":
            self._send_json({"suggestions": query("SELECT * FROM suggestions")})

        else:
            self._send_json({"error":"not found"}, 404)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8700))
    print(f"久久小镇 v3 (SQLite): http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), TownHandler).serve_forever()
