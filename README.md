🔥 HotSpot

HotSpot 是一个极简、纯净的全网热搜实时聚合工具。

在这个算法推荐泛滥的时代，HotSpot 帮你过滤噪音。它通过实时抓取主流社交平台的官方热榜，清洗广告与推广内容，让你在一个页面就能通过“上帝视角”俯瞰全网热点。

✨ 核心特性

🚀 多源聚合：目前已支持 微博热搜 (Weibo) 和 知乎热榜 (Zhihu)，更多平台接入中。

⚡ 实时更新：直连官方 API，每 5 分钟自动刷新一次数据，确保你看到的永远是最新鲜的资讯。

🛡️ 纯净无广：内置过滤算法，自动剔除热搜榜中的“商业推广”、“置顶广告”等干扰项。

🌊 极速体验：基于 Streamlit 构建，配合智能缓存机制，秒级加载，拒绝卡顿。

📱 全端适配：响应式布局设计，无论是电脑大屏还是手机移动端，体验同样丝滑。

🚀 快速开始

只需要 3 步，你就可以在本地拥有自己的热搜看板。

1. 克隆项目

git clone [https://github.com/your-username/HotSpot.git](https://github.com/your-username/HotSpot.git)
cd HotSpot


2. 安装依赖

建议使用 Python 3.8 或以上版本。

pip install requests streamlit pandas


3. 启动应用

streamlit run hotspot.py


运行成功后，浏览器会自动打开 http://localhost:8501。

🛠️ 技术栈

本项目适合 Python 新手学习和练手，代码结构清晰。

核心语言: Python 3

Web 框架: Streamlit (极速构建数据应用)

网络请求: Requests (模拟浏览器抓取)

数据处理: Pandas (预留用于后续的数据清洗与分析)

🗺️ 开发路线图 (Roadmap)

我们要做的不仅是一个聚合器，而是一个互联网趋势观察室。

 数据源扩展: 接入 Bilibili 热门、GitHub Trending、百度热搜、少数派等。

 历史回溯: 引入 SQLite 数据库，支持查看“昨天/上周”的热搜存档。

 AI 总结: 接入大模型 API，一键总结热搜事件的前因后果。

 情绪分析: 分析热搜标题的情绪正负面，生成“今日互联网情绪指数”。

 暗黑模式: 优化 UI 细节，支持夜间模式切换。

🤝 参与贡献

开源社区因为有你才精彩！如果你发现了 Bug，或者想添加一个新的数据源（比如 B 站），欢迎提交 Pull Request。

Fork 本仓库

新建分支 (git checkout -b feature/NewFeature)

提交修改 (git commit -m 'Add some NewFeature')

推送分支 (git push origin feature/NewFeature)

提交 Pull Request

📄 开源协议

本项目基于 MIT License 开源，这意味着你可以免费用于个人学习或商业用途。
