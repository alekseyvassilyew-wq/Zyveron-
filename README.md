# ZYVERON Bot v4

## Environment variables
- BOT_TOKEN — token from @BotFather
- ADMIN_ID — your numeric Telegram ID
- DB_PATH — optional, default data/zyveron.db

## Admin
Send /admin from the Telegram account whose ID is ADMIN_ID.

The admin panel lets you:
- edit service names, descriptions and prices;
- enter any price text such as `50 €`, `от €50`, `по запросу`, `недоступно`;
- add services;
- view new requests/messages;
- add portfolio photos with captions;
- change the contact shown in the bot.

## Important
The bot stores data in SQLite. On Render, use the included persistent disk configuration so the database survives deploys/restarts.
