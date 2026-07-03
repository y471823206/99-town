#!/bin/bash
# 从YouTube视频下载字幕
# 用法: ./download_subtitles.sh <YouTube_URL> [输出目录]
# 优先下载人工字幕，无人工字幕则下载自动生成字幕
# 语言优先级：中文 > 英文 > 其他

set -e

URL="$1"
OUTPUT_DIR="${2:-.}"

if [ -z "$URL" ]; then
    echo "用法: ./download_subtitles.sh <视频URL> [输出目录]"
    echo "支持: YouTube, Bilibili 等 yt-dlp 支持的平台"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# 创建时间戳标记文件，用于判断哪些字幕是本次下载的
MARKER="/tmp/.ytdlp_marker_$$"
touch "$MARKER"
trap "rm -f $MARKER" EXIT

# 检测平台
IS_BILIBILI=false
if echo "$URL" | grep -qE 'bilibili\.com|b23\.tv'; then
    IS_BILIBILI=true
    echo ">>> 检测到B站视频"
fi

echo ">>> 检查可用字幕..."
yt-dlp --list-subs --no-download "$URL" 2>/dev/null | tail -20

echo ""

# B站视频：优先AI生成字幕（B站字幕机制与YouTube不同）
if [ "$IS_BILIBILI" = true ]; then
    echo ">>> B站视频：尝试获取CC字幕/AI字幕..."
    # B站字幕通常是 json3 格式的CC字幕
    if yt-dlp --write-subs --sub-langs "zh-Hans,zh-Hant,zh" --sub-format srt --skip-download -o "$OUTPUT_DIR/%(title)s" "$URL" 2>/dev/null; then
        FOUND=$(find "$OUTPUT_DIR" \( -name "*.srt" -o -name "*.vtt" -o -name "*.json3" \) -newer "$MARKER" 2>/dev/null | head -1)
        if [ -n "$FOUND" ]; then
            echo "✅ B站字幕下载成功: $FOUND"
            exit 0
        fi
    fi
    # B站 fallback: 自动字幕
    if yt-dlp --write-auto-subs --sub-langs "zh-Hans,zh,en" --sub-format srt --skip-download -o "$OUTPUT_DIR/%(title)s" "$URL" 2>/dev/null; then
        FOUND=$(find "$OUTPUT_DIR" \( -name "*.srt" -o -name "*.vtt" \) -newer "$MARKER" 2>/dev/null | head -1)
        if [ -n "$FOUND" ]; then
            echo "✅ B站自动字幕下载成功: $FOUND"
            exit 0
        fi
    fi
    echo "⚠️ B站视频无可用字幕，建议用 gemini-video skill 转写"
    exit 1
fi

# YouTube及其他平台
echo ">>> 尝试下载人工字幕（中文优先）..."

# 尝试1: 人工中文字幕
if yt-dlp --write-subs --sub-langs "zh-Hans,zh-Hant,zh,zh-CN,zh-TW" --sub-format srt --skip-download -o "$OUTPUT_DIR/%(title)s" "$URL" 2>/dev/null; then
    FOUND=$(find "$OUTPUT_DIR" -name "*.srt" -newer "$MARKER" 2>/dev/null | head -1)
    if [ -n "$FOUND" ]; then
        echo "✅ 下载成功: $FOUND"
        exit 0
    fi
fi

# 尝试2: 人工英文字幕
echo ">>> 无中文人工字幕，尝试英文..."
if yt-dlp --write-subs --sub-langs "en,en-US,en-GB" --sub-format srt --skip-download -o "$OUTPUT_DIR/%(title)s" "$URL" 2>/dev/null; then
    FOUND=$(find "$OUTPUT_DIR" -name "*.srt" -newer "$MARKER" 2>/dev/null | head -1)
    if [ -n "$FOUND" ]; then
        echo "✅ 下载成功: $FOUND"
        exit 0
    fi
fi

# 尝试3: 自动生成字幕（中文优先）
echo ">>> 无人工字幕，尝试自动生成字幕..."
if yt-dlp --write-auto-subs --sub-langs "zh-Hans,zh,en" --sub-format srt --skip-download -o "$OUTPUT_DIR/%(title)s" "$URL" 2>/dev/null; then
    FOUND=$(find "$OUTPUT_DIR" \( -name "*.srt" -o -name "*.vtt" \) -newer "$MARKER" 2>/dev/null | head -1)
    if [ -n "$FOUND" ]; then
        echo "✅ 自动字幕下载成功: $FOUND"
        exit 0
    fi
fi

echo "❌ 未找到任何可用字幕"
exit 1
