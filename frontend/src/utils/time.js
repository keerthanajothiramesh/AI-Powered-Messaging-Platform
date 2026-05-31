import { format } from 'date-fns'

// IST = UTC+5:30 = 330 minutes ahead of UTC
// This formula shifts any timestamp so format() displays IST wall-clock time
// regardless of the browser's local timezone.
function toIST(timestamp) {
  const d = new Date(timestamp)
  return new Date(d.getTime() + (330 + d.getTimezoneOffset()) * 60000)
}

export function formatIST(timestamp, fmt = 'HH:mm') {
  if (!timestamp) return ''
  try {
    return format(toIST(timestamp), fmt)
  } catch {
    return ''
  }
}

export function formatISTFull(timestamp) {
  if (!timestamp) return ''
  try {
    return format(toIST(timestamp), 'MMM d, HH:mm')
  } catch {
    return ''
  }
}

export function isISTToday(timestamp) {
  if (!timestamp) return false
  const adj = toIST(timestamp)
  const nowAdj = toIST(new Date().toISOString())
  return adj.toDateString() === nowAdj.toDateString()
}

export function isISTYesterday(timestamp) {
  if (!timestamp) return false
  const adj = toIST(timestamp)
  const yesterday = toIST(new Date(Date.now() - 86400000).toISOString())
  return adj.toDateString() === yesterday.toDateString()
}
