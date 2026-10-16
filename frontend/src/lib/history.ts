import type { Conversation } from '../types'
export const bytes = (value: string) => new TextEncoder().encode(value).length
export function context(chat: Conversation) {
  return chat.exchanges
    .filter((e) => e.answer?.outcome === 'supported')
    .slice(-4)
    .flatMap((e) => {
      const answer = e
        .answer!.fields.map((f) => `${f.name}: ${f.value_text} (${f.kind})`)
        .join('\n')
      if (bytes(e.question) > 4096 || bytes(answer) > 4096)
        throw new Error(
          'A previous turn exceeds the 4 KiB context limit. Start a new conversation; no text was shortened.',
        )
      return [
        { role: 'user', text: e.question },
        { role: 'assistant', text: answer },
      ]
    })
}
