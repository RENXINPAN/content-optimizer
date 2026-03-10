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

LLM_MODEL = "openai/gpt-5.3-chat"
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
- 开头用"这是我听过/见过/读过最xxx的一段话"或"关于xxx有一段话说得特别好"引入（10条中最多用3条这种开头）

风格B「生活感悟型」：
- 从下方【100句开头库】中随机选一句作为开头，10条内不重复
- 描述一个生活瞬间 + 情绪感受 + 一句感悟
- 像一个普通人安静讲述生活

【100句开头库】（每条随机选一句，不要连续用同一类）
顿悟型：后来我才明白一件事 / 长大以后慢慢懂了 / 有些事情真的要很多年才明白 / 人总是在后来才想通 / 有些道理年轻时听不懂 / 很多事情时间久了就懂了 / 有些答案是后来才知道的 / 很多事其实早就有迹象 / 原来很多事情一开始就注定了 / 有些道理是生活教会的
关系型：有些关系其实很安静 / 最舒服的关系大概是这样 / 有些人不常联系却一直记得 / 后来很多朋友慢慢走散了 / 原来关系是会慢慢变淡的 / 有些人只是陪你走一段 / 有些关系不用天天聊天 / 真正重要的人其实不多 / 后来才懂什么叫合适 / 有些人真的只能陪一程
孤独型：有时候会突然觉得很孤独 / 有些孤独只有自己知道 / 夜深的时候最容易想很多 / 有些夜晚特别安静 / 有时候在人群里也会孤单 / 有些情绪只能自己消化 / 很多话后来不再说出口 / 有些路只能一个人走 / 有时候沉默比说话更真实 / 有些夜晚特别长
城市型：有时候走在城市的夜里 / 城市很大人却很小 / 下班的地铁总是很拥挤 / 夜晚的城市灯光很亮 / 有些城市越热闹越孤独 / 有时候会在街上发呆 / 路灯亮着街上人不多 / 有些夜晚适合慢慢走 / 有时候会在路边坐一会
时间型：一转眼很多年过去了 / 时间真的过得很快 / 有些日子再也回不去了 / 很多事情都变了 / 有些人已经很久没见 / 很多回忆停在过去 / 有些夏天再也不会回来 / 原来时间会带走很多人 / 以前的日子已经很远了
成长型：长大其实是一瞬间的事 / 人总是在某一天突然长大 / 有些成长来得很突然 / 原来长大是这样的感觉 / 有些事情只能自己面对 / 有些路只能自己走完 / 很多事情只能慢慢学会 / 人生很多课没有人教 / 有些压力只能自己扛
爱情型：有些感情后来只剩回忆 / 原来有些人真的留不住 / 有些爱只能到这里 / 后来我们没有再见 / 有些喜欢没有结果 / 有些人错过就是一辈子 / 有些感情慢慢就散了 / 有些人只能想一想
感悟型：人生其实没有标准答案 / 有些选择没有对错 / 有些路走着走着就明白了 / 很多事情没有为什么 / 有些事情顺其自然就好 / 很多时候别想太多 / 有些事情不用强求 / 有些日子慢慢过就好
回忆型：有些回忆突然会想起 / 有些画面一直没忘 / 有些人停在记忆里 / 有些瞬间一直记得 / 有些地方再也没去过 / 有些笑容很久没见 / 有些名字已经很远 / 有些日子很怀念
治愈型：有时候生活很简单 / 有些日子其实很温柔 / 有些快乐很普通 / 有些瞬间很治愈 / 有时候慢一点也很好 / 有些日子适合发呆 / 有些风景值得停下 / 有些故事会慢慢变好

每条文案必须 120-160 字（这是硬性要求，低于120字不合格）。自然分成6-8个段落（用\\n\\n分隔段落）。
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


POLISH_PROMPT = """你是一个顶级短视频文案编辑。
下面是一段抖音情绪短视频文案初稿，请你精修润色。

要求：
1. 保持原文主题和情绪不变
2. 字数控制在 130-160 字
3. 每句 6-18 字，口语化，不要文学腔
4. 句子节奏要有呼吸感，短句和稍长句交替
5. 开头第一句要有吸引力
6. 结尾要有一句让人想截图转发的金句
7. 去掉任何鸡汤感、说教感
8. 段落之间用换行分隔

初稿：
{script}

只输出润色后的文案，不要任何解释。"""


def polish_script(script_text, max_retries=2):
    """单条文案润色"""
    prompt = POLISH_PROMPT.format(script=script_text)
    try:
        result = call_llm(prompt, max_retries=max_retries)
        result = result.strip()
        # 去掉可能的引号包裹
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]
        clean = re.sub(r'\s+', '', result)
        if len(clean) < 50:
            return script_text  # 润色结果太短，用原稿
        return result
    except Exception as e:
        log(f"  润色失败，使用原稿: {e}")
        return script_text
        
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
            if wc < 50:
                log(f"  ⚠️ 字数太少({wc}字)，跳过: {title}")
                continue
            if wc > 200:
                log(f"  ⚠️ 字数太多({wc}字)，跳过: {title}")
                continue

            valid_scripts.append({
                "title": title,
                "script": script,
                "emotion": emotion,
            })
            all_titles.append(title)

        log(f"✅ 本轮有效文案: {len(valid_scripts)}/{len(scripts)}")

        # 逐条润色
        if valid_scripts:
            log(f"✨ 开始润色 {len(valid_scripts)} 条文案...")
            for j, s in enumerate(valid_scripts):
                log(f"  润色 {j+1}/{len(valid_scripts)}: {s['title']}")
                original_wc = len(re.sub(r'\s+', '', s['script']))
                s['script'] = polish_script(s['script'])
                polished_wc = len(re.sub(r'\s+', '', s['script']))
                log(f"  ✅ {original_wc}字 → {polished_wc}字")
                time.sleep(2)  # 限流保护

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
