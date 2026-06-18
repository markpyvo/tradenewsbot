import os
import json
import hashlib
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID    = os.environ["TELEGRAM_CHAT_ID"]
MINIMAX_API_KEY     = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_MODEL       = os.environ.get("MINIMAX_MODEL") or "MiniMax-M3"
MINIMAX_API_URL     = os.environ.get("MINIMAX_API_URL", "https://api.minimax.io/v1/chat/completions")
ALLOW_ANY_TIME      = os.environ.get("ALLOW_ANY_TIME", "false").lower() == "true"
PACIFIC_TZ          = ZoneInfo("America/Los_Angeles")
MAX_DAILY_ALERTS    = 3

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=SK+Hynix&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=SK+Hynix+stock&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=SK+Hynix+HBM+DRAM&hl=en-US&gl=US&ceid=US:en",
]

# ── Step 2: MiniMax move estimate ────────────────────────────────────────────
ESTIMATE_SYSTEM = """You are a financial analyst specializing in semiconductor stocks.
Your job is to estimate how much a news headline about SK Hynix could move the
stock price over the next trading session.

Respond ONLY with a JSON object like:
{"direction": "bullish", "move_pct_low": 0.8, "move_pct_high": 1.4, "confidence": "medium", "reason": "one-line reason"}

Rules:
- move_pct_low and move_pct_high are absolute percent move estimates, not signed
- direction: "bullish", "bearish", or "neutral"
- confidence: "low", "medium", or "high"
- reason: max 12 words explaining the estimate
- If you cannot estimate with reasonable confidence, set move_pct_low and move_pct_high to null
- Do not invent precision; prefer null over a guess that is not defensible
- If the article is likely noise or already reflected in price, use low confidence and null estimates

Good estimates should reflect the next trading session's likely swing, not a long-term target."""

def estimate_with_minimax(title: str) -> dict:
    """Call MiniMax to estimate the price move for the headline."""
    if not MINIMAX_API_KEY:
        print("  ⚠️  MiniMax API key missing; using fallback estimate")
        return None

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "content-type": "application/json",
    }
    body = {
        "model": MINIMAX_MODEL,
        "max_tokens": 100,
        "messages": [
            {"role": "system", "content": ESTIMATE_SYSTEM},
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
            print(f"  ⚠️  MiniMax estimate failed: {e}")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def article_id(entry) -> str:
    return hashlib.md5((entry.get("link") or entry.get("title", "")).encode()).hexdigest()

def article_pacific_date(entry):
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return None

    published_dt = datetime(*parsed[:6], tzinfo=timezone.utc)
    return published_dt.astimezone(PACIFIC_TZ).date()

def parse_confidence(confidence: str) -> float:
    mapping = {"high": 1.0, "medium": 0.7, "low": 0.4}
    return mapping.get(str(confidence).lower(), 0.0)

def parse_move_pct(estimate_data: dict) -> float:
    try:
        low = estimate_data.get("move_pct_low")
        high = estimate_data.get("move_pct_high")
        if low is None or high is None:
            single = estimate_data.get("move_pct")
            if single is None:
                return 0.0
            return float(single)
        return (float(low) + float(high)) / 2.0
    except Exception:
        return 0.0

def format_move_estimate(estimate_data: dict) -> str:
    low = estimate_data.get("move_pct_low")
    high = estimate_data.get("move_pct_high")
    single = estimate_data.get("move_pct")

    if low is None or high is None:
        if single is None:
            return "Estimated move: unavailable"
        return f"Estimated move: ~{float(single):.1f}%"

    if abs(float(low) - float(high)) < 0.2:
        return f"Estimated move: ~{(float(low) + float(high)) / 2.0:.1f}%"

    return f"Estimated move: {float(low):.1f}% to {float(high):.1f}%"

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

def format_message(entry, estimate_data: dict) -> str:
    title     = entry.get("title", "No title")
    link      = entry.get("link", "")
    source    = entry.get("source", {}).get("title", "Unknown source")
    published = entry.get("published", "")

    try:
        dt = datetime(*entry.published_parsed[:6])
        published = dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        pass

    reason    = estimate_data.get("reason", "")
    direction = estimate_data.get("direction", "neutral")
    confidence = estimate_data.get("confidence", "")
    emoji     = DIRECTION_EMOJI.get(direction, "⚪")

    return (
        f"🚨 <b>SK Hynix Major News Alert</b>\n\n"
        f"<b>{title}</b>\n\n"
        f"{emoji} <b>{direction.capitalize()}</b> · {format_move_estimate(estimate_data)}\n"
        f"{('Confidence: ' + str(confidence).capitalize()) if confidence else ''}\n"
        f"💡 {reason}\n\n"
        f"🗞 {source} · {published}\n\n"
        f"🔗 <a href='{link}'>Read article</a>"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    alerted     = 0
    scored      = 0

    now_pacific = datetime.now(PACIFIC_TZ)
    if not ALLOW_ANY_TIME and now_pacific.hour != 9:
        print(f"  ⏭️  Not 9am Pacific yet ({now_pacific.strftime('%H:%M %Z')}); exiting")
        return

    target_date = now_pacific.date() - timedelta(days=1)
    candidates = []
    seen_run = set()

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            aid   = article_id(entry)
            title = entry.get("title", "")

            if aid in seen_run:
                continue

            if article_pacific_date(entry) != target_date:
                continue

            seen_run.add(aid)

            # Score every article from the prior Pacific day, then rank them.
            print(f"  🤖 Scoring: {title[:70]}")
            estimate_data = estimate_with_minimax(title)
            scored += 1

            if estimate_data is None:
                estimate_data = {
                    "move_pct_low": None,
                    "move_pct_high": None,
                    "confidence": "low",
                    "reason": "AI unavailable; no reliable estimate",
                    "direction": "neutral",
                }

            published_dt = None
            parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            if parsed:
                published_dt = datetime(*parsed[:6], tzinfo=timezone.utc).astimezone(PACIFIC_TZ)

            candidates.append({
                "entry": entry,
                "estimate_data": estimate_data,
                "rank": parse_move_pct(estimate_data) * parse_confidence(estimate_data.get("confidence", "")),
                "published_dt": published_dt or datetime.min.replace(tzinfo=PACIFIC_TZ),
            })

    candidates.sort(key=lambda item: (item["rank"], item["published_dt"]), reverse=True)

    for candidate in candidates[:MAX_DAILY_ALERTS]:
        entry = candidate["entry"]
        estimate_data = candidate["estimate_data"]
        title = entry.get("title", "")

        try:
            msg = format_message(entry, estimate_data)
            send_telegram(msg)
            alerted += 1
            print(f"  ✅ Alert sent (rank {candidate['rank']:.2f}): {title[:70]}")
        except Exception as e:
            print(f"  ⚠️  Telegram send failed: {e}")

    print(
        f"\nDone — {alerted} alert(s) sent | "
        f"{scored} article(s) scored | "
        f"{len(candidates)} candidate(s) from yesterday"
    )


if __name__ == "__main__":
    main()
