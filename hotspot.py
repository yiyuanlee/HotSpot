import streamlit as st
import requests
import urllib3
import traceback
import json
import asyncio
import platform
import re
import urllib.parse
import os
import sqlite3
from datetime import datetime, timedelta
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

# ================================================================
# 主题配置
# ================================================================
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "realtime"   # "realtime" | "history"

def toggle_dark_mode():
    st.session_state.dark_mode = not st.session_state.dark_mode

if st.session_state.dark_mode:
    bg_primary    = "#1e1e1e"; bg_secondary = "#2d2d2d"; bg_card  = "#252525"
    text_primary  = "#e0e0e0"; text_secondary = "#a0a0a0"; border_color = "#3d3d3d"
    rank_top_bg   = "#ff6b6b"; rank_mid_bg   = "#ffa500"; page_bg     = "#1e1e1e"
else:
    bg_primary    = "#f5f7fa"; bg_secondary = "#ffffff"; bg_card  = "#ffffff"
    text_primary  = "#1a1a1a"; text_secondary = "#666666"; border_color = "#e0e0e0"
    rank_top_bg   = "#ff4757"; rank_mid_bg   = "#ff9f43"; page_bg     = "#f5f7fa"

hot_bar_colors = {"weibo":"#d63031","bili":"#00a1d6","douyin":"#2d3436","xhs":"#ff2442","zhihu":"#0084ff"}
PLATFORM_LOGOS = {"weibo":"🔴","bili":"📺","douyin":"🎵","xhs":"📕","zhihu":"🔵"}
PLATFORM_NAMES = {"weibo":"微博","bili":"B站","douyin":"抖音","xhs":"小红书","zhihu":"知乎"}

# ================================================================
# 数据库层
# ================================================================
DB_PATH = os.path.join(os.path.dirname(__file__), "hotspot_history.db")

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with get_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            platform TEXT, rank INTEGER, title TEXT, hot_value TEXT, engine TEXT, link TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, title TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            peak_rank INTEGER DEFAULT 999, total_appearances INTEGER DEFAULT 1,
            UNIQUE(platform, title))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_topics_platform ON topics(platform)")

def save_snapshot(platform_key, data):
    if not data: return
    now = datetime.now()
    with get_conn() as conn:
        for item in data:
            conn.execute("""INSERT INTO snapshots (ts,platform,rank,title,hot_value,engine,link)
                VALUES (?,?,?,?,?,?,?)""",
                (now, platform_key, item['rank'], item['title'],
                 item.get('hot',''), item.get('engine',''), item.get('link','')))
            conn.execute("""INSERT INTO topics (platform,title,last_seen,peak_rank,total_appearances)
                VALUES (?,?,?,?,1) ON CONFLICT(platform,title) DO UPDATE SET
                last_seen=excluded.last_seen, peak_rank=MIN(peak_rank,excluded.rank),
                total_appearances=total_appearances+1""",
                (platform_key, item['title'], now, item['rank']))

def clean_old_snapshots(days=7):
    cutoff = datetime.now() - timedelta(days=days)
    with get_conn() as conn:
        conn.execute("DELETE FROM snapshots WHERE ts < ?", (cutoff,))
        conn.execute("DELETE FROM topics WHERE last_seen < ?", (cutoff,))

init_db()
clean_old_snapshots(7)

# ================================================================
# 历史数据查询
# ================================================================
def get_topic_history(topic, platform=None, days=7):
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        q = "SELECT ts,platform,rank,hot_value FROM snapshots WHERE title=? ORDER BY ts ASC"
        p = [topic]
        if platform: q += " AND platform=?"; p.append(platform)
        return [dict(r) for r in conn.execute(q, p)]

def get_top_topics(platform=None, days=7, limit=20):
    cutoff = datetime.now() - timedelta(days=days)
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        q = "SELECT title,platform,peak_rank,total_appearances,last_seen FROM topics WHERE last_seen>=?"
        p = [cutoff]
        if platform: q += " AND platform=?"; p.append(platform)
        q += " ORDER BY total_appearances DESC,peak_rank ASC LIMIT ?"
        p.append(limit)
        return [dict(r) for r in conn.execute(q, p)]

def get_topic_heatmap(platform, days=7):
    cutoff = datetime.now() - timedelta(days=days)
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""SELECT DATE(ts) as date,rank,title FROM snapshots
            WHERE platform=? AND ts>=? AND rank<=10 ORDER BY date ASC,rank ASC""",
            [platform, cutoff]).fetchall()
        return [dict(r) for r in rows]

def parse_hot_value(hot_str):
    if not hot_str or hot_str in ("Hot","热搜"): return 50
    s = str(hot_str).replace(",","").replace(" ","")
    m = re.search(r"([\d.]+)([万亿]|wan|yi)", s, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        unit = m.group(2)
        if unit in ("万","wan"): val *= 10000
        elif unit in ("亿","yi"): val *= 100000000
        return min(int(val/100000000*100),100)
    m2 = re.search(r"^([\d.]+)$", s)
    if m2: return min(int(float(m2.group(1))/1000000*100),100)
    return 50

# ================================================================
# 引擎
# ================================================================
def fetch_page_content(url, selector_to_wait=None, timeout=20):
    if not PLAYWRIGHT_AVAILABLE: return None,"No Lib"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={'width':1920,'height':1080})
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout*1000)
                if selector_to_wait:
                    try: page.wait_for_selector(selector_to_wait, timeout=5000)
                    except: pass
                else: page.wait_for_timeout(2000)
                content = page.content(); browser.close()
                return content,"OK"
            except Exception as e:
                browser.close(); return None,str(e)
    except Exception: return None, traceback.format_exc()

def fetch_api_requests(url):
    try:
        headers={"User-Agent":"Mozilla/5.0"}
        resp=requests.get(url,headers=headers,timeout=10,verify=False)
        return resp
    except: return None

# ================================================================
# 数据源（抓取时自动存快照）
# ================================================================
@st.cache_data(ttl=300)
def get_weibo_hot():
    data=[]
    if PLAYWRIGHT_AVAILABLE:
        html,info=fetch_page_content("https://s.weibo.com/top/summary",".td-02")
        if html:
            try:
                soup=BeautifulSoup(html,"html.parser")
                for idx,row in enumerate(soup.select("td.td-02 > a")):
                    title=row.get_text().strip(); link=row.get('href') or ''
                    if link.startswith("/"): link="https://s.weibo.com"+link
                    if "javascript:void(0)" in link: continue
                    hot="Hot"
                    if row.parent and row.parent.find("span"): hot=row.parent.find("span").get_text().strip()
                    data.append({"rank":idx,"title":title,"hot":hot,"link":link,"engine":"Vis-PW"})
                if data: data=data[1:21]
            except Exception as e: log_msg("Weibo",f"Vis Err: {e}")
    if not data:
        resp=fetch_api_requests("https://m.weibo.cn/api/container/getIndex?containerid=106003type%3D25%26t%3D3%26disable_hot%3D1%26filter_type%3Drealtimehot")
        if resp and resp.status_code==200:
            try:
                for item in resp.json()['data']['cards'][0]['card_group']:
                    if 'desc' not in item: continue
                    data.append({"rank":0,"title":item['desc'],"hot":item.get('desc_entr',''),
                                 "link":item['scheme'],"engine":"API-Mob"})
            except: pass
    if data: save_snapshot("weibo",data)
    return data[:20]

@st.cache_data(ttl=300)
def get_douyin_hot():
    data=[]
    if PLAYWRIGHT_AVAILABLE:
        html,info=fetch_page_content("https://tophub.today/n/K7GdaMgdQy","table")
        if html:
            try:
                soup=BeautifulSoup(html,"html.parser")
                for row in soup.find_all("tr"):
                    cells=row.find_all("td")
                    if len(cells)<2: continue
                    rank=re.search(r'\d+',cells[0].get_text().strip())
                    if not rank: continue
                    tc=cells[1]; lt=tc.find("a"); title=lt.get_text().strip() if lt else tc.get_text().strip()
                    link=lt.get('href') if lt else ""
                    if not link or "http" not in link: link=f"https://www.douyin.com/search/{urllib.parse.quote(title)}"
                    hot=cells[2].get_text().strip() if len(cells)>=3 else "Hot"
                    data.append({"rank":int(rank.group()),"title":title,"hot":hot,"link":link,"engine":"Vis-Hub"})
            except Exception as e: log_msg("Douyin",f"Vis Err: {e}")
    if not data:
        resp=fetch_api_requests("https://tenapi.cn/v2/douyinhot")
        if resp and resp.status_code==200:
            try:
                for idx,item in enumerate(resp.json().get('data',[])[:20]):
                    data.append({"rank":idx+1,"title":item['name'],"hot":str(item['hot']),
                                 "link":item['url'],"engine":"API"})
            except: pass
    if data: save_snapshot("douyin",data)
    return data[:20]

@st.cache_data(ttl=300)
def get_xhs_hot():
    data=[]
    if PLAYWRIGHT_AVAILABLE:
        html,info=fetch_page_content("https://tophub.today/n/Jb0vmloB1G","table")
        if html:
            try:
                soup=BeautifulSoup(html,"html.parser")
                for row in soup.find_all("tr"):
                    cells=row.find_all("td")
                    if len(cells)<2: continue
                    rank=re.search(r'\d+',cells[0].get_text().strip())
                    if not rank: continue
                    tc=cells[1]; lt=tc.find("a"); title=lt.get_text().strip() if lt else tc.get_text().strip()
                    link=f"https://www.xiaohongshu.com/search_result?keyword={urllib.parse.quote(title)}&source=web_search_result_notes"
                    hot=cells[2].get_text().strip() if len(cells)>=3 else "Hot"
                    data.append({"rank":int(rank.group()),"title":title,"hot":hot,"link":link,"engine":"Vis-Hub"})
            except Exception as e: log_msg("XHS",f"Vis Err: {e}")
    if not data:
        resp=fetch_api_requests("https://tenapi.cn/v2/xiaohongshuhot")
        if resp and resp.status_code==200:
            try:
                for idx,item in enumerate(resp.json().get('data',[])[:20]):
                    data.append({"rank":idx+1,"title":item['name'],"hot":str(item['hot']),
                                 "link":item['url'],"engine":"API"})
            except: pass
    if data: save_snapshot("xhs",data)
    return data[:20]

@st.cache_data(ttl=300)
def get_zhihu_hot():
    data=[]
    if PLAYWRIGHT_AVAILABLE:
        html,info=fetch_page_content("https://tophub.today/n/mproPpoq6O","table")
        if html:
            try:
                soup=BeautifulSoup(html,"html.parser")
                for row in soup.find_all("tr"):
                    cells=row.find_all("td")
                    if len(cells)<2: continue
                    rank=re.search(r'\d+',cells[0].get_text().strip())
                    if not rank: continue
                    tc=cells[1]; lt=tc.find("a"); title=lt.get_text().strip() if lt else tc.get_text().strip()
                    hot=cells[2].get_text().strip() if len(cells)>=3 else "Hot"
                    link=lt.get('href') if lt else ""
                    if not link or "http" not in link: link=f"https://www.zhihu.com/search?type=content&q={urllib.parse.quote(title)}"
                    data.append({"rank":int(rank.group()),"title":title,"hot":hot,"link":link,"engine":"Vis-Hub"})
            except Exception as e: log_msg("Zhihu",f"Vis Err: {e}")
    if not data:
        resp=fetch_api_requests("https://tenapi.cn/v2/zhihuhot")
        if resp and resp.status_code==200:
            try:
                for idx,item in enumerate(resp.json().get('data',[])[:20]):
                    data.append({"rank":idx+1,"title":item['name'],"hot":str(item['hot']),
                                 "link":item['url'],"engine":"API"})
            except: pass
    if data: save_snapshot("zhihu",data)
    return data[:20]

@st.cache_data(ttl=300)
def get_bilibili_hot():
    data=[]
    resp=fetch_api_requests("https://api.bilibili.com/x/web-interface/search/square?limit=20")
    if resp and resp.status_code==200:
        try:
            for idx,item in enumerate(resp.json()['data']['trending']['list']):
                data.append({"rank":idx+1,"title":item['keyword'],"hot":"热搜",
                             "link":f"https://search.bilibili.com/all?keyword={item['keyword']}","engine":"API"})
        except: pass
    if data: save_snapshot("bili",data)
    return data

# ================================================================
# CSS
# ================================================================
st.markdown(f"""
<style>
    .stApp {{ background-color:{page_bg}; color:{text_primary}; }}
    .main-header {{ font-size:22px; font-weight:bold; padding:8px 0 4px; color:{text_primary}; }}
    .main-caption {{ font-size:12px; color:{text_secondary}; margin-bottom:12px; }}
    .col-wrap {{ background:{bg_card}; border:1px solid {border_color};
                 border-radius:10px; padding:12px 10px; height:100%;
                 box-shadow:0 2px 6px rgba(0,0,0,0.06); }}
    .source-header {{ font-size:15px; font-weight:700; margin-bottom:12px;
                     padding-bottom:8px; border-bottom:2px solid #ddd;
                     display:flex; align-items:center; gap:6px; white-space:nowrap; }}
    .weibo-header {{ color:#d63031; border-color:#d63031; }}
    .bili-header  {{ color:#00a1d6; border-color:#00a1d6; }}
    .douyin-header{{ color:#2d3436; border-color:#2d3436; }}
    .xhs-header   {{ color:#ff2442; border-color:#ff2442; }}
    .zhihu-header {{ color:#0084ff; border-color:#0084ff; }}
    .rank-badge {{ display:inline-block; width:22px; height:22px; line-height:22px;
                  text-align:center; border-radius:50%; font-size:11px; font-weight:bold;
                  margin-right:6px; color:white; flex-shrink:0; }}
    .rank-1 {{ background:{rank_top_bg}; }}
    .rank-2 {{ background:{rank_top_bg}; opacity:0.85; }}
    .rank-3 {{ background:{rank_top_bg}; opacity:0.7; }}
    .rank-4 {{ background:{rank_mid_bg}; }}
    .rank-other {{ background:{text_secondary}; opacity:0.5; }}
    .row-item {{ margin-bottom:9px; font-size:13px; display:flex; align-items:center;
                 gap:4px; color:{text_primary}; }}
    .row-item a {{ color:{text_primary}; text-decoration:none; flex:1;
                   overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .row-item a:hover {{ color:#0084ff; }}
    .engine-tag {{ font-size:9px; padding:1px 4px; border-radius:3px;
                  color:white; flex-shrink:0; }}
    .vis-pw    {{ background-color:#6c5ce7; }}
    .vis-tophub{{ background-color:#e17055; }}
    .api-req   {{ background-color:#00b894; }}
    .hot-wrap  {{ display:flex; align-items:center; gap:5px; flex-shrink:0; }}
    .hot-bar-bg{{ width:50px; height:4px; background:{border_color};
                  border-radius:2px; overflow:hidden; }}
    .hot-bar-fill{{ height:100%; border-radius:2px; transition:width 0.3s ease; }}
    .hot-text  {{ font-size:10px; color:{text_secondary}; min-width:36px; text-align:right; }}
    .empty-msg {{ color:{text_secondary}; font-size:12px; text-align:center; padding:20px 0; }}
    section[data-testid="stSidebar"] {{ background-color:{bg_card}; }}
    a {{ color:#0084ff; }}

    /* Trend chart container */
    .trend-card {{ background:{bg_card}; border:1px solid {border_color};
                   border-radius:10px; padding:16px; margin-bottom:16px; }}
    .trend-title {{ font-size:15px; font-weight:bold; margin-bottom:10px; color:{text_primary}; }}
    .topic-chip {{ display:inline-block; padding:4px 10px; border-radius:20px; font-size:12px;
                   margin:3px; cursor:pointer; border:1px solid {border_color}; color:{text_primary}; }}
    .topic-chip.active {{ background:#0084ff; color:white; border-color:#0084ff; }}
    .topic-chip:hover {{ border-color:#0084ff; }}
    .stats-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:12px; }}
    .stat-item {{ background:{bg_secondary}; border:1px solid {border_color};
                  border-radius:8px; padding:10px; text-align:center; }}
    .stat-val {{ font-size:20px; font-weight:bold; color:#0084ff; }}
    .stat-label {{ font-size:11px; color:{text_secondary}; }}
</style>
""", unsafe_allow_html=True)

st.title("🔥 HotSpot v4.1")
st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Playwright: {'✅ Ready' if PLAYWRIGHT_AVAILABLE else '❌ Missing'} | DB: {DB_PATH}")

if 'logs' not in st.session_state: st.session_state.logs = []
def log_msg(source, msg): st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [{source}] {msg}")

# ================================================================
# 侧边栏
# ================================================================
def force_reload(): st.cache_data.clear()

with st.sidebar:
    st.header("⚙️ 设置")
    st.toggle("🌙 深色模式", value=st.session_state.dark_mode, on_change=toggle_dark_mode)

    st.divider()
    st.subheader("📊 视图模式")
    view_mode = st.radio("切换视图", ["realtime","history"],
                         labels=["⚡ 实时热搜","📈 历史趋势"],
                         horizontal=True, index=0 if st.session_state.view_mode=="realtime" else 1)
    st.session_state.view_mode = view_mode

    st.divider()
    st.button("🔄 立即刷新", on_click=force_reload, use_container_width=True)
    st.divider()
    with st.expander("📋 日志", expanded=False):
        for l in st.session_state.logs:
            c="green" if "Success" in l else "red" if "Err" in l or "Empty" in l else "blue"
            st.markdown(f":{c}[{l}]")
    st.divider()
    st.caption("HotSpot v4.1 · 全网热搜聚合器")

# ================================================================
# 实时视图
# ================================================================
if st.session_state.view_mode == "realtime":
    PLATFORMS = [
        ("weibo", "🔴 微博", "weibo-header",  "weibo",  get_weibo_hot),
        ("bili",  "📺 B站",  "bili-header",   "bili",   get_bilibili_hot),
        ("douyin","🎵 抖音","douyin-header",  "douyin", get_douyin_hot),
        ("xhs",   "📕 小红书","xhs-header",   "xhs",    get_xhs_hot),
        ("zhihu", "🔵 知乎", "zhihu-header",  "zhihu",  get_zhihu_hot),
    ]
    cols = st.columns(5)
    for col,(key,title,css_cls,platform_key,func) in zip(cols,PLATFORMS):
        bar_color=hot_bar_colors[platform_key]
        with col:
            html_content = f'<div class="col-wrap">'
            html_content += f'<div class="source-header {css_cls}">{title}</div>'
            data=func()
            if data:
                for item in data:
                    rank=item.get('rank',0)
                    rank_cls=(f"rank-{rank}" if rank<=3 else "rank-4") if rank<=10 else "rank-other"
                    tag=item.get('engine','')
                    css_tag="vis-pw" if "Vis-PW" in tag else "vis-tophub" if "Hub" in tag else "api-req"
                    link=item.get('link','#')
                    title_text=item.get('title','')
                    hot_str=item.get('hot','')
                    hot_pct=parse_hot_value(hot_str)
                    html_content += f"""
                    <div class="row-item">
                        <span class="rank-badge {rank_cls}">{rank}</span>
                        <a href="{link}" target="_blank">{title_text}</a>
                        <span class="engine-tag {css_tag}">{tag}</span>
                        <div class="hot-wrap">
                            <div class="hot-bar-bg"><div class="hot-bar-fill" style="width:{hot_pct}%;background:{bar_color};"></div></div>
                            <span class="hot-text">{hot_str}</span>
                        </div>
                    </div>"""
            else:
                html_content += '<div class="empty-msg">暂无数据</div>'
            html_content += '</div>'
            st.markdown(html_content, unsafe_allow_html=True)

# ================================================================
# 历史趋势视图
# ================================================================
else:
    # --- 平台选择 + 时间范围 ---
    col_sel1, col_sel2 = st.columns([1,1])
    with col_sel1:
        sel_platform = st.selectbox("选择平台", ["全部","微博","B站","抖音","小红书","知乎"],
                                    index=0)
    with col_sel2:
        sel_days = st.selectbox("时间范围", [1,3,7,14], index=2,
                                format_func=lambda x: f"最近{x}天")

    platform_key_map = {"微博":"weibo","B站":"bili","抖音":"douyin","小红书":"xhs","知乎":"zhihu"}
    plat_filter = platform_key_map.get(sel_platform, None)

    # --- 热门话题统计 ---
    top_topics = get_top_topics(platform=plat_filter, days=sel_days, limit=20)
    if top_topics:
        st.subheader(f"🏆 热门话题榜（最近{sel_days}天）")
        cols_stat = st.columns(4)
        total_appearances = sum(t['total_appearances'] for t in top_topics)
        peak_avg = sum(t['peak_rank'] for t in top_topics) / len(top_topics) if top_topics else 0
        new_topics = sum(1 for t in top_topics if (datetime.now() - datetime.fromisoformat(str(t['last_seen'])) if hasattr(t['last_seen'],'isoformat') else datetime.now()) < timedelta(hours=sel_days*6))
        with cols_stat[0]:
            st.metric("上榜话题数", len(top_topics))
        with cols_stat[1]:
            st.metric("累计上榜次数", total_appearances)
        with cols_stat[2]:
            st.metric("平均巅峰排名", f"#{int(peak_avg)}")
        with cols_stat[3]:
            st.metric("新上榜话题", new_topics)

        st.divider()

        # --- 话题列表 + 趋势图 ---
        st.subheader("📈 话题趋势详情")

        # 话题选择 chips
        topic_titles = [t['title'] for t in top_topics[:15]]
        selected = st.selectbox("选择话题查看趋势", topic_titles)

        # 趋势图
        history = get_topic_history(selected, platform=plat_filter, days=sel_days)
        if history:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            plt.rcParams['font.family'] = ['DejaVu Sans','WenQuanYi Micro Hei','SimHei','Arial Unicode MS']
            plt.rcParams['axes.unicode_minus'] = False

            fig, ax = plt.subplots(figsize=(10,4))
            for pkey in (["weibo","bili","douyin","xhs","zhihu"] if not plat_filter else [plat_filter]):
                ph = [h for h in history if h['platform']==pkey]
                if not ph: continue
                times = [datetime.strptime(h['ts'], "%Y-%m-%d %H:%M:%S") if isinstance(h['ts'],str) else h['ts'] for h in ph]
                ranks = [h['rank'] for h in ph]
                label = PLATFORM_NAMES.get(pkey, pkey)
                ax.plot(times, ranks, marker='o', markersize=4, linewidth=1.5, label=label)
                ax.invert_yaxis()

            ax.set_title(f"#{selected}", fontsize=13)
            ax.set_ylabel("Rank", fontsize=11)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
            plt.xticks(rotation=30, fontsize=8)
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)
        else:
            st.info("暂无历史数据，新话题需要等下次抓取（每小时自动存一次快照）")

        st.divider()

        # --- 表格展示 ---
        st.subheader("📋 详细数据")
        import pandas as pd
        df = pd.DataFrame(top_topics)
        df['巅峰排名'] = df['peak_rank'].apply(lambda x: f"#{x}" if x<999 else "-")
        df['上榜次数'] = df['total_appearances']
        df['最近出现'] = pd.to_datetime(df['last_seen']).dt.strftime("%m-%d %H:%M")
        df['平台'] = df['platform'].map(PLATFORM_NAMES)
        st.dataframe(df[['平台','title','巅峰排名','上榜次数','最近出现']].rename(
            columns={'title':'话题','平台':'平台'}), use_container_width=True, hide_index=True)
    else:
        st.info("暂无历史数据，请稍等几分钟让系统积累抓取记录")
