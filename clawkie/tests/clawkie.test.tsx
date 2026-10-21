import { expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const SURFACES = ['terminal', 'desktop'] as const

const PANE = {
  plugin: 'clawkie',
  component: 'Pane',
  requestId: 'clawkie',
  props: { title: '克讲机 Clawkie', isFocused: true, bodyColumns: 60, placement: 'dock' },
} as const

// 假的主对话：一句很长、带系统提醒的，一句普通的
function fakeSession(on: On, asked: string[]) {
  on('session.messages', async () => ({
    value: [
      { role: 'user', text: '<system-reminder>别看我</system-reminder>帮我做个小窗', toolUses: [] },
      { role: 'assistant', text: '好的'.repeat(600), toolUses: [] },
    ],
  }))
  on('model.complete', async (_$, e) => {
    asked.push(typeof e.prompt === 'string' ? e.prompt : '')
    return {
      value: {
        isAnswered: true,
        text: '叫「唠嗑」吧',
        usage: { input_tokens: 300, output_tokens: 20, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 },
      },
    }
  })
  on('store.set', async () => ({ value: undefined }))
}

for (const surface of SURFACES) {
  test(`${surface}：发一句话，得到回答，只带最后几句`, async ($, on) => {
    const asked: string[] = []
    fakeSession(on, asked)
    const ui = await $.ui.mount({ ...PANE, surface })

    expect((await ui.find({ text: /这次大约/ }))?.text).toContain('token')

    await ui.input({ key: 'ask-0', text: '取个名字', kind: 'change' })
    await ui.input({ key: 'ask-0', text: '取个名字' })

    expect(await ui.find({ text: /叫「唠嗑」吧/ })).toBeDefined()
    expect(await ui.find({ text: /用了 320 token/ })).toBeDefined()
    expect(asked).toHaveLength(1)
    expect(asked[0]).toContain('取个名字')
    expect(asked[0]).toContain('中间省略')
    expect(asked[0]).not.toContain('别看我')
  })

  test(`${surface}：选“不带对话”就不带主对话`, async ($, on) => {
    const asked: string[] = []
    fakeSession(on, asked)
    const ui = await $.ui.mount({ ...PANE, surface })

    await ui.select({ key: 'ctx', value: '0' })
    expect((await ui.find({ text: /这次大约/ }))?.text).toContain('对话 0')
    await ui.input({ key: 'ask-0', text: '随便聊聊' })

    expect(asked[0]).not.toContain('主对话最后几句')
  })
}
