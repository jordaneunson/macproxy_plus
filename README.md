# MacProxy Plus

An extensible HTTP proxy that connects early computers to the Internet.

### Watch it in action

<a href="https://youtu.be/f1v1gWLHcOk" target="_blank">
  <img src="./readme_images/youtube_thumbnail.jpg" alt="Teaching an Old Mac New Tricks" width="400">
</a>

MacProxy Plus lets vintage browsers surf the modern web by sitting between your old machine and the Internet. It strips out incompatible HTML/CSS, converts images to formats your retro hardware can actually display, and provides purpose-built extensions for popular sites — so your 1991 Mac can browse Reddit, chat with an AI, or check the weather.

> **This is a fork of [hunterirving/macproxy_plus](https://github.com/hunterirving/macproxy_plus)** — a fantastic project by Hunter Irving. All the clever bits originated there. This fork adds Docker-based setup and a few extra extensions.

---

## Getting Started

You need exactly two things: **Docker Desktop** and a terminal.

### 1. Install Docker Desktop

→ [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

### 2. Run the setup script

**One-liner (recommended):**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/jordaneunson/macproxy_plus/master/setup.sh)"
```

**Or clone first, then run:**
```bash
git clone https://github.com/jordaneunson/macproxy_plus
cd macproxy_plus
./setup.sh
```

### 3. That's it!

The script will walk you through picking your extensions, ask for any API keys you need, and launch the proxy automatically. No Python, no pip, no virtualenvs — Docker handles everything.

---

## Connecting Your Vintage Machine

Once MacProxy Plus is running, point your vintage browser at it:

| Setting | Value |
|---|---|
| **HTTP Proxy** | IP address of the computer running MacProxy Plus |
| **Port** | `5001` |

Both machines need to be on the same local network. Find your host machine's local IP with `ipconfig getifaddr en0` (macOS) or `hostname -I` (Linux).

> **Using a 4MB 68k Mac (Plus, Classic, SE, etc.)?** You'll want [MacWeb 2.0c+](https://github.com/hunterirving/macweb-2.0c-plus) by Hunter Irving — it's a lightweight browser built specifically for these machines and works great with MacProxy Plus.

<p align="center">
  <img src="readme_images/proxy_settings.gif" alt="Configuring proxy settings in MacWeb 2.0c+" width="400"><br>
  <em>Example: Configuring proxy settings in <a href="https://github.com/hunterirving/macweb-2.0c-plus">MacWeb 2.0c+</a></em>
</p>

---

## Available Extensions

The setup script lets you pick and choose which extensions to enable. Here's what's available:

| Extension | Description |
|---|---|
| **chatgpt** | Chat with OpenAI's GPT models *(requires OpenAI API key)* |
| **claude** | Anthropic's Claude AI assistant *(requires Anthropic API key)* |
| **gemini** | Google's Gemini AI assistant *(requires Gemini API key)* |
| **hackaday** | Pared-down, text-only Hackaday — articles, comments, and search |
| **hacksburg** | Local hackerspace portal |
| **hunterirving** | Personal page extension |
| **jordaneunson** | Personal page extension |
| **kagi** | Privacy-respecting search *(requires Kagi session token)* |
| **kimi** | Moonshot AI assistant *(requires Kimi API key)* |
| **mistral** | Mistral AI chat *(requires Mistral API key)* |
| **notyoutube** | A legally distinct parody of YouTube — encodes video via [MacFlim](https://www.macflim.com/macflim2/) |
| **npr** | Text-only NPR news articles |
| **reddit** | Browse subreddits with dithered black-and-white images |
| **waybackmachine** | Browse the web as it existed on any date back to 1996 |
| **weather** | US weather forecast by ZIP code |
| **websimulator** | AI-generated imagined websites for URLs that don't exist *(requires Anthropic API key)* |
| **wiby** | Handcrafted personal webpage search engine |
| **wikipedia** | Browse 6M+ encyclopedia articles with clickable links and search |

---

## Advanced Usage

For manual configuration, development setup, Docker-free installation, Windows instructions, preset support, and more — see **[ORIGINAL_README.md](./ORIGINAL_README.md)**.

---

*Happy Surfing 😎*
