# main.py - 主流程调度器

import os
import sys
import json
import requests
from datetime import datetime
from airtable import AirtableClient
from ingestion import ArticleIngestion
from evolution import EvolutionEngine
from prompt_builder import PromptBuilder
from feedback import FeedbackProcessor
from memory import MemoryManager


def generate_daily_content():
    """每日内容生成主流程"""
    print(f"\n{'='*50}")
    print(f"🚀 每日内容生成 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    db = AirtableClient()
    builder = PromptBuilder()
    qwen_key = os.environ.get("QWEN_API_KEY")

    # 1. 获取当前最优Prompt
    current_prompt_record = db.get_current_prompt()
    if current_prompt_record:
        prompt = current_prompt_record["fields"]["Prompt内容"]
        version = current_prompt_record["fields"]["版本号"]
        print(f"📋 使用Prompt版本：{version}")
    else:
        print("📋 首次运行，构建初始Prompt...")
        prompt, _ = builder.build_prompt()
        version = "v_init"

    # 2. 调用千问生成内容
    print("🤖 调用千问生成内容...")
    try:
        resp = requests.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {qwen_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "qwen-plus",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        content = resp.json()["choices"][0]["message"]["content"]
        print("✅ 内容生成成功")
    except Exception as e:
        print(f"❌ 千问调用失败：{e}")
        return

    # 3. 解析生成内容
    title, body, cover = parse_generated_content(content)
    print(f"📝 标题：{title}")

    # 4. 存入Airtable内容库
    record_id = db.save_generated_content(
        title=title,
        content=body,
        prompt_version=version,
        predicted_score=0
    )
    print(f"💾 已存入Airtable：{record_id}")

    # 5. 推送到Coze（发送给你手机预览）
    push_to_coze(title, body, cover, record_id)

    print(f"\n✅ 今日内容生成完成！请在微信公众号查看预览。")
    return record_id


def parse_generated_content(content: str) -> tuple:
    """解析千问返回的内容"""
    import re
    title = re.search(r'【标题】\s*(.+?)(?:\n|【)', content + '【')
    body_match = re.search(r'【正文】\s*(.*?)(?=【封面文字】|$)', content, re.DOTALL)
    cover = re.search(r'【封面文字】\s*(.+?)(?:\n|$)', content)

    title = title.group(1).strip() if title else "今日内容"
    body = body_match.group(1).strip() if body_match else content
    cover_text = cover.group(1).strip() if cover else "点击阅读"

    return title, body, cover_text


def push_to_coze(title: str, body: str, cover: str, record_id: str):
    """推送内容到Coze，触发微信通知"""
    coze_token = os.environ.get("COZE_API_TOKEN")
    coze_bot_id = os.environ.get("COZE_BOT_ID")
    coze_user_id = os.environ.get("COZE_USER_ID")

    if not all([coze_token, coze_bot_id, coze_user_id]):
        print("⚠️  Coze配置不完整，跳过推送")
        return

    message = f"""📝 今日内容已生成，请审核：

【标题】{title}

【封面文字】{cover}

【正文预览】
{body[:300]}...

（完整内容已存入Airtable）
记录ID：{record_id}

回复「通过」保存，或直接告诉我需要修改的地方 ✍️"""

    try:
        resp = requests.post(
            "https://api.coze.cn/v3/chat",
            headers={
                "Authorization": f"Bearer {coze_token}",
                "Content-Type": "application/json"
            },
            json={
                "bot_id": coze_bot_id,
                "user_id": coze_user_id,
                "stream": False,
                "auto_save_history": True,
                "additional_messages": [
                    {"role": "user", "content": message, "content_type": "text"}
                ]
            },
            timeout=30
        )
        if resp.status_code == 200:
            print("📱 已推送到Coze，请查看微信")
        else:
            print(f"⚠️  Coze推送失败：{resp.status_code}")
    except Exception as e:
        print(f"⚠️  Coze推送异常：{e}")


def run_weekly_evolution():
    """每周进化流程"""
    print(f"\n{'='*50}")
    print(f"🧬 每周进化 - {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*50}")

    engine = EvolutionEngine()
    builder = PromptBuilder()

    # 三层进化
    for layer in ["短期", "中期", "长期"]:
        engine.run_evolution(layer)

    # 构建新版本Prompt
    builder.save_new_version("每周定期进化")
    print("✅ 每周进化完成！")


def ingest_article(title: str, content: str):
    """摄入单篇文章"""
    ingestion = ArticleIngestion()
    record_id = ingestion.ingest(title, content)
    print(f"✅ 文章已入库：{record_id}")

    # 检查是否需要触发局部进化
    memory = MemoryManager()
    should_evolve, reason = memory.should_evolve()
    if should_evolve:
        print(f"🧬 {reason}")
        engine = EvolutionEngine()
        engine.run_evolution("短期")
        builder = PromptBuilder()
        builder.save_new_version(f"新文章摄入触发：{reason}")

    return record_id


def process_weekly_feedback(feedback_text: str):
    """处理每周数据回流"""
    processor = FeedbackProcessor()
    feedback_list_raw = processor.parse_wechat_feedback(feedback_text)

    if not feedback_list_raw:
        print("⚠️  未能解析到有效数据，请检查格式")
        return

    # 需要匹配Airtable中的record_id
    db = AirtableClient()
    feedback_list = []
    for item in feedback_list_raw:
        # 通过标题查找record_id
        params = {"filterByFormula": f'{{标题}} = "{item["title"]}"'}
        try:
            result = db._request("GET", "contents", params=params)
            records = result.get("records", [])
            if records:
                item["record_id"] = records[0]["id"]
                feedback_list.append(item)
            else:
                print(f"⚠️  未找到文章：{item['title']}")
        except:
            pass

    if feedback_list:
        processor.batch_feedback(feedback_list)


# ==================== 命令行入口 ====================

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "help"

    if command == "generate":
        # GitHub Actions每日触发
        generate_daily_content()

    elif command == "evolve":
        # GitHub Actions每周触发
        run_weekly_evolution()

    elif command == "ingest":
        # 手动摄入文章：python main.py ingest "标题" "正文内容"
        if len(sys.argv) >= 4:
            ingest_article(sys.argv[2], sys.argv[3])
        else:
            print("用法：python main.py ingest '文章标题' '文章正文'")

    elif command == "feedback":
        # 处理数据回流：python main.py feedback "反馈文本"
        if len(sys.argv) >= 3:
            process_weekly_feedback(sys.argv[2])
        else:
            print("用法：python main.py feedback '文章1：《标题》阅读1000 点赞20...'")

    else:
        print("""
内容进化引擎 - 使用说明

命令：
  python main.py generate   每日内容生成（GitHub Actions自动触发）
  python main.py evolve     每周进化（GitHub Actions自动触发）
  python main.py ingest     摄入新爆款文章
  python main.py feedback   处理效果数据回流
        """)
