#!/usr/bin/env python3
"""
skill_officer.py — 小匠技能官每日技能闭环

闭环：探索热门 skill → 安全检查/去重 → 入项目技能池 → 为适合居民装备。
不直接联网安装未知代码；先沉淀为候选技能卡和安装建议，由居民 cron/镇长后续使用。
"""
import json
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "town.db"
SKILL_POOL = ROOT / ".codex" / "skills" / "skill-pool"
SKILL_POOL.mkdir(parents=True, exist_ok=True)

AGENT_NAMES = {
    "designer": "阿画",
    "writer": "小文",
    "reviewer": "审哥",
    "engineer": "阿程",
    "pm": "芝士",
    "craftsman": "小匠",
}

# 先用白名单种子跑通闭环；后续可由小匠 cron 用 Hermes skill hub 搜索替换/扩展。
HOT_SKILL_SEEDS = [
    {
        "id": "security-review-checklist",
        "title": "安全检查清单",
        "summary": "检查 skill 是否含危险命令、硬编码密钥、越权路径和不可验证依赖。",
        "target": "reviewer",
        "strengthens": "让审哥审核 skill 时更稳，先判安全再判质量。",
    },
    {
        "id": "html-output-sanitizer",
        "title": "HTML 产出清理器",
        "summary": "清理 markdown 包裹、指令残留、空产出和不安全外链，保证作品可直接打开。",
        "target": "designer",
        "strengthens": "让阿画产出的页面更完整、少残留说明文字。",
    },
    {
        "id": "brief-to-prd-slicer",
        "title": "需求拆解薄片",
        "summary": "把一句需求拆成目标、边界、验收标准、最小闭环，不做过度工程。",
        "target": "pm",
        "strengthens": "让芝士更快把想法转成可执行悬赏。",
    },
    {
        "id": "bug-root-cause-map",
        "title": "Bug 根因地图",
        "summary": "按数据流、状态流、入口流定位底层原因，避免打一条修一条。",
        "target": "engineer",
        "strengthens": "让阿程修底层逻辑而不是修表面 case。",
    },
    {
        "id": "voice-copy-polisher",
        "title": "口吻润色器",
        "summary": "把生硬任务说明改成自然、有温度、不像填表机器人的表达。",
        "target": "writer",
        "strengthens": "让小文写得更像人、更贴近久久偏好的温暖表达。",
    },
]

DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+[/~]",
    r"taskkill\s+//F\s+//IM",
    r"git\s+reset\s+--hard",
    r"sk-[A-Za-z0-9]",
    r"api[_-]?key\s*=\s*['\"]",
    r"C:/Users/[^/]+/AppData/Local/hermes/profiles/",
]


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def slug_exists(slug: str) -> bool:
    return any((ROOT / base / slug).exists() for base in (".codex/skills/skill-pool", ".codex/skills", "skills"))


def security_findings(text: str):
    findings = []
    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, text, re.I):
            findings.append(pat)
    return findings


def pick_candidate(db: sqlite3.Connection):
    rows = db.execute("SELECT text FROM logs WHERE agent='小匠' ORDER BY id DESC LIMIT 80").fetchall()
    used_text = "\n".join(r[0] for r in rows)
    for seed in HOT_SKILL_SEEDS:
        if seed["id"] not in used_text and not slug_exists(seed["id"]):
            return seed, False
    # 全部重复时，优化已有技能池里最早的一个。
    return HOT_SKILL_SEEDS[int(time.time() // 86400) % len(HOT_SKILL_SEEDS)], True


def skill_markdown(seed, duplicate=False):
    title = seed["title"] + (" · 优化版" if duplicate else "")
    return f"""---
name: {seed['id']}
description: {seed['summary']}
version: 0.1.0
created_by: 小匠
---

# {title}

## 适用对象

优先安装给：{AGENT_NAMES.get(seed['target'], seed['target'])}

## 能力增强

{seed['strengthens']}

## 使用流程

1. 先确认任务目标和验收标准。
2. 对照本 skill 的检查点执行，不跳过安全和完整性。
3. 输出前做一次自检：无密钥、无越权路径、无指令残留、能被真实工具验证。
4. 若与已有 skill 重复，则把新增经验合并进旧 skill，而不是安装重复能力。

## 安全检查

- 不包含 API key 或 token。
- 不要求删除用户目录、重置 Git 历史或修改其他 Hermes profile。
- 不把未经验证的网络脚本直接执行为安装步骤。
- 所有文件路径限定在当前项目或居民自己的 skill 卡范围内。

## 小匠记录

- 创建时间：{now()}
- 来源：小匠每日热门 skill 探索白名单种子
- 状态：已通过静态安全检查，等待居民使用反馈继续优化
"""


def install_for_agent(db, agent_id: str, skill_id: str):
    row = db.execute("SELECT equipped_skills FROM agents WHERE id=?", (agent_id,)).fetchone()
    if not row:
        return False
    try:
        skills = json.loads(row[0] or "[]")
    except json.JSONDecodeError:
        skills = []
    if skill_id not in skills:
        skills.append(skill_id)
        db.execute("UPDATE agents SET equipped_skills=? WHERE id=?", (json.dumps(skills, ensure_ascii=False), agent_id))
    return True


def maybe_level_bonus(db):
    bonuses = []
    for row in db.execute("SELECT id,name,level,equipped_skills FROM agents WHERE id NOT IN ('mayor','craftsman')"):
        agent_id, name, level, equipped = row
        try:
            skills = json.loads(equipped or "[]")
        except json.JSONDecodeError:
            skills = []
        target_count = max(1, int(level or 1) // 2)
        if len(skills) < target_count:
            seed = next((s for s in HOT_SKILL_SEEDS if s["target"] == agent_id), None)
            if seed and seed["id"] not in skills:
                install_for_agent(db, agent_id, seed["id"])
                bonuses.append(f"{name} Lv.{level} 追加装备 {seed['id']}")
    return bonuses


def main():
    db = sqlite3.connect(DB)
    try:
        db.execute("INSERT OR IGNORE INTO agents(id,name,role,emoji,color) VALUES('craftsman','小匠','技能官','🛠️','#8d6e63')")
        seed, duplicate = pick_candidate(db)
        content = skill_markdown(seed, duplicate=duplicate)
        findings = security_findings(content)
        if findings:
            status = "blocked"
            summary = f"小匠技能安全检查拦截 {seed['id']}: {findings}"
        else:
            skill_dir = SKILL_POOL / seed["id"]
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
            install_for_agent(db, seed["target"], seed["id"])
            bonuses = maybe_level_bonus(db)
            status = "done"
            summary = f"小匠探索热门 skill「{seed['title']}」→ 安全检查通过 → 入池 {skill_dir.as_posix()} → 装备给 {AGENT_NAMES.get(seed['target'], seed['target'])}"
            if duplicate:
                summary += "；发现重复主题，本次按优化版沉淀"
            if bonuses:
                summary += "；升级加成：" + "、".join(bonuses)
        tid = f"skill_daily_{int(time.time())}"
        db.execute(
            "INSERT OR REPLACE INTO tasks(id,title,body,assignee,assignee_name,status,auto_generated,xp,coins,output,created,completed) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, f"小匠每日技能探索：{seed['title']}", summary, "craftsman", "小匠", status, 1, 12, 6, f".codex/skills/skill-pool/{seed['id']}/SKILL.md" if status == "done" else "", now(), now()),
        )
        db.execute(
            "INSERT OR REPLACE INTO scores(quest_id,title,agent,agent_name,status,xp,coins,output,completed) VALUES(?,?,?,?,?,?,?,?,?)",
            (tid, f"小匠每日技能探索：{seed['title']}", "craftsman", "小匠", status, 12, 6, f".codex/skills/skill-pool/{seed['id']}/SKILL.md" if status == "done" else "", now()),
        )
        db.execute("INSERT INTO logs(time,agent,text) VALUES(?,?,?)", (now(), "小匠", summary))
        db.execute("UPDATE agents SET xp=xp+12, coins=coins+6 WHERE id='craftsman'")
        db.commit()
        print(summary)
    finally:
        db.close()


if __name__ == "__main__":
    main()
