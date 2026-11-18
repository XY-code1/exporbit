import {useCallback, useEffect, useRef, useState} from 'react'
import {inquiryApi} from './api/inquiries'
import {loadExtractionState, mergeExtractionHistory} from './extractionState'

const EMPTY = {latest: null, history: [], loading: false, extracting: false, error: ''}

export function useInquiryExtractions(inquiryId) {
  const [states, setStates] = useState({})
  const versions = useRef({})
  const pending = useRef(new Set())
  const update = useCallback((id, patch) => {
    setStates(previous => ({...previous, [id]: {...EMPTY, ...previous[id], ...patch}}))
  }, [])

  const reload = useCallback(async () => {
    if (!inquiryId) return
    const id = inquiryId
    const version = (versions.current[id] || 0) + 1
    versions.current[id] = version
    update(id, {loading: true, error: ''})
    try {
      const result = await loadExtractionState(inquiryApi, id)
      if (versions.current[id] === version) {
        setStates(previous => {
          const current = previous[id] || EMPTY
          const history = mergeExtractionHistory(current.history, current.latest, result.history, result.latest)
          return {...previous, [id]: {...EMPTY, ...current, ...result, latest: history[0] || null, history, loading: false}}
        })
      }
    } catch (error) {
      if (versions.current[id] === version) update(id, {loading: false, error: error.message})
    }
  }, [inquiryId, update])

  useEffect(() => {
    reload()
    return () => {
      if (inquiryId) versions.current[inquiryId] = (versions.current[inquiryId] || 0) + 1
    }
  }, [inquiryId, reload])

  const extract = useCallback(async () => {
    if (!inquiryId || pending.current.has(inquiryId)) return null
    const id = inquiryId
    pending.current.add(id)
    const requestVersion = (versions.current[id] || 0) + 1
    versions.current[id] = requestVersion
    update(id, {extracting: true, loading: false, error: ''})
    try {
      const result = await inquiryApi.extract(id)
      // Keep the persisted result for its inquiry, but reconcile by the same
      // timestamp/ID order as the API so a late older success cannot win.
      const isCurrentRequest = versions.current[id] === requestVersion
      if (isCurrentRequest) versions.current[id] = requestVersion + 1
      setStates(previous => {
        const current = previous[id] || EMPTY
        const history = mergeExtractionHistory(current.history, current.latest, result)
        return {
          ...previous,
          [id]: {
            ...EMPTY,
            ...current,
            latest: history[0] || result,
            history,
            ...(isCurrentRequest ? {loading: false, error: ''} : {}),
            extracting: false,
          },
        }
      })
      return result
    } catch (error) {
      if (versions.current[id] === requestVersion) update(id, {extracting: false, error: error.message})
      else update(id, {extracting: false})
      return null
    } finally {
      pending.current.delete(id)
    }
  }, [inquiryId, update])

  return {...(states[inquiryId] || EMPTY), reload, extract}
}
