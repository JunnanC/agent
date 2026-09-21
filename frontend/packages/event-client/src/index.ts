export function openPortalEventStream(onError?: (event: Event) => void): EventSource {
  const source = new EventSource('/api/v2/events/stream', { withCredentials: true })
  if (onError) source.addEventListener('error', onError)
  return source
}

