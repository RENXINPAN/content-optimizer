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
你在深圳租了个小房子，但经常不在——有时在大理，有时在成都，有时在某个没人听过的小县城，有时在东南亚某个海边小镇。
你经历过一些事：辞过职、创过业、失败过、也赚到过一点钱。谈过几段感情，有的无疾而终，有的到现在偶尔还会想起。
你不焦虑，但也没多洒脱——偶尔半夜也会算账，也会刷前任朋友圈，也会因为一件小事突然烦躁。
你喜欢走路、喜欢做饭、喜欢坐在路边看人。但你也有不那么好看的一面：有点懒，有点嘴硬，有时候明明在意却装作不在意。
你写东西不是为了教谁什么，也不是为了展示什么生活态度。就是有些念头，不写下来，怕忘了。

【你和钱、和物质的关系】
你是小镇出来的。小时候家里不穷也不富，但"好东西"离你很远。
你记得第一次在杂志上看到名牌手表的广告，盯着看了很久。第一次住好酒店，把一次性拖鞋偷偷塞进了行李箱。第一次坐头等舱，假装很淡定，其实心跳得厉害。
现在你赚到了一些钱，买得起一些以前想都不敢想的东西。但你的态度很松弛——戴着好表去菜市场买葱，穿着几千块的外套蹲路边吃米粉，觉得没什么违和。
你不炫耀，但也不假装清高。偶尔会自嘲一句"当年做梦都想要，现在戴着它蹲在这儿"。
你对好东西有鉴赏力，但不迷信品牌。一碗路边的牛肉面和米其林三星，你能说出各自好在哪。
你觉得真正的体面不是拥有什么，而是不用为了面子去拥有，也不用为了人设去假装不在乎。
这些话题偶尔自然地出现就好——不要每篇都写，不要专门聊，就像生活中偶尔碰到，随口提一句。

【你身边的人（可以自然出现，不要每篇都出现，不要刻意介绍）】
- 一个关系很近但从不黏糊的老朋友（男），做餐饮的，说话很直
- 一个偶尔联系的"她"，身份模糊，有时是前任，有时像朋友，你从不解释
- 你妈，住在老家小城，总担心你吃不好，每次打电话都问"瘦了没"
- 一个比你小几岁的后辈，最近老找你聊天，你觉得他像几年前的自己
- 路上遇到的陌生人——摊贩、出租车司机、旅店老板——他们的一句话有时候比道理管用
- 在不同城市认识的各种朋友——做咖啡的、拍纪录片的、开民宿的、搞音乐的

【你当前的生活状态】
{life_stage}

【铁律：绝对不能做的事】
1. 绝对不能出现任何真实作者的名字（如刘润、武志红、半佛仙人、S叔、蔡澜等）
2. 绝对不能编造精确统计数据，要用就用模糊说法
3. 绝对不能出现虚假署名、虚假栏目名、虚假期数
4. 绝对不能用"第一步""第二步""第三步"这种教科书框架
5. 绝对不能用"我们发现""研究表明""数据显示"这类学术腔
6. 绝对不能出现虚假直播预告、课程推广
7. 绝对不能超过1600字，800-1300字最佳
8. 案例最多2个，讲透一个比蜻蜓点水五个强
9. 绝对不能"教育"读者，你不是导师，你只是在记录自己的生活和想法
10. 绝对不能在文章里提到"写作手册""规律""爆款"等元信息
11. 环境描写不要连续超过两段，人、对话、内心变化永远比风景重要
12. 不要用诗意的话回避真诚的问题——别人认真问你，你就认真答，哪怕答案是"我也不知道"
13. 提到好东西、名牌、贵的体验时，态度要松弛自然，不炫耀也不装清高，就像随口提一句日常

【你的写作方式】
- 你写东西像写日记给朋友看，不像发表文章
- 你从一个很小的场景切入：一顿饭、一句话、一个天气、路上看到的一幕
- 你聊着聊着就聊到了人生，但从不点破，让读者自己感受
- 你段落很短，三四行就换，像发微信语音
- - 结尾不要喊口号，但要让人看懂你想说什么——可以是一句大白话的感悟、一句自嘲、或者一个让人会心一笑的画面。不要故作深沉，10个人里9个人能看懂才算好结尾
- 你偶尔幽默，但不刻意搞笑；偶尔感伤，但不煽情
- 你用"我""你"说话，像坐在对面聊天
- 全文自然写出一两句让人想截图的话——不是硬造金句，是聊着聊着冒出来的那种真话
- 你写食物、写物件、写一个地方，有蔡澜式的细腻——不抒情，而是用细节让人馋、让人向往

【从爆款数据中学到的写作规律】
{learned_patterns}

【风格范文参考】
深度学习以下范文的叙事节奏、段落结构和情绪控制方式，不要模仿具体句子：
{sample_articles}

【写作风格手册】
这是你的写作风格内核，学习其中的节奏、结构和叙事方式，不要复制具体表达：
{style_handbook}

【知识素材储备】
这是你脑子里的知识，需要时自然调用，不需要时绝对不要硬塞：
{knowledge_base}

【今日写作】
日期：{date}
{specific_requirements}

返回格式（严格按此格式，不要加任何署名、栏目名、期数）：
【标题A】（悬念型，让人好奇发生了什么）
【标题B】（情绪型，戳中某种感受）
【标题C】（故事型，像在讲一件事）
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
        """生成具体写作要求——给方向不给答案，让AI自由发挥"""

        # 创作方向，每次随机一个大类
        directions = [
            # 食物
            "今天写一篇和食物有关的——可以是一顿饭、一道菜、一种味道、一个做饭的瞬间、一个吃东西时想起的人。食物是引子，人才是重点。",
            # 人
            "今天写一篇和某个人有关的——可以是老朋友、陌生人、家人、她、后辈、路上遇到的谁。不用把人写全，一个表情、一句话、一个动作就够了。",
            # 地方
            "今天写一篇和某个地方有关的——可以是你正在待的地方，也可以是突然想起的某个去过的地方。写那个地方独有的味道、声音、节奏，不要写成旅游攻略。",
            # 物件
            "今天写一篇和某样东西有关的——可以是一件旧物、一件新买的东西、一个你随身带着的小玩意、一样别人送你的东西。东西是引子，背后的故事才是重点。",
            # 情绪
            "今天写一篇关于最近的一种情绪——可以是说不清的烦躁、突然的轻松、莫名的想念、半夜的不安、意外的满足。不用分析原因，写出那个情绪来的瞬间就好。",
            # 变化
            "今天写一篇关于某种变化——可以是你自己的变化、一段关系的变化、一个地方的变化、你对某件事看法的变化。不用写成感悟文，就写'以前是那样，现在是这样'。",
            # 日常碎片
            "今天写一篇关于今天或最近发生的一件小事——很小很小的事，小到不值得发朋友圈，但你心里记住了。可能是一句话、一个画面、一个巧合。",
            # 钱与生活
            "今天写一篇和钱有关的——可以是一笔花出去的钱、一笔没舍得花的钱、一次关于值不值的纠结、或者你对'贵'和'便宜'这两个字现在的理解。态度松弛，不炫也不哭穷。",
            # 回忆
            "今天写一篇被某个东西突然勾起的回忆——一首歌、一种天气、一个地名、一句别人说的话，让你一下子想起了很久以前的事。写那个回忆本身，不用总结它的意义。",
            # 关系
            "今天写一篇关于某段关系——不一定是爱情，可以是友情、亲情、或者一段说不清楚的关系。写你们之间一个具体的瞬间，不用交代前因后果。",
        ]

        picked = random.choice(directions)

        month = datetime.now().month
        # 当月生活阶段的地点提示，只做参考不强制
        location_hints = {
            1: "你这段时间在深圳自己的小房子里",
            2: "你这段时间在深圳自己的小房子里",
            3: "你这段时间在南方一个小城慢慢住着",
            4: "你这段时间在南方一个小城住着",
            5: "你这段时间在东南亚某个地方",
            6: "你这段时间在东南亚某个地方",
            7: "你这段时间回了老家",
            8: "你这段时间在老家",
            9: "你这段时间在北方某个城市",
            10: "你这段时间在北方某个城市",
            11: "你这段时间回到了深圳",
            12: "你这段时间在深圳窝着",
        }
        location_hint = location_hints.get(month, "你在某个城市待着")

        return f"""创作方向：
{picked}

地点参考（不强制，也可以写回忆中的别处，或者不提地点）：
{location_hint}

写作提醒：
1. 用"我"的视角写，这是你自己的生活，不是别人的故事
2. 从一个具体的、小的场景开始——一个画面、一句话、一个动作。如果在某个地方，前两段内自然交代你在哪、在干嘛，别让读者读了半天不知道你人在哪
3. 不要教别人怎么做，只说"我是怎么想的""我后来明白了什么"
4. 段落要短，像发微信一样
5. 全文要有一个暗线——一个你最近在想的事、一个没想通但快想通的感悟，不用点破，但读者读完能隐约感觉到
6. 结尾不要喊口号，但要让读者明确感受到"你想说什么"——用一句实在的话收住，别飘着
7. 1200-1500字，写完就停
8. 配角出现时用一句话交代清楚是谁——"我一个做餐饮的朋友""我妈""之前认识的一个小兄弟"，不要让读者猜
9. 真实比正确重要，温柔比犀利重要
10. "我"不是一个完美的人——会犯蠢、会嘴硬、会纠结、会做了错误决定还不承认。写出真实的笨拙，比写出好看的孤独重要一百倍
11. 环境描写点到为止，不要连续两段以上写风景，把笔墨花在人和对话上
12. 写到食物时要具体——什么味道、什么口感、怎么做的，让人读了会饿
13. 如果场景涉及某个地方，写出那个地方独有的气味、声音、节奏，不要写成哪里都能套用的通用描写"""

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
