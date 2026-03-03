"""
review.py — AI审核 + 自动重写重审 + Server酱通知
审核不通过时自动重写，最多3轮
"""
import os
import json
import time
import requests
from datetime import datetime
from airtable import AirtableClient

MAX_REWRITE_ROUNDS = 3


def call_coze_bot(bot_id, message, timeout=60):
    token = os.environ.get("COZE_API_TOKEN")
    if not token:
        return None, "COZE_API_TOKEN未配置"

    url = "https://api.coze.cn/v3/chat"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "bot_id": bot_id,
        "user_id": "review_system",
        "stream": True,
        "auto_save_history": False,
        "additional_messages": [
            {"role": "user", "content": message, "content_type": "text"}
        ]
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=90, stream=True)
        resp.raise_for_status()

        all_events = []
        resp.encoding = "utf-8"
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("event:"):
                continue
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                event = json.loads(data_str)
                if isinstance(event, dict):
                    all_events.append(event)
                else:
                    print(f"  DEBUG 非dict event: {type(event)} {str(event)[:100]}")
            except json.JSONDecodeError:
                continue

        resp.close()

        # 从所有event中找到type=answer的，取最后一条完整内容
        # Coze流式模式：conversation.message.completed 事件包含完整内容
        answer = ""
        for event in all_events:
            if event.get("role") == "assistant" and event.get("type") == "answer":
                content = event.get("content", "")
                if content:
                    answer += content  # 拼接，不是覆盖

        if answer:
            return answer, None

        # 如果没找到，打印所有event供调试
        print(f"  DEBUG 共{len(all_events)}个event")
        for i, e in enumerate(all_events):
            print(f"  DEBUG event[{i}]: role={e.get('role','')} type={e.get('type','')} content=[{str(e.get('content',''))[:100]}] status={e.get('status','')}")

        return None, f"流式响应中未找到回复, 共{len(all_events)}个event"

    except Exception as e:
        return None, str(e)


def parse_json_response(text):
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        clean = clean.rsplit("```", 1)[0]
    try:
        return json.loads(clean.strip()), None
    except json.JSONDecodeError as e:
        return None, f"JSON解析失败: {e}, 原文: {text[:200]}"


def review_content(title, content):
    bot_id = os.environ.get("COZE_BOT_ID")
    if not bot_id:
        return {"score": 0, "passed": False, "review_notes": "COZE_BOT_ID未配置"}

    message = f"审核\n\n标题：{title}\n\n正文：\n{content[:3000]}"
    reply, error = call_coze_bot(bot_id, message)

    print(f"  DEBUG reply={repr(reply)[:200]}")
    print(f"  DEBUG error={repr(error)[:200]}")

    if error:
        return {"score": 0, "passed": False, "review_notes": f"审核调用失败: {error}"}

    result, parse_error = parse_json_response(reply)
    if parse_error:
        return {"score": 0, "passed": False, "review_notes": parse_error}

    if not isinstance(result, dict):
        return {"score": 0, "passed": False, "review_notes": f"审核返回非dict: {type(result)} {str(result)[:200]}"}

    return result


def rewrite_content(title, content, review_notes):
    api_key = os.environ.get("QWEN_API_KEY")
    if not api_key:
        return None, None, "QWEN_API_KEY未配置"

    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    prompt = f"""你是一个专业的公众号写手。以下文章审核未通过，请根据审核意见进行修改。

【审核意见】
{review_notes}

【原标题】
{title}

【原文】
{content[:3000]}

【要求】
1. 根据审核意见针对性修改，保留原文优点
2. 保持口语化、有节奏感的写作风格
3. 确保金句密度（每300字至少1个可传播短句）
4. 标题如果需要优化也一并修改

请按以下格式返回（只返回JSON，不要其他内容）：
{{"title": "修改后的标题", "content": "修改后的正文"}}"""

    payload = {
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        reply = data["choices"][0]["message"]["content"]

        result, parse_error = parse_json_response(reply)
        if parse_error:
            return None, None, parse_error

        return result.get("title", title), result.get("content", content), None

    except Exception as e:
        return None, None, str(e)


def notify_wechat(title, desp):
    key = os.environ.get("SERVERCHAN_KEY")
    if not key:
        print("WARNING: SERVERCHAN_KEY未配置，跳过通知")
        return
    try:
        resp = requests.post(
            f"https://sctapi.ftqq.com/{key}.send",
            data={"title": title[:100], "desp": desp},
            timeout=10
        )
        print(f"Server酱推送: {resp.status_code}")
    except Exception as e:
        print(f"Server酱失败: {e}")


def run_review():
    at = AirtableClient()
    records = at.get_records("contents", filter_formula='{status}="待审核"')

    if not records:
        print("没有待审核内容")
        return

    all_results = []

    for record in records:
        record_id = record["id"]
        fields = record.get("fields", {})
        title = fields.get("标题", "无标题")
        content = fields.get("正文", "")
        current_round = fields.get("review_round", 0)

        print(f"\n{'='*50}")
        print(f"审核: {title}")
        print(f"当前轮次: {current_round}")

        for round_num in range(current_round, MAX_REWRITE_ROUNDS + 1):
            print(f"\n  第 {round_num + 1} 轮审核...")
            review = review_content(title, content)
            score = review.get("score", 0)
            passed = review.get("passed", False)
            notes = review.get("review_notes", "")

            print(f"  评分: {score}, 通过: {passed}")
            print(f"  意见: {notes[:100]}")

            if passed:
                at.update_record("contents", record_id, {
                    "标题": title,
                    "正文": content,
                    "status": "已通过",
                    "score": score,
                    "review_notes": notes,
                    "review_round": round_num + 1,
                })
                all_results.append({
                    "title": title,
                    "score": score,
                    "status": "已通过",
                    "rounds": round_num + 1,
                    "notes": notes,
                    "content_preview": content[:200],
                })
                break

            elif round_num < MAX_REWRITE_ROUNDS:
                print(f"  → 自动重写 (第{round_num + 1}次)...")
                new_title, new_content, rewrite_error = rewrite_content(
                    title, content, notes
                )
                if rewrite_error:
                    print(f"  重写失败: {rewrite_error}")
                    at.update_record("contents", record_id, {
                        "status": "需修改",
                        "score": score,
                        "review_notes": f"第{round_num+1}轮审核未通过，自动重写失败: {rewrite_error}\n原审核意见: {notes}",
                        "review_round": round_num + 1,
                    })
                    all_results.append({
                        "title": title,
                        "score": score,
                        "status": "需修改（重写失败）",
                        "rounds": round_num + 1,
                        "notes": notes,
                    })
                    break
                else:
                    title = new_title
                    content = new_content
                    print(f"  重写完成，新标题: {title}")
                    time.sleep(2)

            else:
                at.update_record("contents", record_id, {
                    "标题": title,
                    "正文": content,
                    "status": "需修改",
                    "score": score,
                    "review_notes": f"经过{MAX_REWRITE_ROUNDS}轮自动重写仍未通过(最高{score}分)。\n最后意见: {notes}",
                    "review_round": round_num + 1,
                })
                all_results.append({
                    "title": title,
                    "score": score,
                    "status": f"需修改（{MAX_REWRITE_ROUNDS}轮后仍未通过）",
                    "rounds": round_num + 1,
                    "notes": notes,
                })

    if all_results:
        passed_count = sum(1 for r in all_results if r["status"] == "已通过")
        total = len(all_results)

        notify_title = f"审核完成: {passed_count}/{total}篇通过"

        desp = "## 今日内容审核报告\n\n"
        for r in all_results:
            if r["status"] == "已通过":
                desp += f"### ✅ {r['title']}\n"
                desp += f"- 评分: **{r['score']}分**\n"
                desp += f"- 轮次: 第{r['rounds']}轮通过\n"
                desp += f"- 意见: {r['notes']}\n"
                desp += f"- 预览: {r.get('content_preview', '')}\n\n"
                desp += "---\n\n"
            else:
                desp += f"### ❌ {r['title']}\n"
                desp += f"- 评分: **{r['score']}分**\n"
                desp += f"- 状态: {r['status']}\n"
                desp += f"- 意见: {r['notes']}\n\n"
                desp += "---\n\n"

        notify_wechat(notify_title, desp)


if __name__ == "__main__":
    run_review()
