# ZYVERON Business Bot v2

Telegram business bot with:
- first-launch language selection: Russian / Latvian / English
- multilingual inline menus
- separate order form using FSM
- request storage in SQLite
- instant admin notifications
- portfolio photos stored as Telegram `file_id`
- admin panel: `/admin`
- basic statistics
- portfolio upload from admin panel
- Render persistent disk configuration

## Environment variables
- `BOT_TOKEN` — token from @BotFather
- `ADMIN_ID` — numeric Telegram ID of the owner/admin
- `DB_PATH` — SQLite path (Render config uses `/var/data/zyveron.db`)

## Run
```bash
pip install -r requirements.txt
export BOT_TOKEN="..."
export ADMIN_ID="123456789"
python bot.py
```

## Admin
Send `/admin` from the Telegram account whose ID is in `ADMIN_ID`.
