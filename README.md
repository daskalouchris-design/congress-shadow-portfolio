# Congress Shadow Portfolio — Web App

Fully automated version: once deployed, this runs itself. No script to
run, no PC that needs to stay on. It's built entirely on free GitHub
infrastructure:

- **GitHub Actions** (free scheduled jobs) checks for new disclosed
  purchases every 2 hours, logs a simulated €50 buy, and takes an hourly
  price snapshot for the chart.
- **GitHub Pages** (free static hosting) serves the dashboard at
  `https://<your-username>.github.io/<repo-name>/`.
- Data lives as JSON files inside the repo — Actions commits updates,
  Pages just serves whatever's currently in the repo. No database, no
  server to manage.

Read this once, before starting: same caveat as always — this pings on
**disclosure**, not on the actual trade (up to ~45 days' legal lag), and
the free Bargo data only covers the last 3 months. Not investment advice.

## One-time setup (~15 minutes)

### 1. Create the repo
- Go to github.com, sign in (or create a free account), click **New repository**.
- Name it anything, e.g. `congress-shadow-portfolio`. Keep it **Public**
  (GitHub Pages is free for public repos; private repos need a paid plan
  to use Pages).
- Upload every file in this folder, preserving the folder structure
  (`.github/workflows/`, `docs/`, `scripts/`). Easiest way: install
  [GitHub Desktop](https://desktop.github.com/), clone your new empty
  repo, drag these files into the local folder, then commit and push.
  Or use the web UI's "Add file → Upload files" and upload the whole tree.

### 2. Add your secrets
In your repo: **Settings → Secrets and variables → Actions → New repository secret**.
Add:
- `BARGO_API_KEY` — get one free at https://www.bargo.ai/free-apis/dash
  (a key isn't strictly required, but the scheduled jobs will run every
  couple hours forever, so you'll want the higher limit).
- `NTFY_TOPIC` — a random, hard-to-guess string, e.g. `congress-x7k2p9`.
  Install the [ntfy app](https://ntfy.sh) on your phone and subscribe to
  this exact topic name.

Optional, same screen but under the **Variables** tab if you want to
change defaults without editing code: `BUY_AMOUNT_EUR` (default 50),
`MIN_TRADES_TO_QUALIFY`, `MAX_MEMBERS_TO_PROFILE`, `TOP_N`.

### 3. Enable GitHub Pages
**Settings → Pages** → under "Build and deployment", Source: **Deploy
from a branch** → Branch: **main**, folder: **/docs** → Save. After a
minute or two your dashboard is live at the URL shown there.

### 4. Kick off the first runs
Go to the **Actions** tab. You'll see three workflows: *Refresh ranking*,
*Check for new trades*, *Snapshot portfolio*. For each one, click into
it and hit **Run workflow** to trigger it manually the first time,
in this order:
1. **Refresh ranking** first (builds `top_30.json` — needed before the
   trade check means anything). If it hits the daily rate limit partway
   through, just run it again — it resumes.
2. **Check for new trades** (safe to run even with an empty portfolio —
   it'll just report nothing new, or start logging buys).
3. **Snapshot portfolio** (safe even with an empty portfolio — it'll
   just note there's nothing to snapshot yet).

After that, you don't need to touch anything — the schedules
(`.github/workflows/*.yml`) take over: ranking refreshes weekly, trade
checks run every 2 hours, snapshots run hourly.

## What you'll see
- The dashboard shows current value, invested, P&L, and a chart with
  1D/1W/1M/1Y/YTD/ALL range buttons.
- A holdings table below the chart, and a "Top 30 watchlist" table
  showing who's currently on your ranked list.
- Your phone buzzes (via ntfy) whenever a new simulated buy is logged.

## Adjusting the schedule
Edit the `cron:` line in the relevant `.yml` file under
`.github/workflows/` and push the change — e.g. want trade checks every
hour instead of every 2? Change `"0 */2 * * *"` to `"0 * * * *"` in
`check_trades.yml`. [crontab.guru](https://crontab.guru) is handy for
building cron expressions. Note: GitHub may delay scheduled runs by a
few minutes during high platform load — irrelevant here given the
45-day disclosure lag anyway.

## Costs
All genuinely free at this scale: GitHub Actions gives public repos
unlimited free minutes; each run here takes well under a minute. GitHub
Pages is free for public repos. Bargo and Yahoo Finance (via `yfinance`)
are both free, no card required.

## Limitations worth knowing
- **History file growth**: `docs/data/history.json` is pruned
  automatically (`snapshot_portfolio.py`) so it won't grow forever, but
  very long-running instances (multi-year) may want coarser pruning —
  easy to tune in that script.
- **yfinance** scrapes Yahoo Finance's public endpoints rather than using
  an official paid API; it's widely used and free but can occasionally
  break if Yahoo changes something — if snapshots start failing, that's
  the first place to check.
- **Public repo = public data**: your portfolio.json, history, and
  top-30 list are visible to anyone who finds the repo (nothing
  sensitive in them, but worth knowing). Secrets (API keys) stay hidden
  regardless.
- If you'd rather run this locally instead of on GitHub, the plain
  Python-script version (no web app) is available too — just ask.
