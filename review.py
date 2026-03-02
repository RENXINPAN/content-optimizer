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

MAX_REWRITE_ROUNDS = 3  # 最多重写次数


# ============================================================
# Coze API 调用
# ============================================================

def call_coze_bot(bot_id, message, timeout=60):
    """
    通用Coze Bot API调用
    返回Bot的文本回复
    """
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
        "stream": False,
        "auto_save_history": False,
        "additional_messages": [
            {"role": "user", "content": message, "content_type": "text"}
        ]
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        chat_id = data.get("data", {}).get("id")
        conversation_id = data.get("data", {}).get("conversation_id")
        if not chat_id:
            return None, f"API调用失败: {data}"

        # 轮询等待结果
        for _ in range(timeout):
            time.sleep(1)
            check_resp = requests.get(
                "https://api.coze.cn/v3/chat/retrieve",
                headers=headers,
                params={"chat_id": chat_id, "conversation_id": conversation_id}
            )
            check_data = check_resp.json()
            status = check_data.get("data", {}).get("status")

            if status == "completed":
                msg_resp = requests.get(
                    "https://api.coze.cn/v3/chat/message/list",
                    headers=headers,
                    params={"chat_id": chat_id, "conversation_id": conversation_id}
                )
                messages = msg_resp.json().get("data", [])
                for msg in messages:
                    if msg.get("role") == "assistant" and msg.get("type") == "answer":
                        return msg.get("content", ""), None
                return None, "未找到回复内容"
            elif status == "failed":
                return None, "Coze处理失败"

        return None, "超时"

    except Exception as e:
        return None, str(e)


def parse_json_response(text):
    """从Bot回复中提取JSON"""
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        clean = clean.rsplit("```", 1)[0]
    try:
        return json.loads(clean.strip()), None
    except json.JSONDecodeError as e:
        return None, f"JSON解析失败: {e}, 原文: {text[:200]}"


# ============================================================
# 审核
# ============================================================

def review_content(title, content):
    """调用审核Bot，返回审核结果dict"""
    bot_id = os.environ.get("COZE_BOT_ID")
    if not bot_id:
        return {"score": 0, "passed": False, "review_notes": "COZE_BOT_ID未配置"}

    message = f"审核\n\n标题：{title}\n\n正文：\n{content[:3000]}"
    reply, error = call_coze_bot(bot_id, message)

    if error:
        return {"score": 0, "passed": False, "review_notes": f"审核调用失败: {error}"}

    result, parse_error = parse_json_response(reply)
    if parse_error:
        return {"score": 0, "passed": False, "review_notes": parse_error}

    return result


# ============================================================
# 重写
# ============================================================

def rewrite_content(title, content, review_notes):
    """
    调用通义千问根据审核意见重写文章
    用的是已有的QWEN_API_KEY，不额外增加依赖
    """
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


# ============================================================
# Server酱通知
# ============================================================

def notify_wechat(title, desp):
    """Server酱推送到微信"""
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


# ============================================================
# 主流程：审核 + 自动重写循环
# ============================================================

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
        content = fields.get("内容", "")
        current_round = fields.get("review_round", 0)

        print(f"\n{'='*50}")
        print(f"审核: {title}")
        print(f"当前轮次: {current_round}")

        # ---- 审核+重写循环 ----
        for round_num in range(current_round, MAX_REWRITE_ROUNDS + 1):
            print(f"\n  第 {round_num + 1} 轮审核...")
            review = review_content(title, content)
            score = review.get("score", 0)
            passed = review.get("passed", False)
            notes = review.get("review_notes", "")

            print(f"  评分: {score}, 通过: {passed}")
            print(f"  意见: {notes[:100]}")

            if passed:
                # 审核通过 → 更新Airtable
                at.update_record("contents", record_id, {
                    "标题": title,
                    "内容": content,
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
                # 未通过且还有重写次数 → 自动重写
                print(f"  → 自动重写 (第{round_num + 1}次)...")
                new_title, new_content, rewrite_error = rewrite_content(
                    title, content, notes
                )
                if rewrite_error:
                    print(f"  重写失败: {rewrite_error}")
                    # 重写失败，标记需修改，退出循环
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
                    # 短暂等待，避免API限流
                    time.sleep(2)

            else:
                # 超过最大重写次数
                at.update_record("contents", record_id, {
                    "标题": title,
                    "内容": content,
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

    # ---- 汇总通知 ----
    if all_results:
        passed_count = sum(1 for r in all_results if r["status"] == "已通过")
        total = len(all_results)

        notify_title = f"审核完成: {passed_count}/{total}篇通过"

        desp = "## 📋 今日内容审核报告\n\n"
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
