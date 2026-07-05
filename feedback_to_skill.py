#!/usr/bin/env python3
"""
feedback_to_skill.py — 评价反馈→技能卡自动沉淀
被守护灵 cron 调用，扫描 feedback_log 中未处理的评价，
提炼后追加到对应居民技能卡的"久久评价记录"和"核心教训"。

用法: python feedback_to_skill.py
"""

import sqlite3
import os
import re
from pathlib import Path
from datetime import datetime

DB_PATH = str(Path(__file__).resolve().parent / "town.db")
PROJECT_SKILLS_BASE = str(Path(__file__).resolve().parent / ".codex" / "skills")
SKILLS_BASE = os.path.expandvars(r"%USERPROFILE%\AppData\Local\hermes\skills\99-town")

RATING_MAP = {
    "excellent": "卓越",
    "good": "好评",
    "ok": "一般",
    "poor": "差评",
    "bad": "差评",
}

AGENT_SKILL = {
    "designer": "ahua-design-lessons",
    "writer": "xiaowen-writing-lessons",
    "reviewer": "shenge-review-lessons",
    "engineer": "acheng-engineering-lessons",
    "pm": "zhishi-product-lessons",
    "truman": "truman-perspective",
    "craftsman": "skill-officer-lessons",
}

def get_skill_path(agent_id):
    """返回技能卡 SKILL.md 的绝对路径."""
    skill_dir = AGENT_SKILL.get(agent_id)
    if not skill_dir:
        return None
    if agent_id in ("truman", "craftsman"):
        return os.path.join(PROJECT_SKILLS_BASE, skill_dir, "SKILL.md")
    return os.path.join(SKILLS_BASE, skill_dir, "SKILL.md")


def read_skill(path):
    """读取技能卡全文."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_task_title(db, task_id):
    """从 tasks 表获取任务标题."""
    cur = db.execute("SELECT title FROM tasks WHERE id=?", (task_id,))
    row = cur.fetchone()
    return row[0] if row else task_id


def append_evaluation_record(skill_text, date_str, task_title, rating_cn, review):
    """在「久久评价记录」表格末尾追加一行.
    
    处理三种情况：
    1. 表格已存在 → 追加行
    2. 章节存在但无表格（如"暂无直接评价"） → 替换为表格
    3. 章节不存在 → 追加新章节+表格
    """
    table_header = "| 日期 | 作品 | 评价 | 久久的话 |"
    new_row = f"| {date_str} | {task_title} | {rating_cn} | \"{review}\" |"
    sep_line = "|------|------|------|----------|"

    # 情况1: 表格已存在
    idx = skill_text.find(table_header)
    if idx != -1:
        sep_idx = skill_text.find(sep_line, idx)
        if sep_idx != -1:
            after_sep = skill_text[sep_idx + len(sep_line):]
            lines = after_sep.split("\n")
            table_end_line = 0
            for i, line in enumerate(lines):
                if line.startswith("## "):
                    table_end_line = i
                    break
                if line.strip() == "" and i > 0 and lines[i-1].strip() == "":
                    table_end_line = i
                    break
            else:
                table_end_line = len(lines)
            insert_pos = idx + len(table_header) + len(sep_line) + 1
            for i in range(table_end_line):
                insert_pos += len(lines[i]) + 1
            return skill_text[:insert_pos] + new_row + "\n" + skill_text[insert_pos:], True

    # 情况2: 章节存在但无表格
    section_header = "## 久久评价记录"
    sec_idx = skill_text.find(section_header)
    if sec_idx != -1:
        # 找到该章节后的下一个 ## 标题（或文件末尾）
        after_sec = skill_text[sec_idx + len(section_header):]
        next_sec = after_sec.find("\n## ")
        if next_sec == -1:
            # 没有下一个 ##，替换到文件末尾
            before = skill_text[:sec_idx + len(section_header)]
            new_section = f"\n\n{table_header}\n{sep_line}\n{new_row}\n"
            return before + new_section, True
        else:
            before = skill_text[:sec_idx + len(section_header)]
            after = after_sec[next_sec:]
            new_section = f"\n\n{table_header}\n{sep_line}\n{new_row}\n"
            return before + new_section + after, True

    # 情况3: 章节不存在，在 YAML frontmatter 后添加
    # 找到第二个 --- (YAML 结束标记)
    first_sep = skill_text.find("---\n")
    if first_sep == -1:
        first_sep = 0
    second_sep = skill_text.find("\n---", first_sep + 4)
    if second_sep == -1:
        insert_pos = 0
    else:
        insert_pos = second_sep + 4  # 跳过 \n---

    new_section = f"\n\n## 久久评价记录\n\n{table_header}\n{sep_line}\n{new_row}\n"
    return skill_text[:insert_pos] + new_section + skill_text[insert_pos:], True


def append_lesson(skill_text, rating, review):
    """差评且有具体原因时，追加到「核心教训」或「提炼的经验」."""
    if rating not in ("poor", "bad"):
        return skill_text, False
    if not review or len(review) < 5:
        return skill_text, False

    # 找核心教训或提炼的经验
    for header in ["## 核心教训", "## 提炼的经验"]:
        idx = skill_text.find(header)
        if idx == -1:
            continue

        # 找到该节后面的第一个编号列表项
        after_header = skill_text[idx + len(header):]
        # 找到最后一个编号项（数字. 开头的行）
        lines_after = after_header.split("\n")
        last_num_line = -1
        for i, line in enumerate(lines_after):
            if re.match(r"^\d+\.\s", line.strip()):
                last_num_line = i

        if last_num_line == -1:
            # 没有编号列表，在节标题后添加
            insert_pos = idx + len(header) + 1
            next_num = 1
        else:
            # 读取最后一个编号
            m = re.match(r"^(\d+)\.", lines_after[last_num_line].strip())
            next_num = int(m.group(1)) + 1
            insert_pos = idx + len(header) + 1
            for i in range(last_num_line + 1):
                insert_pos += len(lines_after[i]) + 1

        new_lesson = f"{next_num}. {review}\n"
        new_skill = skill_text[:insert_pos] + new_lesson + skill_text[insert_pos:]
        return new_skill, True

    return skill_text, False


def process_feedback(db, fb):
    """处理单条反馈记录."""
    fb_id, agent_id, agent_name, task_id, rating, review, created_at = fb

    skill_path = get_skill_path(agent_id)
    if not skill_path:
        print(f"  ⚠ 未知 agent: {agent_id}, 跳过")
        return False

    skill_text = read_skill(skill_path)
    if skill_text is None:
        print(f"  ⚠ 技能卡不存在: {skill_path}, 跳过")
        return False

    task_title = get_task_title(db, task_id)
    rating_cn = RATING_MAP.get(rating, rating)
    date_str = created_at[:10] if created_at else datetime.now().strftime("%m-%d")
    # /api/rate 写入的 created_at 格式可能是 "06-30 00:22"（无年份）
    # 统一取 MM-DD 部分
    if " " in date_str and len(date_str) <= 11:
        date_str = date_str.split(" ")[0]  # "06-30"
    elif len(date_str) >= 10:
        date_str = date_str[5:10]  # "2026-06-29" → "06-29"

    # 1. 追加评价记录
    new_skill, ok1 = append_evaluation_record(skill_text, date_str, task_title, rating_cn, review)
    if not ok1:
        print(f"  ⚠ 未找到「久久评价记录」表: {skill_path}")
        return False

    # 2. 如果是差评，追加核心教训
    new_skill, ok2 = append_lesson(new_skill, rating, review)

    # 写回技能卡
    with open(skill_path, "w", encoding="utf-8") as f:
        f.write(new_skill)

    return True


def main():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    # 读取未处理的反馈
    cur = db.execute(
        "SELECT id, agent_id, agent_name, task_id, rating, review, created_at "
        "FROM feedback_log WHERE processed=0 ORDER BY id"
    )
    rows = cur.fetchall()

    if not rows:
        print("📭 没有待处理的反馈")
        db.close()
        return

    print(f"📋 处理 {len(rows)} 条反馈...")
    processed_count = 0

    for row in rows:
        fb = (row["id"], row["agent_id"], row["agent_name"],
              row["task_id"], row["rating"], row["review"], row["created_at"])
        agent_name = row["agent_name"] or row["agent_id"]
        rating = row["rating"] or "未评"
        print(f"  → {agent_name} | {rating} | {row['review'][:40] if row['review'] else '(无评语)'}")

        if process_feedback(db, fb):
            db.execute("UPDATE feedback_log SET processed=1 WHERE id=?", (row["id"],))
            processed_count += 1
            print(f"    ✅ 已追加到技能卡")

    db.commit()

    # 写处理日志
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO logs(time,agent,text) VALUES(?,?,?)",
        (now, "北北", f"反馈提炼: 处理 {processed_count}/{len(rows)} 条评价→技能卡沉淀")
    )
    db.commit()
    db.close()

    print(f"✅ 完成: {processed_count}/{len(rows)} 条反馈已沉淀到技能卡")


if __name__ == "__main__":
    main()
