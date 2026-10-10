"""英文翻译成中文：把英文资讯的标题和摘要翻成中文，前台双语展示。

默认走 MyMemory 免费接口（https://api.mymemory.translated.net/get），不用注册；
单次最多约 500 字符，摘要会先截断到 450 字符再翻。
设置 MYMEMORY_EMAIL 环境变量（填一个自己的邮箱）可以提高免费额度。

如果配置了 TRANSLATE_API_KEY（OpenAI 兼容接口，配合 TRANSLATE_BASE_URL 和
TRANSLATE_MODEL），就优先用它来翻，比如直接复用 DeepSeek：
  TRANSLATE_BASE_URL=https://api.deepseek.com/v1
  TRANSLATE_MODEL=deepseek-chat
  TRANSLATE_API_KEY=你的 DeepSeek 密钥

任何超时、异常一律吞掉，返回空字符串 ""——翻译失败不影响采集入库。
"""
import os
import requests

MYMEMORY_URL = "https://api.mymemory.translated.net/get"
MAX_CHARS = 450  # MyMemory 单次约 500 字符上限，摘要截断到 450 再翻


def _translate_mymemory(text: str) -> str:
    email = os.environ.get("MYMEMORY_EMAIL", "").strip()
    params = {"q": text, "langpair": "en|zh-CN"}
    if email:
        params["de"] = email
    resp = requests.get(MYMEMORY_URL, params=params, timeout=20)
    data = resp.json()
    if str(data.get("responseStatus")) != "200":
        return ""
    translated = (data.get("responseData", {}).get("translatedText") or "").strip()
    # MyMemory 出错时会原样返回英文或报错提示，这里只做基本过滤
    if not translated or translated.lower().startswith(("invalid", "query length")):
        return ""
    return translated


def _translate_openai_compatible(text: str) -> str:
    base_url = os.environ.get("TRANSLATE_BASE_URL", "").strip().rstrip("/")
    api_key = os.environ.get("TRANSLATE_API_KEY", "").strip()
    model = os.environ.get("TRANSLATE_MODEL", "").strip()
    if not (base_url and api_key and model):
        return ""
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system",
                 "content": "你是翻译助手。把用户输入的英文翻译成简体中文，只输出译文，不要加任何解释。"},
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
        },
        timeout=30,
    )
    data = resp.json()
    content = (
        data.get("choices", [{}])[0].get("message", {}).get("content") or ""
    ).strip()
    return content


def translate(text: str) -> str:
    """英文翻成中文。失败返回空字符串，调用方直接判断空串即可。"""
    text = (text or "").strip()
    if not text:
        return ""
    # 已经是中文为主的就不用翻
    if sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff") > len(text) / 2:
        return ""
    text = text[:MAX_CHARS]
    try:
        if os.environ.get("TRANSLATE_API_KEY", "").strip():
            result = _translate_openai_compatible(text)
        else:
            result = _translate_mymemory(text)
        return result or ""
    except Exception as e:
        print(f"[翻译] 翻译失败，已跳过：{e}")
        return ""
