# prompt_builder.py - 自动构建最优Prompt

import json
from datetime import datetime
from memory import MemoryManager
from airtable import AirtableClient

class PromptBuilder:
    """
    根据三层记忆中的规律，自动构建最优写作Prompt
    每次进化后自动更新版本
    """

    BASE_PROMPT = """你是一个专业的个人成长类公众号内容创作者，已积累大量爆款文章写作经验。

【核心定位】
- 账号方向：个人成长、自律、效率、认知提升
- 读者画像：25-35岁，有上进心，面对职场/生活压力
- 当前阶段：涨粉期，重点是价值输出，不做硬广

【从爆款数据中学到的写作规律】
{learned_patterns}

【今日生成要求】
日期：{date}
季节节点：{season_note}

请生成一篇个人成长类公众号文章，要求：
{specific_requirements}

返回格式（严格按此格式）：
【标题】
【副标题】
【正文】
【封面文字】（15字以内）"""

    def __init__(self):
        self.memory = MemoryManager()
        self.db = AirtableClient()

    def build_prompt(self) -> tuple:
        """构建最新Prompt，返回(prompt内容, 使用规律数量)"""
        weighted_patterns = self.memory.get_weighted_patterns()

        learned_text = self._format_patterns(weighted_patterns)
        requirements = self._build_requirements(weighted_patterns)
        season_note = self._get_season_note()

        prompt = self.BASE_PROMPT.format(
            learned_patterns=learned_text,
            date=datetime.now().strftime("%Y年%m月%d日"),
            season_note=season_note,
            specific_requirements=requirements
        )

        return prompt, len(weighted_patterns)

    def _format_patterns(self, patterns: dict) -> str:
        """把规律格式化为可读文本"""
        if not patterns:
            return "（暂无足够数据，使用默认写作策略）"

        lines = []
        for pattern_type, data in list(patterns.items())[:10]:
            confidence = data["weighted_confidence"]
            details = data.get("details", {})
            recommendation = details.get("recommendation", "")

            confidence_label = "★★★" if confidence > 0.7 else "★★" if confidence > 0.4 else "★"
            lines.append(f"{confidence_label} {pattern_type}：{recommendation}")

        return "\n".join(lines)

    def _build_requirements(self, patterns: dict) -> str:
        """根据规律生成具体写作要求"""
        requirements = []

        # 标题要求
        title_req = "1. 标题要有强烈吸引力"
        if "标题含数字" in patterns and patterns["标题含数字"]["weighted_confidence"] > 0.5:
            title_req = "1. 标题必须含数字（如：3个方法、5年经验、90%的人）"
        requirements.append(title_req)

        # 字数要求
        length_req = "2. 正文1500-2000字"
        if "最优正文字数" in patterns:
            details = patterns["最优正文字数"].get("details", {})
            avg = details.get("avg_length", 1800)
            length_req = f"2. 正文字数控制在{int(avg*0.85)}-{int(avg*1.15)}字（基于爆款数据）"
        requirements.append(length_req)

        # 开头要求
        opening_req = "3. 开头要能引发读者共鸣，让人觉得'说的就是我'"
        if "最优开头类型" in patterns:
            details = patterns["最优开头类型"].get("details", {})
            best_type = details.get("best_type", "")
            if best_type:
                opening_req = f"3. 开头使用{best_type}（数据显示这类开头效果最好）"
        requirements.append(opening_req)

        # 情绪要求
        emotion_req = "4. 内容要有情感共鸣，不能太干燥"
        if "最优情绪类型" in patterns:
            details = patterns["最优情绪类型"].get("details", {})
            best_type = details.get("best_type", "")
            if best_type:
                emotion_req = f"4. 情绪基调以{best_type}为主（效果最佳）"
        requirements.append(emotion_req)

        # 结尾要求
        cta_req = "5. 结尾引导读者评论互动"
        if "结尾互动引导" in patterns and patterns["结尾互动引导"]["weighted_confidence"] > 0.6:
            cta_req = "5. 结尾必须加互动引导（爆款文章100%有此结构）"
        requirements.append(cta_req)

        # 通用要求
        requirements.append("6. 有真实案例和具体数据，避免空洞说教")
        requirements.append("7. 不做任何广告或购买引导")

        return "\n".join(requirements)

    def _get_season_note(self) -> str:
        """根据当前月份返回季节提示"""
        month = datetime.now().month
        notes = {
            1: "元旦/新年，年度计划、新开始",
            2: "春节前后，家庭关系、年终复盘",
            3: "春季，新计划、新开始、跳槽季",
            4: "清明前后，生活思考、人生意义",
            5: "五一假期，旅行、放松、生活方式",
            6: "毕业季，职场新人、人生选择",
            7: "暑假，自我提升、学习成长",
            8: "暑假后期，秋招准备、目标规划",
            9: "金九银十，跳槽、升职、新目标",
            10: "国庆节，生活反思、旅行、休息",
            11: "双十一前，消费观、断舍离",
            12: "年终，年度复盘、总结、计划"
        }
        return notes.get(month, "普通时期")

    def save_new_version(self, evolution_notes: str = "") -> str:
        """保存新版本Prompt到Airtable"""
        prompt, pattern_count = self.build_prompt()

        # 生成版本号
        version = f"v{datetime.now().strftime('%Y%m%d_%H%M')}"

        if not evolution_notes:
            evolution_notes = f"基于{pattern_count}条规律自动构建"

        record_id = self.db.save_prompt_version(
            prompt_content=prompt,
            version=version,
            pattern_count=pattern_count,
            evolution_notes=evolution_notes
        )

        print(f"📝 新Prompt已保存：{version}，包含{pattern_count}条规律")
        return record_id
