import type { Agent, AgentPattern, McpServerTools } from '$lib/types';

export async function getPatterns(): Promise<AgentPattern[]> {
  const res = await fetch('/api/agents/patterns');
  if (!res.ok) throw new Error('Failed to fetch patterns');
  const data = await res.json();
  return data.patterns;
}

export async function listAgents(): Promise<Agent[]> {
  const res = await fetch('/api/agents');
  if (!res.ok) throw new Error('Failed to fetch agents');
  const data = await res.json();
  return data.agents;
}

export async function getAgent(id: string): Promise<Agent> {
  const res = await fetch(`/api/agents/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch agent ${id}`);
  return res.json();
}

export async function createAgent(data: Partial<Agent>): Promise<Agent> {
  const res = await fetch('/api/agents', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error('Failed to create agent');
  return res.json();
}

export async function updateAgent(id: string, data: Partial<Agent>): Promise<Agent> {
  const res = await fetch(`/api/agents/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error('Failed to update agent');
  return res.json();
}

export async function deleteAgent(id: string): Promise<void> {
  const res = await fetch(`/api/agents/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete agent');
}

export async function startAgent(id: string): Promise<void> {
  const res = await fetch(`/api/agents/${id}/start`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to start agent');
}

export async function stopAgent(id: string): Promise<void> {
  const res = await fetch(`/api/agents/${id}/stop`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to stop agent');
}

export async function getMcpTools(): Promise<McpServerTools[]> {
  const res = await fetch('/api/mcp/tools');
  if (!res.ok) throw new Error('Failed to fetch MCP tools');
  const data = await res.json();
  return data.servers;
}
