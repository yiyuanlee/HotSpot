import streamlit as st
import requests
import urllib3
import time
import traceback
import json
import asyncio
import sys
import platform
import re
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup

# --- Windows 补丁 ---
if platform.system() == 'Windows':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError: pass

# Playwright 检查
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="HotSpot - 全网热搜", page_icon="🔥", layout="wide")

# === 初始化 session_state（深色模式） ===
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

def toggle_dark_mode():
    st.session_state.dark_mode = not st.session_state.dark_mode

# === 主题配色 ===
if st.session_state.dark_mode:
    bg_primary   = "#1e1e1e"
    bg_secondary = "#2d2d2d"
    bg_card      = "#252525"
    text_primary = "#e0e0e0"
    text_secondary= "#a0a0a0"
    border_color = "#3d3d3d"
    rank_top_bg  = "#ff6b6b"   # 前3名背景
    rank_mid_bg  = "#ffa500"   # 4-10名
else:
    bg_primary   = "#f5f7fa"
    bg_secondary = "#ffffff"
    bg_card      = "#ffffff"
    text_primary = "#1a1a1a"
    text_secondary= "#666666"
    border_color = "#e0e0e0"
    rank_top_bg  = "#ff4757"
    rank_mid_bg  = "#ff9f43"

# === 热度条颜色（根据平台）===
hot_bar_colors = {
    "weibo":  "#d63031",
    "bili":   "#00a1d6",
    "douyin": "#2d3436",
    "xhs":    "#ff2442",
    "zhihu":  "#0084ff",
}

# === 平台 Logo SVG（各平台官方风格）===
PLATFORM_LOGOS = {
    "weibo":  "🔴",
    "bili":   "📺",
    "douyin": "🎵",
    "xhs":    "📕",
    "zhihu":  "🔵",
}

# === 解析热度值为数值（用于热度条宽度）===
def parse_hot_value(hot_str):
    """把热度字符串转成数值，返回 0-100 的百分比。"""
    if not hot_str or hot_str in ("Hot", "热搜"):
        return 50
    s = str(hot_str).replace(",", "").replace(" ", "")
    # 尝试匹配万/亿单位
    m = re.search(r"([\d.]+)([万亿]|wan|yi)", s, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        unit = m.group(2)
        if unit in ("万", "wan"): val *= 10000
        elif unit in ("亿", "yi"): val *= 100000000
        # 归一化到 0-100（假设最大热度 1 亿）
        return min(int(val / 100000000 * 100), 100)
    # 纯数字
    m2 = re.search(r"^([\d.]+)$", s)
    if m2:
        return min(int(float(m2.group(1)) / 1000000 * 100), 100)
    return 50

# === CSS 样式 ===
st.markdown(f"""
<style>
    /* 全局背景 */
    .stApp {{ background-color: {bg_primary}; color: {text_primary}; }}

    /* 顶栏 */
    .main-header {{ font-size: 22px; font-weight: bold; padding: 8px 0 4px; color: {text_primary}; }}
    .main-caption {{ font-size: 12px; color: {text_secondary}; margin-bottom: 12px; }}

    /* 平台列容器 */
    .col-wrap {{
        background: {bg_card};
        border: 1px solid {border_color};
        border-radius: 10px;
        padding: 12px 10px;
        height: 100%;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    }}

    /* 平台标题栏 */
    .source-header {{
        font-size: 15px;
        font-weight: 700;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 2px solid #ddd;
        display: flex;
        align-items: center;
        gap: 6px;
        white-space: nowrap;
    }}
    .weibo-header {{ color: #d63031; border-color: #d63031; }}
    .bili-header   {{ color: #00a1d6; border-color: #00a1d6; }}
    .douyin-header {{ color: #2d3436; border-color: #2d3436; }}
    .xhs-header    {{ color: #ff2442; border-color: #ff2442; }}
    .zhihu-header  {{ color: #0084ff; border-color: #0084ff; }}

    /* 平台 Logo */
    .platform-logo {{ font-size: 18px; }}

    /* 排名徽章 */
    .rank-badge {{
        display: inline-block;
        width: 22px;
        height: 22px;
        line-height: 22px;
        text-align: center;
        border-radius: 50%;
        font-size: 11px;
        font-weight: bold;
        margin-right: 6px;
        color: white;
        flex-shrink: 0;
    }}
    .rank-1 {{ background: {rank_top_bg}; }}   /* 前3名红色系 */
    .rank-2 {{ background: {rank_top_bg}; opacity: 0.85; }}
    .rank-3 {{ background: {rank_top_bg}; opacity: 0.7; }}
    .rank-4 {{ background: {rank_mid_bg}; }}   /* 4-10名橙色系 */
    .rank-other {{ background: {text_secondary}; opacity: 0.5; }}

    /* 热搜条目 */
    .row-item {{
        margin-bottom: 9px;
        font-size: 13px;
        display: flex;
        align-items: center;
        gap: 4px;
        color: {text_primary};
    }}
    .row-item a {{
        color: {text_primary};
        text-decoration: none;
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}
    .row-item a:hover {{ color: #0084ff; }}

    /* 引擎标签 */
    .engine-tag {{
        font-size: 9px;
        padding: 1px 4px;
        border-radius: 3px;
        color: white;
        flex-shrink: 0;
    }}
    .vis-pw    {{ background-color: #6c5ce7; }}
    .vis-tophub{{ background-color: #e17055; }}
    .api-req   {{ background-color: #00b894; }}

    /* 热度条 */
    .hot-wrap {{
        display: flex;
        align-items: center;
        gap: 5px;
        flex-shrink: 0;
    }}
    .hot-bar-bg {{
        width: 50px;
        height: 4px;
        background: {border_color};
        border-radius: 2px;
        overflow: hidden;
    }}
    .hot-bar-fill {{
        height: 100%;
        border-radius: 2px;
        transition: width 0.3s ease;
    }}
    .hot-text {{
        font-size: 10px;
        color: {text_secondary};
        min-width: 36px;
        text-align: right;
    }}

    /* 空数据 */
    .empty-msg {{
        color: {text_secondary};
        font-size: 12px;
        text-align: center;
        padding: 20px 0;
    }}

    /* 侧边栏 */
    section[data-testid="stSidebar"] {{ background-color: {bg_card}; }}

    /* 链接 */
    a {{ color: #0084ff; }}
</style>
""", unsafe_allow_html=True)

st.title("🔥 HotSpot v4.0")
st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Playwright: {'✅ Ready' if PLAYWRIGHT_AVAILABLE else '❌ Missing'}")

if 'logs' not in st.session_state:
    st.session_state.logs = []

def log_msg(source, msg):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [{source}] {msg}")

# ---------------------------------------------------------
# 引擎: 视觉爬虫 & API
# ---------------------------------------------------------
def fetch_page_content(url, selector_to_wait=None, timeout=20):
    if not PLAYWRIGHT_AVAILABLE:
        return None, "No Lib"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout*1000)
                if selector_to_wait:
                    try:
                        page.wait_for_selector(selector_to_wait, timeout=5000)
                    except:
                        pass
                else:
                    page.wait_for_timeout(2000)
                content = page.content()
                browser.close()
                return content, "OK"
            except Exception as e:
                browser.close()
                return None, str(e)
    except Exception:
        return None, traceback.format_exc()

def fetch_api_requests(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
        return resp
    except Exception:
        return None

# ---------------------------------------------------------
# 数据源
# ---------------------------------------------------------

@st.cache_data(ttl=300)
def get_weibo_hot():
    """微博"""
    data = []
    if PLAYWRIGHT_AVAILABLE:
        html, info = fetch_page_content("https://s.weibo.com/top/summary", ".td-02")
        if html:
            try:
                soup = BeautifulSoup(html, "html.parser")
                rows = soup.select("td.td-02 > a")
                for idx, row in enumerate(rows):
                    title = row.get_text().strip()
                    link = row.get('href')
                    if link.startswith("/"):
                        link = "https://s.weibo.com" + link
                    if "javascript:void(0)" in link:
                        continue
                    hot = "Hot"
                    if row.parent and row.parent.find("span"):
                        hot = row.parent.find("span").get_text().strip()
                    data.append({"rank": idx, "title": title, "hot": hot, "link": link, "engine": "Vis-PW"})
                if data:
                    return data[1:21]
            except Exception as e:
                log_msg("Weibo", f"Vis Err: {e}")

    url = "https://m.weibo.cn/api/container/getIndex?containerid=106003type%3D25%26t%3D3%26disable_hot%3D1%26filter_type%3Drealtimehot"
    resp = fetch_api_requests(url)
    if resp and resp.status_code == 200:
        try:
            cards = resp.json()['data']['cards'][0]['card_group']
            for item in cards:
                if 'desc' not in item:
                    continue
                data.append({"rank": 0, "title": item['desc'], "hot": item.get('desc_entr', ''), "link": item['scheme'], "engine": "API-Mob"})
            return data[:20]
        except:
            pass
    return []

@st.cache_data(ttl=300)
def get_douyin_hot():
    """抖音"""
    data = []
    if PLAYWRIGHT_AVAILABLE:
        html, info = fetch_page_content("https://tophub.today/n/K7GdaMgdQy", "table")
        if html:
            try:
                soup = BeautifulSoup(html, "html.parser")
                rows = soup.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    rank = re.search(r'\d+', cells[0].get_text().strip())
                    if not rank:
                        continue
                    title_cell = cells[1]
                    link_tag = title_cell.find("a")
                    title = link_tag.get_text().strip() if link_tag else title_cell.get_text().strip()
                    link = link_tag.get('href') if link_tag else ""
                    if not link or "http" not in link:
                        safe_title = urllib.parse.quote(title)
                        link = f"https://www.douyin.com/search/{safe_title}"
                    hot = cells[2].get_text().strip() if len(cells) >= 3 else "Hot"
                    data.append({"rank": int(rank.group()), "title": title, "hot": hot, "link": link, "engine": "Vis-Hub"})
                if data:
                    return data[:20]
            except Exception as e:
                log_msg("Douyin", f"Vis Err: {e}")

    resp = fetch_api_requests("https://tenapi.cn/v2/douyinhot")
    if resp and resp.status_code == 200:
        try:
            for idx, item in enumerate(resp.json().get('data', [])[:20]):
                data.append({"rank": idx+1, "title": item['name'], "hot": str(item['hot']), "link": item['url'], "engine": "API"})
            return data
        except:
            pass
    return []

@st.cache_data(ttl=300)
def get_xhs_hot():
    """小红书"""
    data = []
    if PLAYWRIGHT_AVAILABLE:
        html, info = fetch_page_content("https://tophub.today/n/Jb0vmloB1G", "table")
        if html:
            try:
                soup = BeautifulSoup(html, "html.parser")
                rows = soup.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    rank = re.search(r'\d+', cells[0].get_text().strip())
                    if not rank:
                        continue
                    title_cell = cells[1]
                    link_tag = title_cell.find("a")
                    title = link_tag.get_text().strip() if link_tag else title_cell.get_text().strip()
                    safe_title = urllib.parse.quote(title)
                    link = f"https://www.xiaohongshu.com/search_result?keyword={safe_title}&source=web_search_result_notes"
                    hot = cells[2].get_text().strip() if len(cells) >= 3 else "Hot"
                    data.append({"rank": int(rank.group()), "title": title, "hot": hot, "link": link, "engine": "Vis-Hub"})
                if data:
                    return data[:20]
            except Exception as e:
                log_msg("XHS", f"Vis Err: {e}")

    resp = fetch_api_requests("https://tenapi.cn/v2/xiaohongshuhot")
    if resp and resp.status_code == 200:
        try:
            for idx, item in enumerate(resp.json().get('data', [])[:20]):
                data.append({"rank": idx+1, "title": item['name'], "hot": str(item['hot']), "link": item['url'], "engine": "API"})
            return data
        except:
            pass
    return []

@st.cache_data(ttl=300)
def get_zhihu_hot():
    """知乎"""
    data = []
    if PLAYWRIGHT_AVAILABLE:
        html, info = fetch_page_content("https://tophub.today/n/mproPpoq6O", "table")
        if html:
            try:
                soup = BeautifulSoup(html, "html.parser")
                rows = soup.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    rank = re.search(r'\d+', cells[0].get_text().strip())
                    if not rank:
                        continue
                    title_cell = cells[1]
                    link_tag = title_cell.find("a")
                    title = link_tag.get_text().strip() if link_tag else title_cell.get_text().strip()
                    hot = cells[2].get_text().strip() if len(cells) >= 3 else "Hot"
                    link = link_tag.get('href') if link_tag else ""
                    if not link or "http" not in link:
                        safe_title = urllib.parse.quote(title)
                        link = f"https://www.zhihu.com/search?type=content&q={safe_title}"
                    data.append({"rank": int(rank.group()), "title": title, "hot": hot, "link": link, "engine": "Vis-Hub"})
                if data:
                    return data[:20]
            except Exception as e:
                log_msg("Zhihu", f"Vis Err: {e}")

    resp = fetch_api_requests("https://tenapi.cn/v2/zhihuhot")
    if resp and resp.status_code == 200:
        try:
            for idx, item in enumerate(resp.json().get('data', [])[:20]):
                data.append({"rank": idx+1, "title": item['name'], "hot": str(item['hot']), "link": item['url'], "engine": "API"})
            return data
        except:
            pass
    return []

@st.cache_data(ttl=300)
def get_bilibili_hot():
    """B站"""
    url = "https://api.bilibili.com/x/web-interface/search/square?limit=20"
    resp = fetch_api_requests(url)
    data = []
    if resp and resp.status_code == 200:
        try:
            for idx, item in enumerate(resp.json()['data']['trending']['list']):
                data.append({"rank": idx+1, "title": item['keyword'], "hot": "热搜", "link": f"https://search.bilibili.com/all?keyword={item['keyword']}", "engine": "API"})
            return data
        except:
            pass
    return []

# ---------------------------------------------------------
# UI 渲染
# ---------------------------------------------------------
st.session_state.logs = []

PLATFORMS = [
    ("weibo",  "🔴 微博", "weibo-header",  "weibo",  get_weibo_hot),
    ("bili",   "📺 B站",  "bili-header",    "bili",   get_bilibili_hot),
    ("douyin", "🎵 抖音", "douyin-header",  "douyin", get_douyin_hot),
    ("xhs",    "📕 小红书","xhs-header",     "xhs",    get_xhs_hot),
    ("zhihu",  "🔵 知乎", "zhihu-header",   "zhihu",  get_zhihu_hot),
]

cols = st.columns(5)

for col, (key, title, css_cls, platform_key, func) in zip(cols, PLATFORMS):
    bar_color = hot_bar_colors[platform_key]
    logo = PLATFORM_LOGOS[platform_key]

    with col:
        st.markdown(f'<div class="col-wrap">', unsafe_allow_html=True)
        st.markdown(f'<div class="source-header {css_cls}"><span class="platform-logo">{logo}</span> {title.replace(logo+" ","")}</div>', unsafe_allow_html=True)

        data = func()
        if data:
            for item in data:
                rank = item.get('rank', 0)
                # 排名徽章样式
                if rank <= 3:
                    rank_cls = f"rank-{rank}"
                elif rank <= 10:
                    rank_cls = "rank-4"
                else:
                    rank_cls = "rank-other"

                tag = item.get('engine', '')
                css_tag = "vis-pw" if "Vis-PW" in tag else "vis-tophub" if "Hub" in tag else "api-req"
                link = item.get('link', '#')
                title_text = item.get('title', '')
                hot_str = item.get('hot', '')
                hot_pct = parse_hot_value(hot_str)

                st.markdown(f"""
                <div class="row-item">
                    <span class="rank-badge {rank_cls}">{rank}</span>
                    <a href="{link}" target="_blank">{title_text}</a>
                    <span class="engine-tag {css_tag}">{tag}</span>
                    <div class="hot-wrap">
                        <div class="hot-bar-bg">
                            <div class="hot-bar-fill" style="width:{hot_pct}%; background:{bar_color};"></div>
                        </div>
                        <span class="hot-text">{hot_str}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-msg">暂无数据</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
def force_reload():
    st.cache_data.clear()

with st.sidebar:
    st.header("⚙️ 设置")

    # 深色模式开关
    st.toggle("🌙 深色模式", value=st.session_state.dark_mode, on_change=toggle_dark_mode)

    st.divider()

    # 刷新按钮
    st.button("🔄 立即刷新", on_click=force_reload, use_container_width=True)

    st.divider()

    # 日志
    with st.expander("📋 日志", expanded=False):
        for l in st.session_state.logs:
            color = "green" if "Success" in l else "red" if "Err" in l or "Empty" in l else "blue"
            st.markdown(f":{color}[{l}]")

    st.divider()
    st.caption("HotSpot v4.0 · 全网热搜聚合器")
