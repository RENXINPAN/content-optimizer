# feedback.py - 效果数据回流 + 偏差修正

import json
from airtable import AirtableClient
from evolution import EvolutionEngine
from memory import MemoryManager

class FeedbackProcessor:
    """
    处理发布后的效果数据回流：
    1. 计算综合分数
    2. 更新文章记录
    3. 判断是否触发进化
    4. 修正预测偏差
    """

    def __init__(self):
        self.db = AirtableClient()
        self.evolution = EvolutionEngine()
        self.memory = MemoryManager()

    def process_feedback(self, record_id: str, read_count: int,
                         like_count: int, share_count: int, collect_count: int):
        """处理一篇文章的效果反馈"""
        # 更新分数
        self.db.update_article_score(record_id, read_count, like_count, share_count, collect_count)

        # 计算分数用于判断
        score = self._calc_score(read_count, like_count, share_count, collect_count)
        is_viral = score >= 70

        print(f"📊 效果反馈处理完成：综合分数 {score:.1f}分，{'🔥爆款！' if is_viral else '普通内容'}")

        # 判断是否触发进化
        should_evolve, reason = self.memory.should_evolve()
        if should_evolve:
            print(f"🧬 触发进化：{reason}")
            self._run_full_evolution()

        return score, is_viral

    def batch_feedback(self, feedback_list: list):
        """
        批量处理反馈数据
        feedback_list格式：[{"record_id": "xxx", "read": 1000, "like": 20, "share": 5, "collect": 30}]
        """
        print(f"📥 处理{len(feedback_list)}条反馈数据...")
        scores = []
        for item in feedback_list:
            score, is_viral = self.process_feedback(
                item["record_id"],
                item.get("read", 0),
                item.get("like", 0),
                item.get("share", 0),
                item.get("collect", 0)
            )
            scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0
        viral_count = sum(1 for s in scores if s >= 70)
        print(f"✅ 批量反馈完成：平均分{avg_score:.1f}，爆款{viral_count}/{len(scores)}篇")

        # 更新当前Prompt的平均效果分数
        current_prompt = self.db.get_current_prompt()
        if current_prompt:
            self.db.update_prompt_performance(current_prompt["id"], avg_score)

    def _calc_score(self, read_count, like_count, share_count, collect_count) -> float:
        """计算综合分数"""
        read_score = min(read_count / 10000, 1.0)
        like_rate = like_count / max(read_count, 1)
        share_rate = share_count / max(read_count, 1)
        collect_rate = collect_count / max(read_count, 1)
        return (read_score * 0.25 + like_rate * 0.25 +
                collect_rate * 0.35 + share_rate * 0.15) * 100

    def _run_full_evolution(self):
        """运行完整的三层进化"""
        print("🧬 开始三层进化...")
        for layer in ["短期", "中期", "长期"]:
            self.evolution.run_evolution(layer)

        # 构建新Prompt
        from prompt_builder import PromptBuilder
        builder = PromptBuilder()
        builder.save_new_version("数据回流触发自动进化")
        print("✅ 三层进化完成，Prompt已更新")

    def parse_wechat_feedback(self, text: str) -> list:
        """
        解析你发给机器人的微信数据，格式：
        文章1：《标题》阅读2300 点赞45 转发12 收藏38
        """
        import re
        results = []
        lines = text.strip().split('\n')
        for line in lines:
            # 匹配标题
            title_match = re.search(r'《([^》]+)》', line)
            read_match = re.search(r'阅读(\d+)', line)
            like_match = re.search(r'点赞(\d+)', line)
            share_match = re.search(r'转发(\d+)', line)
            collect_match = re.search(r'收藏(\d+)', line)

            if title_match and read_match:
                results.append({
                    "title": title_match.group(1),
                    "read": int(read_match.group(1)),
                    "like": int(like_match.group(1)) if like_match else 0,
                    "share": int(share_match.group(1)) if share_match else 0,
                    "collect": int(collect_match.group(1)) if collect_match else 0
                })
        return results
