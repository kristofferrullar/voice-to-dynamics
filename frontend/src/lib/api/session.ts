import type { SessionStatus } from '$lib/types';

export async function getStatus(): Promise<SessionStatus> {
  const res = await fetch('/status');
  if (!res.ok) throw new Error(`Failed to fetch status: ${res.status}`);
  return res.json();
}

export async function startSession(): Promise<void> {
  const res = await fetch('/start', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to start session');
}

export async function stopSession(): Promise<void> {
  const res = await fetch('/stop', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to stop session');
}

export async function pauseSession(): Promise<void> {
  const res = await fetch('/pause', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to pause session');
}

export async function resumeSession(): Promise<void> {
  const res = await fetch('/resume', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to resume session');
}

export async function setLanguage(language: string): Promise<void> {
  const res = await fetch('/language', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ language })
  });
  if (!res.ok) throw new Error('Failed to set language');
}

export async function sendText(text: string): Promise<{ reply: string }> {
  const res = await fetch('/text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  });
  if (!res.ok) throw new Error('Failed to send text');
  return res.json();
}
