# Clawkie (克讲机)

**A desktop walkie-talkie that sits beside Claude Code.** Ask a cheap model a quick question with only the last few lines of your conversation attached, keep memos pinned to the conversation they belong to, and run an image-generation bench, then hand the result back to the main chat with one tap, without interrupting it.

[中文说明](README.zh-CN.md)

> **The author is looking for a job!** If you have an opportunity, reach out on [LinkedIn](https://www.linkedin.com/in/miaomiao-yang-331901383) · Xiaohongshu (RedNote) @羊猫猫不是猫 · [more](#contact)

![Three modes: Chat, Memo, Paint](docs/screenshots/modes.png)

Made by **Miaomiao** (GitHub [@Miaomiaomeowmeow](https://github.com/Miaomiaomeowmeow)) · License [CC BY-NC-SA 4.0](LICENSE) · Windows only · **The interface is in Chinese** (the knobs and buttons are explained below).

## Why

Halfway through a project you want to ask something small: a name for a feature, what a word means, a quick rewrite. Asking in the main conversation drags the whole context along (tokens) and interrupts the work. Clawkie is a second, cheaper line: it only carries the last few lines of the conversation you are in, and the main conversation never sees it unless you choose to hand something over.

## What you get

One walkie-talkie, three modes (the lever at the top left: **聊** Chat / **记** Memo / **画** Paint). The shell, the channel and the push-to-talk key are shared.

| Mode | On the screen | The input box |
|---|---|---|
| **聊 Chat** | A chat with a cheap model (Haiku by default). Under every answer: 放进输入框 *put it in the main chat's input box* · 直接发 *send it to the main chat now* · 新开对话做 *start a new conversation to do it* · 记一笔 *save as a memo* | Ask one question |
| **记 Memo** | A "contact log" screen: memos grouped by channel (conversation). Red light = not done; click it when done (struck through, OVER). Click a memo to jump to its conversation; ⇄ moves it to another conversation (including ones in your sidebar that are not open right now); ✎ edits; ✕ deletes (undo via right-click) | Write a memo (goes to the current channel by default; the black bar at the top shows where the next one goes) |
| **画 Paint** | One big prompt card (edit it in place), the current picture, reference images and every version as thumbnails. Buttons: ×N 张 *how many at once* · 用这张→存好 *keep this one, save it* · 再来一轮 *regenerate from the prompt* · 问模型 *ask the model to rewrite the prompt from your complaint* · 主对话看图 *ask the main conversation to look at the pictures* | Say what you don't like; Enter regenerates from the selected version |

- **Channels (CH01, CH02…)** are the Claude Code conversations that have the plugin loaded. The top-left knob or the backlit screen switches between them; the name shown is the one in your Claude sidebar.
- **Four knobs**: model · how many lines of the main conversation to attach (0 to 50) · max characters per line · preset ("常用": naming, explain a word, rewrite a sentence, or your own, see `talkie/presets/`). The model knob also sets how hard it thinks (快 / 一般 / 认真 / 很认真 / 最认真) and whether it may search the web (Bing, done by the plugin, max 4 lookups per answer).
- **Push to talk**: hold the mic button (or the side key) and speak. It uses Windows' built-in voice typing (Win+H); the text stays in the input box until you send it.
- **Six bodies** (the top-right knob): the Clawd body (ears are the antenna, eyes are the indicator lights, the right hand is the talk key) and five "real" radios with Clawd perched on top: cobalt pop, outdoor yellow, 80s silver, retro mint, Y2K candy purple. Drawn in code, so the window resizes crisply.

![Five bodies](docs/screenshots/bodies.png)

- **Hand-overs from Claude**: when the Claude in your main conversation wants a picture, it can call the plugin tool `mcp__clawkie__image` and hand the job to the Paint bench instead of generating it itself; it keeps working while you iterate. `mcp__clawkie__image_prompt` pushes a rewritten prompt onto the card. Keeping a finished picture leaves a small note that is attached the next time you talk in that conversation, so nothing interrupts it.
- Everything deletable is deletable in plain sight (chat lines, whole channels, memos, picture versions, requests, presets) and most of it can be undone from the right-click menu.

## How it works

Two halves that talk through a few small JSON files in `~/.claude/clawkie-bridge/`:

- **`clawkie/`** is a Claude Code plugin (mod). It heartbeats "I'm here" every 3 seconds, reads the last lines of its own conversation, asks the model with that conversation's own account (`$.model.complete`, no extra login or API key), writes the answer back, and can fill or submit the main chat's input box, start a new conversation, or register the two image tools.
- **`talkie/`** is a Python tkinter window. It never calls an AI itself; it writes questions into the bridge folder and the plugin answers. Image generation runs the local **Codex CLI** (`codex exec`), so it spends Codex quota, not Claude's.

| File in `~/.claude/clawkie-bridge/` | Written by | What it is |
|---|---|---|
| `live-<session>.json` | plugin, every 3 s | "I'm online", name, context size estimates |
| `ask-` / `answer-<session>.json` | window / plugin | question (with settings and the last 6 lines of the side chat) / answer |
| `tell-` / `told-<session>.json` | window / plugin | hand-over: fill the input box, send, start a new conversation, or leave a note |
| `img-req-*.json`, `img-upd-*.json` | plugin | an image job / a pushed prompt |
| `images/<id>/v1.png…` | window | every version |
| `talkie.json` | window | settings, position, chats, memos, picture records (your data lives here, not in the repo) |
| `notice.json`, `pet-pose.json`, `focus.json` | window / plugin | for the optional ClawdPet desk pet |

## Requirements

- Windows 10 / 11
- The **Claude desktop app** with Claude Code (plugins / mods enabled)
- **Python 3.10+** with **Pillow** (`pip install pillow`); tkinter ships with python.org builds
- Optional: **Codex CLI** installed under `%LOCALAPPDATA%\OpenAI\Codex\bin` for the Paint bench (without it the other two modes work and Paint says it cannot find Codex)
- Optional: [ClawdPet](https://github.com/Miaomiaomeowmeow/clawd-pet), a desk pet that holds a mini walkie-talkie: double-click it to open Clawkie, long-press to push-to-talk, and it reminds you of memos owed by the conversation you just clicked into

## Install

1. Download this repository (Code → Download ZIP) and unzip it somewhere you won't move.
2. Install the plugin: copy the `clawkie` folder to `%USERPROFILE%\.claude\skills\clawkie` (so that `...\skills\clawkie\hooks\register.tsx` exists). New conversations load it automatically (`claude plugin details clawkie` lists it as `clawkie@skills-dir`); conversations that were already open need to be reopened.
3. `pip install pillow`
4. Double-click `talkie\start.bat`. The walkie-talkie appears bottom-right; drag its body to move, drag the edges to resize, right-click for the menu, the power key hides it. Only one instance runs; starting it again just brings it forward.

**Don't want to do it yourself?** Give `AI-SETUP.md` to your AI assistant (Claude Code, Codex, Cursor…) and say "follow AI-SETUP.md and set up Clawkie for me". It checks Python, Pillow, the plugin folder and Codex, asks you one question at a time, and makes a desktop shortcut.

**Pairing with ClawdPet**: start Clawkie once (it leaves a card in `~/.clawd/talkie.json`), then in ClawdPet's right-click menu turn on 克讲机, or run `python pet.py link talkie on` in the pet's folder. Clawkie, in turn, borrows the pet's drawing so the Clawd on top wears whatever your pet wears.

## Presets ("常用")

One Markdown file in `talkie/presets/` = one preset on the knob. Line 1 is the name; the rest is the rule text added to the model's instructions. You can also create, edit and delete presets from inside the window (deleted ones go to `presets/deleted/`). A second line `来自：<file>｜<section>` pulls a marked section out of another file, so a rule your main conversation also reads is written only once. See `talkie/presets/README.md`.

## Known limits

- Interface language is Chinese only (English UI is on the wish list).
- Voice typing is as fast as Windows' own voice input.
- Image generation needs Codex CLI; there is no other image backend yet.
- On a phone (Claude's mobile app) the plugin pane only says to come back to the desktop.

## Files

```
clawkie/            the Claude Code plugin (hooks/register.tsx is the whole thing; tests/ has 12 automated tests)
talkie/
  clawkie_talkie.py the window: three modes, channels, memos, Paint bench, voice
  skin.py           the six bodies, drawn with Pillow
  presets/          "常用" presets
  start.bat         double-click to start
  clawkie.ico / clawkie-icon.png   the icon (made on the Paint bench itself)
docs/screenshots/   the pictures above (sample data)
AI-SETUP.md         install guide for your AI assistant
```

Test the plugin with `claude plugin validate clawkie` and `claude plugin test clawkie`.

## Contact

Miaomiao · GitHub [@Miaomiaomeowmeow](https://github.com/Miaomiaomeowmeow) · [LinkedIn](https://www.linkedin.com/in/miaomiao-yang-331901383) · Xiaohongshu (RedNote) @羊猫猫不是猫

If you build something on Clawkie, I'd love to hear about it.

Clawd is the Claude Code mascot; this is an unofficial fan project, not affiliated with Anthropic.
