"""
drama_main.py - AI短剧文学视频生产主调度器

用法:
    python drama_main.py generate              # 生成一条完整短剧视频
    python drama_main.py generate "主题"        # 指定主题生成
    python drama_main.py resume <video_id>      # 断点续传（从失败步骤继续）
    python drama_main.py topic_only             # 只生成选题（调试用）

流程:
    选题 → AI写短剧(200-400字) → 拆镜头(6-8个) → Flux生图 → Edge-TTS配音
    → FFmpeg合成视频 → 存Airtable → Server酱通知
"""
import os
import sys
import json
import time
import random
import re
import base64
import glob
import subprocess
import asyncio
from datetime import datetime

import requests

# ============================================================
# 配置（复用现有仓库的 Secrets）
# ============================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "apphDOxCslstliiKO")
SERVERCHAN_KEY = os.getenv("SERVERCHAN_KEY", "")

# 模型配置
LLM_MODEL = "anthropic/claude-sonnet-4-20250514"
IMAGE_MODEL = "black-forest-labs/flux.2-pro"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Airtable 表名（新建表，不影响现有表）
DRAMA_TABLE = "drama_videos"

# 视频参数
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
TARGET_DURATION_SEC = 40
TRANSITION_SEC = 0.8
MIN_SHOTS = 6
MAX_SHOTS = 8

# 配音参数 (Edge-TTS)
TTS_VOICE = "zh-CN-XiaoyiNeural"
TTS_RATE = "-5%"

# 字幕参数
SUBTITLE_FONTSIZE = 42
SUBTITLE_MARGIN_BOTTOM = 180

# BGM
BGM_DIR = os.path.join(os.path.dirname(__file__), "templates", "bgm")
BGM_VOLUME = 0.15

# 输出目录
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "drama_output")

# 选题主题库
THEME_CATEGORY = "按自己喜欢的方式过完这一生"
THEME_TAGS = [
    "治愈", "成长", "情感", "自由", "勇气",
    "温暖", "独处", "远方", "回忆", "释然",
    "慢生活", "小确幸", "告别", "重逢", "梦想",
    "四季", "旅途", "家", "友情", "自我",
]

# Flux 风格
FLUX_BASE_STYLE = (
    "anime illustration style, soft watercolor aesthetic, "
    "dreamy pastel colors, warm lighting, gentle atmosphere, "
    "delicate line art, Studio Ghibli inspired, "
    "beautiful detailed background, cinematic composition, "
    "vertical portrait orientation 9:16 aspect ratio, "
    "high quality, masterpiece"
)

MOOD_STYLES = {
    "治愈": "healing atmosphere, warm golden tones, soft bokeh, comforting",
    "成长": "hopeful mood, dawn light, path stretching forward, inspirational",
    "感伤": "bittersweet mood, rain, soft blue tones, melancholic beauty",
    "喜悦": "joyful mood, bright colors, sparkles, celebration, happiness",
    "宁静": "serene peaceful mood, calm water reflection, tranquil silence",
    "思念": "nostalgic mood, old photographs, faded warm tones, memories",
    "勇气": "brave determination, wind blowing, dramatic sky, strong pose",
    "自由": "freedom, open sky, birds flying, vast horizon, liberating",
}


# ============================================================
# 工具函数
# ============================================================

def log(step, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{step}] {msg}")


def ensure_dirs():
    for sub in ["images", "audio", "video", "temp"]:
        os.makedirs(os.path.join(OUTPUT_DIR, sub), exist_ok=True)


def generate_video_id():
    date_str = datetime.now().strftime("%Y%m%d")
    seq = len(glob.glob(os.path.join(OUTPUT_DIR, f"{date_str}_*"))) + 1
    return f"{date_str}_{seq:03d}"


def save_state(video_id, stage, data):
    """保存中间状态，支持断点续传"""
    state_dir = os.path.join(OUTPUT_DIR, video_id)
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, f"{stage}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def load_state(video_id, stage):
    path = os.path.join(OUTPUT_DIR, video_id, f"{stage}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def call_llm(prompt, system_prompt="", max_retries=3):
    """调用 Claude Sonnet via OpenRouter（与现有 main.py 一致的调用方式）"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/RENXINPAN/content-optimizer",
        "X-Title": "Content Optimizer - Drama Video"
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.8,
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers, json=payload, timeout=120
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            log("LLM", f"请求失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise


def parse_json_response(text):
    """从 LLM 输出提取 JSON（复用现有 review.py 的花括号匹配逻辑）"""
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.index("\n")
        last_block = text.rfind("```")
        if last_block > first_nl:
            text = text[first_nl + 1:last_block].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(f"无法解析 JSON:\n{text[:500]}")


# ============================================================
# Airtable 操作（与现有 airtable.py 风格一致）
# ============================================================

class DramaAirtable:
    """drama_videos 表的读写，风格与现有 airtable.py 一致"""

    def __init__(self):
        self.base_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{DRAMA_TABLE}"
        self.headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json; charset=utf-8"
        }

    def create_record(self, fields):
        resp = requests.post(
            self.base_url,
            headers=self.headers,
            json={"records": [{"fields": fields}]},
            timeout=30
        )
        if resp.status_code == 422:
            log("Airtable", f"422错误，可能表不存在或字段不匹配: {resp.text}")
            return None
        resp.raise_for_status()
        data = resp.json()
        return data.get("records", [{}])[0].get("id")

    def update_record(self, record_id, fields):
        resp = requests.patch(
            self.base_url,
            headers=self.headers,
            json={"records": [{"id": record_id, "fields": fields}]},
            timeout=30
        )
        resp.raise_for_status()
        return True

    def get_recent(self, count=5):
        """拉最近几条记录（用于防重复，与 main.py 拉最近5篇的逻辑一致）"""
        params = {
            "maxRecords": count,
            "sort[0][field]": "created_at",
            "sort[0][direction]": "desc"
        }
        resp = requests.get(self.base_url, headers=self.headers, params=params, timeout=30)
        if resp.status_code != 200:
            return []
        return [r["fields"] for r in resp.json().get("records", [])]


# ============================================================
# Server酱通知（复用现有 SERVERCHAN_KEY）
# ============================================================

def notify_serverchan(title, content):
    """Server酱推送到微信，与现有 review.py 一致"""
    if not SERVERCHAN_KEY:
        log("通知", "未配置 SERVERCHAN_KEY，跳过通知")
        return
    try:
        resp = requests.post(
            f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send",
            data={"title": title, "desp": content},
            timeout=15
        )
        log("通知", f"Server酱推送: {resp.status_code}")
    except Exception as e:
        log("通知", f"推送失败: {e}")


# ============================================================
# Step 1: 选题生成
# ============================================================

TOPIC_PROMPT = """你是一个擅长创作治愈系短视频选题的创意策划师。

## 任务
根据主题方向"按自己喜欢的方式过完这一生"，生成一个适合短视频的选题。

## 选题要求
- 方向：治愈/成长/情感，温暖人心
- 目标受众：18-35岁，追求精神生活品质的年轻人
- 平台：抖音短视频（图片轮播+配音叙述）
- 内容需引发共鸣，有"想转发"的冲动

## 今日灵感标签
{tags}

## 最近做过的选题（避免重复）
{recent_topics}

## 输出格式（纯JSON，不要其他内容）
{{
  "title": "选题标题（10-20字，有吸引力）",
  "hook": "开头金句（引发观众停留的第一句话）",
  "angle": "切入角度（一句话描述叙事视角）",
  "emotion": "核心情绪（治愈/成长/感伤/喜悦/宁静/思念/勇气/自由）",
  "target_scene": "主场景设定（如：海边小屋/山间咖啡馆/老家的院子）"
}}"""


def step_topic(video_id, custom_topic=None):
    log("选题", f"开始生成选题 [{video_id}]")

    # 防重复：拉最近5条
    db = DramaAirtable()
    recent = db.get_recent(5)
    recent_str = "\n".join([f"- {r.get('topic', '未知')}" for r in recent]) if recent else "暂无"

    if custom_topic:
        # 指定主题，与 main.py 指定主题生成逻辑一致
        topic_data = {
            "title": custom_topic,
            "hook": "",
            "angle": "围绕指定主题展开",
            "emotion": "治愈",
            "target_scene": "",
        }
        log("选题", f"使用指定主题: {custom_topic}")
    else:
        tags = random.sample(THEME_TAGS, min(5, len(THEME_TAGS)))
        prompt = TOPIC_PROMPT.format(tags="、".join(tags), recent_topics=recent_str)
        resp = call_llm(prompt)
        topic_data = parse_json_response(resp)

    topic_data["video_id"] = video_id
    save_state(video_id, "01_topic", topic_data)
    log("选题", f"标题: {topic_data.get('title', 'N/A')}")
    return topic_data


# ============================================================
# Step 2: 剧本撰写
# ============================================================

SCRIPT_PROMPT = """你是一个擅长创作治愈系短视频文案的编剧。

## 任务
根据以下选题，撰写一段200-400字的短剧旁白文案。这段文案将配合6-8张唯美卡通图片，制作成抖音图片轮播视频。

## 选题信息
- 标题：{title}
- 开头金句：{hook}
- 切入角度：{angle}
- 核心情绪：{emotion}
- 主场景：{target_scene}

## 写作要求
1. 字数严格控制在200-400字
2. 结构：开头吸引（金句/问句）→ 中间展开（故事/画面）→ 结尾升华（感悟/金句）
3. 语言风格：
   - 口语化，像朋友在耳边轻声讲述
   - 句子不要太长，适合配音朗读（每句15字以内最佳）
   - 多用画面感强的词汇
   - 不要鸡汤，不要说教
4. 留白感，有呼吸的感觉
5. 每段之间标注 [停顿]

## 输出格式（纯JSON）
{{
  "script": "完整文案内容（含[停顿]标注）",
  "word_count": 字数,
  "estimated_duration_sec": 预估朗读时长
}}"""


def step_script(video_id):
    log("剧本", f"开始撰写剧本 [{video_id}]")
    topic = load_state(video_id, "01_topic")

    prompt = SCRIPT_PROMPT.format(
        title=topic.get("title", ""),
        hook=topic.get("hook", ""),
        angle=topic.get("angle", ""),
        emotion=topic.get("emotion", "治愈"),
        target_scene=topic.get("target_scene", "")
    )
    resp = call_llm(prompt)
    script_data = parse_json_response(resp)

    # 实际字数
    clean = script_data.get("script", "").replace("[停顿]", "").replace("*", "")
    script_data["actual_word_count"] = len(re.sub(r'\s+', '', clean))
    script_data["topic"] = topic

    save_state(video_id, "02_script", script_data)
    log("剧本", f"字数: {script_data['actual_word_count']}")
    return script_data


# ============================================================
# Step 3: 镜头拆解
# ============================================================

SHOTS_PROMPT = """你是一个专业的短视频分镜师，同时精通 AI 绘画提示词。

## 任务
将以下短剧文案拆解为 {num_shots} 个镜头，并为每个镜头撰写 Flux AI 绘画的英文提示词。

## 文案
{script}

## 选题信息
- 标题：{title}
- 核心情绪：{emotion}
- 主场景：{target_scene}

## 拆镜要求
1. 每个镜头对应一段文案
2. 镜头之间有视觉层次变化（远景→近景→特写 循环）
3. 画面风格统一（同一个主角/场景贯穿）
4. 第一个镜头要有视觉冲击力
5. 最后一个镜头要有画面升华感

## Flux 提示词要求
- 英文，描述具体：人物外貌、动作、表情、场景、光线、构图
- 保持角色一致性（每个镜头主角描述一致）
- 竖屏构图 (9:16)

## 输出格式（纯JSON）
{{
  "character_description": "主角固定外貌描述（英文）",
  "shots": [
    {{
      "shot_number": 1,
      "subtitle_text": "这个镜头对应的中文配音文案",
      "flux_prompt": "English prompt for Flux",
      "mood": "治愈/成长/感伤/喜悦/宁静/思念/勇气/自由",
      "composition": "远景/中景/近景/特写"
    }}
  ]
}}"""


def step_shots(video_id):
    log("拆镜", f"开始拆解镜头 [{video_id}]")
    script_data = load_state(video_id, "02_script")
    topic = script_data["topic"]

    est_duration = script_data.get("estimated_duration_sec", TARGET_DURATION_SEC)
    num_shots = min(MAX_SHOTS, max(MIN_SHOTS, round(est_duration / 5)))

    prompt = SHOTS_PROMPT.format(
        num_shots=num_shots,
        script=script_data["script"],
        title=topic.get("title", ""),
        emotion=topic.get("emotion", "治愈"),
        target_scene=topic.get("target_scene", "")
    )
    resp = call_llm(prompt)
    shots_data = parse_json_response(resp)

    # 按文案长度分配时长
    shots = shots_data.get("shots", [])
    total_len = sum(len(s.get("subtitle_text", "")) for s in shots) or 1
    for s in shots:
        ratio = len(s.get("subtitle_text", "")) / total_len
        s["duration_sec"] = max(3.0, round(TARGET_DURATION_SEC * ratio, 1))

    shots_data["video_id"] = video_id
    save_state(video_id, "03_shots", shots_data)
    log("拆镜", f"镜头数: {len(shots)}")
    return shots_data


# ============================================================
# Step 4: Flux 生图
# ============================================================

def generate_single_image(flux_prompt, output_path, max_retries=3):
    """调用 Flux via OpenRouter 生成单张图片
    
    OpenRouter 图片生成走 /chat/completions 端点，需要 modalities: ["image"]
    返回的图片是 base64 data URL 格式，在 assistant message content 中
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/RENXINPAN/content-optimizer",
        "X-Title": "Content Optimizer - Drama Video"
    }
    payload = {
        "model": IMAGE_MODEL,
        "messages": [
            {"role": "user", "content": flux_prompt}
        ],
        "modalities": ["image"],
        "max_tokens": 4096,
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers, json=payload, timeout=180
            )
            resp.raise_for_status()
            data = resp.json()

            # 从 assistant message 中提取 base64 图片
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # content 可能是字符串(data URL)或数组
            img_data = None
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "image_url":
                        img_data = block.get("image_url", {}).get("url", "")
                        break
                    elif isinstance(block, dict) and block.get("type") == "image":
                        img_data = block.get("url", "") or block.get("data", "")
                        break
            elif isinstance(content, str) and "base64" in content:
                img_data = content

            if not img_data:
                raise ValueError(f"未找到图片数据，响应: {json.dumps(data, ensure_ascii=False)[:500]}")

            # 解析 base64 data URL: "data:image/png;base64,xxxxx"
            if img_data.startswith("data:"):
                b64_str = img_data.split(",", 1)[1]
            else:
                b64_str = img_data

            with open(output_path, "wb") as f:
                f.write(base64.b64decode(b64_str))

            return output_path
        except Exception as e:
            log("生图", f"失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(10 * (attempt + 1))
            else:
                raise


def step_images(video_id):
    log("生图", f"开始生成图片 [{video_id}]")
    shots_data = load_state(video_id, "03_shots")
    shots = shots_data["shots"]
    char_desc = shots_data.get("character_description", "")

    img_dir = os.path.join(OUTPUT_DIR, "images", video_id)
    os.makedirs(img_dir, exist_ok=True)

    for i, shot in enumerate(shots):
        sn = shot["shot_number"]
        log("生图", f"镜头 {sn}/{len(shots)}...")

        base_prompt = shot["flux_prompt"]
        if char_desc:
            base_prompt = f"{char_desc}, {base_prompt}"

        mood_extra = MOOD_STYLES.get(shot.get("mood", ""), "")
        full_prompt = f"{base_prompt}, {mood_extra}, {FLUX_BASE_STYLE}"

        out_path = os.path.join(img_dir, f"shot_{sn:02d}.png")
        try:
            generate_single_image(full_prompt, out_path)
            shot["image_path"] = out_path
            log("生图", f"✅ 镜头 {sn} → {out_path}")
        except Exception as e:
            log("生图", f"❌ 镜头 {sn} 失败: {e}")
            shot["image_path"] = None

        if i < len(shots) - 1:
            time.sleep(3)  # API 限流保护

    success = sum(1 for s in shots if s.get("image_path"))
    log("生图", f"完成: {success}/{len(shots)}")
    shots_data["image_dir"] = img_dir
    save_state(video_id, "04_images", shots_data)
    return shots_data


# ============================================================
# Step 5: Edge-TTS 配音
# ============================================================

async def _tts_segment(text, audio_path, sub_path):
    """生成单段配音"""
    import edge_tts
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = text.replace("[停顿]", "。")
    text = re.sub(r'。+', '。', text).strip()

    if os.path.exists(audio_path):
        os.remove(audio_path)

    communicate = edge_tts.Communicate(text, voice=TTS_VOICE, rate=TTS_RATE)
    subtitles = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            with open(audio_path, "ab") as f:
                f.write(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            subtitles.append({
                "text": chunk["text"],
                "offset": chunk["offset"],
                "duration": chunk["duration"],
            })

    duration_ms = 0
    if subtitles:
        last = subtitles[-1]
        duration_ms = (last["offset"] + last["duration"]) / 10000

    return {"audio_path": audio_path, "duration_ms": duration_ms}


async def _generate_all_voice(video_id):
    shots_data = load_state(video_id, "04_images")
    shots = shots_data["shots"]

    audio_dir = os.path.join(OUTPUT_DIR, "audio", video_id)
    os.makedirs(audio_dir, exist_ok=True)

    total_ms = 0
    for shot in shots:
        sn = shot["shot_number"]
        text = shot.get("subtitle_text", "").strip()
        if not text:
            continue

        log("配音", f"镜头 {sn}...")
        audio_path = os.path.join(audio_dir, f"shot_{sn:02d}.mp3")
        sub_path = os.path.join(audio_dir, f"shot_{sn:02d}.vtt")

        result = await _tts_segment(text, audio_path, sub_path)
        shot["audio_path"] = result["audio_path"]
        shot["audio_duration_ms"] = result["duration_ms"]
        shot["duration_sec"] = max(3.0, result["duration_ms"] / 1000 + 0.5)
        total_ms += result["duration_ms"]
        log("配音", f"✅ 镜头 {sn}: {result['duration_ms']:.0f}ms")

    # 合并全部音频
    full_audio = os.path.join(audio_dir, "full_narration.mp3")
    concat_list = os.path.join(audio_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for shot in shots:
            if shot.get("audio_path") and os.path.exists(shot["audio_path"]):
                f.write(f"file '{os.path.abspath(shot['audio_path'])}'\n")

    os.system(f'ffmpeg -y -f concat -safe 0 -i "{concat_list}" -c copy "{full_audio}" 2>/dev/null')

    shots_data["full_audio_path"] = full_audio
    shots_data["total_audio_duration_ms"] = total_ms
    save_state(video_id, "05_voice", shots_data)
    log("配音", f"总时长: {total_ms/1000:.1f}s")
    return shots_data


def step_voice(video_id):
    log("配音", f"开始生成配音 [{video_id}]")
    return asyncio.run(_generate_all_voice(video_id))


# ============================================================
# Step 6: FFmpeg 合成视频
# ============================================================

def format_ass_time(ms):
    ts = ms / 1000
    h = int(ts // 3600)
    m = int((ts % 3600) // 60)
    s = ts % 60
    cs = int((s % 1) * 100)
    return f"{h}:{m:02d}:{int(s):02d}.{cs:02d}"


def generate_ass_subtitle(shots, output_path):
    """生成 ASS 字幕"""
    header = f"""[Script Info]
Title: Drama Subtitle
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans CJK SC,{SUBTITLE_FONTSIZE},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3,1,2,30,30,{SUBTITLE_MARGIN_BOTTOM},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    cum_ms = 0
    for shot in shots:
        dur_ms = shot.get("audio_duration_ms", shot.get("duration_sec", 5) * 1000)
        text = shot.get("subtitle_text", "").strip()
        if not text:
            cum_ms += dur_ms
            continue

        text = text.replace("[停顿]", "")
        text = re.sub(r'\*([^*]+)\*', r'\1', text)

        # 自动换行（每15字）
        lines = []
        line = ""
        for ch in text:
            line += ch
            if len(line) >= 15 and ch in "，。！？、；：":
                lines.append(line)
                line = ""
        if line:
            lines.append(line)

        display = "\\N".join(lines)
        start = format_ass_time(cum_ms)
        end = format_ass_time(cum_ms + dur_ms)
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{{\\fad(300,300)}}{display}")
        cum_ms += dur_ms

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")
    return output_path


def step_video(video_id):
    log("合成", f"开始视频合成 [{video_id}]")
    voice_data = load_state(video_id, "05_voice")
    shots = voice_data["shots"]
    full_audio = voice_data.get("full_audio_path", "")

    video_dir = os.path.join(OUTPUT_DIR, "video", video_id)
    os.makedirs(video_dir, exist_ok=True)

    # 字幕
    sub_path = os.path.join(video_dir, "subtitles.ass")
    generate_ass_subtitle(shots, sub_path)

    # BGM
    bgm_path = None
    if os.path.exists(BGM_DIR):
        bgm_files = glob.glob(os.path.join(BGM_DIR, "*.mp3"))
        if bgm_files:
            bgm_path = random.choice(bgm_files)
            log("合成", f"BGM: {os.path.basename(bgm_path)}")

    # 构建 FFmpeg 命令
    valid_shots = [s for s in shots if s.get("image_path") and os.path.exists(s["image_path"])]
    n = len(valid_shots)
    if n == 0:
        raise ValueError("没有可用图片！")

    inputs = []
    filter_parts = []
    for i, shot in enumerate(valid_shots):
        dur = shot.get("duration_sec", 5)
        inputs.extend(["-loop", "1", "-t", str(dur), "-i", shot["image_path"]])

        # Ken Burns 效果
        frames = int(dur * VIDEO_FPS)
        if i % 3 == 0:
            zoom = f"zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS}"
        elif i % 3 == 1:
            zoom = f"zoompan=z='1.05':x='if(eq(on,1),0,x+1)':y='ih/2-(ih/zoom/2)':d={frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS}"
        else:
            zoom = f"zoompan=z='if(eq(on,1),1.08,max(zoom-0.0008,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS}"

        filter_parts.append(
            f"[{i}:v]{zoom},"
            f"fade=t=in:st=0:d={TRANSITION_SEC}:alpha=1,"
            f"fade=t=out:st={dur - TRANSITION_SEC}:d={TRANSITION_SEC}:alpha=1,"
            f"setpts=PTS-STARTPTS[v{i}]"
        )

    concat_in = "".join(f"[v{i}]" for i in range(n))
    filter_parts.append(f"{concat_in}concat=n={n}:v=1:a=0[slideshow]")

    filter_complex = ";\n".join(filter_parts)

    cmd = ["ffmpeg", "-y"] + inputs
    audio_idx = n
    cmd.extend(["-i", full_audio])

    if bgm_path:
        cmd.extend(["-i", bgm_path])
        bgm_idx = n + 1
        filter_complex += f";\n[{audio_idx}:a]aformat=sample_rates=44100:channel_layouts=mono[narration]"
        filter_complex += f";\n[{bgm_idx}:a]aformat=sample_rates=44100:channel_layouts=mono,volume={BGM_VOLUME}[bgm]"
        filter_complex += f";\n[narration][bgm]amix=inputs=2:duration=first:dropout_transition=3[mixed]"
        audio_map = "[mixed]"
    else:
        audio_map = f"{audio_idx}:a"

    filter_complex += f";\n[slideshow]ass='{sub_path}'[final]"

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[final]", "-map", audio_map,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        os.path.join(video_dir, f"{video_id}_final.mp4")
    ])

    log("合成", f"执行 FFmpeg ({n} 个镜头)...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        log("合成", f"❌ FFmpeg 错误:\n{result.stderr[-500:]}")
        raise RuntimeError(f"FFmpeg 失败")

    output_path = os.path.join(video_dir, f"{video_id}_final.mp4")

    # 获取视频信息
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", output_path],
        capture_output=True, text=True
    )
    video_info = {}
    if probe.returncode == 0:
        fmt = json.loads(probe.stdout).get("format", {})
        video_info = {
            "duration_sec": round(float(fmt.get("duration", 0)), 1),
            "size_mb": round(int(fmt.get("size", 0)) / 1024 / 1024, 2),
        }

    result_data = {
        "video_id": video_id,
        "video_path": output_path,
        "video_info": video_info,
        "shots": shots,
    }
    save_state(video_id, "06_video", result_data)
    log("合成", f"✅ 完成: {video_info.get('duration_sec', 0)}s / {video_info.get('size_mb', 0)}MB")
    return result_data


# ============================================================
# Step 7: 存 Airtable + 通知
# ============================================================

def step_publish(video_id):
    log("发布", f"上传 Airtable + 通知 [{video_id}]")

    topic = load_state(video_id, "01_topic") or {}
    script = load_state(video_id, "02_script") or {}
    video = load_state(video_id, "06_video") or {}

    db = DramaAirtable()
    fields = {
        "video_id": video_id,
        "topic": topic.get("title", ""),
        "emotion": topic.get("emotion", ""),
        "script": script.get("script", ""),
        "word_count": script.get("actual_word_count", 0),
        "shots_count": len(video.get("shots", [])),
        "video_duration_sec": video.get("video_info", {}).get("duration_sec", 0),
        "video_size_mb": video.get("video_info", {}).get("size_mb", 0),
        "status": "待发布",
        "platform": "douyin",
        "created_at": datetime.now().isoformat(),
    }

    record_id = None
    try:
        record_id = db.create_record(fields)
        log("发布", f"✅ Airtable记录: {record_id}")
    except Exception as e:
        log("发布", f"⚠️ Airtable失败: {e}")

    # Server酱通知（与 review.py 一致）
    info = video.get("video_info", {})
    notify_serverchan(
        f"🎬 短剧视频已生成: {topic.get('title', video_id)}",
        f"**视频ID**: {video_id}\n\n"
        f"**选题**: {topic.get('title', 'N/A')}\n\n"
        f"**情绪**: {topic.get('emotion', 'N/A')}\n\n"
        f"**时长**: {info.get('duration_sec', 0)}s\n\n"
        f"**大小**: {info.get('size_mb', 0)}MB\n\n"
        f"**状态**: 待发布到抖音\n\n"
        f"请到 GitHub Actions Artifacts 下载视频文件。"
    )

    return {"record_id": record_id, "fields": fields}


# ============================================================
# 主流程
# ============================================================

PIPELINE_STEPS = [
    ("01_topic",  "选题生成", step_topic),
    ("02_script", "剧本撰写", step_script),
    ("03_shots",  "镜头拆解", step_shots),
    ("04_images", "图片生成", step_images),
    ("05_voice",  "AI配音",   step_voice),
    ("06_video",  "视频合成", step_video),
    ("07_publish","发布通知", step_publish),
]


def run_pipeline(video_id=None, custom_topic=None, start_from=None):
    ensure_dirs()
    if video_id is None:
        video_id = generate_video_id()

    log("Pipeline", "=" * 60)
    log("Pipeline", f"🎬 短剧视频流水线启动")
    log("Pipeline", f"   Video ID: {video_id}")
    if custom_topic:
        log("Pipeline", f"   指定主题: {custom_topic}")
    log("Pipeline", "=" * 60)

    # 确定起始步骤（断点续传）
    start_idx = 0
    if start_from:
        for i, (sid, _, _) in enumerate(PIPELINE_STEPS):
            if sid == start_from or start_from in sid:
                start_idx = i
                break

    results = {}
    t0 = time.time()

    for i, (step_id, step_name, step_func) in enumerate(PIPELINE_STEPS):
        if i < start_idx:
            log("Pipeline", f"⏭️ 跳过 [{step_name}]")
            continue

        log("Pipeline", f"\n{'='*40}")
        log("Pipeline", f"📍 {i+1}/{len(PIPELINE_STEPS)}: {step_name}")
        log("Pipeline", f"{'='*40}")

        st = time.time()
        try:
            if step_id == "01_topic":
                step_func(video_id, custom_topic)
            else:
                step_func(video_id)
            dur = time.time() - st
            log("Pipeline", f"✅ {step_name} ({dur:.1f}s)")
            results[step_id] = "success"
        except Exception as e:
            dur = time.time() - st
            log("Pipeline", f"❌ {step_name} 失败 ({dur:.1f}s): {e}")
            results[step_id] = f"failed: {e}"
            if step_id in ["01_topic", "02_script", "03_shots"]:
                log("Pipeline", "🛑 关键步骤失败，中止")
                break

    total = time.time() - t0
    log("Pipeline", "\n" + "=" * 60)
    log("Pipeline", f"🏁 完成 | 耗时 {total:.0f}s ({total/60:.1f}min) | ID: {video_id}")
    for sid, status in results.items():
        icon = "✅" if status == "success" else "❌"
        log("Pipeline", f"   {icon} {sid}: {status}")
    log("Pipeline", "=" * 60)

    # GitHub Actions 输出
    gh_output = os.getenv("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"video_id={video_id}\n")
            ok = all(v == "success" for v in results.values())
            f.write(f"pipeline_status={'success' if ok else 'partial_failure'}\n")

    return video_id, results


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python drama_main.py generate              # 自动选题生成")
        print("  python drama_main.py generate \"主题\"        # 指定主题")
        print("  python drama_main.py resume <video_id>      # 断点续传")
        print("  python drama_main.py topic_only             # 只生成选题")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "generate":
        topic = sys.argv[2] if len(sys.argv) > 2 else None
        run_pipeline(custom_topic=topic)

    elif cmd == "resume":
        if len(sys.argv) < 3:
            print("请指定 video_id")
            sys.exit(1)
        vid = sys.argv[2]
        # 找到最后完成的步骤，从下一步开始
        last_done = None
        for step_id, _, _ in PIPELINE_STEPS:
            if load_state(vid, step_id):
                last_done = step_id
        if last_done:
            idx = [s[0] for s in PIPELINE_STEPS].index(last_done)
            next_step = PIPELINE_STEPS[idx + 1][0] if idx + 1 < len(PIPELINE_STEPS) else None
            if next_step:
                log("Resume", f"从 {next_step} 继续")
                run_pipeline(video_id=vid, start_from=next_step)
            else:
                log("Resume", "所有步骤已完成")
        else:
            run_pipeline(video_id=vid)

    elif cmd == "topic_only":
        ensure_dirs()
        vid = generate_video_id()
        topic = sys.argv[2] if len(sys.argv) > 2 else None
        result = step_topic(vid, topic)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
