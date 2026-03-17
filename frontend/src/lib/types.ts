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

export interface AgentPattern {
  id: string;
  name: string;
  description: string;
  icon: string;
  recommended_mcps: string[];
}

export interface AgentMemory {
  enabled: boolean;
  max_turns: number;
}

export interface Agent {
  id: string;
  name: string;
  pattern: string;
  model: string;
  mcp_servers: string[];
  channels: string[];
  memory: AgentMemory;
  system_prompt_override: string | null;
  status: 'stopped' | 'running' | 'paused';
}

export interface McpTool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface McpServerTools {
  name: string;
  description: string;
  tool_count: number;
  tools: McpTool[];
}
