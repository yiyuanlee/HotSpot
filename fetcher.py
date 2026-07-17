"""各平台热搜抓取（无 Streamlit 依赖，可供看板与定时 Agent 共用）。"""

from __future__ import annotations

import asyncio
import logging
import platform
import re
import urllib.parse
from typing import Callable

import requests
import urllib3
from bs4 import BeautifulSoup

if platform.system() == "Windows":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        pass

try:
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

PLATFORM_NAMES = {
    "weibo": "微博",
    "bili": "B站",
    "douyin": "抖音",
    "xhs": "小红书",
    "zhihu": "知乎",
}

PLATFORM_ORDER = ("weibo", "bili", "douyin", "xhs", "zhihu")


def fetch_page_content(url: str, selector_to_wait: str | None = None, timeout: int = 20):
    def _fallback():
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            if "weibo.com" in url:
                headers["Cookie"] = (
                    "SUB=_2AkMSWd50f8NxqwJRmP0SzGjnaYt2zQvEieKnWqM7JRMxHRl-yT9kqmFAtRB6PYC00XUo_oIeFok08G61yWnE2Yv2gqB9;"
                )
            resp = requests.get(url, headers=headers, timeout=timeout, verify=False)
            if resp.status_code == 200:
                resp.encoding = "utf-8"
                return resp.text, "Req-Fallback"
            return None, f"HTTP {resp.status_code}"
        except Exception as e:
            return None, str(e)

    if not PLAYWRIGHT_AVAILABLE:
        return _fallback()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                if selector_to_wait:
                    try:
                        page.wait_for_selector(selector_to_wait, timeout=5000)
                    except Exception:
                        pass
                else:
                    page.wait_for_timeout(2000)
                content = page.content()
                browser.close()
                return content, "OK"
            except Exception:
                browser.close()
                return _fallback()
    except Exception:
        return _fallback()


def fetch_api_requests(url: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        return requests.get(url, headers=headers, timeout=10, verify=False)
    except Exception:
        return None


def get_weibo_hot(limit: int = 20) -> list[dict]:
    data: list[dict] = []
    html, _ = fetch_page_content("https://s.weibo.com/top/summary", ".td-02")
    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for idx, row in enumerate(soup.select("td.td-02 > a")):
                title = row.get_text().strip()
                link = row.get("href") or ""
                if link.startswith("/"):
                    link = "https://s.weibo.com" + link
                if "javascript:void(0)" in link:
                    continue
                hot = "Hot"
                if row.parent and row.parent.find("span"):
                    hot = row.parent.find("span").get_text().strip()
                data.append(
                    {
                        "rank": idx,
                        "title": title,
                        "hot": hot,
                        "link": link,
                        "engine": "Vis-PW",
                    }
                )
            if data:
                data = data[1:21]
        except Exception as e:
            logger.warning("Weibo Vis Err: %s", e)

    if not data:
        resp = fetch_api_requests(
            "https://m.weibo.cn/api/container/getIndex?containerid=106003type%3D25%26t%3D3%26disable_hot%3D1%26filter_type%3Drealtimehot"
        )
        if resp and resp.status_code == 200:
            try:
                for item in resp.json()["data"]["cards"][0]["card_group"]:
                    if "desc" not in item:
                        continue
                    data.append(
                        {
                            "rank": 0,
                            "title": item["desc"],
                            "hot": item.get("desc_entr", ""),
                            "link": item["scheme"],
                            "engine": "API-Mob",
                        }
                    )
            except Exception:
                pass

    return _normalize_ranks(data[:limit])


def _parse_tophub_rows(html: str, link_builder, engine: str = "Vis-Hub") -> list[dict]:
    """解析 tophub.today 表格行，兼容标题/热度列错位。"""
    data: list[dict] = []
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        rank_m = re.search(r"\d+", cells[0].get_text().strip())
        if not rank_m:
            continue
        tc = cells[1]
        lt = tc.find("a")
        title = (lt.get_text().strip() if lt else tc.get_text().strip()) or ""
        hot = cells[2].get_text().strip() if len(cells) >= 3 else "Hot"
        # 部分页面把标题塞进热度列、标题列为空
        if not title and hot:
            title = hot.split("\n")[0].strip()
            hot = "Hot"
        if not title:
            continue
        link = ""
        if lt and lt.get("href") and "http" in (lt.get("href") or ""):
            link = lt.get("href")
        else:
            link = link_builder(title)
        data.append(
            {
                "rank": int(rank_m.group()),
                "title": title,
                "hot": hot.replace("\n", " ").strip(),
                "link": link,
                "engine": engine,
            }
        )
    return data


def get_douyin_hot(limit: int = 20) -> list[dict]:
    data: list[dict] = []
    html, _ = fetch_page_content("https://tophub.today/n/K7GdaMgdQy", "table")
    if html:
        try:
            data = _parse_tophub_rows(
                html,
                lambda t: f"https://www.douyin.com/search/{urllib.parse.quote(t)}",
            )
        except Exception as e:
            logger.warning("Douyin Vis Err: %s", e)

    if not data:
        resp = fetch_api_requests("https://tenapi.cn/v2/douyinhot")
        if resp and resp.status_code == 200:
            try:
                for idx, item in enumerate(resp.json().get("data", [])[:20]):
                    data.append(
                        {
                            "rank": idx + 1,
                            "title": item["name"],
                            "hot": str(item["hot"]),
                            "link": item["url"],
                            "engine": "API",
                        }
                    )
            except Exception:
                pass

    return data[:limit]


def get_xhs_hot(limit: int = 20) -> list[dict]:
    data: list[dict] = []
    html, _ = fetch_page_content("https://tophub.today/n/Jb0vmloB1G", "table")
    if html:
        try:
            data = _parse_tophub_rows(
                html,
                lambda t: (
                    "https://www.xiaohongshu.com/search_result?"
                    f"keyword={urllib.parse.quote(t)}&source=web_search_result_notes"
                ),
            )
        except Exception as e:
            logger.warning("XHS Vis Err: %s", e)

    if not data:
        resp = fetch_api_requests("https://tenapi.cn/v2/xiaohongshuhot")
        if resp and resp.status_code == 200:
            try:
                for idx, item in enumerate(resp.json().get("data", [])[:20]):
                    data.append(
                        {
                            "rank": idx + 1,
                            "title": item["name"],
                            "hot": str(item["hot"]),
                            "link": item["url"],
                            "engine": "API",
                        }
                    )
            except Exception:
                pass

    return data[:limit]


def get_zhihu_hot(limit: int = 20) -> list[dict]:
    data: list[dict] = []
    html, _ = fetch_page_content("https://tophub.today/n/mproPpoq6O", "table")
    if html:
        try:
            data = _parse_tophub_rows(
                html,
                lambda t: f"https://www.zhihu.com/search?type=content&q={urllib.parse.quote(t)}",
            )
            # 知乎热度常与标题粘在同一单元格，再拆一次
            cleaned = []
            for item in data:
                title = item["title"]
                hot = item["hot"]
                m = re.search(r"(.+?)\n?\s*([\d.]+\s*[万亿]?\s*热度)\s*$", title)
                if m:
                    title, hot = m.group(1).strip(), m.group(2).strip()
                elif "热度" in hot and len(title) < 2:
                    parts = re.split(r"\s+(?=[\d.]+\s*[万亿]?\s*热度)", hot, maxsplit=1)
                    if len(parts) == 2:
                        title, hot = parts[0].strip(), parts[1].strip()
                cleaned.append({**item, "title": title, "hot": hot, "link": item["link"] or f"https://www.zhihu.com/search?type=content&q={urllib.parse.quote(title)}"})
            data = cleaned
        except Exception as e:
            logger.warning("Zhihu Vis Err: %s", e)

    if not data:
        resp = fetch_api_requests("https://tenapi.cn/v2/zhihuhot")
        if resp and resp.status_code == 200:
            try:
                for idx, item in enumerate(resp.json().get("data", [])[:20]):
                    data.append(
                        {
                            "rank": idx + 1,
                            "title": item["name"],
                            "hot": str(item["hot"]),
                            "link": item["url"],
                            "engine": "API",
                        }
                    )
            except Exception:
                pass

    return data[:limit]


def get_bilibili_hot(limit: int = 20) -> list[dict]:
    data: list[dict] = []
    resp = fetch_api_requests(
        "https://api.bilibili.com/x/web-interface/search/square?limit=20"
    )
    if resp and resp.status_code == 200:
        try:
            for idx, item in enumerate(resp.json()["data"]["trending"]["list"]):
                data.append(
                    {
                        "rank": idx + 1,
                        "title": item["keyword"],
                        "hot": "热搜",
                        "link": f"https://search.bilibili.com/all?keyword={item['keyword']}",
                        "engine": "API",
                    }
                )
        except Exception:
            pass
    return data[:limit]


FETCHERS: dict[str, Callable[[int], list[dict]]] = {
    "weibo": get_weibo_hot,
    "bili": get_bilibili_hot,
    "douyin": get_douyin_hot,
    "xhs": get_xhs_hot,
    "zhihu": get_zhihu_hot,
}


def _normalize_ranks(data: list[dict]) -> list[dict]:
    """保证 rank 从 1 开始连续编号。"""
    out = []
    for i, item in enumerate(data, start=1):
        row = dict(item)
        row["rank"] = i
        out.append(row)
    return out


def fetch_all_hot(top_n: int = 10) -> dict[str, list[dict]]:
    """抓取全部平台热搜，各取 Top N。"""
    results: dict[str, list[dict]] = {}
    for key in PLATFORM_ORDER:
        fetcher = FETCHERS[key]
        try:
            items = _normalize_ranks(fetcher(top_n)[:top_n])
            results[key] = items
            logger.info("%s: %d 条", PLATFORM_NAMES[key], len(items))
        except Exception as e:
            logger.exception("抓取 %s 失败: %s", PLATFORM_NAMES[key], e)
            results[key] = []
    return results
