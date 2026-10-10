"""GitHub 采集器：按分类配置里的关键词调 GitHub 搜索接口，按星数取前 15 个仓库。

翻译策略：只有配置了 TRANSLATE_API_KEY（OpenAI 兼容接口）时才翻译项目简介。
按仓库全名缓存——DELETE 旧数据前先读出该子分类已有行的 {仓库全名: 中文简介}，
新抓到的若命中缓存直接复用，只翻新增的，避免每次全量重翻浪费额度。
没配 key 时 summary_cn 留空。仓库名不翻译标题。
"""
import os
import time
import requests
from datetime import datetime

from .translator import translate

API_URL = "https://api.github.com/search/repositories"
PER_CATEGORY = 15  # 每个子分类取前 15 条


def _headers():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    h = {"Accept": "application/vnd.github+json", "User-Agent": "ai-ecommerce-collector"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def fetch_top_repos(query: str, limit: int = PER_CATEGORY, session=None):
    """抓一个关键词的前 N 个仓库，带限流等待重试"""
    s = session or requests.Session()
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": limit}
    for attempt in range(4):
        resp = s.get(API_URL, params=params, headers=_headers(), timeout=30)
        if resp.status_code == 200:
            return resp.json().get("items", [])
        if resp.status_code in (403, 429):
            # 撞上限流：看接口告诉我们要等多久，等完再试
            wait = int(resp.headers.get("Retry-After", 60)) + 5
            reset = resp.headers.get("X-RateLimit-Reset")
            if reset:
                wait = max(wait, int(reset) - int(time.time()) + 5)
            print(f"[GitHub] 限流了，等待 {wait} 秒后重试（第 {attempt + 1} 次）")
            time.sleep(min(wait, 600))
            continue
        print(f"[GitHub] 请求失败：{resp.status_code} {resp.text[:200]}")
        break
    return []


def collect_github(categories):
    """categories：从 categories.yaml 读出的 github 类型子分类列表。
    返回 (写入总条数, 各分类明细)。直接写 SQLite。"""
    from ..database import get_conn

    translate_on = bool(os.environ.get("TRANSLATE_API_KEY", "").strip())
    total = 0
    detail = {}
    s = requests.Session()
    now = datetime.now().isoformat(timespec="seconds")
    for cat in categories:
        sub_id = cat["id"]
        items = fetch_top_repos(cat["github_query"], session=s)
        conn = get_conn()
        # 先读出旧的翻译缓存：{仓库全名: 中文简介}
        cache = {}
        if translate_on:
            for row in conn.execute(
                "SELECT title, summary_cn FROM items WHERE subcategory_id = ? AND summary_cn <> ''",
                (sub_id,),
            ):
                cache[row["title"]] = row["summary_cn"]
        conn.execute("DELETE FROM items WHERE subcategory_id = ? AND is_manual = 0", (sub_id,))
        for it in items:
            full_name = it.get("full_name", "")
            desc = (it.get("description") or "")[:300]
            summary_cn = ""
            if translate_on:
                if full_name in cache:
                    summary_cn = cache[full_name]  # 命中缓存，直接复用
                else:
                    summary_cn = translate(desc)  # 新增的才翻
            conn.execute(
                """INSERT INTO items (subcategory_id, title, url, description, source_name, stars,
                                      published_at, collected_at, is_manual,
                                      title_cn, summary_cn, lang)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, 'en')""",
                (
                    sub_id,
                    full_name,
                    it.get("html_url", ""),
                    desc,
                    "GitHub",
                    it.get("stargazers_count", 0),
                    (it.get("updated_at") or "")[:10],
                    now,
                    summary_cn,
                ),
            )
        conn.commit()
        conn.close()
        total += len(items)
        detail[sub_id] = len(items)
        print(f"[GitHub] {cat['name']}：写入 {len(items)} 条")
        time.sleep(2)  # 每个分类之间歇 2 秒，别太猛
    return total, detail
