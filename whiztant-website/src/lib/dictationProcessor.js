import { SPOKEN_EXTENSION_REGEX, normalizeExtension } from './fileExtensions'

// ============================================================================
// Configuration
// ============================================================================

/** Words that the speech engine often hallucinates during silence/pauses. */
const FILLER_WORDS = new Set([
  'dev', 'deb', 'dew', 'deaf', 'div', 'dav', 'dof', 'dov',
  'uh', 'um', 'uhh', 'umm', 'eh', 'ah', 'ohh',
  'hmm', 'hm', 'mmm', 'mm',
  // Some STT engines repeat these when uncertain
  'the', 'a', 'an',
])

/** Question words / auxiliary verbs that signal a question. */
const QUESTION_STARTERS = new Set([
  'what', 'whats', "what's",
  'why', 'whys', "why's",
  'how', 'hows', "how's",
  'when', 'whens', "when's",
  'where', 'wheres', "where's",
  'who', 'whos', "who's",
  'which', 'whichever',
  'whose',
  'is', 'are', 'am',
  'can', 'could',
  'would', 'should',
  'will', 'shall',
  'did', 'do', 'does',
  'have', 'has', 'had',
  'may', 'might',
  'was', 'were',
])

/** Keywords that suggest excitement / exclamation. */
const EXCLAMATION_WORDS = new Set([
  'wow', 'amazing', 'awesome', 'great', 'incredible', 'excellent',
  'fantastic', 'unbelievable', 'wonderful', 'brilliant', 'outstanding',
  'superb', 'marvelous', 'magnificent', 'terrific', 'fabulous',
  'stupendous', 'phenomenal', 'extraordinary', 'remarkable', 'impressive',
  'congratulations', 'hurray', 'yahoo', 'yay', 'woohoo', 'hell',
  'yes', 'yeah', 'yep', 'sure', 'absolutely', 'definitely',
  'certainly', 'obviously', 'clearly', 'seriously', 'honestly',
  'frankly', 'truly', 'really', 'actually', 'indeed',
  'no', 'nope', 'never', 'stop', 'wait', 'oops', 'ouch',
])

/** Words/phrases after which a comma often belongs (conjunctive adverbs, transitions). */
const COMMA_TRIGGERS = new Set([
  'however', 'moreover', 'furthermore', 'meanwhile', 'nevertheless',
  'therefore', 'consequently', 'additionally', 'similarly', 'likewise',
  'otherwise', 'instead', 'afterwards', 'subsequently', 'previously',
  'currently', 'recently', 'originally', 'finally', 'lastly',
  'ultimately', 'eventually', 'initially', 'firstly', 'secondly',
  'thirdly', 'namely', 'specifically', 'particularly', 'especially',
  'generally', 'typically', 'usually', 'normally', 'commonly',
  'frequently', 'often', 'sometimes', 'occasionally', 'rarely',
  'seldom', 'basically', 'essentially', 'fundamentally', 'primarily',
  'mainly', 'largely', 'mostly', 'partly', 'partially', 'completely',
  'totally', 'entirely', 'fully', 'fortunately', 'unfortunately',
  'luckily', 'hopefully', 'thankfully', 'amazingly', 'surprisingly',
  'astonishingly', 'interestingly', 'significantly', 'importantly',
  'notably', 'remarkably', 'strikingly', 'noticeably', 'markedly',
  'dramatically', 'radically', 'drastically', 'substantially',
  'considerably', 'slightly', 'somewhat', 'anyway', 'anyhow',
])

// ============================================================================
// Pipeline Stages
// ============================================================================

/**
 * Stage 1: Remove repeated filler artifacts and isolated filler words.
 * Handles patterns like "dev dev dev" or standalone "uh" / "um".
 */
function filterFillers(text) {
  // Split into words, process, rejoin.
  const words = text.trim().split(/\s+/)
  const cleaned = []

  for (let i = 0; i < words.length; i++) {
    const w = words[i].toLowerCase().replace(/[^a-z0-9]/g, '')

    // If it's a filler word...
    if (FILLER_WORDS.has(w)) {
      // Skip if the next word is the same filler (repetition).
      if (i + 1 < words.length && words[i + 1].toLowerCase().replace(/[^a-z0-9]/g, '') === w) {
        continue
      }
      // Skip if the previous word was also the same filler.
      if (i > 0 && words[i - 1].toLowerCase().replace(/[^a-z0-9]/g, '') === w) {
        continue
      }
      // Skip isolated single-letter or two-letter fillers entirely.
      if (w.length <= 2) {
        continue
      }
      // Otherwise allow it through (might be a real word).
    }

    cleaned.push(words[i])
  }

  return cleaned.join(' ')
}

/**
 * Stage 2: Normalize spoken file extensions.
 * "dot md" => ".md", "period txt" => ".txt", etc.
 */
function normalizeExtensions(text) {
  return text.replace(SPOKEN_EXTENSION_REGEX, normalizeExtension)
}

/**
 * Stage 3: Sanitize spacing around punctuation.
 * - Removes spaces before . , ; : ? !
 * - Ensures single space after . , ; : ? ! ) } ]
 * - Collapses multiple spaces into one.
 * - Removes spaces at start/end.
 */
function sanitizeSpacing(text) {
  return (
    text
      // Remove spaces before punctuation
      .replace(/\s+([.,;:!?\])}])/g, '$1')
      // Ensure single space after punctuation (but not for decimals like 3.14)
      .replace(/([.,;:!?\])}])(?![\d\s])/g, '$1 ')
      .replace(/([.,;:!?\])}])\s+/g, '$1 ')
      // Collapse multiple spaces
      .replace(/\s{2,}/g, ' ')
      // Trim
      .trim()
  )
}

/**
 * Stage 4: Smart punctuation insertion.
 * Adds terminal punctuation and commas where speech engines typically omit them.
 */
function addSmartPunctuation(text) {
  if (!text) return text

  // Split into sentences by existing punctuation to avoid double-punctuating.
  const segments = text.split(/(?<=[.!?])\s+/)
  const processed = segments.map((segment) => {
    const trimmed = segment.trim()
    if (!trimmed) return trimmed

    // If it already ends with punctuation, leave it.
    if (/[.!?]$/.test(trimmed)) return trimmed

    const words = trimmed.split(/\s+/)
    const firstWord = words[0].toLowerCase().replace(/[^a-z]/g, '')
    const lastWord = words[words.length - 1].toLowerCase().replace(/[^a-z]/g, '')

    // Question detection
    if (QUESTION_STARTERS.has(firstWord)) {
      // Check if it's actually a question phrasing
      // (avoid false positives like "What a day" → we still add ? since user explicitly wants it)
      return trimmed + '?'
    }

    // Exclamation detection
    if (EXCLAMATION_WORDS.has(lastWord) || EXCLAMATION_WORDS.has(firstWord)) {
      return trimmed + '!'
    }

    // Default: add period for complete-looking sentences (≥3 words)
    if (words.length >= 3) {
      return trimmed + '.'
    }

    return trimmed
  })

  return processed.join(' ')
}

/**
 * Stage 5: Insert commas after transition words when they appear mid-sentence.
 */
function addCommas(text) {
  // Match transition words that are NOT already followed by a comma.
  const pattern = new RegExp(
    `\\b(${Array.from(COMMA_TRIGGERS).join('|')})\\b(?!,)`,
    'gi'
  )

  return text.replace(pattern, (match, word, offset, string) => {
    // Don't add comma if it's the very last word.
    const after = string.slice(offset + word.length).trim()
    if (!after) return match

    // Don't add comma if the next character is already punctuation.
    if (/^[.!?;,:]/.test(after)) return match

    return `${word},`
  })
}

/**
 * Stage 6: Capitalize first letter of each sentence.
 */
function capitalizeSentences(text) {
  // Match the first letter after sentence-ending punctuation + space, or start of string.
  return text.replace(/(^|[.!?]\s+)([a-z])/g, (_, prefix, letter) => prefix + letter.toUpperCase())
}

// ============================================================================
// Public API
// ============================================================================

/**
 * Dictation post-processing options.
 * @typedef {Object} ProcessOptions
 * @property {boolean} [filterFillers=true] - Remove filler artifacts.
 * @property {boolean} [normalizeExtensions=true] - Convert "dot md" → ".md".
 * @property {boolean} [smartPunctuation=true] - Auto-add ?, !, . and commas.
 * @property {boolean} [capitalize=true] - Capitalize sentence starts.
 */

/**
 * Processes raw speech-to-text output into polished, readable text.
 *
 * @param {string} rawText - The transcript straight from the speech engine.
 * @param {ProcessOptions} [options={}] - Which stages to run.
 * @returns {string} The cleaned, punctuated, normalized text.
 */
export function processDictation(rawText, options = {}) {
  const {
    filterFillers: doFilterFillers = true,
    normalizeExtensions: doNormalizeExtensions = true,
    smartPunctuation: doSmartPunctuation = true,
    capitalize: doCapitalize = true,
  } = options

  if (!rawText || typeof rawText !== 'string') return ''

  let text = rawText

  if (doFilterFillers) {
    text = filterFillers(text)
  }

  if (doNormalizeExtensions) {
    text = normalizeExtensions(text)
  }

  // Always sanitize spacing so extensions glue properly.
  text = sanitizeSpacing(text)

  if (doSmartPunctuation) {
    text = addSmartPunctuation(text)
    text = addCommas(text)
    // Re-sanitize after punctuation insertions.
    text = sanitizeSpacing(text)
  }

  if (doCapitalize) {
    text = capitalizeSentences(text)
  }

  return text.trim()
}
