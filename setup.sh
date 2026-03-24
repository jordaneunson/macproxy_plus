#!/usr/bin/env bash
# =============================================================================
#  MacProxy Plus Setup
#  For retro computing enthusiasts who just want to surf the web on vintage iron
# =============================================================================

set -e

# ── Colors & ASCII flair ──────────────────────────────────────────────────────
BOLD='\033[1m'
DIM='\033[2m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
RESET='\033[0m'

banner() {
  echo ""
  echo -e "${CYAN}${BOLD}"
  echo "  ╔╦╗╔═╗╔═╗╔═╗╦═╗╔═╗═╗ ╦╦ ╦  ╔═╗╦  ╦ ╦╔═╗"
  echo "  ║║║╠═╣║  ╠═╝╠╦╝║ ║╔╩╦╝╚╦╝  ╠═╝║  ║ ║╚═╗"
  echo "  ╩ ╩╩ ╩╚═╝╩  ╩╚═╚═╝╩ ╚═ ╩   ╩  ╩═╝╚═╝╚═╝"
  echo -e "${RESET}"
  echo -e "${DIM}  Bringing the modern web to vintage machines since... well, now.${RESET}"
  echo ""
}

print_step() {
  echo -e "\n${MAGENTA}${BOLD}▶ $1${RESET}"
}

print_ok() {
  echo -e "${GREEN}  ✓ $1${RESET}"
}

print_warn() {
  echo -e "${YELLOW}  ⚠ $1${RESET}"
}

print_err() {
  echo -e "${RED}  ✗ $1${RESET}"
}

# ── Docker check ──────────────────────────────────────────────────────────────
check_docker() {
  print_step "Checking for Docker..."

  if ! command -v docker &>/dev/null; then
    print_err "Docker is not installed."
    echo ""
    echo -e "  Please install Docker Desktop first:"
    echo -e "  ${CYAN}https://www.docker.com/products/docker-desktop/${RESET}"
    echo ""
    exit 1
  fi
  print_ok "Docker found: $(docker --version | head -1)"

  # Check docker compose (v2 plugin or v1 standalone)
  if docker compose version &>/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
    print_ok "Docker Compose found: $(docker compose version --short 2>/dev/null || docker compose version | head -1)"
  elif command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE="docker-compose"
    print_ok "Docker Compose found: $(docker-compose --version | head -1)"
  else
    print_err "Docker Compose is not available."
    echo ""
    echo -e "  Please install Docker Desktop (which includes Compose):"
    echo -e "  ${CYAN}https://www.docker.com/products/docker-desktop/${RESET}"
    echo ""
    exit 1
  fi

  # Make sure the Docker daemon is actually running
  if ! docker info &>/dev/null 2>&1; then
    print_err "Docker daemon is not running."
    echo ""
    echo -e "  Please start Docker Desktop and try again."
    echo ""
    exit 1
  fi
}

# ── Repo check / clone ────────────────────────────────────────────────────────
ensure_in_repo() {
  REPO_URL="https://github.com/jordaneunson/macproxy_plus"

  # If we're already inside the repo, great
  if [[ -f "proxy.py" && -f "config.py.example" ]]; then
    print_ok "Already inside the MacProxy Plus repo."
    return
  fi

  print_step "Cloning MacProxy Plus..."
  if ! command -v git &>/dev/null; then
    print_err "Git is not installed. Please install Git and try again."
    exit 1
  fi

  git clone "$REPO_URL" macproxy_plus
  cd macproxy_plus
  print_ok "Cloned into ./macproxy_plus"
}

# ── Extensions ────────────────────────────────────────────────────────────────
# All available extensions (excluding 'override' which is internal)
ALL_EXTENSIONS=(
  chatgpt
  claude
  gemini
  hackaday
  hacksburg
  hunterirving
  jordaneunson
  kagi
  kimi
  mistral
  notyoutube
  npr
  reddit
  waybackmachine
  weather
  websimulator
  wiby
  wikipedia
)

# Extensions that ship with nice descriptions for the menu
ext_desc() {
  case "$1" in
    chatgpt)      echo "ChatGPT — chat with OpenAI's GPT models (requires API key)" ;;
    claude)       echo "Claude — Anthropic's AI assistant (requires API key)" ;;
    gemini)       echo "Gemini — Google's AI assistant (requires API key)" ;;
    hackaday)     echo "Hackaday — text-only hacker news & articles" ;;
    hacksburg)    echo "Hacksburg — local hackerspace portal" ;;
    hunterirving) echo "HunterIrving — personal page extension" ;;
    jordaneunson) echo "JordanEunson — personal page extension" ;;
    kagi)         echo "Kagi — privacy-respecting search (requires session token)" ;;
    kimi)         echo "Kimi — Moonshot AI assistant (requires API key)" ;;
    mistral)      echo "Mistral — Mistral AI chat (requires API key)" ;;
    notyoutube)   echo "(not) YouTube — vintage video player via MacFlim" ;;
    npr)          echo "NPR — text-only NPR news articles" ;;
    reddit)       echo "Reddit — browse subreddits with dithered images" ;;
    waybackmachine) echo "Wayback Machine — browse the web as it existed in the past" ;;
    weather)      echo "Weather — US weather forecast by ZIP code" ;;
    websimulator) echo "Web Simulator — AI-generated imagined websites (requires API key)" ;;
    wiby)         echo "Wiby — handcrafted personal webpage search engine" ;;
    wikipedia)    echo "Wikipedia — browse 6M+ encyclopedia articles" ;;
    *)            echo "$1" ;;
  esac
}

# Which extensions need what credential
ext_needs_key() {
  case "$1" in
    chatgpt)      echo "OPEN_AI_API_KEY" ;;
    claude)       echo "ANTHROPIC_API_KEY" ;;
    gemini)       echo "GEMINI_API_KEY" ;;
    mistral)      echo "MISTRAL_API_KEY" ;;
    kagi)         echo "KAGI_SESSION_TOKEN" ;;
    kimi)         echo "KIMI_API_KEY" ;;
    websimulator) echo "ANTHROPIC_API_KEY" ;;
    weather)      echo "ZIP_CODE" ;;
    *)            echo "" ;;
  esac
}

ext_key_prompt() {
  case "$1" in
    OPEN_AI_API_KEY)    echo "Enter your OpenAI API key" ;;
    ANTHROPIC_API_KEY)  echo "Enter your Anthropic API key" ;;
    GEMINI_API_KEY)     echo "Enter your Google Gemini API key" ;;
    MISTRAL_API_KEY)    echo "Enter your Mistral API key" ;;
    KAGI_SESSION_TOKEN) echo "Enter your Kagi session token" ;;
    KIMI_API_KEY)       echo "Enter your Kimi API key" ;;
    ZIP_CODE)           echo "Enter your US ZIP code (for weather)" ;;
    *)                  echo "Enter value for $1" ;;
  esac
}

# Interactive extension toggle menu
run_extension_menu() {
  # enabled[] tracks which are on (1) or off (0)
  declare -A enabled
  for ext in "${ALL_EXTENSIONS[@]}"; do
    enabled[$ext]=0
  done

  while true; do
    clear
    banner
    echo -e "${WHITE}${BOLD}  ── Extension Menu ──────────────────────────────────────────${RESET}"
    echo -e "${DIM}  Use the number to toggle an extension on/off. Press ${WHITE}s${DIM} when done.${RESET}"
    echo ""

    local i=1
    for ext in "${ALL_EXTENSIONS[@]}"; do
      if [[ "${enabled[$ext]}" == "1" ]]; then
        status="${GREEN}[ON] ${RESET}"
      else
        status="${DIM}[off]${RESET}"
      fi
      printf "  ${BOLD}%2d)${RESET} %b %-12s %b%s%b\n" \
        "$i" "$status" "$ext" "${DIM}" "$(ext_desc "$ext")" "${RESET}"
      ((i++))
    done

    echo ""
    echo -e "${DIM}  ────────────────────────────────────────────────────────────${RESET}"
    echo -e "  ${BOLD}a)${RESET} Enable all   ${BOLD}n)${RESET} Disable all   ${BOLD}s)${RESET} Save & continue"
    echo ""
    read -rp "  Toggle #: " choice

    if [[ "$choice" == "s" || "$choice" == "S" ]]; then
      break
    elif [[ "$choice" == "a" || "$choice" == "A" ]]; then
      for ext in "${ALL_EXTENSIONS[@]}"; do enabled[$ext]=1; done
    elif [[ "$choice" == "n" || "$choice" == "N" ]]; then
      for ext in "${ALL_EXTENSIONS[@]}"; do enabled[$ext]=0; done
    elif [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#ALL_EXTENSIONS[@]} )); then
      local idx=$((choice - 1))
      local ext="${ALL_EXTENSIONS[$idx]}"
      if [[ "${enabled[$ext]}" == "1" ]]; then
        enabled[$ext]=0
      else
        enabled[$ext]=1
      fi
    else
      print_warn "Unrecognized input, try again."
      sleep 0.8
    fi
  done

  # Export selected extensions for use outside the function
  SELECTED_EXTENSIONS=()
  for ext in "${ALL_EXTENSIONS[@]}"; do
    if [[ "${enabled[$ext]}" == "1" ]]; then
      SELECTED_EXTENSIONS+=("$ext")
    fi
  done
}

# ── Collect credentials ───────────────────────────────────────────────────────
collect_credentials() {
  declare -gA CREDENTIALS

  # Some extensions share a key (claude + websimulator both need ANTHROPIC_API_KEY)
  # so we track which keys we've already asked for
  declare -A asked

  echo ""
  print_step "Collecting API keys for enabled extensions..."

  for ext in "${SELECTED_EXTENSIONS[@]}"; do
    local key
    key="$(ext_needs_key "$ext")"
    [[ -z "$key" ]] && continue
    [[ "${asked[$key]+set}" == "set" ]] && continue

    local prompt
    prompt="$(ext_key_prompt "$key")"
    echo ""
    echo -e "  ${CYAN}${BOLD}$ext${RESET} needs ${YELLOW}$key${RESET}"

    while true; do
      if [[ "$key" == *TOKEN* || "$key" == *KEY* ]]; then
        read -rsp "  $prompt: " value
        echo ""
      else
        read -rp "  $prompt: " value
      fi

      if [[ -n "$value" ]]; then
        CREDENTIALS[$key]="$value"
        asked[$key]=1
        print_ok "Got it."
        break
      else
        print_warn "Value cannot be empty. Try again (or Ctrl+C to quit)."
      fi
    done
  done
}

# ── Write config.py ───────────────────────────────────────────────────────────
write_config() {
  print_step "Writing config.py..."

  # Read the example file to preserve all settings below the extensions block
  local example_content
  example_content="$(cat config.py.example)"

  # Build config.py header with credentials
  local config=""
  config+="# config.py — generated by setup.sh\n"
  config+="# Edit this file to change extensions, API keys, or proxy settings.\n\n"

  # Write out any credentials we collected
  if [[ ${#CREDENTIALS[@]} -gt 0 ]]; then
    for key in "${!CREDENTIALS[@]}"; do
      local val="${CREDENTIALS[$key]}"
      # Skip ZIP_CODE — it goes in the weather section below
      [[ "$key" == "ZIP_CODE" ]] && continue
      config+="$key = \"$val\"\n"
    done
    config+="\n"
  fi

  # ZIP_CODE
  if [[ -n "${CREDENTIALS[ZIP_CODE]+set}" ]]; then
    config+="ZIP_CODE = \"${CREDENTIALS[ZIP_CODE]}\"\n\n"
  fi

  # ENABLED_EXTENSIONS list
  config+="ENABLED_EXTENSIONS = [\n"
  for ext in "${SELECTED_EXTENSIONS[@]}"; do
    config+="\t\"$ext\",\n"
  done
  config+="]\n"

  # Append everything from config.py.example *after* the ENABLED_EXTENSIONS block
  # (keep WHITELISTED_DOMAINS, PRESET, SIMPLIFY_HTML, etc.)
  local after_block
  after_block="$(awk '/^WHITELISTED_DOMAINS/,0' config.py.example)"
  if [[ -n "$after_block" ]]; then
    config+="\n$after_block"
  fi

  printf "%b" "$config" > config.py
  print_ok "config.py written."
}

# ── Launch ────────────────────────────────────────────────────────────────────
launch_docker() {
  echo ""
  print_step "Launching MacProxy Plus with Docker..."
  echo -e "  ${DIM}(This may take a minute the first time — grabbing images & building)${RESET}"
  echo ""

  if ! $DOCKER_COMPOSE up -d --build; then
    echo ""
    print_err "Docker Compose failed. Check the output above for clues."
    echo ""
    echo -e "  Common fixes:"
    echo -e "    • Make sure Docker Desktop is running"
    echo -e "    • Try:  ${CYAN}$DOCKER_COMPOSE logs${RESET}"
    exit 1
  fi
}

# ── Success ───────────────────────────────────────────────────────────────────
print_success() {
  local host_ip
  host_ip="$(hostname -I 2>/dev/null | awk '{print $1}' || ipconfig getifaddr en0 2>/dev/null || echo "YOUR_HOST_IP")"

  echo ""
  echo -e "${GREEN}${BOLD}"
  echo "  ╔═══════════════════════════════════════════════════════╗"
  echo "  ║       MacProxy Plus is up and running!  🎉            ║"
  echo "  ╚═══════════════════════════════════════════════════════╝"
  echo -e "${RESET}"
  echo -e "  ${BOLD}Proxy address:${RESET}  ${CYAN}0.0.0.0:5001${RESET}  (port 5001 on this machine)"
  echo ""
  echo -e "  ${BOLD}On your vintage machine:${RESET}"
  echo -e "    Open your browser's Network/Proxy settings and enter:"
  echo ""
  echo -e "      ${YELLOW}HTTP Proxy:${RESET}  ${host_ip}"
  echo -e "      ${YELLOW}Port:${RESET}        5001"
  echo ""
  echo -e "  ${DIM}Both machines must be on the same local network.${RESET}"
  echo ""
  echo -e "  ${BOLD}Useful commands:${RESET}"
  echo -e "    ${CYAN}$DOCKER_COMPOSE logs -f${RESET}       — watch live logs"
  echo -e "    ${CYAN}$DOCKER_COMPOSE down${RESET}          — stop the proxy"
  echo -e "    ${CYAN}$DOCKER_COMPOSE up -d --build${RESET} — restart / rebuild"
  echo ""
  echo -e "  ${DIM}Happy surfing, retronaut! 🖥️${RESET}"
  echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
  clear
  banner

  check_docker
  ensure_in_repo

  echo ""
  echo -e "  ${DIM}Welcome to the MacProxy Plus setup wizard.${RESET}"
  echo -e "  ${DIM}We'll get you on the vintage superhighway in just a moment.${RESET}"
  echo ""

  # Copy config.py.example → config.py if not already there
  if [[ ! -f "config.py" ]]; then
    cp config.py.example config.py
    print_ok "Created config.py from config.py.example"
  else
    print_warn "config.py already exists — will overwrite with your selections."
  fi

  # Extension selection menu
  run_extension_menu

  if [[ ${#SELECTED_EXTENSIONS[@]} -eq 0 ]]; then
    print_warn "No extensions selected. Running with bare proxy only."
  else
    echo ""
    echo -e "  ${GREEN}${BOLD}Enabled extensions:${RESET} ${SELECTED_EXTENSIONS[*]}"
  fi

  # Collect API keys for extensions that need them
  collect_credentials

  # Write config.py
  write_config

  # Fire it up
  launch_docker

  # Party time
  print_success
}

main "$@"
