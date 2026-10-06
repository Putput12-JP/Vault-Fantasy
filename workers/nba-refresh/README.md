# nba-refresh

Cloudflare Worker that starts the NBA GitHub workflows on time and serves the live board without GitHub's CDN lag.

Deploy (once):

    cd workers/nba-refresh
    npx wrangler login
    npx wrangler secret put GITHUB_TOKEN      # fine-grained token, this repo only, Actions: read and write
    npx wrangler deploy

Then set `NBA_WORKER` in `nba/ui/projections.template.html` to the printed `https://nba-refresh.<you>.workers.dev`,
re-render (`python3 nba/scripts/render_app.py`) and push. The Refresh button and the 30 second board appear on the site.
