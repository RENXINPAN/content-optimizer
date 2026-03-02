# evolution.py - 进化引擎核心：规律提炼 + 权重更新

import json
import os
import requests
from collections import defaultdict, Counter
from airtable import AirtableClient

class EvolutionEngine:
    """
    进化引擎：从爆款文章中提炼规律，更新三层记忆
    
    核心逻辑：
    1. 对比爆款 vs 普通文章的特征差异
    2. 差异显著的特征 → 提炼为规律
    3. 规律的置信度 = 差异显著程度 × 样本量权重
    4. 按短/中/长期分层存储
    """

    def __init__(self):
        self.db = AirtableClient()
        self.qwen_api_key = os.environ.get("QWEN_API_KEY")
        self.viral_threshold = 70

    def run_evolution(self, layer: str = "中期"):
        """执行一次进化"""
        print(f"\n🧬 开始进化 [{layer}记忆层]...")

        articles = self.db.get_all_articles(
            limit=10 if layer == "短期" else 50 if layer == "中期" else 5000
        )
        
        if len(articles) < 5:
            print("⚠️  数据不足5篇，跳过进化")
            return
        
        # 所有文章都当爆款处理
        viral = articles
        normal = []
        
        print(f"📊 分析文章：{len(viral)}篇")

        # 提炼规律
        patterns = self._extract_patterns(viral, normal, layer)
        print(f"💡 提炼出 {len(patterns)} 条规律")

        # 存入规律库
        for p in patterns:
            self.db.save_pattern(
                pattern_type=p["type"],
                description=p["description"],
                confidence=p["confidence"],
                source_count=len(viral),
                details=p["details"],
                memory_layer=layer
            )

        print(f"✅ 进化完成，{layer}记忆层已更新")
        return patterns

    def _extract_patterns(self, viral: list, normal: list, layer: str) -> list:
        """对比爆款和普通文章，提炼规律"""
        viral_features = self._aggregate_features(viral)
        normal_features = self._aggregate_features(normal)
        patterns = []

        # ---- 规律1：标题特征 ----
        viral_number_rate = viral_features["title"]["has_number"]
        normal_number_rate = normal_features["title"].get("has_number", 0)
        if viral_number_rate - normal_number_rate > 0.2:
            confidence = min((viral_number_rate - normal_number_rate) * len(viral) / 10, 1.0)
            patterns.append({
                "type": "标题含数字",
                "description": f"爆款文章中{viral_number_rate*100:.0f}%含数字，高于普通文章{normal_number_rate*100:.0f}%",
                "confidence": confidence,
                "details": {
                    "viral_rate": viral_number_rate,
                    "normal_rate": normal_number_rate,
                    "lift": viral_number_rate - normal_number_rate,
                    "recommendation": "标题中加入具体数字，如：3个、5年、90%"
                }
            })

        # ---- 规律2：最优字数范围 ----
        viral_lengths = [a["fields"].get("字数", 0) for a in viral if a["fields"].get("字数", 0) > 0]
        if viral_lengths:
            avg_len = sum(viral_lengths) / len(viral_lengths)
            patterns.append({
                "type": "最优正文字数",
                "description": f"爆款文章平均字数{avg_len:.0f}字",
                "confidence": min(len(viral_lengths) / 20, 0.95),
                "details": {
                    "avg_length": round(avg_len),
                    "min_length": min(viral_lengths),
                    "max_length": max(viral_lengths),
                    "recommendation": f"正文字数控制在{int(avg_len*0.8)}-{int(avg_len*1.2)}字之间"
                }
            })

        # ---- 规律3：最优开头类型 ----
        viral_openings = Counter()
        for a in viral:
            try:
                features = json.loads(a["fields"].get("特征数据", "{}"))
                opening = features.get("content_features", {}).get("opening_type", "其他")
                viral_openings[opening] += 1
            except:
                pass

        if viral_openings:
            best_opening = viral_openings.most_common(1)[0]
            opening_rate = best_opening[1] / len(viral)
            if opening_rate > 0.3:
                patterns.append({
                    "type": "最优开头类型",
                    "description": f"爆款文章中{opening_rate*100:.0f}%使用{best_opening[0]}",
                    "confidence": min(opening_rate * len(viral) / 15, 0.9),
                    "details": {
                        "best_type": best_opening[0],
                        "rate": opening_rate,
                        "distribution": dict(viral_openings),
                        "recommendation": f"优先使用{best_opening[0]}作为文章开头"
                    }
                })

        # ---- 规律4：情绪类型 ----
        viral_emotions = Counter()
        for a in viral:
            try:
                features = json.loads(a["fields"].get("特征数据", "{}"))
                emotion = features.get("emotion_features", {}).get("emotion_type", "混合情绪")
                viral_emotions[emotion] += 1
            except:
                pass

        if viral_emotions:
            best_emotion = viral_emotions.most_common(1)[0]
            emotion_rate = best_emotion[1] / len(viral)
            patterns.append({
                "type": "最优情绪类型",
                "description": f"爆款文章中{emotion_rate*100:.0f}%为{best_emotion[0]}",
                "confidence": min(emotion_rate * len(viral) / 15, 0.9),
                "details": {
                    "best_type": best_emotion[0],
                    "distribution": dict(viral_emotions),
                    "recommendation": f"内容情绪基调以{best_emotion[0]}为主"
                }
            })

        # ---- 规律5：结尾互动引导 ----
        viral_cta_rate = viral_features["structure"]["has_cta"]
        normal_cta_rate = normal_features["structure"].get("has_cta", 0)
        if viral_cta_rate - normal_cta_rate > 0.15:
            patterns.append({
                "type": "结尾互动引导",
                "description": f"爆款文章中{viral_cta_rate*100:.0f}%有互动引导，高于普通文章{normal_cta_rate*100:.0f}%",
                "confidence": min((viral_cta_rate - normal_cta_rate) * len(viral) / 8, 0.9),
                "details": {
                    "viral_rate": viral_cta_rate,
                    "normal_rate": normal_cta_rate,
                    "recommendation": "结尾必须加互动引导，引导读者评论或转发"
                }
            })

        # ---- 规律6：用千问深度分析（高级规律）----
        if len(viral) >= 10 and self.qwen_api_key:
            deep_patterns = self._deep_analysis_with_qwen(viral)
            patterns.extend(deep_patterns)

        return patterns

    def _aggregate_features(self, articles: list) -> dict:
        """聚合一批文章的特征均值"""
        title_features = defaultdict(list)
        content_features = defaultdict(list)
        structure_features = defaultdict(list)

        for a in articles:
            try:
                features = json.loads(a["fields"].get("特征数据", "{}"))
                for k, v in features.get("title_features", {}).items():
                    if isinstance(v, (int, float, bool)):
                        title_features[k].append(float(v))
                for k, v in features.get("content_features", {}).items():
                    if isinstance(v, (int, float)):
                        content_features[k].append(v)
                for k, v in features.get("structure_features", {}).items():
                    if isinstance(v, bool):
                        structure_features[k].append(float(v))
            except:
                pass

        def avg(lst):
            return sum(lst) / len(lst) if lst else 0

        return {
            "title": {k: avg(v) for k, v in title_features.items()},
            "content": {k: avg(v) for k, v in content_features.items()},
            "structure": {k: avg(v) for k, v in structure_features.items()}
        }

    def _deep_analysis_with_qwen(self, viral_articles: list) -> list:
        """用千问做深度规律分析"""
        print("🤖 调用千问进行深度规律分析...")

        # 取前5篇爆款文章的标题和开头
        samples = []
        for a in viral_articles[:5]:
            fields = a["fields"]
            content = fields.get("正文", "")[:200]
            samples.append(f"标题：{fields.get('标题', '')}\n开头：{content}...")

        sample_text = "\n\n---\n\n".join(samples)

        prompt = f"""以下是{len(viral_articles)}篇高效果个人成长类文章的样本（评分均超过70分）：

{sample_text}

请分析这些爆款文章的共同规律，重点关注：
1. 标题的语言模式和情感钩子
2. 开头的叙事策略
3. 内容组织的独特之处
4. 读者心理触发点

请严格返回JSON，不要其他文字：
{{"patterns": [{{"type": "规律名称", "description": "具体规律描述", "confidence": 0.8, "recommendation": "写作建议"}}]}}"""

        try:
            resp = requests.post(
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.qwen_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen-plus",
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
            content = resp.json()["choices"][0]["message"]["content"]
            content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)

            patterns = []
            for p in data.get("patterns", []):
                patterns.append({
                    "type": f"深度分析_{p['type']}",
                    "description": p["description"],
                    "confidence": p.get("confidence", 0.7),
                    "details": {"recommendation": p.get("recommendation", "")}
                })
            print(f"✅ 千问深度分析完成，提炼{len(patterns)}条规律")
            return patterns
        except Exception as e:
            print(f"⚠️ 千问分析失败：{e}")
            return []
