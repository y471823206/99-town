"""
TDD 测试: 久久小镇积分榜数据管线
验证 API 返回字段与前端消费字段一致。

原则: 先写测试→看它失败→修代码→看它通过
"""

import json
import urllib.request
import os
import sys

API = "http://localhost:8700/api/state"
HTML = r"D:\北北\99-town\town.html"


def fetch_state():
    """调用 /api/state 获取数据."""
    req = urllib.request.Request(API)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def read_frontend():
    """读取 town.html 源码."""
    with open(HTML, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================
# TEST 1: API agents 有 xp 字段，没有 total 字段
# 这是积分榜显示 0 的根因——前端用了不存在的 total
# ============================================================
def test_agents_have_xp_not_total():
    """API 的 agents 对象必须有 xp，不能依赖 total."""
    state = fetch_state()
    agents = state.get("agents", {})

    assert len(agents) >= 5, f"至少应有5个agent，实际{len(agents)}"

    for agent_id, data in agents.items():
        # xp 必须存在
        assert "xp" in data, f"{agent_id} 缺少 xp 字段，可用字段: {list(data.keys())}"
        assert isinstance(data["xp"], (int, float)), f"{agent_id}.xp 不是数字: {data['xp']}"

        # total 不应该存在（前端曾误用）
        assert "total" not in data, (
            f"{agent_id} 有 total 字段={data.get('total')}，"
            f"但前端目前只用 xp。如果后端新增了 total，需同步更新前端。"
        )

    print("  ✅ test_agents_have_xp_not_total")


# ============================================================
# TEST 2: 前端积分榜渲染代码使用 xp 而非 total
# 防止未来有人改回错误的字段名
# ============================================================
def test_frontend_scores_tab_uses_xp():
    """积分榜 tab 的渲染代码必须使用 xp 字段."""
    html = read_frontend()

    # 找到 renderModal 函数中 Scores 部分
    # 关键检查点: scores 排序和显示都用的 xp
    checks = [
        # 排序
        ('scores).sort((a,b)=>(b[1].xp', '积分榜排序必须用 xp'),
        # 最大值
        ('scores).map(s=>s.xp', 'maxScore 计算必须用 xp'),
        # 百分比
        ('(s.xp||0)/maxScore', '进度条百分比必须用 xp'),
        # 显示值
        ('score-pts">${s.xp', '积分显示必须用 xp'),
    ]

    for pattern, desc in checks:
        assert pattern in html, (
            f"前端代码缺少: {desc}\n"
            f"  期望包含: {pattern}\n"
            f"  如果找不到，说明有人把 xp 改回了 total——会导致积分榜全显示 0"
        )

    # 反检查: 积分榜部分不应该用 total
    # 提取积分榜渲染代码段（Scores 注释到下一个主要区块）
    scores_start = html.find("// Scores")
    if scores_start == -1:
        scores_start = html.find("Scores")
    scores_end = html.find("奏折", scores_start) if scores_start != -1 else -1

    if scores_start != -1 and scores_end != -1:
        scores_section = html[scores_start:scores_end]
        # 在这个区块内，不应该有对 agents 对象的 .total 访问
        # 但可以出现 quests 的 total_score（那是正确的）
        lines = scores_section.split("\n")
        bad_lines = []
        for i, line in enumerate(lines):
            if "s.total" in line and "total_score" not in line:
                bad_lines.append(f"    L{scores_start//80 + i}: {line.strip()[:80]}")

        assert not bad_lines, (
            f"积分榜代码段中发现错误字段引用 (s.total 应改为 s.xp):\n"
            + "\n".join(bad_lines)
        )

    print("  ✅ test_frontend_scores_tab_uses_xp")


# ============================================================
# TEST 3: 前端居民卡片渲染使用正确的积分字段
# 侧边栏和点击弹窗都用 xp
# ============================================================
def test_frontend_sidebar_uses_xp():
    """侧边栏和 clickAgent 弹窗的积分显示使用 xp."""
    html = read_frontend()

    # 侧边栏: ${sc.xp || sc.total || 0} — xp 优先，total 作为兜底可接受
    assert "sc.xp" in html, "侧边栏积分显示必须引用 xp 字段"

    # clickAgent 弹窗: 必须用 xp
    assert "agents[id]||{xp:0}).xp" in html, (
        "clickAgent 弹窗积分必须用 xp\n"
        "  如果是 .total 会导致弹窗显示 0"
    )

    print("  ✅ test_frontend_sidebar_uses_xp")


# ============================================================
# TEST 4: API 数据完整性——所有 agent 的 xp 是合理值
# ============================================================
def test_agent_xp_values_sane():
    """确认 agent 的 xp 值不是全 0 或异常."""
    state = fetch_state()
    agents = state.get("agents", {})

    xp_values = [data.get("xp", 0) for data in agents.values()]

    # 不能全是 0
    assert sum(xp_values) > 0, (
        f"所有 agent xp 总和为 0！数据异常或评分系统未工作。\n"
        f"  xp 值: {dict(zip(agents.keys(), xp_values))}"
    )

    # 每个值应该 >= 0
    for agent_id, data in agents.items():
        assert data["xp"] >= 0, f"{agent_id} xp 为负数: {data['xp']}"

    print(f"  ✅ test_agent_xp_values_sane (总和={sum(xp_values)}, 值={dict(zip(agents.keys(), xp_values))})")


# ============================================================
# TEST 5: 产出链接渲染——验证 renderOutputLinks 不再有转义bug
# ============================================================
def test_render_output_links_escaping():
    """renderOutputLinks 函数中 href 不应有反斜杠转义."""
    html = read_frontend()

    # 错误模式: href=\\\" 会导致生成 href=\"...\" 而非 href="..."
    assert 'href=\\\\\"' not in html, (
        "renderOutputLinks 仍有 \\\" 转义bug！\n"
        "  这会导致产出链接不可点击。应改为 href=\""
    )

    # 正确模式应该存在
    assert 'href="' in html, "前端代码中应该存在正确的 href=\" 写法"

    print("  ✅ test_render_output_links_escaping")


# ============================================================
# TEST 6: CSS——积分榜进度条定位
# ============================================================
def test_score_row_has_position_relative():
    """.score-row 必须有 position:relative 供子元素的 absolute 定位."""
    html = read_frontend()

    # 找到 .score-row 的 CSS 定义
    css_start = html.find(".score-row {")
    assert css_start != -1, "找不到 .score-row CSS 定义"

    css_end = html.find("}", css_start)
    css_block = html[css_start:css_end]

    assert "position:relative" in css_block, (
        ".score-row 缺少 position:relative！\n"
        "  .score-bar-wrap 用了 position:absolute，"
        "  没有 relative 父元素会导致进度条定位到错误位置。"
    )

    print("  ✅ test_score_row_has_position_relative")


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("久久小镇 积分管线测试")
    print("=" * 60)

    tests = [
        test_agents_have_xp_not_total,
        test_frontend_scores_tab_uses_xp,
        test_frontend_sidebar_uses_xp,
        test_agent_xp_values_sane,
        test_render_output_links_escaping,
        test_score_row_has_position_relative,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"\n  ❌ FAIL: {test.__name__}")
            print(f"     {e}")
        except Exception as e:
            failed += 1
            print(f"\n  💥 ERROR: {test.__name__}")
            print(f"     {type(e).__name__}: {e}")

    print(f"\n{'=' * 60}")
    print(f"结果: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'=' * 60}")

    sys.exit(1 if failed > 0 else 0)
