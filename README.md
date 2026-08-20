# World News — GitHub starter

Copy the contents of this folder into the root of the separate GitHub repository you created for the World news feed.

Then:

1. Repository **Settings → Secrets and variables → Actions → New repository secret**.
2. Name it exactly `DISCORD_BOT_TOKEN` and paste the bot token there.
3. Repository **Settings → Pages → Build and deployment → Source → GitHub Actions**.
4. Open **Actions → Update World News → Run workflow** once.
5. After the run succeeds, GitHub Pages exposes `news.json` at your repository Pages URL.

The scheduled workflow refreshes the feed every 10 minutes. The token is available only to the GitHub Action and is never written to `news.json`, committed to the repository, or distributed with World.

Configured relay channels are already in `data/news/sources.json`:

- Project Zomboid: `1540046686301200454`
- Unofficial PZ Mapping Discord — News: `1540046752483123202`
- Unofficial PZ Mapping Discord — Event News: `1540046789091131432`
