# year1738 Discord Bot 🤖

A comprehensive, fully featured Discord bot built with `discord.py`. Includes moderation, auto-mod, activity tracking, leaderboards, react roles, polls, utility commands, and fun commands.

---

## Features

### ⚙️ Moderation
- `/ban` `/kick` `/warn` `/warnings` `/clearwarnings`
- `/mute` `/unmute` (with auto-expiry)
- `/clear` (purge messages, optionally by user)
- `/unban` (by user ID)
- All actions logged to a configurable mod-log channel

### 🤖 Auto-Mod
- Profanity filtering (auto-delete + warn)
- Spam detection (rate limiting + repeated text)
- Mass mention spam detection
- Discord invite link blocking
- All-caps spam detection
- Escalating actions: warn → mute → kick based on violation count

### 📊 Activity Tracking & Leaderboards
- Tracks voice channel hours and message counts automatically
- `/leaderboard hours` — Top 10 by VC hours
- `/leaderboard messages` — Top 10 by messages sent
- `/leaderboard points` — Top 10 by reputation points

### 🎭 Community
- `/reactrole` — Assign roles when members react to a message
- `/poll` — Simple 👍/👎 poll
- `/custompoll` — Poll with up to 4 options
- Welcome messages for new members

### 🛠️ Utilities
- `/ping` `/userinfo` `/serverinfo` `/avatar` `/membercount` `/embed` `/help`

### 🎉 Fun
- `/joke` `/8ball` `/dice` `/flip` `/random`

---

## File Structure

```
year1738/
├── bot.py                 # Main entry point
├── database.py            # SQLite setup and queries
├── config.json            # Configurable settings
├── cogs/
│   ├── moderation.py      # Moderation commands + logging
│   ├── tracking.py        # Voice/message activity tracking
│   ├── leaderboard.py     # Leaderboard commands
│   ├── auto_mod.py        # Auto-moderation
│   ├── react_roles.py     # React role system
│   ├── polls.py           # Poll creation
│   ├── utilities.py       # Utility commands
│   └── fun.py             # Fun commands
├── requirements.txt
├── Procfile               # Railway deployment
└── .env.example           # Environment variable template
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/narrwq-cell/year1738.git
cd year1738
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create your bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application → Bot → Enable all **Privileged Gateway Intents**
3. Copy your bot token

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```
DISCORD_TOKEN=your_bot_token_here
DATABASE_PATH=bot.db
MOD_LOG_CHANNEL_ID=your_channel_id_here
WELCOME_CHANNEL_ID=your_channel_id_here
```

### 5. Configure settings

Edit `config.json` to customize:
- `mod_log_channel_id` — Channel for moderation logs
- `welcome_channel_id` — Channel for welcome messages
- `muted_role_name` — Name of the muted role (auto-created if missing)
- `auto_mod` — Auto-mod thresholds and settings
- `profanity_words` — List of words to filter

### 6. Run

```bash
python bot.py
```

---

## Railway Deployment

1. Push this repository to GitHub
2. Go to [Railway](https://railway.app) → New Project → Deploy from GitHub repo
3. Add environment variables from `.env.example` in the Railway dashboard
4. Railway automatically uses the `Procfile` — no extra configuration needed

---

## Permissions

The bot requires the following permissions:
- **Manage Roles** (for react roles and muting)
- **Ban Members / Kick Members**
- **Manage Messages** (for clearing and auto-mod)
- **Send Messages**, **Embed Links**, **Add Reactions**
- **View Channels**, **Read Message History**

Enable all **Privileged Gateway Intents** in the Developer Portal:
- Presence Intent
- Server Members Intent
- Message Content Intent
