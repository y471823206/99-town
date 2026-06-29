"""久久小镇 — JSON → SQLite 迁移脚本"""

import json, sqlite3, time, os, shutil
from pathlib import Path
from datetime import datetime

TOWN = Path(r"D:\北北")
DB_PATH = TOWN / "town.db"
BACKUP_DIR = TOWN / "json_backup"

def migrate():
    # 1. 备份旧JSON
    BACKUP_DIR.mkdir(exist_ok=True)
    for f in TOWN.glob("*.json"):
        shutil.copy2(f, BACKUP_DIR / f.name)
    print(f"备份: {list(BACKUP_DIR.glob('*.json'))}")

    # 2. 建库
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")

    db.executescript("""
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
            assignee TEXT REFERENCES agents(id),
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
            agent TEXT REFERENCES agents(id),
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
            agent TEXT NOT NULL,
            title TEXT DEFAULT '',
            time TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS town_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)

    now = datetime.now().strftime("%m-%d %H:%M")

    # 3. 迁移agents
    eco = json.load(open(TOWN / "town_economy.json", encoding="utf-8"))
    for aid, a in eco.get("agents", {}).items():
        db.execute("""INSERT OR REPLACE INTO agents(id,name,role,emoji,color,xp,coins,gold,level,equipped_skills)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (
            aid, a.get("name", aid), a.get("role", ""), a.get("emoji", ""),
            a.get("color", ""), a.get("xp", 0), a.get("coins", 0),
            a.get("gold", 0), a.get("level", 1), json.dumps(a.get("equipped_skills", []))
        ))
    db.execute("INSERT OR REPLACE INTO town_state VALUES('town_xp',?)", (str(eco.get("town_xp", 0)),))
    db.execute("INSERT OR REPLACE INTO town_state VALUES('town_gold',?)", (str(eco.get("town_gold", 0)),))
    print(f"agents: {len(eco.get('agents',{}))} 条")

    # 4. 迁移tasks
    tasks = json.load(open(TOWN / "town_tasks.json", encoding="utf-8"))
    for t in tasks.get("tasks", []):
        db.execute("""INSERT OR REPLACE INTO tasks(id,title,assignee,assignee_name,status,auto_generated,xp,coins,output,outputs,created,completed)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
            t.get("id", f"task_{int(time.time())}"), t.get("title", ""),
            t.get("assignee", ""), t.get("assignee_name", ""),
            t.get("status", "done"), 1 if t.get("auto_generated") else 0,
            t.get("xp", 10), t.get("coins", 5),
            t.get("output", ""), json.dumps(t.get("outputs", [])),
            t.get("created", now), t.get("completed", now)
        ))
    print(f"tasks: {len(tasks.get('tasks',[]))} 条")

    # 5. 迁移scores
    scores = json.load(open(TOWN / "town_scores.json", encoding="utf-8"))
    for q in scores.get("quests", []):
        db.execute("""INSERT OR REPLACE INTO scores(quest_id,title,agent,agent_name,status,rating,review,total_score,base_score,xp,coins,output,completed)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            q.get("id", f"quest_{int(time.time())}"), q.get("title", ""),
            q.get("agent", ""), q.get("agent_name", ""),
            q.get("status", "done"), q.get("rating", ""), q.get("review", ""),
            q.get("total_score", 0), q.get("base_score", 10),
            q.get("xp", 10), q.get("coins", 5),
            q.get("output", ""), q.get("completed", now)
        ))
    print(f"scores: {len(scores.get('quests',[]))} 条")

    # 6. 迁移logs
    logs = json.load(open(TOWN / "town_log.json", encoding="utf-8"))
    for l in logs:
        db.execute("INSERT INTO logs(time,agent,text) VALUES(?,?,?)",
            (l.get("time", now), l.get("agent", ""), l.get("text", "")))
    print(f"logs: {len(logs)} 条")

    # 7. 迁移assets
    assets = json.load(open(TOWN / "town_assets.json", encoding="utf-8"))
    for a in assets:
        db.execute("INSERT OR REPLACE INTO assets(id,file,type,size,time,url) VALUES(?,?,?,?,?,?)",
            (a.get("id", ""), a.get("file", ""), a.get("type", ""),
             a.get("size", 0), a.get("time", ""), a.get("url", "")))
    print(f"assets: {len(assets)} 条")

    # 8. 迁移suggestions
    sugg = json.load(open(TOWN / "town_suggestions.json", encoding="utf-8"))
    for s in sugg.get("suggestions", []):
        db.execute("INSERT OR REPLACE INTO suggestions(id,title,description,category,status,period,review,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (s.get("id", ""), s.get("title", ""), s.get("desc", ""),
             s.get("category", ""), s.get("status", "pending"),
             s.get("period", ""), s.get("review", ""), s.get("created_at", "")))
    print(f"suggestions: {len(sugg.get('suggestions',[]))} 条")

    db.commit()
    db.close()
    print(f"\n迁移完成 → {DB_PATH} ({DB_PATH.stat().st_size} bytes)")
    print(f"备份 → {BACKUP_DIR}/")

if __name__ == "__main__":
    migrate()
