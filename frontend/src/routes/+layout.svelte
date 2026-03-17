<script lang="ts">
  import '../app.css';
  import { AppLayout, Sidebar, NavItem } from 'wop-ui';
  import type { Snippet } from 'svelte';

  interface Props { children: Snippet; }
  let { children }: Props = $props();
</script>

<AppLayout>
  {#snippet sidebar()}
    <Sidebar>
      {#snippet header()}
        <div style="font-size: var(--font-size-sm); font-weight: 600; color: var(--text-primary);">
          voice-mcp
        </div>
        <div style="font-size: var(--font-size-xs); color: var(--text-dim); margin-top: var(--space-1);">
          voice agent platform
        </div>
      {/snippet}

      {#snippet nav()}
        <NavItem href="/agents">🤖 Agents</NavItem>
        <NavItem href="/session">🎙 Session</NavItem>
        <NavItem href="/credentials">🔑 Credentials</NavItem>
        <NavItem href="/channels">📡 Channels</NavItem>
        <NavItem href="/mcp">🔧 MCP Servers</NavItem>
      {/snippet}

      {#snippet footer()}
        v0.1.0
      {/snippet}
    </Sidebar>
  {/snippet}

  {@render children()}
</AppLayout>
