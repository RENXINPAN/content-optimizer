"""
finance_main.py - 财经图文自动生成系统

用法:
    python finance_main.py generate              # 从选题库取一条，生成文章+图片，存入Airtable
    python finance_main.py generate 5            # 一次生成5篇
    python finance_main.py batch_topics 20       # 批量生成20条选题填入选题库

流程:
    finance_topics表取选题 → AI写文章 → Python生成3张图 → 存入finance_articles表
"""
import os
import sys
import json
import time
import re
import textwrap
import requests
from datetime import datetime
from io import BytesIO

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("请安装 Pillow: pip install Pillow")
    sys.exit(1)

# ============================================================
# 配置
# ============================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "apphDOxCslstliiKO")
SERVERCHAN_KEY = os.getenv("SERVERCHAN_KEY", "")

LLM_MODEL = "anthropic/claude-sonnet-4.6"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

TOPICS_TABLE = "finance_topics"
ARTICLES_TABLE = "finance_articles"

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "finance_output")

# 图片设计参数
IMG_WIDTH = 1080
IMG_HEIGHT = 1440
BG_COLOR = (15, 23, 52)        # 深蓝背景
GOLD_COLOR = (218, 175, 72)    # 金色文字
WHITE_COLOR = (255, 255, 255)  # 白色辅助文字
GRAY_COLOR = (140, 150, 180)   # 灰色小字

# 字体路径（GitHub Actions Ubuntu 环境）
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_BLACK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"


# ============================================================
# 工具函数
# ============================================================

def log(step, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{step}] {msg}")


def call_llm(prompt, model=None, max_retries=3):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/RENXINPAN/content-optimizer",
        "X-Title": "Content Optimizer - Finance"
    }
    payload = {
        "model": model or LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
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
            log("LLM", f"请求失败 ({attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise


def parse_json_response(text):
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.index("\n")
        last_block = text.rfind("```")
        if last_block > first_nl:
            text = text[first_nl + 1:last_block].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            fixed = re.sub(r'(?<!\\)\n', '\\n', text)
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # 尝试数组
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法解析 JSON:\n{text[:500]}")


# ============================================================
# Airtable 操作
# ============================================================

class AirtableClient:
    def __init__(self, table_name):
        self.base_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_name}"
        self.headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json; charset=utf-8"
        }

    def get_next(self, status_field="status", status_value="待使用"):
        params = {
            "maxRecords": 1,
            "filterByFormula": f"{{{status_field}}}='{status_value}'",
        }
        resp = requests.get(self.base_url, headers=self.headers, params=params, timeout=30)
        if resp.status_code != 200:
            return None
        records = resp.json().get("records", [])
        if not records:
            return None
        return records[0]["id"], records[0]["fields"]

    def update_status(self, record_id, status_field, status_value):
        requests.patch(
            self.base_url,
            headers=self.headers,
            json={"records": [{"id": record_id, "fields": {status_field: status_value}}]},
            timeout=30
        )

    def create_record(self, fields):
        resp = requests.post(
            self.base_url,
            headers=self.headers,
            json={"records": [{"fields": fields}]},
            timeout=30
        )
        if resp.status_code == 422:
            log("Airtable", f"422: {resp.text[:300]}")
            return None
        resp.raise_for_status()
        return resp.json().get("records", [{}])[0].get("id")

    def create_records_batch(self, records_fields):
        """批量创建（最多10条）"""
        records = [{"fields": f} for f in records_fields]
        resp = requests.post(
            self.base_url,
            headers=self.headers,
            json={"records": records},
            timeout=30
        )
        resp.raise_for_status()
        return len(resp.json().get("records", []))

    def upload_attachment(self, record_id, field_name, file_path):
        """上传附件到 Airtable（通过 URL 方式，需先上传到可访问的地方）"""
        # Airtable 附件需要 URL，本地文件无法直接上传
        # 这里改为将图片路径记录下来，在 GitHub Actions 中通过 Artifacts 下载
        pass


# ============================================================
# 图片生成
# ============================================================

def get_font(path, size):
    """安全获取字体，找不到则用默认"""
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        # 尝试备用路径
        for alt in [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
        ]:
            try:
                return ImageFont.truetype(alt, size)
            except (OSError, IOError):
                continue
        log("图片", "⚠️ 找不到中文字体，使用默认字体")
        return ImageFont.load_default()


def wrap_text(text, font, max_width, draw):
    """按像素宽度自动换行中文文本"""
    lines = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] > max_width:
            if current_line:
                lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    return lines


def generate_cover_image(title, output_path):
    """生成封面图：深蓝背景 + 金色大标题"""
    img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 顶部装饰线
    draw.rectangle([(40, 40), (IMG_WIDTH - 40, 44)], fill=GOLD_COLOR)

    # 标题
    font_title = get_font(FONT_BLACK, 72)
    lines = wrap_text(title, font_title, IMG_WIDTH - 120, draw)

    # 垂直居中
    line_height = 95
    total_height = len(lines) * line_height
    y_start = (IMG_HEIGHT - total_height) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_title)
        x = (IMG_WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, y_start + i * line_height), line, font=font_title, fill=GOLD_COLOR)

    # 底部装饰线
    draw.rectangle([(40, IMG_HEIGHT - 44), (IMG_WIDTH - 40, IMG_HEIGHT - 40)], fill=GOLD_COLOR)

    # 底部标识
    font_small = get_font(FONT_BOLD, 28)
    draw.text((IMG_WIDTH // 2 - 60, IMG_HEIGHT - 90), "1 / 3", font=font_small, fill=GRAY_COLOR)

    img.save(output_path, "PNG", quality=95)
    return output_path


def generate_content_image(summary, output_path):
    """生成核心观点图：深蓝背景 + 白色正文 + 金色重点"""
    img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 顶部标签
    font_label = get_font(FONT_BOLD, 32)
    draw.text((60, 60), "▎核心观点", font=font_label, fill=GOLD_COLOR)

    # 分隔线
    draw.rectangle([(60, 110), (IMG_WIDTH - 60, 112)], fill=(40, 50, 80))

    # 正文
    font_body = get_font(FONT_BOLD, 48)
    lines = wrap_text(summary, font_body, IMG_WIDTH - 160, draw)

    line_height = 72
    total_height = len(lines) * line_height
    y_start = max(160, (IMG_HEIGHT - total_height) // 2 - 40)

    for i, line in enumerate(lines):
        draw.text((80, y_start + i * line_height), line, font=font_body, fill=WHITE_COLOR)

    # 底部装饰
    draw.rectangle([(60, IMG_HEIGHT - 120), (IMG_WIDTH - 60, IMG_HEIGHT - 118)], fill=(40, 50, 80))
    font_small = get_font(FONT_BOLD, 28)
    draw.text((IMG_WIDTH // 2 - 60, IMG_HEIGHT - 90), "2 / 3", font=font_small, fill=GRAY_COLOR)

    img.save(output_path, "PNG", quality=95)
    return output_path


def generate_ending_image(golden_line, output_path):
    """生成总结金句图：深蓝背景 + 金色金句 + 装饰"""
    img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 顶部标签
    font_label = get_font(FONT_BOLD, 32)
    draw.text((60, 60), "| 金句", font=font_label, fill=GOLD_COLOR)

    # 顶部装饰线
    draw.rectangle([(60, 110), (IMG_WIDTH - 60, 112)], fill=(40, 50, 80))

    # 左侧装饰竖线
    draw.rectangle([(80, 400), (88, 700)], fill=GOLD_COLOR)

    # 金句
    font_golden = get_font(FONT_BLACK, 56)
    lines = wrap_text(golden_line, font_golden, IMG_WIDTH - 200, draw)

    line_height = 80
    total_height = len(lines) * line_height
    y_start = (IMG_HEIGHT - total_height) // 2

    for i, line in enumerate(lines):
        draw.text((120, y_start + i * line_height), line, font=font_golden, fill=GOLD_COLOR)

    # 底部装饰
    draw.rectangle([(40, IMG_HEIGHT - 44), (IMG_WIDTH - 40, IMG_HEIGHT - 40)], fill=GOLD_COLOR)
    font_small = get_font(FONT_BOLD, 28)
    draw.text((IMG_WIDTH // 2 - 60, IMG_HEIGHT - 90), "3 / 3", font=font_small, fill=GRAY_COLOR)

    img.save(output_path, "PNG", quality=95)
    return output_path

# ============================================================
# 文章生成 Prompt
# ============================================================

ARTICLE_PROMPT = """你是一个硬核财经认知型博主，擅长用最短的文字讲透一个商业或经济道理。

## 任务
根据以下选题，写一篇200-400字的财经短文。

## 选题
标题：{title}
角度：{angle}

## 写作要求

【钩子】开头第一句必须制造好奇心、紧张感或认知冲突，让人忍不住读下去。

【节奏】每一句都在拉着读者往下看。信息密度高，没有一句废话。短句制造冲击，稍长句展开价值。

【语气】像一个真正懂行的人在说大实话。用"说白了""本质上""很多人不知道的是"这类内行人语气。不吹嘘、不说教、不装专家。

【结尾】最后一句是值得截图转发的金句，要扎心、要让人记住。

## 禁止
- 不要用"首先、其次、最后"的结构
- 不要鸡汤、不要说教
- 不要"让我们一起""希望大家"这类号召
- 不要空洞的大道理

## 输出格式（纯JSON，不要其他内容）
{{
  "title": "文章标题（可以优化选题标题，让它更有吸引力）",
  "content": "正文内容，200-400字",
  "summary": "核心观点，一句话概括，20字以内",
  "golden_line": "总结金句，一句话，要有传播力，25字以内"
}}"""


# ============================================================
# 选题批量生成 Prompt
# ============================================================

TOPICS_PROMPT = """你是一个硬核财经内容策划师，擅长找到让普通人觉得"原来如此"的商业和经济选题。

## 任务
生成 {count} 个财经类图文选题。

## 选题方向（混合使用）
1. 认知刷新型：一个反常识的经济学道理（如：为什么穷人越存钱越穷）
2. 商业揭秘型：某个公司/行业的赚钱逻辑（如：瑞幸9块9怎么赚钱的）
3. 历史复盘型：过去某次危机/泡沫/暴富的故事（如：2008年华尔街怎么骗了全世界）

## 要求
- 标题本身就是钩子，看到就想点
- 每个标题15字以内
- 不要太学术，普通人看得懂
- {count}个选题主题全部不同

{dedup}

## 输出格式（纯JSON数组）
[
  {{"title": "选题标题", "angle": "一句话说明切入角度"}}
]"""


# ============================================================
# 主流程
# ============================================================

def generate_article(topic_title, topic_angle=""):
    """根据选题生成一篇文章 + 3张图"""
    log("写作", f"选题: {topic_title}")

    # 1. AI 写文章
    prompt = ARTICLE_PROMPT.format(title=topic_title, angle=topic_angle or "自由发挥")
    resp = call_llm(prompt)
    article = parse_json_response(resp)

    title = article.get("title", topic_title)
    content = article.get("content", "")
    summary = article.get("summary", "")
    golden_line = article.get("golden_line", "")

    clean = re.sub(r'\s+', '', content)
    log("写作", f"标题: {title}")
    log("写作", f"字数: {len(clean)}")
    log("写作", f"观点: {summary}")
    log("写作", f"金句: {golden_line}")

    # 2. 生成3张图
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    cover_path = os.path.join(OUTPUT_DIR, f"{ts}_cover.png")
    content_path = os.path.join(OUTPUT_DIR, f"{ts}_content.png")
    ending_path = os.path.join(OUTPUT_DIR, f"{ts}_ending.png")

    generate_cover_image(title, cover_path)
    log("图片", f"✅ 封面 → {cover_path}")

    generate_content_image(summary, content_path)
    log("图片", f"✅ 观点 → {content_path}")

    generate_ending_image(golden_line, ending_path)
    log("图片", f"✅ 金句 → {ending_path}")

    return {
        "title": title,
        "content": content,
        "summary": summary,
        "golden_line": golden_line,
        "cover_path": cover_path,
        "content_path": content_path,
        "ending_path": ending_path,
    }


def run_generate(count=1):
    """从选题库取选题，生成文章+图片，存入成品库"""
    topics_db = AirtableClient(TOPICS_TABLE)
    articles_db = AirtableClient(ARTICLES_TABLE)

    for i in range(count):
        log("Pipeline", f"\n{'='*50}")
        log("Pipeline", f"📝 第 {i+1}/{count} 篇")

        # 取选题
        result = topics_db.get_next("status", "待使用")
        if not result:
            log("Pipeline", "❌ 选题库没有待使用的选题了")
            break

        record_id, fields = result
        topic_title = fields.get("title", "")
        topic_angle = fields.get("angle", "")

        # 标记已使用
        topics_db.update_status(record_id, "status", "已使用")

        try:
            # 生成文章+图片
            article = generate_article(topic_title, topic_angle)

            # 存入 Airtable（图片路径暂存，通过 Artifacts 下载）
            articles_db.create_record({
                "title": article["title"],
                "content": article["content"],
                "summary": article["summary"],
                "golden_line": article["golden_line"],
                "status": "待发布",
                "created_at": datetime.now().isoformat(),
            })
            log("Pipeline", f"✅ 已存入 Airtable")

        except Exception as e:
            log("Pipeline", f"❌ 生成失败: {e}")

        if i < count - 1:
            time.sleep(3)

    log("Pipeline", f"\n{'='*50}")
    log("Pipeline", f"🏁 完成，共处理 {count} 篇")


def run_batch_topics(count=20):
    """批量生成选题填入选题库"""
    log("选题", f"开始生成 {count} 条选题")

    topics_db = AirtableClient(TOPICS_TABLE)

    # 获取已有选题防重复
    existing = []
    try:
        resp = requests.get(
            topics_db.base_url,
            headers=topics_db.headers,
            params={"maxRecords": 100, "fields[]": "title"},
            timeout=30
        )
        if resp.status_code == 200:
            existing = [r["fields"].get("title", "") for r in resp.json().get("records", [])]
    except:
        pass

    all_titles = list(existing)
    total_created = 0
    rounds = (count + 9) // 10

    for round_num in range(1, rounds + 1):
        remaining = count - total_created
        batch = min(10, remaining)

        dedup = ""
        if all_titles:
            dedup = f"以下选题已存在，不要重复：\n{', '.join(all_titles[-30:])}"

        prompt = TOPICS_PROMPT.format(count=batch, dedup=dedup)
        log("选题", f"第 {round_num}/{rounds} 轮，生成 {batch} 条")

        try:
            resp = call_llm(prompt)
            topics = parse_json_response(resp)
            if not isinstance(topics, list):
                topics = [topics]
        except Exception as e:
            log("选题", f"❌ 生成失败: {e}")
            continue

        # 去重
        valid = []
        for t in topics:
            title = t.get("title", "").strip()
            if title and title not in all_titles:
                valid.append({
                    "title": title,
                    "angle": t.get("angle", ""),
                    "status": "待使用",
                })
                all_titles.append(title)

        if valid:
            try:
                created = topics_db.create_records_batch(valid)
                total_created += created
                log("选题", f"✅ 写入 {created} 条")
            except Exception as e:
                log("选题", f"❌ 写入失败: {e}")

        for t in valid:
            log("选题", f"  📌 {t['title']}")

        if round_num < rounds:
            time.sleep(3)

    log("选题", f"\n🏁 选题生成完成，共 {total_created} 条")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python finance_main.py generate          # 生成1篇")
        print("  python finance_main.py generate 5        # 生成5篇")
        print("  python finance_main.py batch_topics 20   # 批量生成20条选题")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "generate":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        run_generate(count)

    elif cmd == "batch_topics":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        run_batch_topics(count)

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
