# ingestion.py - 爆款文章摄入 + 特征提取

import re
import json
from typing import Optional
from airtable import AirtableClient

# 情绪词库
EMOTION_WORDS = [
    "崩溃", "绝望", "焦虑", "迷茫", "后悔", "心疼", "感动", "震惊",
    "惊喜", "治愈", "温暖", "心酸", "愤怒", "委屈", "感激", "励志",
    "扎心", "破防", "共鸣", "真实", "戳心", "泪目", "上头", "emo"
]

# 反常识词库
COUNTER_INTUITIVE = [
    "其实", "真相是", "你错了", "别人不告诉你", "没人说过",
    "反而", "恰恰相反", "出乎意料", "颠覆认知", "打破"
]

# 开头类型识别
OPENING_PATTERNS = {
    "故事型": ["那一天", "记得那次", "去年", "三年前", "我曾经", "有一次", "小时候"],
    "痛点型": ["你有没有", "是不是", "有没有人", "每次", "总是", "一直", "还在"],
    "数据型": ["根据", "研究表明", "数据显示", "%", "调查", "统计"],
    "反常识型": ["其实", "你可能不知道", "大多数人都错了", "真相是", "别人不告诉你"],
    "问题型": ["为什么", "怎么", "如何", "是什么", "什么是"]
}

# 结尾类型识别
ENDING_PATTERNS = {
    "互动型": ["你呢", "你觉得", "评论区", "留言", "分享一下", "说说你"],
    "行动型": ["现在就", "从今天", "立刻", "马上", "开始行动"],
    "总结型": ["总结", "最后", "归根结底", "核心是", "记住"],
    "情感型": ["愿你", "希望", "加油", "你值得", "相信自己"]
}


class ArticleIngestion:
    def __init__(self):
        self.db = AirtableClient()

    def ingest(self, title: str, content: str, source: str = "手动上传") -> str:
        """摄入一篇新文章，提取特征，存入Airtable"""
        print(f"📥 摄入文章：{title[:20]}...")

        # 1. 存入数据库
        record_id = self.db.add_article(title, content, source)

        # 2. 提取特征
        features = self.extract_features(title, content)
        print(f"✅ 特征提取完成：{len(features)} 个维度")

        # 3. 更新到数据库
        self.db.update_article_features(record_id, features)

        return record_id

    def extract_features(self, title: str, content: str) -> dict:
        """提取文章的全部特征"""
        return {
            "title_features": self._extract_title_features(title),
            "content_features": self._extract_content_features(content),
            "structure_features": self._extract_structure_features(content),
            "emotion_features": self._extract_emotion_features(title, content)
        }

    def _extract_title_features(self, title: str) -> dict:
        """标题特征"""
        has_number = bool(re.search(r'\d+', title))
        has_emotion = any(w in title for w in EMOTION_WORDS)
        has_counter = any(w in title for w in COUNTER_INTUITIVE)
        char_count = len(title)

        # 判断标题类型
        if "？" in title or "?" in title or "为什么" in title or "怎么" in title:
            title_type = "疑问型"
        elif any(w in title for w in COUNTER_INTUITIVE):
            title_type = "反常识型"
        elif has_number:
            title_type = "数字型"
        elif has_emotion:
            title_type = "情绪型"
        else:
            title_type = "陈述型"

        return {
            "has_number": has_number,
            "char_count": char_count,
            "has_emotion_word": has_emotion,
            "has_counter_intuitive": has_counter,
            "title_type": title_type,
            "char_count_range": self._get_range(char_count, [10, 15, 20, 25])
        }

    def _extract_content_features(self, content: str) -> dict:
        """正文内容特征"""
        char_count = len(content)
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        para_count = len(paragraphs)
        avg_para_len = char_count / max(para_count, 1)

        # 案例数量（有"我"+"动词"的段落）
        case_count = len(re.findall(r'我[曾经|曾|之前|以前|有一次]', content))

        # 数据引用（数字+单位）
        data_count = len(re.findall(r'\d+[%％万亿元个次年月天小时分钟]', content))

        # 开头类型
        first_para = paragraphs[0] if paragraphs else ""
        opening_type = "其他"
        for type_name, patterns in OPENING_PATTERNS.items():
            if any(p in first_para for p in patterns):
                opening_type = type_name
                break

        # 结尾类型
        last_para = paragraphs[-1] if paragraphs else ""
        ending_type = "其他"
        for type_name, patterns in ENDING_PATTERNS.items():
            if any(p in last_para for p in patterns):
                ending_type = type_name
                break

        return {
            "char_count": char_count,
            "char_count_range": self._get_range(char_count, [800, 1200, 1600, 2000, 2500]),
            "para_count": para_count,
            "avg_para_len": round(avg_para_len, 0),
            "case_count": case_count,
            "data_count": data_count,
            "opening_type": opening_type,
            "ending_type": ending_type
        }

    def _extract_structure_features(self, content: str) -> dict:
        """结构特征"""
        # 是否有小标题（**文字** 或 【文字】形式）
        has_subtitle = bool(re.search(r'(\*\*[^*]+\*\*|【[^】]+】|# )', content))
        subtitle_count = len(re.findall(r'(\*\*[^*]+\*\*|【[^】]+】)', content))

        # 是否有总结段
        has_summary = any(w in content[-300:] for w in ["总结", "最后", "归根结底", "核心", "记住"])

        # 是否有互动引导
        has_cta = any(w in content[-200:] for w in ["评论区", "留言", "你呢", "你觉得", "分享"])

        # 是否有排比/列举结构
        has_list = bool(re.search(r'[①②③④⑤]|[1-9][.、]', content))

        return {
            "has_subtitle": has_subtitle,
            "subtitle_count": subtitle_count,
            "has_summary": has_summary,
            "has_cta": has_cta,
            "has_list_structure": has_list
        }

    def _extract_emotion_features(self, title: str, content: str) -> dict:
        """情绪特征"""
        full_text = title + content

        # 情绪词密度
        emotion_count = sum(full_text.count(w) for w in EMOTION_WORDS)
        emotion_density = emotion_count / max(len(full_text) / 100, 1)

        # 主要情绪类型
        negative = sum(full_text.count(w) for w in ["崩溃", "绝望", "焦虑", "迷茫", "后悔", "心酸", "扎心"])
        positive = sum(full_text.count(w) for w in ["治愈", "温暖", "感动", "励志", "感激", "惊喜"])

        if negative > positive * 1.5:
            emotion_type = "负向共鸣"
        elif positive > negative * 1.5:
            emotion_type = "正向激励"
        else:
            emotion_type = "混合情绪"

        # 反常识密度
        counter_count = sum(full_text.count(w) for w in COUNTER_INTUITIVE)

        return {
            "emotion_count": emotion_count,
            "emotion_density": round(emotion_density, 2),
            "emotion_type": emotion_type,
            "counter_intuitive_count": counter_count,
            "has_strong_emotion": emotion_density > 1.5
        }

    def _get_range(self, value: int, thresholds: list) -> str:
        """把数值转成区间标签"""
        for i, t in enumerate(thresholds):
            if value <= t:
                return f"<{t}" if i == 0 else f"{thresholds[i-1]}-{t}"
        return f">{thresholds[-1]}"

    def batch_analyze_pending(self):
        """批量分析所有待处理文章"""
        articles = self.db.get_unanalyzed_articles()
        print(f"📋 待分析文章：{len(articles)} 篇")
        for article in articles:
            fields = article["fields"]
            features = self.extract_features(
                fields.get("标题", ""),
                fields.get("正文", "")
            )
            self.db.update_article_features(article["id"], features)
            print(f"✅ {fields.get('标题', '')[:20]}... 分析完成")
