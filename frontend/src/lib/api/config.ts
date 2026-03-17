import type { Credential, ChannelsConfig, McpServer } from '$lib/types';

export async function getCredentials(): Promise<{ credentials: Credential[] }> {
  const res = await fetch('/config/credentials');
  if (!res.ok) throw new Error('Failed to fetch credentials');
  return res.json();
}

export async function updateCredentials(updates: Record<string, string>): Promise<void> {
  const res = await fetch('/config/credentials', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updates })
  });
  if (!res.ok) throw new Error('Failed to update credentials');
}

export async function getChannels(): Promise<ChannelsConfig> {
  const res = await fetch('/config/channels');
  if (!res.ok) throw new Error('Failed to fetch channels');
  return res.json();
}

export async function getMcp(): Promise<{ servers: McpServer[] }> {
  const res = await fetch('/config/mcp');
  if (!res.ok) throw new Error('Failed to fetch MCP config');
  return res.json();
}

export async function toggleMcp(name: string, enabled: boolean): Promise<void> {
  const res = await fetch('/config/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ server: name, enabled })
  });
  if (!res.ok) throw new Error('Failed to toggle MCP server');
}
