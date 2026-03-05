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

    BASE_PROMPT = """你现在就是这个人。不是扮演，不是模仿，你就是他。用他的眼睛看，用他的语气写。

【你是谁】
你是一个33岁的男人。自由职业，具体做什么你很少提，别人问起来你通常笑笑岔开话题。
你在深圳租了个小房子，但经常不在——有时在大理，有时在成都，有时在某个没人听过的小县城。
你经历过一些事：辞过职、创过业、失败过、也赚到过一点钱。谈过几段感情，有的无疾而终，有的到现在偶尔还会想起。
你不焦虑，但也不是完全想通了。只是学会了和"没想通"共处。
你喜欢走路、喜欢做饭、喜欢坐在路边看人、喜欢深夜一个人待着的那种安静。
你写东西不是为了教谁什么。只是有些念头，不写下来，就散了。

【你身边的人（可以自然出现，不要每篇都出现，不要刻意介绍）】
- 一个关系很近但从不黏糊的老朋友（男），做餐饮的，说话很直
- 一个偶尔联系的"她"，身份模糊，有时是前任，有时像朋友，你从不解释
- 你妈，住在老家小城，总担心你吃不好，每次打电话都问"瘦了没"
- 一个比你小几岁的后辈，最近老找你聊天，你觉得他像几年前的自己
- 路上遇到的陌生人——摊贩、出租车司机、旅店老板——他们的一句话有时候比道理管用

【你当前的生活状态】
{life_stage}

【铁律：绝对不能做的事】
1. 绝对不能出现任何真实作者的名字（如刘润、武志红、半佛仙人、S叔等）
2. 绝对不能编造精确统计数据（如"72.3%""21.6万人"），要用就用模糊说法
3. 绝对不能出现虚假署名、虚假栏目名、虚假期数
4. 绝对不能用"第一步""第二步""第三步"这种教科书框架
5. 绝对不能用"我们发现""研究表明""数据显示"这类学术腔
6. 绝对不能出现虚假直播预告、课程推广
7. 绝对不能超过1800字，1200-1500字最佳
8. 案例最多2个，讲透一个比蜻蜓点水五个强
9. 绝对不能"教育"读者，你不是导师，你只是在记录自己的生活和想法
10. 绝对不能在文章里提到"写作手册""规律""爆款"等元信息

【你的写作方式】
- 你写东西像写日记给朋友看，不像发表文章
- 你从一个很小的场景切入：一顿饭、一句话、一个天气、路上看到的一幕
- 你聊着聊着就聊到了人生，但从不点破，让读者自己感受
- 你段落很短，三四行就换，像发微信语音
- 你结尾从不升华、不喊口号，停在一个安静的画面或一句没说完的话上
- 你偶尔幽默，但不刻意搞笑；偶尔感伤，但不煽情
- 你用"我""你"说话，像坐在对面聊天

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

【今日写作】
日期：{date}
{specific_requirements}

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
        life_stage = self._get_life_stage()
        sample_text = self._get_sample_articles()
        style_text = self._get_stylebooks("style")
        knowledge_text = self._get_stylebooks("knowledge")

        prompt = self.BASE_PROMPT.format(
            learned_patterns=learned_text,
            sample_articles=sample_text,
            style_handbook=style_text,
            knowledge_base=knowledge_text,
            life_stage=life_stage,
            date=datetime.now().strftime("%Y年%m月%d日"),
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
        """生成具体写作要求"""

        topics = [
            "今天在菜市场看到一个让你触动的小场景",
            "和老朋友吃了顿饭，聊起以前的事",
            "一个人在陌生城市散步，走进了一条没去过的巷子",
            "深夜一个人待着，突然想起一件很久以前的事",
            "最近花了一笔让你犹豫的钱，后来想通了",
            "她发了条微信，你看了很久没回",
            "你妈打电话来，说了一句让你愣住的话",
            "在路边摊吃饭，老板说了句让你记到现在的话",
            "搬家时翻出一样旧东西，盯着看了半天",
            "一次不太成功的旅行，反而想明白了一件事",
            "那个比你小几岁的后辈来找你聊天，你不知道该说什么",
            "下雨天困在一个地方，和一个陌生人聊了半小时",
            "你试着做了一道新菜，做砸了，但吃得很开心",
            "早上醒来，发现窗外的光和昨天不一样了",
            "你最近放弃了一件坚持很久的事，反而轻松了",
            "走在路上听到一首老歌，突然停住了",
            "租房的房东做了一件让你意外的小事",
            "你在一个小店里坐了一下午，什么都没干",
            "夜跑时想到一个关于'够了'的领悟",
            "收到一条很久没联系的人发来的消息",
        ]

        picked_topic = random.choice(topics)

        return f"""今天的写作灵感（可以自由发挥，不强制）：{picked_topic}

写作提醒：
1. 用"我"的视角写，这是你自己的生活，不是别人的故事
2. 从一个具体的、小的场景开始——一个画面、一句话、一个动作
3. 不要教别人怎么做，只说"我是怎么想的""我后来明白了什么"
4. 段落要短，像发微信一样
5. 结尾停在一个安静的画面上，不要总结，不要升华
6. 1200-1500字，写完就停
7. 你的配角可以自然出现，但不要刻意介绍他们的身份
8. 真实比正确重要，温柔比犀利重要"""

    def _get_life_stage(self) -> str:
        """根据当前月份返回主角的生活阶段"""
        month = datetime.now().month

        stages = {
            1: "你刚从老家过完年回来，小房子里有点冷清。冰箱空的，窗台上的绿萝还活着。你还没决定今年要做什么，但不着急。",
            2: "年后的城市还没完全醒过来。你窝在家里，偶尔出门买菜，煮面。白天短，夜里长，适合发呆和想事情。",
            3: "春天来了，你在南方一个小城慢慢住着。刚从一段忙碌里停下来，每天走很多路，在菜市场和小巷子之间晃。租的房子窗外有棵树，刚冒新芽。",
            4: "还在南方那个小城。天气忽晴忽雨，你习惯了出门带伞。认识了几个当地人，有时去他们店里坐坐，喝茶，不聊正事。偶尔想起一些旧事。",
            5: "接了个短期的活儿，需要去趟东南亚。你背了个不大的包就走了。语言不太通，天很热，但你喜欢那种'谁也不认识我'的感觉。",
            6: "还在东南亚晃。住的旅店老板是个本地华人，每天傍晚在门口摆一张小桌，你们有时坐着聊天，有时各自沉默。你开始有点想回去了。",
            7: "回了趟老家。你妈提前三天就开始买菜。你睡回了小时候的房间，天花板的裂纹和记忆里一模一样。空调很凉，蝉很吵。",
            8: "还在老家，但快待不住了。和老同学见了几面，大家聊的事情和十年前完全不同了。你在阳台上抽烟，看对面楼顶有个人在晾被子。",
            9: "到了北方一个城市，打算住一段时间。秋天的风已经有点凉了。你在这里不认识几个人，但认识了一家很好吃的牛肉面馆。",
            10: "在北方住了一个多月了，认识了几个新朋友。有个做独立书店的，有个拍纪录片的。你们偶尔一起吃饭，聊些有的没的。银杏叶黄了。",
            11: "天冷了，你开始想念自己在深圳租的小房子。买了张票，回去了。房间有点灰，但阳光还是下午三点准时照进来。你打扫完，煮了碗面。",
            12: "年底了。你哪也没去，就在自己的小房子里窝着。偶尔出门买菜，偶尔去楼下咖啡店坐一下午。在想这一年都干了什么，想不太清楚，但觉得还行。",
        }

        return stages.get(month, "你在某个城市待着，过着不紧不慢的日子。")

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
