# SK Hynix News Alert — Setup Guide

Get a free Telegram message every time a new SK Hynix article drops,
powered by Google News RSS + GitHub Actions (no paid services needed).

---

## Step 1 — Create your Telegram Bot (2 min)

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts (pick any name/username)
3. BotFather gives you a token like `123456:ABCdef...` — **copy it**

Next, get your Chat ID:
1. Start a chat with your new bot (search its username, press Start)
2. Visit this URL in your browser (replace `YOUR_TOKEN`):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. Look for `"id"` inside `"chat"` — that number is your **Chat ID**

---

## Step 2 — Create a GitHub Repository

1. Go to https://github.com/new
2. Create a **private** repository (e.g. `sk-hynix-alert`)
3. Upload these files maintaining the folder structure:
   ```
   check_news.py
   .github/
     workflows/
       sk_hynix_alert.yml
   ```
   You can drag-and-drop files in the GitHub UI, or use git.

---

## Step 3 — Add Secrets to GitHub

1. In your repo, go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret** and add:

   | Secret name          | Value                        |
   |----------------------|------------------------------|
   | `TELEGRAM_BOT_TOKEN` | The token from BotFather     |
   | `TELEGRAM_CHAT_ID`   | Your numeric Chat ID         |

---

## Step 4 — Enable Actions & Test

1. Go to the **Actions** tab in your repo
2. If prompted, click **"I understand my workflows, go ahead and enable them"**
3. Click **SK Hynix News Alert** → **Run workflow** to trigger a manual test
4. Check your Telegram — you should receive alerts for recent articles!

---

## How It Works

- GitHub Actions runs the script **every hour** (free, no server needed)
- The script fetches Google News RSS for "SK Hynix"
- New articles are sent to your Telegram bot
- Already-seen articles are cached so you never get duplicates

---

## Customization

**Check more/less often** — edit the cron line in the workflow file:
```yaml
- cron: "0 * * * *"    # every hour (default)
- cron: "0 */4 * * *"  # every 4 hours
- cron: "0 9 * * *"    # once a day at 9am UTC
```

**Add more search terms** — edit `RSS_FEEDS` in `check_news.py`:
```python
"https://news.google.com/rss/search?q=SK+Hynix+earnings&hl=en-US&gl=US&ceid=US:en",
```

---

## Troubleshooting

- **No updates in getUpdates?** Make sure you sent a message to the bot first.
- **Workflow not running?** GitHub may disable scheduled workflows on inactive repos — just push a small commit to re-activate.
- **"Chat not found" error?** Double-check the Chat ID is correct and the bot was started.
