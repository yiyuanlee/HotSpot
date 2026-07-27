# 🔥 HotSpot — 全网热搜 + 飞书每日 Digest

抓取微博 / B站 / 抖音 / 小红书 / 知乎热搜，支持：

1. **Streamlit 看板**（原实时 + 历史趋势）
2. **每日 9:00 Agent**（各平台 Top10 + AI 一句话摘要 → 推送飞书）

---

## 🤖 飞书每日 Digest（推荐）

每天北京时间 **09:00** 自动抓取各平台 Top10，生成一句 AI 摘要，发到飞书群。

### 1. 配置飞书机器人

1. 打开目标飞书群 → **设置** → **群机器人** → **添加自定义机器人**
2. 复制 Webhook 地址（形如 `https://open.feishu.cn/open-apis/bot/v2/hook/...`）

### 2. 本地试跑

```bash
git clone https://github.com/yiyuanlee/HotSpot.git
cd HotSpot
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 FEISHU_WEBHOOK_URL；可选填 OPENAI_API_KEY
```

```bash
# 只打印卡片 JSON，不发送
python digest_agent.py --dry-run

# 真正推送到飞书
python digest_agent.py
```

### 3. GitHub Actions 定时（每天 9:00）

仓库已包含 `.github/workflows/daily-digest.yml`（UTC 01:00 = 北京时间 09:00）。

在 GitHub 仓库 **Settings → Secrets and variables → Actions** 添加：

| Secret | 必填 | 说明 |
|--------|------|------|
| `FEISHU_WEBHOOK_URL` | ✅ | 飞书机器人 Webhook |
| `OPENAI_API_KEY` | 推荐 | 用于 AI 摘要；不填则用规则摘要 |
| `OPENAI_BASE_URL` | 可选 | 默认 `https://api.openai.com/v1`，可换成 DeepSeek 等兼容地址 |
| `OPENAI_MODEL` | 可选 | 默认 `gpt-4o-mini` |

推送后可在 **Actions** 页手动点 **Run workflow** 立刻测一次。

> **注意：** 未配置 `FEISHU_WEBHOOK_URL` 时任务会在启动阶段直接失败（避免静默空跑）。  
> 未配置 `OPENAI_API_KEY` 时仍会推送，摘要为基于各平台第 1 名的规则句子。

### 可靠性

- Workflow 启动前校验必填 Secret
- 单平台抓取失败会重试 3 次；失败不影响其他平台
- 飞书推送失败会重试 3 次；仍失败时尝试发送失败告警卡片
- `DIGEST_MIN_OK_PLATFORMS`：至少成功几个平台才推送（默认 1）

### 环境变量一览

见 [`.env.example`](.env.example)。

---

## 🖥️ Streamlit 看板（可选）

```bash
pip install -r requirements.txt
streamlit run hotspot.py
```

Playwright 可选（提高视觉抓取成功率）：

```bash
pip install playwright
playwright install
```

### 看板能力

- 实时热搜：微博 / B站 / 抖音 / 小红书 / 知乎
- 历史趋势：SQLite 快照、话题排行、折线图
- 深色模式、多引擎兜底（Vis-PW / Vis-Hub / API）

---

## 📂 项目结构

```
HotSpot/
├── digest_agent.py     # 飞书每日 Digest Agent（主入口）
├── fetcher.py          # 各平台抓取逻辑（无 UI 依赖）
├── hotspot.py          # Streamlit 看板
├── hotspot_history.py  # 历史相关脚本
├── requirements.txt
├── .env.example
└── .github/workflows/daily-digest.yml
```

---

## 🛠️ 技术栈

- Python 3.9+
- Requests + BeautifulSoup4 — 抓取
- OpenAI 兼容 Chat Completions — AI 摘要
- 飞书自定义机器人 Webhook — 消息推送
- GitHub Actions — 定时调度
- Streamlit / SQLite / Matplotlib — 可选看板

---

## ⚠️ 注意事项

1. 数据源来自各平台公开页面/接口，可能偶发失败或限流
2. 飞书 Webhook、API Key 请用 Secrets / `.env`，不要提交到仓库
3. GitHub 免费仓库的 schedule 可能有数分钟延迟，属正常现象
4. Windows 下若使用 Playwright，需 Proactor 事件循环策略（代码已处理）

---

## 📌 版本历史

| 版本 | 更新内容 |
|------|----------|
| v5.1 | Secrets 启动校验、抓取/推送重试、单平台容错、失败告警卡片 |
| v5.0 | 飞书每日 Digest Agent、AI 摘要、GitHub Actions 定时、抓取逻辑抽离 `fetcher.py` |
| v4.1 | 历史趋势视图、SQLite 持久化、热门话题统计表、趋势折线图 |
| v4.0 | 深色模式、卡片布局、热度进度条、排名徽章、知乎支持 |
| v3.6 | 小红书热搜、Playwright 视觉爬虫 |

---

## 🔗 相关链接

- 微博热搜：https://s.weibo.com/top/summary
- 小红书搜索：https://www.xiaohongshu.com
- B站搜索：https://search.bilibili.com
- 抖音搜索：https://www.douyin.com
- 飞书机器人文档：https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
