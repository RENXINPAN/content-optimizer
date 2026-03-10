"""
batch_generate_scripts.py - 批量生成短剧文案并填充到 Airtable drama_scripts 表

用法:
    python batch_generate_scripts.py              # 生成100条（10轮×10条）
    python batch_generate_scripts.py 50            # 生成50条（5轮×10条）
    python batch_generate_scripts.py 20 --dry-run  # 试跑，只生成不写入Airtable

每轮生成10条，自动把已生成的主题传给下一轮防重复。
"""
import os
import sys
import json
import time
import re
import requests
from datetime import datetime

# ============================================================
# 配置（复用现有 Secrets）
# ============================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "apphDOxCslstliiKO")

LLM_MODEL = "anthropic/claude-sonnet-4.6"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
SCRIPT_TABLE = "drama_scripts"

BATCH_SIZE = 10  # 每轮生成条数


# ============================================================
# Prompt
# ============================================================
BATCH_PROMPT = """你是一名顶级抖音情绪短视频文案创作者。
你的文案特点：共鸣极强、情绪真实、句子极短、画面感强。
你同时擅长两种风格，每条文案随机使用其中一种：

风格A「金句解读型」：
- 开头用"这是我听过/见过/读过最xxx的一段话"引入
- 围绕一个概念展开（关系/自由/安全感/成长等）
- 用生活小场景传递道理，不说教
- 句式有对仗感和节奏感

风格B「生活感悟型」：
- 开头用"后来我才发现/有时候走在路上会想/长大以后才明白"引入
- 描述一个生活瞬间 + 情绪感受 + 一句感悟
- 像一个普通人安静讲述生活

每条文案：120-160字，自然分成6-8个段落（用\\n\\n分隔段落）。
每句6-18字，简单口语，不要文学腔、成功学、鸡汤。

主题从以下随机选（每条不同）：
关系松弛感 / 成年人的孤独 / 成长顿悟 / 时间流逝 / 错过与遗憾 /
城市生活 / 努力与现实 / 普通生活治愈 / 爱情与安全感 / 人生选择 /
青春回忆 / 父母与成长 / 深夜情绪 / 失去与放下 / 重新开始 /
友情变化 / 边界感 / 和解 / 自由与代价 / 慢生活

结构：开头钩子(1句) → 场景展开(3-5句) → 金句收尾(1-2句)

禁止：写剧情/对话/悬疑/商业广告/成功学/连续相同句式

{dedup_instruction}

输出严格JSON数组，不要任何其他内容，不要markdown代码块：
[
  {{
    "title": "主题关键词3-6字",
    "emotion": "核心情绪（治愈/成长/感伤/喜悦/宁静/思念/勇气/自由）",
    "script": "完整文案，段落之间用\\n\\n分隔"
  }}
]

请生成 {count} 条完全不同主题、不同开头、不同结尾的文案。"""


# ============================================================
# 工具函数
# ============================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def call_llm(prompt, max_retries=3):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/RENXINPAN/content-optimizer",
        "X-Title": "Content Optimizer - Batch Scripts"
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8192,
        "temperature": 0.9,
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers, json=payload, timeout=180
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            log(f"LLM 请求失败 ({attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise


def parse_json_array(text):
    """从 LLM 输出中提取 JSON 数组"""
    text = text.strip()
    # 去除 markdown code block
    if text.startswith("```"):
        first_nl = text.index("\n")
        last_block = text.rfind("```")
        if last_block > first_nl:
            text = text[first_nl + 1:last_block].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取第一个 JSON 数组
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(f"无法解析 JSON 数组:\n{text[:500]}")


def write_to_airtable(records):
    """批量写入 Airtable（每次最多10条）"""
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{SCRIPT_TABLE}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json; charset=utf-8"
    }

    # Airtable 批量写入最多10条
    airtable_records = []
    for r in records:
        airtable_records.append({
            "fields": {
                "title": r.get("title", ""),
                "script": r.get("script", ""),
                "emotion": r.get("emotion", "治愈"),
                "status": "待使用",
            }
        })

    resp = requests.post(
        url,
        headers=headers,
        json={"records": airtable_records},
        timeout=30
    )
    if resp.status_code == 422:
        log(f"⚠️ Airtable 422: {resp.text[:300]}")
        return 0
    resp.raise_for_status()
    created = resp.json().get("records", [])
    return len(created)


# ============================================================
# 主流程
# ============================================================

def batch_generate(total_count=100, dry_run=False):
    """
    批量生成文案

    Args:
        total_count: 总条数
        dry_run: 试跑模式，只生成不写入
    """
    log(f"🚀 开始批量生成 {total_count} 条文案")
    if dry_run:
        log("📋 试跑模式：不写入 Airtable")

    rounds = (total_count + BATCH_SIZE - 1) // BATCH_SIZE
    all_scripts = []
    all_titles = []
    total_written = 0

    for round_num in range(1, rounds + 1):
        remaining = total_count - len(all_scripts)
        count = min(BATCH_SIZE, remaining)

        log(f"\n{'='*50}")
        log(f"📝 第 {round_num}/{rounds} 轮，生成 {count} 条")

        # 防重复指令
        if all_titles:
            dedup = f"以下主题已经生成过，绝对不要重复：\n{', '.join(all_titles)}"
        else:
            dedup = "这是第一轮生成，请自由选择主题。"

        prompt = BATCH_PROMPT.format(count=count, dedup_instruction=dedup)

        try:
            response = call_llm(prompt)
            scripts = parse_json_array(response)
        except Exception as e:
            log(f"❌ 第 {round_num} 轮生成失败: {e}")
            continue

        # 校验
        valid_scripts = []
        for s in scripts:
            title = s.get("title", "").strip()
            script = s.get("script", "").strip()
            emotion = s.get("emotion", "治愈").strip()

            if not title or not script:
                log(f"  ⚠️ 跳过空文案")
                continue
            if title in all_titles:
                log(f"  ⚠️ 跳过重复主题: {title}")
                continue

            # 字数检查
            clean = re.sub(r'\s+', '', script)
            wc = len(clean)
            if wc < 80:
                log(f"  ⚠️ 字数太少({wc}字)，跳过: {title}")
                continue
            if wc > 250:
                log(f"  ⚠️ 字数太多({wc}字)，跳过: {title}")
                continue

            valid_scripts.append({
                "title": title,
                "script": script,
                "emotion": emotion,
            })
            all_titles.append(title)

        log(f"✅ 本轮有效文案: {len(valid_scripts)}/{len(scripts)}")

        for s in valid_scripts:
            clean = re.sub(r'\s+', '', s['script'])
            log(f"  📄 {s['title']} ({len(clean)}字) [{s['emotion']}]")

        # 写入 Airtable
        if valid_scripts and not dry_run:
            try:
                written = write_to_airtable(valid_scripts)
                total_written += written
                log(f"📤 已写入 Airtable: {written} 条")
            except Exception as e:
                log(f"❌ Airtable 写入失败: {e}")
                # 保存到本地备份
                backup_path = f"drama_scripts_backup_round{round_num}.json"
                with open(backup_path, "w", encoding="utf-8") as f:
                    json.dump(valid_scripts, f, ensure_ascii=False, indent=2)
                log(f"💾 已备份到本地: {backup_path}")
        else:
            all_scripts.extend(valid_scripts)

        # 限流保护：每轮间隔5秒
        if round_num < rounds:
            log("⏳ 等待 5 秒...")
            time.sleep(5)

    # 总结
    log(f"\n{'='*60}")
    log(f"🏁 批量生成完成")
    log(f"   总轮次: {rounds}")
    log(f"   有效文案: {len(all_titles)} 条")
    if dry_run:
        log(f"   试跑模式，未写入 Airtable")
        # 试跑模式保存到本地
        output_path = "drama_scripts_all.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_scripts, f, ensure_ascii=False, indent=2)
        log(f"   已保存到: {output_path}")
    else:
        log(f"   已写入 Airtable: {total_written} 条")
    log(f"{'='*60}")


if __name__ == "__main__":
    total = 100
    dry_run = False

    if len(sys.argv) > 1:
        try:
            total = int(sys.argv[1])
        except ValueError:
            pass

    if "--dry-run" in sys.argv:
        dry_run = True

    batch_generate(total_count=total, dry_run=dry_run)
