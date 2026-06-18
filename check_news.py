import os
import json
import hashlib
import requests
import feedparser
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID    = os.environ["TELEGRAM_CHAT_ID"]
MINIMAX_API_KEY     = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_MODEL       = os.environ.get("MINIMAX_MODEL") or "MiniMax-M3"
MINIMAX_API_URL     = os.environ.get("MINIMAX_API_URL", "https://api.minimax.io/v1/chat/completions")
MIN_ALERT_SCORE     = int(os.environ.get("MIN_ALERT_SCORE", "5"))
SEEN_FILE           = "seen_articles.json"

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=SK+Hynix&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=SK+Hynix+stock&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=SK+Hynix+HBM+DRAM&hl=en-US&gl=US&ceid=US:en",
]

# ── Step 2: MiniMax scoring ──────────────────────────────────────────────────
SCORE_SYSTEM = """You are a financial analyst specializing in semiconductor stocks.
Your job is to assess whether a news headline about SK Hynix is likely to
materially move its stock price (up or down).

Respond ONLY with a JSON object like:
{"score": 8, "reason": "one-line reason", "direction": "bullish"}

Rules:
- score: 1-10 (1 = noise, 10 = major market-moving event)
- direction: "bullish", "bearish", or "neutral"
- reason: max 12 words explaining the score
- Score 7+ = major event worth alerting
- Score 4-6 = moderate news, skip
- Score 1-3 = noise, skip

High-score examples (7+):
- Quarterly earnings beat/miss
- HBM supply deal with Nvidia/Apple
- US export restriction to China announced
- Analyst upgrade/downgrade with big target change
- DRAM pricing collapse or surge reported
- Major fab capacity change

Low-score examples (1-3):
- Generic industry commentary
- Reposted old news
- Minor executive quotes
- Unrelated market roundups"""

def score_with_minimax(title: str) -> dict:
    """Call MiniMax to score the headline. Returns score dict or None on error."""
    if not MINIMAX_API_KEY:
        print("  ⚠️  MiniMax API key missing; using fallback alert")
        return None

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "content-type": "application/json",
    }
    body = {
        "model": MINIMAX_MODEL,
        "max_tokens": 100,
        "messages": [
            {"role": "system", "content": SCORE_SYSTEM},
            {"role": "user", "content": f"Headline: {title}"},
        ],
    }
    try:
        r = requests.post(
            MINIMAX_API_URL,
            headers=headers,
            json=body,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        raw = data["choices"][0]["message"]["content"]
        if isinstance(raw, list):
            raw = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in raw
            )
        raw = str(raw).strip().replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(raw[start : end + 1])
            raise
    except Exception as e:
        response_text = ""
        if isinstance(e, requests.HTTPError) and e.response is not None:
            response_text = e.response.text.strip()
        if response_text:
            print(f"  ⚠️  MiniMax scoring failed: {e} | {response_text}")
        else:
            print(f"  ⚠️  MiniMax scoring failed: {e}")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def article_id(entry) -> str:
    return hashlib.md5((entry.get("link") or entry.get("title", "")).encode()).hexdigest()

def article_is_today(entry) -> bool:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return False

    published_date = datetime(*parsed[:6]).date()
    return published_date == datetime.utcnow().date()

def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()

DIRECTION_EMOJI = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}

def format_message(entry, score_data: dict) -> str:
    title     = entry.get("title", "No title")
    link      = entry.get("link", "")
    source    = entry.get("source", {}).get("title", "Unknown source")
    published = entry.get("published", "")

    try:
        dt = datetime(*entry.published_parsed[:6])
        published = dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        pass

    score     = score_data.get("score", "?")
    reason    = score_data.get("reason", "")
    direction = score_data.get("direction", "neutral")
    emoji     = DIRECTION_EMOJI.get(direction, "⚪")

    return (
        f"🚨 <b>SK Hynix Major News Alert</b>\n\n"
        f"<b>{title}</b>\n\n"
        f"{emoji} <b>{direction.capitalize()}</b> · Score {score}/10\n"
        f"💡 {reason}\n\n"
        f"🗞 {source} · {published}\n\n"
        f"🔗 <a href='{link}'>Read article</a>"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    seen        = load_seen()
    alerted     = 0
    filtered_ai = 0
    fallback_ai = 0

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            aid   = article_id(entry)
            title = entry.get("title", "")

            if aid in seen:
                continue

            if not article_is_today(entry):
                print(f"  ⏭️  Old article skip: {title[:70]}")
                continue

            # Always mark as seen so we don't re-process next run
            seen.add(aid)

            # MiniMax scoring for every same-day article.
            print(f"  🤖 Scoring: {title[:70]}")
            score_data = score_with_minimax(title)

            if score_data is None:
                fallback_ai += 1
                score_data = {
                    "score": "N/A",
                    "reason": "AI unavailable; sending keyword alert",
                    "direction": "neutral",
                }
            elif score_data.get("score", 0) < MIN_ALERT_SCORE:
                score = score_data.get("score", "err") if score_data else "err"
                filtered_ai += 1
                print(f"  ⏭️  AI skip (score {score}): {title[:70]}")
                continue

            # Passes both filters — send alert
            try:
                msg = format_message(entry, score_data)
                send_telegram(msg)
                alerted += 1
                print(f"  ✅ Alert sent (score {score_data['score']}): {title[:70]}")
            except Exception as e:
                print(f"  ⚠️  Telegram send failed: {e}")

    save_seen(seen)
    print(
        f"\nDone — {alerted} alert(s) sent | "
        f"{filtered_ai} AI-filtered | "
        f"{fallback_ai} AI-fallback alert(s)"
    )


if __name__ == "__main__":
    main()
