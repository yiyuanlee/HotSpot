import streamlit as st
import requests
import urllib3
import random
import time
from datetime import datetime

# 1. 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 2. 页面配置
st.set_page_config(
    page_title="HotSpot - 全网热搜",
    page_icon="🔥",
    layout="wide"
)

# 3. CSS 样式
st.markdown("""
<style>
    .source-header { 
        font-size: 20px; font-weight: bold; padding-bottom: 5px; 
        margin-bottom: 15px; border-bottom: 2px solid #ddd;
    }
    .weibo-header { color: #d63031; border-color: #d63031; }
    .bili-header { color: #00a1d6; border-color: #00a1d6; }
    .douyin-header { color: #2d3436; border-color: #2d3436; }
    
    a { text-decoration: none; color: #333; transition: 0.3s; }
    a:hover { color: #FF4B4B; }
    
    .rank-badge {
        display: inline-block; width: 18px; text-align: center;
        margin-right: 4px; font-weight: bold; color: #999; font-size: 14px;
    }
    .hot-val { font-size: 12px; color: #aaa; float: right; }
    .row-item { margin-bottom: 6px; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block;}
    .status-tag { font-size: 10px; color: #fff; padding: 2px 4px; border-radius: 3px; vertical-align: middle; }
    .status-ok { background-color: #2ecc71; }
    .status-bak { background-color: #f1c40f; color: #333; }
</style>
""", unsafe_allow_html=True)

st.title("🔥 HotSpot 全网热搜")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 全局日志列表
if 'logs' not in st.session_state:
    st.session_state.logs = []

def log_msg(source, msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{timestamp}] [{source}] {msg}")

# ---------------------------------------------------------
# 4. 网络请求核心
# ---------------------------------------------------------

def get_random_ua():
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
    ]
    return random.choice(uas)

def fetch_url(url, headers=None, timeout=8):
    try:
        if headers is None:
            headers = {}
        if "User-Agent" not in headers:
            headers["User-Agent"] = get_random_ua()
            
        session = requests.Session()
        session.trust_env = False  # 忽略系统代理
        response = session.get(url, headers=headers, timeout=timeout, verify=False)
        return response
    except Exception as e:
        return str(e)

# ---------------------------------------------------------
# 5. 爬虫模块
# ---------------------------------------------------------

@st.cache_data(ttl=300)
def get_weibo_hot():
    """微博热搜 (PC -> Mobile 自动降级)"""
    data = []
    
    # --- Plan A: PC API (数据最全) ---
    url_pc = "https://weibo.com/ajax/side/hotSearch"
    # 移除 Cookie，有时候无 Cookie 反而更安全，或者使用极简 Cookie
    headers_pc = {
        "Referer": "https://s.weibo.com/",
        "Cookie": "SUB=_2AkMR_123;" 
    }
    
    resp = fetch_url(url_pc, headers_pc)
    
    # 修复逻辑：显式检查 resp 是否为 None
    if resp is not None and not isinstance(resp, str):
        if resp.status_code == 200:
            try:
                items = resp.json()['data']['realtime']
                for idx, item in enumerate(items):
                    if 'is_ad' in item: continue
                    hot_val = item.get('num', 0)
                    hot_str = f"{hot_val/10000:.1f}w" if hot_val > 10000 else str(hot_val)
                    data.append({
                        "rank": idx + 1,
                        "title": item.get('note', item.get('word')),
                        "hot": hot_str,
                        "link": f"https://s.weibo.com/weibo?q={item.get('word')}"
                    })
                log_msg("Weibo", "Plan A (PC) Success")
                return data[:20]
            except:
                log_msg("Weibo", "Plan A Parse Failed")
        else:
            log_msg("Weibo", f"Plan A Failed: {resp.status_code}")
    else:
        log_msg("Weibo", f"Plan A Net Err: {resp}")

    # --- Plan B: Mobile API (备用，抗封锁) ---
    log_msg("Weibo", "Switching to Plan B (Mobile)...")
    url_mobile = "https://m.weibo.cn/api/container/getIndex?containerid=106003type%3D25%26t%3D3%26disable_hot%3D1%26filter_type%3Drealtimehot"
    resp = fetch_url(url_mobile)
    
    if resp is not None and not isinstance(resp, str) and resp.status_code == 200:
        try:
            cards = resp.json().get('data', {}).get('cards', [])[0].get('card_group', [])
            for idx, item in enumerate(cards):
                if 'desc' not in item: continue
                data.append({
                    "rank": idx, 
                    "title": item.get('desc'),
                    "hot": item.get('desc_entr', ''),
                    "link": item.get('scheme')
                })
            log_msg("Weibo", "Plan B (Mobile) Success")
            return data[:20]
        except Exception as e:
            log_msg("Weibo", f"Plan B Parse Err: {e}")
            
    return []

@st.cache_data(ttl=300)
def get_bilibili_hot():
    """B站热搜"""
    url = "https://api.bilibili.com/x/web-interface/search/square?limit=20"
    headers = {"Referer": "https://www.bilibili.com/"}
    data = []
    resp = fetch_url(url, headers)
    
    if resp is not None and not isinstance(resp, str) and resp.status_code == 200:
        try:
            items = resp.json().get('data', {}).get('trending', {}).get('list', [])
            for idx, item in enumerate(items):
                data.append({
                    "rank": idx + 1,
                    "title": item.get('keyword'),
                    "hot": "热搜",
                    "link": f"https://search.bilibili.com/all?keyword={item.get('keyword')}"
                })
            return data[:20]
        except: pass
    else:
        status = resp.status_code if hasattr(resp, 'status_code') else str(resp)
        log_msg("Bilibili", f"Failed: {status}")
    return data

@st.cache_data(ttl=300)
def get_douyin_hot():
    """抖音热搜 (TenAPI -> Vvhan -> Official)"""
    data = []
    
    # Plan A: TenAPI
    resp = fetch_url("https://tenapi.cn/v2/douyinhot")
    if resp is not None and not isinstance(resp, str) and resp.status_code == 200:
        try:
            json_data = resp.json()
            if json_data.get('code') == 200:
                for idx, item in enumerate(json_data.get('data', [])[:20]):
                    data.append({"rank": idx+1, "title": item['name'], "hot": item['hot'], "link": item['url']})
                log_msg("Douyin", "Plan A (TenAPI) Success")
                return data
        except: pass

    # Plan B: Vvhan
    log_msg("Douyin", "Trying Plan B (Vvhan)...")
    resp = fetch_url("https://api.vvhan.com/api/hotlist?type=douyinHot")
    if resp is not None and not isinstance(resp, str) and resp.status_code == 200:
        try:
            json_data = resp.json()
            if json_data.get('success'):
                for item in json_data.get('data', [])[:20]:
                    data.append({"rank": item['index'], "title": item['title'], "hot": item['hot'], "link": item['url']})
                log_msg("Douyin", "Plan B (Vvhan) Success")
                return data
        except: pass
        
    # Plan C: Official (Direct)
    log_msg("Douyin", "Trying Plan C (Official)...")
    url_off = "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/"
    resp = fetch_url(url_off)
    if resp is not None and not isinstance(resp, str) and resp.status_code == 200:
        try:
            items = resp.json().get('word_list', [])
            for idx, item in enumerate(items):
                hot_val = item.get('hot_value', 0)
                data.append({
                    "rank": idx + 1, 
                    "title": item.get('word'), 
                    "hot": f"{hot_val/10000:.1f}w", 
                    "link": f"https://www.douyin.com/search/{item.get('word')}"
                })
            log_msg("Douyin", "Plan C (Official) Success")
            return data[:20]
        except: pass
        
    return []

# ---------------------------------------------------------
# 6. UI 渲染
# ---------------------------------------------------------

st.session_state.logs = [] # Reset logs

c1, c2, c3 = st.columns(3)

def render_list(column, title, css_class, data_func):
    with column:
        st.markdown(f'<div class="source-header {css_class}">{title}</div>', unsafe_allow_html=True)
        data = data_func()
        if data:
            for item in data:
                st.markdown(
                    f"""
                    <div class="row-item">
                        <span class="rank-badge">{item['rank']}</span>
                        <a href="{item['link']}" target="_blank">{item['title']}</a>
                        <span class="hot-val">🔥{item['hot']}</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        else:
            st.warning("暂无数据")

render_list(c1, "🔴 微博热搜", "weibo-header", get_weibo_hot)
render_list(c2, "📺 Bilibili", "bili-header", get_bilibili_hot)
render_list(c3, "🎵 抖音热榜", "douyin-header", get_douyin_hot)

# Sidebar
with st.sidebar:
    st.header("HotSpot v2.3")
    if st.button("立即刷新"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    with st.expander("运行日志 (Debug Log)", expanded=True):
        if st.session_state.logs:
            for log in st.session_state.logs:
                color = "green" if "Success" in log else "red" if "Fail" in log or "Err" in log else "blue"
                st.markdown(f":{color}[{log}]")