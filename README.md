# Arborist

Discord forum archiver bot. Archives forum posts to a GitHub Pages static site.

## How it works

A Python bot connects to Discord, watches configured forum channels, and mirrors every thread, message, and attachment to a local folder. Changes are committed and pushed to a GitHub repo's `gh-pages` branch, which GitHub Pages serves as a static site.

## Setup

```bash
# 1. Clone
git clone https://github.com/yourname/arborist.git
cd arborist

# 2. Install
uv sync

# 3. Configure
cp .env.example .env
# Edit .env with your Discord bot token, channel IDs, and GitHub repo

# 4. Run
uv run python -m bot.main
```

### Discord bot setup

1. Go to https://discord.com/developers/applications
2. Create a new application → Bot → Add Bot
3. Enable **Message Content Intent** and **Server Members Intent**
4. Copy the token into `.env`
5. Invite bot with `bot` + `application.commands` scopes

### Required env vars

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Bot token from Discord Developer Portal |
| `CHANNEL_IDS` | Comma-separated forum channel IDs to watch |
| `GIT_REMOTE_URL` | GitHub repo URL (https://...) |
| `GIT_USER_NAME` | Commit author name |
| `GIT_USER_EMAIL` | Commit author email |

### Optional env vars

| Variable | Default | Description |
|---|---|---|
| `OUTPUT_DIR` | `./output` | Where archived content lives |
| `GIT_BRANCH` | `gh-pages` | Branch to push to |

## Commands

- `/archive channel <id>` — archive a specific channel (or `all`)
- `/archive status` — _(planned)_ show archive status

## Output structure

```
output/
├── index.html                 ← root: all channels
├── styles.css                 ← dark green Discord-like theme
├── attachments/
│   └── {channel_id}/
│       └── {attachment_id}/
│           └── {filename}
└── channels/
    └── {channel_id}/
        ├── index.html         ← channel: thread list
        └── {thread_id}/
            ├── index.html     ← thread: all messages
            └── {message_id}.md  ← raw markdown reference
```

## Download readable backup

On the site, click "Download readable backup" — it fetches the archive, renames ID folders to human names (from YAML frontmatter), and triggers a browser download with a progress bar.

## Design

Dark theme, Discord-like layout, grassy green accent (`#4ade80`), faint green-black background (`#0e100f`).
