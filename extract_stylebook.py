"""
extract_stylebook.py — 从爆款文章库提炼4份写作手册
按作者分别提炼，风格作者和知识作者提炼维度不同

用法：
  python extract_stylebook.py          # 提炼全部4个作者
  python extract_stylebook.py 半佛仙人  # 只提炼指定作者

产出：存入Airtable的prompts表，或输出为本地文件
"""

import os
import sys
import json
import time
import random
import requests
from datetime import datetime
from airtable import AirtableClient

# ============================================================
# 配置
# ============================================================

# 风格作者：重点提炼怎么写
STYLE_AUTHORS = ["半佛仙人", "香港S叔"]

# 知识作者：重点提炼写了什么
KNOWLEDGE_AUTHORS = ["刘润", "武志红"]

# 每批处理文章数
BATCH_SIZE = 10

# 每批之间等待秒数（避免API限流）
BATCH_DELAY = 3

# 风格作者的提炼Prompt
STYLE_EXTRACT_PROMPT = """你是一个资深的写作教练，擅长分析作者的写作风格。

以下是作者「{author}」的{count}篇文章。请深度分析这些文章，提炼以下维度：

1.【金句/金语】提取10条最有传播力的金句原文，分析其句式结构
2.【开头模板】总结3种常用的开头手法，每种给出具体示例
3.【结尾模板】总结3种常用的结尾手法，每种给出具体示例
4.【比喻/类比手法】提取5个最精彩的比喻或类比，分析其手法
5.【论证结构模式】总结2-3种常用的文章整体结构
6.【情绪节奏控制】分析作者如何控制文章的情绪起伏节奏
7.【标志性语言习惯】总结作者独特的口头禅、句式偏好、用词特点

请用具体的例子说明每个维度，不要空泛描述。

--- 以下是文章 ---
{articles}
"""

# 知识作者的提炼Prompt
KNOWLEDGE_EXTRACT_PROMPT = """你是一个资深的知识整理专家。

以下是作者「{author}」的{count}篇文章。请深度分析这些文章，提炼以下维度：

1.【核心概念库】提取作者反复使用的10-15个核心概念/术语，每个用一句话解释
2.【底层逻辑/思维模型】总结作者常用的3-5个分析框架或思维模型
3.【经典案例库】提取5-8个最有说服力的案例，每个用2-3句话概述
4.【高频观点】总结作者最核心的5-8个观点立场
5.【金句/金语】提取8条最有洞察力的金句原文
6.【独特视角】分析作者看问题的独特角度是什么

请用具体的例子说明每个维度，不要空泛描述。

--- 以下是文章 ---
{articles}
"""

# 最终汇总Prompt（风格作者）
STYLE_SUMMARY_PROMPT = """你是一个写作教练，请将以下多批次的分析结果汇总成一份完整的「{author}风格写作手册」。

要求：
1. 去重合并，保留最精华的内容
2. 每个维度保留最具代表性的例子
3. 总字数控制在3000-5000字
4. 格式清晰，方便直接作为写作参考

最终手册应包含：
- 金句库（15-20条最强金句）
- 开头模板（5种，含示例）
- 结尾模板（5种，含示例）
- 比喻/类比手法（8-10个精彩案例）
- 论证结构模式（3-4种）
- 情绪节奏控制技巧
- 标志性语言习惯

--- 以下是多批次分析结果 ---
{batch_results}
"""

# 最终汇总Prompt（知识作者）
KNOWLEDGE_SUMMARY_PROMPT = """你是一个知识整理专家，请将以下多批次的分析结果汇总成一份完整的「{author}知识素材库」。

要求：
1. 去重合并，保留最精华的内容
2. 每个维度保留最具代表性的例子
3. 总字数控制在3000-5000字
4. 格式清晰，方便写作时快速查阅和引用

最终素材库应包含：
- 核心概念库（15-20个关键概念及解释）
- 思维模型库（5-8个分析框架）
- 经典案例库（10-15个可复用的案例）
- 核心观点库（8-10个代表性观点）
- 金句库（10-15条最有洞察力的句子）
- 独特视角总结

--- 以下是多批次分析结果 ---
{batch_results}
"""


# ============================================================
# 千问API调用
# ============================================================

def call_qwen(prompt, max_tokens=4000):
    """调用千问API"""
    api_key = os.environ.get("QWEN_API_KEY")
    if not api_key:
        print("ERROR: QWEN_API_KEY未配置")
        return None

    try:
        resp = requests.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json; charset=utf-8"
            },
            json={
                "model": "qwen-plus",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,  # 低温度，提取更准确
            },
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  千问调用失败: {e}")
        return None


# ============================================================
# 文章获取
# ============================================================

def get_articles_by_author(author, limit=500):
    """从Airtable获取指定作者的所有文章"""
    db = AirtableClient()
    all_records = []
    offset = None

    while True:
        params = {
            "filterByFormula": f'{{来源}} = "{author}"',
            "pageSize": 100,
        }
        if offset:
            params["offset"] = offset

        result = db._request("GET", "爆款文章库", params=params)
        records = result.get("records", [])
        all_records.extend(records)
        offset = result.get("offset")

        if not offset or len(all_records) >= limit:
            break

    # 只保留有正文的
    valid = [
        r for r in all_records
        if r.get("fields", {}).get("正文", "").strip()
    ]

    print(f"  {author}: 共{len(all_records)}篇，有效{len(valid)}篇")
    return valid


# ============================================================
# 分批提炼
# ============================================================

def extract_batch(author, articles, is_style_author):
    """对一批文章进行提炼"""
    # 拼接文章内容
    articles_text = ""
    for i, r in enumerate(articles):
        fields = r.get("fields", {})
        title = fields.get("标题", "无标题")
        body = fields.get("正文", "")
        articles_text += f"\n\n===== 第{i+1}篇：{title} =====\n{body}"

    # 选择Prompt模板
    if is_style_author:
        prompt = STYLE_EXTRACT_PROMPT.format(
            author=author,
            count=len(articles),
            articles=articles_text
        )
    else:
        prompt = KNOWLEDGE_EXTRACT_PROMPT.format(
            author=author,
            count=len(articles),
            articles=articles_text
        )

    return call_qwen(prompt, max_tokens=4000)


def summarize_results(author, batch_results, is_style_author):
    """汇总所有批次结果"""
    combined = "\n\n".join([
        f"--- 第{i+1}批分析 ---\n{result}"
        for i, result in enumerate(batch_results)
        if result
    ])

    if is_style_author:
        prompt = STYLE_SUMMARY_PROMPT.format(
            author=author,
            batch_results=combined
        )
    else:
        prompt = KNOWLEDGE_SUMMARY_PROMPT.format(
            author=author,
            batch_results=combined
        )

    return call_qwen(prompt, max_tokens=6000)


# ============================================================
# 存储
# ============================================================

def save_stylebook(author, content, book_type):
    """保存写作手册到Airtable的prompts表"""
    db = AirtableClient()

    version = f"stylebook_{author}_{datetime.now().strftime('%Y%m%d')}"
    note = f"{author}{'风格手册' if book_type == 'style' else '知识素材库'}"

    # 检查是否已存在同作者的手册
    params = {
        "filterByFormula": f'AND(FIND("stylebook_{author}", {{版本号}}) > 0)'
    }
    existing = db._request("GET", "prompts", params=params)
    records = existing.get("records", [])

    fields = {
        "版本号": version,
        "Prompt内容": content,
        "基于规律数量": 0,
        "进化说明": note,
        "创建时间": datetime.now().isoformat(),
        "状态": "写作手册"
    }

    if records:
        # 更新已有的
        db._request("PATCH", "prompts", data={"fields": fields}, record_id=records[0]["id"])
        print(f"  ✅ 已更新: {version}")
    else:
        db._request("POST", "prompts", data={"fields": fields})
        print(f"  ✅ 已保存: {version}")

    return version


# ============================================================
# 主流程
# ============================================================

def extract_one_author(author):
    """提炼单个作者"""
    is_style = author in STYLE_AUTHORS
    book_type = "style" if is_style else "knowledge"
    label = "风格手册" if is_style else "知识素材库"

    print(f"\n{'='*50}")
    print(f"📚 开始提炼: {author} ({label})")
    print(f"{'='*50}")

    # 1. 获取文章
    articles = get_articles_by_author(author)
    if not articles:
        print(f"  ⚠️ {author}没有文章，跳过")
        return

    # 2. 随机打乱，分批处理
    random.shuffle(articles)
    batches = [articles[i:i+BATCH_SIZE] for i in range(0, len(articles), BATCH_SIZE)]
    # 最多处理20批（200篇），避免太耗时
    batches = batches[:20]

    print(f"  共{len(articles)}篇文章，分{len(batches)}批处理")

    # 3. 逐批提炼
    batch_results = []
    for i, batch in enumerate(batches):
        print(f"  📖 第{i+1}/{len(batches)}批 ({len(batch)}篇)...")
        result = extract_batch(author, batch, is_style)
        if result:
            batch_results.append(result)
            print(f"    ✅ 提炼完成 ({len(result)}字)")
        else:
            print(f"    ❌ 提炼失败")
        time.sleep(BATCH_DELAY)

    if not batch_results:
        print(f"  ❌ 所有批次都失败了")
        return

    # 4. 汇总
    print(f"\n  📝 汇总{len(batch_results)}批结果...")
    final = summarize_results(author, batch_results, is_style)

    if not final:
        print(f"  ❌ 汇总失败")
        return

    print(f"  ✅ 手册生成完成 ({len(final)}字)")

    # 5. 保存
    save_stylebook(author, final, book_type)

    # 6. 同时保存本地备份
    filename = f"stylebook_{author}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# {author} {label}\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"基于文章数: {len(articles)}\n\n")
        f.write(final)
    print(f"  💾 本地备份: {filename}")


def main():
    all_authors = STYLE_AUTHORS + KNOWLEDGE_AUTHORS

    if len(sys.argv) > 1:
        # 指定作者
        target = sys.argv[1]
        if target in all_authors:
            extract_one_author(target)
        else:
            print(f"未知作者: {target}")
            print(f"可选: {', '.join(all_authors)}")
    else:
        # 全部提炼
        print(f"🚀 开始提炼全部{len(all_authors)}位作者的写作手册")
        print(f"预计耗时: 15-30分钟\n")

        for author in all_authors:
            extract_one_author(author)

        print(f"\n🎉 全部提炼完成！")


if __name__ == "__main__":
    main()
