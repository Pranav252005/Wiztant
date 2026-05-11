/**
 * Wiztant Credit System — Client-side engine
 * Mirrors core/credit_system.py logic for the website.
 */

const MARKUP = 5
const COST_PER_CREDIT = {
  free: 0.006,
  pro: 0.006,
  power: 0.005,
}

export const TIER_ALLOCATIONS = {
  free: 50,
  pro: 1000,
  power: 5000,
}

const MODELS = {
  'qwen/qwen3.5-plus-20260420': { input: 0.40, output: 2.40, category: 'Budget', speed: 'Fast' },
  'google/gemini-3-flash-preview': { input: 0.50, output: 3.00, category: 'Budget', speed: 'Fast' },
  'x-ai/grok-4.3': { input: 1.25, output: 2.50, category: 'Budget', speed: 'Fast' },
  'moonshotai/kimi-k2.6': { input: 0.75, output: 3.50, category: 'Budget', speed: 'Fast' },
  'openai/gpt-5.4-mini': { input: 0.75, output: 4.50, category: 'Budget', speed: 'Fast' },
  'anthropic/claude-haiku-4.5': { input: 1.00, output: 5.00, category: 'Mid', speed: 'Fast' },
  'google/gemini-3.1-pro-preview': { input: 2.00, output: 12.00, category: 'Pro', speed: 'Medium' },
  'openai/gpt-5.4': { input: 2.50, output: 15.00, category: 'Pro', speed: 'Medium' },
  'anthropic/claude-sonnet-4.6': { input: 3.00, output: 15.00, category: 'Pro', speed: 'Medium' },
  'openai/gpt-5.5': { input: 5.00, output: 30.00, category: 'Ultra', speed: 'Slow' },
}

const TUNEHUB_ITERATIONS = {
  LOW: 3,
  MEDIUM: 10,
  HIGH: 30,
}

const TOKEN_ESTIMATES = {
  reprompt: { input: 3000, output: 2000 },
  judge: { input: 2000, output: 20 },
}

export function getModelList() {
  return Object.entries(MODELS).map(([id, m]) => ({
    id,
    name: id.split('/')[1],
    ...m,
  }))
}

export function calculateApiCost(modelId, inputTokens, outputTokens) {
  const m = MODELS[modelId]
  if (!m) return 0
  return (inputTokens * m.input / 1_000_000) + (outputTokens * m.output / 1_000_000)
}

export function calculateCredits(apiCost, tier = 'pro') {
  const cpc = COST_PER_CREDIT[tier] ?? COST_PER_CREDIT.pro
  return Math.max(1, Math.ceil((apiCost * MARKUP) / cpc))
}

export function calculateRepromptCredits(modelId) {
  const id = modelId || 'google/gemini-3-flash-preview'
  const cost = calculateApiCost(id, TOKEN_ESTIMATES.reprompt.input, TOKEN_ESTIMATES.reprompt.output)
  return calculateCredits(cost)
}

export function calculateDictationCredits() {
  return 1
}

export function calculateTunehubCredits(complexity = 'LOW', featureModel, judgeModel) {
  const fm = featureModel || 'google/gemini-3-flash-preview'
  const jm = judgeModel || 'anthropic/claude-haiku-4.5'
  const iters = TUNEHUB_ITERATIONS[complexity] || TUNEHUB_ITERATIONS.LOW

  const featureCost = calculateApiCost(fm, TOKEN_ESTIMATES.reprompt.input, TOKEN_ESTIMATES.reprompt.output)
  const judgeCost = calculateApiCost(jm, TOKEN_ESTIMATES.judge.input, TOKEN_ESTIMATES.judge.output)

  return iters * (calculateCredits(featureCost) + calculateCredits(judgeCost))
}

export function getTierCredits(tier) {
  return TIER_ALLOCATIONS[tier] ?? TIER_ALLOCATIONS.free
}

export function getFeaturePreview() {
  const defaultModel = 'google/gemini-3-flash-preview'
  return [
    { feature: 'Dictation', credits: 1, note: 'Per utterance', model: 'Groq Whisper' },
    { feature: 'RePrompt', credits: calculateRepromptCredits(defaultModel), note: 'Default model', model: 'Gemini 3 Flash' },
    { feature: 'RePrompt (Pro)', credits: calculateRepromptCredits('openai/gpt-5.4'), note: 'Premium model', model: 'GPT-5.4' },
    { feature: 'RePrompt (Ultra)', credits: calculateRepromptCredits('openai/gpt-5.5'), note: 'Max quality', model: 'GPT-5.5' },
    { feature: 'TuneHub LOW', credits: calculateTunehubCredits('LOW'), note: '3 iterations' },
    { feature: 'TuneHub MEDIUM', credits: calculateTunehubCredits('MEDIUM'), note: '10 iterations' },
    { feature: 'TuneHub HIGH', credits: calculateTunehubCredits('HIGH'), note: '30 iterations' },
  ]
}
