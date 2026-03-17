<script lang="ts">
  import { onMount } from 'svelte';
  import { PageContainer, PageHeader, Badge, Card, EmptyState, Alert } from 'wop-ui';
  import { getChannels } from '$lib/api/config';

  const CHANNELS = [
    { key: 'telegram', label: 'Telegram', icon: '✈️', webhook: null, hint: 'Set TELEGRAM_BOT_TOKEN' },
    { key: 'teams',    label: 'Microsoft Teams', icon: '💼', webhook: '/webhook/teams', hint: 'Set TEAMS_APP_ID + TEAMS_APP_PASSWORD' },
    { key: 'whatsapp', label: 'WhatsApp (Twilio)', icon: '📱', webhook: '/webhook/whatsapp', hint: 'Set TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN' },
    { key: 'acs',      label: 'ACS Voice', icon: '📞', webhook: '/webhook/acs/call', hint: 'Set ACS_CONNECTION_STRING' }
  ] as const;

  let config = $state<Record<string, { configured: boolean }>>({});
  let error = $state('');

  onMount(async () => {
    try {
      config = await getChannels() as Record<string, { configured: boolean }>;
    } catch (e) {
      error = String(e);
    }
  });
</script>

<PageContainer>
  <PageHeader title="Channels" subtitle="Connect messaging and voice channels" />

  {#if error}<Alert variant="danger">{error}</Alert><div style="height:var(--space-4)"></div>{/if}

  <div style="display: flex; flex-direction: column; gap: var(--space-3);">
    {#each CHANNELS as ch}
      {@const configured = config[ch.key]?.configured ?? false}
      <div class="card">
        <div style="display: flex; align-items: center; gap: var(--space-4);">
          <span style="font-size: 1.5rem;">{ch.icon}</span>
          <div style="flex: 1;">
            <div style="display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1);">
              <span style="font-size: var(--font-size-sm); font-weight: 500;">{ch.label}</span>
              <Badge status={configured ? 'running' : 'offline'}>{configured ? 'active' : 'not configured'}</Badge>
            </div>
            {#if ch.webhook}
              <div style="font-size: var(--font-size-xs); color: var(--text-dim); font-family: var(--font);">
                webhook: {ch.webhook}
              </div>
            {/if}
            {#if !configured}
              <div style="font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: var(--space-1);">
                {ch.hint} → <a href="/credentials" style="color: var(--accent-bright);">Credentials</a>
              </div>
            {/if}
          </div>
        </div>
      </div>
    {/each}
  </div>
</PageContainer>
