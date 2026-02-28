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
  - `.github/workflows/crawl.yml` — 抓取工作流
  - `.github/workflows/daily.yml` — 每日生成工作流

### Airtable
- Base ID：`apphDOxCslstliiKO`
- 4张表：
  - `articles` — 存储抓取的文章（字段：标题、正文、来源、发布时间等）
  - `patterns` — 提取的写作规律
  - `prompts` — 历次Prompt版本
  - `contents` — 每日生成的内容

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
- 充值账户：需要余额才能使用
- 接口地址：`https://www.dajiala.com/fbmain/monitor/v3`

### 接口价格
| 接口 | 价格 |
|------|------|
| 历史文章列表（post_history） | 0.06-0.08元/次 |
| 文章详情（article_detail） | 0.045元/次 |

### 目标公众号
```python
TARGET_ACCOUNTS = [
    "刘润",
    "S叔Spenser", 
    "武志红",
    "半佛仙人",
]
```

### 触发抓取
在GitHub Actions手动触发 `crawl.yml`，输入参数为每账号抓取篇数（建议填50或100）。

### 已知问题与解决方案
1. **SSL证书问题** → `verify=False` 已加入代码
2. **API返回code=0表示成功**（不是200）→ 已修复
3. **详情接口返回HTML**，需用正则清理标签 → 已修复
4. **正文判断阈值** → 设为50字符，避免误判
5. **文章开头含标题/作者/Tips等模板内容** → 不影响AI分析，直接存入

---

## 每日工作流

`daily.yml` 每天自动运行，流程：
1. 调用通义千问生成当日内容
2. 存入Airtable `contents` 表
3. 积累5篇以上自动触发进化引擎

---

## 后续待做

- [ ] 接入Coze，实现内容自动推送微信
- [ ] 加入文章去重逻辑（避免重复抓取消耗费用）
- [ ] 抓取文章阅读量/点赞数，筛选真正爆款
- [ ] 扩展更多目标公众号

---

## 调试历史（给新Claude看）

### 问题排查记录
- API POST请求需要JSON body，不是URL参数
- `post_history` 返回的 `data` 直接是数组，不需要 `.get("list")`
- 文章详情返回的是完整HTML页面，字段名为 `content` 或 `html`
- Airtable表名全部为英文（articles/patterns/prompts/contents），字段名为中文（标题、正文等）

### 常见报错
| 报错 | 原因 | 解决 |
|------|------|------|
| SSL证书错误 | GitHub Actions环境问题 | requests加verify=False |
| 403 Airtable | Token权限或字段名问题 | 检查Secret是否正确传入workflow env |
| 正文太短跳过 | HTML未清理 / 阈值太高 | 用re清理HTML标签，阈值改50 |

---

## 联系方式

如有问题，把这份README发给新的Claude，他能快速了解项目背景接手工作。
