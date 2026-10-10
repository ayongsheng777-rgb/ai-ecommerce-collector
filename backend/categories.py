"""分类配置读取：读 config/categories.yaml，叠加数据库里的启停开关"""
import yaml
from .database import get_conn

CONFIG_PATH = "config/categories.yaml"


def load_categories():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    modules = cfg.get("modules", [])
    # 读数据库里的启停开关（管理员在后台改的）
    conn = get_conn()
    rows = conn.execute("SELECT subcategory_id, enabled FROM subcat_state").fetchall()
    conn.close()
    override = {r["subcategory_id"]: bool(r["enabled"]) for r in rows}
    for m in modules:
        for sub in m.get("subcategories", []):
            if sub["id"] in override:
                sub["enabled"] = override[sub["id"]]
    return modules


def get_subcategory(sub_id):
    for m in load_categories():
        for sub in m.get("subcategories", []):
            if sub["id"] == sub_id:
                return sub, m
    return None, None


def github_categories():
    subs = []
    for m in load_categories():
        for sub in m.get("subcategories", []):
            if sub.get("source") == "github" and sub.get("enabled", True):
                subs.append(sub)
    return subs


def set_subcat_enabled(sub_id, enabled: bool):
    conn = get_conn()
    conn.execute(
        "INSERT INTO subcat_state (subcategory_id, enabled) VALUES (?, ?) "
        "ON CONFLICT(subcategory_id) DO UPDATE SET enabled = ?",
        (sub_id, 1 if enabled else 0, 1 if enabled else 0),
    )
    conn.commit()
    conn.close()
