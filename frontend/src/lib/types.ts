export interface SessionStatus {
  status: 'stopped' | 'running' | 'paused';
  language: string;
  voice: string;
  mcp_servers: McpServer[];
}

export interface McpServer {
  name: string;
  enabled: boolean;
  description: string;
}

export interface Credential {
  key: string;
  label: string;
  set: boolean;
  preview: string;
  description: string;
  group: 'Core' | 'MCP Servers' | 'Channels';
}

export interface ChannelStatus {
  configured: boolean;
  [key: string]: unknown;
}

export interface ChannelsConfig {
  teams: ChannelStatus;
  whatsapp: ChannelStatus;
  acs: ChannelStatus;
  telegram: ChannelStatus;
}
