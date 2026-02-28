# crawler.py - 公众号历史文章抓取 + 自动喂入进化引擎
from airtable import AirtableClient
from html.parser import HTMLParser
import re
import os
import time
import requests
import warnings
warnings.filterwarnings('ignore')

from ingestion import ArticleIngestion
from evolution import EvolutionEngine
from prompt_builder import PromptBuilder

WXAPI_KEY = os.environ.get("WXAPI_KEY")
BASE_URL = "https://www.dajiala.com/fbmain/monitor/v3"

TARGET_ACCOUNTS = [
    "刘润",
    "S叔Spenser",
    "武志红",
    "半佛仙人",
]

def get_article_list(account_name: str, page: int = 1) -> list:
    url = f"{BASE_URL}/post_history"
    payload = {"key": WXAPI_KEY, "name": account_name, "page": page}
    try:
        resp = requests.post(url, json=payload, timeout=15, verify=False)
        data = resp.json()
        if data.get("code") == 0:
            return data.get("data", [])
        else:
            print(f"  ⚠️  列表获取失败：{data.get('msg', '')}")
            return []
    except Exception as e:
        print(f"  ⚠️  请求异常：{e}")
        return []

def get_article_detail(article_url: str) -> dict:
    url = f"{BASE_URL}/article_detail"
    payload = {"key": WXAPI_KEY, "url": article_url}
    try:
        resp = requests.post(url, json=payload, timeout=20, verify=False)
        data = resp.json()
        if data.get("code") == 0:
            return data
        else:
            print(f"  ⚠️  详情获取失败：{data.get('msg', '')}")
            return {}
    except Exception as e:
        print(f"  ⚠️  详情请求异常：{e}")
        return {}

def extract_content(detail: dict) -> str:
    for key in ["content", "text", "body", "article_content", "html"]:
        val = detail.get(key, "")
        if val and isinstance(val, str) and len(val) > 100:
            # 去掉style标签和内容
            clean = re.sub(r'<style[^>]*>.*?</style>', '', val, flags=re.DOTALL)
            # 去掉script标签
            clean = re.sub(r'<script[^>]*>.*?</script>', '', clean, flags=re.DOTALL)
            # 去掉所有HTML标签
            clean = re.sub(r'<[^>]+>', '', clean)
            # 清理HTML实体
            clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
            # 清理多余空白
            clean = re.sub(r'\s+', ' ', clean).strip()
            return clean
    print(f"  🔍 详情字段：{list(detail.keys())}")
    return ""

def crawl_account(account_name: str, max_articles: int = 50):
    print(f"\n📡 开始抓取：{account_name}")
    ingestion = ArticleIngestion()
    count = 0
    page = 1

    while count < max_articles:
        print(f"  第{page}页...")
        articles = get_article_list(account_name, page)
        if not articles:
            print(f"  第{page}页无数据，停止")
            break

        for article in articles:
            if count >= max_articles:
                break
            
            title = article.get("title", "")
            article_url = article.get("url", "")
            
            # 跳过广告/日历卡片类文章
            if not title or not article_url:
                continue
            if any(x in title for x in ["日历卡片", "润米商城", "速览"]):
                continue
            # 只抓原创文章（original=1）
            if article.get("original", 0) != 1:
                continue

            print(f"  📄 {title[:35]}...")
            # URL去重检查
            try:
                existing = db._request("GET", "articles", params={"filterByFormula": f'{{url}}="{article_url}"'})
                if existing.get("records"):
                    print(f"  ⏭️  已存在，跳过")
                    continue
            except Exception:
                pass

            detail = get_article_detail(article_url)
            content = extract_content(detail)

            if not content:
                continue
            
            if len(content) < 50:
                print(f"  ⚠️  正文太短({len(content)}字)，跳过")
                continue

            try:
                ingestion.ingest(
    title=title,
    content=content,
    source=f"{account_name}",
    url=article_url
)
                count += 1
                print(f"  ✅ 已入库（{count}/{max_articles}）")
            except Exception as e:
                print(f"  ⚠️  入库失败：{e}")

            time.sleep(0.8)

        page += 1
        if page > 20:  # 最多翻20页防止无限循环
            break
        time.sleep(1)

    print(f"✅ {account_name} 完成，共入库{count}篇")
    return count

def crawl_all(max_articles_per_account: int = 50):
    print(f"\n{'='*50}")
    print(f"🚀 开始批量抓取爆款文章")
    print(f"目标账号：{', '.join(TARGET_ACCOUNTS)}")
    print(f"每个账号最多：{max_articles_per_account}篇")
    print(f"{'='*50}")

    total = 0
    for account in TARGET_ACCOUNTS:
        count = crawl_account(account, max_articles=max_articles_per_account)
        total += count
        time.sleep(2)

    print(f"\n🎉 全部完成！共入库{total}篇文章")

    if total >= 5:
        print(f"\n🧬 触发进化引擎...")
        try:
            engine = EvolutionEngine()
            for layer in ["短期", "中期", "长期"]:
                engine.run_evolution(layer)
            builder = PromptBuilder()
            builder.save_new_version(f"批量抓取{total}篇文章后触发进化")
            print("✅ 进化完成！Prompt已更新")
        except Exception as e:
            print(f"⚠️  进化出错：{e}")

    return total

if __name__ == "__main__":
    import sys
    max_articles = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    crawl_all(max_articles_per_account=max_articles)
