# token-usage-dash

Pushes Claude and OpenAI Codex subscription plan usage to a [dot.mindreset.tech](https://dot.mindreset.tech) e-ink display as a 296×152 image.

![Token usage on e-ink display](docs/preview.jpg)

## What it shows

- **Claude** — 5-hour and 7-day utilization (% used, % left, time to reset)
- **OpenAI Codex** — 5-hour and weekly utilization

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure

```bash
cp .env.sample .env
```

Edit `.env` with your credentials:

| Key | Description |
|-----|-------------|
| `QUOTE_API_KEY` | Bearer token from dot.mindreset.tech |
| `QUOTE_DEVICE_ID` | Device serial number |
| `OPENAI_ENABLED` | Set to `false` to skip OpenAI fetching (default: `true`) |
| `UPDATE_INTERVAL` | Seconds between updates in loop mode (default: `1800`) |
| `CODEX_ACCESS_TOKEN` | Override Codex OAuth token (optional; default: read from `~/.codex/auth.json`) |
| `CODEX_ACCOUNT_ID` | Override Codex account ID (optional) |

### 3. Claude auth

Claude credentials are read automatically from `~/.claude/.credentials.json` (created when you authenticate with [Claude Code](https://claude.ai/code)).

### 4. OpenAI Codex auth

Codex credentials are read automatically from `~/.codex/auth.json` (created when you authenticate with [Codex](https://github.com/openai/codex)). Run `codex` once to log in.

Alternatively, set `CODEX_ACCESS_TOKEN` in `.env` to supply the token directly.

### 5. Add Image API content in Content Studio

In the dot.mindreset.tech app, add an **Image API** content slot to your device. The script targets this slot.

## Usage

```bash
# One-shot update
uv run display.py

# Loop every 30 minutes
uv run display.py --loop

# Loop with custom interval and save preview PNG
uv run display.py --loop --interval 900 --preview

# Preview image without pushing to device
uv run render.py   # saves to /tmp/usage_preview.png

# Print usage to terminal only
uv run usage.py
uv run usage.py --claude-only
uv run usage.py --openai-only
```

## Files

| File | Purpose |
|------|---------|
| `usage.py` | Fetches Claude and OpenAI usage data |
| `render.py` | Renders the 296×152 PNG image |
| `display.py` | Orchestrates fetch → render → push to device |
