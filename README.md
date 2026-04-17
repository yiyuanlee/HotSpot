# 🔥 HotSpot v4.1 - 全网热搜聚合器

HotSpot 是一个 **实时全网热搜聚合器**，使用 **Streamlit** 构建，支持微博、B站、抖音、小红书、知乎五大平台，并提供 **历史趋势分析**。

---

## ✨ 功能特色

### 实时热搜
- 🔴 微博热搜 · 📺 B站热搜 · 🎵 抖音热榜 · 📕 小红书热搜 · 🔵 知乎热搜
- 每条热搜显示**排名**、**热度值**、**抓取引擎标识**
- 热度进度条直观展示热度对比
- 排名前 3 名高亮标识

### 历史趋势 📈（v4.0+ 新增）
- 每次抓取自动存入本地 SQLite 数据库
- 查看任意话题在任意平台的历史上榜轨迹
- 热门话题排行榜（按上榜次数 / 巅峰排名排序）
- 折线图展示话题排名变化趋势
- 支持 1 / 3 / 7 / 14 天时间范围筛选

### UI 体验（v4.0+ 优化）
- 🌙 **深色模式**（侧边栏一键切换）
- 四列卡片布局，每列独立圆角卡片 + 平台品牌色标题
- 响应式设计，适配不同屏幕尺寸

### 多引擎兜底
- **视觉爬虫**（Playwright）优先，成功率更高
- **API 请求**（requests）兜底，极速响应
- 引擎标签：`Vis-PW` / `Vis-Hub` / `API`

---

## 🚀 快速开始

```bash
git clone https://github.com/yiyuanlee/HotSpot.git
cd HotSpot
pip install streamlit requests beautifulsoup4 matplotlib pandas
streamlit run hotspot.py
```

> Playwright 可选（支持视觉抓取）：
> ```bash
> pip install playwright
> playwright install
> ```

---

## 📂 项目结构

```
HotSpot/
├── hotspot.py          # 主程序（v4.1）
├── hotspot_history.db  # SQLite 历史数据库（运行后自动生成）
├── README.md
└── start.py            # 启动脚本
```

---

## 🖥️ 使用说明

### 视图切换
侧边栏提供两种视图：

| 视图 | 说明 |
|------|------|
| ⚡ 实时热搜 | 当前各平台实时热搜榜 |
| 📈 历史趋势 | 话题历史轨迹、热门话题排行、趋势折线图 |

### 侧边栏功能
- 🌙 深色模式开关
- 📊 视图切换
- 🔄 立即刷新（清空缓存重新抓取）
- 📋 日志面板

### 引擎标签
| 标签 | 含义 |
|------|------|
| `Vis-PW` | Playwright 视觉爬虫 |
| `Vis-Hub` | Tophub 视觉解析 |
| `API` | API 请求直接抓取 |
| `API-Mob` | 微博移动端 API |

---

## 🛠️ 技术栈

- **Python 3.9+**
- [Streamlit](https://streamlit.io/) — Web UI
- [SQLite](https://docs.python.org/3/library/sqlite3.html) — 历史数据存储（Python 内置）
- [Matplotlib](https://matplotlib.org/) — 趋势图绘制
- [Pandas](https://pandas.pydata.org/) — 数据表格
- [Playwright](https://playwright.dev/python/)（可选）
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) — HTML 解析
- [Requests](https://docs.python-requests.org/) — HTTP 请求

---

## ⚠️ 注意事项

1. Windows 系统运行 Playwright 需设置：
   ```python
   import asyncio
   asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
   ```
2. 数据源来自各平台公开接口，部分平台可能存在访问限制
3. 历史趋势数据需要运行一段时间后才会丰富（每小时自动快照）

---

## 📌 版本历史

| 版本 | 更新内容 |
|------|----------|
| v4.1 | 历史趋势视图、SQLite 持久化、热门话题统计表、趋势折线图 |
| v4.0 | 深色模式、卡片布局、热度进度条、排名徽章、知乎支持 |
| v3.6 | 小红书热搜、Playwright 视觉爬虫 |

---

## 🔗 相关链接

- 微博热搜：https://s.weibo.com/top/summary
- 小红书搜索：https://www.xiaohongshu.com
- B站搜索：https://search.bilibili.com
- 抖音搜索：https://www.douyin.com
