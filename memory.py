# memory.py - 三层记忆管理系统

import json
from airtable import AirtableClient

class MemoryManager:
    """
    三层记忆系统：
    - 短期记忆：最近10篇爆款，权重0.5，捕捉最新趋势
    - 中期记忆：最近50篇，权重0.3，稳定规律
    - 长期记忆：全量数据，权重0.2，底层不变规律
    """

    WEIGHTS = {
        "短期": 0.5,
        "中期": 0.3,
        "长期": 0.2
    }

    VIRAL_THRESHOLD = 70  # 爆款分数门槛

    def __init__(self):
        self.db = AirtableClient()

    def get_weighted_patterns(self) -> dict:
        """获取三层记忆加权后的规律"""
        all_patterns = {}

        for layer, weight in self.WEIGHTS.items():
            patterns = self.db.get_patterns_by_layer(layer)
            for p in patterns:
                fields = p["fields"]
                pattern_type = fields.get("规律类型", "")
                confidence = fields.get("置信度", 0)

                if pattern_type not in all_patterns:
                    all_patterns[pattern_type] = {
                        "weighted_confidence": 0,
                        "details": {},
                        "layers": []
                    }

                all_patterns[pattern_type]["weighted_confidence"] += confidence * weight
                all_patterns[pattern_type]["layers"].append(layer)

                # 合并规律详情（短期记忆优先）
                try:
                    details = json.loads(fields.get("规律详情", "{}"))
                    if layer == "短期" or not all_patterns[pattern_type]["details"]:
                        all_patterns[pattern_type]["details"] = details
                except:
                    pass

        # 按加权置信度排序
        sorted_patterns = dict(sorted(
            all_patterns.items(),
            key=lambda x: x[1]["weighted_confidence"],
            reverse=True
        ))

        return sorted_patterns

    def get_memory_summary(self) -> dict:
        """获取三层记忆的摘要统计"""
        summary = {}
        for layer in ["短期", "中期", "长期"]:
            patterns = self.db.get_patterns_by_layer(layer)
            summary[layer] = {
                "pattern_count": len(patterns),
                "avg_confidence": sum(p["fields"].get("置信度", 0) for p in patterns) / max(len(patterns), 1),
                "top_patterns": [p["fields"].get("规律类型", "") for p in patterns[:3]]
            }
        return summary

    def should_evolve(self) -> tuple:
        """判断是否需要触发进化，返回(是否进化, 原因)"""
        articles = self.db.get_articles_with_scores(limit=200)
        viral_articles = [a for a in articles
                         if a["fields"].get("综合分数", 0) >= self.VIRAL_THRESHOLD]

        # 获取上次进化时的文章数
        current_prompt = self.db.get_current_prompt()
        if not current_prompt:
            return True, "首次运行，需要初始化"

        last_pattern_count = current_prompt["fields"].get("基于规律数量", 0)
        current_patterns = self.db.get_all_patterns()

        # 触发条件1：爆款文章数增加了5篇
        if len(viral_articles) > 0 and len(viral_articles) % 5 == 0:
            return True, f"爆款文章累计{len(viral_articles)}篇，触发局部进化"

        # 触发条件2：规律数量增加超过20%
        if len(current_patterns) > last_pattern_count * 1.2:
            return True, f"新规律增加{len(current_patterns) - last_pattern_count}条，触发全局进化"

        return False, "暂不需要进化"
