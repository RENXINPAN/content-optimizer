"""
extract_title_patterns.py — 从爆款文章库提炼标题结构库
分析2100+篇文章标题，提取：
1. 标题结构模板（如"很多人不知道…""我观察了…"）
2. 高频主题关键词（如副业、职场、赚钱、认知）
3. 情绪类型（焦虑、反转、信息差、认知升级）

产出：存入Airtable的prompts表（状态=选题手册）+ 本地备份

用法：
  python extract_title_patterns.py
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from airtable import AirtableClient


BATCH_SIZE = 100  # 标题很短，每批可以多放一些
BATCH_DELAY = 3


def call_model(prompt, max_tokens=4000):
    """调用Claude via OpenRouter"""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY未配置")
        return None

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json; charset=utf-8"
            },
            json={
                "model": "anthropic/claude-sonnet-4.6",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.2,
            },
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  模型调用失败: {e}")
        return None


def get_all_titles():
    """从Airtable获取所有文章标题"""
    print("正在获取所有文章标题...", flush=True)
    db = AirtableClient()
    all_records = []
    offset = None

    while True:
        params = {
            "pageSize": 100,
            "fields[]": "标题",
        }
        if offset:
            params["offset"] = offset

        result = db._request("GET", "爆款文章库", params=params)
        records = result.get("records", [])
        all_records.extend(records)
        offset = result.get("offset")

        if not offset:
            break

    titles = [
        r.get("fields", {}).get("标题", "").strip()
        for r in all_records
        if r.get("fields", {}).get("标题", "").strip()
    ]

    print(f"共获取 {len(titles)} 个标题", flush=True)
    return titles


BATCH_ANALYZE_PROMPT = """你是一个资深的公众号运营专家，擅长分析爆款标题的规律。

以下是{count}个公众号爆款文章的标题。请从中分析以下三个维度：

【1. 标题结构模板】
提取出这些标题中反复出现的句式结构，用"___"代替具体内容。
例如：
- "为什么___的人，反而___"
- "我花了___年才明白，___"
- "___：普通人最大的误区"
- "很多人不知道，___其实___"
请提取15-20个最常见的结构模板。

【2. 高频主题关键词】
这些标题中反复出现的主题词是什么？
按频率从高到低列出20-30个关键词，每个标注大概出现了多少次。
例如：赚钱(47次)、职场(35次)、认知(28次)...

【3. 情绪类型分布】
这些标题主要在调动什么情绪？请归类并统计比例。
例如：
- 焦虑/恐惧型（"你还不知道就晚了"）：占比约30%
- 反常识/颠覆型（"其实你一直搞反了"）：占比约25%
- 信息差型（"90%的人不知道"）：占比约20%
- 好奇/悬念型（"他说了一句话，我愣住了"）：占比约15%
- 认同/共鸣型（"看完才发现，说的就是我"）：占比约10%

请用具体的标题举例说明每个维度。

--- 以下是标题列表 ---
{titles}
"""


SUMMARY_PROMPT = """你是一个资深公众号运营专家。以下是多批次的标题分析结果，请汇总成一份完整的「爆款选题手册」。

要求：
1. 去重合并，保留最有代表性的
2. 总字数控制在3000-5000字
3. 格式清晰，方便直接作为选题参考

最终手册应包含以下三个部分：

【第一部分：标题结构模板库】
汇总出25-30个最有效的标题结构模板，按效果分级：
- S级（几乎必爆的结构）：5-8个
- A级（高概率爆的结构）：8-10个
- B级（稳定有效的结构）：10-12个
每个模板给出2个具体示例。

【第二部分：高频关键词库】
按主题分类整理，每类列出关键词：
- 赚钱/财富类：...
- 职场/成长类：...
- 认知/思维类：...
- 情感/关系类：...
- 生活方式类：...
- 社会观察类：...

【第三部分：情绪触发类型】
列出6-8种最有效的情绪触发类型，每种给出：
- 定义（一句话说清楚）
- 为什么有效（读者心理）
- 标题公式（2-3个）
- 适合搭配的关键词

--- 以下是多批次分析结果 ---
{batch_results}
"""


def extract_title_patterns():
    """主流程"""
    print("🚀 开始提炼爆款标题结构库", flush=True)

    # 1. 获取所有标题
    titles = get_all_titles()
    if not titles:
        print("❌ 没有获取到标题")
        return

    # 2. 分批分析
    batches = [titles[i:i+BATCH_SIZE] for i in range(0, len(titles), BATCH_SIZE)]
    # 最多处理25批（2500个标题）
    batches = batches[:25]

    print(f"共 {len(titles)} 个标题，分 {len(batches)} 批处理", flush=True)

    batch_results = []
    for i, batch in enumerate(batches):
        print(f"📖 第{i+1}/{len(batches)}批 ({len(batch)}个标题)...", flush=True)

        titles_text = "\n".join([f"{j+1}. {t}" for j, t in enumerate(batch)])

        prompt = BATCH_ANALYZE_PROMPT.format(
            count=len(batch),
            titles=titles_text
        )

        result = call_model(prompt)
        if result:
            batch_results.append(result)
            print(f"  ✅ 分析完成 ({len(result)}字)", flush=True)
        else:
            print(f"  ❌ 分析失败", flush=True)

        time.sleep(BATCH_DELAY)

    if not batch_results:
        print("❌ 所有批次都失败了")
        return

    # 3. 汇总
    print(f"\n📝 汇总 {len(batch_results)} 批结果...", flush=True)

    combined = "\n\n".join([
        f"--- 第{i+1}批分析 ---\n{result}"
        for i, result in enumerate(batch_results)
    ])

    final = call_model(
        SUMMARY_PROMPT.format(batch_results=combined),
        max_tokens=6000
    )

    if not final:
        print("❌ 汇总失败")
        return

    print(f"✅ 选题手册生成完成 ({len(final)}字)", flush=True)

    # 4. 保存到Airtable
    db = AirtableClient()
    version = f"title_patterns_{datetime.now().strftime('%Y%m%d')}"

    # 检查是否已存在
    params = {
        "filterByFormula": 'FIND("title_patterns", {版本号}) > 0'
    }
    existing = db._request("GET", "prompts", params=params)
    records = existing.get("records", [])

    fields = {
        "版本号": version,
        "Prompt内容": final,
        "基于规律数量": len(titles),
        "进化说明": f"从{len(titles)}篇文章标题提炼的选题手册",
        "创建时间": datetime.now().isoformat(),
        "状态": "选题手册"
    }

    if records:
        db._request("PATCH", "prompts", data={"fields": fields}, record_id=records[0]["id"])
        print(f"✅ 已更新: {version}")
    else:
        db._request("POST", "prompts", data={"fields": fields})
        print(f"✅ 已保存: {version}")

    # 5. 本地备份
    filename = "title_patterns.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# 爆款选题手册\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"基于标题数: {len(titles)}\n\n")
        f.write(final)
    print(f"💾 本地备份: {filename}")

    print(f"\n🎉 提炼完成！")


if __name__ == "__main__":
    extract_title_patterns()
