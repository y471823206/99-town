#!/usr/bin/env python3
"""
自动检查生成的SKILL.md是否通过Phase 4质量标准。
对照通过标准表格逐项检查，输出通过/不通过和具体原因。

用法:
    python3 quality_check.py <SKILL.md路径>

示例:
    python3 quality_check.py .claude/skills/elon-musk-perspective/SKILL.md
"""

import sys
import re
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def extract_section(content: str, header_pattern: str) -> str:
    """提取指定section的内容（从该header到下一个同级header）"""
    lines = content.split('\n')
    in_section = False
    section_level = 0
    section_lines = []

    for line in lines:
        header_match = re.match(r'^(#{1,6})\s+', line)
        if in_section:
            if header_match and len(header_match.group(1)) <= section_level:
                break
            section_lines.append(line)
            continue
        if header_match and re.search(header_pattern, line, re.IGNORECASE):
            in_section = True
            section_level = len(header_match.group(1))

    return '\n'.join(section_lines)


def check_mental_models(content: str) -> tuple[bool, str]:
    """检查心智模型数量（3-7个）"""
    section = extract_section(content, r'心智模型|Mental Model|核心.*模型')
    if not section.strip():
        return False, "未检测到心智模型section"

    # 计数section内的所有###子标题
    sub_headers = re.findall(r'^###\s+.+', section, re.MULTILINE)
    count = len(sub_headers)

    if count == 0:
        # fallback: 数编号列表项 (1. xxx, 2. xxx)
        numbered = re.findall(r'^\d+\.\s+\*\*', section, re.MULTILINE)
        count = len(numbered)

    if count == 0:
        return False, "未检测到心智模型条目"

    passed = 3 <= count <= 7
    return passed, f"{count}个心智模型 {'✅' if passed else '❌ (应为3-7个)'}"


def check_limitations(content: str) -> tuple[bool, str]:
    """检查每个模型是否有局限性描述"""
    section = extract_section(content, r'心智模型|Mental Model|核心.*模型')
    if not section.strip():
        return False, "❌ 未找到心智模型section，无法检查局限性"

    limitation_count = len(re.findall(
        r'局限|失效|不适用|盲区|limitation|blind spot|不擅长|弱点|边界',
        section, re.IGNORECASE
    ))
    passed = limitation_count >= 2
    return passed, f"局限性描述: {limitation_count}处 {'✅' if passed else '❌ (应≥2处)'}"


def check_expression_dna(content: str) -> tuple[bool, str]:
    """检查表达DNA辨识度"""
    section = extract_section(content, r'表达DNA|Expression DNA|表达风格|风格规则')
    if not section.strip():
        return False, "❌ 未找到表达DNA section"

    # 检查是否有多维度的具体风格描述
    style_markers = len(re.findall(
        r'句式|词汇|语气|幽默|节奏|确定性|引用|口头禅|高频|禁忌|口癖|短句|长句|类比|转折|断言|谨慎',
        section
    ))
    passed = style_markers >= 3
    return passed, f"表达DNA特征: {style_markers}项 {'✅' if passed else '❌ (应≥3项)'}"


def check_honest_boundary(content: str) -> tuple[bool, str]:
    """检查诚实边界（至少3条）"""
    section = extract_section(content, r'诚实边界|Honest Boundar|局限声明')
    if not section.strip():
        return False, "❌ 未找到诚实边界section"

    # 计算列表项
    items = re.findall(r'^[-*]\s+', section, re.MULTILINE)
    count = len(items)
    passed = count >= 3
    return passed, f"诚实边界: {count}条 {'✅' if passed else '❌ (应≥3条)'}"


def check_tensions(content: str) -> tuple[bool, str]:
    """检查内在张力（至少2对）"""
    # 先检查专门的张力/矛盾section
    section = extract_section(content, r'张力|矛盾|价值观.*反模式|内在冲突')
    if section.strip():
        # 在专门section内计数
        pairs = re.findall(
            r'张力|矛盾|tension|paradox|一方面.*另一方面|既.*又|vs\.|对立',
            section, re.IGNORECASE
        )
        count = len(pairs)
    else:
        # fallback: 全文搜索
        pairs = re.findall(
            r'张力|矛盾|tension|paradox|一方面.*另一方面|既.*又',
            content, re.IGNORECASE
        )
        count = len(pairs)

    passed = count >= 2
    return passed, f"内在张力: {count}处 {'✅' if passed else '❌ (应≥2处)'}"


def check_primary_sources(content: str) -> tuple[bool, str]:
    """检查一手来源占比"""
    section = extract_section(content, r'调研来源|来源|Source|Reference|附录')
    if not section.strip():
        return True, "未找到来源section（跳过检查）"

    # 方式1: 检查结构化标记 [一手] [二手]
    primary_tagged = len(re.findall(r'\[一手\]', section))
    secondary_tagged = len(re.findall(r'\[二手\]', section))

    if primary_tagged + secondary_tagged > 0:
        total = primary_tagged + secondary_tagged
        ratio = primary_tagged / total
        passed = ratio > 0.5
        return passed, f"一手来源占比: {primary_tagged}/{total} ({ratio:.0%}) {'✅' if passed else '❌ (应>50%)'}"

    # 方式2: 检查一手/二手子section内的列表项数量
    primary_section = extract_section(section, r'一手|primary|本人.*产出')
    secondary_section = extract_section(section, r'二手|secondary|他人.*分析')

    primary_items = len(re.findall(r'^[-*]\s+', primary_section, re.MULTILINE)) if primary_section else 0
    secondary_items = len(re.findall(r'^[-*]\s+', secondary_section, re.MULTILINE)) if secondary_section else 0

    total = primary_items + secondary_items
    if total == 0:
        return True, "未标记来源类型（跳过检查）"

    ratio = primary_items / total
    passed = ratio > 0.5
    return passed, f"一手来源占比: {primary_items}/{total} ({ratio:.0%}) {'✅' if passed else '❌ (应>50%)'}"


def check_agentic_protocol(content: str) -> tuple[bool, str]:
    """检查是否有Agentic Protocol回答工作流"""
    section = extract_section(content, r'回答工作流|Agentic Protocol|工作流')
    if not section.strip():
        return False, "❌ 未找到回答工作流section"

    has_steps = bool(re.search(r'Step\s*[123]|步骤\s*[123]', section, re.IGNORECASE))
    has_classification = bool(re.search(r'问题分类|分类|需要事实|纯框架', section))

    passed = has_steps and has_classification
    detail = f"有Step结构: {'✅' if has_steps else '❌'}  有问题分类: {'✅' if has_classification else '❌'}"
    return passed, detail


def check_example_dialogues(content: str) -> tuple[bool, str]:
    """检查是否有示例对话"""
    section = extract_section(content, r'示例对话|示例')
    if not section.strip():
        return False, "❌ 未找到示例对话section"

    examples = re.findall(r'示例[一二三四五六七八九十\d]|###\s+示例', section)
    count = len(examples)
    passed = count >= 2
    return passed, f"示例对话: {count}个 {'✅' if passed else '❌ (应≥2个)'}"


def main():
    if len(sys.argv) < 2:
        print("用法: python3 quality_check.py <SKILL.md路径>")
        sys.exit(1)

    skill_path = Path(sys.argv[1])
    if not skill_path.exists():
        print(f"❌ 文件不存在: {skill_path}")
        sys.exit(1)

    content = skill_path.read_text(encoding='utf-8')

    checks = [
        ("心智模型数量", check_mental_models),
        ("模型局限性", check_limitations),
        ("表达DNA辨识度", check_expression_dna),
        ("诚实边界", check_honest_boundary),
        ("内在张力", check_tensions),
        ("一手来源占比", check_primary_sources),
        ("回答工作流", check_agentic_protocol),
        ("示例对话", check_example_dialogues),
    ]

    print(f"质量检查: {skill_path.name}")
    print("=" * 60)

    passed_count = 0
    total = len(checks)

    for name, check_fn in checks:
        passed, detail = check_fn(content)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name:<12} {status}  {detail}")
        if passed:
            passed_count += 1

    print("=" * 60)
    print(f"结果: {passed_count}/{total} 通过")

    if passed_count == total:
        print("🎉 全部通过，可以交付")
    elif passed_count >= total - 2:
        print("⚠️ 基本通过，建议修复不通过项后交付")
    else:
        print("❌ 多项不通过，建议回到Phase 2迭代")

    sys.exit(0 if passed_count == total else 1)


if __name__ == '__main__':
    main()
