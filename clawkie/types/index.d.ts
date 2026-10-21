/** 小窗里的一句话：me = 你问的，ai = 它答的 */
export type Line = {
  who: 'me' | 'ai'
  text: string
  /** 答完写上：用了多少 token、哪个模型 */
  note?: string
  isError?: boolean
}

/** 设置：会存进 $.store，下次开对话还在 */
export type Settings = {
  /** haiku / sonnet / opus / claude-fable-5-1 / custom */
  model: string
  /** model = custom 时自己填的模型名 */
  customModel: string
  /** 带主对话最后几句（0 = 不带，纯闲聊） */
  ctxCount: number
  /** 每句最多带多少字 */
  perChars: number
}

export type Bridge = {
  askId: string
  tellId: string
  label: string
  /** "带几句-每句几字" → 大约多少 token */
  est: Record<string, number>
  /** 主对话最近一次说完话的时间（毫秒），对讲机默认听最近在动的那个 */
  active: number
  /** 这个对话最近交给生图台的请求编号（改提示词时不写编号就改它） */
  lastImg: string
  /** 克讲机留的小纸条，用户下次说话时跟着给 Claude */
  notes: string[]
}

declare module 'claude-code' {
  interface PluginState {
    clawkie: {
      lines: Line[]
      settings: Settings
      draft: string
      busy: boolean
      /** 主对话每说完一轮 +1，让预估重新算 */
      tick: number
      /** 发送一次 +1，换掉输入框让它清空 */
      sent: number
      /** 对讲机：处理过的问题 / 告诉项目的编号，给对讲机看的名字和预估 */
      bridge: Bridge
    }
  }
}
