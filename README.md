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

st.markdown("""
<style>
    .source-header { font-size: 18px; font-weight: bold; margin-bottom: 10px; border-bottom: 2px solid #ddd; white-space: nowrap; }
    
    .weibo-header { color: #d63031; border-color: #d63031; }
    .bili-header { color: #00a1d6; border-color: #00a1d6; }
    .douyin-header { color: #2d3436; border-color: #2d3436; }
    .xhs-header { color: #ff2442; border-color: #ff2442; }
    .zhihu-header { color: #0084ff; border-color: #0084ff; }
    
    .rank-badge { display: inline-block; width: 20px; text-align: center; margin-right: 2px; color: #999; font-weight: bold; font-size: 14px; }
    .row-item { margin-bottom: 5px; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
    
    .engine-tag { font-size: 9px; padding: 1px 3px; border-radius: 3px; margin-left: 3px; color: white; vertical-align: middle; opacity: 0.8; }
    .vis-pw { background-color: #6c5ce7; }
    .vis-tophub { background-color: #e17055; }
    .api-req { background-color: #00b894; }
    
    a { text-decoration: none; color: #333; }
    a:hover { color: #0084ff; }
    
    @media (max-width: 1400px) {
        .row-item { font-size: 12px; }
        .source-header { font-size: 16px; }
    }
</style>
""", unsafe_allow_html=True)

st.title("🔥 HotSpot v3.9 (Smooth Refresh)")
st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} | PW: {'✅ Ready' if PLAYWRIGHT_AVAILABLE else '❌ Missing'}")

if 'logs' not in st.session_state: st.session_state.logs = []
def log_msg(source, msg):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [{source}] {msg}")

# ---------------------------------------------------------
# 引擎: 视觉爬虫 & API
# ---------------------------------------------------------
def fetch_page_content(url, selector_to_wait=None, timeout=20):
    if not PLAYWRIGHT_AVAILABLE: return None, "No Lib"
    
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
                    try: page.wait_for_selector(selector_to_wait, timeout=5000)
                    except: pass
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
    except Exception as e:
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
                    if link.startswith("/"): link = "https://s.weibo.com" + link
                    if "javascript:void(0)" in link: continue 
                    hot = "Hot"
                    if row.parent and row.parent.find("span"): hot = row.parent.find("span").get_text().strip()
                    data.append({"rank": idx, "title": title, "hot": hot, "link": link, "engine": "Vis-PW"})
                if data: return data[1:21]
            except Exception as e: log_msg("Weibo", f"Vis Err: {e}")

    url = "https://m.weibo.cn/api/container/getIndex?containerid=106003type%3D25%26t%3D3%26disable_hot%3D1%26filter_type%3Drealtimehot"
    resp = fetch_api_requests(url)
    if resp and resp.status_code == 200:
        try:
            cards = resp.json()['data']['cards'][0]['card_group']
            for item in cards:
                if 'desc' not in item: continue
                data.append({"rank": 0, "title": item['desc'], "hot": item.get('desc_entr', ''), "link": item['scheme'], "engine": "API-Mob"})
            return data[:20]
        except: pass
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
                    if len(cells) < 2: continue
                    rank = re.search(r'\d+', cells[0].get_text().strip())
                    if not rank: continue
                    
                    title_cell = cells[1]
                    link_tag = title_cell.find("a")
                    title = link_tag.get_text().strip() if link_tag else title_cell.get_text().strip()
                    link = link_tag.get('href') if link_tag else ""
                    if not link or "http" not in link:
                         safe_title = urllib.parse.quote(title)
                         link = f"https://www.douyin.com/search/{safe_title}"

                    hot = cells[2].get_text().strip() if len(cells) >= 3 else "Hot"
                    data.append({"rank": int(rank.group()), "title": title, "hot": hot, "link": link, "engine": "Vis-Hub"})
                if data: return data[:20]
            except Exception as e: log_msg("Douyin", f"Vis Err: {e}")

    resp = fetch_api_requests("https://tenapi.cn/v2/douyinhot")
    if resp and resp.status_code == 200:
        try:
            for idx, item in enumerate(resp.json().get('data', [])[:20]):
                data.append({"rank": idx+1, "title": item['name'], "hot": str(item['hot']), "link": item['url'], "engine": "API"})
            return data
        except: pass
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
                    if len(cells) < 2: continue
                    rank = re.search(r'\d+', cells[0].get_text().strip())
                    if not rank: continue
                    
                    title_cell = cells[1]
                    link_tag = title_cell.find("a")
                    title = link_tag.get_text().strip() if link_tag else title_cell.get_text().strip()
                    safe_title = urllib.parse.quote(title)
                    link = f"https://www.xiaohongshu.com/search_result?keyword={safe_title}&source=web_search_result_notes"
                    
                    hot = cells[2].get_text().strip() if len(cells) >= 3 else "Hot"
                    data.append({"rank": int(rank.group()), "title": title, "hot": hot, "link": link, "engine": "Vis-Hub"})
                if data: return data[:20]
            except Exception as e: log_msg("XHS", f"Vis Err: {e}")

    resp = fetch_api_requests("https://tenapi.cn/v2/xiaohongshuhot")
    if resp and resp.status_code == 200:
        try:
            for idx, item in enumerate(resp.json().get('data', [])[:20]):
                data.append({"rank": idx+1, "title": item['name'], "hot": str(item['hot']), "link": item['url'], "engine": "API"})
            return data
        except: pass
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
                    if len(cells) < 2: continue
                    
                    rank = re.search(r'\d+', cells[0].get_text().strip())
                    if not rank: continue
                    
                    title_cell = cells[1]
                    link_tag = title_cell.find("a")
                    title = link_tag.get_text().strip() if link_tag else title_cell.get_text().strip()
                    hot = cells[2].get_text().strip() if len(cells) >= 3 else "Hot"
                    
                    link = link_tag.get('href') if link_tag else ""
                    if not link or "http" not in link:
                        safe_title = urllib.parse.quote(title)
                        link = f"https://www.zhihu.com/search?type=content&q={safe_title}"
                    
                    data.append({"rank": int(rank.group()), "title": title, "hot": hot, "link": link, "engine": "Vis-Hub"})
                if data: return data[:20]
            except Exception as e: log_msg("Zhihu", f"Vis Err: {e}")

    resp = fetch_api_requests("https://tenapi.cn/v2/zhihuhot")
    if resp and resp.status_code == 200:
        try:
            for idx, item in enumerate(resp.json().get('data', [])[:20]):
                data.append({"rank": idx+1, "title": item['name'], "hot": str(item['hot']), "link": item['url'], "engine": "API"})
            return data
        except: pass
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
        except: pass
    return []

# ---------------------------------------------------------
# UI 渲染
# ---------------------------------------------------------
st.session_state.logs = [] 

c1, c2, c3, c4, c5 = st.columns(5)

def render_col(col, title, css, func):
    with col:
        st.markdown(f'<div class="source-header {css}">{title}</div>', unsafe_allow_html=True)
        data = func()
        if data:
            for i in data:
                tag = i.get('engine', '')
                css_tag = "vis-pw" if "Vis-PW" in tag else "vis-tophub" if "Hub" in tag else "api-req"
                link = i.get('link', '#')
                st.markdown(f"""
                <div class="row-item">
                    <span class="rank-badge">{i['rank']}</span>
                    <a href="{link}" target="_blank">{i['title']}</a>
                    <span class="engine-tag {css_tag}">{tag}</span>
                    <span class="hot-val">{i['hot']}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("暂无数据")

render_col(c1, "🔴 微博", "weibo-header", get_weibo_hot)
render_col(c2, "📺 B站", "bili-header", get_bilibili_hot)
render_col(c3, "🎵 抖音", "douyin-header", get_douyin_hot)
render_col(c4, "📕 小红书", "xhs-header", get_xhs_hot)
render_col(c5, "🔵 知乎", "zhihu-header", get_zhihu_hot)

# ---------------------------------------------------------
# Sidebar (修复刷新逻辑)
# ---------------------------------------------------------
def force_reload():
    # 回调函数：在脚本重新运行之前清除缓存
    st.cache_data.clear()

with st.sidebar:
    # 使用 on_click 参数，避免 rerun() 造成的二次刷新
    st.button("立即刷新", on_click=force_reload)
    
    st.divider()
    with st.expander("日志", expanded=True):
        for l in st.session_state.logs:
            c = "green" if "Success" in l else "red" if "Err" in l or "Empty" in l else "blue"
            st.markdown(f":{c}[{l}]")