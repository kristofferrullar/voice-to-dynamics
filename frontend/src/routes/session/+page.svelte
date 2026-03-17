<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { PageContainer, PageHeader, Button, Badge, Alert, Select } from 'wop-ui';
  import { getStatus, startSession, stopSession, pauseSession, resumeSession, setLanguage, sendText } from '$lib/api/session';
  import { createLogStream } from '$lib/api/sse';
  import type { SessionStatus } from '$lib/types';

  let status = $state<SessionStatus | null>(null);
  let logLines = $state<string[]>([]);
  let error = $state('');
  let loading = $state(false);
  let textInput = $state('');
  let textReply = $state('');
  let showTextInput = $state(false);
  let logContainer = $state<HTMLElement | undefined>();

  let stopStream: (() => void) | null = null;

  onMount(async () => {
    await refresh();
    stopStream = createLogStream((line) => {
      logLines = [...logLines.slice(-299), line];
      setTimeout(() => {
        if (logContainer) logContainer.scrollTop = logContainer.scrollHeight;
      }, 0);
    });
  });

  onDestroy(() => stopStream?.());

  async function refresh() {
    try {
      status = await getStatus();
    } catch (e) {
      error = String(e);
    }
  }

  async function act(fn: () => Promise<void>) {
    loading = true; error = '';
    try { await fn(); await refresh(); }
    catch (e) { error = String(e); }
    finally { loading = false; }
  }

  async function handleSendText() {
    if (!textInput.trim()) return;
    loading = true;
    try {
      const res = await sendText(textInput);
      textReply = res.reply;
      textInput = '';
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  }

  function logColor(line: string): string {
    if (line.includes('❌') || line.toLowerCase().includes('error')) return 'var(--danger)';
    if (line.includes('⚠️') || line.toLowerCase().includes('warn')) return 'var(--warning)';
    if (line.includes('✅') || line.includes('▶') || line.includes('🤖')) return 'var(--success)';
    return 'var(--text-secondary)';
  }
</script>

<PageContainer>
  <PageHeader title="Session" subtitle="Start and manage the voice agent">
    {#snippet actions()}
      <Select
        value={status?.language ?? 'en-US'}
        onchange={(e) => act(() => setLanguage(e.currentTarget.value))}
      >
        <option value="en-US">English</option>
        <option value="sv-SE">Swedish</option>
      </Select>
    {/snippet}
  </PageHeader>

  {#if error}
    <Alert variant="danger" >{error}</Alert>
    <div style="margin-bottom: var(--space-4)"></div>
  {/if}

  <!-- Controls -->
  <div style="display: flex; gap: var(--space-3); align-items: center; margin-bottom: var(--space-6);">
    {#if status?.status === 'stopped'}
      <Button variant="primary" disabled={loading} onclick={() => act(startSession)}>▶ Start</Button>
    {:else if status?.status === 'running'}
      <Button variant="ghost" disabled={loading} onclick={() => act(pauseSession)}>⏸ Pause</Button>
      <Button variant="danger" disabled={loading} onclick={() => act(stopSession)}>■ Stop</Button>
    {:else if status?.status === 'paused'}
      <Button variant="primary" disabled={loading} onclick={() => act(resumeSession)}>▶ Resume</Button>
      <Button variant="danger" disabled={loading} onclick={() => act(stopSession)}>■ Stop</Button>
    {/if}

    {#if status}
      <Badge status={status.status}>{status.status}</Badge>
    {/if}

    <button
      type="button"
      class="btn btn-ghost btn-sm"
      style="margin-left: auto"
      onclick={() => (showTextInput = !showTextInput)}
    >
      💬 Text input
    </button>
  </div>

  <!-- Text input panel -->
  {#if showTextInput}
    <div class="card" style="margin-bottom: var(--space-4);">
      <div style="display: flex; gap: var(--space-3);">
        <input
          class="input"
          bind:value={textInput}
          placeholder="Type a message to the agent…"
          onkeydown={(e) => e.key === 'Enter' && handleSendText()}
        />
        <Button variant="primary" disabled={loading || !textInput.trim()} onclick={handleSendText}>Send</Button>
      </div>
      {#if textReply}
        <div style="margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary);">
          {textReply}
        </div>
      {/if}
    </div>
  {/if}

  <!-- Log pane -->
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
</PageContainer>
