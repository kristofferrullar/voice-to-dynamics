<script lang="ts">
  import { onMount } from 'svelte';
  import { PageContainer, PageHeader, Button, Badge, StatusDot, Alert, EmptyState } from 'wop-ui';
  import { listAgents, startAgent, stopAgent, deleteAgent } from '$lib/api/agents';
  import type { Agent } from '$lib/types';

  const PATTERN_ICONS: Record<string, string> = {
    voice_assistant: '🎙',
    task_agent: '⚙️'
  };

  const CHANNEL_LABELS: Record<string, string> = {
    telegram: 'Telegram',
    teams: 'Teams',
    whatsapp: 'WhatsApp',
    local: 'Local mic',
    acs: 'ACS Voice'
  };

  let agents = $state<Agent[]>([]);
  let error = $state('');
  let acting = $state<Record<string, boolean>>({});

  onMount(async () => {
    await refresh();
  });

  async function refresh() {
    try {
      agents = await listAgents();
    } catch (e) {
      error = String(e);
    }
  }

  async function toggleStatus(agent: Agent) {
    acting = { ...acting, [agent.id]: true };
    try {
      if (agent.status === 'running') {
        await stopAgent(agent.id);
      } else {
        await startAgent(agent.id);
      }
      await refresh();
    } catch (e) {
      error = String(e);
    } finally {
      const { [agent.id]: _, ...rest } = acting;
      acting = rest;
    }
  }

  async function remove(agent: Agent) {
    if (!confirm(`Delete agent "${agent.name}"?`)) return;
    try {
      await deleteAgent(agent.id);
      await refresh();
    } catch (e) {
      error = String(e);
    }
  }
</script>

<PageContainer>
  <PageHeader title="Agents" subtitle="Define and manage your voice agents">
    {#snippet actions()}
      <Button variant="primary" onclick={() => window.location.href = '/agents/new'}>+ New Agent</Button>
    {/snippet}
  </PageHeader>

  {#if error}
    <Alert variant="danger">{error}</Alert>
    <div style="height: var(--space-4)"></div>
  {/if}

  {#if agents.length === 0}
    <EmptyState
      icon="🤖"
      title="No agents yet"
      description="Create your first voice agent to get started."
    >
      {#snippet action()}
        <Button variant="primary" onclick={() => window.location.href = '/agents/new'}>+ New Agent</Button>
      {/snippet}
    </EmptyState>
  {:else}
    <div style="display: flex; flex-direction: column; gap: var(--space-3);">
      {#each agents as agent}
        <div class="card" style="padding: var(--space-5);">
          <div style="display: flex; align-items: flex-start; gap: var(--space-4);">
            <!-- Icon + status -->
            <div style="font-size: 1.5rem; line-height: 1; margin-top: 2px;">
              {PATTERN_ICONS[agent.pattern] ?? '🤖'}
            </div>

            <!-- Info -->
            <div style="flex: 1; min-width: 0;">
              <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2);">
                <span style="font-size: var(--font-size-sm); font-weight: 600;">{agent.name}</span>
                <Badge status={agent.status === 'running' ? 'running' : 'offline'}>
                  {agent.status}
                </Badge>
                <Badge data-type="functional">{agent.pattern.replace('_', ' ')}</Badge>
              </div>

              <div style="display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-2);">
                {#each agent.channels as ch}
                  <span style="font-size: var(--font-size-xs); color: var(--text-secondary); background: var(--surface-overlay); padding: 2px 6px; border-radius: var(--radius-sm);">
                    {CHANNEL_LABELS[ch] ?? ch}
                  </span>
                {/each}
              </div>

              <div style="font-size: var(--font-size-xs); color: var(--text-dim);">
                {agent.model} · {agent.mcp_servers.length === 0 ? 'all MCP servers' : agent.mcp_servers.join(', ')}
              </div>
            </div>

            <!-- Actions -->
            <div style="display: flex; gap: var(--space-2); align-items: center; flex-shrink: 0;">
              <Button
                variant={agent.status === 'running' ? 'ghost' : 'primary'}
                size="sm"
                disabled={acting[agent.id]}
                onclick={() => toggleStatus(agent)}
              >
                {agent.status === 'running' ? '■ Stop' : '▶ Start'}
              </Button>
              <Button variant="ghost" size="sm" onclick={() => window.location.href = `/agents/${agent.id}`}>
                Edit
              </Button>
              {#if agent.id !== 'default'}
                <Button variant="danger" size="sm" onclick={() => remove(agent)}>Delete</Button>
              {/if}
            </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</PageContainer>
