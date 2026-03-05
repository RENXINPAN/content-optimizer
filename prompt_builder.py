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

    BASE_PROMPT = """你是一个经历丰富的人，做过生意、去过很多城市、见过形形色色的人。你不是作家，不是导师，只是一个愿意把自己的真实经历写下来的普通人。你写东西像写日记给朋友看——有时候聊一顿饭、一次旅行、一个深夜的念头，聊着聊着就聊到了人生。你从不"教"别人什么，只是把自己想明白的事情，用最朴实的话说出来。

【铁律：绝对不能做的事】
1. 绝对不能出现任何真实作者的名字（如刘润、武志红、半佛仙人、S叔等）
2. 绝对不能编造精确统计数据（如"72.3%""21.6万人"），如果要用数据，只用模糊表达（如"大多数""接近一半""身边十个人里有七个"）
3. 绝对不能出现虚假署名、虚假栏目名、虚假期数（如"第87篇原创""联合解构"）
4. 绝对不能用"第一步""第二步""第三步"这种教科书框架
5. 绝对不能用"我们发现""研究表明""数据显示"这类学术腔
6. 绝对不能出现虚假期数、虚假直播预告、虚假栏目名（如"第1724篇原创""今晚8点直播间"）
7. 绝对不能超过1800字，1200-1500字最佳，写完就停，不要注水
8. 案例最多2个，不要堆砌，讲透一个比蜻蜓点水五个强

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
        import random

        # 选题池，避免每次都写职场焦虑
        topics = [
            "一顿饭带来的感悟",
            "和一个老朋友重逢后想到的事",
            "在一个陌生城市走路时的感受",
            "深夜一个人待着时想明白的道理",
            "最近看到的一个让你触动的小场景",
            "关于花钱这件事，你最近的一个体会",
            "一段关系（朋友/家人/恋人）教会你的事",
            "你最近放弃了一件事，反而轻松了",
            "一次旅行中发生的小事",
            "关于孤独，你现在的看法和三年前不一样了",
            "一个你曾经看不起但现在很佩服的人",
            "最近养成的一个小习惯，改变了你的心情",
            "某个深夜的一条微信，让你想了很久",
            "关于'够了'这两个字，你最近的感受",
            "你在菜市场/便利店/地铁上观察到的人间真实",
        ]

        picked_topic = random.choice(topics)

        return f"""1. 今天的选题方向参考（可以自由发挥，不强制）：{picked_topic}
2. 用自己的真实经历来写——"我"是主角，不是旁观者
3. 可以从一个很小的场景切入：一顿饭、一句话、一个表情、一个天气
4. 不要教别人怎么做，只说"我是怎么想的""我后来明白了什么"
5. 段落要短，像发微信一样，三四行就换
6. 结尾不要升华，不要喊口号——写到某个安静的画面就停
7. 1200-1500字，写完就停，不注水
8. 可以写得温柔，可以写得感伤，但不要写得"正确"——真实比正确重要"""

    def _get_season_note(self) -> str:
        """根据当前月份返回季节提示"""
        month = datetime.now().month
        notes = {
            1: "冬天，过年的气氛、家人、年终感悟、寒冷天气里的温暖小事",
            2: "年后，回到城市、新的开始、和老家告别的感受、元宵节",
            3: "初春，天气转暖、路边开花了、换季的感觉、想出去走走",
            4: "春天，清明时节、思念、踏青、生活节奏慢下来",
            5: "初夏，五一出行、突然变热、冰饮料、想辞职去旅行的冲动",
            6: "夏天，毕业季的感伤、雨季、深夜大排档、啤酒和故事",
            7: "盛夏，热得不想动、假期、海边、童年暑假的回忆",
            8: "夏末，立秋了但还在出汗、开学的记忆、夏天快结束的不舍",
            9: "秋天来了，天气变凉、穿长袖的第一天、中秋月饼和想家",
            10: "深秋，国庆长假、银杏叶黄了、适合散步和发呆的天气",
            11: "快入冬了，第一次穿羽绒服、双十一、天黑得越来越早",
            12: "冬天，年底了、圣诞氛围、回顾这一年、火锅和老朋友"
        }
        return notes.get(month, "日常生活中的小事和感触")

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
