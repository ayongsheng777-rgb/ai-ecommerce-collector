"""RSS 资讯采集器：从 config/rss.yaml 的订阅源抓新闻，归到对应子分类。

中文源（feeds）直接入库；英文源（english_feeds）抓到的条目，
标题和摘要会翻译成中文（title_cn/summary_cn），lang 记为 'en'，前台双语展示。
"""
import re
import time
import yaml
import feedparser
from datetime import datetime

from .translator import translate

CONFIG_PATH = "config/rss.yaml"
MAX_PER_FEED = 15


def load_feeds():
    """返回全部订阅源，英文源多带一个 en=True 标记"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    out = []
    for x in cfg.get("feeds", []):
        if x.get("enabled", True):
            out.append({**x, "en": False})
    for x in cfg.get("english_feeds", []):
        if x.get("enabled", True):
            out.append({**x, "en": True})
    return out


def collect_rss():
    from ..database import get_conn

    total = 0
    detail = {}
    now = datetime.now().isoformat(timespec="seconds")
    for feed in load_feeds():
        name, url, sub_id, is_en = feed["name"], feed["url"], feed["category"], feed["en"]
        try:
            parsed = feedparser.parse(url, agent="ai-ecommerce-collector")
            entries = parsed.entries[:MAX_PER_FEED]
        except Exception as e:
            print(f"[RSS] {name} 抓取失败：{e}")
            detail[name] = f"失败：{e}"
            continue
        conn = get_conn()
        # 按来源名清理旧数据，避免重复堆积
        conn.execute(
            "DELETE FROM items WHERE subcategory_id = ? AND source_name = ? AND is_manual = 0",
            (sub_id, name),
        )
        n = 0
        for e in entries:
            link = e.get("link", "")
            if not link:
                continue
            title = (e.get("title") or "")[:200]
            summary = (e.get("summary") or e.get("description") or "").strip()
            # 去掉摘要里的网页标签，只留文字
            summary = re.sub(r"<[^>]+>", "", summary)[:200]
            pub = ""
            if e.get("published_parsed"):
                pub = datetime(*e.published_parsed[:6]).isoformat(timespec="seconds")
            title_cn, summary_cn, lang = "", "", "zh"
            if is_en:
                # 英文源：标题和摘要翻成中文，双语入库
                title_cn = translate(title)
                summary_cn = translate(summary)
                lang = "en"
            conn.execute(
                """INSERT INTO items (subcategory_id, title, url, description, source_name,
                                      stars, published_at, collected_at, is_manual,
                                      title_cn, summary_cn, lang)
                   VALUES (?, ?, ?, ?, ?, NULL, ?, ?, 0, ?, ?, ?)""",
                (sub_id, title, link, summary, name, pub, now, title_cn, summary_cn, lang),
            )
            n += 1
        conn.commit()
        conn.close()
        total += n
        detail[name] = n
        print(f"[RSS] {name}：写入 {n} 条")
        time.sleep(1)
    return total, detail
