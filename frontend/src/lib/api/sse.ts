export function createLogStream(
  onLine: (line: string) => void,
  onError?: (err: Event) => void,
  agentId?: string
): () => void {
  const url = agentId ? `/logs?agent_id=${encodeURIComponent(agentId)}` : '/logs';
  const es = new EventSource(url);

  es.onmessage = (event) => {
    try {
      const line = JSON.parse(event.data) as string;
      onLine(line);
    } catch {
      onLine(event.data);
    }
  };

  es.onerror = (err) => {
    onError?.(err);
  };

  return () => es.close();
}
