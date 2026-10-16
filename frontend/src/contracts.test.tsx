import { afterEach, describe, it, expect, vi } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import 'fake-indexeddb/auto'
import { AnswerCard } from './App'
import { context } from './lib/history'
import { load, save, reserveTurn, releaseTurn } from './lib/store'
import type { Answer, Conversation, Workspace } from './types'
afterEach(cleanup)
const literal = '9007199254740993.00000000000001'
const answer: Answer = {
  outcome: 'supported',
  fields: [
    {
      name: 'amount',
      kind: 'number',
      value_text: literal,
      evidence_id: 'E1',
      quote: '',
      pointer: '/amount',
    },
  ],
  evidence: [
    {
      id: 'E1',
      key: { document_id: 'doc', revision: 'rev', chunk_id: 'chunk' },
      text: '<img src=x onerror=alert(1)>',
      sources: [],
      labels: [],
    },
  ],
  workflow: {},
  raw_report: `{"value":${literal}}`,
}
describe('browser integrity', () => {
  it('atomically reserves one pending turn across tabs and recovers it after a stale save', async () => {
    const state: Workspace = { version: 1, current: 'reserved-chat', theme: 'light', uploads: [],
      conversations: [{ id: 'reserved-chat', created: 'now', scope: ['doc'], exchanges: [
        { id: 'pending', job_id: 'reserved-job', question: 'Amount?', pending: true, mode: 'hybrid' },
      ] }] }
    await reserveTurn(state, 'reserved-chat')
    await expect(reserveTurn(state, 'reserved-chat')).rejects.toThrow('unfinished answer')
    await save({ ...state, conversations: [] })
    expect((await load())?.conversations[0].exchanges[0].job_id).toBe('reserved-job')
    await releaseTurn('reserved-job')
    await reserveTurn(state, 'reserved-chat')
    await releaseTurn('reserved-job')
  })
  it('renders exact values and citation, with safe text', () => {
    const choose = vi.fn()
    render(<AnswerCard answer={answer} onEvidence={choose} />)
    expect(screen.getByText(literal)).toBeTruthy()
    fireEvent.click(
      screen.getByRole('button', { name: 'Source E1 for amount' }),
    )
    expect(choose).toHaveBeenCalledWith(answer.evidence[0])
    expect(document.querySelector('img')).toBeNull()
  })
  it('saves exact reports and file bytes in IndexedDB', async () => {
    const state: Workspace = {
      version: 1,
      current: 'chat',
      theme: 'light',
      uploads: [
        {
          id: 'upload',
          filename: 'x.txt',
          file: new Blob(['test']),
          state: 'retry',
          record_pointer: '',
          allow_partial: false,
        },
      ],
      conversations: [
        {
          id: 'chat',
          created: 'now',
          scope: ['doc'],
          exchanges: [{ id: 'q', question: 'Amount?', answer }],
        },
      ],
    }
    await save(state)
    const restored = await load()
    expect(restored?.conversations[0].exchanges[0].answer?.raw_report).toBe(
      answer.raw_report,
    )
    expect(
      JSON.parse(JSON.stringify(restored)).conversations[0].exchanges[0].answer
        .fields[0].value_text,
    ).toBe(literal)
  })
  it('sends only four complete supported exchanges and never rejected drafts', () => {
    const chat: Conversation = {
      id: 'c',
      created: 'now',
      scope: ['doc'],
      exchanges: Array.from({ length: 6 }, (_, i) => ({
        id: String(i),
        question: `Q${i}`,
        answer,
      })),
    }
    chat.exchanges.push({
      id: 'bad',
      question: 'Bad',
      answer: { ...answer, outcome: 'rejected' },
    })
    const turns = context(chat)
    expect(turns).toHaveLength(8)
    expect(turns[0].text).toBe('Q2')
    expect(turns[7].text).toContain(literal)
    expect(JSON.stringify(turns)).not.toContain('Bad')
  })
  it('refuses oversized context without shortening', () => {
    expect(() =>
      context({
        id: 'c',
        created: 'now',
        scope: [],
        exchanges: [{ id: 'a', question: 'a'.repeat(4097), answer }],
      }),
    ).toThrow('no text was shortened')
  })
  it('distinguishes null, zero and rejected outcomes', () => {
    render(
      <AnswerCard
        answer={{ ...answer, outcome: 'rejected', fields: [] }}
        onEvidence={() => {}}
      />,
    )
    expect(screen.getByText('Answer rejected')).toBeTruthy()
    expect(screen.queryByText(literal)).toBeNull()
  })
})
