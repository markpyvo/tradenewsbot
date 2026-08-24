# tradenewsbot

Single-file bot (`check_news.py`) that alerts on same-day stock news via Telegram.
Runs on a GitHub Actions cron schedule — no server, no database.

## Ticker is configuration, not code

The tracked company/ticker is set entirely through the `STOCK_NAME` environment
variable (with an optional `STOCK_EXTRA_QUERY` for a third, more specific search
term). Never hardcode a company name, ticker, or sector anywhere in the code,
prompts, comments, or workflow file — this repo is public and meant to be forked
and repointed at any ticker by editing GitHub Actions variables only.

## Pipeline (in `check_news.py`, top to bottom)

1. **Trigger gate** — the workflow cron fires twice (16:00 and 17:00 UTC) so the
   9am-Pacific check in `main()` lands correctly across DST; the run that isn't
   9am Pacific exits immediately.
2. **RSS fetch** — three Google News RSS queries built from `STOCK_NAME` and
   `STOCK_EXTRA_QUERY`.
3. **Dedupe + date filter** — dedupe by `md5(link)`, keep only entries published
   on the prior Pacific calendar day (`target_date`).
4. **LLM scoring** (`estimate_with_minimax`) — one MiniMax call per surviving
   headline, returns `{direction, move_pct_low, move_pct_high, confidence, reason}`.
   The prompt explicitly prefers `null` over a low-confidence guess.
5. **Rank + cap** — sort by `move_pct × confidence_weight` descending, keep the
   top `MAX_DAILY_ALERTS` (default 3).
6. **Deliver** — send each via Telegram `sendMessage`.

## Conventions

- Keep it a single script. Don't split into modules or add a framework unless
  the script genuinely outgrows one file.
- No local persistence (no `seen_articles.json` or similar) — dedupe is
  per-run only, scoped to the prior Pacific day's articles. Don't reintroduce
  cross-run state.
- MiniMax failures fall back to a neutral, zero-confidence estimate rather than
  crashing the run — preserve that fallback if you touch `estimate_with_minimax`.
- Secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `MINIMAX_API_KEY`) go in
  GitHub Actions **secrets**; the ticker config (`STOCK_NAME`,
  `STOCK_EXTRA_QUERY`) goes in **variables** — keep that split, don't move
  ticker config into secrets or vice versa.
