"""定时任务：每天凌晨 3 点自动全量采集一次；采集日志写数据库，后台可见"""
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from ..database import get_conn
from ..categories import github_categories
from .github_collector import collect_github
from .rss_collector import collect_rss


def _log(task_name, status, count, message, started):
    conn = get_conn()
    conn.execute(
        "INSERT INTO collect_logs (task_name, status, count, message, started_at, finished_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (task_name, status, count, message, started, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def run_full_collect():
    """全量采集：GitHub + RSS，各记一条日志"""
    started = datetime.now().isoformat(timespec="seconds")
    try:
        total, detail = collect_github(github_categories())
        _log("GitHub 采集", "成功", total, str(detail), started)
    except Exception as e:
        _log("GitHub 采集", "失败", 0, str(e)[:500], started)
    started = datetime.now().isoformat(timespec="seconds")
    try:
        total, detail = collect_rss()
        _log("RSS 资讯采集", "成功", total, str(detail), started)
    except Exception as e:
        _log("RSS 资讯采集", "失败", 0, str(e)[:500], started)
    print("[定时任务] 全量采集完成")


def start_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(run_full_collect, "cron", hour=3, minute=0, id="daily_collect")
    scheduler.start()
    print("[定时任务] 已启动：每天凌晨 3 点自动采集")
    return scheduler
