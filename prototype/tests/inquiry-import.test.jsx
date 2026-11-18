import React from 'react'
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import {InquiryImportModal} from '../src/InquiryImport'
import {inquiryApi} from '../src/api/inquiries'

vi.mock('../src/api/inquiries', () => ({inquiryApi: {
  create: vi.fn(), importFiles: vi.fn(),
}}))

const pdfMode = () => fireEvent.click(screen.getByRole('button', {name: 'PDF'}))
const fileInput = () => screen.getByLabelText('选择文件')
const makeFile = (name, content = 'content') => new File([content], name, {type: 'application/octet-stream'})

beforeEach(() => {
  vi.resetAllMocks()
  inquiryApi.importFiles.mockResolvedValue({items: []})
})
afterEach(cleanup)

describe('inquiry file import validation', () => {
  it('rejects unsupported and oversized files before upload and keeps the reason visible', () => {
    render(<InquiryImportModal close={vi.fn()} done={vi.fn()} toast={vi.fn()}/>)
    pdfMode()
    const unsupported = makeFile('notes.txt')
    const oversized = new File([new Uint8Array(26 * 1024 * 1024)], 'oversized.pdf', {type: 'application/pdf'})
    fireEvent.change(fileInput(), {target: {files: [unsupported, oversized]}})

    expect(screen.getByRole('alert').textContent).toContain('notes.txt')
    expect(screen.getByRole('alert').textContent).toContain('oversized.pdf')
    expect(screen.queryByText(/待上传/)).toBeNull()
    expect(inquiryApi.importFiles).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', {name: 'EML'}))
    expect(screen.getByRole('alert').textContent).toContain('oversized.pdf')
  })

  it('rejects an over-limit drag-and-drop batch without truncating it or hiding the warning', () => {
    render(<InquiryImportModal close={vi.fn()} done={vi.fn()} toast={vi.fn()}/>)
    pdfMode()
    const dropZone = screen.getByText('选择或拖放文件').parentElement
    const tooMany = Array.from({length: 11}, (_, index) => makeFile(`file-${index}.pdf`))
    fireEvent.drop(dropZone, {dataTransfer: {files: tooMany}})

    expect(screen.getByRole('alert').textContent).toContain('最多导入 10 个文件')
    expect(screen.queryByText(/待上传/)).toBeNull()

    fireEvent.click(screen.getByRole('button', {name: 'EML'}))
    expect(screen.getByRole('alert').textContent).toContain('最多导入 10 个文件')
    fireEvent.change(fileInput(), {target: {files: [makeFile('buyer.eml')]}})

    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByText('待上传 · 1 个文件')).toBeTruthy()
  })

  it('applies the same type validation to dropped files', () => {
    render(<InquiryImportModal close={vi.fn()} done={vi.fn()} toast={vi.fn()}/>)
    pdfMode()
    const dropZone = screen.getByText('选择或拖放文件').parentElement
    fireEvent.drop(dropZone, {dataTransfer: {files: [makeFile('program.exe')]}})

    expect(screen.getByRole('alert').textContent).toContain('program.exe')
    expect(inquiryApi.importFiles).not.toHaveBeenCalled()
  })

  it('keeps supported queued files valid when switching the picker type filter', async () => {
    render(<InquiryImportModal close={vi.fn()} done={vi.fn()} toast={vi.fn()}/>)
    pdfMode()
    const pdf = makeFile('buyer.pdf')
    fireEvent.change(fileInput(), {target: {files: [pdf]}})

    fireEvent.click(screen.getByRole('button', {name: 'EML'}))
    expect(screen.getByText('待上传 · 1 个文件')).toBeTruthy()
    expect(screen.getByText(/可混合导入/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', {name: '文本'}))
    expect(screen.getByRole('alert').textContent).toContain('未清空的文件队列')
    expect(screen.getByText('选择或拖放文件')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', {name: '上传并解析'}))

    await waitFor(() => expect(inquiryApi.importFiles).toHaveBeenCalledWith([pdf]))
  })
})
