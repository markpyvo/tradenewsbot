# tradenewsbot

SK Hynix news alerts from Google News RSS, filtered locally and sent to Telegram.

## Setup

1. Create a Telegram bot with @BotFather and copy the bot token.
2. Start a chat with the bot, then get your numeric chat ID from `getUpdates`.
3. Add these GitHub Actions secrets:
	- `TELEGRAM_BOT_TOKEN`
	- `TELEGRAM_CHAT_ID`
	- `MINIMAX_API_KEY`
	- `MINIMAX_MODEL` if you want to override the default `MiniMax-M3`
4. Push the repo and run the workflow at `.github/workflows/sk_hynix_alert.yml`.

## Local run

```bash
cp .env.example .env
# fill in the values in .env, then load them in your shell
pip install -r requirements.txt
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... MINIMAX_API_KEY=... MINIMAX_MODEL=MiniMax-M3 python check_news.py
```

Required variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `MINIMAX_API_KEY`
- `MINIMAX_MODEL` is optional and defaults to `MiniMax-M3`
