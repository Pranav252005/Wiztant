// ─────────────────────────────────────────────────────────────
// ARCHIVED: WizType BYOK helpers — replaced by WizPrompt in Settings.tsx
// Original location: ui/whiztant-overlay/src/renderer/settings/wiztype.ts
// Kept for reference; no longer imported by the renderer bundle.
// ─────────────────────────────────────────────────────────────

export type WizModel = { key: string; name: string; sizeGb: number };
export type WizState = {
  enabled: boolean;
  currentModel: string;
  models: WizModel[];
};
export type WizAPI = {
  getState?: () => Promise<WizState>;
  setEnabled?: (v: boolean) => Promise<boolean>;
  setModel?: (model: string) => Promise<boolean>;
  setCustomModel?: (
    modelInput: string,
    provider?: string,
  ) => Promise<boolean>;
  getCustomModel?: () => Promise<{
    modelInput: string;
    provider: string | null;
  } | null>;
};

export type Validation = {
  isValid: boolean;
  emoji: string;
  message: string;
  requiresFallback: boolean;
  provider: string;
};

declare global {
  interface Window {
    electronAPI?: {
      isElectron?: boolean;
      wiztype?: WizAPI;
      ENV?: Record<string, string>;
      [key: string]: unknown;
    };
  }
}

const PROVIDER_PATTERNS: Record<string, { patterns: RegExp[]; envKey: string }> = {
  openai: {
    patterns: [/^gpt-[0-9]/, /^o[0-9]/, /^text-embedding/],
    envKey: 'OPENAI_API_KEY',
  },
  anthropic: {
    patterns: [/^claude-/, /^anthropic/],
    envKey: 'ANTHROPIC_API_KEY',
  },
  mistral: {
    patterns: [/^mistral-/, /^mixtral-/, /^codestral-/],
    envKey: 'MISTRAL_API_KEY',
  },
  openrouter: {
    patterns: [/^qwen\//, /:free$/, /^openrouter\//],
    envKey: 'OPENROUTER_API_KEY',
  },
  google: { patterns: [/^gemini-/, /^palm-/], envKey: 'GOOGLE_API_KEY' },
};

const LOCAL_PATTERNS = [
  /^http:\/\/localhost:/,
  /^http:\/\/127\.0\.0\.1:/,
  /^https?:\/\/.*:\d+\/v1$/,
];
const AMBIGUOUS_MODELS = [
  'mistral-large',
  'llama-3',
  'llama3',
  'llama-2',
  'qwen',
  'qwen2',
];

export const PROVIDERS = [
  '',
  'openai',
  'anthropic',
  'mistral',
  'openrouter',
  'google',
  'local',
] as const;

function expandEnvVars(value: string): string {
  if (!value) return value;
  return value.replace(/\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)/g, (_, a, b) => {
    const name = a || b;
    const env = window.electronAPI?.ENV?.[name];
    return env ?? '${' + name + '}';
  });
}

function isLocalEndpoint(value: string): boolean {
  const expanded = expandEnvVars(value);
  return LOCAL_PATTERNS.some((p) => p.test(expanded));
}

function inferProvider(modelId: string): {
  provider: string;
  isAmbiguous: boolean;
} {
  const expanded = expandEnvVars(modelId).toLowerCase().trim();
  if (isLocalEndpoint(expanded)) return { provider: 'local', isAmbiguous: false };

  const matches: string[] = [];
  for (const [provider, config] of Object.entries(PROVIDER_PATTERNS)) {
    if (config.patterns.some((p) => p.test(expanded))) matches.push(provider);
  }

  if (matches.length === 0) {
    for (const prefix of AMBIGUOUS_MODELS) {
      if (expanded.includes(prefix)) {
        return { provider: prefix.split('-')[0], isAmbiguous: true };
      }
    }
    return { provider: '', isAmbiguous: false };
  }
  if (matches.length === 1) return { provider: matches[0], isAmbiguous: false };
  return { provider: matches[0], isAmbiguous: true };
}

export function validateModelInput(
  modelInput: string,
  fallbackProvider = '',
): Validation {
  if (!modelInput.trim()) {
    return {
      isValid: false,
      emoji: '',
      message: 'Enter model ID or endpoint',
      requiresFallback: false,
      provider: '',
    };
  }

  const { provider, isAmbiguous } = inferProvider(modelInput);
  const finalProvider = fallbackProvider || provider;

  if (!finalProvider && !isLocalEndpoint(modelInput)) {
    return {
      isValid: false,
      emoji: '⚠',
      message: 'Unknown format — specify provider',
      requiresFallback: false,
      provider: '',
    };
  }

  if (isAmbiguous && !fallbackProvider) {
    return {
      isValid: true,
      emoji: '⚠',
      message: `Ambiguous — select provider for ${provider}`,
      requiresFallback: true,
      provider,
    };
  }

  if (finalProvider === 'local' || isLocalEndpoint(modelInput)) {
    return {
      isValid: true,
      emoji: '✓',
      message: 'Local endpoint (Ollama/vLLM)',
      requiresFallback: false,
      provider: 'local',
    };
  }

  const config = PROVIDER_PATTERNS[finalProvider];
  const apiKey = config ? window.electronAPI?.ENV?.[config.envKey] : null;

  if (config) {
    return {
      isValid: true,
      emoji: apiKey ? '✓' : '⚠',
      message: `${finalProvider.charAt(0).toUpperCase() + finalProvider.slice(1)} — ${apiKey ? 'API key found' : `Add ${config.envKey}`}`,
      requiresFallback: false,
      provider: finalProvider,
    };
  }

  return {
    isValid: true,
    emoji: '✓',
    message: `${finalProvider} provider detected`,
    requiresFallback: false,
    provider: finalProvider,
  };
}
