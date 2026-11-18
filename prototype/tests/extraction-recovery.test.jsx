import React from 'react'
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest'
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import {App, resolveActiveInquiryId} from '../src/App'
import {inquiryApi} from '../src/api/inquiries'

vi.mock('../src/api/inquiries', () => ({inquiryApi: {
  list: vi.fn(), get: vi.fn(), create: vi.fn(), latestExtraction: vi.fn(), extractionHistory: vi.fn(), extract: vi.fn(),
}}))

const inquiry = id => ({id, customer_name: `Customer ${id}`, subject: `RFQ ${id}`, raw_text: `Original ${id}`,
  workflow_status: 'NEW', source_type: 'TEXT', created_at: '2026-11-18T05:00:00Z'})
const field = value => ({value, status: value === null ? 'INSUFFICIENT_DATA' : 'CONFIRMED'})
const record = (id, inquiryId = 'a', status = 'SUCCESS') => ({
  extraction_id: id, inquiry_id: inquiryId, extraction_status: status,
  provider: 'deepseek', model: 'test-model', error_code: status === 'FAILED' ? 'TIMEOUT' : null,
  created_at: `2026-11-18T05:00:0${id.slice(-1)}Z`,
  structured_data: status === 'FAILED' ? null : {
    customer: {company_name: field(`Extracted ${id}`), customer_name: field(null), email: field(null), country: field(null)},
    business: {target_market: field(null), expected_delivery: field(null), target_price: field(null), purchasing_intent: field(null)},
    products: [], missing_fields: [], clarification_questions: [],
  },
})
let records
const runButton = () => screen.getByRole('button', {name: '运行 AI 提取'})
const switchTo = id => fireEvent.click(screen.getByRole('button', {name: new RegExp(`Customer ${id} RFQ ${id}`)}))
const deferred = () => {let resolve, reject; const promise = new Promise((res, rej) => {resolve=res; reject=rej}); return {promise, resolve, reject}}

beforeEach(() => {
  vi.resetAllMocks()
  localStorage.clear()
  records = {a: [], b: [], c1: [], c2: []}
  inquiryApi.list.mockResolvedValue({items: [inquiry('a'), inquiry('b')]})
  inquiryApi.get.mockImplementation(async id => inquiry(id))
  inquiryApi.latestExtraction.mockImplementation(async id => records[id]?.[0] || null)
  inquiryApi.extractionHistory.mockImplementation(async id => ({items: [...(records[id] || [])], total: (records[id] || []).length}))
  inquiryApi.extract.mockImplementation(async id => {
    const result = record(`run-${records[id].length + 1}`, id)
    records[id].unshift(result)
    return result
  })
})
afterEach(cleanup)

it('preserves a newer inquiry selection instead of applying a stale preferred ID', () => {
  const rows = [['A', 'RFQ A', '新询盘', 0, 'a'], ['B', 'RFQ B', '新询盘', 1, 'b'], ['C', 'RFQ C', '新询盘', 2, 'c']]
  expect(resolveActiveInquiryId(rows, 'b', 'c')).toBe('c')
  expect(resolveActiveInquiryId(rows, 'b', 'c', true)).toBe('b')
  const nextActive = resolveActiveInquiryId([rows[0], rows[2]], 'b', 'c', true)
  expect(nextActive).toBeNull()
  expect(nextActive ?? 'b').toBe('b')
})

describe('persisted extraction recovery in the actual inquiry workspace', () => {
  it('shows first-time empty state and appends repeated retries without losing previous records', async () => {
    render(<App/>)
    await screen.findByText('尚未运行 AI 提取')
    fireEvent.click(runButton())
    await screen.findByText('Extracted run-1')
    fireEvent.click(runButton())
    await screen.findByText('Extracted run-2')
    expect(screen.getByText('提取历史 · 2 条')).toBeTruthy()
    expect(inquiryApi.extract.mock.calls).toEqual([['a'], ['a']])
    expect(records.a.map(item => item.extraction_id)).toEqual(['run-2', 'run-1'])
  })

  it('retains a failed run and adds a new successful retry', async () => {
    const failed = record('run-1', 'a', 'FAILED')
    inquiryApi.extract.mockImplementationOnce(async () => {records.a.unshift(failed); return failed})
    render(<App/>)
    await screen.findByText('尚未运行 AI 提取')
    fireEvent.click(runButton())
    await screen.findByText('最近一次提取失败：TIMEOUT')
    expect(screen.queryByText('尚未运行 AI 提取')).toBeNull()
    fireEvent.click(runButton())
    await screen.findByText('Extracted run-2')
    expect(screen.getByText('提取历史 · 2 条')).toBeTruthy()
    expect(screen.getByText('错误码：TIMEOUT')).toBeTruthy()
  })

  it.each(['SUCCESS', 'FAILED'])('restores a %s latest record after a complete unmount/remount (refresh)', async status => {
    records.b = [record('run-1', 'b', status)]
    const mounted = render(<App/>)
    await screen.findByText('尚未运行 AI 提取')
    switchTo('b')
    if (status === 'SUCCESS') await screen.findByText('Extracted run-1')
    else await screen.findByText('最近一次提取失败：TIMEOUT')
    mounted.unmount()
    render(<App/>)
    if (status === 'SUCCESS') await screen.findByText('Extracted run-1')
    else await screen.findByText('最近一次提取失败：TIMEOUT')
    expect(screen.getByRole('heading', {level: 1}).textContent).toBe('Customer b')
    expect(screen.getByText('提取历史 · 1 条')).toBeTruthy()
    expect(inquiryApi.extract).not.toHaveBeenCalled()
  })

  it('does not show another inquiry\'s pending status or late extraction error after switching', async () => {
    const slow = deferred()
    inquiryApi.extract.mockReturnValueOnce(slow.promise)
    render(<App/>)
    await screen.findByText('尚未运行 AI 提取')
    fireEvent.click(runButton())
    await screen.findByRole('button', {name: 'AI 分析中'})
    switchTo('b')
    await waitFor(() => expect(runButton().disabled).toBe(false))
    await act(async () => slow.reject(new Error('Only inquiry A failed')))
    expect(screen.queryByText('Only inquiry A failed')).toBeNull()
    switchTo('a')
    await waitFor(() => expect(runButton().disabled).toBe(false))
  })

  it('does not let a late extraction failure overwrite a newer restored record', async () => {
    const slow = deferred()
    inquiryApi.extract.mockReturnValueOnce(slow.promise)
    render(<App/>)
    await screen.findByText('尚未运行 AI 提取')
    fireEvent.click(runButton())
    await screen.findByRole('button', {name: 'AI 分析中'})
    switchTo('b')
    await screen.findByText('尚未运行 AI 提取')
    records.a = [record('run-2')]
    switchTo('a')
    await screen.findByText('Extracted run-2')

    await act(async () => slow.reject(new Error('Old extraction failed')))

    expect(screen.getByText('Extracted run-2')).toBeTruthy()
    expect(screen.queryByText('Old extraction failed')).toBeNull()
    await waitFor(() => expect(runButton().disabled).toBe(false))
  })

  it('merges a late older extraction success without replacing a newer restored latest record', async () => {
    const slow = deferred()
    inquiryApi.extract.mockReturnValueOnce(slow.promise)
    render(<App/>)
    await screen.findByText('尚未运行 AI 提取')
    fireEvent.click(runButton())
    await screen.findByRole('button', {name: 'AI 分析中'})
    switchTo('b')
    await screen.findByText('尚未运行 AI 提取')
    records.a = [record('run-2'), record('run-1')]
    switchTo('a')
    await screen.findByText('Extracted run-2')

    await act(async () => slow.resolve(record('run-1')))

    expect(screen.getByText('Extracted run-2')).toBeTruthy()
    expect(screen.getByText('提取历史 · 2 条')).toBeTruthy()
    expect(screen.getByRole('button', {name: '查看提取记录 run-1'})).toBeTruthy()
    expect(screen.getAllByText('最新')).toHaveLength(1)
  })

  it('ignores stale inquiry detail errors and loading completion after a rapid switch', async () => {
    const stale = deferred()
    const current = deferred()
    inquiryApi.get.mockImplementation(id => id === 'b' ? stale.promise : current.promise)
    render(<App/>)
    await screen.findByText('尚未运行 AI 提取')
    switchTo('b')
    await screen.findByText('正在加载询盘详情')
    switchTo('a')
    await screen.findByText('正在加载询盘详情')

    await act(async () => stale.reject(new Error('Stale inquiry B detail failed')))

    expect(screen.getByText('正在加载询盘详情')).toBeTruthy()
    expect(screen.queryByText('Stale inquiry B detail failed')).toBeNull()
    await act(async () => current.resolve(inquiry('a')))
    await waitFor(() => expect(screen.queryByText('正在加载询盘详情')).toBeNull())
  })

  it('ignores an old load when a later switch to the same inquiry has already restored newer data', async () => {
    const slow = deferred()
    inquiryApi.latestExtraction.mockReturnValueOnce(slow.promise)
    inquiryApi.extractionHistory.mockReturnValueOnce(slow.promise)
    render(<App/>)
    await screen.findByText('正在恢复最近一次提取')
    switchTo('b')
    await screen.findByText('尚未运行 AI 提取')
    records.a = [record('run-2')]
    switchTo('a')
    await screen.findByText('Extracted run-2')
    await act(async () => slow.resolve(null))
    expect(screen.getByText('Extracted run-2')).toBeTruthy()
  })

  it('ignores an older list refresh after a newer import refresh has completed', async () => {
    const slow = deferred()
    inquiryApi.list
      .mockResolvedValueOnce({items: [inquiry('a'), inquiry('b')]})
      .mockReturnValueOnce(slow.promise)
      .mockResolvedValueOnce({items: [inquiry('a'), inquiry('b'), inquiry('c1'), inquiry('c2')]})
    inquiryApi.create
      .mockResolvedValueOnce({id: 'c1'})
      .mockResolvedValueOnce({id: 'c2'})

    render(<App/>)
    await screen.findByText('尚未运行 AI 提取')

    fireEvent.click(screen.getByRole('button', {name: /新建询盘/}))
    fireEvent.click(screen.getByRole('button', {name: '创建询盘'}))
    await waitFor(() => expect(inquiryApi.list).toHaveBeenCalledTimes(2))

    fireEvent.click(screen.getByRole('button', {name: /新建询盘/}))
    fireEvent.click(screen.getByRole('button', {name: '创建询盘'}))
    await waitFor(() => expect(inquiryApi.list).toHaveBeenCalledTimes(3))
    await waitFor(() => expect(screen.getByRole('heading', {level: 1}).textContent).toBe('Customer c2'))

    await act(async () => slow.resolve({items: [inquiry('a'), inquiry('b'), inquiry('c1')]}))

    expect(screen.getByRole('heading', {level: 1}).textContent).toBe('Customer c2')
    expect(screen.getByRole('button', {name: /Customer c2 RFQ c2/})).toBeTruthy()
  })
})


it('views an earlier result read-only and returns to the latest without issuing extraction writes', async () => {
  records.a = [record('run-2'), record('run-1')]
  render(<App/>)
  await screen.findByText('Extracted run-2')
  fireEvent.click(screen.getByRole('button', {name: '查看提取记录 run-1'}))
  await screen.findByText('Extracted run-1')
  expect(screen.getByText('历史 AI 提取')).toBeTruthy()
  expect(screen.queryByText('Extracted run-2')).toBeNull()
  fireEvent.click(screen.getByRole('button', {name: '返回最新记录'}))
  await screen.findByText('Extracted run-2')
  expect(inquiryApi.extract).not.toHaveBeenCalled()
  expect(records.a[0].extraction_id).toBe('run-2')
})

it('does not claim no extraction exists after read failure and retries the read without extracting', async () => {
  records.a = [record('run-1')]
  inquiryApi.latestExtraction.mockRejectedValueOnce(new Error('Read failed'))
  inquiryApi.extractionHistory.mockRejectedValueOnce(new Error('History failed'))
  render(<App/>)
  await screen.findByText('未能恢复提取记录')
  expect(screen.queryByText('尚未运行 AI 提取')).toBeNull()
  fireEvent.click(screen.getByRole('button', {name: '重新读取'}))
  await screen.findByText('Extracted run-1')
  expect(inquiryApi.extract).not.toHaveBeenCalled()
})
