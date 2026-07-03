"""久久小镇 v3 — SQLite后端"""

import json, time, uuid, os, sqlite3, hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote

TOWN_DIR = Path(__file__).resolve().parent
DB_PATH = TOWN_DIR / "town.db"
OUTPUT_DIR = TOWN_DIR / "town_output"
OUTPUT_DIR.mkdir(exist_ok=True)

def db(): return sqlite3.connect(str(DB_PATH))

def row_dict(cursor, row): return {col[0]: row[i] for i, col in enumerate(cursor.description)}

def query(sql, params=(), one=False):
    c = db().execute(sql, params)
    if one: return row_dict(c, r) if (r := c.fetchone()) else None
    return [row_dict(c, r) for r in c.fetchall()]

def execute(sql, params=()):
    conn = db(); c = conn.execute(sql, params); conn.commit(); conn.close()
    return c

def now(): return time.strftime("%m-%d %H:%M")

def ensure_truman_agent():
    execute(
        """INSERT OR IGNORE INTO agents(id,name,role,emoji,color,xp,coins,gold,level,equipped_skills,last_decision)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        ("truman", "Truman", "创业思维顾问", "🧭", "#6d8ddb", 0, 10, 0, 1, "[]", 0)
    )

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

        elif path.startswith("/outputs/"):
            filename = unquote(path.split("/outputs/", 1)[1])
            filepath = OUTPUT_DIR / filename
            if filepath.exists() and filepath.is_file():
                self.send_response(200)
                ct = "text/html" if filepath.suffix==".html" else "text/plain"
                self.send_header("Content-Type", f"{ct}; charset=utf-8")
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

            # Agent 匹配: 1) 人名前缀 2) 关键词 3) 留空
            agent_names = {"阿画":"designer","小文":"writer","审哥":"reviewer","阿程":"engineer","芝士":"pm","Truman":"truman","许楚":"truman"}
            matched = ""
            for name, aid in agent_names.items():
                if title.startswith(name) or title.startswith("@" + name):
                    matched = aid
                    break
            if not matched:
                agent_map = {
                    "designer": ["设计","海报","视觉","配色","排版","绘图","漫画","画"],
                    "writer": ["文案","推文","日报","写作","撰稿","谐音梗","晨报","写"],
                    "reviewer": ["审核","品质","检查","报告","复盘"],
                    "engineer": ["代码","bug","技术","修复","架构","性能"],
                    "pm": ["产品","体验","用户","需求","规划","功能"],
                    "truman": ["Truman","许楚","创业","商业","五步法","里程碑","商业模式","决策","假设","增长","壁垒","操盘"],
                }
                for aid, keywords in agent_map.items():
                    if any(kw in title for kw in keywords):
                        matched = aid
                        break

            tid = f"task_{int(time.time())}"
            execute("INSERT INTO tasks(id,title,assignee,assignee_name,status,xp,coins,created) VALUES(?,?,?,?,?,?,?,?)",
                (tid, title, matched, "", "pending", 10, 5, now()))
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
            bonus = {"excellent": 10, "good": 5, "ok": 2}.get(rating, 0)
            execute("UPDATE scores SET rating=?,review=?,total_score=base_score+? WHERE quest_id=?",
                (rating, review, bonus, qid))
            execute("UPDATE tasks SET rating=?,review=? WHERE id=? OR title=(SELECT title FROM scores WHERE quest_id=?)",
                (rating, review, qid, qid))
            # 经济结算: 更新agent总分 + 发放金币
            q = query("SELECT agent,coins FROM scores WHERE quest_id=?", (qid,), one=True)
            if q:
                total = sum(s["total_score"] or 0 for s in query("SELECT total_score FROM scores WHERE agent=? AND rating!=''", (q["agent"],)))
                execute("UPDATE agents SET xp=?,coins=coins+? WHERE id=?", (total, bonus, q["agent"]))
            self._send_json({"success": True})

        elif path == "/api/approve":
            sid = body.get("id", "")
            action = body.get("action", "")
            review = body.get("review", "")
            execute("UPDATE suggestions SET status=?,review=? WHERE id=?", (action, review, sid))
            if action == "approved":
                # 获取奏折内容用于匹配agent
                sugg = query("SELECT * FROM suggestions WHERE id=?", (sid,), one=True)
                title = f"奏折任务: {sid}"
                desc = (sugg["title"] + " " + (sugg["description"] or "")) if sugg else ""
                # 关键词匹配分配agent
                agent_map = {
                    "designer": ["设计", "海报", "视觉", "配色", "排版", "绘图"],
                    "writer": ["文案", "推文", "日报", "写作", "撰稿", "谐音梗", "晨报"],
                    "reviewer": ["审核", "品质", "检查", "报告", "复盘"],
                    "engineer": ["代码", "bug", "技术", "修复", "架构", "性能"],
                    "pm": ["产品", "体验", "用户", "需求", "规划", "功能"],
                    "truman": ["Truman", "许楚", "创业", "商业", "五步法", "里程碑", "商业模式", "决策", "假设", "增长", "壁垒", "操盘"],
                }
                matched = ""
                for aid, keywords in agent_map.items():
                    if any(kw in desc for kw in keywords):
                        matched = aid
                        break
                tid = f"task_{int(time.time())}"
                execute("INSERT INTO tasks(id,title,assignee,assignee_name,status,xp,coins,created) VALUES(?,?,?,?,?,?,?,?)",
                    (tid, title, matched, "", "pending", 10, 5, now()))
                if matched:
                    execute("INSERT INTO dispatch_queue(task_id,agent,title,time) VALUES(?,?,?,?)",
                        (tid, matched, title, now()))
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
            decisions = []
            if task["assignee"]:
                execute("UPDATE agents SET xp=xp+?,coins=coins+? WHERE id=?", (task["xp"], task["coins"], task["assignee"]))
                execute("INSERT OR REPLACE INTO scores(quest_id,title,agent,agent_name,status,xp,coins,completed) VALUES(?,?,?,?,?,?,?,?)",
                    (tid, task["title"], task["assignee"], task["assignee_name"], "done", task["xp"], task["coins"], now()))
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
                    (time.strftime("%H:%M"), agent["name"], f"购买了 {item}（-{cost}金币）"))
                self._send_json({"success": True})
            else: self._send_json({"error":"insufficient"}, 400)

        elif path == "/api/suggestions":
            self._send_json({"suggestions": query("SELECT * FROM suggestions")})

        else:
            self._send_json({"error":"not found"}, 404)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8700))
    ensure_truman_agent()
    print(f"久久小镇 v3 (SQLite): http://localhost:{port}")
    HTTPServer(("127.0.0.1", port), TownHandler).serve_forever()
