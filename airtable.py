# airtable.py - Airtable数据读写客户端

import os
import requests
import json
from datetime import datetime
from typing import Optional

class AirtableClient:
    def __init__(self):
        self.api_key = os.environ.get("AIRTABLE_API_KEY")
        self.base_id = os.environ.get("AIRTABLE_BASE_ID")
        self.base_url = f"https://api.airtable.com/v0/{self.base_id}"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _request(self, method, table, data=None, params=None, record_id=None):
        url = f"{self.base_url}/{table}"
        if record_id:
            url = f"{url}/{record_id}"
        print(f"DEBUG请求: method={method}, url={url}, data={str(data)[:200]}")
        resp = requests.request(method, url, headers=self.headers, json=data, params=params)
        if not resp.ok:
            print(f"DEBUG错误详情: {resp.status_code} {resp.text}")
            resp.raise_for_status()
        return resp.json()

    # ==================== 爆款文章库 ====================

    def add_article(self, title: str, content: str, source: str = "手动上传", url: str = "") -> str:
        """新增一篇爆款文章，返回记录ID"""
        fields = {
            "标题": title,
            "正文": content,
            "来源": source,
            "入库时间": datetime.now().isoformat(),
            "状态": "待分析"
        }
       
        data = {"fields": fields}
        result = self._request("POST", "articles", data=data)
        return result["id"]

    def get_unanalyzed_articles(self) -> list:
        """获取所有待分析的文章"""
        params = {
            "filterByFormula": '{状态} = "待分析"',
            "pageSize": 100
        }
        result = self._request("GET", "articles", params=params)
        return result.get("records", [])

    def update_article_features(self, record_id: str, features: dict):
        """更新文章的特征提取结果"""
        data = {
            "fields": {
                "特征数据": json.dumps(features, ensure_ascii=False),
                "状态": "已分析",
                "分析时间": datetime.now().isoformat()
            }
        }
        self._request("PATCH", "articles", data=data, record_id=record_id)

    def update_article_score(self, record_id: str, read_count: int,
                              like_count: int, share_count: int, collect_count: int):
        """更新文章的效果数据并计算综合分数"""
        # 归一化分数（假设满分参考值）
        read_score = min(read_count / 10000, 1.0)
        like_rate = like_count / max(read_count, 1)
        share_rate = share_count / max(read_count, 1)
        collect_rate = collect_count / max(read_count, 1)

        # 综合分数公式
        score = (read_score * 0.25 + like_rate * 0.25 +
                 collect_rate * 0.35 + share_rate * 0.15) * 100

        data = {
            "fields": {
                "阅读量": read_count,
                "点赞数": like_count,
                "转发数": share_count,
                "收藏数": collect_count,
                "综合分数": round(score, 2),
                "是否爆款": score >= 70,
                "数据更新时间": datetime.now().isoformat()
            }
        }
        self._request("PATCH", "articles", data=data, record_id=record_id)

    def get_articles_with_scores(self, limit: int = 200) -> list:
        """获取已有效果数据的文章（用于训练）"""
        params = {
            "filterByFormula": 'AND({状态} = "已分析", {综合分数} > 0)',
            "pageSize": limit,
            "sort[0][field]": "入库时间",
            "sort[0][direction]": "desc"
        }
        result = self._request("GET", "articles", params=params)
        return result.get("records", [])

    def get_recent_viral_articles(self, limit: int = 10) -> list:
        """获取最近的爆款文章（短期记忆）"""
        params = {
            "filterByFormula": 'AND({是否爆款} = 1, {综合分数} >= 70)',
            "pageSize": limit,
            "sort[0][field]": "入库时间",
            "sort[0][direction]": "desc"
        }
        result = self._request("GET", "articles", params=params)
        return result.get("records", [])

    # ==================== 规律库 ====================

    def save_pattern(self, pattern_type: str, description: str,
                     confidence: float, source_count: int,
                     details: dict, memory_layer: str = "中期") -> str:
        """保存或更新一条规律"""
        # 先检查是否已有同类规律
        params = {
            "filterByFormula": f'AND({{规律类型}} = "{pattern_type}", {{记忆层}} = "{memory_layer}")'
        }
        existing = self._request("GET", "patterns", params=params)
        records = existing.get("records", [])

        fields = {
            "规律类型": pattern_type,
            "规律描述": description,
            "置信度": round(confidence, 4),
            "来源文章数": source_count,
            "规律详情": json.dumps(details, ensure_ascii=False),
            "记忆层": memory_layer,
            "最后更新": datetime.now().isoformat()
        }

        if records:
            # 更新已有规律
            self._request("PATCH", "patterns", data={"fields": fields}, record_id=records[0]["id"])
            return records[0]["id"]
        else:
            # 新建规律
            result = self._request("POST", "patterns", data={"fields": fields})
            return result["id"]

    def get_all_patterns(self) -> list:
        """获取所有规律（用于构建Prompt）"""
        params = {
            "sort[0][field]": "置信度",
            "sort[0][direction]": "desc",
            "pageSize": 100
        }
        result = self._request("GET", "patterns", params=params)
        return result.get("records", [])

    def get_patterns_by_layer(self, layer: str) -> list:
        """按记忆层获取规律"""
        params = {
            "filterByFormula": f'{{记忆层}} = "{layer}"',
            "sort[0][field]": "置信度",
            "sort[0][direction]": "desc"
        }
        result = self._request("GET", "patterns", params=params)
        return result.get("records", [])

    # ==================== Prompt版本库 ====================

    def save_prompt_version(self, prompt_content: str, version: str,
                             pattern_count: int, evolution_notes: str) -> str:
        """保存新版本的Prompt"""
        data = {
            "fields": {
                "版本号": version,
                "Prompt内容": prompt_content,
                "基于规律数量": pattern_count,
                "进化说明": evolution_notes,
                "创建时间": datetime.now().isoformat(),
                "状态": "当前版本"
            }
        }
        # 把旧版本标记为历史
        self._archive_old_prompts()
        result = self._request("POST", "prompts", data=data)
        return result["id"]

    def _archive_old_prompts(self):
        """把当前版本标记为历史版本"""
        params = {"filterByFormula": '{状态} = "当前版本"'}
        existing = self._request("GET", "prompts", params=params)
        for record in existing.get("records", []):
            self._request("PATCH", "prompts",
                         data={"fields": {"状态": "历史版本"}},
                         record_id=record["id"])

    def get_current_prompt(self) -> Optional[dict]:
        """获取当前使用的Prompt"""
        params = {"filterByFormula": '{状态} = "当前版本"'}
        result = self._request("GET", "prompts", params=params)
        records = result.get("records", [])
        return records[0] if records else None

    def update_prompt_performance(self, record_id: str, avg_score: float):
        """更新Prompt的平均效果分数"""
        self._request("PATCH", "prompts",
                     data={"fields": {"平均效果分数": round(avg_score, 2)}},
                     record_id=record_id)

    # ==================== 生成内容库 ====================

    def save_generated_content(self, title: str, content: str,
                                prompt_version: str, predicted_score: float) -> str:
        """保存生成的内容"""
        data = {
            "fields": {
                "标题": title,
                "正文": content,
                "使用Prompt版本": prompt_version,
                "预测分数": round(predicted_score, 2),
                "状态": "待审核",
                "生成时间": datetime.now().isoformat()
            }
        }
        result = self._request("POST", "contents", data=data)
        return result["id"]

    def update_content_actual_score(self, record_id: str, actual_score: float):
        """更新内容的实际效果分数"""
        self._request("PATCH", "contents",
                     data={"fields": {
                         "实际分数": round(actual_score, 2),
                         "偏差值": round(actual_score - self._get_predicted_score(record_id), 2),
                         "状态": "已发布"
                     }},
                     record_id=record_id)

    def _get_predicted_score(self, record_id: str) -> float:
        result = self._request("GET", "contents", record_id=record_id)
        return result.get("fields", {}).get("预测分数", 0)

    def get_pending_review_content(self) -> list:
        """获取待审核的内容"""
        params = {"filterByFormula": '{状态} = "待审核"'}
        result = self._request("GET", "contents", params=params)
        return result.get("records", [])
