export function createLogStream(
  onLine: (line: string) => void,
  onError?: (err: Event) => void
): () => void {
  const es = new EventSource('/logs');

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
