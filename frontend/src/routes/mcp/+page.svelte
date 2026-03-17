<script lang="ts">
  import { onMount } from 'svelte';
  import { PageContainer, PageHeader, Badge, Alert, EmptyState } from 'wop-ui';
  import { getStatus } from '$lib/api/session';
  import type { McpServer } from '$lib/types';

  // MCP server list comes from /status
  let servers = $state<McpServer[]>([]);
  let error = $state('');
  let toggling = $state<Record<string, boolean>>({});

  onMount(async () => {
    try {
      const s = await getStatus();
      servers = s.mcp_servers;
    } catch (e) {
      error = String(e);
    }
  });

  async function toggle(name: string, enabled: boolean) {
    toggling = { ...toggling, [name]: true };
    try {
      // POST /config/mcp to toggle
      const res = await fetch('/config/mcp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, enabled })
      });
      if (!res.ok) throw new Error('Failed to toggle');
      servers = servers.map((s) => s.name === name ? { ...s, enabled } : s);
    } catch (e) {
      error = String(e);
    } finally {
      const { [name]: _, ...rest } = toggling;
      toggling = rest;
    }
  }
</script>

<PageContainer>
  <PageHeader title="MCP Servers" subtitle="Connected tool servers" />

  {#if error}<Alert variant="danger">{error}</Alert><div style="height:var(--space-4)"></div>{/if}

  {#if servers.length === 0}
    <EmptyState icon="🔧" title="No MCP servers configured" description="Add servers to mcp_servers.yaml to get started." />
  {:else}
    <div style="display: flex; flex-direction: column; gap: var(--space-3);">
      {#each servers as srv}
        <div class="card">
          <div style="display: flex; align-items: center; gap: var(--space-4);">
            <div style="flex: 1;">
              <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1);">
                <span style="font-size: var(--font-size-sm); font-weight: 500;">{srv.name}</span>
                <Badge status={srv.enabled ? 'running' : 'offline'}>{srv.enabled ? 'enabled' : 'disabled'}</Badge>
              </div>
              <div style="font-size: var(--font-size-xs); color: var(--text-dim);">{srv.description}</div>
            </div>
            <button
              type="button"
              class="btn btn-ghost btn-sm"
              disabled={toggling[srv.name]}
              onclick={() => toggle(srv.name, !srv.enabled)}
            >
              {srv.enabled ? 'Disable' : 'Enable'}
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</PageContainer>
