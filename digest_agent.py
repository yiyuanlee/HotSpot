"""HotSpot 每日 Digest Agent：抓取各平台 Top10 → AI 摘要 → 推送飞书。"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from fetcher import PLATFORM_NAMES, PLATFORM_ORDER, fetch_all_hot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("digest_agent")

TZ = ZoneInfo("Asia/Shanghai")


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def build_topics_text(hotspots: dict[str, list[dict]]) -> str:
    lines = []
    for key in PLATFORM_ORDER:
        name = PLATFORM_NAMES[key]
        items = hotspots.get(key) or []
        lines.append(f"【{name}】")
        if not items:
            lines.append("（暂无数据）")
            continue
        for item in items:
            hot = item.get("hot") or ""
            suffix = f" · {hot}" if hot and hot not in ("Hot", "热搜") else ""
            lines.append(f"{item['rank']}. {item['title']}{suffix}")
        lines.append("")
    return "\n".join(lines).strip()


def generate_ai_summary(hotspots: dict[str, list[dict]]) -> str:
    """调用 OpenAI 兼容接口生成一句话摘要；失败则回退到规则摘要。"""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _fallback_summary(hotspots)

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    topics = build_topics_text(hotspots)

    prompt = (
        "你是中文互联网舆情观察助手。根据以下今日各平台热搜 Top10，"
        "用一句中文（不超过 80 字）概括今天舆论焦点与情绪，不要列举清单，不要加引号。\n\n"
        f"{topics}"
    )

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你擅长简洁、准确的中文热点摘要。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
                "max_tokens": 120,
            },
            timeout=45,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        return text.replace("\n", " ")
    except Exception as e:
        logger.warning("AI 摘要失败，使用规则摘要: %s", e)
        return _fallback_summary(hotspots)


def _fallback_summary(hotspots: dict[str, list[dict]]) -> str:
    tops = []
    for key in PLATFORM_ORDER:
        items = hotspots.get(key) or []
        if items:
            tops.append(f"{PLATFORM_NAMES[key]}「{items[0]['title']}」")
    if not tops:
        return "今日各平台热搜暂无可用数据，请稍后重试。"
    joined = "、".join(tops[:3])
    return f"今日舆论焦点集中在{joined}等话题，跨平台热度持续升温。"


def build_feishu_card(hotspots: dict[str, list[dict]], summary: str, now: datetime) -> dict:
    date_str = now.strftime("%Y-%m-%d %H:%M")
    elements: list[dict] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**🤖 AI 摘要**\n{summary}",
            },
        },
        {"tag": "hr"},
    ]

    for key in PLATFORM_ORDER:
        name = PLATFORM_NAMES[key]
        items = hotspots.get(key) or []
        if not items:
            body = "暂无数据"
        else:
            rows = []
            for item in items:
                title = item["title"]
                link = item.get("link") or ""
                hot = item.get("hot") or ""
                hot_part = f" `{hot}`" if hot and hot not in ("Hot", "热搜") else ""
                if link and link.startswith("http"):
                    rows.append(f"{item['rank']}. [{title}]({link}){hot_part}")
                else:
                    rows.append(f"{item['rank']}. {title}{hot_part}")
            body = "\n".join(rows)

        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{name} Top10**\n{body}",
                },
            }
        )

    elements.append(
        {
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": f"HotSpot Digest · {date_str} (Asia/Shanghai)",
                }
            ],
        }
    )

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🔥 全网热搜日报 · {now.strftime('%m/%d')}",
                },
                "template": "red",
            },
            "elements": elements,
        },
    }


def send_feishu(webhook_url: str, payload: dict) -> None:
    resp = requests.post(webhook_url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json() if resp.content else {}
    # 飞书成功通常 StatusCode=0 或 code=0
    code = data.get("StatusCode", data.get("code", 0))
    if code not in (0, "0", None):
        raise RuntimeError(f"飞书返回异常: {data}")
    logger.info("飞书推送成功")


def run(dry_run: bool = False) -> int:
    load_dotenv()
    webhook = os.getenv("FEISHU_WEBHOOK_URL", "").strip()
    top_n = int(os.getenv("DIGEST_TOP_N", "10"))

    if not dry_run and not webhook:
        logger.error("请设置环境变量 FEISHU_WEBHOOK_URL（飞书自定义机器人 Webhook）")
        return 1

    logger.info("开始抓取各平台 Top%d …", top_n)
    hotspots = fetch_all_hot(top_n=top_n)
    summary = generate_ai_summary(hotspots)
    now = datetime.now(TZ)
    payload = build_feishu_card(hotspots, summary, now)

    logger.info("AI 摘要: %s", summary)
    if dry_run:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        try:
            print(text)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        return 0

    send_feishu(webhook, payload)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="HotSpot 飞书每日热搜 Digest")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只抓取并打印卡片 JSON，不发送飞书",
    )
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
