<script lang="ts">
  import { onMount } from 'svelte';
  import { PageContainer, PageHeader, Tabs, Badge, Alert, Button } from 'wop-ui';
  import { getCredentials, updateCredentials } from '$lib/api/config';
  import type { Credential } from '$lib/types';

  type Group = 'Core' | 'MCP Servers' | 'Channels';
  const TABS: { id: Group; label: string }[] = [
    { id: 'Core', label: 'Core' },
    { id: 'MCP Servers', label: 'MCP Servers' },
    { id: 'Channels', label: 'Channels' }
  ];

  let credentials = $state<Credential[]>([]);
  let activeTab = $state<Group>('Core');
  let editing = $state<Record<string, string>>({});
  let saving = $state<Record<string, boolean>>({});
  let error = $state('');
  let successKey = $state('');

  onMount(async () => {
    try {
      const data = await getCredentials();
      credentials = data.credentials;
    } catch (e) {
      error = String(e);
    }
  });

  const visible = $derived(credentials.filter((c) => c.group === activeTab));

  function startEdit(key: string) {
    editing = { ...editing, [key]: '' };
  }

  function cancelEdit(key: string) {
    const { [key]: _, ...rest } = editing;
    editing = rest;
  }

  async function save(key: string) {
    const value = editing[key];
    if (!value) return;
    saving = { ...saving, [key]: true };
    try {
      await updateCredentials({ [key]: value });
      successKey = key;
      cancelEdit(key);
      const data = await getCredentials();
      credentials = data.credentials;
      setTimeout(() => (successKey = ''), 2000);
    } catch (e) {
      error = String(e);
    } finally {
      const { [key]: _, ...rest } = saving;
      saving = rest;
    }
  }
</script>

<PageContainer>
  <PageHeader title="Credentials" subtitle="API keys and secrets for all integrations" />

  {#if error}<Alert variant="danger">{error}</Alert><div style="height:var(--space-4)"></div>{/if}

  <Tabs tabs={TABS} active={activeTab} onchange={(id) => (activeTab = id as Group)} />

  <div style="margin-top: var(--space-6); display: flex; flex-direction: column; gap: var(--space-3);">
    {#each visible as cred}
      <div class="card">
        <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4);">
          <div style="flex: 1;">
            <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1);">
              <Badge status={cred.set ? 'done' : 'open'}>{cred.set ? 'set' : 'not set'}</Badge>
              <span style="font-size: var(--font-size-sm); font-weight: 500;">{cred.label}</span>
              {#if successKey === cred.key}<span style="color: var(--success); font-size: var(--font-size-xs);">✓ saved</span>{/if}
            </div>
            <div style="font-size: var(--font-size-xs); color: var(--text-dim);">{cred.description}</div>
            {#if cred.set && cred.preview}
              <div style="font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: var(--space-1); font-family: var(--font);">{cred.preview}</div>
            {/if}
          </div>

          {#if editing[cred.key] !== undefined}
            <div style="display: flex; gap: var(--space-2); align-items: center; flex-shrink: 0;">
              <input
                class="input"
                type="password"
                bind:value={editing[cred.key]}
                placeholder="Enter value…"
                style="width: 240px;"
                onkeydown={(e) => e.key === 'Enter' && save(cred.key)}
              />
              <Button variant="primary" size="sm" disabled={saving[cred.key]} onclick={() => save(cred.key)}>Save</Button>
              <Button variant="ghost" size="sm" onclick={() => cancelEdit(cred.key)}>Cancel</Button>
            </div>
          {:else}
            <Button variant="ghost" size="sm" onclick={() => startEdit(cred.key)}>Edit</Button>
          {/if}
        </div>
      </div>
    {/each}
  </div>
</PageContainer>
