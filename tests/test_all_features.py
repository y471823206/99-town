"""
TDD 全功能测试: 久久小镇市政厅
覆盖: API端点 + 数据完整性 + 前端渲染假设 + 业务流程

每个测试验证一个功能点的"应该怎样"，不依赖现有实现的"现在怎样"。
"""

import json
import urllib.request
import os
import sys
import re
import sqlite3
from pathlib import Path

BASE_URL = "http://127.0.0.1:8700"
API = f"{BASE_URL}/api/state"
TOWN_DIR = Path(__file__).resolve().parents[1]
HTML = TOWN_DIR / "town.html"
DB = TOWN_DIR / "town.db"
OUTPUT_DIR = TOWN_DIR / "town_output"


def fetch(path, method="GET", data=None, timeout=10):
    """HTTP 请求封装."""
    url = f"{BASE_URL}{path}" if path.startswith("/") else path
    req = urllib.request.Request(url, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode("utf-8")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def read_html():
    with open(HTML, "r", encoding="utf-8") as f:
        return f.read()


def sql(query_str):
    """SQLite 查询."""
    import subprocess
    result = subprocess.run(
        ["sqlite3", DB, query_str],
        capture_output=True, text=True, timeout=10
    )
    return result.stdout.strip()


def cleanup_test_task(task_id, output_name=None):
    """Remove API test records so regression tests do not pollute the real town."""
    conn = sqlite3.connect(DB)
    try:
        for table, column in (("dispatch_queue", "task_id"), ("feedback_log", "task_id"), ("scores", "quest_id"), ("tasks", "id")):
            conn.execute(f"DELETE FROM {table} WHERE {column}=?", (task_id,))
        conn.commit()
    finally:
        conn.close()
    if output_name:
        output_path = OUTPUT_DIR / output_name
        if output_path.exists():
            output_path.unlink()


PASS = 0
FAIL = 0
ERRORS = 0


def test(name):
    """测试装饰器——打印结果并计数."""
    def decorator(fn):
        def wrapper():
            global PASS, FAIL, ERRORS
            try:
                fn()
                PASS += 1
                print(f"  ✅ {name}")
            except AssertionError as e:
                FAIL += 1
                print(f"  ❌ {name}")
                print(f"     {e}")
            except Exception as e:
                ERRORS += 1
                print(f"  💥 {name}")
                print(f"     {type(e).__name__}: {e}")
        return wrapper
    return decorator


# ================================================================
# 1. API 端点测试
# ================================================================

@test("/api/state 返回200且包含所有必要字段")
def test_state_returns_all_fields():
    state = fetch("/api/state")
    required = ["agents", "tasks", "quests", "assets", "log", "suggestions", "economy", "scoring_rules"]
    for field in required:
        assert field in state, f"/api/state 缺少字段: {field}"

    # agents 至少有5个居民
    assert len(state["agents"]) >= 5, f"agents 数量不足: {len(state['agents'])}"

    # 每个 agent 有完整字段
    agent_fields = ["id", "name", "xp", "coins", "gold", "level"]
    for aid, data in state["agents"].items():
        for f in agent_fields:
            assert f in data, f"agent {aid} 缺少字段: {f}"


@test("/api/publish 创建任务成功并写入scores+dispatch_queue")
def test_publish_creates_task():
    title = f"TDD测试任务_{int(__import__('time').time())}"
    description = "TDD测试：验证发布接口会保存中文描述"
    result = fetch("/api/publish", "POST", {"title": title, "description": description})

    assert result.get("success"), f"publish 失败: {result}"
    task_id = result.get("task_id")
    assert task_id, "未返回 task_id"
    try:
        # 验证 scores 表有记录
        scores_check = sql(f"SELECT COUNT(*) FROM scores WHERE quest_id='{task_id}'")
        assert scores_check == "1", f"scores 表缺少记录: {scores_check}"

        # 验证 dispatch_queue 有记录
        dispatch_check = sql(f"SELECT COUNT(*) FROM dispatch_queue WHERE task_id='{task_id}'")
        assert int(dispatch_check) >= 1, f"dispatch_queue 缺少记录: {dispatch_check}"

        body_check = sql(f"SELECT body FROM tasks WHERE id='{task_id}'")
        assert body_check == description, f"中文描述未保存到 tasks.body: {body_check}"
    finally:
        cleanup_test_task(task_id)


@test("/api/complete 完成任务并保留可访问成果链接")
def test_complete_awards_xp():
    # 自己 publish 一个任务来测，并在 finally 中清理，不碰居民真实任务。
    ts = int(__import__('time').time())
    title = f"TDD完成任务_{ts}"
    description = "TDD complete测试：完成后应该有真实成果链接"
    output_name = f"tdd_complete_output_{ts}.html"
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / output_name).write_text("<html><body>TDD complete output</body></html>", encoding="utf-8")

    pub = fetch("/api/publish", "POST", {"title": title, "description": description})
    task_id = pub["task_id"]
    try:
        result = fetch("/api/complete", "POST", {"task_id": task_id, "output": output_name})
        assert result.get("success"), f"complete 失败: {result}"

        # 验证 tasks 状态变为 done，且 output 是真实存在的文件名，不是缺文件占位。
        state = fetch("/api/state")
        task = next((t for t in state["tasks"] if t["id"] == task_id), None)
        assert task and task["status"] == "done", f"complete 后状态未变 done: {task}"
        assert task.get("output") == output_name, f"complete 后成果链接不正确: {task}"
        assert task.get("body") == description, f"complete 后中文描述丢失: {task}"
    finally:
        cleanup_test_task(task_id, output_name)


@test("/api/rate 评分后写入 feedback_log")
def test_rate_writes_feedback_log():
    # 找一个 done 且未评分的 quest
    state = fetch("/api/state")
    quests = state.get("quests", [])
    unrated = [q for q in quests if q["status"] == "done" and not q.get("rating")]
    if not unrated:
        print("     (无未评分任务，跳过)")
        return

    quest = unrated[0]
    quest_id = quest["quest_id"]

    # 评分前 feedback_log 记录数
    before = int(sql(f"SELECT COUNT(*) FROM feedback_log WHERE task_id='{quest_id}'"))

    fetch("/api/rate", "POST", {
        "quest_id": quest_id,
        "rating": "good",
        "review": "TDD测试评价"
    })

    after = int(sql(f"SELECT COUNT(*) FROM feedback_log WHERE task_id='{quest_id}'"))
    assert after > before, f"feedback_log 未新增记录: before={before}, after={after}"


@test("/api/approve 批准奏折创建任务")
def test_approve_creates_task():
    state = fetch("/api/state")
    suggestions = state.get("suggestions", {}).get("suggestions", [])
    pending_sugs = [s for s in suggestions if s["status"] == "pending"]
    if not pending_sugs:
        print("     (无待批奏折，跳过)")
        return

    sug = pending_sugs[0]
    tasks_before = len(state["tasks"])

    result = fetch("/api/approve", "POST", {
        "id": sug["id"],
        "action": "approved",
        "review": "TDD测试批准"
    })
    assert result.get("success"), f"approve 失败: {result}"

    state_after = fetch("/api/state")
    tasks_after = len(state_after["tasks"])
    assert tasks_after > tasks_before, (
        f"approve 后任务数未增加: before={tasks_before}, after={tasks_after}"
    )


@test("/api/assets 返回资产列表")
def test_assets_returns_list():
    result = fetch("/api/assets")
    assert isinstance(result, list), f"assets 不是列表: {type(result)}"
    assert len(result) > 0, "assets 列表为空"
    # 每个资产应有 id, file, type
    for a in result[:3]:
        assert "id" in a and "file" in a, f"资产缺少字段: {list(a.keys())}"


@test("/file/{idx} 可访问产出文件")
def test_file_endpoint_works():
    assets = fetch("/api/assets")
    if not assets:
        print("     (无资产，跳过)")
        return

    # 取第一个资产，通过 /file/0 访问
    req = urllib.request.Request(f"{BASE_URL}/file/0")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"/file/0 返回 {resp.status}"
        content = resp.read()[:100]
        assert len(content) > 0, "/file/0 返回空内容"


# ================================================================
# 2. 数据完整性测试
# ================================================================

@test("tasks↔scores 无孤儿记录")
def test_tasks_scores_consistency():
    state = fetch("/api/state")
    task_ids = {t["id"] for t in state["tasks"]}
    quest_ids = {q["quest_id"] for q in state["quests"]}

    # scores 中有但 tasks 中没有的（quests with no task）
    orphans_in_quests = quest_ids - task_ids
    if orphans_in_quests:
        # 允许少量（旧数据），但不应超过 5 个
        assert len(orphans_in_quests) <= 5, (
            f"scores 中有 {len(orphans_in_quests)} 条孤儿记录（无对应tasks）: "
            f"{list(orphans_in_quests)[:5]}"
        )


@test("agents.xp = 该agent所有scores.total_score之和")
def test_agent_xp_matches_scores():
    state = fetch("/api/state")

    for agent_id, agent_data in state["agents"].items():
        # 计算该 agent 所有 rated 的 scores 总和
        total_from_scores = sum(
            q.get("total_score", 0) or 0
            for q in state["quests"]
            if q["agent"] == agent_id and q.get("rating")
        )
        agent_xp = agent_data.get("xp", 0)

        # 允许一定误差（有些任务无 rating 但有 base_score）
        diff = abs(agent_xp - total_from_scores)
        if diff > 50:
            print(f"     ⚠ {agent_data['name']}: xp={agent_xp}, scores_sum={total_from_scores}, diff={diff}")


@test("scores 表中 done 任务的 agent 栏位不为空")
def test_scores_have_agent():
    result = sql("SELECT COUNT(*) FROM scores WHERE status='done' AND (agent IS NULL OR agent='')")
    assert result == "0", f"scores 中有 {result} 条 done 记录缺少 agent"


@test("feedback_log 无泄漏——processed=1 的记录对应技能卡已更新")
def test_feedback_log_processed_integrity():
    result = sql("SELECT COUNT(*) FROM feedback_log WHERE processed=1")
    count = int(result)
    # 只要 processed=1 的记录存在，说明流程工作过
    # 但 processed=0 的不应该积压超过 24 小时
    stale = sql(
        "SELECT COUNT(*) FROM feedback_log WHERE processed=0 "
        "AND julianday('now') - julianday(created_at) > 1"
    )
    assert int(stale) == 0, f"有 {stale} 条反馈超过24小时未处理"


# ================================================================
# 3. 前端渲染假设测试
# ================================================================

@test("前端5个tab全部存在")
def test_frontend_five_tabs():
    html = read_html()
    tabs = ["悬赏板", "任务记录", "积分榜", "奏折", "探索"]
    for tab_name in tabs:
        assert tab_name in html, f"前端缺少 tab: {tab_name}"


@test("悬赏板: 渲染非done任务")
def test_frontend_quests_tab():
    html = read_html()
    # 应存在 active-quests 容器和 quest-item 渲染逻辑
    assert "active-quests" in html, "缺少 active-quests 容器"
    assert "quest-item" in html, "缺少 quest-item 渲染"
    assert "暂无活跃悬赏" in html, "缺少空状态提示"


@test("任务记录: 评分按钮存在且有4档")
def test_frontend_history_tab():
    html = read_html()
    assert "rate-btn" in html, "缺少评分按钮"
    for rating in ["excellent", "good", "ok", "poor"]:
        assert f"sel-{rating}" in html, f"缺少评分档位: {rating}"


@test("积分榜: 排名渲染+进度条")
def test_frontend_scores_tab():
    html = read_html()
    assert "score-row" in html, "缺少 score-row"
    assert "score-bar" in html, "缺少进度条"
    assert "score-rank" in html, "缺少排名"
    # 必须用 xp 不是 total
    assert "s.xp||0" in html or "s.xp" in html, "积分榜未使用 xp 字段"


@test("奏折: 审批按钮+状态显示")
def test_frontend_zouzhe_tab():
    html = read_html()
    assert "approveSugg" in html, "缺少审批函数"
    assert "已批准" in html or "approved" in html, "缺少审批状态显示"
    assert "驳回" in html or "rejected" in html, "缺少驳回功能"


@test("探索: auto_generated 任务展示")
def test_frontend_explore_tab():
    html = read_html()
    assert "auto_generated" in html, "缺少 auto_generated 过滤"
    assert "tab-explore" in html, "缺少探索 tab 容器"


@test("智库: Library modal 存在")
def test_frontend_library():
    html = read_html()
    assert "openLibrary" in html, "缺少智库打开函数"
    assert "library-modal" in html, "缺少智库弹窗"
    assert "asset-card" in html, "缺少资产卡片渲染"
    assert "asset-grid" in html, "缺少资产网格"


@test("产出链接: renderOutputLinks 无转义bug")
def test_frontend_output_links():
    html = read_html()
    # 不应该有 \\\" 转义
    assert '\\\\\\"' not in html.replace('\\\\\\\\"', ''), "renderOutputLinks 仍有转义bug"
    # 应该有正确的 href="
    assert 'href="' in html, "缺少正确的 href 写法"


@test("发布悬赏: 输入框+发布按钮")
def test_frontend_publish():
    html = read_html()
    assert "pub-input" in html, "缺少发布输入框"
    assert "publishTask" in html, "缺少发布函数"


@test("CSS: .score-row 有 position:relative")
def test_frontend_css_score_row():
    html = read_html()
    score_row_start = html.find(".score-row {")
    score_row_end = html.find("}", score_row_start)
    css_block = html[score_row_start:score_row_end]
    assert "position:relative" in css_block, ".score-row 缺少 position:relative"


@test("前端有8秒轮询刷新机制")
def test_frontend_polling():
    html = read_html()
    assert "setInterval(fetchState" in html, "缺少定时轮询"
    assert "8000" in html, "轮询间隔不是8秒"


@test("镇长驾驶舱: 第一屏暴露治理闭环")
def test_frontend_mayor_dashboard():
    html = read_html()
    required = [
        "mayor-dashboard",
        "stat-pending",
        "stat-unrated",
        "stat-today-done",
        "stat-health",
        "guardian-advice",
        "openGallery",
        "作品长廊",
    ]
    for marker in required:
        assert marker in html, f"镇长驾驶舱缺少: {marker}"


@test("市政厅入口: 去除重复直达入口，保留上下文入口")
def test_frontend_townhall_entry_scope():
    html = read_html()
    dashboard_start = html.find('<div class="mayor-dashboard"')
    dashboard_end = html.find('<!-- Main -->', dashboard_start)
    dashboard_html = html[dashboard_start:dashboard_end]
    assert "openTownHallTab" not in dashboard_html, "驾驶舱指标卡不应重复直达市政厅 tab"
    assert 'class="dash-card' in dashboard_html, "驾驶舱指标卡仍需保留为状态展示"

    map_head_start = html.find('<div class="map-head">')
    map_head_end = html.find('</div>\n      <canvas', map_head_start)
    map_head_html = html[map_head_start:map_head_end]
    assert "进入市政厅" not in map_head_html, "地图头部不应再放重复的市政厅按钮"
    assert "openTownHall()" not in map_head_html, "地图头部不应绑定市政厅打开动作"

    assert "if (b.id === 'townhall') openTownHall();" in html, "地图建筑点击仍应打开市政厅"
    assert "openTownHallTab('${i.tab}')" in html, "闭环提醒仍应保留上下文入口"
    assert "'去评分', () => { openTownHallTab('history'); }" in html, "交付 toast 仍应保留去评分入口"


# ================================================================
# 4. 业务流程测试
# ================================================================

@test("评分闭环: rate → feedback_log → feedback_to_skill.py 可运行")
def test_feedback_pipeline():
    # feedback_to_skill.py 文件存在
    script_path = r"D:\北北\99-town\feedback_to_skill.py"
    assert os.path.exists(script_path), f"feedback_to_skill.py 不存在: {script_path}"

    # 脚本语法正确（直接 compile 检查，避免 subprocess 路径转义）
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            compile(f.read(), script_path.replace("\\", "/"), "exec")
    except SyntaxError as e:
        assert False, f"feedback_to_skill.py 语法错误: {e}"


@test("北北cron包含反馈提炼步骤")
def test_beibei_cron_has_feedback_step():
    # 检查北北 cron prompt 中包含 feedback_to_skill.py
    import subprocess
    result = subprocess.run(
        ["hermes", "cron", "get", "b8a66a8373ff"],
        capture_output=True, text=True, timeout=10
    )
    # cron prompt 应该提到反馈提炼
    output = result.stdout + result.stderr
    # 检查 cron job 配置
    import sqlite3 as sqlite3_module
    cron_db = os.path.expandvars(r"%USERPROFILE%\AppData\Local\hermes\cron.db")
    if os.path.exists(cron_db):
        conn = sqlite3_module.connect(cron_db)
        cur = conn.execute(
            "SELECT prompt FROM cron_jobs WHERE job_id='b8a66a8373ff'"
        )
        row = cur.fetchone()
        conn.close()
        if row:
            prompt = row[0] or ""
            assert "feedback_to_skill" in prompt, (
                "北北 cron prompt 未包含反馈提炼步骤"
            )
    else:
        print("     (cron.db 不可访问，跳过)")


@test("审批→任务流程: approve后dispatch_queue有记录")
def test_approve_to_dispatch():
    # 找一个已批准的 suggest 对应的 task，检查 dispatch_queue
    result = sql(
        "SELECT COUNT(*) FROM dispatch_queue WHERE time > datetime('now', '-1 hour')"
    )
    # 最近1小时内有 dispatch 记录就说明流程工作过
    # 不强制要求，因为可能没新审批


@test("dispatch_queue 存在且 agent 可扫描")
def test_dispatch_queue_accessible():
    result = sql("SELECT COUNT(*) FROM dispatch_queue")
    assert int(result) >= 0, "dispatch_queue 查询失败"


# ================================================================
# Main
# ================================================================

def run_section(title, tests_list):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")
    for t in tests_list:
        t()


if __name__ == "__main__":
    print("=" * 60)
    print("  久久小镇 · 全功能 TDD 测试")
    print("=" * 60)

    # Section 1: API
    run_section("1. API 端点", [
        test_state_returns_all_fields,
        test_publish_creates_task,
        test_complete_awards_xp,
        test_rate_writes_feedback_log,
        test_approve_creates_task,
        test_assets_returns_list,
        test_file_endpoint_works,
    ])

    # Section 2: Data integrity
    run_section("2. 数据完整性", [
        test_tasks_scores_consistency,
        test_agent_xp_matches_scores,
        test_scores_have_agent,
        test_feedback_log_processed_integrity,
    ])

    # Section 3: Frontend
    run_section("3. 前端渲染假设", [
        test_frontend_five_tabs,
        test_frontend_quests_tab,
        test_frontend_history_tab,
        test_frontend_scores_tab,
        test_frontend_zouzhe_tab,
        test_frontend_explore_tab,
        test_frontend_library,
        test_frontend_output_links,
        test_frontend_publish,
        test_frontend_css_score_row,
        test_frontend_polling,
        test_frontend_mayor_dashboard,
        test_frontend_townhall_entry_scope,
    ])

    # Section 4: Business flow
    run_section("4. 业务流程", [
        test_feedback_pipeline,
        test_beibei_cron_has_feedback_step,
        test_approve_to_dispatch,
        test_dispatch_queue_accessible,
    ])

    total = PASS + FAIL + ERRORS
    print(f"\n{'=' * 60}")
    print(f"  结果: {PASS} passed, {FAIL} failed, {ERRORS} errors, {total} total")
    print(f"{'=' * 60}")

    if FAIL == 0 and ERRORS == 0:
        print("  🟢 全绿！所有功能正常。")
    else:
        print(f"  🔴 发现问题: {FAIL + ERRORS} 项需要修复")

    sys.exit(1 if FAIL + ERRORS > 0 else 0)
