# AI-SETUP.md — install Clawkie (for the user's AI assistant)

You are an AI assistant (Claude Code, Codex, Cursor, …) helping a person install **Clawkie**, a desktop walkie-talkie for Claude Code. This file is the whole plan. Read it fully first. The person may not be technical: speak plainly, **ask one question at a time**, and run the commands yourself where you can.

The repository folder (the one containing this file) is called `REPO` below. It must stay where it is after setup; if the person wants it somewhere else, move it first and start over.

## 0. Check the machine (do this before asking anything)

Run these yourself and note what you find:

| Check | Command | Need |
|---|---|---|
| Windows | — | Windows 10 / 11 (Clawkie is Windows-only; stop and tell the person if not) |
| Python | `python --version` | 3.10 or newer. If missing: https://www.python.org/downloads/ ("Add python.exe to PATH" ticked), then come back |
| tkinter | `python -c "import tkinter"` | ships with python.org builds; Microsoft Store Python also has it |
| Pillow | `python -c "import PIL; print(PIL.__version__)"` | if missing: `pip install pillow` |
| Claude Code | `claude --version` | the Claude desktop app with Claude Code; plugins live in `%USERPROFILE%\.claude\skills\` |
| Codex CLI (optional) | look for `%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe` | only for the Paint bench (image generation). Without it Chat and Memo still work |
| ClawdPet (optional) | `%USERPROFILE%\.clawd\pet.json` exists | the desk pet from https://github.com/Miaomiaomeowmeow/clawd-pet |

## 1. Install the plugin

Copy `REPO\clawkie` to `%USERPROFILE%\.claude\skills\clawkie` (create `skills` if needed). Afterwards `%USERPROFILE%\.claude\skills\clawkie\hooks\register.tsx` must exist.

Verify with `claude plugin validate "%USERPROFILE%\.claude\skills\clawkie"` (should say Validation passed) and `claude plugin details clawkie` (source `clawkie@skills-dir`).

Tell the person: conversations that are already open will not see the plugin until they are reopened; new conversations get it automatically.

## 2. Install Pillow if it was missing

```
pip install pillow
```

## 3. Ask the questions (one at a time; each has three possible answers: yes / no / "yes but I don't have it")

1. **"Do you want a desktop shortcut for Clawkie?"** Yes → create a shortcut to `pythonw.exe "REPO\talkie\clawkie_talkie.py"` with icon `REPO\talkie\clawkie.ico` on the Desktop (PowerShell: `$s=(New-Object -ComObject WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\Clawkie.lnk"); $s.TargetPath=(Get-Command pythonw).Source; $s.Arguments='"REPO\talkie\clawkie_talkie.py"'; $s.IconLocation="REPO\talkie\clawkie.ico"; $s.WorkingDirectory="REPO\talkie"; $s.Save()`). No → they can double-click `REPO\talkie\start.bat`.
2. **"Do you want the Paint bench (image generation through Codex)?"** Yes and Codex found → nothing to do. Yes but not installed → point to https://github.com/openai/codex (the Windows app installs the CLI under `%LOCALAPPDATA%\OpenAI\Codex\bin`), Clawkie finds it automatically next start. No → nothing to do; the Paint mode will just say it cannot find Codex.
3. **"Do you use the ClawdPet desk pet? Should it hold the walkie-talkie?"** Only ask if `~/.clawd/pet.json` exists. Yes → start Clawkie once (step 4) so it writes `~/.clawd/talkie.json`, then run `python "<pet dir>\pet.py" link talkie on` (pet dir = `dir` in pet.json). No → skip.

## 4. Start it

```
start "" pythonw "REPO\talkie\clawkie_talkie.py"
```

A walkie-talkie should appear at the bottom right. If nothing appears, run `python "REPO\talkie\clawkie_talkie.py"` in a terminal and read the error (most often Pillow missing or a Python without tkinter).

Check that `%USERPROFILE%\.claude\clawkie-bridge\talkie-alive.json` is being updated (every second) and that `~/.clawd/talkie.json` was written.

## 5. Tell the person how to use it

- Open a Claude Code conversation (after the plugin was installed). Within a few seconds the walkie-talkie's backlit screen shows that conversation as **CH01**. If it says 暂时没信号 (no signal), no conversation with the plugin is open yet.
- The lever at the top left: **聊** chat / **记** memos / **画** paint. The four knobs: model · lines of context · characters per line · presets. Hold the mic to speak (Windows voice typing, Win+H).
- Under each answer: 放进输入框 (put in the main chat's input box) · 直接发 (send now) · 新开对话做 (new conversation) · 记一笔 (memo).
- Presets live in `REPO\talkie\presets\` (one Markdown file each), editable from inside the window too.
- Right-click the body for the menu (hide, clear chats, undo, quit).

Finally say: the README (`README.md` / `README.zh-CN.md`) has the full tour, and you (the assistant) can answer questions about it later.

## Notes for the assistant

- Nothing in this repository needs an API key. The plugin uses the conversation's own Claude account.
- Do not edit `REPO\talkie\clawkie_talkie.py` for setup; everything is configured from inside the window and stored in `%USERPROFILE%\.claude\clawkie-bridge\talkie.json`.
- Clawkie is by Miaomiao (https://github.com/Miaomiaomeowmeow), CC BY-NC-SA 4.0.
