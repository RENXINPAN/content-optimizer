# 内容进化引擎 - 项目说明文档

> 如果你是新的Claude，请先读完这份文档，再开始帮用户处理问题。

---

## 项目简介

这是一套**自动化内容生成系统**，通过抓取爆款公众号文章，分析规律，自动进化写作Prompt，最终生成高质量内容。

**核心流程：**
```
抓取爆款文章 → 提取写作规律 → 进化Prompt → 生成新内容 → 推送微信
```

---

## 基础设施

### GitHub仓库
- 地址：`RENXINPAN/content-optimizer`
- 主要文件：
  - `crawler.py` — 公众号历史文章抓取
  - `ingestion.py` — 文章特征提取入库
  - `evolution.py` — 进化引擎
  - `prompt_builder.py` — Prompt构建
  - `main.py` — 主流程调度器
  - `airtable.py` — Airtable数据读写客户端
  - `.github/workflows/crawl.yml` — 抓取工作流
  - `.github/workflows/daily.yml` — 每日生成工作流

### Airtable
- Base ID：`apphDOxCslstliiKO`
- Base名称：**内容进化系统**
- 4张表（表名必须和代码完全一致）：

| Airtable表名 | 代码中的名称 | 用途 |
|------------|------------|------|
| 爆款文章库 | 爆款文章库 | 存储抓取的文章 |
| patterns | patterns | 提取的写作规律 |
| prompts | prompts | Prompt版本库 |
| contents | contents | 每日生成的内容 |

**注意：爆款文章库用中文名，其余三张表用英文名！**

### 爆款文章库字段
- 标题、正文、来源、url、入库时间、状态、特征数据

### GitHub Secrets（已配置）
| 名称 | 用途 |
|------|------|
| `AIRTABLE_API_KEY` | Airtable访问密钥 |
| `AIRTABLE_BASE_ID` | Airtable库ID |
| `QWEN_API_KEY` | 通义千问API |
| `WXAPI_KEY` | 极致了公众号API |

---

## 爬虫说明

### 使用的API服务
- 服务商：**极致了**（dajiala.com）
- 接口地址：`https://www.dajiala.com/fbmain/monitor/v3`

### 接口价格
| 接口 | 价格 |
|------|------|
| 历史文章列表（post_history） | 0.06-0.08元/次，每次20篇 |
| 文章详情（article_detail） | 0.045元/次 |
| 去重查Airtable | 免费 |

### 费用估算
- 每篇文章成本约0.05元
- 每账号抓500篇约25元
- 4个账号共约100元

### 目标公众号
```python
TARGET_ACCOUNTS = [
    "刘润",
    "香港S叔",   # 注意：不是"S叔Spenser"，已改名
    "武志红",
    "半佛仙人",
]
```

### 触发抓取
在GitHub Actions手动触发`crawl.yml`，输入参数为每账号抓取篇数。

---

## 运行命令

```bash
python main.py generate   # 每日内容生成
python main.py evolve     # 每周进化（分析规律）
python main.py ingest     # 手动摄入单篇文章
python main.py feedback   # 处理效果数据回流
```

---

## 三层记忆系统

| 层级 | 分析篇数 | 用途 |
|------|---------|------|
| 短期 | 10篇 | 当前热点趋势，时效性强 |
| 中期 | 50篇 | 近期稳定规律 |
| 长期 | 3000篇 | 底层稳定规律 |

生成内容时三层规律叠加使用，长期打底+中期调整+短期微调。

---

## 已知问题与解决方案

### 1. 表名问题（重要！）
代码里部分表用中文名，部分用英文名，混用会导致403错误：
- `爆款文章库` — 中文
- `patterns`、`prompts`、`contents` — 英文

如果报403且错误信息是`INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND`，第一步先检查表名是否匹配！

### 2. Airtable URL字段
爆款文章库里有`url`字段，类型为URL，**不能传空字符串**，代码里已做保护：
```python
if url:
    fields["url"] = url
```

### 3. 翻页限制
Airtable单次请求最多返回100条，`get_all_articles`已实现翻页逻辑，可获取全部文章。

### 4. 进化引擎无综合分数
抓取的文章没有阅读量/点赞数，所以没有综合分数。已将所有文章都当爆款处理，直接分析规律。

### 5. 爬虫翻页限制
原代码限制最多翻20页（400篇），已改为200页，确保能抓到足够文章。

### 6. SSL证书问题
极致了API在GitHub Actions环境下SSL验证失败，所有请求已加`verify=False`。

### 7. API返回码
极致了API返回`code=0`表示成功，不是`code=200`。

### 8. pageSize限制
Airtable的`pageSize`最大100，超过会报422错误。

---

## 后续待做

- [ ] 清理DEBUG代码（现在日志很乱）
- [ ] 接入Coze，实现内容推送微信审核
- [ ] 抓取文章阅读量/点赞数，实现真正的爆款筛选
- [ ] 输入一句核心观点自动扩展成完整文章
- [ ] 多平台输出（公众号/小红书/微博）
- [ ] 小说创作系统

---

## 当前数据状态

- 已入库文章：约2152篇（刘润156篇、香港S叔53篇、武志红、半佛仙人等）
- 已提取规律：短期3条、中期3条、长期8条
- 内容生成：已跑通，每次生成存入contents表

---

## 给新Claude的接手说明

1. 先看这份README了解全貌
2. 如果报403，先检查表名是否匹配（最常见问题）
3. 如果进化引擎跳过，检查文章是否有`特征数据`字段
4. 如果内容没存进去，检查`contents`表名是否正确
5. 遇到缩进报错，让用户用Tab键选中整块缩进
6. 调试时在`_request`方法加`print(f"DEBUG错误详情: {resp.status_code} {resp.text}")`看具体错误原因
