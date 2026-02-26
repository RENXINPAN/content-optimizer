# setup_airtable.py - 自动创建Airtable所有表和字段

import os
import requests
import json

API_KEY = os.environ.get("AIRTABLE_API_KEY")
BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def create_table(name, fields):
    """创建一张表"""
    url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"
    data = {"name": name, "fields": fields}
    resp = requests.post(url, headers=HEADERS, json=data)
    if resp.status_code in [200, 201]:
        print(f"✅ 表创建成功：{name}")
        return resp.json()["id"]
    else:
        print(f"⚠️  {name} 可能已存在或创建失败：{resp.text[:100]}")
        return None

def setup_all_tables():
    print("🚀 开始自动创建Airtable表结构...\n")

    # ==================== 表1：爆款文章库 ====================
    create_table("爆款文章库", [
        {"name": "标题", "type": "singleLineText"},
        {"name": "正文", "type": "multilineText"},
        {"name": "来源", "type": "singleLineText"},
        {"name": "入库时间", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Asia/Shanghai"}},
        {"name": "状态", "type": "singleSelect", "options": {"choices": [
            {"name": "待分析", "color": "yellowLight2"},
            {"name": "已分析", "color": "greenLight2"}
        ]}},
        {"name": "特征数据", "type": "multilineText"},
        {"name": "分析时间", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Asia/Shanghai"}},
        {"name": "阅读量", "type": "number", "options": {"precision": 0}},
        {"name": "点赞数", "type": "number", "options": {"precision": 0}},
        {"name": "转发数", "type": "number", "options": {"precision": 0}},
        {"name": "收藏数", "type": "number", "options": {"precision": 0}},
        {"name": "综合分数", "type": "number", "options": {"precision": 2}},
        {"name": "是否爆款", "type": "checkbox", "options": {"icon": "star", "color": "yellowBright"}},
        {"name": "数据更新时间", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Asia/Shanghai"}},
    ])

    # ==================== 表2：规律库 ====================
    create_table("规律库", [
        {"name": "规律类型", "type": "singleLineText"},
        {"name": "规律描述", "type": "multilineText"},
        {"name": "置信度", "type": "number", "options": {"precision": 4}},
        {"name": "来源文章数", "type": "number", "options": {"precision": 0}},
        {"name": "规律详情", "type": "multilineText"},
        {"name": "记忆层", "type": "singleSelect", "options": {"choices": [
            {"name": "短期", "color": "redLight2"},
            {"name": "中期", "color": "orangeLight2"},
            {"name": "长期", "color": "blueLight2"}
        ]}},
        {"name": "最后更新", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Asia/Shanghai"}},
    ])

    # ==================== 表3：Prompt版本库 ====================
    create_table("Prompt版本库", [
        {"name": "版本号", "type": "singleLineText"},
        {"name": "Prompt内容", "type": "multilineText"},
        {"name": "基于规律数量", "type": "number", "options": {"precision": 0}},
        {"name": "进化说明", "type": "multilineText"},
        {"name": "创建时间", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Asia/Shanghai"}},
        {"name": "状态", "type": "singleSelect", "options": {"choices": [
            {"name": "当前版本", "color": "greenLight2"},
            {"name": "历史版本", "color": "grayLight2"}
        ]}},
        {"name": "平均效果分数", "type": "number", "options": {"precision": 2}},
    ])

    # ==================== 表4：生成内容库 ====================
    create_table("生成内容库", [
        {"name": "标题", "type": "singleLineText"},
        {"name": "正文", "type": "multilineText"},
        {"name": "使用Prompt版本", "type": "singleLineText"},
        {"name": "预测分数", "type": "number", "options": {"precision": 2}},
        {"name": "实际分数", "type": "number", "options": {"precision": 2}},
        {"name": "偏差值", "type": "number", "options": {"precision": 2}},
        {"name": "状态", "type": "singleSelect", "options": {"choices": [
            {"name": "待审核", "color": "yellowLight2"},
            {"name": "已通过", "color": "blueLight2"},
            {"name": "已发布", "color": "greenLight2"}
        ]}},
        {"name": "生成时间", "type": "dateTime", "options": {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Asia/Shanghai"}},
    ])

    print("\n🎉 全部完成！去Airtable刷新页面查看4张新表。")

if __name__ == "__main__":
    if not API_KEY or not BASE_ID:
        print("❌ 请先设置环境变量：AIRTABLE_API_KEY 和 AIRTABLE_BASE_ID")
    else:
        setup_all_tables()
