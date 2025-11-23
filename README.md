# 🔥 HotSpot -- Trending Aggregator

HotSpot 是一个基于 **Streamlit** 构建的轻量级实时热搜聚合器（Trending
Aggregator）。 它支持从 **微博热搜榜** 与 **知乎热榜**
自动抓取最新热度数据，并以简洁、美观的 UI 展示。

## ✨ Features

-   实时抓取微博热搜
-   实时抓取知乎热榜
-   每 5 分钟自动刷新缓存
-   手动刷新功能
-   双列页面布局，简洁优雅
-   自定义 CSS 样式增强 UI

## 🛠️ Tech Stack

-   Python 3.x
-   Streamlit
-   Requests
-   Pandas
-   Datetime

## 🚀 Getting Started

### 1. 克隆项目

``` bash
git clone https://github.com/your-repo/hotspot.git
cd hotspot
```

### 2. 安装依赖

``` bash
pip install -r requirements.txt
```

### 3. 运行应用

``` bash
streamlit run app.py
```

## 📂 Project Structure

    hotspot/
    │── app.py
    │── requirements.txt
    │── README.md

## 📜 License

MIT License
