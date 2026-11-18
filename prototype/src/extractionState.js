function timestampMicros(timestamp) {
  const millis = Date.parse(timestamp)
  if (!Number.isFinite(millis)) return 0n
  const fraction = String(timestamp).match(/\.(\d+)/)?.[1] || ''
  const subMillis = fraction.padEnd(6, '0').slice(3, 6)
  return BigInt(millis) * 1000n + BigInt(subMillis || '0')
}

export function mergeExtractionHistory(...groups) {
  const recordsById = new Map()
  for (const record of groups.flatMap(group => Array.isArray(group) ? group : [group]).filter(Boolean)) {
    recordsById.set(record.extraction_id, record)
  }
  return [...recordsById.values()].sort((left, right) => {
    const leftTime = timestampMicros(left.created_at)
    const rightTime = timestampMicros(right.created_at)
    if (leftTime !== rightTime) return leftTime > rightTime ? -1 : 1
    if (left.extraction_id === right.extraction_id) return 0
    return left.extraction_id < right.extraction_id ? 1 : -1
  })
}

export async function loadExtractionState(api, inquiryId) {
  if (!inquiryId) return {latest: null, history: []}

  const [latestResult, historyResult] = await Promise.allSettled([
    api.latestExtraction(inquiryId),
    api.extractionHistory(inquiryId),
  ])
  if (latestResult.status === 'rejected' && historyResult.status === 'rejected') {
    throw latestResult.reason
  }
  const latestResponse = latestResult.status === 'fulfilled' ? latestResult.value : null
  const historyResponse = historyResult.status === 'fulfilled' ? historyResult.value : null
  const history = Array.isArray(historyResponse?.items) ? historyResponse.items : []
  const records = mergeExtractionHistory(history, latestResponse)
  let error = ''
  if (historyResult.status === 'rejected') error = '提取历史读取失败，当前仅显示最新记录。'
  if (latestResult.status === 'rejected') error = '最新记录接口读取失败，已从历史记录恢复。'

  return {
    latest: records[0] || null,
    history: records,
    ...(error ? {error} : {}),
  }
}

export function prependExtraction(history, extraction) {
  return mergeExtractionHistory(history || [], extraction)
}
