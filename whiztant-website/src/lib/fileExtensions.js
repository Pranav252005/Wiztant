/**
 * File extension database for dictation normalization.
 * Maps spoken patterns to their actual file extension forms.
 */

// Common file extensions that users might dictate.
// Both the key (spoken form) and value (normalized form) are lowercase.
export const EXTENSION_MAP = new Map([
  // Documentation / text
  ['md', '.md'],
  ['txt', '.txt'],
  ['rtf', '.rtf'],
  ['pdf', '.pdf'],
  ['doc', '.doc'],
  ['docx', '.docx'],
  ['odt', '.odt'],

  // Data / config
  ['json', '.json'],
  ['xml', '.xml'],
  ['yaml', '.yaml'],
  ['yml', '.yml'],
  ['csv', '.csv'],
  ['tsv', '.tsv'],
  ['sql', '.sql'],
  ['db', '.db'],
  ['sqlite', '.sqlite'],

  // Spreadsheets
  ['xls', '.xls'],
  ['xlsx', '.xlsx'],
  ['ods', '.ods'],

  // Web
  ['html', '.html'],
  ['htm', '.htm'],
  ['css', '.css'],
  ['scss', '.scss'],
  ['sass', '.sass'],
  ['less', '.less'],
  ['php', '.php'],

  // JavaScript / TypeScript ecosystem
  ['js', '.js'],
  ['jsx', '.jsx'],
  ['ts', '.ts'],
  ['tsx', '.tsx'],
  ['mjs', '.mjs'],
  ['cjs', '.cjs'],

  // Python
  ['py', '.py'],
  ['pyw', '.pyw'],
  ['pyc', '.pyc'],
  ['ipynb', '.ipynb'],

  // Java / JVM
  ['java', '.java'],
  ['class', '.class'],
  ['jar', '.jar'],
  ['kt', '.kt'],
  ['scala', '.scala'],

  // C / C++
  ['c', '.c'],
  ['cpp', '.cpp'],
  ['cc', '.cc'],
  ['cxx', '.cxx'],
  ['h', '.h'],
  ['hpp', '.hpp'],
  ['hh', '.hh'],

  // Systems / compiled
  ['go', '.go'],
  ['rs', '.rs'],
  ['swift', '.swift'],
  ['r', '.r'],
  ['rb', '.rb'],
  ['pl', '.pl'],
  ['lua', '.lua'],
  ['sh', '.sh'],
  ['bash', '.bash'],
  ['zsh', '.zsh'],
  ['ps1', '.ps1'],
  ['bat', '.bat'],
  ['cmd', '.cmd'],
  ['exe', '.exe'],
  ['dll', '.dll'],

  // Markup / other
  ['tex', '.tex'],
  ['bib', '.bib'],
  ['log', '.log'],
  ['ini', '.ini'],
  ['cfg', '.cfg'],
  ['conf', '.conf'],
  ['env', '.env'],
  ['toml', '.toml'],
  ['lock', '.lock'],

  // Images (less common to dictate but useful)
  ['svg', '.svg'],
  ['png', '.png'],
  ['jpg', '.jpg'],
  ['jpeg', '.jpeg'],
  ['gif', '.gif'],
  ['webp', '.webp'],
  ['ico', '.ico'],

  // Audio / video
  ['mp3', '.mp3'],
  ['mp4', '.mp4'],
  ['wav', '.wav'],
  ['ogg', '.ogg'],
  ['webm', '.webm'],
  ['mov', '.mov'],
  ['avi', '.avi'],
  ['mkv', '.mkv'],

  // Archives
  ['zip', '.zip'],
  ['tar', '.tar'],
  ['gz', '.gz'],
  ['rar', '.rar'],
  ['7z', '.7z'],
  ['bz2', '.bz2'],
])

// Spoken prefixes that indicate a file extension is being dictated.
export const EXTENSION_PREFIXES = ['dot', 'period', 'point']

// Build a regex-safe string of all extension keys for pattern matching.
const extKeys = Array.from(EXTENSION_MAP.keys()).join('|')

// Build a regex-safe string of all prefixes.
const prefixKeys = EXTENSION_PREFIXES.join('|')

/**
 * Global regex that matches spoken file extension patterns like:
 *   "dot md", "period txt", "point xml", "dot xlsx"
 * Case-insensitive, word-bounded.
 */
export const SPOKEN_EXTENSION_REGEX = new RegExp(
  `\\b(${prefixKeys})\\s+(${extKeys})\\b`,
  'gi'
)

/**
 * Normalizes a single matched spoken extension.
 * @param {string} _fullMatch - The full matched string (e.g. "dot md")
 * @param {string} _prefix - The prefix word (e.g. "dot")
 * @param {string} ext - The extension word (e.g. "md")
 * @returns {string} The normalized extension (e.g. ".md")
 */
export function normalizeExtension(_fullMatch, _prefix, ext) {
  const normalized = EXTENSION_MAP.get(ext.toLowerCase())
  return normalized || `.${ext.toLowerCase()}`
}
