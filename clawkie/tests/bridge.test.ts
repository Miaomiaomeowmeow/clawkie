import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const DIR = 'C:/Users/me/.claude/clawkie-bridge'
const SID = 's1'
// Windows 上引擎会把路径里的 / 换成 \，假电脑也这样存
const ctxLog: string[][] = []
const norm = (p: string) => p.replace(/\//g, '\\')

// 假电脑：文件放在内存里；假对话：两句话；假模型：总回答同一句
function fakeComputer(on: On, files: Map<string, string>, filled: string[], asked: string[], sent: string[] = [], opened: unknown[] = [], ownModel = false) {
  mock.env(on, { USERPROFILE: 'C:\\Users\\me' })
  mock.store(on)
  on('session.id', async () => ({ value: SID }))
  on('session.cwd', async () => ({ value: 'D:/项目/小克助手' }))
  on('session.messages', async () => ({
    value: [
      { role: 'user', text: '帮我做个记账工具', toolUses: [] },
      { role: 'assistant', text: '好的，先搭框架', toolUses: [] },
    ],
  }))
  on('command.register', async () => ({ value: { isRegistered: true } }))
  on('fs.exists', async (_$, e) => ({ value: files.has(norm(e.path)) }))
  on('fs.read', async (_$, e) => ({ value: files.get(norm(e.path)) ?? '' }))
  on('fs.write', async (_$, e) => {
    files.set(norm(e.path), e.text)
    return { value: undefined }
  })
  if (!ownModel) on('model.complete', async (_$, e) => {
    asked.push(typeof e.prompt === 'string' ? e.prompt : '')
    return {
      value: {
        isAnswered: true,
        text: '叫「记记」吧',
        usage: { input_tokens: 200, output_tokens: 10, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 },
      },
    }
  })
  on('prompt.read', async () => ({ value: { text: '', cursor: 0 } }))
  on('prompt.fill', async (_$, e) => {
    filled.push(e.text)
    return { isFilled: true, box: { text: e.text, cursor: e.text.length } }
  })
  on('ui.toast', async () => ({ value: undefined }))
  on('session.start', async (_$, e) => ({ cwd: e.cwd }))
  on('tool.register', async (_$, e) => ({ value: { tool: `mcp__clawkie__${e.name}` } }))
  on('prompt.submit', async (_$, e) => {
    sent.push(e.text)
    ctxLog.push([...(e.context ?? [])])
    return { text: e.text }
  })
  on('mcp.call', async (_$, e) => {
    opened.push(e)
    return { value: { content: [{ type: 'text', text: 'ok' }] } }
  })
}

test('对讲机：报到、回答问题、把认可的答案放进输入框', async ($, on) => {
  const files = new Map<string, string>()
  const filled: string[] = []
  const asked: string[] = []
  fakeComputer(on, files, filled, asked)
  const clock = mock.clock(on)

  await $.session.start({ cwd: 'D:/项目/小克助手', surface: 'desktop', isInteractive: true })

  const live = JSON.parse(files.get(norm(`${DIR}/live-${SID}.json`)) ?? '{}')
  expect(live.label).toContain('小克助手')
  expect(live.label).toContain('帮我做个记账工具')
  expect(live.est['6-800']).toBeGreaterThan(0)

  files.set(
    norm(`${DIR}/ask-${SID}.json`),
    JSON.stringify({ id: 'q1', text: '取个名字', model: 'haiku', label: 'Haiku 5.5', ctxCount: 6, perChars: 800 }),
  )
  await clock.advance(800)
  const answer = JSON.parse(files.get(norm(`${DIR}/answer-${SID}.json`)) ?? '{}')
  expect(answer.id).toBe('q1')
  expect(answer.text).toBe('叫「记记」吧')
  expect(asked[0]).toContain('帮我做个记账工具')

  // 同一个问题不会再问一遍
  await clock.advance(800)
  expect(asked).toHaveLength(1)

  files.set(norm(`${DIR}/tell-${SID}.json`), JSON.stringify({ id: 't1', text: '名字定了：记记' }))
  await clock.advance(800)
  expect(filled).toHaveLength(1)
  expect(filled[0]).toContain('名字定了：记记')
})

test('对讲机：直接发给对话、新开对话去做', async ($, on) => {
  const files = new Map<string, string>()
  const sent: string[] = []
  const opened: unknown[] = []
  fakeComputer(on, files, [], [], sent, opened)
  const clock = mock.clock(on)
  await $.session.start({ cwd: 'D:/项目/小克助手', surface: 'desktop', isInteractive: true })

  files.set(norm(`${DIR}/tell-${SID}.json`), JSON.stringify({ id: 't1', text: '名字就叫 Ledgo', mode: 'send' }))
  await clock.advance(800)
  expect(sent[0]).toContain('名字就叫 Ledgo')
  expect(JSON.parse(files.get(norm(`${DIR}/told-${SID}.json`)) ?? '{}').id).toBe('t1')

  files.set(norm(`${DIR}/tell-${SID}.json`), JSON.stringify({ id: 't2', text: '做一个记账小工具', mode: 'new', title: '记账小工具' }))
  await clock.advance(800)
  expect(JSON.stringify(opened[0])).toContain('start_session')
  expect(JSON.stringify(opened[0])).toContain('记账小工具')
  expect(JSON.parse(files.get(norm(`${DIR}/told-${SID}.json`)) ?? '{}').msg).toContain('新开了')
})

test('对讲机问问题：照选的努力程度想，要上网时先搜再答', async ($, on) => {
  const files = new Map<string, string>()
  const asked: string[] = []
  fakeComputer(on, files, [], asked, [], [], true)
  const efforts: unknown[] = []
  const urls: string[] = []
  let round = 0
  on('model.complete', async (_$, e) => {
    efforts.push(e.effort)
    asked.push(typeof e.prompt === 'string' ? e.prompt : '')
    round++
    const text = round === 1 ? '【搜索】Claude 最新模型' : '最新的是 Opus 5.5。\n来源：https://a.example/claude'
    return { value: { isAnswered: true, text, usage: { input_tokens: 100, output_tokens: 10, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 } } }
  })
  on('http.fetch', async (_$, e) => {
    urls.push(e.url)
    const html = '<li class="b_algo"><h2><a href="https://a.example/claude">Claude 模型</a></h2><p>Opus 5.5 发布了</p></li>'
    return { value: { status: 200, ok: true, headers: {}, text: html } }
  })
  const clock = mock.clock(on)
  await $.session.start({ cwd: 'D:/项目/小克助手', surface: 'desktop', isInteractive: true })

  files.set(
    norm(`${DIR}/ask-${SID}.json`),
    JSON.stringify({ id: 'w1', text: '现在最新的 Claude 是哪个', model: 'opus', ctxCount: 0, perChars: 800, effort: 'max', web: true }),
  )
  await clock.advance(800)
  const answer = JSON.parse(files.get(norm(`${DIR}/answer-${SID}.json`)) ?? '{}')
  expect(answer.text).toContain('Opus 5.5')
  expect(answer.note).toContain('上网查了 1 次')
  expect(efforts).toEqual(['max', 'max'])
  expect(urls[0]).toContain('bing.com/search')
  expect(asked[1]).toContain('Opus 5.5 发布了')
  expect(JSON.parse(files.get(norm(`${DIR}/progress-${SID}.json`)) ?? '{}').text).toContain('在搜')
})

test('插件刚装上（自己的记录是空的）：已经交过的话不再交一遍', async ($, on) => {
  const files = new Map<string, string>()
  const sent: string[] = []
  fakeComputer(on, files, [], [], sent, [])
  const clock = mock.clock(on)
  files.set(norm(`${DIR}/tell-${SID}.json`), JSON.stringify({ id: 'old1', text: '（克讲机生图台定稿）旧的', mode: 'send' }))
  files.set(norm(`${DIR}/told-${SID}.json`), JSON.stringify({ id: 'old1', ok: true, msg: '发给对话了' }))
  await $.session.start({ cwd: 'D:/项目/小克助手', surface: 'desktop', isInteractive: true })
  await clock.advance(2000)
  expect(sent.length).toBe(0)

  files.set(norm(`${DIR}/tell-${SID}.json`), JSON.stringify({ id: 'new1', text: '新的一句', mode: 'send' }))
  await clock.advance(800)
  expect(sent[0]).toContain('新的一句')
})

test('生图台：对讲机开着就把生图请求交过去，没开就让 Claude 自己生', async ($, on) => {
  const files = new Map<string, string>()
  fakeComputer(on, files, [], [])
  mock.clock(on)
  await $.session.start({ cwd: 'D:/项目/小克助手', surface: 'desktop', isInteractive: true })

  const off = await $.tool.call({ tool: 'mcp__clawkie__image', title: '咖啡店贴纸', prompt: '一张可爱的咖啡店贴纸' } as never)
  expect(JSON.stringify(off)).toContain('没开')

  files.set(norm(`${DIR}/talkie-alive.json`), JSON.stringify({ pid: 1, at: Date.now() / 1000 }))
  const on2 = await $.tool.call({ tool: 'mcp__clawkie__image', title: '咖啡店贴纸', prompt: '一张可爱的咖啡店贴纸', saveAs: 'cafe.png' } as never)
  expect(JSON.stringify(on2)).toContain('已交给')
  const req = [...files.entries()].find(([k]) => k.includes('img-req-'))
  expect(req).toBeDefined()
  expect(JSON.parse(req![1]).saveAs).toBe('cafe.png')
  expect(JSON.parse(req![1]).sid).toBe(SID)
})

test('你在对话里发消息：告诉桌宠是哪个对话（唠嗑自己发的不算）', async ($, on) => {
  const files = new Map<string, string>()
  fakeComputer(on, files, [], [])
  mock.clock(on)
  await $.session.start({ cwd: 'D:/项目/小克助手', surface: 'desktop', isInteractive: true })

  await $.prompt.submit({ text: '（唠嗑小窗里定的）名字叫 Ledgo' } as never)
  expect(files.has(norm(`${DIR}/focus.json`))).toBe(false)
  await $.prompt.submit({ text: '帮我把首页改一下' } as never)
  expect(JSON.parse(files.get(norm(`${DIR}/focus.json`)) ?? '{}').sid).toBe(SID)
})

test('改提示词：推到克讲机的提示词卡上（不写编号就改最近那个请求）', async ($, on) => {
  const files = new Map<string, string>()
  fakeComputer(on, files, [], [])
  mock.clock(on)
  await $.session.start({ cwd: 'D:/项目/小克助手', surface: 'desktop', isInteractive: true })
  files.set(norm(`${DIR}/talkie-alive.json`), JSON.stringify({ pid: 1, at: Date.now() / 1000 }))

  const none = await $.tool.call({ tool: 'mcp__clawkie__image_prompt', prompt: '新的' } as never)
  expect(JSON.stringify(none)).toContain('不知道要改哪个')

  await $.tool.call({ tool: 'mcp__clawkie__image', title: '图标', prompt: '旧的提示词' } as never)
  const rid = JSON.parse([...files.entries()].find(([k]) => k.includes('img-req-'))![1]).id
  const ok = await $.tool.call({ tool: 'mcp__clawkie__image_prompt', prompt: '小克画大一点，透明底', note: '放大 + 透明' } as never)
  expect(JSON.stringify(ok)).toContain('提示词卡')
  const upd = [...files.entries()].find(([k]) => k.includes(`img-upd-${rid}-`))
  expect(upd).toBeDefined()
  expect(JSON.parse(upd![1]).prompt).toBe('小克画大一点，透明底')
})

test('送回定稿不打扰对话：只留小纸条，下次用户说话时顺带给 Claude', async ($, on) => {
  const files = new Map<string, string>()
  const sent: string[] = []
  const contexts = ctxLog
  fakeComputer(on, files, [], [], sent)
  const clock = mock.clock(on)
  await $.session.start({ cwd: 'D:/项目/小克助手', surface: 'desktop', isInteractive: true })

  files.set(norm(`${DIR}/tell-${SID}.json`), JSON.stringify({ id: 'n1', text: '定稿在 D:/x/icon.png', mode: 'note' }))
  await clock.advance(800)
  expect(sent).toHaveLength(0)
  expect(JSON.parse(files.get(norm(`${DIR}/told-${SID}.json`)) ?? '{}').msg).toContain('不打扰')

  await $.prompt.submit({ text: '接着做首页' } as never)
  expect(contexts.at(-1)?.join(' ')).toContain('定稿在 D:/x/icon.png')
  await $.prompt.submit({ text: '再说一句' } as never)
  expect(contexts.at(-1)?.join(' ') ?? '').not.toContain('定稿在')
})
