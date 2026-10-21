// 克讲机 Clawkie — made by Miaomiao (https://github.com/Miaomiaomeowmeow) · CC BY-NC-SA 4.0
// 对讲机 → 克讲机：Claude 桌面应用旁边的小聊天窗 / 对讲机的插件那一半。
// 用便宜的模型回答，只带当前对话最后几句；它说的话不进主对话。
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Line, Settings } from '../types'

const PANE = 'clawkie'
const TITLE = '克讲机 Clawkie'

const DEFAULTS: Settings = { model: 'haiku', customModel: '', ctxCount: 6, perChars: 800 }

const lines = atom({ plugin: 'clawkie', key: 'lines' } as const, [])
const settings = atom({ plugin: 'clawkie', key: 'settings' } as const, DEFAULTS)
const draft = atom({ plugin: 'clawkie', key: 'draft' } as const, '')
const busy = atom({ plugin: 'clawkie', key: 'busy' } as const, false)
const tick = atom({ plugin: 'clawkie', key: 'tick' } as const, 0)
const sent = atom({ plugin: 'clawkie', key: 'sent' } as const, 0)
const bridge = atom({ plugin: 'clawkie', key: 'bridge' } as const, { askId: '', tellId: '', label: '', est: {}, active: 0, lastImg: '', notes: [] as string[] })

const MODELS = [
  { value: 'haiku', label: 'Haiku 5.5' },
  { value: 'sonnet', label: 'Sonnet 5.5' },
  { value: 'opus', label: 'Opus 5.5' },
  { value: 'claude-fable-5-1', label: 'Fable 5.1' },
  { value: 'custom', label: '自己填…' },
]
// 带几句、每句几字的选项（对讲机里也是这几个，改了两边一起改）
const COUNT_STEPS = [2, 4, 6, 10, 15, 20, 30, 50]
const CHAR_STEPS = [200, 500, 800, 1500, 3000, 0]
// 「不截」也设个上限，防止一句特别长的塞爆
const NO_CUT = 20000
const COUNTS = [0, ...COUNT_STEPS].map(n => ({
  value: String(n),
  label: n === 0 ? '不带对话（纯闲聊）' : `最后 ${n} 句`,
}))
const CHARS = CHAR_STEPS.map(n => ({ value: String(n), label: n === 0 ? '每句不截' : `每句最多 ${n} 字` }))

// 小窗自己的聊天记录只带最近几句
const HISTORY = 6
// 面板里最多显示几句，再早的收起来
const SHOWN = 8

// 用户 2026-10-15：“非常笨，即使是用同样的模型还是很笨” → 以前叫它“简短直接、多半是小事”，又只给 2000 字、不让想
const SYSTEM = [
  '你是「克讲机 Clawkie」：用户桌面上一台对讲机里的 Claude，跟主对话里的 Claude 一样聪明，只是没带主对话的全部内容。',
  '用户正在另一个对话里和 Claude 一起做事；如果附了那个对话的最后几句，只是给你参考，可能被截断了。不知道的就说不知道，或者先问清楚。',
  '先想清楚再答：简单的问题简短答，要比较、要步骤、要想法的就认真展开，给理由和具体做法。用中文，讲简单（用户不是技术专家）。',
  '你不能改文件、不能操作电脑。用户满意了会自己点按钮，把你的话转给主对话或新开一个对话去做，所以把结论说清楚、能直接拿去用。',
].join('\n')

// 能上网：模型整条回复只写一行【搜索】/【打开】，插件去查，再把结果交回给它（最多 WEB_STEPS 次）
const WEB_STEPS = 4
const WEB_RULES = [
  '你可以上网。需要最新的、你不确定的、或用户要你查的东西时，整条回复只写下面其中一行，别的什么都不写：',
  '【搜索】关键词　——　用必应搜，会给你前几条的标题、网址、摘要',
  '【打开】网址　——　读这个网页的正文',
  `最多查 ${WEB_STEPS} 次。查到了就正常回答，最后列出用到的网址。不需要查就直接回答。`,
].join('\n')
const EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max'] as const
type Effort = (typeof EFFORTS)[number]
/** 想得越认真，留的字数越多（思考也占字数） */
const MAX_TOKENS: Record<Effort, number> = { low: 4000, medium: 8000, high: 16000, xhigh: 32000, max: 32000 }
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'

function unhtml(t: string): string {
  return t
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;|&ensp;|&emsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#0?39;|&#x27;/g, "'")
    .replace(/&#(\d+);/g, (_m, n) => String.fromCodePoint(Number(n)))
}

/** 必应的结果链接是跳转地址，真网址在 u=a1<base64> 里 */
function bingTarget(href: string): string {
  const m = /[?&]u=a1([^&]+)/.exec(href)
  if (!m) return href
  // 自己解 base64（不靠 atob / TextDecoder，插件里不一定有）
  const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
  const bytes: string[] = []
  let buf = 0
  let bits = 0
  for (const ch of (m[1] ?? '').replace(/\+/g, '-').replace(/\//g, '_')) {
    const v = A.indexOf(ch)
    if (v < 0) continue
    buf = ((buf << 6) | v) & 0xffffff
    bits += 6
    if (bits >= 8) {
      bits -= 8
      bytes.push('%' + ((buf >> bits) & 255).toString(16).padStart(2, '0'))
    }
  }
  try {
    return decodeURIComponent(bytes.join(''))
  } catch {
    return href
  }
}

async function webSearch($: EngineInterface, q: string): Promise<string> {
  const r = await $.http.fetch(`https://www.bing.com/search?q=${encodeURIComponent(q)}`, {
    headers: { 'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8' },
  })
  if (!r.ok) return `搜索没成功（${r.status}）`
  const out: string[] = []
  for (const blk of r.text.match(/<li class="b_algo"[\s\S]*?<\/li>/g) ?? []) {
    const a = /<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/.exec(blk)
    if (!a) continue
    const p = /<p[^>]*>([\s\S]*?)<\/p>/.exec(blk)
    const [, href = '', title = ''] = a
    const snip = p?.[1] ?? ''
    out.push(`${out.length + 1}. ${unhtml(title).trim()}\n   ${bingTarget(unhtml(href))}\n   ${unhtml(snip).trim().slice(0, 220)}`)
    if (out.length >= 8) break
  }

  return out.length ? out.join('\n') : '没搜到东西，换个关键词试试。'
}

async function webOpen($: EngineInterface, url: string): Promise<string> {
  if (!/^https?:\/\//.test(url)) return '网址要以 http:// 或 https:// 开头'
  const r = await $.http.fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8' } })
  if (!r.ok) return `打不开（${r.status}）`
  const body = unhtml(
    r.text
      .replace(/<(script|style|noscript|svg|head|nav|footer)[\s\S]*?<\/\1>/gi, ' ')
      .replace(/<(br|\/p|\/div|\/li|\/h\d|\/tr)[^>]*>/gi, '\n'),
  )
    .replace(/[ \t]+/g, ' ')
    .replace(/\n\s*\n+/g, '\n')
    .trim()

  return body.length > 8000 ? `${body.slice(0, 8000)}\n…（后面太长，省略了）` : body || '网页里没读到文字'
}

/** 粗估 token：中文大约一个字一个，英文大约 3.5 个字母一个 */
function estimate(text: string): number {
  let cjk = 0
  let other = 0
  for (const ch of text) {
    if (/[⺀-鿿가-힯＀-￯　-〿]/.test(ch)) cjk++
    else other++
  }
  return Math.ceil(cjk * 1.1 + other / 3.5)
}

function fmt(n: number): string {
  return n < 1000 ? String(n) : `${(n / 1000).toFixed(1)}k`
}

/** 去掉对话里系统塞进去的提醒，只留人说的话 */
function clean(text: string): string {
  return text
    .replace(/<system-reminder>[\s\S]*?<\/system-reminder>/g, '')
    .replace(/<\/?(command-[a-z-]+|local-command-[a-z-]+)>/g, '')
    .trim()
}

/** 太长的留开头和结尾，中间省略 */
function cut(text: string, max: number): string {
  if (max <= 0) max = NO_CUT
  const chars = Array.from(text)
  if (chars.length <= max) return text
  const head = Math.round(max * 0.6)
  const tail = max - head

  return `${chars.slice(0, head).join('')} …（中间省略）… ${chars.slice(-tail).join('')}`
}

type Said = { role: 'user' | 'assistant'; text: string }

/** 对话里人说的话（去掉没字的、系统提醒） */
async function saidSoFar($: EngineInterface): Promise<Said[]> {
  const all = await $.session.messages()
  if (!Array.isArray(all)) return []

  return all.map(m => ({ role: m.role, text: clean(m.text) })).filter(m => m.text !== '')
}

async function contextText($: EngineInterface, s: Settings): Promise<string> {
  if (s.ctxCount === 0) return ''

  return contextFrom(await saidSoFar($), s)
}

function contextFrom(said: readonly Said[], s: Settings): string {
  if (s.ctxCount === 0) return ''

  return said
    .slice(-s.ctxCount)
    .map(m => `[${m.role === 'user' ? '用户' : 'Claude'}] ${cut(m.text, s.perChars)}`)
    .join('\n\n')
}

function historyText(list: readonly Line[]): string {
  return list
    .filter(l => !l.isError)
    .slice(-HISTORY)
    .map(l => `[${l.who === 'me' ? '用户' : '你'}] ${l.text}`)
    .join('\n\n')
}

function buildPrompt(ctx: string, hist: string, question: string): string {
  const parts: string[] = []
  if (ctx) parts.push(`<主对话最后几句>\n${ctx}\n</主对话最后几句>`)
  if (hist) parts.push(`<小窗里之前聊的>\n${hist}\n</小窗里之前聊的>`)
  parts.push(`用户现在问：${question}`)

  return parts.join('\n\n')
}

function modelLabel(s: Settings): string {
  if (s.model === 'custom') return s.customModel.trim() || '（没填模型名）'

  return MODELS.find(m => m.value === s.model)?.label ?? s.model
}

async function saveSettings($: EngineInterface, change: Partial<Settings>) {
  const next = await update($, settings, s => ({ ...DEFAULTS, ...s, ...change }))
  await $.store.set('settings', next)
}

async function send($: EngineInterface, raw: string) {
  const question = raw.trim()
  if (question === '' || (await read($, busy))) return

  const s = { ...DEFAULTS, ...(await read($, settings)) }
  const model = s.model === 'custom' ? s.customModel.trim() : s.model
  const before = await read($, lines)

  await update($, lines, (l): Line[] => [...l, { who: 'me', text: question }])
  await update($, draft, () => '')
  await update($, sent, n => n + 1)

  if (model === '') {
    await update($, lines, (l): Line[] => [...l, { who: 'ai', text: '先在「自己填」里写上模型名。', isError: true }])
    return
  }

  await update($, busy, () => true)
  try {
    const line = await ask($, model, modelLabel(s), await contextText($, s), historyText(before), question)
    await update($, lines, l => [...l, line].slice(-100))
  } finally {
    await update($, busy, () => false)
  }
}

/** 问一次模型，答案（或出错的原因）变成一句话 */
type AskOpts = { effort?: string; web?: boolean; progress?: (text: string) => Promise<void> }
const EFFORT_LABEL: Record<Effort, string> = { low: '快', medium: '一般', high: '认真', xhigh: '很认真', max: '最认真' }

async function ask(
  $: EngineInterface,
  model: string,
  label: string,
  ctx: string,
  hist: string,
  question: string,
  extra = '',
  opts: AskOpts = {},
): Promise<Line> {
  try {
    const effort: Effort = (EFFORTS as readonly string[]).includes(opts.effort ?? '') ? (opts.effort as Effort) : 'high'
    const web = opts.web ?? true
    const today = new Date().toISOString().slice(0, 10)
    let system = `${SYSTEM}\n今天是 ${today}。`
    if (web) system += `\n\n${WEB_RULES}`
    if (extra) system += `\n\n这次照下面的规矩回答：\n${extra}`
    let prompt = buildPrompt(ctx, hist, question)
    let used = 0
    let looked = 0
    for (;;) {
      const r = await $.model.complete({ model, system, prompt, effort, maxTokens: MAX_TOKENS[effort], timeoutMs: 300000 })
      const u = r.usage
      used += u ? u.input_tokens + u.output_tokens + u.cache_read_input_tokens + u.cache_creation_input_tokens : 0
      if (!r.isAnswered) {
        if (r.reason === 'api-error') {
          return { who: 'ai', text: `出错了（${r.error}${r.status ? ` ${r.status}` : ''}），等一下再试。`, isError: true }
        }
        if (r.reason === 'empty-reply') return { who: 'ai', text: '它没说话，换个问法试试。', isError: true }

        return { who: 'ai', text: '等太久了，没等到回答。', isError: true }
      }
      const reply = r.text.trim()
      const go = web && looked < WEB_STEPS && reply.split('\n').length <= 2 ? /^【(搜索|打开)】\s*(.+)$/m.exec(reply) : null
      if (!go) {
        const how = `${label} · ${EFFORT_LABEL[effort]}${looked ? ` · 上网查了 ${looked} 次` : ''}`

        return { who: 'ai', text: r.text, note: `用了 ${fmt(used)} token · ${how}` }
      }
      looked++
      const what = (go[2] ?? '').trim()
      await opts.progress?.(go[1] === '搜索' ? `在搜：${what}` : `在看：${what}`)
      let found: string
      try {
        found = go[1] === '搜索' ? await webSearch($, what) : await webOpen($, what)
      } catch (err) {
        found = `没查成：${err instanceof Error ? err.message : String(err)}`
      }
      prompt += `\n\n[你刚才] 【${go[1]}】${what}\n<结果>\n${found}\n</结果>\n（还要查就再只写一行【搜索】/【打开】；够了就直接回答用户。）`
    }
  } catch (err) {
    const why = err instanceof Error ? err.message : String(err)

    return { who: 'ai', text: `这个模型用不了：${why}`, isError: true }
  }
}

// ---------- 对讲机（桌宠旁边能拖的小窗）----------
// 对讲机是电脑上另一个小程序，和这里靠几个小文件说话，都放在 ~/.claude/clawkie-bridge/：
//   live-<对话>.json   这里每 3 秒写一次：我在线、叫什么、带几句大约多少 token
//   ask-<对话>.json    对讲机写：问题 + 设置 + 小窗里之前聊的
//   answer-<对话>.json 这里写：答案
//   tell-<对话>.json   对讲机写：认可的答案，这里放进主对话的输入框

type Ask = {
  id: string
  text: string
  model: string
  label?: string
  ctxCount: number
  perChars: number
  history?: { who: 'me' | 'ai'; text: string }[]
  /** 常用功能的规矩（例：取名字），加在说明后面 */
  extra?: string
  /** 想得多认真：low / medium / high / xhigh / max（没写 = high） */
  effort?: string
  /** 能不能上网（没写 = 能） */
  web?: boolean
}
/** fill = 放进输入框；send = 直接发给对话；new = 新开一个对话去做 */
/** note = 不打扰：记成小纸条，用户下次在这个对话说话时顺带告诉 Claude（用户 2026-10-15：克讲机的意义就是不用在主对话里来回） */
type Tell = { id: string; text: string; mode?: 'fill' | 'send' | 'new' | 'note'; title?: string; background?: string }

const COMBOS = COUNT_STEPS.flatMap(n => CHAR_STEPS.map(c => [n, c] as const))

async function bridgeDir($: EngineInterface): Promise<string> {
  const home = (await $.env.get('USERPROFILE')) ?? (await $.env.get('HOME')) ?? '.'

  return `${home.replace(/\\/g, '/')}/.claude/clawkie-bridge`
}

async function readJson<T>($: EngineInterface, path: string): Promise<T | undefined> {
  try {
    if (!(await $.fs.exists(path))) return undefined

    return JSON.parse(await $.fs.read(path)) as T
  } catch {
    return undefined
  }
}

/** 给对讲机看的名字：文件夹名 + 第一句话开头 */
async function sessionLabel($: EngineInterface): Promise<string> {
  const cwd = (await $.session.cwd()).replace(/\\/g, '/')
  const folder = cwd.split('/').filter(Boolean).pop() ?? cwd
  const all = await $.session.messages()
  const first = Array.isArray(all) ? all.find(m => m.role === 'user' && clean(m.text) !== '') : undefined
  const head = first ? Array.from(clean(first.text).replace(/\s+/g, ' ')).slice(0, 16).join('') : '新对话'

  return `${folder} · ${head}`
}

/** 各种「带几句 × 每句几字」大约多少 token，对讲机拿来显示预估 */
async function estimates($: EngineInterface): Promise<Record<string, number>> {
  const out: Record<string, number> = {}
  const said = await saidSoFar($)
  for (const [ctxCount, perChars] of COMBOS) {
    const ctx = contextFrom(said, { ...DEFAULTS, ctxCount, perChars })
    out[`${ctxCount}-${perChars}`] = ctx ? estimate(ctx) : 0
  }

  return out
}

async function heartbeat($: EngineInterface, ended = false) {
  const dir = await bridgeDir($)
  const sid = await $.session.id()
  const prev = await read($, bridge)
  const info = {
    sid,
    label: prev.label,
    cwd: await $.session.cwd(),
    est: prev.est,
    active: prev.active,
    at: await $.clock.now(),
    ended,
  }
  await $.fs.write(`${dir}/live-${sid}.json`, JSON.stringify(info))
}

async function refreshInfo($: EngineInterface) {
  const label = await sessionLabel($)
  const est = await estimates($)
  const active = await $.clock.now()
  await update($, bridge, b => ({ ...b, label, est, active }))
}

async function serveBridge($: EngineInterface) {
  const dir = await bridgeDir($)
  const sid = await $.session.id()
  const done = await read($, bridge)

  const q = await readJson<Ask>($, `${dir}/ask-${sid}.json`)
  if (q && q.id && q.id !== done.askId) {
    await update($, bridge, b => ({ ...b, askId: q.id }))
    const answered = await readJson<{ id: string }>($, `${dir}/answer-${sid}.json`)
    if (answered?.id !== q.id) {
      const s = { ...DEFAULTS, ctxCount: q.ctxCount, perChars: q.perChars }
      const hist = historyText((q.history ?? []).map(h => ({ who: h.who, text: h.text })))
      // 上网时把“在搜什么”写给对讲机看，不然它只看到“在想……”干等
      const progress = async (text: string) => {
        await $.fs.write(`${dir}/progress-${sid}.json`, JSON.stringify({ id: q.id, text }))
      }
      const line = q.model
        ? await ask($, q.model, q.label ?? q.model, await contextText($, s), hist, q.text, q.extra ?? '', {
            effort: q.effort,
            web: q.web,
            progress,
          })
        : { who: 'ai' as const, text: '先在设置里选一个模型。', isError: true }
      await $.fs.write(`${dir}/answer-${sid}.json`, JSON.stringify({ id: q.id, ...line }))
    }
  }

  const t = await readJson<Tell>($, `${dir}/tell-${sid}.json`)
  if (t && t.id && t.id !== done.tellId) {
    await update($, bridge, b => ({ ...b, tellId: t.id }))
    // 交过的不再交：插件重装 / 换版本后自己的记录是空的，要看 told 文件（2026-10-15 长期版装上后把一条旧定稿又发了一遍）
    const told0 = await readJson<{ id: string }>($, `${dir}/told-${sid}.json`)
    if (told0?.id !== t.id) {
      const told = await tell($, t)
      await $.fs.write(`${dir}/told-${sid}.json`, JSON.stringify({ id: t.id, ...told }))
    }
  }
}

// ---------- 生图台：主对话的 Claude 要出图时交给对讲机 ----------
// 对讲机用 Codex 生图，用户在那里看、提意见、再生，满意了把定稿路径用「直接发」送回这个对话

const IMAGE_TOOL = 'mcp__clawkie__image'
const IMAGE_SPEC = {
  name: 'image',
  description: [
    '把要生成的图交给用户桌面上的「克讲机 · 生图台」。它用 Codex 生图，用户在那里看图、提意见、反复改，',
    '满意后会把定稿图的路径发回这个对话（以「（克讲机生图台定稿）」开头的消息）。交出去以后你接着做别的，不用等。',
    '用户要求：对讲机开着时，要生图一律先交给它；对讲机没开时本工具会直接告诉你，那时照常自己用 Codex 生图。',
  ].join(''),
  inputSchema: {
    type: 'object',
    properties: {
      title: { type: 'string', description: '一句话说这是什么图（例：咖啡店贴纸），对讲机上显示' },
      prompt: { type: 'string', description: '生图提示词原文' },
      refs: { type: 'array', items: { type: 'string' }, description: '参考图的绝对路径（可以没有）' },
      saveTo: { type: 'string', description: '定稿存到哪个文件夹（绝对路径）' },
      saveAs: { type: 'string', description: '定稿的英文文件名，例 cover.png' },
    },
    required: ['title', 'prompt'],
  },
}

type ImageAsk = { title?: string; prompt?: string; refs?: string[]; saveTo?: string; saveAs?: string }

async function talkieAlive($: EngineInterface): Promise<boolean> {
  const alive = await readJson<{ at?: number }>($, `${await bridgeDir($)}/talkie-alive.json`)

  return !!alive?.at && (await $.clock.now()) / 1000 - alive.at < 6
}

async function handOverImage($: EngineInterface, req: ImageAsk): Promise<string> {
  if (!req.prompt) return '没写提示词（prompt），没交出去。'
  if (!(await talkieAlive($))) return '克讲机现在没开，没交出去。请照常自己用 Codex 生图。'
  const dir = await bridgeDir($)
  const id = `${Math.round(await $.clock.now())}`
  const info = await read($, bridge)
  await $.fs.write(
    `${dir}/img-req-${id}.json`,
    JSON.stringify({
      id,
      sid: await $.session.id(),
      label: info.label,
      title: req.title ?? '',
      prompt: req.prompt,
      refs: req.refs ?? [],
      saveTo: req.saveTo ?? '',
      saveAs: req.saveAs ?? '',
      at: await $.clock.now(),
    }),
  )

  await update($, bridge, b => ({ ...b, lastImg: id }))

  return `已交给克讲机生图台：「${req.title ?? ''}」（请求编号 ${id}）。用户改到满意后会把定稿路径发回来，你先接着做别的。`
}

// 改提示词：对话里定了新提示词（用户说“改成 XX”，或你看图后想好了），推到克讲机的提示词卡上，不用用户复制
// 只是摆在卡上，用户看过点「再来一轮」才生（用户 2026-10-15 选的）
const PROMPT_TOOL = 'mcp__clawkie__image_prompt'
const PROMPT_SPEC = {
  name: 'image_prompt',
  description: [
    '把新的生图提示词推到用户桌面「克讲机 · 画档」的提示词卡上（替换某个生图请求的提示词），用户不用复制。',
    '用户在对话里说要改某张图、或者你看完图想好了怎么改提示词时用。只摆在卡上，用户点「再来一轮」才会照它生。',
    '写完整的新提示词（不是只写改动），note 用一句话说改了什么。',
  ].join(''),
  inputSchema: {
    type: 'object',
    properties: {
      id: { type: 'string', description: '生图请求编号（克讲机发来的消息里有）；不写 = 这个对话最近交过去的那个' },
      prompt: { type: 'string', description: '完整的新提示词' },
      note: { type: 'string', description: '一句话说改了什么（例：小克画大一点、透明底）' },
    },
    required: ['prompt'],
  },
}

type PromptPush = { id?: string; prompt?: string; note?: string }

async function pushPrompt($: EngineInterface, req: PromptPush): Promise<string> {
  if (!req.prompt) return '没写新提示词（prompt），没推过去。'
  const info = await read($, bridge)
  const rid = req.id || info.lastImg
  if (!rid) return '不知道要改哪个生图请求：请写上请求编号 id（克讲机发来的消息里有）。'
  const dir = await bridgeDir($)
  const now = Math.round(await $.clock.now())
  await $.fs.write(
    `${dir}/img-upd-${rid}-${now}.json`,
    JSON.stringify({ rid, prompt: req.prompt, note: req.note ?? '', from: info.label, at: now }),
  )
  const alive = await talkieAlive($)

  return `新提示词已经摆到克讲机的提示词卡上了（请求 ${rid}）${alive ? '' : '（克讲机现在没开，打开后就能看到）'}。用户点「再来一轮」才会照它生。`
}

/** 把对讲机里认可的话交出去：放进输入框 / 直接发 / 新开对话 */
async function tell($: EngineInterface, t: Tell): Promise<{ ok: boolean; msg: string }> {
  const text = t.text.trim()
  if (t.mode === 'note') {
    await update($, bridge, b => ({ ...b, notes: [...(b.notes ?? []), text].slice(-10) }))
    $.ui.toast('克讲机：定稿存好了，下次你在这个对话说话时会顺带告诉 Claude')

    return { ok: true, msg: '存好了；不打扰对话，下次你在那边说话时会顺带告诉它' }
  }
  if (t.mode === 'send') {
    // 生图台定稿自己带了「（克讲机生图台定稿）」开头，不再加
    await $.prompt.submit({ text: text.startsWith('（唠嗑') || text.startsWith('（克讲机') ? text : `（克讲机里定的）${text}` })

    return { ok: true, msg: '发给对话了，它会接着做' }
  }
  if (t.mode === 'new') {
    const title = (t.title ?? '').trim() || Array.from(text.replace(/\s+/g, ' ')).slice(0, 24).join('')
    const from = (await read($, bridge)).label
    const background = [
      (t.background ?? '').trim(),
      `这是用户在「克讲机」小聊天窗里和便宜模型聊好的想法，现在新开一个对话把它做出来。聊的时候开着的对话是：${from}。`,
      '用户不是技术专家：用中文，讲简单。',
    ]
      .filter(Boolean)
      .join('\n')
    try {
      // 应用自带的「开新对话」工具，和 Claude 开任务卡用的是同一个
      await $.mcp.call('ccd_session', 'start_session', {
        initiation: 'user_asked',
        title,
        prompt: text,
        context: 'fresh',
        background,
      })

      return { ok: true, msg: `新开了一个对话：${title}` }
    } catch {
      // 开不了就请主对话帮忙开
      await $.prompt.submit({
        text: `（克讲机里定的）请帮我新开一个对话（start_session，initiation 用 user_asked）去做这件事，标题「${title}」：\n${text}`,
      })

      return { ok: true, msg: '请主对话帮你新开了' }
    }
  }
  const box = await $.prompt.read()
  const gap = box.text.trim() === '' ? '' : '\n\n'
  await $.prompt.fill({ text: `${gap}（克讲机里认可的）${text}`, mode: 'append' })
  $.ui.toast('克讲机的答案放进输入框了，看一眼再发')

  return { ok: true, msg: '放进对话的输入框了，回去看一眼再发' }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const saved = await $.store.get('settings')
    if (saved && typeof saved === 'object') {
      await update($, settings, () => ({ ...DEFAULTS, ...(saved as Partial<Settings>) }))
    }
    await $.command.register({ name: 'clawkie', description: '在应用里打开克讲机小窗（平时双击桌宠就行）' })
    await $.tool.register(IMAGE_SPEC)
    await $.tool.register(PROMPT_SPEC)

    // 对讲机：先报到，之后每 3 秒报一次在线，每 0.7 秒看有没有新问题
    await refreshInfo($)
    await heartbeat($)
    $.clock.every(3000, () => void heartbeat($))
    let serving = false
    $.clock.every(700, async () => {
      if (serving) return
      serving = true
      try {
        await serveBridge($)
      } finally {
        serving = false
      }
    })

    return next(e)
  })

  // 你在这个对话里发了消息：告诉桌宠小克（它会看这个对话还欠着哪些备忘，跑来提醒）
  on('prompt.submit', async ($, e, next) => {
    // 克讲机留的小纸条（例：生图定稿存在哪），跟着用户这句话一起给 Claude，不单独开一轮
    const notes = (await read($, bridge)).notes ?? []
    if (notes.length > 0) {
      await update($, bridge, b => ({ ...b, notes: [] }))
      e = { ...e, context: [...(e.context ?? []), ...notes.map(n => `克讲机留言：${n}`)] }
    }
    if (!e.text.startsWith('（唠嗑') && !e.text.startsWith('（克讲机')) {
      try {
        const info = await read($, bridge)
        await $.fs.write(
          `${await bridgeDir($)}/focus.json`,
          JSON.stringify({ sid: await $.session.id(), label: info.label, at: (await $.clock.now()) / 1000 }),
        )
      } catch {
        // 写不进去就算了，不挡着发消息
      }
    }

    return next(e)
  })

  on('tool.call', { tool: PROMPT_TOOL }, async ($, e) => {
    return { result: await pushPrompt($, e as unknown as PromptPush) }
  })

  on('tool.call', { tool: IMAGE_TOOL }, async ($, e) => {
    const input = e as unknown as ImageAsk

    return { result: await handOverImage($, input) }
  })

  on('session.end', async ($, e, next) => {
    await heartbeat($, true)

    return next(e)
  })

  on('command.run', { command: 'clawkie' }, async $ => {
    await $.ui.open({ id: PANE, title: TITLE, focus: true })

    return { text: '克讲机小窗打开了。' }
  })

  // 主对话每说完一轮，预估重新算
  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (e.agentId === undefined) {
      await update($, tick, n => n + 1)
      await refreshInfo($)
    }

    return done
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    // 手机上没有输入框和下拉框
    if (e.surface === 'mobile') {
      const { Text } = $.ui.resolve(e)

      return <Text dimColor>手机上打不了字，回电脑上用克讲机吧。</Text>
    }
    const { Box, Text, Button, Input, Select, Markdown } = $.ui.resolve(e)
    await read($, tick)
    const list = await read($, lines)
    const s = { ...DEFAULTS, ...(await read($, settings)) }
    const text = await read($, draft)
    const thinking = await read($, busy)
    const n = await read($, sent)

    const ctx = await contextText($, s)
    const hist = historyText(list)
    const a = ctx ? estimate(ctx) : 0
    const b = hist ? estimate(hist) : 0
    const c = estimate(text)
    const total = a + b + c + estimate(SYSTEM) + 120
    const shown = list.slice(-SHOWN)
    const hidden = list.length - shown.length

    return (
      <Box flexDirection="column" gap={1}>
        <Box flexDirection="row" justifyContent="space-between">
          <Text bold>{TITLE}</Text>
          <Button key="clear" dimColor onPress={() => void update($, lines, () => [])}>
            清空
          </Button>
        </Box>

        {list.length === 0 && (
          <Text dimColor>取名字、查个词、随口问一句都行。主对话的 AI 看不到这里。</Text>
        )}
        {hidden > 0 && <Text dimColor>（前面还有 {hidden} 句，收起来了）</Text>}
        {shown.map(l =>
          l.who === 'me' ? (
            <Text bold>你：{l.text}</Text>
          ) : l.isError ? (
            <Text color="red">{l.text}</Text>
          ) : (
            <Box flexDirection="column">
              <Markdown text={l.text} />
              {l.note && <Text dimColor>{l.note}</Text>}
            </Box>
          ),
        )}
        {thinking && <Text dimColor>在想……</Text>}

        <Box flexDirection="row" flexWrap="wrap" columnGap={2}>
          <Select key="model" options={MODELS} value={s.model} onSelect={v => void saveSettings($, { model: v })} />
          <Select
            key="ctx"
            options={COUNTS}
            value={String(s.ctxCount)}
            onSelect={v => void saveSettings($, { ctxCount: Number(v) })}
          />
          {s.ctxCount > 0 && (
            <Select
              key="chars"
              options={CHARS}
              value={String(s.perChars)}
              onSelect={v => void saveSettings($, { perChars: Number(v) })}
            />
          )}
        </Box>
        {s.model === 'custom' && (
          <Input
            key="custom-model"
            label="模型名"
            placeholder="claude-sonnet-5-5"
            value={s.customModel}
            submitLabel="存"
            onSubmit={v => void saveSettings($, { customModel: v.trim() })}
          />
        )}
        <Input
          key={`ask-${n}`}
          placeholder="问点什么……"
          submitLabel="发送"
          autoFocus
          value={text}
          onInput={v => void update($, draft, () => v)}
          onSubmit={v => void send($, v)}
        />
        <Text dimColor>
          这次大约 {fmt(total)} token（对话 {fmt(a)} · 小窗记录 {fmt(b)} · 问题 {fmt(c)}）
        </Text>
      </Box>
    )
  })
}
