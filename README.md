# 🔥 HotSpot v3.6 - 全网热搜聚合器

HotSpot 是一个 **实时全网热搜聚合器**，使用 **Streamlit** 构建，可展示微博、B站、抖音、小红书等平台的热门内容。
v3.6 新增小红书热搜功能，并支持 **Playwright 视觉爬虫** 与 **API 数据抓取**。

---

## 🚀 功能特色

* **多平台热搜聚合**：

  * 微博热搜（微博网页端 + 微博移动端 API）
  * Bilibili 热搜（官方 API）
  * 抖音热榜（Tophub 视觉解析 + TenAPI 备用 API）
  * 小红书热搜（Tophub 视觉解析 + TenAPI 备用 API）

* **多引擎支持**：

  * **视觉爬虫**（Playwright）
  * **API 请求**（requests）

* **实时刷新**：

  * 默认缓存 5 分钟 (`st.cache_data(ttl=300)`)
  * 支持手动刷新按钮

* **日志追踪**：

  * 显示抓取状态、成功与失败信息
  * Playwright 状态提示

* **UI 优化**：

  * 四列布局，支持微博/B站/抖音/小红书同时显示
  * 热搜标题、排名、热度值、抓取引擎标识
  * 响应式设计，适配小屏幕

---

## ⚙️ 技术栈

* Python 3.9+
* [Streamlit](https://streamlit.io/)
* [Playwright](https://playwright.dev/python/)（可选，支持视觉抓取）
* [Requests](https://docs.python-requests.org/)
* [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)

---

## 📦 安装依赖

```bash
pip install streamlit requests beautifulsoup4
pip install playwright
playwright install
```

> Playwright 仅在需要视觉抓取时使用，如果仅依赖 API，可跳过。

---

## 💻 运行项目

在项目根目录下运行：

```bash
streamlit run app.py
```

* 页面默认显示四列热搜列表：

  * 🔴 微博热搜
  * 📺 Bilibili
  * 🎵 抖音热榜
  * 📕 小红书
* 侧边栏可查看日志和手动刷新数据。

---

## 📝 日志与调试

* 日志显示每个抓取模块的状态：

  * **绿色**：成功抓取
  * **红色**：抓取失败或异常
  * **蓝色**：信息性日志
* Playwright 可选，可显示 `✅ Ready` 或 `❌ Missing` 状态

---

## ⚡ 使用说明

* **缓存机制**：默认每 5 分钟刷新一次热搜数据
* **手动刷新**：点击侧边栏 “立即刷新” 按钮即可清空缓存并重新抓取
* **引擎标签**：

  * `Vis-PW`：Playwright 视觉抓取
  * `Vis-Hub`：Tophub 视觉抓取
  * `API`：API 请求抓取

---

## 🔗 链接示例

* 微博热搜：[https://s.weibo.com/top/summary](https://s.weibo.com/top/summary)
* 小红书搜索链接示例：[https://www.xiaohongshu.com/search_result?keyword=关键词&source=web_search_result_notes](https://www.xiaohongshu.com/search_result?keyword=关键词&source=web_search_result_notes)
* Bilibili 热搜：[https://search.bilibili.com/all?keyword=关键词](https://search.bilibili.com/all?keyword=关键词)
* 抖音搜索：[https://www.douyin.com/search/关键词](https://www.douyin.com/search/关键词)

---

## 📌 注意事项

1. Playwright 在 Windows 系统需设置：

```python
import asyncio
asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
```

2. 关闭 HTTPS 警告：

```python
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
```

3. 对于视觉抓取失败，可使用备用 API 数据源（TenAPI）。

---

## 🎯 未来计划

* 增加更多平台支持（知乎、贴吧等）
* 增加排序与筛选功能
* 增加历史趋势可视化
