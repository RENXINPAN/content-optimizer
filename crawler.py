# crawler.py - 公众号历史文章抓取 + 自动喂入进化引擎

import os
import time
import requests
from ingestion import ArticleIngestion
from memory import MemoryManager
from evolution import EvolutionEngine
from prompt_builder import PromptBuilder

WXAPI_KEY = os.environ.get("WXAPI_KEY")
BASE_URL = "https://www.dajiala.com/fbmain/monitor/v3"

# 目标公众号列表
TARGET_ACCOUNTS = [
    "刘润",      # 刘润
    "S叔Spenser",       # S叔Spenser  
    "武志红",        # 武志红
    "半佛仙人",      # 半佛仙人
]

def get_article_list(account_name: str, page: int = 1) -> list:
    url = f"{BASE_URL}/post_history"
    payload = {
        "key": WXAPI_KEY,
        "name": account_name,
        "page": page
    }
    try:
        resp = requests.post(url, json=payload, timeout=15, verify=False)
        data = resp.json()
        if data.get("code") == 200:
            return data.get("data", {}).get("list", [])
        else:
            print(f"⚠️  {account_name} 获取失败：{data.get('msg', '')}")
            return []
    except Exception as e:
        print(f"⚠️  {account_name} 请求异常：{e}")
        return []

def get_article_detail(article_url: str) -> str:
    url = f"{BASE_URL}/article_detail"
    payload = {
        "key": WXAPI_KEY,
        "url": article_url
    }
    try:
        resp = requests.post(url, json=payload, timeout=15, verify=False)
        data = resp.json()
        if data.get("code") == 200:
            return data.get("data", {}).get("content", "")
        else:
            print(f"⚠️  详情获取失败：{data.get('msg', '')}")
            return ""
    except Exception as e:
        print(f"⚠️  详情请求异常：{e}")
        return ""

def crawl_account(account_name: str, max_pages: int = 5, max_articles: int = 50):
    """
    抓取单个公众号的历史文章
    max_pages: 最多抓几页（每页约10篇）
    max_articles: 最多抓多少篇
    """
    print(f"\n📡 开始抓取：{account_name}")
    ingestion = ArticleIngestion()
    count = 0

    for page in range(1, max_pages + 1):
        print(f"  第{page}页...")
        articles = get_article_list(account_name, page)

        if not articles:
            print(f"  第{page}页无数据，停止")
            break

        for article in articles:
            if count >= max_articles:
                break

            title = article.get("title", "")
            article_url = article.get("url", "") or article.get("link", "")

            if not title or not article_url:
                continue

            print(f"  📄 {title[:30]}...")

            # 获取正文
            content = get_article_detail(article_url)
            if not content or len(content) < 200:
                print(f"  ⚠️  正文太短，跳过")
                continue

            # 喂入进化引擎
            try:
                ingestion.ingest(
                    title=title,
                    content=content,
                    source=f"{account_name}_历史文章"
                )
                count += 1
                print(f"  ✅ 已入库（{count}/{max_articles}）")
            except Exception as e:
                print(f"  ⚠️  入库失败：{e}")

            # 避免请求太频繁
            time.sleep(0.5)

        if count >= max_articles:
            break

        time.sleep(1)

    print(f"✅ {account_name} 抓取完成，共入库{count}篇")
    return count

def crawl_all(max_articles_per_account: int = 50):
    """抓取所有目标公众号"""
    print(f"\n{'='*50}")
    print(f"🚀 开始批量抓取爆款文章")
    print(f"目标账号：{', '.join(TARGET_ACCOUNTS)}")
    print(f"每个账号最多：{max_articles_per_account}篇")
    print(f"{'='*50}")

    total = 0
    for account in TARGET_ACCOUNTS:
        count = crawl_account(account, max_articles=max_articles_per_account)
        total += count
        time.sleep(2)  # 账号之间间隔2秒

    print(f"\n🎉 全部抓取完成！共入库{total}篇文章")

    # 抓取完成后触发进化
    if total >= 5:
        print(f"\n🧬 文章数量充足，开始触发进化引擎...")
        try:
            engine = EvolutionEngine()
            for layer in ["短期", "中期", "长期"]:
                engine.run_evolution(layer)

            builder = PromptBuilder()
            builder.save_new_version(f"批量抓取{total}篇文章后触发进化")
            print("✅ 进化完成！Prompt已更新")
        except Exception as e:
            print(f"⚠️  进化过程出错：{e}")
    else:
        print(f"⚠️  入库文章少于5篇，暂不触发进化")

    return total

if __name__ == "__main__":
    import sys
    # 支持命令行参数指定每个账号抓取数量
    max_articles = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    crawl_all(max_articles_per_account=max_articles)
