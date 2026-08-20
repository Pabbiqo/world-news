# World News Collector

This helper reads the three **relay channels on your own Discord server** and writes `data/news/feed.json` for the World startup screen.

It does **not** connect to the Project Zomboid or Unofficial PZ Mapping Discord servers directly. Discord's Announcement Channel Follow feature has already copied published posts into your relay channels.

## Configured relay channels

- Project Zomboid: `1540046686301200454`
- Unofficial PZ Mapping Discord — News: `1540046752483123202`
- Unofficial PZ Mapping Discord — Event News: `1540046789091131432`

The IDs live in `data/news/sources.json`, not in the Python code.

## Bot permissions

The bot only needs these permissions in the three relay channels:

- View Channel
- Read Message History

`Message Content Intent` should be enabled in the Discord Developer Portal so message text/embeds can be normalized reliably.

## Token

Never put the token in World, this repository, a ZIP, `sources.json`, or `feed.json`.

For a single PowerShell window:

```powershell
$env:DISCORD_BOT_TOKEN='your-token-here'
```

Then run:

```powershell
python tools/news-collector/collect_news.py
```

or double-click `Collect News Once.bat` from this folder after setting the environment variable in the same process environment.

For continuous local testing:

```powershell
python tools/news-collector/collect_news.py --watch 300
```

This polls only once every five minutes. It uses Discord's REST API and therefore does not need a permanently connected Gateway bot.

## Output

The collector writes `data/news/feed.json` atomically. World already reads that file on the startup screen.

The collector keeps normalized title, summary, published time, image, source and a usable source/original link when Discord exposes one. Diagnostic relay IDs are also retained in the JSON but World does not need to display them.

Later, the exact same normalized `feed.json` can be published on a small HTTPS/static host. At that point World clients can fetch one public feed and no end user needs Discord or the bot.
