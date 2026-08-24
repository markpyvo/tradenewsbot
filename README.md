# tradenewsbot

Same-day stock news alerts for any ticker: pulled from Google News RSS,
deduplicated and filtered locally, scored by an LLM for likely price impact,
and sent to Telegram. Runs on a GitHub Actions schedule — no server required.

## Setup

1. Create a Telegram bot with @BotFather and copy the bot token.
2. Start a chat with the bot, then get your numeric chat ID from `getUpdates`.
3. Add these GitHub Actions **secrets** (Settings → Secrets and variables → Actions → Secrets):
	- `TELEGRAM_BOT_TOKEN`
	- `TELEGRAM_CHAT_ID`
	- `MINIMAX_API_KEY`
	- `MINIMAX_MODEL` if you want to override the default `MiniMax-M3`
4. Add these GitHub Actions **variables** (same page, "Variables" tab):
	- `STOCK_NAME` — the company or ticker to track, e.g. `Nvidia` or `NVDA`
	- `STOCK_EXTRA_QUERY` (optional) — a third, more specific search term, e.g. `Nvidia data center`. Defaults to `"<STOCK_NAME> earnings"`.
5. Push the repo and run the workflow at `.github/workflows/news_alert.yml` (or wait for the daily schedule).

## Local run

```bash
cp .env.example .env
# fill in the values in .env, then load them in your shell
pip install -r requirements.txt
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... MINIMAX_API_KEY=... MINIMAX_MODEL=MiniMax-M3 STOCK_NAME="Nvidia" python check_news.py
```

Required variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `MINIMAX_API_KEY`
- `STOCK_NAME` — the company or ticker to track
- `MINIMAX_MODEL` is optional and defaults to `MiniMax-M3`
- `STOCK_EXTRA_QUERY` is optional and defaults to `"<STOCK_NAME> earnings"`

## How it works

1. A scheduled run fires at 16:00 and 17:00 UTC; the script only proceeds once it's
   9am Pacific, so it self-selects the correct run across the DST shift.
2. It pulls three Google News RSS searches built from `STOCK_NAME` and
   `STOCK_EXTRA_QUERY`, deduplicates by article link, and keeps only headlines
   published on the prior Pacific calendar day.
3. Each surviving headline is scored by MiniMax, which returns a direction,
   a confidence level, and an estimated price move — the model is instructed
   to return `null` rather than guess when it isn't confident.
4. Headlines are ranked by `move_pct × confidence_weight` and the top 3 per
   day are sent to Telegram.

Want a different ticker? Just change `STOCK_NAME` — no code changes needed.
