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
import sqlite3
import os
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
# 数据库层
# ================================================================
DB_PATH = os.path.join(os.path.dirname(__file__), "hotspot_history.db")

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                platform TEXT,
                rank INTEGER,
                title TEXT,
                hot_value TEXT,
                engine TEXT,
                link TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                title TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                peak_rank INTEGER DEFAULT 999,
                total_appearances INTEGER DEFAULT 1,
                UNIQUE(platform, title)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_topics_platform ON topics(platform)
        """)

def save_snapshot(platform_key, data):
    """保存一轮抓取结果到快照表，并更新话题统计"""
    if not data:
        return
    now = datetime.now()
    with get_conn() as conn:
        for item in data:
            # 写入快照
            conn.execute("""
                INSERT INTO snapshots (ts, platform, rank, title, hot_value, engine, link)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now, platform_key, item['rank'], item['title'],
                  item.get('hot', ''), item.get('engine', ''), item.get('link', '')))

            # 更新话题统计（upsert）
            conn.execute("""
                INSERT INTO topics (platform, title, last_seen, peak_rank, total_appearances)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(platform, title) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    peak_rank = MIN(peak_rank, excluded.rank),
                    total_appearances = total_appearances + 1
            """, (platform_key, item['title'], now, item['rank']))

def clean_old_snapshots(days=7):
    """删除 N 天前的快照，保留话题表"""
    cutoff = datetime.now() - timedelta(days=days)
    with get_conn() as conn:
        conn.execute("DELETE FROM snapshots WHERE ts < ?", (cutoff,))
        conn.execute("DELETE FROM topics WHERE last_seen < ?", (cutoff,))

# 启动时初始化
init_db()
# 清理 7 天前数据
clean_old_snapshots(7)

# ================================================================
# 引擎: 视觉爬虫 & API
# ================================================================
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

# ================================================================
# 数据源（抓取时自动保存快照）
# ================================================================
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
                    data = data[1:21]
            except Exception as e:
                log_msg("Weibo", f"Vis Err: {e}")

    if not data:
        url = "https://m.weibo.cn/api/container/getIndex?containerid=106003type%3D25%26t%3D3%26disable_hot%3D1%26filter_type%3Drealtimehot"
        resp = fetch_api_requests(url)
        if resp and resp.status_code == 200:
            try:
                cards = resp.json()['data']['cards'][0]['card_group']
                for item in cards:
                    if 'desc' not in item:
                        continue
                    data.append({"rank": 0, "title": item['desc'], "hot": item.get('desc_entr', ''), "link": item['scheme'], "engine": "API-Mob"})
            except:
                pass

    if data:
        save_snapshot("weibo", data)
    return data[:20]

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
            except Exception as e:
                log_msg("Douyin", f"Vis Err: {e}")

    if not data:
        resp = fetch_api_requests("https://tenapi.cn/v2/douyinhot")
        if resp and resp.status_code == 200:
            try:
                for idx, item in enumerate(resp.json().get('data', [])[:20]):
                    data.append({"rank": idx+1, "title": item['name'], "hot": str(item['hot']), "link": item['url'], "engine": "API"})
            except:
                pass

    if data:
        save_snapshot("douyin", data)
    return data[:20]

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
            except Exception as e:
                log_msg("XHS", f"Vis Err: {e}")

    if not data:
        resp = fetch_api_requests("https://tenapi.cn/v2/xiaohongshuhot")
        if resp and resp.status_code == 200:
            try:
                for idx, item in enumerate(resp.json().get('data', [])[:20]):
                    data.append({"rank": idx+1, "title": item['name'], "hot": str(item['hot']), "link": item['url'], "engine": "API"})
            except:
                pass

    if data:
        save_snapshot("xhs", data)
    return data[:20]

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
            except Exception as e:
                log_msg("Zhihu", f"Vis Err: {e}")

    if not data:
        resp = fetch_api_requests("https://tenapi.cn/v2/zhihuhot")
        if resp and resp.status_code == 200:
            try:
                for idx, item in enumerate(resp.json().get('data', [])[:20]):
                    data.append({"rank": idx+1, "title": item['name'], "hot": str(item['hot']), "link": item['url'], "engine": "API"})
            except:
                pass

    if data:
        save_snapshot("zhihu", data)
    return data[:20]

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
        except:
            pass
    if data:
        save_snapshot("bili", data)
    return data

# ================================================================
# 历史趋势数据查询
# ================================================================
def get_topic_history(topic, platform=None, days=7):
    """查询某个话题的历史排名轨迹"""
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        query = """
            SELECT ts, platform, rank, hot_value
            FROM snapshots
            WHERE title = ?
        """
        params = [topic]
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        query += " ORDER BY ts ASC"
        cur = conn.execute(query, params)
        return [dict(r) for r in cur.fetchall()]

def get_top_topics(platform=None, days=7, limit=20):
    """查询上榜次数最多的话题（热门话题）"""
    cutoff = datetime.now() - timedelta(days=days)
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        query = """
            SELECT title, platform, peak_rank, total_appearances, last_seen
            FROM topics
            WHERE last_seen >= ?
        """
        params = [cutoff]
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        query += " ORDER BY total_appearances DESC, peak_rank ASC LIMIT ?"
        params.append(limit)
        cur = conn.execute(query, params)
        return [dict(r) for r in cur.fetchall()]

def get_topic_heatmap(platform, days=7):
    """获取每日Top10排行（用于热力图）"""
    cutoff = datetime.now() - timedelta(days=days)
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT DATE(ts) as date, rank, title
            FROM snapshots
            WHERE platform = ? AND ts >= ? AND rank <= 10
            ORDER BY date ASC, rank ASC
        """, [platform, cutoff]).fetchall()
        return [dict(r) for r in rows]

def get_recent_snapshots(platform, hours=24):
    """获取最近 N 小时的快照概览"""
    since = datetime.now() - timedelta(hours=hours)
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT ts, COUNT(*) as count
            FROM snapshots
            WHERE platform = ? AND ts >= ?
            GROUP BY DATE(ts), HOUR(ts)
            ORDER BY ts ASC
        """, [platform, since]).fetchall()
        return [dict(r) for r in rows]
