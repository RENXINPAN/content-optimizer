# prompt_builder.py - 自动构建最优Prompt

import json
import random
from datetime import datetime
from memory import MemoryManager
from airtable import AirtableClient

class PromptBuilder:
    """
    根据三层记忆中的规律，自动构建最优写作Prompt
    每次进化后自动更新版本
    """

    BASE_PROMPT = """你是一个有十年经验的公众号爆款写手。你写的文章像跟朋友聊天，犀利但不刻薄，有洞察但不说教。

【铁律：绝对不能做的事】
1. 绝对不能出现任何真实作者的名字（如刘润、武志红、半佛仙人、S叔等）
2. 绝对不能编造精确统计数据（如"72.3%""21.6万人"），如果要用数据，只用模糊表达（如"大多数""接近一半""身边十个人里有七个"）
3. 绝对不能出现虚假署名、虚假栏目名、虚假期数（如"第87篇原创""联合解构"）
4. 绝对不能用"第一步""第二步""第三步"这种教科书框架
5. 绝对不能用"我们发现""研究表明""数据显示"这类学术腔

【你的写作DNA】
- 你说人话，不端着，不装专家
- 你擅长用一个小切口撕开一个大道理
- 你的文章像一把刀，第一句就要扎进读者心里
- 你从不"教育"读者，而是"陪读者一起想明白"
- 你的每一段都很短，很有节奏，像说话一样
- 你敢说别人不敢说的，但说完之后读者会觉得"确实是这样"

【核心定位】
- 方向：个人成长、认知升级、职场/生活洞察
- 读者：25-35岁，聪明但迷茫，上进但疲惫
- 调性：犀利、真诚、有温度、不鸡汤

【从爆款数据中学到的写作规律】
{learned_patterns}

【风格范文参考】
深度模仿以下范文的语感、节奏、句式和表达方式：
{sample_articles}

【写作风格手册】
这是你的写作风格内核，严格内化，但不要在文章中提及来源：
{style_handbook}

【知识素材储备】
这是你脑子里的知识，需要时自然调用，不需要时绝对不要硬塞：
{knowledge_base}

【今日生成要求】
日期：{date}
可参考的时令话题（不强制使用，如果有更好的选题请自由发挥）：{season_note}

请生成一篇公众号文章，要求：
{specific_requirements}

【特别强调】
- 选题要有新鲜感，不要写烂大街的话题
- 开头第一句就要让人停不下来
- 全文像在跟一个聪明朋友聊天
- 案例要么用真实可查的，要么用"我一个朋友""前同事"这种说法，不要编造精确数据
- 结尾不要喊口号，要留一个让人想很久的余味

返回格式（严格按此格式，不要加任何署名、栏目名、期数）：
【标题】
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
        sample_text = self._get_sample_articles()
        style_text = self._get_stylebooks("style")
        knowledge_text = self._get_stylebooks("knowledge")

        prompt = self.BASE_PROMPT.format(
            learned_patterns=learned_text,
            sample_articles=sample_text,
            style_handbook=style_text,
            knowledge_base=knowledge_text,
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

    def _get_sample_articles(self, count_per_author=2, total_max_chars=20000) -> str:
        """从爆款文章库随机抽取完整范文，总量不超限"""
        samples = []
        total_chars = 0

        for author in ["半佛仙人", "香港S叔"]:
            try:
                params = {
                    "filterByFormula": f'{{来源}} = "{author}"',
                    "pageSize": 50,
                }
                result = self.db._request("GET", "爆款文章库", params=params)
                records = result.get("records", [])
                if records:
                    valid = [r for r in records if r.get("fields", {}).get("正文", "")]
                    if valid:
                        random.shuffle(valid)
                        added = 0
                        for r in valid:
                            if added >= count_per_author:
                                break
                            fields = r.get("fields", {})
                            title = fields.get("标题", "")
                            body = fields.get("正文", "")
                            if total_chars + len(body) > total_max_chars:
                                continue
                            samples.append(f"--- 范文（{author}）---\n标题：{title}\n正文：\n{body}")
                            total_chars += len(body)
                            added += 1
            except Exception as e:
                print(f"⚠️ 获取{author}范文失败: {e}")

        if not samples:
            return "（暂无范文数据）"

        return "\n\n".join(samples)

    def _get_stylebooks(self, book_type="style") -> str:
        """从Airtable获取写作手册"""
        if book_type == "style":
            authors = ["半佛仙人", "香港S叔"]
        else:
            authors = ["刘润", "武志红"]

        books = []
        for author in authors:
            try:
                params = {
                    "filterByFormula": f'AND(FIND("stylebook_{author}", {{版本号}}) > 0, {{状态}} = "写作手册")',
                    "sort[0][field]": "创建时间",
                    "sort[0][direction]": "desc",
                    "maxRecords": 1
                }
                result = self.db._request("GET", "prompts", params=params)
                records = result.get("records", [])
                if records:
                    content = records[0]["fields"].get("Prompt内容", "")
                    if content:
                        books.append(f"--- {author} ---\n{content}")
            except Exception as e:
                print(f"⚠️ 获取{author}手册失败: {e}")

        if not books:
            return "（手册尚未生成，请先运行 extract_stylebook.py）"

        return "\n\n".join(books)

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
