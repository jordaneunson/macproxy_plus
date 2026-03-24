# Development Notes

## Setup Script (`setup.sh`)

### Adding a New Extension
The extension menu is **hardcoded** in `setup.sh`. When adding a new extension to `extensions/`, you also need to update:

1. `ALL_EXTENSIONS` array — add the extension name
2. `ext_desc()` — add a one-line description for the menu
3. `ext_needs_key()` — if it requires an API key or config value, map it here
4. `ext_key_prompt()` — add a user-friendly prompt for the key (if applicable)

**Future improvement:** Scan `extensions/` dynamically instead of hardcoding.

### How curl install works
Uses the Homebrew pattern: `/bin/bash -c "$(curl -fsSL ...)"` — downloads the full script first, then runs it with stdin free for interactive input.

### Config generation
The header (API keys, enabled extensions) is written with `printf "%b"` for escape sequences. The body (WHITELISTED_DOMAINS, CONVERSION_TABLE, etc.) is appended verbatim from `config.py.example` via `awk >>` to preserve backslashes.

### Bash 3 compatibility
macOS ships with bash 3.2 — no associative arrays (`declare -A`). Uses parallel indexed arrays instead.
