"""
hot_topics.py — 抓取微博热搜和今日头条热榜
用于生成文章时提供热点参考
失败不影响正常生成，返回空字符串即可
"""

import requests
import json


def get_weibo_hot(limit=20) -> list:
    """获取微博热搜前N条"""
    apis = [
        "https://api.aa1.cn/api/weibo-rs",
        "https://weibo-hot-search.vercel.app/data",
    ]

    for api_url in apis:
        try:
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # 不同API返回格式不同，尝试多种解析方式
                topics = []

                if isinstance(data, list):
                    for item in data[:limit]:
                        title = item.get("title") or item.get("word") or item.get("hostWord", [""])[0]
                        if title:
                            topics.append(title)
                elif isinstance(data, dict):
                    items = data.get("data", [])
                    if isinstance(items, list):
                        for item in items[:limit]:
                            if isinstance(item, dict):
                                title = item.get("title") or item.get("word") or item.get("hostWord", [""])[0]
                            elif isinstance(item, str):
                                title = item
                            else:
                                continue
                            if title:
                                topics.append(title)

                if topics:
                    return topics
        except Exception as e:
            print(f"  ⚠️ 微博热搜API({api_url})失败: {e}")
            continue

    return []


def get_toutiao_hot(limit=20) -> list:
    """获取今日头条热榜前N条"""
    apis = [
        "https://api.aa1.cn/api/toutiao-rs",
        "https://www.coderutil.com/api/resou/v1/toutiao",
    ]

    for api_url in apis:
        try:
            resp = requests.get(api_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                topics = []

                if isinstance(data, list):
                    for item in data[:limit]:
                        title = item.get("title") or item.get("word") or ""
                        if title:
                            topics.append(title)
                elif isinstance(data, dict):
                    items = data.get("data", [])
                    if isinstance(items, list):
                        for item in items[:limit]:
                            if isinstance(item, dict):
                                title = item.get("title") or item.get("word") or ""
                            elif isinstance(item, str):
                                title = item
                            else:
                                continue
                            if title:
                                topics.append(title)

                if topics:
                    return topics
        except Exception as e:
            print(f"  ⚠️ 头条热榜API({api_url})失败: {e}")
            continue

    return []


def get_hot_topics_text(limit=10) -> str:
    """获取热点话题，格式化为文本，供Prompt使用"""
    weibo = get_weibo_hot(limit)
    toutiao = get_toutiao_hot(limit)

    if not weibo and not toutiao:
        return "（今日热点获取失败，请自由选题）"

    lines = []
    if weibo:
        lines.append("微博热搜：")
        for i, topic in enumerate(weibo[:limit], 1):
            lines.append(f"  {i}. {topic}")

    if toutiao:
        lines.append("今日头条热榜：")
        for i, topic in enumerate(toutiao[:limit], 1):
            lines.append(f"  {i}. {topic}")

    return "\n".join(lines)


if __name__ == "__main__":
    # 测试
    print("=== 微博热搜 ===")
    for t in get_weibo_hot(10):
        print(f"  {t}")
    print("\n=== 今日头条 ===")
    for t in get_toutiao_hot(10):
        print(f"  {t}")
