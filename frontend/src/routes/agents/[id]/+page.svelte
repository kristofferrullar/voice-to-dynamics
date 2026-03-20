<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { PageContainer, PageHeader, Button, Badge, Alert, Tabs } from 'wop-ui';
  import { getAgent, updateAgent, startAgent, stopAgent, getMcpTools } from '$lib/api/agents';
  import { createLogStream } from '$lib/api/sse';
  import type { Agent, McpServerTools } from '$lib/types';

  const TABS = [
    { id: 'overview',  label: 'Overview' },
    { id: 'tools',     label: 'Tools' },
    { id: 'channels',  label: 'Channels' },
    { id: 'logs',      label: 'Logs' },
  ];

  const CHANNEL_LABELS: Record<string, string> = {
    telegram: 'Telegram', teams: 'Microsoft Teams',
    whatsapp: 'WhatsApp', local: 'Local mic', acs: 'ACS Voice'
  };

  const ALL_CHANNELS = ['telegram', 'teams', 'whatsapp', 'local', 'acs'];

  const MODELS = ['claude-sonnet-4-6', 'claude-haiku-4-5-20251001', 'claude-opus-4-6'];

  let activeTab = $state('overview');
  let agent = $state<Agent | null>(null);
  let tools = $state<McpServerTools[]>([]);
  let toolsLoaded = $state(false);
  let error = $state('');
  let saving = $state(false);
  let acting = $state(false);
  let logLines = $state<string[]>([]);
  let logContainer = $state<HTMLElement | undefined>();
  let stopStream: (() => void) | null = null;

  // Editable fields
  let editName = $state('');
  let editModel = $state('');
  let editChannels = $state<string[]>([]);
  let editPrompt = $state('');
  let editMemoryEnabled = $state(true);
  let editMaxTurns = $state(10);
  let dirty = $state(false);

  const agentId = $derived($page.params.id);

  onMount(async () => {
    try {
      agent = await getAgent(agentId);
      editName = agent.name;
      editModel = agent.model;
      editChannels = [...agent.channels];
      editPrompt = agent.system_prompt_override ?? '';
      editMemoryEnabled = agent.memory.enabled;
      editMaxTurns = agent.memory.max_turns;
    } catch (e) {
      error = String(e);
    }
    stopStream = createLogStream((line) => {
      logLines = [...logLines.slice(-299), line];
      setTimeout(() => { if (logContainer) logContainer.scrollTop = logContainer.scrollHeight; }, 0);
    }, undefined, agentId);
  });

  onDestroy(() => stopStream?.());

  async function loadTools() {
    if (toolsLoaded) return;
    try {
      tools = await getMcpTools();
      toolsLoaded = true;
    } catch (e) {
      error = String(e);
    }
  }

  function onTabChange(id: string) {
    activeTab = id;
    if (id === 'tools') loadTools();
  }

  async function toggleStatus() {
    if (!agent) return;
    acting = true;
    try {
      if (agent.status === 'running') {
        await stopAgent(agent.id);
        agent = { ...agent, status: 'stopped' };
      } else {
        await startAgent(agent.id);
        agent = { ...agent, status: 'running' };
      }
    } catch (e) {
      error = String(e);
    } finally {
      acting = false;
    }
  }

  async function save() {
    if (!agent) return;
    saving = true; error = '';
    try {
      const updated = await updateAgent(agent.id, {
        name: editName,
        model: editModel,
        channels: editChannels,
        system_prompt_override: editPrompt || null,
        memory: { enabled: editMemoryEnabled, max_turns: editMaxTurns },
      });
      agent = updated;
      dirty = false;
    } catch (e) {
      error = String(e);
    } finally {
      saving = false;
    }
  }

  function toggleChannel(ch: string) {
    if (editChannels.includes(ch)) {
      editChannels = editChannels.filter(c => c !== ch);
    } else {
      editChannels = [...editChannels, ch];
    }
    dirty = true;
  }

  function logColor(line: string): string {
    if (line.includes('❌') || line.toLowerCase().includes('error')) return 'var(--danger)';
    if (line.includes('⚠️') || line.toLowerCase().includes('warn')) return 'var(--warning)';
    if (line.includes('✅') || line.includes('▶') || line.includes('🤖')) return 'var(--success)';
    return 'var(--text-secondary)';
  }
</script>

<PageContainer>
  {#if !agent}
    {#if error}
      <Alert variant="danger">{error}</Alert>
    {:else}
      <div style="color: var(--text-dim); font-size: var(--font-size-sm);">Loading…</div>
    {/if}
  {:else}
    <PageHeader title={agent.name} subtitle="{agent.pattern.replace('_',' ')} · {agent.model}">
      {#snippet actions()}
        <Badge status={agent.status === 'running' ? 'running' : 'offline'}>{agent.status}</Badge>
        <Button
          variant={agent.status === 'running' ? 'ghost' : 'primary'}
          size="sm"
          disabled={acting}
          onclick={toggleStatus}
        >
          {agent.status === 'running' ? '■ Stop' : '▶ Start'}
        </Button>
        <Button variant="ghost" size="sm" onclick={() => window.location.href = '/agents'}>← Agents</Button>
      {/snippet}
    </PageHeader>

    {#if error}
      <Alert variant="danger">{error}</Alert>
      <div style="height: var(--space-3)"></div>
    {/if}

    <Tabs tabs={TABS} active={activeTab} onchange={onTabChange} />

    <div style="margin-top: var(--space-5);">

      <!-- Overview tab -->
      {#if activeTab === 'overview'}
        <div style="max-width: 560px; display: flex; flex-direction: column; gap: var(--space-5);">
          <div class="form-field">
            <label class="label" for="name">Name</label>
            <input class="input" id="name" bind:value={editName} oninput={() => dirty = true} />
          </div>

          <div class="form-field">
            <label class="label" for="model">Model</label>
            <select class="select" id="model" bind:value={editModel} onchange={() => dirty = true}>
              {#each MODELS as m}
                <option value={m}>{m}</option>
              {/each}
            </select>
          </div>

          <div class="form-field">
            <span class="label">Memory</span>
            <div style="display: flex; align-items: center; gap: var(--space-4); margin-top: var(--space-1);">
              <label style="display: flex; align-items: center; gap: var(--space-2); cursor: pointer; font-size: var(--font-size-sm);">
                <input type="checkbox" bind:checked={editMemoryEnabled} onchange={() => dirty = true} style="accent-color: var(--accent);" />
                Conversation history
              </label>
              {#if editMemoryEnabled}
                <div style="display: flex; align-items: center; gap: var(--space-2);">
                  <span style="font-size: var(--font-size-xs); color: var(--text-dim);">Max turns:</span>
                  <input type="number" class="input" bind:value={editMaxTurns} oninput={() => dirty = true} min="1" max="50" style="width: 64px;" />
                </div>
              {/if}
            </div>
          </div>

          <div class="form-field">
            <label class="label" for="prompt">System prompt override</label>
            <textarea class="textarea" id="prompt" bind:value={editPrompt} oninput={() => dirty = true} rows={6} placeholder="Leave empty to use the pattern's default prompt…"></textarea>
            <div class="helper-text">Overrides the "{agent.pattern.replace('_',' ')}" pattern prompt when set.</div>
          </div>

          {#if dirty}
            <div style="display: flex; gap: var(--space-2);">
              <Button variant="primary" disabled={saving} onclick={save}>{saving ? 'Saving…' : 'Save changes'}</Button>
              <Button variant="ghost" onclick={() => {
                editName = agent?.name ?? '';
                editModel = agent?.model ?? '';
                editChannels = [...(agent?.channels ?? [])];
                editPrompt = agent?.system_prompt_override ?? '';
                dirty = false;
              }}>Discard</Button>
            </div>
          {/if}
        </div>
      {/if}

      <!-- Tools tab -->
      {#if activeTab === 'tools'}
        {#if !toolsLoaded}
          <div style="color: var(--text-dim); font-size: var(--font-size-sm);">Loading tools…</div>
        {:else if tools.length === 0}
          <div style="color: var(--text-dim); font-size: var(--font-size-sm);">No tools available.</div>
        {:else}
          {#each tools as srv}
            <div style="margin-bottom: var(--space-5);">
              <div style="font-size: var(--font-size-xs); font-weight: 500; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-dim); margin-bottom: var(--space-3);">
                {srv.name} — {srv.description} ({srv.tool_count} tools)
              </div>
              <div style="display: flex; flex-direction: column; gap: var(--space-2);">
                {#each srv.tools as tool}
                  <div class="card" style="padding: var(--space-3) var(--space-4);">
                    <div style="font-size: var(--font-size-xs); font-weight: 600; color: var(--accent-bright); margin-bottom: 2px;">{tool.name}</div>
                    <div style="font-size: var(--font-size-xs); color: var(--text-secondary);">{tool.description}</div>
                  </div>
                {/each}
              </div>
            </div>
          {/each}
        {/if}
      {/if}

      <!-- Channels tab -->
      {#if activeTab === 'channels'}
        <div style="max-width: 480px; display: flex; flex-direction: column; gap: var(--space-3);">
          {#each ALL_CHANNELS as ch}
            {@const active = editChannels.includes(ch)}
            <div class="card" style="padding: var(--space-4);">
              <label style="display: flex; align-items: center; gap: var(--space-3); cursor: pointer;">
                <input type="checkbox" checked={active} onchange={() => toggleChannel(ch)} style="width: 16px; height: 16px; accent-color: var(--accent); cursor: pointer;" />
                <div style="flex: 1;">
                  <div style="font-size: var(--font-size-sm); font-weight: 500;">{CHANNEL_LABELS[ch]}</div>
                </div>
                <Badge status={active ? 'running' : 'offline'}>{active ? 'enabled' : 'disabled'}</Badge>
              </label>
            </div>
          {/each}
          {#if dirty}
            <Button variant="primary" disabled={saving} onclick={save}>{saving ? 'Saving…' : 'Save channels'}</Button>
          {/if}
        </div>
      {/if}

      <!-- Logs tab -->
      {#if activeTab === 'logs'}
        <div
          bind:this={logContainer}
          class="card"
          style="height: 420px; overflow-y: auto; padding: var(--space-4);"
        >
          {#if logLines.length === 0}
            <div style="color: var(--text-dim); font-size: var(--font-size-xs);">Waiting for logs…</div>
          {:else}
            {#each logLines as line}
              <div style="font-size: var(--font-size-xs); color: {logColor(line)}; line-height: 1.6;">{line}</div>
            {/each}
          {/if}
        </div>
      {/if}

    </div>
  {/if}
</PageContainer>
