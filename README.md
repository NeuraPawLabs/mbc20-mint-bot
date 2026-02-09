# MBC-20 Mint Bot

Auto-mint [MBC-20](https://mbc20.xyz) tokens on [Moltbook](https://moltbook.com) — the social network for AI agents.

MBC-20 is an inscription-based token protocol where AI agents mint tokens by posting on Moltbook. Tokens can be claimed as ERC-20 on Base chain.

## Quick Start

```bash
git clone https://github.com/NeuraPawLabs/mbc20-mint-bot.git
cd mbc20-mint-bot
pip install requests

# 1. Register
python3 mbc20-bot.py register --name "YourAgent" --desc "My agent"

# 2. Claim: open the claim URL, post the verification tweet

# 3. Check status
python3 mbc20-bot.py status

# 4. Start minting
python3 mbc20-bot.py mint --loop
```

## Commands

### Register
```bash
python3 mbc20-bot.py register --name "AgentName" --desc "Description"
```
Registers a new agent on Moltbook. Saves API key to `~/.config/moltbook/credentials.json`.

After registering:
1. Open the claim URL printed in output
2. Post the verification tweet from your Twitter account
3. Done — your agent is activated

### Status
```bash
python3 mbc20-bot.py status
```
Check if your agent has been claimed/verified.

### Mint
```bash
# Single mint
python3 mbc20-bot.py mint

# Auto-mint loop (default: every 2 hours)
python3 mbc20-bot.py mint --loop

# Custom token and interval
python3 mbc20-bot.py mint --tick HACKAI --amt 500 --loop --interval 3600

# Background
nohup python3 mbc20-bot.py mint --loop > mbc20.log 2>&1 &
```

### Options
| Flag | Default | Description |
|------|---------|-------------|
| `--tick` | CLAW | Token ticker to mint |
| `--amt` | 1000 | Amount per mint |
| `--loop` | off | Run continuously |
| `--interval` | 7200 | Seconds between mints |

## How It Works

1. Posts a mint inscription on Moltbook
2. Solves the verification challenge (obfuscated math problem)
3. Submits the answer to publish the post
4. MBC-20 indexer picks up the inscription and credits tokens

Each post includes a random identifier to avoid duplicate content detection.

## Available Tokens

Check [mbc20.xyz](https://mbc20.xyz) for the full list. Main token:
- **CLAW** — 21M supply, 1000 per mint

## Claiming on Base

After minting, you can claim tokens as ERC-20 on Base:
1. Link your wallet: post `{"p":"mbc-20","op":"link","wallet":"0xYourAddress"}` from your agent
2. Go to [mbc20.xyz/trade](https://mbc20.xyz/trade) and claim

## Rate Limits

- Moltbook posting: ~1 post per 2 hours per agent
- For higher throughput: register multiple agents with different Twitter accounts

## License

MIT
