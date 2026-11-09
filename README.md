# Discord Account Humanizer

A tool that bulk-customizes Discord accounts. Updates avatars, display names, bios, pronouns, and HypeSquad houses across many accounts at once.

---

## Project Structure

```text
Humanizer/
├── main.py              # Main runner
├── config.json          # Behavior & customization toggles
├── README.md
├── input/
│   ├── tokens.txt       # Input accounts (email:pass:token or raw token)
│   └── proxies.txt      # Optional HTTP proxies
├── data/
│   ├── bios.txt         # Bio presets (1 per line)
│   ├── names.txt        # Display names (1 per line)
│   └── pronouns.txt     # Pronoun options (1 per line)
├── avatar/              # Put your profile pictures here (.png, .jpg, .jpeg)
└── output/
    ├── success.txt      # Finished accounts
    └── failed.txt       # Failed / dead accounts
```

---

## Getting Started

### 1. Requirements

You need Python 3.9 or newer.

```bash
pip install primp websocket-client pillow
```

### 2. Add Your Data

1. Tokens - put your accounts in `input/tokens.txt`. Accepted formats:
   - `email:password:token`
2. Avatars - drop any `.png`, `.jpg`, or `.jpeg` files into the `avatar/` folder. One gets picked at random and resized.
3. Bios, Names, Pronouns - write whatever you want into `data/bios.txt`, `data/names.txt`, and `data/pronouns.txt`.
4. Proxies (optional) - put your proxies in `input/proxies.txt`. Leave it empty to run direct.

### 3. Configure (`config.json`)

Change these to whatever you want updated:

```json
{
  "max_threads": 5,
  "avatar_dimension": 256,
  "max_avatar_cache": 100,
  "update_display_name": true,
  "update_bio": true,
  "update_pronouns": true,
  "update_avatar": true,
  "update_hypesquad": true,
  "proxy": false,
  "retry_limit": 1
}
```

### 4. Run

```bash
python main.py
```

Type the thread count when it asks (or hit `Enter` to use the config default) and let it run. Done accounts go to `output/success.txt` and get removed from `input/tokens.txt`. do not skid this or resell this, this is free and open source

---

> this is for educational purposes only
