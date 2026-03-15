"""
finance_main.py - 财经图文自动生成系统

用法:
    python finance_main.py generate              # 从选题库取一条，生成文章+图片，存入Airtable
    python finance_main.py generate 5            # 一次生成5篇
    python finance_main.py batch_topics 20       # 批量生成20条选题填入选题库

流程:
    finance_topics表取选题 → AI写文章 → Nano Banana生成2张封面图(竖版+横版)
    → catbox.moe上传图床 → 存入finance_articles表(含图片URL)
"""
import os
import sys
import json
import time
import re
import base64
import requests
from datetime import datetime
from io import BytesIO

# ============================================================
# 配置
# ============================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "apphDOxCslstliiKO")
SERVERCHAN_KEY = os.getenv("SERVERCHAN_KEY", "")

LLM_MODEL = "anthropic/claude-sonnet-4.6"
IMAGE_MODEL = "google/gemini-3.1-flash-image-preview"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

TOPICS_TABLE = "finance_topics"
ARTICLES_TABLE = "finance_articles"

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "finance_output")

# 样图路径（仓库内）
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
SAMPLE_VERTICAL = os.path.join(TEMPLATE_DIR, "sample_vertical.png")
SAMPLE_HORIZONTAL = os.path.join(TEMPLATE_DIR, "sample_horizontal.png")


# ============================================================
# 工具函数
# ============================================================

def log(step, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{step}] {msg}")


def call_llm(prompt, model=None, max_retries=3):
    """调用 OpenRouter 文本模型"""
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
    """从 LLM 响应中提取 JSON"""
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
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法解析 JSON:\n{text[:500]}")


def image_to_base64(path):
    """将本地图片转为 base64 字符串"""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ============================================================
# Nano Banana 图片生成 (via OpenRouter)
# ============================================================

def generate_image_nano_banana(title, sample_path, aspect, max_retries=3):
    """
    调用 Nano Banana 2 (gemini-3.1-flash-image-preview) 生成风格一致的封面图。

    参数:
        title: 文章标题，将出现在图片上
        sample_path: 样图路径，用于风格参考
        aspect: "vertical" (3:4, 810x1080) 或 "horizontal" (16:9, 1920x1080)

    返回:
        bytes: 生成的图片 PNG 数据
    """
    # 读取样图
    sample_b64 = image_to_base64(sample_path)

    # 根据比例设置尺寸说明
    if aspect == "vertical":
        size_desc = "竖版 3:4 比例 (810×1080像素)"
        platform = "支付宝"
    else:
        size_desc = "横版 16:9 比例 (1920×1080像素)"
        platform = "百家号"

    prompt = f"""请参考这张样图的视觉风格（配色方案、排版布局、字体风格、装饰元素），
生成一张全新的财经文章封面图。

要求：
1. 保持样图的整体视觉风格和配色
2. 图片上清晰展示以下标题文字：「{title}」
3. 标题文字要大而醒目，居中排列，确保易读
4. 尺寸：{size_desc}，用于{platform}平台发布
5. 背景要有财经/商业氛围感
6. 整体要专业、高级、有质感
7. 文字必须是简体中文，不能有错别字

请直接生成图片，不要回复文字。"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/RENXINPAN/content-optimizer",
        "X-Title": "Content Optimizer - Finance"
    }

    # 构造多模态消息：样图 + 文字提示
    payload = {
        "model": IMAGE_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{sample_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "max_tokens": 4096,
        # 指定图片尺寸参数（OpenRouter 透传给 Gemini）
        "provider": {
            "order": ["Google"],
            "allow_fallbacks": False
        }
    }

    for attempt in range(max_retries):
        try:
            log("图片", f"Nano Banana 生成中... ({aspect}, 尝试 {attempt+1}/{max_retries})")
            resp = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers, json=payload, timeout=180
            )
            resp.raise_for_status()
            data = resp.json()

            # 从响应中提取图片
            # Gemini image generation 返回格式可能有几种
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("API 返回空 choices")

            message = choices[0].get("message", {})
            content = message.get("content", "")

            # 情况1: content 是一个数组（多模态响应）
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        # inline_data 格式
                        if part.get("type") == "image_url":
                            img_url = part.get("image_url", {}).get("url", "")
                            if img_url.startswith("data:"):
                                b64_data = img_url.split(",", 1)[1]
                                return base64.b64decode(b64_data)
                        # 直接 base64 格式
                        if "inline_data" in part:
                            b64_data = part["inline_data"].get("data", "")
                            if b64_data:
                                return base64.b64decode(b64_data)
                        # OpenRouter 包装的格式
                        if part.get("type") == "image" and "source" in part:
                            b64_data = part["source"].get("data", "")
                            if b64_data:
                                return base64.b64decode(b64_data)

            # 情况2: content 是字符串，可能包含 base64
            if isinstance(content, str):
                # 检查是否有嵌入的 base64 图片
                b64_match = re.search(
                    r'data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=]+)',
                    content
                )
                if b64_match:
                    return base64.b64decode(b64_match.group(1))

                # 检查纯 base64 字符串
                if len(content) > 1000 and re.match(r'^[A-Za-z0-9+/=\s]+$', content):
                    return base64.b64decode(content.replace("\n", "").replace(" ", ""))

            # 如果找不到图片数据，输出调试信息
            log("图片", f"⚠️ 未从响应中提取到图片数据，response keys: {list(data.keys())}")
            log("图片", f"  message keys: {list(message.keys())}")
            if isinstance(content, list):
                for i, part in enumerate(content):
                    if isinstance(part, dict):
                        log("图片", f"  content[{i}] type={part.get('type')} keys={list(part.keys())}")
            elif isinstance(content, str):
                log("图片", f"  content (str) length={len(content)}, preview={content[:200]}")

            raise ValueError("无法从 API 响应中提取图片数据")

        except Exception as e:
            log("图片", f"生成失败 ({attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(10 * (attempt + 1))
            else:
                raise

    raise RuntimeError("图片生成超过最大重试次数")


def generate_cover_images(title):
    """
    生成竖版+横版两张封面图。

    返回:
        dict: {"vertical": bytes, "horizontal": bytes}
    """
    results = {}

    # 竖版 (3:4) - 支付宝
    log("图片", f"🎨 生成竖版封面: {title}")
    results["vertical"] = generate_image_nano_banana(
        title=title,
        sample_path=SAMPLE_VERTICAL,
        aspect="vertical"
    )
    log("图片", f"✅ 竖版封面完成 ({len(results['vertical'])} bytes)")

    # 间隔一下避免限流
    time.sleep(3)

    # 横版 (16:9) - 百家号
    log("图片", f"🎨 生成横版封面: {title}")
    results["horizontal"] = generate_image_nano_banana(
        title=title,
        sample_path=SAMPLE_HORIZONTAL,
        aspect="horizontal"
    )
    log("图片", f"✅ 横版封面完成 ({len(results['horizontal'])} bytes)")

    return results


# ============================================================
# 图床上传 (catbox.moe)
# ============================================================

def upload_to_catbox(image_bytes, filename="cover.png", max_retries=3):
    """
    上传图片到 catbox.moe，返回可访问的 URL。

    参数:
        image_bytes: PNG 图片的 bytes 数据
        filename: 文件名

    返回:
        str: 图片 URL (如 https://files.catbox.moe/xxxxx.png)
    """
    for attempt in range(max_retries):
        try:
            files = {
                "fileToUpload": (filename, BytesIO(image_bytes), "image/png")
            }
            data = {
                "reqtype": "fileupload",
                "userhash": ""  # 匿名上传
            }
            resp = requests.post(
                "https://catbox.moe/user/api.php",
                files=files,
                data=data,
                timeout=60
            )
            resp.raise_for_status()

            url = resp.text.strip()
            if url.startswith("https://"):
                log("上传", f"✅ catbox.moe → {url}")
                return url
            else:
                raise ValueError(f"catbox 返回异常: {url[:200]}")

        except Exception as e:
            log("上传", f"上传失败 ({attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise

    raise RuntimeError("图片上传超过最大重试次数")


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


# ============================================================
# 文章生成 Prompt
# ============================================================

ARTICLE_PROMPT = """你是一个硬核财经认知型博主。你的文章有三个特征：
每一句都在制造好奇心，每一行都让人无法停止阅读，读完后觉得你是真正懂行的人。

## 任务
根据以下选题，写一篇200-400字的财经短文。

## 选题
标题：{title}
角度：{angle}

## 写作三层引擎

【第一层：钩子引擎】
开头第一句必须在2秒内抓住读者。制造好奇心、紧张感或认知冲突。
不用标题党，不用虚假声称，用真实的数字或事实本身制造冲击。

【第二层：留存引擎】
把文章当成一个滑梯，读者一旦坐上去就停不下来。
- 每一句结尾都埋下一个小钩子，让人想看下一句
- 短句制造冲击，稍长句展开价值，节奏交替
- 关键转折用"但是""问题在于""真相是"引导
- 信息密度要高，每一句都在提供新信息或新视角，没有一句废话

【第三层：权威引擎】
让读者觉得你是内行人，但不是通过吹嘘或秀数据。
- 用"说白了""本质上""很多人没注意到的是"这类内行人语气
- 给出别人看不到的角度，或者把复杂的事情用大白话讲透
- 不装专家、不说教、不居高临下
- 像一个真正懂行的朋友在跟你聊天

## 结尾
最后一句是值得截图转发的金句。要扎心、要让人记住、要有传播力。

## 禁止
- 不要"首先、其次、最后"的结构
- 不要鸡汤、不要说教
- 不要"让我们一起""希望大家"这类号召
- 不要空洞的大道理
- 不要重复标题已经说过的信息作为开头

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

TOPICS_PROMPT = """你是一个顶级财经自媒体选题策划师。你的选题有一个核心特征：
用一个具体数字撕开认知缺口，让读者必须点进来才能填上。

## 任务
生成 {count} 个财经类图文选题。

## 选题的黄金标准
好选题 = 一个真实数字 + 一个未解的悬念

数字的作用不是展示事实，而是制造矛盾或好奇：
- 矛盾型："瑞幸卖9块9还能赚钱，星巴克卖38块却在关店" → 读者想知道为什么便宜的反而活得好
- 缺口型："孙正义投马云2000万赚回1700亿，他看到了什么" → 读者想知道他的判断依据
- 反直觉型："日本印了20年的钱，老百姓反而越来越穷" → 读者想知道钱去哪了
- 悬念型："比特币跌了6次90%，每次抄底的人后来怎样了" → 读者想知道结局

## 自检标准
生成每个选题后，问自己：
1. 读者看到这个数字，会不会产生"为什么？""怎么可能？""然后呢？"的反应？
2. 如果只是"哦，原来如此"就结束了，这个选题不合格，换掉
3. 数字是否真实可查？不能瞎编

## 要求
- 标题20字以内，必须含至少1个具体真实数字
- {count}个选题覆盖不同领域（投资、商业、经济、历史、行业），不要扎堆
- 陈述句和问句混用，不要全是问号结尾
- 不要鸡汤、不要说教

{dedup}

## 输出格式（纯JSON数组）
[
  {{"title": "选题标题", "angle": "切入角度，标注核心数字出处"}}
]"""

# ============================================================
# 主流程
# ============================================================

def generate_article(topic_title, topic_angle=""):
    """根据选题生成一篇文章 + 2张封面图（竖版+横版）"""
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

    # 2. Nano Banana 生成2张封面图
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    images = generate_cover_images(title)

    # 保存到本地（备份 + Artifacts 存档）
    vertical_path = os.path.join(OUTPUT_DIR, f"{ts}_cover_vertical.png")
    horizontal_path = os.path.join(OUTPUT_DIR, f"{ts}_cover_horizontal.png")

    with open(vertical_path, "wb") as f:
        f.write(images["vertical"])
    log("图片", f"💾 竖版已保存 → {vertical_path}")

    with open(horizontal_path, "wb") as f:
        f.write(images["horizontal"])
    log("图片", f"💾 横版已保存 → {horizontal_path}")

    # 3. 上传到 catbox.moe 图床
    vertical_url = upload_to_catbox(
        images["vertical"],
        filename=f"{ts}_cover_vertical.png"
    )
    horizontal_url = upload_to_catbox(
        images["horizontal"],
        filename=f"{ts}_cover_horizontal.png"
    )

    return {
        "title": title,
        "content": content,
        "summary": summary,
        "golden_line": golden_line,
        "vertical_path": vertical_path,
        "horizontal_path": horizontal_path,
        "vertical_url": vertical_url,
        "horizontal_url": horizontal_url,
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

            # 存入 Airtable（含图片附件 URL）
            record_fields = {
                "title": article["title"],
                "content": article["content"],
                "summary": article["summary"],
                "golden_line": article["golden_line"],
                "status": "待发布",
                "created_at": datetime.now().isoformat(),
            }

            # Airtable 附件字段格式：[{"url": "..."}]
            if article.get("vertical_url"):
                record_fields["cover_vertical"] = [{"url": article["vertical_url"]}]
            if article.get("horizontal_url"):
                record_fields["cover_horizontal"] = [{"url": article["horizontal_url"]}]

            articles_db.create_record(record_fields)
            log("Pipeline", f"✅ 已存入 Airtable（含图片附件）")
            log("Pipeline", f"   竖版: {article.get('vertical_url', 'N/A')}")
            log("Pipeline", f"   横版: {article.get('horizontal_url', 'N/A')}")

        except Exception as e:
            log("Pipeline", f"❌ 生成失败: {e}")
            import traceback
            traceback.print_exc()

        if i < count - 1:
            time.sleep(5)

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
