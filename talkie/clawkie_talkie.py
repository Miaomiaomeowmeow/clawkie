# 克讲机 Clawkie · Clawkie-talkie — made by Miaomiao (https://github.com/Miaomiaomeowmeow) · CC BY-NC-SA 4.0
# 对讲机 → 克讲机：桌面上一台能拖、能拉大小的对讲机（小克机，或者小克趴在上面的 5 种机身）。
# 三个档位（机身左上角的拨杆）：聊 = 和便宜模型唠嗑；记 = 备忘录；画 = 生图台。
# 它自己不调 AI：问题写进 ~/.claude/clawkie-bridge/ 里的小文件，Claude 应用里装了「克讲机 Clawkie」插件的对话
# 看到后用自己的账号问小模型，再把答案写回来。生图用电脑上的 Codex（没装就只是画档用不了）。
#
# 打开：双击同目录的 start.bat；装了 ClawdPet 桌宠的话双击桌宠小克（长按小克 = 按住说话）。只开一个。
# 机身画法在 skin.py；常用功能在 presets 文件夹（写法见那里的 README.md）。
#
# 机身上能点的：
#   拨杆 = 聊 / 记 / 画          顶上左旋钮或背光屏 = 换频道（听哪个对话）   顶上右旋钮 = 换机身   电源键 = 收起
#   四个旋钮 = 模型 / 带几句 / 每句几字 / 常用    麦克风、侧面通话键（小克机是右手）= 按住说话（Windows 自带的语音输入）
#   大红键、回车 = 发送 / 记下 / 再生    拖机身空白处 = 挪位置；拖四条边、四个角 = 改大小；右键 = 菜单

import argparse
import ctypes
import glob
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

from PIL import Image, ImageTk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # 用 python -I 开时也找得到旁边的 skin.py
import skin  # noqa: E402

VERSION = "1.0"
PRESETS = os.path.join(HERE, "presets")
BRIDGE = os.path.join(os.path.expanduser("~"), ".claude", "clawkie-bridge")
STATE = os.path.join(BRIDGE, "talkie.json")
ALIVE = os.path.join(BRIDGE, "talkie-alive.json")
SHOW = os.path.join(BRIDGE, "talkie-show.json")
NOTICE = os.path.join(BRIDGE, "notice.json")   # 给桌宠：头顶冒个泡
POSE = os.path.join(BRIDGE, "pet-pose.json")    # 给桌宠：现在在干嘛（它手里的迷你对讲机跟着摆动作）
IMAGES = os.path.join(BRIDGE, "images")
# 名片：各个小克程序在用户文件夹 ~/.clawd/ 里留一张，写着自己装在哪，别的程序就能找到它，不用填路径
# （测试时可以用环境变量 CLAWD_CARDS 换个文件夹；ClawdPet 桌宠那边也认这个变量）
CARDS = os.environ.get("CLAWD_CARDS") or os.path.join(os.path.expanduser("~"), ".clawd")
PET_CARD = os.path.join(CARDS, "pet.json")        # 桌宠 ClawdPet 写：{"dir": 它装在哪}
TALKIE_CARD = os.path.join(CARDS, "talkie.json")  # 克讲机自己写：{"path": clawkie_talkie.py 在哪}，桌宠读到就会出现「克讲机」联动
CODEX_BIN = os.path.join(os.environ.get("LOCALAPPDATA", ""), "OpenAI", "Codex", "bin")
CODEX_OUT = os.path.join(os.path.expanduser("~"), ".codex", "generated_images")

KEY = "#ff00fe"
FONT = "Microsoft YaHei UI"
MONO = "Consolas"

MODELS = [("haiku", "Haiku 5.5"), ("sonnet", "Sonnet 5.5"), ("opus", "Opus 5.5"), ("claude-fable-5-1", "Fable 5.1")]
# 和插件里的 COUNT_STEPS / CHAR_STEPS 一样，改了两边一起改
COUNTS = [0, 2, 4, 6, 10, 15, 20, 30, 50]
CHARS = [200, 500, 800, 1500, 3000, 0]
HISTORY = 6
KEEP = 60
LIVE_S = 30      # 插件重新加载时会断十几秒，30 秒内不算关
WAIT_S = 900     # 想得认真 + 上网查，最多等 15 分钟
# 想得多认真（插件把它交给模型的 effort）。用户 2026-10-15：“非常笨……可不可以增加努力程度”
EFFORTS = [("low", "快"), ("medium", "一般"), ("high", "认真"), ("xhigh", "很认真"), ("max", "最认真")]
GEN_S = 420      # 生一张图最多等 7 分钟
SYSTEM_EST = 320
MIN_W, MIN_H = 360, 560
SEND_LABEL = ["发送", "记下", "再生"]


def read_json(path, fallback):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return fallback


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def estimate(text):
    """粗估 token：中文大约一个字一个，英文大约 3.5 个字母一个（和插件里一样）"""
    cjk = sum(1 for ch in text if "\u2e80" <= ch <= "\u9fff" or "\uac00" <= ch <= "\ud7af" or "\uff00" <= ch <= "\uffef" or "\u3000" <= ch <= "\u303f")
    return int(cjk * 1.1 + (len(text) - cjk) / 3.5 + 0.999)


def fmt(n):
    return str(n) if n < 1000 else f"{n / 1000:.1f}k"


def short(text, n):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def hexc(c):
    return "#%02x%02x%02x" % tuple(c)


def new_id():
    return f"{int(time.time() * 1000)}-{random.randint(1000, 9999)}"


# Claude 应用把每个对话在侧边栏里的名字存在这里（应用是商店装的，外面的程序要走 Packages 那条路）
APP_SESSIONS = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages", "Claude_pzs8sxrjxfjjc", "LocalCache", "Roaming", "Claude", "claude-code-sessions"),
    os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude-code-sessions"),
]
_titles = {"at": 0, "map": {}}


def app_titles():
    """对话编号 → 侧边栏里的名字（用户改了名就跟着变），10 秒读一次"""
    if time.time() - _titles["at"] < 10:
        return _titles["map"]
    m, recent = {}, []
    for root in APP_SESSIONS:
        for f in glob.glob(os.path.join(root, "*", "*", "local_*.json")):
            d = read_json(f, None)
            if isinstance(d, dict) and d.get("title"):
                for cid in [d.get("cliSessionId")] + list(d.get("priorCliSessionIds") or []):
                    if cid:
                        m[cid] = d["title"]
                if d.get("cliSessionId") and not d.get("isArchived"):
                    recent.append({"sid": d["cliSessionId"], "label": d["title"], "at": d.get("lastActivityAt") or 0,
                                   "local": d.get("sessionId", ""), "cwd": d.get("cwd", "")})
        if m:
            break
    recent.sort(key=lambda d: d["at"], reverse=True)
    _titles.update(at=time.time(), map=m, recent=recent)
    return m


def recent_convs(n=12):
    """侧边栏里最近用过的对话（没归档的），记备忘时可以挂到没开着对讲机的对话下面"""
    app_titles()
    return _titles.get("recent", [])[:n]


def sidebar_groups():
    """跟侧边栏一样分组（用户 2026-10-15：“我的对话是有分组的……按环境文件夹分”）：
    置顶 → 自己建的组（如「小克外挂箱」）→ 按环境（预设名，找不到用文件夹名）。返回 [(组名, [对话…])]"""
    convs = recent_convs(500)
    prefs, presets = {}, {}
    for root in APP_SESSIONS:
        base = os.path.dirname(root)
        cfg = read_json(os.path.join(base, "claude_desktop_config.json"), None)
        if isinstance(cfg, dict):
            prefs = (cfg.get("preferences") or {}).get("epitaxyPrefs") or {}
            for acc in ((read_json(os.path.join(base, "ccd-session-presets.json"), {}) or {}).get("byAccount") or {}).values():
                for p in acc.get("presets") or []:
                    cwd = ((p.get("target") or {}).get("cwd") or "").rstrip("\\/").lower()
                    if cwd and p.get("name"):
                        presets[cwd] = p["name"]
            break
    starred = {str(s).replace("code:", "") for s in (prefs.get("starred-local-code-sessions") or [])}
    gname, assign = {}, {}
    for scope in (prefs.get("dframe-group-scopes") or {}).values():
        for g in scope.get("groups") or []:
            gname[g.get("id")] = g.get("name") or "未命名的组"
        for k, gid in (scope.get("assignments") or {}).items():
            assign[k.replace("code:", "")] = gid
    groups, order = {}, []

    def put(name, c):
        if name not in groups:
            groups[name] = []
            order.append(name)
        groups[name].append(c)
    for c in convs:  # 已经按最近用过排好
        if c.get("local") in starred:
            put("★ 置顶", c)
        elif assign.get(c.get("local")) in gname:
            put("▣ " + gname[assign[c.get("local")]], c)
        else:
            cwd = (c.get("cwd") or "").rstrip("\\/")
            put("◇ " + (presets.get(cwd.lower()) or os.path.basename(cwd) or "没选文件夹"), c)
    rank = lambda n: 0 if n.startswith("★") else 1 if n.startswith("▣") else 2
    order.sort(key=rank)  # 稳定排序：同一类里还是最近用过的在前
    return [(n, groups[n]) for n in order]


def live_sessions():
    out = []
    now = time.time() * 1000
    try:
        names = os.listdir(BRIDGE)
    except OSError:
        return out
    titles = app_titles()
    for name in names:
        if name.startswith("live-") and name.endswith(".json"):
            d = read_json(os.path.join(BRIDGE, name), None)
            if isinstance(d, dict) and not d.get("ended") and now - (d.get("at") or 0) < LIVE_S * 1000:
                if titles.get(d.get("sid")):
                    d["label"] = titles[d["sid"]]  # 侧边栏里的名字优先，找不到才用「文件夹 · 第一句话」
                out.append(d)
    out.sort(key=lambda d: d.get("active") or 0, reverse=True)
    return out


def load_presets():
    """常用功能：presets 文件夹里一个 .md 一个（README.md 除外）"""
    out = []
    try:
        names = sorted(n for n in os.listdir(PRESETS) if n.endswith(".md") and n.lower() != "readme.md")
    except OSError:
        return out
    for n in names:
        try:
            text = open(os.path.join(PRESETS, n), encoding="utf-8").read()
        except OSError:
            continue
        lines = text.splitlines()
        name = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("#") else os.path.splitext(n)[0]
        rules = []
        for ln in lines[1:]:
            m = re.match(r"\s*来自[:：]\s*(.+?)[｜|](.+)$", ln)
            rules.append(read_section(m.group(1).strip(), m.group(2).strip()) if m else ln)
        out.append({"name": name, "file": n, "rules": "\n".join(rules).strip()})
    return out


def read_section(path, mark):
    try:
        src = open(path, encoding="utf-8").read()
    except OSError:
        return f"（读不到 {path}）"
    a, b = f"<!-- 克讲机:{mark} 开始 -->", f"<!-- 克讲机:{mark} 结束 -->"
    if a in src and b in src:
        return src.split(a, 1)[1].split(b, 1)[0].strip()
    return f"（{path} 里没找到「{mark}」那段的标记）"


def pet_dir():
    """桌宠 ClawdPet 装在哪：看它留的名片；没装就是空字符串"""
    d = (read_json(PET_CARD, {}) or {}).get("dir") or ""
    return d if d and os.path.exists(os.path.join(d, "clawd_pet.py")) else ""


def write_card():
    """留一张名片，桌宠（和别的程序）靠它找到克讲机"""
    try:
        write_json(TALKIE_CARD, {"app": "clawkie", "version": VERSION, "path": os.path.abspath(__file__), "dir": HERE,
                                 "bridge": BRIDGE, "at": int(time.time())})
    except OSError:
        pass


def load_clawd():
    """借桌宠的画小克函数（桌宠换衣服这里也跟着换）；没装桌宠就用一只最简单的"""
    try:
        spec = importlib.util.spec_from_file_location("clawd_pet", os.path.join(pet_dir(), "clawd_pet.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m.clawd
    except Exception:
        def simple(look, st, parts):
            c = (look or {}).get("color", "#d97757")
            return [("r", 0, 2, 22, 12, c), ("r", 5, 6, 2, 3, "#151513"), ("r", 15, 6, 2, 3, "#151513"),
                    ("r", 2, 14, 2, 4, c), ("r", 7, 14, 2, 4, c), ("r", 13, 14, 2, 4, c), ("r", 18, 14, 2, 4, c)]
        return simple


def find_codex():
    exes = glob.glob(os.path.join(CODEX_BIN, "*", "codex.exe"))
    return max(exes, key=os.path.getmtime) if exes else None


def press_win_h():
    """Windows 自带的语音输入：Win+H 开 / 关"""
    k = ctypes.windll.user32.keybd_event
    k(0x5B, 0, 0, 0)
    k(0x48, 0, 0, 0)
    k(0x48, 0, 2, 0)
    k(0x5B, 0, 2, 0)


class Talkie:
    def __init__(self, near, talk=False):
        self.state = {"model": "haiku", "customModel": "", "effort": "high", "web": True, "ctxCount": 6, "perChars": 800, "theme": "clawd", "preset": "",
                      "x": None, "y": None, "w": None, "h": None, "sid": "", "chats": {}, "mode": 0, "knobs": True,
                      "memos": [], "imgs": {}, "imgCur": "", **read_json(STATE, {})}
        if self.state.get("v") != 3:  # 新机身尺寸不一样：用一次默认大小，默认换成小克机
            self.state.update(v=3, w=None, h=None, theme="clawd")
        self.sessions, self.presets = [], load_presets()
        self.waiting = None      # 聊：(问题编号, 对话, 开始时间)
        self.telling = None      # (编号, 对话, 开始时间)
        self.img_ask = None      # 画档里问小模型：(编号, 对话, 开始时间, 请求)
        self.gen = None          # 正在生的一轮：{rid, t0, left 还差几张}
        self.gen_results = []    # 生图线程放结果的地方（主线程来取）
        self.claimed = set()     # 已经认领过的 Codex 图（几张同时生时别拿错）
        self.flash_msg, self.flash_until = "", 0
        self.mood, self.mood_until = "busy", 0
        self.dictating, self.talk_t0 = False, 0
        self.drag = None
        self.render_job = None
        self.deleted = None
        self.clawd = load_clawd()
        self.photos = []

        self.root = tk.Tk()
        self.root.title("克讲机")
        try:  # 图标：克讲机生图台自己生的第一张定稿（2026-10-15）
            self.root.iconbitmap(default=os.path.join(HERE, "clawkie.ico"))
        except tk.TclError:
            pass
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.config(bg=KEY)
        self.root.wm_attributes("-transparentcolor", KEY)
        self.k = self.root.winfo_fpixels("1i") / 96
        self.f = tkfont.Font(family=FONT, size=10)
        self.fb = tkfont.Font(family=FONT, size=10, weight="bold")
        self.fs = tkfont.Font(family=FONT, size=8)
        self.fsb = tkfont.Font(family=FONT, size=8, weight="bold")
        self.fl = tkfont.Font(family=MONO, size=14, weight="bold")
        self.fm = tkfont.Font(family=FONT, size=9, weight="bold")
        self.flog = tkfont.Font(family=MONO, size=10)
        self.flog_b = tkfont.Font(family=MONO, size=10, weight="bold")

        self.cv = tk.Canvas(self.root, bg=KEY, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        # 三个档位各自的屏幕内容
        self.chat = tk.Text(self.root, wrap="word", font=self.f, relief="flat", bd=0, padx=8, pady=6,
                            spacing1=2, spacing3=3, cursor="arrow", highlightthickness=0)
        self.memo = tk.Text(self.root, wrap="word", font=self.f, relief="flat", bd=0, padx=6, pady=6,
                            spacing1=3, spacing3=5, cursor="arrow", highlightthickness=0)
        self.imgf = tk.Frame(self.root, bd=0, highlightthickness=0)
        self.build_img_view()
        self.entry = tk.Entry(self.root, font=self.f, relief="flat", bd=0, highlightthickness=0)
        self.entry.bind("<Return>", lambda e: self.send())
        self.entry.bind("<KeyRelease>", lambda e: self.draw_overlay())
        self.cv.bind("<Motion>", self.on_motion)
        self.cv.bind("<ButtonPress-1>", self.on_press)
        self.cv.bind("<B1-Motion>", self.on_drag)
        self.cv.bind("<ButtonRelease-1>", self.on_release)
        self.cv.bind("<Button-3>", self.menu_main)
        for w in (self.chat, self.memo):
            w.bind("<Button-3>", self.menu_main)

        self.place(near)
        self.refresh_sessions()
        self.scan_img_reqs()
        self.render()
        self.refresh_screen()
        self.root.after(400, self.poll_answer)
        self.root.after(1000, self.beat)
        self.root.after(2000, self.poll_sessions)
        self.root.after(500, self.poll_show)
        self.show_mtime = self._mtime(SHOW)
        self.root.after(200, self.entry.focus_force)
        if talk:
            self.root.after(500, self.talk_start)

    # ================= 画机身 =================
    @property
    def T(self):
        t = dict(skin.THEMES.get(self.state["theme"], skin.THEMES["clawd"]))
        if self.state["theme"] == "clawd":
            t["face"] = self.clawd_color()
        return t

    def pet_status(self):
        d = pet_dir()
        return read_json(os.path.join(d, "status.json"), {}) if d else {}

    def clawd_color(self):
        return (self.pet_status().get("look") or {}).get("color") or "#d97757"

    def knob_angles(self):
        s = self.state

        def ang(i, n):
            return -120 + 240 * i / max(1, n - 1)
        mi = next((i for i, (v, _) in enumerate(MODELS) if v == s["model"]), len(MODELS))
        ci = COUNTS.index(s["ctxCount"]) if s["ctxCount"] in COUNTS else 0
        hi = CHARS.index(s["perChars"]) if s["perChars"] in CHARS else 0
        names = [""] + [p["name"] for p in self.presets]
        pi = names.index(s["preset"]) if s["preset"] in names else 0
        return (ang(mi, len(MODELS) + 1), ang(ci, len(COUNTS)), ang(hi, len(CHARS)), ang(pi, len(names)))

    def clawd_cells(self):
        st = self.pet_status()
        look = dict(st.get("look") or {})
        look["hold"] = "none"
        mood = self.mood if time.time() < self.mood_until else "busy"
        try:
            return list(self.clawd(look, mood, st.get("parts") or []))
        except Exception:
            return []

    def busy(self):
        return bool(self.waiting or self.gen or self.img_ask or self.dictating)

    def render(self):
        self.render_job = None
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if w < 50:
            w, h = int(self.state["w"] or 440 * self.k), int(self.state["h"] or 700 * self.k)
        w, h = max(w, int(MIN_W * self.k)), max(h, int(MIN_H * self.k))
        img, self.L = skin.render(w, h, self.k, self.state["theme"], self.clawd_cells(), self.knob_angles(),
                                  mode=self.state["mode"], knobs=self.state["knobs"], clawd_color=self.clawd_color(), busy=self.busy())
        self.photo = ImageTk.PhotoImage(img)
        self.cv.delete("all")
        self.cv.create_image(0, 0, image=self.photo, anchor="nw")
        T = self.T
        x0, y0, x1, y1 = self.L["screen"]
        for wdg in (self.chat, self.memo):
            wdg.config(bg=T["screen"], fg=T["ink"], insertbackground=T["ink"], selectbackground=T["lcd"])
        view = [self.chat, self.memo, self.imgf][self.state["mode"]]
        self.cv.create_window(x0, y0, window=view, anchor="nw", width=x1 - x0, height=y1 - y0)
        self.screen_size = (int(x1 - x0), int(y1 - y0))
        x0, y0, x1, y1 = self.L["input"]
        self.entry.config(bg=T["screen"], fg=T["ink"], insertbackground=T["ink"])
        self.cv.create_window(x0, y0, window=self.entry, anchor="nw", width=x1 - x0, height=y1 - y0)
        self.style_views()
        self.draw_overlay()

    def schedule_render(self, delay=60):
        if self.render_job:
            self.root.after_cancel(self.render_job)
        self.render_job = self.root.after(delay, self.render)

    def draw_overlay(self):
        """机身上会变的字：背光屏、旋钮旁的字、发送键、麦克风亮灯"""
        cv, T, s = self.cv, self.T, self.state
        cv.delete("ov")
        x0, y0, x1, y1 = self.L["lcd"]
        idx = next((i for i, d in enumerate(self.sessions) if d["sid"] == s["sid"]), -1)
        mode = s["mode"]
        if mode == 2:
            ch = "IMG"
        else:
            ch = f"CH{idx + 1:02d}" if idx >= 0 else "CH--"
        cv.create_text(x0 + 6 * self.k, (y0 + y1) / 2, text=ch, font=self.fl, fill=T["lcd_ink"], anchor="w", tags="ov")
        tx = x0 + 6 * self.k + self.fl.measure("CH00") + 10 * self.k
        room = max(4, int((x1 - tx) / self.fs.measure("字")) - 1)
        line1, line2 = self.lcd_lines()
        if time.time() < self.flash_until:
            line2 = self.flash_msg
        if self.dictating:
            line2 = "● 在听你说……（松手 / 再点一下停）"
        cv.create_text(tx, y0 + (y1 - y0) * 0.3, text=short(line1, room), font=self.fsb, fill=T["lcd_ink"], anchor="w", tags="ov")
        cv.create_text(tx, y0 + (y1 - y0) * 0.74, text=short(line2, room), font=self.fs, fill=T["lcd_ink"], anchor="w", tags="ov")

        if s["knobs"]:
            labels = [(f"模型·{dict(EFFORTS).get(s.get('effort'), '认真')}", self.model_label()),
                      ("带几句", "不带" if s["ctxCount"] == 0 else f"{s['ctxCount']} 句"),
                      ("每句", "不截" if s["perChars"] == 0 else f"{s['perChars']} 字"),
                      ("常用", s["preset"] or "随便聊")]
            for i, (a, b) in enumerate(labels):
                cx, cy = self.L[f"knob{i}_label"]
                cv.create_text(cx, cy - 1, text=a, font=self.fs, fill=T["label"], anchor="sw", tags="ov")
                cv.create_text(cx, cy + 1, text=short(b, 9), font=self.fsb, fill=T["label"], anchor="nw", tags="ov")
        px0, py0, px1, py1 = self.L["ptt"]
        cv.create_text((px0 + px1) / 2, (py0 + py1) / 2, text=SEND_LABEL[mode], font=self.fm, fill="#ffffff", tags="ov")
        if self.dictating:
            mx0, my0, mx1, my1 = self.L["mic"]
            cv.create_oval(mx0 - 3, my0 - 3, mx1 + 3, my1 + 3, outline="#ff3b2f", width=max(2, int(2.5 * self.k)), tags="ov")

    def lcd_lines(self):
        s, cur = self.state, self.current()
        if s["mode"] == 1:
            linked = sum(1 for m in s["memos"] if m.get("link"))
            todo = sum(1 for m in s["memos"] if not m.get("done"))
            return f"备忘 {todo} 条没做 · {linked} 条连着对话", (cur.get("label") if cur else "点一条备忘 → 跳到它的对话")
        if s["mode"] == 2:
            r = s["imgs"].get(s["imgCur"])
            if not r:
                n = len(s["imgs"])
                return ("生图台", f"{n} 个请求 · 右键可以新建一张" if n else "主对话要图时会交到这里")
            vs = [v for v in r["versions"] if not v.get("gone")]
            st = "在生……" if self.gen and self.gen["rid"] == r["id"] else ("等你挑" if vs else "排队中")
            if r.get("fresh"):
                st = "换了新提示词，还没生"
            return short(r.get("title") or r["prompt"], 30), f"第 {len(vs)} 版 · {st} · 送回 {short(r.get('label') or '?', 12)}"
        if cur:
            total, _ = self.estimate()
            preset = f"  ◆{s['preset']}" if s["preset"] else ""
            line2 = f"≈{fmt(total)} token{preset}"
            if self.waiting and self.waiting[1] == s["sid"]:
                line2 = "收到，在想" + "·" * (int(time.time() * 2) % 3 + 1)
            return cur.get("label", "?"), line2
        return "没有开着的对话", "打开 Claude 里装了克讲机插件的对话"

    # ================= 点到哪了 =================
    def hit(self, x, y):
        def inside(b):
            return b[0] <= x <= b[2] and b[1] <= y <= b[3]
        for name in ("power", "chan", "skin", "lcd", "ptt", "side", "mic", "mode0", "mode1", "mode2"):
            if name in self.L and inside(self.L[name]):
                return name
        for i, b in enumerate(self.L["knobs"]):
            if inside(b):
                return f"knob{i}"
        return None

    def edge(self, x, y):
        bx0, by0, bx1, by1 = self.L["body"]
        m = 10 * self.k
        if not (bx0 - m <= x <= bx1 + m and by0 - m <= y <= by1 + m):
            return ""
        e = ""
        if y <= by0 + m:
            e += "t"
        elif y >= by1 - m:
            e += "b"
        if x <= bx0 + m:
            e += "l"
        elif x >= bx1 - m:
            e += "r"
        return e

    CURSORS = {"t": "sb_v_double_arrow", "b": "sb_v_double_arrow", "l": "sb_h_double_arrow", "r": "sb_h_double_arrow",
               "tl": "size_nw_se", "br": "size_nw_se", "tr": "size_ne_sw", "bl": "size_ne_sw"}

    def on_motion(self, e):
        if self.drag:
            return
        what = self.hit(e.x, e.y)
        ed = "" if what in ("side",) else self.edge(e.x, e.y)
        if what:
            self.cv.config(cursor="hand2")
        elif ed:
            self.cv.config(cursor=self.CURSORS.get(ed, "fleur"))
        else:
            self.cv.config(cursor="fleur")

    def on_press(self, e):
        r = self.root
        what = self.hit(e.x, e.y)
        if what in ("mic", "side"):
            self.drag = ("talk", what)
            self.talk_press()
            return
        if what:
            self.drag = ("click", what, e)
            return
        ed = self.edge(e.x, e.y)
        if ed:
            self.drag = ("size", ed, e.x_root, e.y_root, r.winfo_x(), r.winfo_y(), r.winfo_width(), r.winfo_height())
            return
        self.drag = ("move", e.x_root, e.y_root, r.winfo_x(), r.winfo_y())

    def on_drag(self, e):
        if not self.drag:
            return
        if self.drag[0] == "move":
            _, sx, sy, wx, wy = self.drag
            self.root.geometry(f"+{wx + e.x_root - sx}+{wy + e.y_root - sy}")
        elif self.drag[0] == "size":
            _, ed, sx, sy, wx, wy, ww, wh = self.drag
            dx, dy = e.x_root - sx, e.y_root - sy
            mw, mh = int(MIN_W * self.k), int(MIN_H * self.k)
            x, y, w, h = wx, wy, ww, wh
            if "r" in ed:
                w = max(mw, ww + dx)
            if "l" in ed:
                w = max(mw, ww - dx)
                x = wx + ww - w
            if "b" in ed:
                h = max(mh, wh + dy)
            if "t" in ed:
                h = max(mh, wh - dy)
                y = wy + wh - h
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self.schedule_render()

    def on_release(self, e):
        d, self.drag = self.drag, None
        if not d:
            return
        if d[0] == "talk":
            self.talk_release()
        elif d[0] == "click":
            self.press(d[1], d[2])
        else:
            if d[0] == "size":
                self.render()
                self.refresh_screen()
            self.save()

    def press(self, what, e):
        if what in ("chan", "lcd"):
            self.menu_sessions(e)
        elif what == "skin":
            self.popup(e, [(skin.THEMES[t]["name"], lambda t=t: self.set(theme=t), self.state["theme"] == t) for t in skin.ORDER])
        elif what == "power":
            self.hide()
        elif what == "ptt":
            self.send()
        elif what.startswith("mode"):
            self.set_mode(int(what[-1]))
        elif what.startswith("knob"):
            self.knob_menu(int(what[-1]), e)

    def knob_menu(self, i, e):
        s = self.state
        if i == 0:
            items = [(label, lambda v=v: self.set(model=v), s["model"] == v) for v, label in MODELS]
            items.append(("自己填…", self.ask_custom, s["model"] == "custom"))
            items.append(None)
            items.append(("想得多认真", [(f"{name}（{v}）", lambda v=v: self.set(effort=v), s.get("effort", "high") == v) for v, name in EFFORTS],
                          False))
            items.append(("能上网查（要查时自己去必应搜）", lambda: self.set(web=not s.get("web", True)), s.get("web", True)))
        elif i == 1:
            items = [("不带对话（纯闲聊）" if n == 0 else f"最后 {n} 句", lambda n=n: self.set(ctxCount=n), s["ctxCount"] == n) for n in COUNTS]
        elif i == 2:
            items = [("每句不截（最多 2 万字）" if n == 0 else f"每句最多 {n} 字", lambda n=n: self.set(perChars=n), s["perChars"] == n) for n in CHARS]
        else:
            self.presets = load_presets()
            items = [("随便聊（不带规矩）", lambda: self.set(preset=""), not s["preset"])]
            items += [(p["name"], lambda n=p["name"]: self.set(preset=n), s["preset"] == p["name"]) for p in self.presets]
            items += [None, ("新建一个常用…", self.new_preset, False), ("改一个常用…", lambda: self.preset_pick(e, "edit"), False),
                      ("删掉一个常用…", lambda: self.preset_pick(e, "del"), False), ("打开「常用」文件夹", lambda: os.startfile(PRESETS), False)]
        self.popup(e, items)

    # ================= 语音：按住说话 =================
    # 用 Windows 自带的语音输入（Win+H），字直接打进输入框；松手（或再点一下）停，字留在输入框里（用户 2026-10-15 选的）
    def talk_press(self):
        if self.dictating:
            self.talk_stop()
            self.talk_t0 = 0
            return
        self.talk_t0 = time.time()
        self.talk_start()

    def talk_release(self):
        if self.dictating and self.talk_t0 and time.time() - self.talk_t0 > 0.6:
            self.talk_stop()

    def talk_start(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.entry.focus_force()
        self.entry.icursor("end")
        self.dictating = True
        self.root.after(150, press_win_h)
        self.render()

    def talk_stop(self):
        if not self.dictating:
            return
        self.dictating = False
        self.entry.focus_force()
        press_win_h()
        self.render()

    # ================= 菜单、对话框 =================
    def popup(self, e, items):
        m = tk.Menu(self.root, tearoff=0, font=self.f)
        for it in items:
            if it is None:
                m.add_separator()
            elif isinstance(it[1], list):  # (名字, [子菜单项…]) = 往右展开一层
                sub = tk.Menu(m, tearoff=0, font=self.f)
                for x in it[1]:
                    if x is None:
                        sub.add_separator()
                    else:
                        sub.add_command(label=("● " if x[2] else "　 ") + x[0], command=x[1])
                m.add_cascade(label=("● " if len(it) > 2 and it[2] else "　 ") + it[0], menu=sub)
            else:
                label, fn, on = it
                m.add_command(label=("● " if on else "　 ") + label, command=fn)
        m.tk_popup(e.x_root, e.y_root)

    def menu_main(self, e):
        s = self.state
        items = [("换频道（听哪个对话）…", lambda: self.menu_sessions(e), False)]
        if s["mode"] == 0:
            items.append(("清空这个频道的聊天", self.clear, False))
            items.append(("清空所有频道的聊天…", self.clear_all, False))
            if getattr(self, "deleted_chat", None):
                items.append(("撤销刚才删的聊天", self.undo_chat, False))
        if s["mode"] == 1 and self.deleted:
            items.append(("撤销刚才删的备忘", self.undo_delete, False))
        if s["mode"] == 2:
            items += [("新建一张图…", self.img_new, False), ("换一个生图请求…", lambda: self.img_pick(e), False)]
            if getattr(self, "deleted_img", None):
                items.append(("撤销刚才删的生图请求", self.undo_img_delete, False))
        items.append(None)
        if s["knobs"]:
            items.append(("收起旋钮（屏幕更大）", lambda: self.set(knobs=False), False))
        else:
            items += [("展开旋钮", lambda: self.set(knobs=True), False),
                      ("模型…", lambda: self.knob_menu(0, e), False), ("带几句…", lambda: self.knob_menu(1, e), False),
                      ("每句几字…", lambda: self.knob_menu(2, e), False), ("常用功能…", lambda: self.knob_menu(3, e), False)]
        items += [None, ("收起（双击桌宠再叫出来）", self.hide, False), ("退出对讲机", self.quit, False)]
        self.popup(e, items)

    def menu_sessions(self, e, then=None):
        self.refresh_sessions()
        if not self.sessions:
            self.popup(e, [("还没有开着的对话（要装好克讲机插件）", lambda: None, False)])
            return
        pick = then or self.choose
        self.popup(e, [(f"CH{i + 1:02d}  {d.get('label', d['sid'])}", lambda d=d: pick(d["sid"]), d["sid"] == self.state["sid"])
                       for i, d in enumerate(self.sessions)])

    def dialog(self, title, fields, ok_text="好", extra=None):
        """小对话框：fields = [(标签, 初始值, 是否多行)]；返回填好的值，取消返回 None"""
        T = self.T
        top = tk.Toplevel(self.root)
        top.title(title)
        top.wm_attributes("-topmost", True)
        top.config(bg=T["face"], padx=14, pady=12)
        top.transient(self.root)
        tk.Label(top, text=title, font=self.fb, bg=T["face"], fg=T["label"]).pack(anchor="w", pady=(0, 8))
        boxes, result = [], {"v": None}
        for label, value, multi in fields:
            tk.Label(top, text=label, font=self.fs, bg=T["face"], fg=T["label"]).pack(anchor="w")
            if multi:
                w = tk.Text(top, font=self.f, height=8, width=44, wrap="word", relief="flat", bg=T["screen"], fg=T["ink"])
                w.insert("1.0", value)
            else:
                w = tk.Entry(top, font=self.f, width=44, relief="flat", bg=T["screen"], fg=T["ink"])
                w.insert(0, value)
            w.pack(fill="x", pady=(2, 8), ipady=3)
            boxes.append((w, multi))
        row = tk.Frame(top, bg=T["face"])
        row.pack(fill="x")

        def ok():
            result["v"] = [w.get("1.0", "end").strip() if multi else w.get().strip() for w, multi in boxes]
            top.destroy()
        tk.Button(row, text=ok_text, font=self.fb, bg=T["accent"], fg="#ffffff", relief="flat", padx=14, command=ok).pack(side="right")
        tk.Button(row, text="算了", font=self.f, relief="flat", padx=10, command=top.destroy).pack(side="right", padx=6)
        if extra:  # 例：「删掉这条」，放在最左边，红字
            def do_extra():
                top.destroy()
                extra[1]()
            tk.Button(row, text=extra[0], font=self.f, relief="flat", fg="#c8341f", padx=8, command=do_extra).pack(side="left")
        top.update_idletasks()
        top.geometry(f"+{self.root.winfo_x() + 20}+{self.root.winfo_y() + 80}")
        boxes[0][0].focus_set()
        top.grab_set()
        self.root.wait_window(top)
        return result["v"]

    def ask_custom(self):
        v = self.dialog("自己填模型", [("模型名（例：claude-sonnet-5-5）", self.state["customModel"], False)])
        if v and v[0]:
            self.set(model="custom", customModel=v[0])

    def new_preset(self):
        v = self.dialog("新建一个常用功能", [("名字（例：起小红书标题）", "", False), ("规矩：问的时候照什么来", "", True)], "存好")
        if v and v[0]:
            n = len([p for p in os.listdir(PRESETS) if p.endswith(".md")]) if os.path.isdir(PRESETS) else 0
            safe = re.sub(r'[\\/:*?"<>|\s]+', "-", v[0])
            os.makedirs(PRESETS, exist_ok=True)
            with open(os.path.join(PRESETS, f"{n}-{safe}.md"), "w", encoding="utf-8") as f:
                f.write(f"# {v[0]}\n{v[1]}\n")
            self.presets = load_presets()
            self.set(preset=v[0])

    def preset_pick(self, e, what):
        self.presets = load_presets()
        items = [(p["name"], lambda p=p: self.preset_edit(p) if what == "edit" else self.preset_delete(p), False) for p in self.presets]
        self.popup(e, items or [("还没有常用功能", lambda: None, False)])

    def preset_edit(self, p):
        path = os.path.join(PRESETS, p["file"])
        raw = open(path, encoding="utf-8").read()
        body = "\n".join(raw.splitlines()[1:]).strip()
        v = self.dialog(f"改常用：{p['name']}", [("名字", p["name"], False), ("规矩（「来自：」那行是去读别的文件，别删）", body, True)], "改好",
                        extra=("删掉这个常用", lambda: self.preset_delete(p)))
        if v and v[0]:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {v[0]}\n{v[1]}\n")
            if self.state["preset"] == p["name"]:
                self.state["preset"] = v[0]
            self.presets = load_presets()
            self.save()
            self.render()

    def preset_delete(self, p):
        """删掉的常用放进 presets\\deleted，想找回就从那里拖回来"""
        if not self.confirm(f"删掉常用功能「{p['name']}」？\n（文件放进 presets\\deleted，想要再拖回来）"):
            return
        os.makedirs(os.path.join(PRESETS, "deleted"), exist_ok=True)
        os.replace(os.path.join(PRESETS, p["file"]), os.path.join(PRESETS, "deleted", p["file"]))
        if self.state["preset"] == p["name"]:
            self.state["preset"] = ""
        self.presets = load_presets()
        self.save()
        self.render()
        self.flash(f"删掉了常用「{p['name']}」")

    def set(self, **kv):
        self.state.update(kv)
        self.save()
        self.render()
        self.refresh_screen()

    def set_mode(self, m):
        self.state["mode"] = m
        self.save()
        self.render()
        self.refresh_screen()
        self.entry.focus_force()

    # ================= 频道 =================
    def refresh_sessions(self):
        self.sessions = live_sessions()
        ids = [d["sid"] for d in self.sessions]
        if self.state["sid"] not in ids and ids:
            self.state["sid"] = ids[0]
        self.autolink_memos()

    def current(self):
        return next((d for d in self.sessions if d["sid"] == self.state["sid"]), None)

    def session(self, sid):
        return next((d for d in self.sessions if d["sid"] == sid), None)

    def choose(self, sid):
        self.state["sid"] = sid
        self.save()
        self.refresh_screen()
        self.draw_overlay()

    def poll_sessions(self):
        old = (self.state["sid"], [d.get("label") for d in self.sessions])
        self.refresh_sessions()
        if old != (self.state["sid"], [d.get("label") for d in self.sessions]):
            self.refresh_screen()
        self.scan_img_reqs()
        self.draw_overlay()
        self.root.after(2000, self.poll_sessions)

    # ================= 屏幕内容 =================
    def style_views(self):
        T = self.T
        soft = hexc(skin.mix(T["ink"], 0.45))
        for c in (self.chat, self.memo):
            c.tag_config("me", font=self.fb, foreground=T["ink"], spacing1=10)
            c.tag_config("ai", font=self.f, foreground=T["ink"], lmargin1=8, lmargin2=8)
            c.tag_config("note", font=self.fs, foreground=soft, lmargin1=8)
            c.tag_config("err", font=self.f, foreground="#c8341f", lmargin1=8, lmargin2=8)
            c.tag_config("hint", font=self.f, foreground=soft, justify="center", spacing1=24)
            c.tag_config("link", font=self.fsb, foreground="#ffffff", background=T["accent"])
            c.tag_config("chip", font=self.fsb, foreground="#ffffff", background="#2f4fd8")
            c.tag_config("chipnew", font=self.fsb, foreground="#ffffff", background="#e2412b")
            c.tag_config("chipoff", font=self.fsb, foreground="#ffffff", background="#9a8f80")
            c.tag_config("done", overstrike=True, foreground=soft)
            for t in ("link", "chip", "chipnew", "chipoff", "box", "row"):
                c.tag_bind(t, "<Enter>", lambda e, c=c: c.config(cursor="hand2"))
                c.tag_bind(t, "<Leave>", lambda e, c=c: c.config(cursor="arrow"))
        w = max(100, self.screen_size[0] - 16) if hasattr(self, "screen_size") else 300
        self.memo.config(tabs=(w, "right"))
        for wdg in (self.imgf, self.img_hrow, self.img_head, self.img_del, self.img_label, self.img_thumbs, self.img_acts, self.img_pend, self.img_plabel):
            wdg.config(bg=T["screen"])
        self.img_head.config(fg=T["ink"])
        self.img_log.config(bg=T["screen"], fg=T["ink"])
        self.img_log.tag_config("note", font=self.fs, foreground=soft)
        self.img_log.tag_config("link", font=self.fsb, foreground="#ffffff", background=T["accent"])

    def refresh_screen(self):
        [self.render_chat, self.render_memo, self.render_img][self.state["mode"]]()

    # ---------- 聊 ----------
    def lines(self, sid=None):
        return self.state["chats"].setdefault(sid or self.state["sid"] or "_", [])

    def render_chat(self):
        c = self.chat
        c.config(state="normal")
        c.delete("1.0", "end")
        if not self.current():
            c.insert("end", "还没有开着的对话\n\n打开 Claude 应用里的一个对话\n（装好克讲机插件的），这里就能问了", "hint")
        elif not self.lines():
            c.insert("end", "取名字、查个词、随口问一句都行\n按住麦克风可以直接说\n\n主对话看不到这里\n满意的话点下面的按钮交给它去做", "hint")
        items = self.lines() if self.current() else []
        c.tag_config("del", font=self.fs, foreground="#c8341f")
        c.tag_bind("del", "<Enter>", lambda e: c.config(cursor="hand2"))
        c.tag_bind("del", "<Leave>", lambda e: c.config(cursor="arrow"))
        if items:  # 删除要看得见（用户 2026-10-15：“以前那些对话可不可以清空还有删掉”）
            c.insert("end", " ✕ 清空这个频道的聊天 ", ("del", "clearall"))
            c.tag_bind("clearall", "<Button-1>", lambda e: self.clear())
            c.insert("end", "\n")
        for i, l in enumerate(items):
            if l["who"] == "me":
                c.insert("end", "你：" + l["text"], "me")
                c.insert("end", "  ✕\n", ("del", f"dl{i}"))
            elif l.get("isError"):
                c.insert("end", l["text"], "err")
                c.insert("end", "  ✕\n", ("del", f"dl{i}"))
            else:
                c.insert("end", l["text"].strip() + "\n", "ai")
                c.insert("end", (l.get("note") or "") + "\n", "note")
            c.tag_bind(f"dl{i}", "<Button-1>", lambda e, i=i: self.chat_delete(i))
            if l["who"] == "me" or l.get("isError"):
                continue
            ask = next((x["text"] for x in reversed(items[:i]) if x["who"] == "me"), "")
            for label, mode in ((" 放进输入框 ", "fill"), (" 直接发 ", "send"), (" 新开对话做 ", "new"), (" 记一笔 ", "memo")):
                tag = f"act{i}{mode}"
                c.insert("end", label, ("link", tag))
                if mode == "memo":
                    c.tag_bind(tag, "<Button-1>", lambda e, t=l["text"]: self.memo_add(t, link=self.cur_link()))
                else:
                    c.tag_bind(tag, "<Button-1>", lambda e, t=l["text"], q=ask, m=mode: self.tell(t, q, m))
                c.insert("end", " ")
            c.insert("end", " ✕ ", ("del", f"dl{i}"))  # 删这条回答（右键能撤销）
            c.insert("end", "\n")
        if self.waiting and self.waiting[1] == self.state["sid"]:
            pr = read_json(os.path.join(BRIDGE, f"progress-{self.waiting[1]}.json"), None)
            doing = pr.get("text") if isinstance(pr, dict) and pr.get("id") == self.waiting[0] else ""
            c.insert("end", (f"🔎 {doing}……" if doing else "在想……") + "\n", "note")
        c.config(state="disabled")
        c.see("end")

    def history(self):
        good = [l for l in self.lines() if not l.get("isError")][-HISTORY:]
        return [{"who": l["who"], "text": l["text"]} for l in good]

    def preset_rules(self):
        p = next((p for p in self.presets if p["name"] == self.state["preset"]), None)
        return p["rules"] if p else ""

    def estimate(self):
        cur, s = self.current(), self.state
        if not cur:
            return 0, ""
        a = 0 if s["ctxCount"] == 0 else int((cur.get("est") or {}).get(f"{s['ctxCount']}-{s['perChars']}", 0))
        b = estimate("\n\n".join(h["text"] for h in self.history()))
        q = estimate(self.entry.get())
        r = estimate(self.preset_rules())
        return a + b + q + r + SYSTEM_EST, f"对话 {fmt(a)} · 记录 {fmt(b)} · 规矩 {fmt(r)} · 问题 {fmt(q)}"

    def ask_model(self, sid, text, extra, history):
        """交给那个对话的插件去问小模型，返回问题编号"""
        s = self.state
        model = s["customModel"] if s["model"] == "custom" else s["model"]
        qid = new_id()
        write_json(os.path.join(BRIDGE, f"ask-{sid}.json"), {
            "id": qid, "text": text, "model": model, "label": self.model_label(), "extra": extra,
            "ctxCount": s["ctxCount"], "perChars": s["perChars"], "history": history,
            "effort": s.get("effort", "high"), "web": s.get("web", True)})
        return qid

    def send(self):
        if self.dictating:
            self.talk_stop()
        mode = self.state["mode"]
        if mode == 1:
            return self.memo_from_entry()
        if mode == 2:
            return self.img_feedback()
        text = self.entry.get().strip()
        cur = self.current()
        if not text or self.waiting:
            return
        if not cur:
            self.flash("没有开着的对话，先打开 Claude 应用")
            return
        qid = self.ask_model(cur["sid"], text, self.preset_rules(), self.history())
        self.lines().append({"who": "me", "text": text})
        self.waiting = (qid, cur["sid"], time.time())
        self.entry.delete(0, "end")
        self.save()
        self.render()
        self.render_chat()

    def poll_answer(self):
        if self.waiting:
            qid, sid, t0 = self.waiting
            a = read_json(os.path.join(BRIDGE, f"answer-{sid}.json"), None)
            if isinstance(a, dict) and a.get("id") == qid:
                self.waiting = None
                self.lines(sid).append({k: a.get(k) for k in ("who", "text", "note", "isError") if a.get(k) is not None})
                self.state["chats"][sid] = self.lines(sid)[-KEEP:]
                self.save()
                self.mood, self.mood_until = ("cheer", time.time() + 4) if not a.get("isError") else ("urgent", time.time() + 4)
                if self.root.state() == "withdrawn":
                    self.notice("克讲机有回音：" + short(a.get("text") or "", 18))
                self.render()
                self.refresh_screen()
            elif time.time() - t0 > WAIT_S:
                self.waiting = None
                self.lines(sid).append({"who": "ai", "text": "等太久了，没等到回答（那个对话可能关了）。", "isError": True})
                self.render()
                self.refresh_screen()
            else:
                pr = read_json(os.path.join(BRIDGE, f"progress-{sid}.json"), None)
                key = (pr or {}).get("text") if isinstance(pr, dict) and pr.get("id") == qid else ""
                if key != getattr(self, "_progress", "") and self.state["mode"] == 0:
                    self._progress = key
                    self.render_chat()
                self.draw_overlay()
        if self.img_ask:
            qid, sid, t0, rid = self.img_ask
            a = read_json(os.path.join(BRIDGE, f"answer-{sid}.json"), None)
            if isinstance(a, dict) and a.get("id") == qid:
                self.img_ask = None
                r = self.state["imgs"].get(rid)
                if r is not None:
                    txt = a.get("text") or ""
                    tip = txt.split("【新提示词】", 1)[1].strip().strip("：:").strip() if "【新提示词】" in txt else ""
                    r.setdefault("talk", []).append({"who": "ai", "text": txt.split("【新提示词】")[0].strip() or txt,
                                                     "isError": a.get("isError"), "prompt": tip})
                    self.save()
                self.render()
                self.refresh_screen()
            elif time.time() - t0 > WAIT_S:
                self.img_ask = None
        while self.gen_results:
            self._gen_done(*self.gen_results.pop(0))
        if self.telling:
            tid, sid, t0 = self.telling
            t = read_json(os.path.join(BRIDGE, f"told-{sid}.json"), None)
            if isinstance(t, dict) and t.get("id") == tid:
                self.telling = None
                self.flash(t.get("msg") or "交过去了")
            elif time.time() - t0 > 20:
                self.telling = None
                self.flash("那个对话没反应，可能关了")
        if self.mood_until and time.time() > self.mood_until:
            self.mood_until = 0
            self.render()
        self.tell_pet()
        self.root.after(400, self.poll_answer)

    def tell_pet(self):
        """告诉桌宠小克现在在干嘛：它手里的迷你对讲机跟着摆动作（说话 / 听 / 画图 / 别在腰上）"""
        if self.dictating:
            pose = "talk"
        elif self.gen:
            pose = "paint"
        elif self.waiting or self.img_ask or (self.mood_until and time.time() < self.mood_until):
            pose = "listen"
        else:
            pose = "idle"
        T = self.T
        cols = {"body": "#fff3e0" if self.state["theme"] == "clawd" else T["face"], "screen": T["lcd"], "accent": T["accent"]}
        key = (pose, tuple(cols.values()))
        if key != getattr(self, "_pet_key", None) or time.time() - getattr(self, "_pet_at", 0) > 20:
            self._pet_key, self._pet_at = key, time.time()
            write_json(POSE, {"pose": pose, "until": time.time() + 30, "colors": cols})

    def tell(self, text, question, mode, sid=None, title=None):
        """交给那个对话：fill 放进输入框 / send 直接发 / new 新开对话。成功返回 True"""
        cur = self.session(sid) if sid else self.current()
        if not cur:
            self.flash("那个对话关了")
            return False
        data = {"id": new_id(), "text": text.strip(), "mode": mode}
        if mode == "new":
            v = self.dialog("新开一个对话去做", [("标题", title or short(question or text, 24), False),
                                             ("交给新对话的话（可以改）", f"{question}\n\n{text.strip()}" if question else text.strip(), True)], "开新对话")
            if not v:
                return False
            data.update(title=v[0], text=v[1])
        write_json(os.path.join(BRIDGE, f"tell-{cur['sid']}.json"), data)
        self.telling = (data["id"], cur["sid"], time.time())
        self.flash({"fill": "正在放进输入框…", "send": "正在发给对话…", "new": "正在开新对话…", "note": "存好了，等你下次在那边说话时顺带告诉它"}[mode])
        return data

    def clear(self):
        key = self.state["sid"] or "_"
        if not self.state["chats"].get(key):
            return
        self.deleted_chat = (key, list(self.state["chats"][key]), None)
        self.state["chats"][key] = []
        self.save()
        self.refresh_screen()
        self.draw_overlay()
        self.flash("清空了（右键能撤销）")

    def clear_all(self):
        if not any(self.state["chats"].values()) or not self.confirm("把所有频道的聊天记录都清空？（右键能撤销）"):
            return
        self.deleted_chat = ("*", {k: list(v) for k, v in self.state["chats"].items()}, None)
        self.state["chats"] = {}
        self.save()
        self.refresh_screen()
        self.flash("所有频道的聊天都清空了（右键能撤销）")

    def chat_delete(self, i):
        key = self.state["sid"] or "_"
        items = self.state["chats"].get(key) or []
        if 0 <= i < len(items):
            self.deleted_chat = (key, items.pop(i), i)
            self.save()
            self.refresh_screen()
            self.flash("删了这条（右键能撤销）")

    def undo_chat(self):
        d = getattr(self, "deleted_chat", None)
        if not d:
            return
        key, what, i = d
        if key == "*":
            self.state["chats"] = what
        elif i is None:
            self.state["chats"][key] = what
        else:
            self.state["chats"].setdefault(key, []).insert(i, what)
        self.deleted_chat = None
        self.save()
        self.refresh_screen()

    # ---------- 记（备忘录） ----------
    def cur_link(self):
        cur = self.current()
        return {"sid": cur["sid"], "label": cur.get("label", "")} if cur else None

    def memo_to(self):
        """新的一条记到哪：state["memoTo"] 没设 = 跟着现在的频道（用户 2026-10-15：记的时候要能挑挂到哪个对话下面）"""
        to = self.state.get("memoTo")
        return to if to else self.cur_link()

    def memo_to_text(self):
        to = self.state.get("memoTo")
        if not to:
            cur = self.cur_link()
            return f"跟着频道 · {short(cur['label'], 10)}" if cur else "现在没频道 → 不连"
        if to.get("new"):
            return "新开一个对话去做"
        if to.get("none"):
            return "不连对话"
        i = next((i for i, d in enumerate(self.sessions) if d["sid"] == to.get("sid")), -1)
        return (f"CH{i + 1:02d} " if i >= 0 else "○ ") + short(to.get("label", ""), 16)

    def conv_choices(self, pick, now_sid=None):
        """菜单项：开着的频道 + 侧边栏里最近的对话（没开着对讲机的也能挂）"""
        self.refresh_sessions()
        items = [(f"CH{i + 1:02d}  {short(d.get('label', d['sid']), 24)}", lambda d=d: pick({"sid": d["sid"], "label": d.get("label", "")}),
                  now_sid == d["sid"]) for i, d in enumerate(self.sessions)]
        # 再往下：跟侧边栏一样的分组，每组往右展开（没开着对讲机的对话也能挂）
        ch = {d["sid"]: i for i, d in enumerate(self.sessions)}
        groups = sidebar_groups()
        if groups:
            items.append(None)
        for name, convs in groups:
            sub = [((f"CH{ch[c['sid']] + 1:02d} " if c["sid"] in ch else "○ ") + short(c["label"], 26),
                    lambda c=c: pick({"sid": c["sid"], "label": c["label"]}), now_sid == c["sid"]) for c in convs[:25]]
            items.append((f"{short(name, 18)}（{len(convs)}）", sub, any(c["sid"] == now_sid for c in convs)))
        return items

    def memo_to_menu(self, e):
        to = self.state.get("memoTo")

        def pick(v):
            self.state["memoTo"] = v
            self.save()
            self.render_memo()
            self.entry.focus_set()
        items = [("跟着现在的频道（换频道它也跟着换）", lambda: pick(None), not to), None]
        items += self.conv_choices(pick, (to or {}).get("sid"))
        items += [None, ("新开一个对话去做（记下就开）", lambda: pick({"new": True}), bool(to and to.get("new"))),
                  ("不连对话", lambda: pick({"none": True}), bool(to and to.get("none")))]
        self.popup(e, items)

    def memo_to_set(self, link):
        self.state["memoTo"] = link
        self.save()
        self.render_memo()
        self.entry.focus_set()
        self.flash(f"下一条记到「{short(link.get('label', ''), 12)}」，在下面打字回车")

    def memo_from_entry(self):
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            to = self.memo_to()
            if to and to.get("new"):
                self.memo_add(text, link=None)
                self.memo_new_session(self.state["memos"][0]["id"])
            else:
                self.memo_add(text, link=None if not to or to.get("none") else to)

    def memo_add(self, text, link=None):
        self.state["memos"].insert(0, {"id": new_id(), "text": text.strip(), "done": False, "link": link, "at": time.time()})
        self.save()
        self.flash("记下了" + (f"，挂在「{short(link.get('label', ''), 12)}」下面" if link else ""))
        if self.state["mode"] == 1:
            self.render_memo()

    def memo_by(self, mid):
        return next((m for m in self.state["memos"] if m["id"] == mid), None)

    def chip_text(self, m):
        ln = m.get("link")
        if not ln:
            return " 连到… ", "chipoff"
        if ln.get("new"):
            return (" 已开新对话 " if ln.get("started") else " 新开对话 "), "chipnew"
        i = next((i for i, d in enumerate(self.sessions) if d["sid"] == ln.get("sid")), -1)
        ch = f"CH{i + 1:02d} " if i >= 0 else "（关了）"
        return f" {ch}{short(ln.get('label', ''), 8)} ", "chip"

    def render_memo(self):
        """记档 = 通联日志屏（用户 2026-10-15 选的）：整块屏变成背光屏，按频道分组；没做完的亮红灯，做完写 OVER"""
        c, T = self.memo, self.T
        c.config(state="normal", bg=T["lcd"], fg=T["lcd_ink"])
        c.delete("1.0", "end")
        memos = self.state["memos"]
        ink = T["lcd_ink"]
        dim = hexc(skin.mix(T["lcd_ink"], 0.45))
        c.tag_config("lh", font=self.flog_b, foreground=ink, spacing1=8, spacing3=2)
        c.tag_config("lline", font=self.flog, foreground=ink, lmargin1=6, lmargin2=34)
        c.tag_config("lled", font=self.flog, foreground="#e2412b")
        c.tag_config("lover", font=self.flog, foreground=dim, overstrike=True, lmargin1=6, lmargin2=34)
        c.tag_config("ltime", font=self.flog, foreground=dim)
        c.tag_config("ledit", font=self.flog, foreground=dim)
        c.tag_config("ldel", font=self.flog, foreground="#c8341f")
        c.tag_config("lhint", font=self.flog, foreground=dim, justify="center", spacing1=20)
        c.tag_config("lto", font=self.flog_b, foreground=T["lcd"], background=ink, lmargin1=6, spacing1=4, spacing3=4)
        c.tag_config("ladd", font=self.flog_b, foreground=ink)
        for t in ("lh", "lline", "lled", "ledit", "ldel", "lto", "ladd"):
            c.tag_bind(t, "<Enter>", lambda e: c.config(cursor="hand2"))
            c.tag_bind(t, "<Leave>", lambda e: c.config(cursor="arrow"))
        # 最上面一行：新的一条记到哪（点开挑：开着的频道 / 侧边栏里的对话 / 新开 / 不连）
        c.insert("end", f" ✎ 下一条记到：{self.memo_to_text()} ▾\n", "lto")
        c.tag_bind("lto", "<Button-1>", self.memo_to_menu)
        if not memos:
            c.insert("end", "— 日志是空的 —\n\n下面打字（或按住麦克风说），回车记一条\n记到哪个对话：点最上面那行挑\n点一条就跳到它的频道", "lhint")
            c.config(state="disabled")
            return
        # 分组：开着的频道（按 CH 顺序）→ 关了的 → 新开对话 → 没连
        groups, order = {}, []

        def key_of(m):
            ln = m.get("link") or {}
            if ln.get("sid"):
                return "s:" + ln["sid"]
            if ln.get("new"):
                return "new"
            return "none"
        for m in memos:
            k = key_of(m)
            if k not in groups:
                groups[k] = []
                order.append(k)
            groups[k].append(m)
        ids = [d["sid"] for d in self.sessions]
        order.sort(key=lambda k: (0, ids.index(k[2:])) if k.startswith("s:") and k[2:] in ids
                   else (1, 0) if k.startswith("s:") else (2, 0) if k == "new" else (3, 0))
        for gi, k in enumerate(order):
            items = sorted(groups[k], key=lambda m: (m.get("done", False), -m.get("at", 0)))
            todo = sum(1 for m in items if not m.get("done"))
            if k.startswith("s:"):
                sid = k[2:]
                i = ids.index(sid) if sid in ids else -1
                label = (self.session(sid) or {}).get("label") or (items[0].get("link") or {}).get("label", "")
                head = f"CH{i + 1:02d} {short(label, 16)}" if i >= 0 else f"○ {short(label, 14)}（没开着）"
            elif k == "new":
                head, sid = "NEW 新开的对话", None
            else:
                head, sid = "—  没连频道", None
            htag = f"grp{gi}"
            c.insert("end", f"{head}  ▸ {todo}", ("lh", htag))
            if sid:
                c.tag_bind(htag, "<Button-1>", lambda e, s=sid: self.jump_channel(s))
                # 组标题后面「＋」：下一条直接记到这一组的对话
                link = {"sid": sid, "label": label}
                c.insert("end", "  ＋记这里", ("ladd", f"add{gi}"))
                c.tag_bind(f"add{gi}", "<Button-1>", lambda e, ln=link: self.memo_to_set(ln))
            c.insert("end", "\n", "lh")
            for m in items:
                mid = m["id"]
                t = time.localtime(m.get("at") or time.time())
                stamp = time.strftime("%H:%M" if time.time() - (m.get("at") or 0) < 86400 else "%m-%d", t)
                if m.get("done"):
                    c.insert("end", f"  {stamp} {m['text']} ··· OVER", ("lover", f"row{mid}"))
                else:
                    c.insert("end", "● ", ("lled", f"box{mid}"))
                    c.insert("end", stamp + " ", "ltime")
                    c.insert("end", m["text"], ("lline", f"row{mid}"))
                c.insert("end", "  ⇄", ("ledit", f"mv{mid}"))
                c.insert("end", "  ✎", ("ledit", f"ed{mid}"))
                c.insert("end", "  ✕\n", ("ldel", f"del{mid}"))
                c.tag_bind(f"mv{mid}", "<Button-1>", lambda e, i=mid: self.memo_link_menu(i, e))
                c.tag_bind(f"box{mid}", "<Button-1>", lambda e, i=mid: self.memo_toggle(i))
                c.tag_bind(f"row{mid}", "<Button-1>", lambda e, i=mid: self.memo_open(i))
                c.tag_bind(f"row{mid}", "<Double-Button-1>", lambda e, i=mid: self.memo_edit(i))
                c.tag_bind(f"row{mid}", "<Button-3>", lambda e, i=mid: self.memo_menu(i, e))
                c.tag_bind(f"ed{mid}", "<Button-1>", lambda e, i=mid: self.memo_edit(i))
                c.tag_bind(f"del{mid}", "<Button-1>", lambda e, i=mid: self.memo_delete(i))
        c.insert("end", "\n红灯=做完 · 点一条=跳频道 · ⇄=挂到别的对话 · ✎=改 · ✕=删（右键能撤销）", "lhint")
        c.config(state="disabled")

    def jump_channel(self, sid):
        if self.session(sid):
            self.state["sid"] = sid
            self.set_mode(0)
        else:
            self.flash("那个对话现在没开")

    def memo_toggle(self, mid):
        m = self.memo_by(mid)
        if m:
            m["done"] = not m.get("done")
            self.save()
            self.render_memo()
            self.draw_overlay()

    def memo_open(self, mid):
        """点一条：频道跳到它连着的对话，换到聊档"""
        m = self.memo_by(mid)
        ln = (m or {}).get("link") or {}
        if ln.get("sid") and self.session(ln["sid"]):
            self.state["sid"] = ln["sid"]
            self.flash(f"跳到 {short(ln.get('label', ''), 12)}")
            self.set_mode(0)
        elif ln.get("sid"):
            self.flash("它连着的对话暂时没信号（关了或者在重新加载）")
        elif not ln:
            self.flash("这条还没连对话，点右边的牌子连一个")

    def memo_edit(self, mid):
        m = self.memo_by(mid)
        if not m:
            return
        v = self.dialog("改这条备忘", [("内容", m["text"], True)], "改好", extra=("删掉这条", lambda: self.memo_delete(mid)))
        if v and v[0]:
            m["text"] = v[0]
            self.save()
            self.render_memo()

    def memo_menu(self, mid, e):
        self.popup(e, [("改…", lambda: self.memo_edit(mid), False), ("做完了 / 没做完", lambda: self.memo_toggle(mid), False),
                       ("连到哪个对话…", lambda: self.memo_link_menu(mid, e), False), None,
                       ("删掉", lambda: self.memo_delete(mid), False)])

    def memo_delete(self, mid):
        m = self.memo_by(mid)
        if m:
            self.state["memos"].remove(m)
            self.deleted = m
            self.save()
            self.render_memo()
            self.flash("删了（右键能撤销）")

    def undo_delete(self):
        if self.deleted:
            self.state["memos"].insert(0, self.deleted)
            self.deleted = None
            self.save()
            self.render_memo()

    def memo_link_menu(self, mid, e):
        m = self.memo_by(mid)
        if not m:
            return
        items = self.conv_choices(lambda ln: self.memo_link(mid, ln), (m.get("link") or {}).get("sid"))
        items += [None, ("新开一个对话去做这件事…", lambda: self.memo_new_session(mid), False),
                  ("不连", lambda: self.memo_link(mid, None), not m.get("link"))]
        self.popup(e, items)

    def memo_link(self, mid, link):
        m = self.memo_by(mid)
        if m:
            m["link"] = link
            self.save()
            self.render_memo()
            self.draw_overlay()

    def memo_new_session(self, mid):
        m = self.memo_by(mid)
        if not m:
            return
        if not self.current():
            self.flash("要先有一个开着的对话帮忙开新对话")
            return
        data = self.tell(m["text"], "", "new", title=short(m["text"], 24))
        if data:
            m["link"] = {"new": True, "started": True, "title": data.get("title", ""), "key": short(data.get("text", ""), 12)}
            self.save()
            self.render_memo()

    def autolink_memos(self):
        """新开的对话报到后（名字里有它第一句话的开头），自动连上"""
        for m in self.state.get("memos", []):
            ln = m.get("link") or {}
            if ln.get("new") and ln.get("started") and ln.get("key"):
                key = ln["key"].rstrip("…")[:8]
                hit = next((d for d in self.sessions if key and key in d.get("label", "")), None)
                if hit:
                    m["link"] = {"sid": hit["sid"], "label": hit.get("label", "")}

    # ---------- 画（生图台） ----------
    # 一个生图请求 r：prompt 现在的提示词；pending 对话 / 模型推来、还没用的新提示词；history 改过的提示词；
    # feedback 你写的“哪里不满意”（换了新提示词就清空）；versions 每一版图；count 一次出几张（用户 2026-10-15 要的）
    def build_img_view(self):
        f = self.imgf
        self.img_hrow = tk.Frame(f)
        self.img_hrow.pack(fill="x", padx=6, pady=(4, 1))
        self.img_del = tk.Label(self.img_hrow, text="✕ 删掉这个请求", cursor="hand2", fg="#c8341f")
        self.img_del.pack(side="right")
        self.img_del.bind("<Button-1>", lambda e: self.img_delete())
        self.img_head = tk.Label(self.img_hrow, anchor="w", justify="left")
        self.img_head.pack(side="left", fill="x", expand=True)
        self.img_pend = tk.Frame(f)          # 推来的新提示词（有才显示）
        self.img_pend.pack(fill="x", padx=6)
        pf = tk.Frame(f)
        pf.pack(fill="x", padx=6, pady=(2, 0))
        self.img_plabel = tk.Label(pf, anchor="w")
        self.img_plabel.pack(fill="x")
        self.img_prompt = tk.Text(pf, height=6, wrap="word", relief="solid", bd=1, padx=6, pady=4, highlightthickness=0)
        self.img_prompt.pack(fill="x")
        self.img_prompt.bind("<FocusOut>", lambda e: self.img_prompt_saved())
        self.img_log = tk.Text(f, height=3, wrap="word", relief="flat", bd=0, padx=4, pady=2, highlightthickness=0)
        self.img_log.pack(side="bottom", fill="x", padx=6, pady=(2, 4))
        self.img_acts = tk.Frame(f)
        self.img_acts.pack(side="bottom", fill="x", padx=6, pady=2)
        self.img_thumbs = tk.Frame(f)
        self.img_thumbs.pack(side="bottom", fill="x", padx=6, pady=2)
        self.img_label = tk.Label(f, bd=0, cursor="hand2")
        self.img_label.pack(fill="both", expand=True, padx=6, pady=(4, 0))
        self.img_label.bind("<Button-1>", lambda e: self.img_open_file())

    def scan_img_reqs(self):
        """主对话交过来的生图请求（img-req-*）和推来的新提示词（img-upd-*）"""
        try:
            names = os.listdir(BRIDGE)
        except OSError:
            return
        imgs, new = self.state["imgs"], []
        seen = self.state.setdefault("seenImg", [])
        for n in names:
            if n.startswith("img-req-") and n.endswith(".json"):
                path = os.path.join(BRIDGE, n)
                r = read_json(path, None)
                if not isinstance(r, dict) or not r.get("id"):
                    continue
                if r["id"] not in imgs and r["id"] not in seen:
                    imgs[r["id"]] = {**r, "versions": [], "talk": [], "feedback": [], "history": [], "pending": None}
                    new.append(r)
                # 读进来了就只认克讲机自己的记录：记下编号、删掉文件，删了的请求不会再冒出来
                if r["id"] not in seen:
                    seen.append(r["id"])
                    del seen[:-300]
                try:
                    os.remove(path)
                except OSError:
                    pass
        upd = []
        for n in sorted(names):
            if n.startswith("img-upd-") and n.endswith(".json"):
                p = os.path.join(BRIDGE, n)
                u = read_json(p, None)
                if isinstance(u, dict) and u.get("rid") in imgs:
                    r = imgs[u["rid"]]
                    self.img_adopt(r, {"prompt": u.get("prompt", ""), "note": u.get("note", ""), "from": "对话"})
                    r["fresh"] = {"note": u.get("note", ""), "from": "对话"}
                    upd.append(u)
                try:
                    os.remove(p)
                except OSError:
                    pass
        if new:
            self.state["imgCur"] = new[-1]["id"]
            self.notice("生图台来活了：" + short(new[-1].get("title") or new[-1].get("prompt", ""), 14))
            self.flash("有新的生图请求")
            for r in new:
                self.img_generate(r["id"])
        if upd:
            self.state["imgCur"] = upd[-1]["rid"]
            self.notice("对话推来了新提示词，等你点「再来一轮」")
            self.flash("对话推来了新提示词，已经换进提示词框")
        if new or upd:
            self.save()
            if self.state["mode"] == 2:
                self.render_img()

    def img_new(self):
        cur = self.current()
        v = self.dialog("新建一张图", [("这是什么图（一句话）", "", False), ("要求 / 提示词", "", True)], "开始生")
        if not v or not v[1]:
            return
        rid = new_id()
        self.state["imgs"][rid] = {"id": rid, "sid": cur["sid"] if cur else "", "label": cur.get("label", "") if cur else "",
                                   "title": v[0], "prompt": v[1], "refs": [], "saveTo": "", "saveAs": "", "at": time.time() * 1000,
                                   "versions": [], "talk": [], "feedback": [], "history": [], "pending": None}
        self.state["imgCur"] = rid
        self.save()
        self.img_generate(rid)
        self.set_mode(2)

    def img_pick(self, e):
        items = [(f"{short(r.get('title') or r['prompt'], 18)}（{len([v for v in r['versions'] if not v.get('gone')])} 版）",
                  lambda i=rid: (self.state.update(imgCur=i), self.save(), self.render(), self.render_img()), rid == self.state["imgCur"])
                 for rid, r in sorted(self.state["imgs"].items(), key=lambda kv: -kv[1].get("at", 0))]
        self.popup(e, items or [("还没有生图请求", lambda: None, False)])

    def img_cur(self):
        return self.state["imgs"].get(self.state["imgCur"])

    def img_count(self):
        return int(self.state.get("imgCount") or 1)

    def img_adopt(self, r, src=None):
        """把推来的新提示词换上：旧的进历史，“不满意”清空"""
        p = src or r.get("pending")
        if not p or not p.get("prompt"):
            return
        r.setdefault("history", []).append({"prompt": r["prompt"], "note": p.get("note", ""), "from": p.get("from", ""), "at": time.time()})
        r["prompt"] = p["prompt"]
        r["feedback"] = []
        r["pending"] = None

    def img_round(self):
        """再来一轮：有推来的新提示词就先换上，再按「一次几张」生"""
        r = self.img_cur()
        if not r:
            self.flash("还没有生图请求，右键可以新建一张")
            return
        self.img_prompt_saved()
        if r.get("pending"):
            self.img_adopt(r)
        self.save()
        self.img_generate(r["id"])

    def img_generate(self, rid, feedback=""):
        r = self.state["imgs"].get(rid)
        if not r:
            return
        if self.gen:
            r.setdefault("queue", []).append(feedback)
            self.flash("前面一轮还在生，排上队了")
            return
        codex = find_codex()
        if not codex:
            r["talk"].append({"who": "ai", "text": "电脑上找不到 Codex，生不了图。", "isError": True})
            self.render_img()
            return
        vs = [v for v in r["versions"] if not v.get("gone")]
        refs = [p for p in r.get("refs") or [] if os.path.exists(p)]
        if feedback:
            r["feedback"].append(feedback)
        # 有“不满意”就在上一版（或选中的那版）上改；换了新提示词就从头画
        pick = r.get("pick")
        base = r["versions"][pick]["path"] if (r["feedback"] and isinstance(pick, int) and 0 <= pick < len(r["versions"])) else \
            (vs[-1]["path"] if r["feedback"] and vs else None)
        n = self.img_count()
        r.pop("fresh", None)
        self.gen = {"rid": rid, "t0": time.time(), "left": n}
        self.render()
        if self.state["mode"] == 2:
            self.render_img()
        for i in range(n):
            lines = ["请直接用你的生图功能生成一张图片（不要写代码，不要改任何文件），然后告诉我图片保存在哪里（写出完整路径）。"]
            if base:
                lines.append("第一张附图是上一版，照下面的修改意见改它。")
            if refs:
                lines.append(f"{'后面' if base else ''}的附图是参考图。")
            lines.append("要求：" + r["prompt"])
            if r["feedback"]:
                lines.append("修改意见（按先后，最后一条最重要）：\n" + "\n".join(f"- {x}" for x in r["feedback"]))
            if n > 1:
                lines.append(f"（这一轮要出 {n} 张，这是第 {i + 1} 张：在符合要求的前提下，构图或细节和别的几张拉开一点。）")
            args = [codex, "exec", "--skip-git-repo-check", "-s", "read-only"]
            for p in ([base] if base else []) + refs:
                args += ["-i", p]
            args.append("-")
            threading.Thread(target=self._gen_run, args=(rid, args, "\n".join(lines)), daemon=True).start()

    def _gen_run(self, rid, args, prompt):
        t0 = time.time()
        err, out = "", ""
        try:
            p = subprocess.run(args, input=prompt.encode("utf-8"), capture_output=True, timeout=GEN_S, creationflags=0x08000000)
            out = (p.stdout or b"").decode("utf-8", "replace")
            if p.returncode != 0:
                err = (p.stderr or b"").decode("utf-8", "replace")[-200:]
        except subprocess.TimeoutExpired:
            err = "等太久了（超过 7 分钟）"
        except OSError as ex:
            err = str(ex)
        # 先从 Codex 的回答里找它说的图片路径（几张同时生时不会拿错），找不到再找这段时间里新出的图
        path = None
        for m in re.findall(r"[A-Za-z]:[\\/][^\s\"'`<>|*?]+?\.png", out):
            if os.path.exists(m):
                path = m
        if not path:
            made = [f for f in glob.glob(os.path.join(CODEX_OUT, "**", "*.png"), recursive=True)
                    if os.path.getmtime(f) >= t0 - 1 and f not in self.claimed]
            path = max(made, key=os.path.getmtime) if made else None
        if path:
            self.claimed.add(path)
        # 窗口只能在主线程里改：结果先放这儿，poll_answer 来取
        self.gen_results.append((rid, path, err))

    def _gen_done(self, rid, path, err):
        r = self.state["imgs"].get(rid)
        if r is not None:
            if path:
                n = len(r["versions"]) + 1
                dst = os.path.join(IMAGES, rid, f"v{n}.png")
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(path, dst)
                r["versions"].append({"path": dst, "at": time.time(), "fb": r["feedback"][-1] if r["feedback"] else "",
                                      "prompt": r["prompt"]})
                r["pick"] = len(r["versions"]) - 1
                self.mood, self.mood_until = "cheer", time.time() + 4
                if self.root.state() == "withdrawn":
                    self.notice("图生好了：" + short(r.get("title") or "", 14))
            else:
                r["talk"].append({"who": "ai", "text": "这张没生出来" + (f"：{err}" if err else "") + "。可以再点一次「再来一轮」。", "isError": True})
            self.save()
        if self.gen and self.gen["rid"] == rid:
            self.gen["left"] -= 1
            if self.gen["left"] <= 0:
                self.gen = None
                q = (r or {}).get("queue") or []
                if q:
                    self.img_generate(rid, q.pop(0))
        self.render()
        if self.state["mode"] == 2:
            self.render_img()

    def render_img(self):
        T = self.T
        r = self.img_cur()
        soft = hexc(skin.mix(T["ink"], 0.45))
        for wdg in self.img_thumbs.winfo_children() + self.img_acts.winfo_children() + self.img_pend.winfo_children():
            wdg.destroy()
        self.photos = []
        log = self.img_log
        log.config(state="normal")
        log.delete("1.0", "end")
        self.img_prompt.config(state="normal")
        self.img_prompt.delete("1.0", "end")
        if not r:
            self.img_head.config(text="生图台还空着", font=self.fsb)
            self.img_del.pack_forget()
            self.img_plabel.config(text="")
            self.img_prompt.config(state="disabled")
            self.img_label.config(image="", text="主对话的 Claude 要出图时会交到这里\n你也可以右键 →「新建一张图」", font=self.f, fg=soft)
            log.config(state="disabled")
            return
        if r.get("pending"):  # 旧版留下的“推来没用”的提示词：现在直接换进框里
            p0 = r["pending"]
            self.img_adopt(r)
            r["fresh"] = {"note": p0.get("note", ""), "from": p0.get("from", "对话")}
        self.img_head.config(text=f"「{short(r.get('title') or '', 12)}」 来自 {short(r.get('label') or '自己', 10)}",
                             font=self.fsb, fg=T["ink"])
        self.img_del.config(font=self.fs)
        self.img_del.pack(side="right")
        hist = r.get("history") or []
        more = f"　改过 {len(hist)} 次 ▾" if hist else ""
        fresh = r.get("fresh")
        if fresh:  # 对话 / 模型刚推来、还没生：整行亮一下
            self.img_plabel.config(text=f"📻 {fresh.get('from') or '对话'}刚换进来的提示词，还没生" + (f"：{fresh['note']}" if fresh.get("note") else "") + more,
                                   font=self.fsb, fg=T["lcd_ink"], bg=T["lcd"], cursor="hand2" if hist else "arrow")
        else:
            self.img_plabel.config(text=f"提示词（直接在框里改）{more}", font=self.fs, fg=soft, bg=T["screen"], cursor="hand2" if hist else "arrow")
        self.img_plabel.bind("<Button-1>", lambda e: self.img_history_menu(e) if hist else None)
        self.img_prompt.insert("1.0", r["prompt"])
        self.img_prompt.config(bg="#ffffff", fg=T["ink"], font=self.fs, insertbackground=T["ink"])
        vs = [(i, v) for i, v in enumerate(r["versions"]) if not v.get("gone")]
        pick = r.get("pick", vs[-1][0] if vs else -1)
        if vs and pick not in [i for i, _ in vs]:
            pick = vs[-1][0]
        # 大图的大小 = 上下几样摆好以后剩下的地方（先把小图、按钮行画上，量一下）
        self.img_label.config(image="", text="")
        self.img_thumbs.config(height=int(36 * self.k))
        self.root.update_idletasks()
        sw, sh = getattr(self, "screen_size", (300, 300))
        used = sum(w.winfo_reqheight() for w in (self.img_head, self.img_pend, self.img_plabel, self.img_prompt, self.img_log)) \
            + int(36 * self.k) + int(30 * self.k) + int(24 * self.k)
        box_w, box_h = max(60, sw - int(16 * self.k)), max(60, sh - used)
        if self.gen and self.gen["rid"] == r["id"]:
            secs = int(time.time() - self.gen["t0"])
            self.img_label.config(image="", text=f"Codex 在画……{secs} 秒（还差 {self.gen['left']} 张）\n一般 1～3 分钟", font=self.f, fg=T["ink"])
            self.root.after(1000, lambda: self.state["mode"] == 2 and self.gen and self.render_img())
        elif vs:
            im = Image.open(r["versions"][pick]["path"])
            im.thumbnail((box_w, box_h))
            ph = ImageTk.PhotoImage(im)
            self.photos.append(ph)
            self.img_label.config(image=ph, text="")
        else:
            self.img_label.config(image="", text="还没有图（排队中）", font=self.f, fg=T["ink"])
        # 参考图：蓝框，点一下看大图，✕ 去掉；「＋参考」加
        for ref in (r.get("refs") or [])[:3]:
            try:
                im = Image.open(ref)
                im.thumbnail((int(30 * self.k), int(30 * self.k)))
                ph = ImageTk.PhotoImage(im)
                self.photos.append(ph)
                b = tk.Label(self.img_thumbs, image=ph, bd=2, relief="solid", bg="#2f4fd8", cursor="hand2")
                b.pack(side="left", padx=(2, 0))
                b.bind("<Button-1>", lambda e, f=ref: os.startfile(f))
                x = tk.Label(self.img_thumbs, text="✕", font=self.fs, fg="#c8341f", bg=T["screen"], cursor="hand2")
                x.pack(side="left", padx=(0, 2))
                x.bind("<Button-1>", lambda e, f=ref: self.img_ref_remove(f))
            except OSError:
                pass
        add = tk.Label(self.img_thumbs, text="＋参考", font=self.fs, fg="#2f4fd8", bg=T["screen"], cursor="hand2")
        add.pack(side="left", padx=(2, 8))
        add.bind("<Button-1>", lambda e: self.img_ref_add())
        for i, v in vs[-6:]:
            try:
                im = Image.open(v["path"])
                im.thumbnail((int(32 * self.k), int(32 * self.k)))
                ph = ImageTk.PhotoImage(im)
                self.photos.append(ph)
                b = tk.Label(self.img_thumbs, image=ph, bd=2, relief="solid" if i == pick else "flat",
                             bg=T["accent"] if i == pick else T["screen"], cursor="hand2")
                b.pack(side="left", padx=2)
                b.bind("<Button-1>", lambda e, i=i: self.img_select(i))
                b.bind("<Button-3>", lambda e, i=i: self.img_drop(i))
            except OSError:
                pass
        if vs:  # 小图后面：扔掉选中的那版（看得见，不只靠右键）
            dl = tk.Label(self.img_thumbs, text="✕ 扔掉这版", font=self.fs, fg="#c8341f", bg=T["screen"], cursor="hand2")
            dl.pack(side="right")
            dl.bind("<Button-1>", lambda e, i=pick: self.img_drop(i))
        n = self.img_count()
        cnt = tk.Label(self.img_acts, text=f" ×{n} 张 ▾ ", font=self.fsb, fg=T["ink"], bg="#ffffff", cursor="hand2",
                       highlightthickness=1, highlightbackground=T["ink"])
        cnt.pack(side="left", padx=(0, 6))
        cnt.bind("<Button-1>", lambda e: self.popup(e, [(f"一次 {k} 张" + ("（每张都花一次 Codex 额度）" if k > 1 else ""),
                                                         lambda k=k: (self.state.update(imgCount=k), self.save(), self.render_img()), n == k)
                                                        for k in (1, 2, 3)]))
        for text, fn, col in (("用这张→存好", self.img_use, "#3b8f4e"), ("再来一轮", self.img_round, T["ink"]),
                              ("问模型", self.img_discuss, T["ink"]), ("主对话看图", self.img_ask_main, T["accent"])):
            b = tk.Label(self.img_acts, text=f" {text} ", font=self.fsb, fg="#ffffff", bg=col, cursor="hand2")
            b.pack(side="left", padx=(0, 4), pady=1)
            b.bind("<Button-1>", lambda e, fn=fn: fn())
        for t in r.get("talk", [])[-3:]:
            log.insert("end", ("你：" if t["who"] == "me" else f"{self.model_label()}：") + t["text"].strip() + "\n", "note")
        tip = next((t for t in reversed(r.get("talk", [])) if t["who"] == "ai" and not t.get("isError") and t.get("prompt")), None)
        if tip:
            log.insert("end", " 把它写的新提示词换进去 ", ("link", "use_tip"))
            log.tag_bind("use_tip", "<Button-1>", lambda e, t=tip: (self.img_adopt(r, {"prompt": t["prompt"], "note": "模型建议", "from": "模型"}),
                                                                    r.update(fresh={"note": "模型建议", "from": "模型"}), self.save(), self.render_img()))
        if not r.get("talk"):
            log.insert("end", "提示词直接在上面框里改；下面输入框写哪里不满意 → 回车照着改上一版；「再来一轮」按提示词重新画；"
                              "蓝框小图是参考图，点开看大图", "note")
        log.see("end")
        log.config(state="disabled")

    def img_prompt_saved(self):
        """提示词卡里直接改了：存下来，旧的进历史"""
        r = self.img_cur()
        if not r or str(self.img_prompt.cget("state")) == "disabled":
            return
        text = self.img_prompt.get("1.0", "end").strip()
        if text and text != r["prompt"]:
            self.img_adopt(r, {"prompt": text, "note": "你自己改的", "from": "你"})
            self.save()

    def img_history_menu(self, e):
        r = self.img_cur()
        if not r:
            return
        items = [(f"{h.get('from') or '?'} · {short(h['prompt'], 30)}", lambda h=h: (self.img_adopt(r, {"prompt": h["prompt"], "note": "换回旧的", "from": "你"}),
                                                                             self.save(), self.render_img()), False)
                 for h in reversed(r.get("history") or [])]
        self.popup(e, [("换回以前的提示词：", lambda: None, False), None] + items)

    def img_delete(self):
        """删掉整个生图请求（图片文件还留在 clawkie-bridge\\images 里，右键能撤销）"""
        r = self.img_cur()
        if not r:
            return
        if not self.confirm(f"删掉「{short(r.get('title') or r['prompt'], 16)}」这个生图请求？\n（已经生出来的图文件不删，右键菜单能撤销）"):
            return
        self.deleted_img = self.state["imgs"].pop(r["id"])
        seen = self.state.setdefault("seenImg", [])
        if r["id"] not in seen:
            seen.append(r["id"])
        try:  # 请求文件还在的话也删掉，免得又被读回来
            os.remove(os.path.join(BRIDGE, f"img-req-{r['id']}.json"))
        except OSError:
            pass
        rest = sorted(self.state["imgs"].values(), key=lambda x: -x.get("at", 0))
        self.state["imgCur"] = rest[0]["id"] if rest else ""
        self.save()
        self.render()
        self.render_img()
        self.flash("删掉了这个生图请求（右键能撤销）")

    def undo_img_delete(self):
        r = getattr(self, "deleted_img", None)
        if r:
            self.state["imgs"][r["id"]] = r
            self.state["imgCur"] = r["id"]
            self.deleted_img = None
            self.save()
            self.render_img()

    def confirm(self, text):
        from tkinter import messagebox
        return messagebox.askyesno("克讲机", text, parent=self.root, icon="warning")

    def img_ref_add(self):
        from tkinter import filedialog
        r = self.img_cur()
        if not r:
            return
        fs = filedialog.askopenfilenames(parent=self.root, title="选参考图", filetypes=[("图片", "*.png *.jpg *.jpeg *.webp"), ("全部", "*.*")])
        if fs:
            r["refs"] = list(dict.fromkeys((r.get("refs") or []) + list(fs)))[:3]
            self.save()
            self.render_img()

    def img_ref_remove(self, f):
        r = self.img_cur()
        if r and f in (r.get("refs") or []):
            r["refs"].remove(f)
            self.save()
            self.render_img()
            self.flash("去掉了这张参考图（＋参考 能再加回来）")

    def img_select(self, i):
        r = self.img_cur()
        if r:
            r["pick"] = i
            self.save()
            self.render_img()

    def img_drop(self, i):
        r = self.img_cur()
        if r and 0 <= i < len(r["versions"]):
            r["versions"][i]["gone"] = True
            self.save()
            self.render_img()
            self.flash("扔掉了这一版")

    def img_open_file(self):
        r = self.img_cur()
        if r and r["versions"]:
            v = r["versions"][r.get("pick", len(r["versions"]) - 1)]
            if os.path.exists(v["path"]):
                os.startfile(v["path"])

    def img_feedback(self):
        r = self.img_cur()
        text = self.entry.get().strip()
        if not r:
            self.flash("还没有生图请求，右键可以新建一张")
            return
        self.img_prompt_saved()
        self.entry.delete(0, "end")
        if text:
            r.setdefault("talk", []).append({"who": "me", "text": "改：" + text})
        self.img_generate(r["id"], text)

    def img_discuss(self):
        """问问模型：用旋钮选的那个模型，把你的不满意改写成一整段新提示词（它看不到图，只看文字）"""
        r = self.img_cur()
        text = self.entry.get().strip()
        sid = r.get("sid") if (r and self.session(r.get("sid"))) else self.state["sid"]
        if not r or not text:
            self.flash("先在输入框写你哪里不满意，再点「问模型」")
            return
        if not self.session(sid):
            self.flash("没有开着的对话帮忙问")
            return
        self.img_prompt_saved()
        extra = ("用户在调一张 AI 生成的图（你看不到图，只能根据文字判断）。现在的提示词：\n" + r["prompt"] +
                 ("\n之前提过的修改意见：" + "；".join(r["feedback"]) if r["feedback"] else "") +
                 "\n根据用户这次说的不满意，先用一两句话说你打算怎么改，然后另起一行写「【新提示词】」，后面跟一整段改好的完整提示词（中文，能直接交给生图 AI）。")
        qid = self.ask_model(sid, text, extra, [])
        r.setdefault("talk", []).append({"who": "me", "text": text})
        self.entry.delete(0, "end")
        self.img_ask = (qid, sid, time.time(), r["id"])
        self.save()
        self.render_img()

    def img_ask_main(self):
        """请主对话看图：主对话的 Claude 能看图，对着参考图和这几版想好新提示词，用工具推回提示词卡（用户 2026-10-15 选的）"""
        r = self.img_cur()
        if not r:
            self.flash("还没有生图请求")
            return
        if not self.session(r.get("sid")):
            self.flash("要这张图的那个对话没开；先打开它")
            return
        self.img_prompt_saved()
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        vs = [v for v in r["versions"] if not v.get("gone")]
        pick = r.get("pick")
        chosen = r["versions"][pick]["path"] if isinstance(pick, int) and 0 <= pick < len(r["versions"]) else (vs[-1]["path"] if vs else "")
        lines = [f"（克讲机）请帮我看图改提示词（生图请求编号 {r['id']}，「{r.get('title') or ''}」）。"]
        if r.get("refs"):
            lines.append("参考图：" + "；".join(r["refs"]))
        if chosen:
            lines.append("我现在选中的这一版：" + chosen)
        others = [v["path"] for v in vs if v["path"] != chosen][-3:]
        if others:
            lines.append("其他几版：" + "；".join(others))
        lines.append("现在的提示词：" + r["prompt"])
        if r["feedback"]:
            lines.append("我之前提过的意见：" + "；".join(r["feedback"]))
        lines.append("我这次的想法：" + (text or "你看着办，对照参考图找出最不像的地方"))
        lines.append(f"请用 Read 看这些图，对比后用一两句话告诉我问题在哪，再用工具 mcp__clawkie__image_prompt（id 写 {r['id']}）把完整的新提示词推回克讲机。只推到卡上，我会自己点「再来一轮」。")
        if text:
            r.setdefault("talk", []).append({"who": "me", "text": "请主对话看图：" + text})
        self.tell("\n".join(lines), "", "send", sid=r["sid"])
        self.save()
        self.render_img()

    def img_use(self):
        r = self.img_cur()
        if not r or not r["versions"]:
            self.flash("还没有图可以用")
            return
        i = r.get("pick", len(r["versions"]) - 1)
        src = r["versions"][i]["path"]
        name = r.get("saveAs") or f"image-{r['id'][:8]}.png"
        folder = r.get("saveTo") or os.path.join(IMAGES, r["id"])
        try:
            os.makedirs(folder, exist_ok=True)
            dst = os.path.join(folder, name)
            shutil.copyfile(src, dst)
        except OSError as ex:
            self.flash(f"存不进去：{ex}")
            return
        r["final"] = dst
        self.save()
        fb = "；".join(r["feedback"]) or "没改"
        text = (f"（克讲机生图台定稿）「{r.get('title') or ''}」：图在 {dst}（第 {i + 1} 版；最后用的提示词：{short(r['prompt'], 120)}；"
                f"用户提过的修改：{fb}）。请接着用这张图往下做。")
        self.root.clipboard_clear()
        self.root.clipboard_append(dst)
        if r.get("sid") and self.session(r["sid"]):
            self.tell(text, "", "note", sid=r["sid"])  # 用户 2026-10-15：不要为这个在主对话开一轮
        self.flash(f"存好了：{short(dst, 40)}（路径已复制）")

    # ================= 桌宠、窗口 =================
    def notice(self, text):
        write_json(NOTICE, {"id": new_id(), "text": text, "at": time.time()})

    def flash(self, msg):
        self.flash_msg, self.flash_until = msg, time.time() + 4
        self.draw_overlay()
        self.root.after(4100, self.draw_overlay)

    def model_label(self):
        s = self.state
        if s["model"] == "custom":
            return s["customModel"] or "自己填的"
        return dict(MODELS).get(s["model"], s["model"])

    def place(self, near):
        s, r = self.state, self.root
        w, h = int(s["w"] or 440 * self.k), int(s["h"] or 700 * self.k)
        w, h = max(w, int(MIN_W * self.k)), max(h, int(MIN_H * self.k))
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        if near:
            px, py, pw, ph = near
            x = px - w - 8 if px - w - 8 > 0 else px + pw + 8
            y = py + ph - h
        elif s["x"] is not None:
            x, y = s["x"], s["y"]
        else:
            x, y = sw - w - 60, sh - h - 120
        x = max(0, min(int(x), sw - w))
        y = max(0, min(int(y), sh - h - 40))
        r.geometry(f"{w}x{h}+{x}+{y}")
        r.update_idletasks()

    def hide(self):
        if self.dictating:
            self.talk_stop()
        self.save()
        self.root.withdraw()

    def show(self, near):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
        self.root.update_idletasks()
        if near:
            self.place(near)
        self.root.lift()
        self.root.wm_attributes("-topmost", True)
        self.refresh_sessions()
        self.render()
        self.refresh_screen()
        self.root.after(50, self.entry.focus_force)

    def save(self):
        r = self.root
        if r.state() != "withdrawn":
            self.state.update(x=r.winfo_x(), y=r.winfo_y(), w=r.winfo_width(), h=r.winfo_height())
        write_json(STATE, self.state)

    def quit(self):
        self.save()
        try:
            os.remove(ALIVE)
        except OSError:
            pass
        self.root.destroy()

    def _mtime(self, path):
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0

    def beat(self):
        write_json(ALIVE, {"pid": os.getpid(), "at": time.time()})
        self.root.after(1000, self.beat)

    def poll_show(self):
        """桌宠叫我：双击 = 出来；长按 = 出来并开始说话，松手 = 停"""
        m = self._mtime(SHOW)
        if m != self.show_mtime:
            self.show_mtime = m
            d = read_json(SHOW, {})
            d = d if isinstance(d, dict) else {}
            talk = d.get("talk")
            if talk == "stop":
                self.talk_stop()
            else:
                self.show(d.get("near"))
                if d.get("mode") in MODE_ARG:
                    self.set_mode(MODE_ARG[d["mode"]])
                if talk == "start":
                    self.talk_t0 = time.time()
                    self.talk_start()
        self.root.after(300, self.poll_show)


MODE_ARG = {"chat": 0, "memo": 1, "paint": 2}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--near", type=int, nargs=4, metavar=("X", "Y", "W", "H"), help="放在这个窗口（桌宠）旁边")
    p.add_argument("--talk", choices=["start", "stop"], help="桌宠长按：开始 / 停止说话")
    p.add_argument("--mode", choices=list(MODE_ARG), help="打开就拨到这一档（桌宠点脚下的待办 = memo）")
    a = p.parse_args()
    write_card()
    alive = read_json(ALIVE, {})
    if isinstance(alive, dict) and time.time() - (alive.get("at") or 0) < 3:
        write_json(SHOW, {"at": time.time(), "near": a.near, "talk": a.talk, "mode": a.mode})
        return
    if a.talk == "stop":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    t = Talkie(a.near, talk=a.talk == "start")
    if a.mode:
        t.set_mode(MODE_ARG[a.mode])
    t.root.mainloop()


if __name__ == "__main__":
    main()
