<script lang="ts">
  import { onMount } from 'svelte';
  import { PageContainer, PageHeader, Button, Card, Alert, Input } from 'wop-ui';
  import { getPatterns, createAgent, getMcpTools } from '$lib/api/agents';
  import { getMcp } from '$lib/api/config';
  import type { AgentPattern, McpServerTools, McpServer } from '$lib/types';

  const AVAILABLE_CHANNELS = [
    { id: 'telegram', label: 'Telegram' },
    { id: 'teams',    label: 'Microsoft Teams' },
    { id: 'whatsapp', label: 'WhatsApp' },
    { id: 'local',    label: 'Local mic' },
    { id: 'acs',      label: 'ACS Voice' },
  ];

  const MODELS = [
    'claude-sonnet-4-6',
    'claude-haiku-4-5-20251001',
    'claude-opus-4-6',
  ];

  let step = $state(1);
  let patterns = $state<AgentPattern[]>([]);
  let mcpServers = $state<McpServer[]>([]);
  let mcpTools = $state<McpServerTools[]>([]);
  let toolsLoading = $state(false);
  let expandedServer = $state<string | null>(null);

  // Form state
  let selectedPattern = $state('voice_assistant');
  let selectedMcps = $state<string[]>([]);  // empty = all
  let agentName = $state('My Voice Agent');
  let agentModel = $state('claude-sonnet-4-6');
  let selectedChannels = $state<string[]>(['telegram', 'local']);
  let memoryEnabled = $state(true);
  let maxTurns = $state(10);
  let promptOverride = $state('');
  let showPromptOverride = $state(false);
  let openclawUrl = $state('ws://openclaw-gateway:18789');
  let openclawAgentId = $state('voice-agent');

  let error = $state('');
  let saving = $state(false);

  onMount(async () => {
    try {
      [patterns, mcpServers] = await Promise.all([getPatterns(), getMcp().then(d => d.servers)]);
    } catch (e) {
      error = String(e);
    }
  });

  async function loadTools() {
    if (mcpTools.length > 0) return;
    toolsLoading = true;
    try {
      mcpTools = await getMcpTools();
    } catch (e) {
      error = String(e);
    } finally {
      toolsLoading = false;
    }
  }

  function toggleMcp(name: string) {
    if (selectedMcps.includes(name)) {
      selectedMcps = selectedMcps.filter(s => s !== name);
    } else {
      selectedMcps = [...selectedMcps, name];
    }
  }

  function toggleChannel(id: string) {
    if (selectedChannels.includes(id)) {
      selectedChannels = selectedChannels.filter(c => c !== id);
    } else {
      selectedChannels = [...selectedChannels, id];
    }
  }

  function goToStep(n: number) {
    if (n === 2) loadTools();
    step = n;
  }

  async function finish() {
    saving = true;
    error = '';
    try {
      await createAgent({
        name: agentName,
        pattern: selectedPattern,
        model: agentModel,
        mcp_servers: selectedMcps,
        channels: selectedChannels,
        memory: { enabled: memoryEnabled, max_turns: maxTurns },
        system_prompt_override: showPromptOverride && promptOverride ? promptOverride : null,
        openclaw_url: openclawUrl,
        openclaw_agent_id: openclawAgentId,
      });
      window.location.href = '/agents';
    } catch (e) {
      error = String(e);
    } finally {
      saving = false;
    }
  }

  function toolsForServer(name: string): McpServerTools | undefined {
    return mcpTools.find(s => s.name === name);
  }
</script>

<PageContainer>
  <PageHeader
    title="New Agent"
    subtitle={`Step ${step} of 3 — ${step === 1 ? 'Choose a pattern' : step === 2 ? 'Select MCP servers' : 'Configure'}`}
  >
    {#snippet actions()}
      <Button variant="ghost" onclick={() => window.location.href = '/agents'}>Cancel</Button>
    {/snippet}
  </PageHeader>

  <!-- Step indicator -->
  <div style="display: flex; gap: var(--space-2); margin-bottom: var(--space-6);">
    {#each [1,2,3] as s}
      <div style="
        width: 28px; height: 28px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: var(--font-size-xs); font-weight: 600;
        background: {s === step ? 'var(--accent)' : s < step ? 'var(--success-muted)' : 'var(--surface-overlay)'};
        color: {s === step ? '#fff' : s < step ? 'var(--success)' : 'var(--text-dim)'};
        border: 1px solid {s === step ? 'var(--accent)' : s < step ? 'var(--success)' : 'var(--surface-border)'};
      ">{s}</div>
      {#if s < 3}
        <div style="flex: 1; height: 1px; background: var(--surface-border); margin: auto;"></div>
      {/if}
    {/each}
  </div>

  {#if error}
    <Alert variant="danger">{error}</Alert>
    <div style="height: var(--space-4)"></div>
  {/if}

  <!-- ── Step 1: Pattern ── -->
  {#if step === 1}
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--space-4);">
      {#each patterns as p}
        <button
          type="button"
          onclick={() => { selectedPattern = p.id; }}
          style="
            text-align: left; cursor: pointer;
            border-radius: var(--radius-lg);
            border: 2px solid {selectedPattern === p.id ? 'var(--accent)' : 'var(--surface-border-subtle)'};
            background: {selectedPattern === p.id ? 'var(--accent-muted)' : 'var(--surface-raised)'};
            padding: var(--space-5);
            transition: var(--transition-colors);
            font-family: var(--font);
          "
        >
          <div style="font-size: 2rem; margin-bottom: var(--space-3);">{p.icon}</div>
          <div style="font-size: var(--font-size-sm); font-weight: 600; margin-bottom: var(--space-2);">{p.name}</div>
          <div style="font-size: var(--font-size-xs); color: var(--text-secondary); line-height: 1.5;">{p.description}</div>
        </button>
      {/each}
    </div>
    <div style="margin-top: var(--space-6); display: flex; justify-content: flex-end;">
      <Button variant="primary" onclick={() => goToStep(2)}>Next →</Button>
    </div>
  {/if}

  <!-- ── Step 2: MCP Servers ── -->
  {#if step === 2}
    <div style="margin-bottom: var(--space-3);">
      <p style="font-size: var(--font-size-xs); color: var(--text-secondary);">
        {selectedPattern === 'openclaw_agent'
          ? 'OpenClaw agents manage their own tools and skills via SOUL.md.'
          : 'Select which MCP servers this agent can use. Leave all unchecked to use all enabled servers.'}
      </p>
    </div>

    {#if selectedPattern === 'openclaw_agent'}
      <Card>
        <div style="display: flex; flex-direction: column; gap: var(--space-4);">
          <p style="font-size: var(--font-size-sm); color: var(--text-secondary); margin: 0;">
            Configure the OpenClaw gateway connection below.
          </p>
          <div class="form-field">
            <label class="label" for="openclaw-url">Gateway URL</label>
            <Input
              id="openclaw-url"
              bind:value={openclawUrl}
              placeholder="ws://openclaw-gateway:18789"
            />
          </div>
          <div class="form-field">
            <label class="label" for="openclaw-agent-id">Agent ID</label>
            <Input
              id="openclaw-agent-id"
              bind:value={openclawAgentId}
              placeholder="voice-agent"
            />
          </div>
        </div>
      </Card>
    {:else if toolsLoading}
      <div style="color: var(--text-dim); font-size: var(--font-size-sm); padding: var(--space-4);">Loading tools…</div>
    {:else}
      <div style="display: flex; flex-direction: column; gap: var(--space-3);">
        {#each mcpServers as srv}
          {@const srvTools = toolsForServer(srv.name)}
          {@const checked = selectedMcps.length === 0 || selectedMcps.includes(srv.name)}
          <Card>
            <div style="display: flex; align-items: center; gap: var(--space-3);">
              <input
                type="checkbox"
                id="mcp-{srv.name}"
                checked={checked}
                onchange={() => toggleMcp(srv.name)}
                style="width: 16px; height: 16px; accent-color: var(--accent); cursor: pointer;"
              />
              <label for="mcp-{srv.name}" style="flex: 1; cursor: pointer;">
                <span style="font-size: var(--font-size-sm); font-weight: 500;">{srv.name}</span>
                <span style="font-size: var(--font-size-xs); color: var(--text-dim); margin-left: var(--space-2);">{srv.description}</span>
              </label>
              {#if srvTools}
                <span style="font-size: var(--font-size-xs); color: var(--text-secondary);">{srvTools.tool_count} tools</span>
                <button
                  type="button"
                  class="btn btn-ghost btn-sm"
                  onclick={() => expandedServer = expandedServer === srv.name ? null : srv.name}
                >
                  {expandedServer === srv.name ? '▲ hide' : '▼ show'}
                </button>
              {/if}
            </div>
            {#if expandedServer === srv.name && srvTools}
              <div style="margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--surface-border-subtle);">
                {#each srvTools.tools as tool}
                  <div style="padding: var(--space-2) 0; border-bottom: 1px solid var(--surface-border-subtle);">
                    <div style="font-size: var(--font-size-xs); font-weight: 500; color: var(--accent-bright);">{tool.name}</div>
                    <div style="font-size: var(--font-size-xs); color: var(--text-dim); margin-top: 2px;">{tool.description}</div>
                  </div>
                {/each}
              </div>
            {/if}
          </Card>
        {/each}
      </div>
    {/if}

    <div style="margin-top: var(--space-6); display: flex; justify-content: space-between;">
      <Button variant="ghost" onclick={() => goToStep(1)}>← Back</Button>
      <Button variant="primary" onclick={() => goToStep(3)}>Next →</Button>
    </div>
  {/if}

  <!-- ── Step 3: Configure ── -->
  {#if step === 3}
    <div style="display: flex; flex-direction: column; gap: var(--space-5); max-width: 560px;">
      <div class="form-field">
        <label class="label" for="agent-name">Agent name</label>
        <input class="input" id="agent-name" bind:value={agentName} placeholder="My Voice Agent" />
      </div>

      <div class="form-field">
        <label class="label" for="agent-model">Model</label>
        <select class="select" id="agent-model" bind:value={agentModel}>
          {#each MODELS as m}
            <option value={m}>{m}</option>
          {/each}
        </select>
      </div>

      <div class="form-field">
        <span class="label">Channels</span>
        <div style="display: flex; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-1);">
          {#each AVAILABLE_CHANNELS as ch}
            <label style="display: flex; align-items: center; gap: var(--space-2); cursor: pointer; font-size: var(--font-size-sm);">
              <input
                type="checkbox"
                checked={selectedChannels.includes(ch.id)}
                onchange={() => toggleChannel(ch.id)}
                style="accent-color: var(--accent);"
              />
              {ch.label}
            </label>
          {/each}
        </div>
      </div>

      <div class="form-field">
        <span class="label">Memory</span>
        <div style="display: flex; align-items: center; gap: var(--space-4); margin-top: var(--space-1);">
          <label style="display: flex; align-items: center; gap: var(--space-2); cursor: pointer; font-size: var(--font-size-sm);">
            <input type="checkbox" bind:checked={memoryEnabled} style="accent-color: var(--accent);" />
            Remember conversation history
          </label>
          {#if memoryEnabled}
            <div style="display: flex; align-items: center; gap: var(--space-2);">
              <span style="font-size: var(--font-size-xs); color: var(--text-dim);">Max turns:</span>
              <input
                type="number"
                class="input"
                bind:value={maxTurns}
                min="1" max="50"
                style="width: 64px;"
              />
            </div>
          {/if}
        </div>
      </div>

      <div class="form-field">
        <label style="display: flex; align-items: center; gap: var(--space-2); cursor: pointer; font-size: var(--font-size-sm);">
          <input type="checkbox" bind:checked={showPromptOverride} style="accent-color: var(--accent);" />
          <span class="label" style="margin: 0;">Custom system prompt (override pattern)</span>
        </label>
        {#if showPromptOverride}
          <textarea
            class="textarea"
            bind:value={promptOverride}
            rows={6}
            placeholder="Enter a custom system prompt…"
            style="margin-top: var(--space-2);"
          ></textarea>
        {/if}
      </div>
    </div>

    <div style="margin-top: var(--space-6); display: flex; justify-content: space-between;">
      <Button variant="ghost" onclick={() => goToStep(2)}>← Back</Button>
      <Button variant="primary" disabled={saving || !agentName.trim()} onclick={finish}>
        {saving ? 'Creating…' : '✓ Create Agent'}
      </Button>
    </div>
  {/if}
</PageContainer>
