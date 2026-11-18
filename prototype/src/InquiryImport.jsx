import {useState} from 'react'
import {inquiryApi} from './api/inquiries'
import {CheckCircle,CircleNotch,EnvelopeSimple,FileArrowUp,FilePdf,FloppyDisk,Image,Warning,X} from '@phosphor-icons/react'

const ACCEPT = {
  PDF: '.pdf',
  图片: '.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff',
  EML: '.eml',
}
const SUPPORTED_EXTENSIONS = {
  PDF: new Set(['.pdf']),
  图片: new Set(['.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff']),
  EML: new Set(['.eml']),
}
const ALL_SUPPORTED_EXTENSIONS = new Set(Object.values(SUPPORTED_EXTENSIONS).flatMap(extensions => [...extensions]))
const MAX_FILE_BYTES = 25 * 1024 * 1024
const PARSE_ERRORS = {
  UNSUPPORTED_FORMAT: '不支持此文件类型，请上传 PDF、图片或 EML。',
  FILE_TOO_LARGE: '文件超过单个 25 MiB 的大小上限。',
  CORRUPTED: '文件已损坏或格式无效。',
  ENCRYPTED: '文件受密码保护，暂时无法解析。',
  EMPTY_TEXT: '没有提取到足够的可读文本。',
  OCR_UNAVAILABLE: '当前环境的 OCR 不可用，扫描文件暂时无法识别。',
  TOO_MANY_PAGES: 'PDF 页数超过限制（最多 50 页）。',
  STORAGE_ERROR: '原始文件保存失败，请重试。',
  PARSER_ERROR: '文件解析失败，可重试或粘贴文本。',
}

function formatBytes(value) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function FileResult({item}) {
  const success = item.parse_status === 'SUCCESS'
  const message = PARSE_ERRORS[item.error_code] || item.error_message
  return <article className="fileresult">
    <div className="fileresulthead">
      <div className="fileresultname"><b>{item.original_name}</b><small>{formatBytes(item.byte_size)} · {item.page_count || 0} 页</small></div>
      <span className={`pill ${success ? 'green' : 'amber'}`}>{success ? '解析成功' : '解析失败'}</span>
    </div>
    {success ? <>
      {item.preview_text && <pre className="filepreview">{item.preview_text}{item.preview_text.length >= 1200 ? '…' : ''}</pre>}
      {item.attachments?.length > 0 && <small className="filemeta">邮件附件：{item.attachments.map(file => `${file.filename}${file.parsed ? '' : `（${file.skip_reason || '未解析'}）`}`).join('、')}</small>}
      {item.warnings?.length > 0 && <small className="filemeta">提示：{item.warnings.join('；')}</small>}
    </> : <p className="filefailure">{message}</p>}
  </article>
}

export function InquiryImportModal({close,done,toast}) {
  const [mode,setMode] = useState('文本')
  const [loading,setLoading] = useState(false)
  const [error,setError] = useState('')
  const [fileSelectionError,setFileSelectionError] = useState('')
  const [text,setText] = useState('Dear Sales Team, We are Nordlicht GmbH in Germany and need 1,000 ANC wireless earbuds with OEM logo...')
  const [files,setFiles] = useState([])
  const [results,setResults] = useState([])
  const firstSuccess = results.find(item => item.parse_status === 'SUCCESS' && item.inquiry_id)
  const closeModal = () => close(results.length > 0)

  const addFiles = fileList => {
    const incoming = Array.from(fileList || [])
    const merged = [...files]
    const rejected = []
    const additions = []
    for (const file of incoming) {
      const extension = file.name.includes('.') ? `.${file.name.split('.').pop().toLowerCase()}` : ''
      if (!ALL_SUPPORTED_EXTENSIONS.has(extension)) {
        rejected.push(`${file.name}：仅支持 PDF、图片或 EML 文件。`)
        continue
      }
      if (file.size > MAX_FILE_BYTES) {
        rejected.push(`${file.name}：超过单个 25 MiB 的大小上限。`)
        continue
      }
      if (!merged.some(existing => existing.name === file.name && existing.size === file.size && existing.lastModified === file.lastModified) &&
          !additions.some(existing => existing.name === file.name && existing.size === file.size && existing.lastModified === file.lastModified)) additions.push(file)
    }
    setResults([])
    if (merged.length + additions.length > 10) {
      rejected.unshift('每次最多导入 10 个文件；本次新增文件未加入队列，请分批添加或先移除已选文件。')
      setFileSelectionError(rejected.join(' '))
      return
    }
    setFiles([...merged, ...additions])
    setFileSelectionError(rejected.join(' '))
  }

  const submit = async () => {
    setError('')
    if (mode === '文本') {
      if (text.trim().length < 10) {
        setError('询盘原文至少需要 10 个字符。')
        return
      }
      setLoading(true)
      try {
        const subject = text.trim().split(/\r?\n/)[0].slice(0, 120) || '新询盘'
        const created = await inquiryApi.create({subject,raw_text:text,source_type:'TEXT'})
        toast('询盘已保存到 PostgreSQL')
        done(created)
      } catch (e) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
      return
    }
    if (!files.length) {
      setError('请先选择至少一个文件。')
      return
    }
    setLoading(true)
    try {
      const response = await inquiryApi.importFiles(files)
      setResults(response.items || [])
      const succeeded = (response.items || []).filter(item => item.parse_status === 'SUCCESS').length
      toast(succeeded ? `${succeeded} 个文件已解析并保存` : '文件处理结果已保存，请查看失败原因')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const resetFiles = () => {
    setFiles([])
    setResults([])
    setError('')
    setFileSelectionError('')
  }
  const switchMode = nextMode => {
    if (nextMode === '文本' && files.length > 0) {
      setFileSelectionError('当前仍有未清空的文件队列，请先上传或清空后再切换到文本询盘。')
      return
    }
    setMode(nextMode)
    setError('')
  }

  const typeTabs = [['文本',EnvelopeSimple],['PDF',FilePdf],['图片',Image],['EML',FileArrowUp]]
  return <div className="overlay"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="import-title">
    <div className="modalhead"><div><h2 id="import-title">导入新询盘</h2><p>文本询盘直接保存；文件会逐个解析并保留原文件和解析记录。</p></div><button onClick={closeModal} aria-label="关闭"><X/></button></div>
    <div className="importtabs" aria-label="文件选择器类型筛选">{typeTabs.map(([label,Icon])=><button key={label} className={mode===label?'active':''} onClick={()=>switchMode(label)}><Icon/>{label}</button>)}</div>
    {mode === '文本' ? <textarea value={text} onChange={event=>setText(event.target.value)} aria-label="询盘原文"/> : <>
      <div className="drop" onDragOver={event=>event.preventDefault()} onDrop={event=>{event.preventDefault();addFiles(event.dataTransfer.files)}}>
        <FileArrowUp size={36}/><b>选择或拖放文件</b><span>支持 PDF、图片或 EML，可混合导入；每份不超过 25 MiB，每次最多 10 份。</span>
        <label className="secondary filepick">选择文件<input type="file" accept={ACCEPT[mode]} multiple onChange={event=>{addFiles(event.target.files);event.target.value=''}}/></label>
      </div>
      {fileSelectionError && <div className="formerror" role="alert">{fileSelectionError}</div>}
      {files.length > 0 && <div className="filequeue"><div className="queuehead"><b>待上传 · {files.length} 个文件</b><button className="textbutton" onClick={resetFiles}>清空</button></div>{files.map((file,index)=><div className="queuedfile" key={`${file.name}-${file.size}-${file.lastModified}`}><span><b>{file.name}</b><small>{formatBytes(file.size)}</small></span><button aria-label={`移除 ${file.name}`} onClick={()=>{setFiles(current=>current.filter((_,i)=>i!==index));setResults([])}}><X/></button></div>)}</div>}
      {results.length > 0 && <div className="fileresults"><div className="queuehead"><b>处理结果 · {results.filter(item=>item.parse_status==='SUCCESS').length} 成功 / {results.filter(item=>item.parse_status==='FAILED').length} 失败</b></div>{results.map(item=><FileResult item={item} key={item.file_id}/>)}</div>}
    </>}
    {error && <div className="formerror"><Warning/>{error}</div>}
    <div className="modalactions"><button className="secondary" onClick={closeModal}>取消</button>
      {results.length > 0 ? <>
        <button className="secondary" onClick={resetFiles}>重新选择</button>
        {firstSuccess && <button className="primary" onClick={()=>done({id:firstSuccess.inquiry_id})}><CheckCircle/>查看成功询盘</button>}
      </> : <button className="primary" disabled={loading || (mode==='文本' ? text.trim().length < 10 : files.length === 0)} onClick={submit}>{loading?<CircleNotch className="spin"/>:mode==='文本'?<FloppyDisk/>:<FileArrowUp/>}{loading?'处理中':mode==='文本'?'创建询盘':'上传并解析'}</button>}
    </div>
  </section></div>
}
