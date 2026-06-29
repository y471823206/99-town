"""
数据自愈脚本 — 修复 #2-#5
孤儿评分映射 / 漏评补建 / 孤儿文件清理 / Agent分数重算
"""
import sqlite3, json, os, time
from pathlib import Path

DB = Path(__file__).parent / "town.db"
OUTPUT = Path(__file__).parent / "town_output"

def now(): return time.strftime("%m-%d %H:%M")

def main():
    db = sqlite3.connect(str(DB))
    db.row_factory = sqlite3.Row
    fixed = {"orphan_mapped": 0, "scores_created": 0, "orphan_files": 0, "xp_fixed": 0}

    # ===== #2: 孤儿评分 → 按标题匹配映射到正确 task id =====
    print("=== #2: 修复孤儿评分 ===")
    tasks = {t["id"]: t for t in db.execute("SELECT * FROM tasks").fetchall()}
    scores = db.execute("SELECT * FROM scores").fetchall()

    # 映射规则: 孤儿 quest_id 往往是 task_xxx_designer/writer 或 quest_xxx_N
    orphan_map = {}
    for s in scores:
        if s["quest_id"] not in tasks:
            # 尝试匹配 title
            for tid, t in tasks.items():
                if s["title"] == t["title"]:
                    orphan_map[s["quest_id"]] = tid
                    break
            # 如果 title 也没匹配到，尝试前缀匹配
            if s["quest_id"] not in orphan_map:
                base = s["quest_id"].rsplit("_", 1)[0]  # task_xxx_designer → task_xxx
                if base in tasks:
                    orphan_map[s["quest_id"]] = base

    for old_id, new_id in orphan_map.items():
        # 检查新 id 是否已有 score
        existing = db.execute("SELECT 1 FROM scores WHERE quest_id=?", (new_id,)).fetchone()
        if existing:
            # 合并：把孤儿评分的信息更新到已有 score
            orphan = db.execute("SELECT * FROM scores WHERE quest_id=?", (old_id,)).fetchone()
            if orphan and orphan["rating"]:
                db.execute("UPDATE scores SET rating=?,review=?,total_score=? WHERE quest_id=?",
                    (orphan["rating"], orphan["review"], orphan["total_score"], new_id))
            db.execute("DELETE FROM scores WHERE quest_id=?", (old_id,))
        else:
            db.execute("UPDATE scores SET quest_id=? WHERE quest_id=?", (new_id, old_id))
        print(f"  {old_id} → {new_id}")
        fixed["orphan_mapped"] += 1

    # ===== #3: 11个done任务缺scores → 补建 =====
    print("\n=== #3: 补建缺失scores ===")
    tasks_done = [t for t in tasks.values() if t["status"] == "done" and (t["assignee"] or "")]
    score_ids = {s["quest_id"] for s in db.execute("SELECT quest_id FROM scores").fetchall()}

    for t in tasks_done:
        if t["id"] not in score_ids:
            db.execute(
                "INSERT INTO scores(quest_id,title,agent,agent_name,status,xp,coins,completed) VALUES(?,?,?,?,?,?,?,?)",
                (t["id"], t["title"], t["assignee"], t["assignee_name"] or "",
                 "done", t["xp"] or 10, t["coins"] or 5, t["completed"] or now()))
            print(f"  + score: {t['id']} ({t['title'][:30]})")
            fixed["scores_created"] += 1

    # ===== #4: 孤儿文件 → 按文件名创建 task 记录（标记来源） =====
    print("\n=== #4: 孤儿文件处理 ===")
    task_outputs = set()
    for t in tasks.values():
        o = t["output"] or ""
        if o:
            task_outputs.add(o.split("/")[-1] if "/" in o else o)

    for f in sorted(OUTPUT.glob("*")):
        if f.is_file() and not f.name.startswith(".") and f.name not in task_outputs:
            found = False
            for t in tasks.values():
                if t["output"] and f.name in t["output"]:
                    found = True
                    break
            if not found:
                print(f"  orphan file: {f.name} (保留，未创建task)")
                fixed["orphan_files"] += 1

    # ===== #5: Agent XP 重算 =====
    print("\n=== #5: Agent分数重算 ===")
    agents = db.execute("SELECT * FROM agents").fetchall()
    for a in agents:
        if a["id"] == "mayor":
            continue  # 北北不算
        total = 0
        for s in db.execute(
            "SELECT total_score FROM scores WHERE agent=? AND rating IS NOT NULL AND rating!=''",
            (a["id"],)
        ).fetchall():
            total += s["total_score"] or 0
        if total != a["xp"]:
            db.execute("UPDATE agents SET xp=? WHERE id=?", (total, a["id"]))
            print(f"  {a['name']}({a['id']}): {a['xp']} → {total}")
            fixed["xp_fixed"] += 1

    db.commit()

    print(f"\n=== 修复汇总 ===")
    print(f"  孤儿评分映射: {fixed['orphan_mapped']}")
    print(f"  补建scores: {fixed['scores_created']}")
    print(f"  孤儿文件: {fixed['orphan_files']} (保留在磁盘)")
    print(f"  分数重算: {fixed['xp_fixed']}")
    db.close()

if __name__ == "__main__":
    main()
