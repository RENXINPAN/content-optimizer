# 内容进化引擎

一台可持续自我进化的个人成长公众号内容生产机器。

## 核心能力
- 从爆款文章中自动学习写作规律
- 三层记忆系统（短期/中期/长期）
- 自动进化写作Prompt
- 与Coze+微信公众号打通，手机对话式审核

## 环境变量配置
在GitHub仓库的 Settings → Secrets 中添加：
- AIRTABLE_API_KEY
- AIRTABLE_BASE_ID
- QWEN_API_KEY
- COZE_API_TOKEN
- COZE_BOT_ID
- COZE_USER_ID

## Airtable表结构
需要创建4张表：爆款文章库、规律库、Prompt版本库、生成内容库
（详见搭建文档）
