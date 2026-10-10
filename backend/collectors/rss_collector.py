"""RSS 资讯采集器：从 config/rss.yaml 的订阅源抓新闻，归到对应子分类"""
import time
import yaml
import feedparser
from datetime import datetime

CONFIG_PATH = "config/rss.yaml"
MAX_PER_FEED = 15


def load_feeds():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return [x for x in cfg.get("feeds", []) if x.get("enabled", True)]


def collect_rss():
    from ..database import get_conn

    total = 0
    detail = {}
    now = datetime.now().isoformat(timespec="seconds")
    for feed in load_feeds():
        name, url, sub_id = feed["name"], feed["url"], feed["category"]
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
            summary = (e.get("summary") or e.get("description") or "").strip()
            # 去掉摘要里的网页标签，只留文字
            import re
            summary = re.sub(r"<[^>]+>", "", summary)[:200]
            pub = ""
            if e.get("published_parsed"):
                pub = datetime(*e.published_parsed[:6]).isoformat(timespec="seconds")
            conn.execute(
                """INSERT INTO items (subcategory_id, title, url, description, source_name,
                                      published_at, collected_at, is_manual)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (sub_id, (e.get("title") or "")[:200], link, summary, name, pub, now),
            )
            n += 1
        conn.commit()
        conn.close()
        total += n
        detail[name] = n
        print(f"[RSS] {name}：写入 {n} 条")
        time.sleep(1)
    return total, detail
