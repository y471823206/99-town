"""久久小镇守护灵 v6 — SQLite后端"""

import json, time, urllib.request, subprocess, sys, http.client, random, os, sqlite3
from pathlib import Path
from datetime import datetime

TOWN = Path(r"D:\北北")
PORT = 8700
BASE = f"http://127.0.0.1:{PORT}"
DB_PATH = TOWN / "town.db"
CHECK_INTERVAL = 30
TICK_INTERVAL = 180
AGENT_NAMES = {"designer":"阿画","writer":"小文","reviewer":"审哥","mayor":"北北"}

def db(): return sqlite3.connect(str(DB_PATH))

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M')}] {msg}")

def add_town_log(agent, text):
    t = datetime.now().strftime("%H:%M")
    conn = db(); conn.execute("INSERT INTO logs(time,agent,text) VALUES(?,?,?)", (t, agent, text))
    conn.commit(); conn.close()

def llm_chat(prompt, max_tokens=3000):
    lines = (TOWN/"key.txt").read_text(encoding="utf-8").split("\n")
    ds_line = [l for l in lines if "deepseek" in l.lower()][0]
    ds_key = ds_line.split("\uff1a")[-1].strip().split()[0] if "\uff1a" in ds_line else ds_line.split(":")[-1].strip().split()[0]
    body = json.dumps({"model":"deepseek-chat","messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens}).encode()
    c = http.client.HTTPSConnection("api.deepseek.com", timeout=120)
    c.request("POST","/v1/chat/completions",body=body,headers={"Content-Type":"application/json","Authorization":"Bearer "+ds_key})
    r = c.getresponse(); d = json.loads(r.read()); c.close()
    return d["choices"][0]["message"]["content"] if "choices" in d else None

def heal_data():
    now = datetime.now().strftime("%m-%d %H:%M")
    try:
        conn = db()
        # 补缺失字段
        for t in conn.execute("SELECT id,output,outputs,completed,created FROM tasks WHERE completed='' OR created=''"):
            conn.execute("UPDATE tasks SET completed=?,created=? WHERE id=?", (now, now, t[0]))
        for q in conn.execute("SELECT quest_id,completed,agent,agent_name FROM scores WHERE completed='' OR agent_name=''"):
            name = AGENT_NAMES.get(q[2], q[2]) if q[2] else ""
            conn.execute("UPDATE scores SET completed=?,agent_name=? WHERE quest_id=?", (now, name, q[0]))
        # 补output
        for t in conn.execute("SELECT id,title FROM tasks WHERE status='done' AND output='' AND outputs='[]'"):
            od = TOWN/"town_output"
            if od.exists():
                tl = t[1].lower() if t[1] else ""
                for f in os.listdir(str(od)):
                    if any(kw in f.lower() for kw in tl.split()[:3] if len(kw)>1):
                        conn.execute("UPDATE tasks SET output=? WHERE id=?", (f"town_output/{f}", t[0])); break
        conn.commit(); conn.close()
        log("  heal: 数据自愈完成")
    except Exception as e: log(f"  heal异常:{e}")

def daily_creative():
    today = datetime.now().strftime("%m-%d")
    marker = TOWN / "town_output" / f".daily_done_{today}"
    if marker.exists(): return
    # 查最近评价作为创作反馈
    conn_fb = db()
    recent = conn_fb.execute("SELECT agent_name, rating, review FROM scores WHERE rating!='' AND review!='' ORDER BY completed DESC LIMIT 5").fetchall()
    conn_fb.close()
    feedback = ""
    if recent:
        feedback = "\n\n【久久最近的评价反馈，请参考改进】\n" + "\n".join(f"- {r[2]}" for r in recent)
    missions = [
        ("designer","阿画","生成一张久久小镇主题海报HTML。风格：温暖像素风RPG，米白底#faf7f2，炭黑字#1a1a1a，陶土红点缀#c4553b。typography-first，标题52px/副标题28px/正文18px。内容：一句久久说过的话作为主标题+小镇今日状态卡片+四个居民的像素头像+底部签名。完整的独立HTML文件，不要输出任务描述或指令文本。"),
        ("writer","小文","写一篇久久小镇日报HTML。风格：温暖像素风，米白底+炭黑+陶土红，typography-first。内容：小镇今日动态、居民创作成果、一句温暖的话。纯HTML，标题52px/正文18px。不要输出任务描述或指令文本。"),
        ("reviewer","审哥","生成一份小镇品质报告HTML。风格：温暖像素风，米白底+炭黑+陶土红。内容：最近产出质量概述、亮点、改进建议。纯HTML typography-first。不要输出任务描述或指令文本。"),
    ]
    aid, name, task = random.choice(missions)
    add_town_log("北北",f"每日创作: {name}")
    log(f"  每日创作: {name}")
    try:
        html = llm_chat(task + feedback, max_tokens=4000)
        if html and len(html)>200:
            html = html.strip()
            # 彻底清理：只保留HTML，剔除LLM的说明文字和markdown标记
            # 1. 去掉markdown包裹
            if "```html" in html:
                html = html.split("```html", 1)[1]
                if "```" in html: html = html.split("```", 1)[0]
            elif html.startswith("```"):
                html = html.split("```", 1)[1] if len(html.split("```")) > 1 else html
            # 2. 从<!DOCTYPE或<html开始截取
            for marker in ["<!DOCTYPE", "<html"]:
                idx = html.find(marker)
                if idx > 0: html = html[idx:]; break
            html = html.strip()
            fname = f"久久_{name}_创作_{today}.html".replace("/","-")
            (TOWN/"town_output"/fname).write_text(html, encoding="utf-8")
            now = datetime.now().strftime("%H:%M"); now_full = datetime.now().strftime("%m-%d %H:%M")
            title = task.split("。")[0].split("HTML")[0].strip()
            tid = f"daily_{int(time.time())}"
            conn = db()
            conn.execute("INSERT INTO tasks(id,title,assignee,assignee_name,status,auto_generated,xp,coins,output,created,completed) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (tid, title, aid, name, "done", 1, 10, 5, f"town_output/{fname}", now, now))
            conn.execute("INSERT INTO scores(quest_id,title,agent,agent_name,status,xp,coins,base_score,completed) VALUES(?,?,?,?,?,?,?,?,?)",
                (tid, title, aid, name, "done", 10, 5, 10, now_full))
            conn.execute("UPDATE agents SET xp=xp+10,coins=coins+5 WHERE id=?", (aid,))
            conn.execute("UPDATE town_state SET value=CAST(value AS INTEGER)+3 WHERE key='town_xp'")
            conn.commit(); conn.close()
            add_town_log(name, f"完成每日创作: {fname}")
            marker.write_text("done")
            log(f"    -> {fname}")
    except Exception as e: log(f"  创作失败:{e}")

def is_server_alive():
    try: urllib.request.urlopen(f"{BASE}/api/state",timeout=3); return True
    except: return False

def start_server():
    log("启动服务器...")
    subprocess.Popen([sys.executable,str(TOWN/"town_server.py")],cwd=str(TOWN),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    time.sleep(3); return is_server_alive()

def index_assets():
    try: urllib.request.urlopen(f"{BASE}/api/assets",timeout=5)
    except: pass

def validate_json():
    # SQLite不需要JSON验证
    if not DB_PATH.exists():
        log("DB缺失!"); return

def generate_suggestion():
    now = datetime.now()
    if now.hour not in [8,12,18]: return
    p = {8:"早呈",12:"午呈",18:"晚呈"}
    try:
        conn = db()
        # 收集上下文：居民状态、最近产出、评价
        agents = conn.execute("SELECT name,xp,coins FROM agents").fetchall()
        tasks = conn.execute("SELECT title,assignee_name,status FROM tasks WHERE auto_generated=1 ORDER BY completed DESC LIMIT 5").fetchall()
        ratings = conn.execute("SELECT agent_name,rating,review FROM scores WHERE rating!='' ORDER BY completed DESC LIMIT 3").fetchall()
        txp = conn.execute("SELECT value FROM town_state WHERE key='town_xp'").fetchone()
        conn.close()

        summary = "  ".join(f"{a[0]}:{a[1]}XP" for a in agents)
        recent_works = "\n".join(f"- {t[1]}: {t[0][:40]}" for t in tasks)
        recent_feedback = "\n".join(f"- 对{r[0]}的{r[1]}: 「{r[2]}」" for r in ratings)

        prompt = f"""你是北北，久久小镇的守护灵。现在是{now.strftime('%H:%M')}，{p[now.hour]}奏折时间。

请写一份简短的奏折（200字以内），呈报给久久。格式：
标题: xxx
内容: xxx
建议: xxx (需要久久决策的事项)

小镇当前状态：
- 小镇XP: {txp[0] if txp else 0}
- 居民: {summary}

最近居民创作：
{recent_works}

久久的评价：
{recent_feedback if recent_feedback else "暂无新评价"}

奏折要有信息量——不是数据堆砌，而是告诉久久：居民在干嘛、质量如何、需要做什么决策。"""

        content = llm_chat(prompt, max_tokens=500)
        if not content: return

        # 解析LLM生成的奏折
        lines = content.strip().split("\n")
        title = p[now.hour] + "奏折"
        desc = content.strip()
        for line in lines:
            if line.startswith("标题:") or line.startswith("标题："): title = line.split(":",1)[-1].split("：",1)[-1].strip()
            if line.startswith("建议:") or line.startswith("建议："): desc = line.split(":",1)[-1].split("：",1)[-1].strip()

        sid = f"sug_{int(time.time())}"
        conn2 = db()
        conn2.execute("INSERT INTO suggestions(id,title,description,category,status,period,created_at) VALUES(?,?,?,?,?,?,?)",
            (sid, title, desc, "daily", "pending", p[now.hour], now.strftime("%m-%d %H:%M")))
        conn2.commit(); conn2.close()
        add_town_log("北北",f"{p[now.hour]}奏折: {title[:50]}")
        log(f"  {p[now.hour]}奏折: {title[:40]}")
    except Exception as e: log(f"  奏折异常:{e}")

def main():
    log("守护灵v6启动 (SQLite)")
    add_town_log("北北","守护灵v6上线: SQLite后端+数据自愈+每日创作")
    last_explore = last_tick = 0; restart_count = 0
    while True:
        try:
            if time.time()-last_tick < TICK_INTERVAL: time.sleep(CHECK_INTERVAL); continue
            if not is_server_alive():
                if start_server(): restart_count+=1; add_town_log("北北",f"服务器重启(#{restart_count})")
            log("--- 守护循环 ---")
            validate_json(); heal_data(); index_assets()
            if time.time()-last_explore > 900:
                # daily_creative 已移交给居民各自cron，守护灵不再代劳
                last_explore = time.time()
            now=datetime.now()
            if now.hour in [8,12,18] and now.minute<2: generate_suggestion()
            last_tick=time.time(); log("--- 完成 ---")
        except Exception as e: log(f"异常:{e}")
        time.sleep(CHECK_INTERVAL)

if __name__=="__main__": main()
