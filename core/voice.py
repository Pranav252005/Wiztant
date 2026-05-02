"""
Whiztant core/voice.py — Groq cloud Whisper transcription + local fallback + TTS.
Records audio, transcribes via Groq Whisper Large v3 Turbo, corrects transcript.
Falls back to local faster-whisper if Groq is unavailable.
"""

import os
import io
import re
import threading
import time
from pathlib import Path

import core as state
from core.vocab import apply_corrections as _apply_vocab_corrections

# =============================================================
#  CONFIG
# =============================================================

GROQ_API_KEY     = os.getenv("GROQ_API_KEY")
WHISPER_PROVIDER = os.getenv("WHISPER_PROVIDER", "groq")
WHISPER_MODEL    = "whisper-large-v3-turbo"

SAMPLE_RATE    = 16000
CHANNELS       = 1
CHUNK          = 1024
SILENCE_LIMIT  = 1.5   # seconds of silence before auto-stop
MAX_RECORD_SEC = 999999  # effectively unlimited

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Groq client (lazy init to avoid crash if key missing)
_groq_client = None

def _get_groq_client():
    global _groq_client
    if _groq_client is None and GROQ_API_KEY:
        from groq import Groq
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client

print(f"[Voice] Provider: {WHISPER_PROVIDER}, Groq key: {'set' if GROQ_API_KEY else 'MISSING'}")

# =============================================================
#  TRANSCRIPTION CORRECTION — Layer 1: spoken patterns
# =============================================================

_SPOKEN_PATTERNS = [
    (r"\bdouble\s+underscore\s+(\w+)\s+double\s+underscore\b", r"__\1__"),
    (r"\bdouble\s+underscore\b",                               "__"),
    (r"\bdot\s+agents\b",    ".agents"),
    (r"\bdot\s+py\b",        ".py"),
    (r"\bdot\s+js\b",        ".js"),
    (r"\bdot\s+ts\b",        ".ts"),
    (r"\bdot\s+json\b",      ".json"),
    (r"\bdot\s+txt\b",       ".txt"),
    (r"\bdot\s+md\b",        ".md"),
    (r"\bdot\s+csv\b",       ".csv"),
    (r"\bdot\s+html\b",      ".html"),
    (r"\bdot\s+css\b",       ".css"),
    (r"\bdot\s+env\b",       ".env"),
    (r"\bdot\s+exe\b",       ".exe"),
    (r"\bdot\s+com\b",       ".com"),
    (r"\bdot\s+org\b",       ".org"),
    (r"\bdot\s+net\b",       ".net"),
    (r"\bdot\s+io\b",        ".io"),
    (r"\bdot\s+ai\b",        ".ai"),
    (r"\bdot\s+git\b",       ".git"),
    (r"\bhttps\s+colon\s+slash\s+slash\b", "https://"),
    (r"\bhttp\s+colon\s+slash\s+slash\b",  "http://"),
    (r"\bforward\s+slash\b",               "/"),
    (r"\bback\s+slash\b",                  "BKSL"),
    (r"\bcolon\s+slash\s+slash\b",         "://"),
    (r"\bat\s+sign\b",       "@"),
    (r"\bhash\s+hash\b",     "##"),
    (r"\bhash\s+sign\b",     "#"),
    (r"\bpound\s+sign\b",    "#"),
    (r"\bunderscore\b",      "_"),
    (r"\basterisk\b",        "*"),
    (r"\bdash\s+dash\b",     "--"),
    (r"\bequals\s+equals\b", "=="),
    (r"\bnot\s+equals\b",    "!="),
    (r"\barrow\s+right\b",   "->"),
    (r"\bfat\s+arrow\b",     "=>"),
    (r"\bplus\s+plus\b",     "++"),
    (r"\bminus\s+minus\b",   "--"),
    (r"\bbacktick\b",        "`"),
    (r"\bsemicolon\b",       ";"),
    (r"\bfull\s+stop\b",             "."),
    (r"\bperiod\b",                  "."),
    (r"\bcomma\b",                   ","),
    (r"\bexclamation\s+mark\b",      "!"),
    (r"\bquestion\s+mark\b",         "?"),
    (r"\bopen\s+paren(?:thesis)?\b", "("),
    (r"\bclose\s+paren(?:thesis)?\b",")"),
    (r"\bnew\s+line\b",              "\n"),
    (r"\btab\s+key\b",               "\t"),
    # General dot / slash / backslash expansion (specific patterns above take precedence)
    (r"\bdot\s+(\w+)\b",              r".\1"),
    (r"\bslash\s+(\w+)\b",            r"/\1"),
    (r"\bbackslash\s+(\w+)\b",        r"\\\1"),
]

_COMPILED_PATTERNS = [
    (re.compile(p, re.IGNORECASE), r)
    for p, r in _SPOKEN_PATTERNS
]

# =============================================================
#  Layer 2: word correction dictionary
# =============================================================

# =============================================================
#  Layer 2: MASSIVE word correction dictionary — phonetic + exact
# =============================================================

# AI/ML & LLMs
_AI_TERMS = {
    # Claude / Anthropic
    "clod": "Claude", "cloud": "Claude", "claude": "Claude",
    "claudes": "Claude's", "clawed": "Claude", "clod's": "Claude's",
    "anthropic": "Anthropic", "anthropics": "Anthropic's", "anthropik": "Anthropic",
    "sonnet": "Sonnet", "sonet": "Sonnet", "sonit": "Sonnet",
    "haiku": "Haiku", "haikyu": "Haiku", "opis": "Opus", "opus": "Opus",
    
    # OpenAI
    "chatgpt": "ChatGPT", "chat gpt": "ChatGPT", "chat gee pee tee": "ChatGPT",
    "gpt": "GPT", "gee pee tee": "GPT", "gpt-4": "GPT-4", "gpt-3": "GPT-3",
    "gpt4": "GPT-4", "gpt3": "GPT-3", "gpt 4": "GPT-4", "gpt 3": "GPT-3",
    "gpt four": "GPT-4", "gpt three": "GPT-3",
    "openai": "OpenAI", "open ai": "OpenAI", "open ey": "OpenAI",
    "dall-e": "DALL-E", "dalle": "DALL-E", "dal e": "DALL-E",
    "whisper": "Whisper", "whissper": "Whisper", "wisper": "Whisper",
    "davinci": "Davinci", "da vinci": "Davinci", "curie": "Curie",
    "ada": "Ada", "babbage": "Babbage", "babbidge": "Babbage",
    "gpt-4o": "GPT-4o", "gpt4o": "GPT-4o", "gpt 4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o mini", "gpt4o mini": "GPT-4o mini",
    "o1": "o1", "o1-mini": "o1-mini", "o3": "o3", "o3-mini": "o3-mini",
    "sora": "Sora",
    
    # Meta / Other LLMs
    "llama": "Llama", "lama": "Llama", "llamma": "Llama",
    "llama 2": "Llama 2", "llama 3": "Llama 3", "llama2": "Llama 2", "llama3": "Llama 3",
    "llama two": "Llama 2", "llama three": "Llama 3",
    "llama 3.1": "Llama 3.1", "llama 3.2": "Llama 3.2", "llama 3.3": "Llama 3.3",
    "llama 4": "Llama 4", "llama four": "Llama 4",
    "mistral": "Mistral", "mistrel": "Mistral", "mixtral": "Mixtral",
    "mistral large": "Mistral Large", "mistral small": "Mistral Small",
    "pixtral": "Pixtral",
    "codellama": "CodeLlama", "code llama": "CodeLlama",
    
    # Google
    "gemini": "Gemini", "gemeny": "Gemini", "jiminy": "Gemini",
    "gemma": "Gemma", "palm": "PaLM", "bard": "Bard",
    "deepmind": "DeepMind", "deep mind": "DeepMind",
    "gemini 1.5": "Gemini 1.5", "gemini 2.0": "Gemini 2.0", "gemini 2.5": "Gemini 2.5",
    "gemini flash": "Gemini Flash", "gemini pro": "Gemini Pro",
    
    # Alibaba / Chinese
    "quen": "Qwen", "qwin": "Qwen", "kwon": "Qwen", "kwan": "Qwen", "qwen": "Qwen",
    "qwen2": "Qwen2", "qwen 2": "Qwen2", "qwen3": "Qwen3", "qwen 3": "Qwen3",
    "qwq": "QwQ", "tongyi": "Tongyi",
    "baichuan": "Baichuan", "chatglm": "ChatGLM",
    
    # Local/Other
    "olama": "Ollama", "ollama": "Ollama", "oh lama": "Ollama",
    "copilot": "Copilot", "co-pilot": "Copilot", "github copilot": "GitHub Copilot",
    "tabnine": "Tabnine", "kite": "Kite", "replit": "Replit",
    "phind": "Phind", "perplexity": "Perplexity", "perplex": "Perplexity",
    "you.com": "You.com", "youcom": "You.com",
    "hugging face": "Hugging Face", "huggingface": "HuggingFace",
    "hf": "HF", "transformers": "Transformers",
    # DeepSeek / xAI / Moonshot / Cohere / AI21 / etc.
    "deepseek": "DeepSeek", "deep seek": "DeepSeek",
    "deepseek r1": "DeepSeek-R1", "deepseek v3": "DeepSeek-V3",
    "grok": "Grok", "groq": "Groq", "grock": "Groq",
    "kimi": "Kimi", "moonshot": "Moonshot AI",
    "command r": "Command R", "command r+": "Command R+", "cohere": "Cohere",
    "jamba": "Jamba", "ai21": "AI21",
    "phi": "Phi", "phi-3": "Phi-3", "phi-4": "Phi-4", "phi 3": "Phi-3", "phi 4": "Phi-4",
    "nova": "Nova", "amazon nova": "Amazon Nova",
    # Image / Video / Audio Gen
    "stable diffusion": "Stable Diffusion", "sdxl": "SDXL",
    "flux": "Flux", "midjourney": "Midjourney",
    "runway": "Runway", "elevenlabs": "ElevenLabs", "eleven labs": "ElevenLabs",
    # Coding assistants
    "cline": "Cline", "roo code": "Roo Code", "roocode": "Roo Code",
    "aider": "Aider", "supermaven": "Supermaven",
    "sourcegraph cody": "Sourcegraph Cody", "cody": "Cody",
    "continue": "Continue.dev",
}

# Frameworks & Libraries
_FRAMEWORKS = {
    # LangChain ecosystem
    "langchain": "LangChain", "lang chain": "LangChain",
    "langgraph": "LangGraph", "lang graph": "LangGraph", "langraph": "LangGraph",
    "langserve": "LangServe", "lang smith": "LangSmith", "langsmith": "LangSmith",
    "lcel": "LCEL", "expression language": "expression language",
    
    # Deep Learning
    "pytorch": "PyTorch", "pie torch": "PyTorch", "py torch": "PyTorch",
    "tensorflow": "TensorFlow", "tensor flow": "TensorFlow", "tf": "TF",
    "keras": "Keras", "jax": "JAX", "flax": "Flax", "trax": "Trax",
    "onnx": "ONNX", "tensorrt": "TensorRT",
    "caffe": "Caffe", "cafe": "Caffe", "theano": "Theano",
    "mxnet": "MXNet", "chainer": "Chainer", "paddle": "PaddlePaddle",
    "paddlepaddle": "PaddlePaddle",
    
    # ML/Data
    "scikit-learn": "scikit-learn", "sklearn": "sklearn", "sk learn": "sklearn",
    "xgboost": "XGBoost", "ex g boost": "XGBoost", "catboost": "CatBoost",
    "lightgbm": "LightGBM", "light gbm": "LightGBM",
    "numpy": "NumPy", "num py": "NumPy", "numbie": "NumPy",
    "pandas": "Pandas", "panda": "Pandas", "pd": "pd",
    "scipy": "SciPy", "sci py": "SciPy", "sympy": "SymPy",
    "matplotlib": "Matplotlib", "matplot lib": "Matplotlib", "mpl": "mpl",
    "seaborn": "Seaborn", "sea born": "Seaborn", "sns": "sns",
    "plotly": "Plotly", "bokeh": "Bokeh", "altair": "Altair",
    "jupyter": "Jupyter", "jupiter": "Jupyter", "ipynb": "ipynb",
    "colab": "Colab", "google colab": "Google Colab",
    "kaggle": "Kaggle", "anaconda": "Anaconda", "conda": "conda",
    "spacy": "spaCy", "spacey": "spaCy", "nltk": "NLTK",
    "gensim": "Gensim", "word2vec": "Word2Vec", "bert": "BERT",
    "roberta": "RoBERTa", "distilbert": "DistilBERT", "gpt2": "GPT-2",
    "t5": "T5", "bart": "BART", "electra": "ELECTRA", "albert": "ALBERT",
}

# Programming Languages
_LANGUAGES = {
    "python": "Python", "pie thon": "Python",
    "javascript": "JavaScript", "java script": "JavaScript", "js": "JS",
    "typescript": "TypeScript", "type script": "TypeScript", "ts": "TS",
    "nodejs": "Node.js", "node js": "Node.js", "node": "Node",
    "golang": "Go", "go lang": "Go",
    "rust": "Rust", "rustlang": "Rust",
    "cplusplus": "C++", "c plus plus": "C++", "cpp": "C++", "c++": "C++",
    "csharp": "C#", "c sharp": "C#", "c#": "C#", "dotnet": ".NET",
    "java": "Java", "jawa": "Java", "kotlin": "Kotlin", "kotlyn": "Kotlin",
    "scala": "Scala", "swift": "Swift", "objective-c": "Objective-C",
    "php": "PHP", "ruby": "Ruby", "perl": "Perl", "lua": "Lua",
    "haskell": "Haskell", "erlang": "Erlang", "elixir": "Elixir",
    "clojure": "Clojure", "scheme": "Scheme", "racket": "Racket",
    "lisp": "Lisp", "prolog": "Prolog", "fortran": "Fortran",
    "matlab": "MATLAB", "octave": "Octave", "r": "R", "sas": "SAS",
    "sql": "SQL", "sequel": "SQL", "mysql": "MySQL", "my sql": "MySQL",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "post gres": "PostgreSQL",
    "sqlite": "SQLite", "sql lite": "SQLite", "mongo": "MongoDB",
    "mongodb": "MongoDB", "mongo db": "MongoDB", "redis": "Redis",
    "cassandra": "Cassandra", "dynamodb": "DynamoDB", "couchdb": "CouchDB",
    "neo4j": "Neo4j", "graphql": "GraphQL", "graph ql": "GraphQL",
    "rest": "REST", "restful": "RESTful", "api": "API", "apis": "APIs",
    "soap": "SOAP", "grpc": "gRPC", "protobuf": "Protobuf",
    "json": "JSON", "xml": "XML", "yaml": "YAML", "yml": "YML",
    "toml": "TOML", "csv": "CSV", "html": "HTML", "css": "CSS",
    "sass": "Sass", "scss": "SCSS", "less": "Less",
    "wasm": "Wasm", "webassembly": "WebAssembly", "web assembly": "WebAssembly",
    "regex": "regex", "regexp": "regexp", "bash": "Bash", "zsh": "Zsh",
    "powershell": "PowerShell", "power shell": "PowerShell",
}

# Web Frameworks
_WEB = {
    "react": "React", "reactjs": "React", "react.js": "React",
    "vue": "Vue", "vuejs": "Vue", "vue.js": "Vue",
    "angular": "Angular", "svelte": "Svelte", "solid": "SolidJS",
    "nextjs": "Next.js", "next.js": "Next.js", "nuxt": "Nuxt",
    "remix": "Remix", "astro": "Astro", "gatsby": "Gatsby",
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI", "fast api": "FastAPI",
    "express": "Express", "expressjs": "Express",
    "spring": "Spring", "spring boot": "Spring Boot", "rails": "Rails",
    "laravel": "Laravel", "symfony": "Symfony", "codeigniter": "CodeIgniter",
    "aspnet": "ASP.NET", "asp.net": "ASP.NET",
    "tailwind": "Tailwind CSS", "tailwindcss": "Tailwind CSS", "tailwind css": "Tailwind CSS",
    "bootstrap": "Bootstrap", "material ui": "Material UI", "mui": "MUI",
    "chakra": "Chakra UI", "antd": "Ant Design",
    "webpack": "Webpack", "vite": "Vite", "rollup": "Rollup", "parcel": "Parcel",
    "esbuild": "esbuild", "swc": "SWC", "babel": "Babel",
    "npm": "npm", "yarn": "Yarn", "pnpm": "pnpm", "bun": "Bun",
    "nvm": "nvm", "npx": "npx",
}

# DevOps & Cloud
_DEVOPS = {
    "docker": "Docker", "dockers": "Docker",
    "kubernetes": "Kubernetes", "k8s": "K8s", "kates": "K8s", "kube": "Kube",
    "kubectl": "kubectl", "kube cuddle": "kubectl", "kube control": "kubectl",
    "helm": "Helm", "terraform": "Terraform", "ansible": "Ansible",
    "vagrant": "Vagrant", "packer": "Packer",
    "jenkins": "Jenkins", "gitlab ci": "GitLab CI", "github actions": "GitHub Actions",
    "circleci": "CircleCI", "circle ci": "CircleCI", "travis": "Travis CI",
    "aws": "AWS", "amazon web services": "AWS", "ec2": "EC2", "s3": "S3",
    "lambda": "Lambda", "rds": "RDS", "dynamodb": "DynamoDB",
    "gcp": "GCP", "google cloud": "Google Cloud", "azure": "Azure",
    "firebase": "Firebase", "supabase": "Supabase", "super base": "Supabase",
    "vercel": "Vercel", "netlify": "Netlify", "heroku": "Heroku",
    "render": "Render", "railway": "Railway", "fly.io": "Fly.io",
    "nginx": "Nginx", "apache": "Apache", "httpd": "httpd",
    "redis": "Redis", "kafka": "Kafka", "rabbitmq": "RabbitMQ",
    "prometheus": "Prometheus", "grafana": "Grafana", "datadog": "Datadog",
    "puppet": "Puppet", "chef": "Chef", "saltstack": "SaltStack",
}

# Tools & Editors
_TOOLS = {
    "git": "Git", "github": "GitHub", "git hub": "GitHub",
    "gitlab": "GitLab", "git lab": "GitLab", "bitbucket": "Bitbucket",
    "vscode": "VS Code", "vs code": "VS Code", "visual studio code": "VS Code",
    "vscodium": "VSCodium", "codium": "Codium",
    "vim": "Vim", "neovim": "Neovim", "nvim": "nvim",
    "emacs": "Emacs", "nano": "Nano", "pico": "Pico",
    "sublime": "Sublime Text", "atom": "Atom", "notepad++": "Notepad++",
    "cursor": "Cursor", "windsurf": "Windsurf", "windsurfer": "Windsurf", "whis": "Whis",
    "trae": "Trae", "zed": "Zed",
    "whiztant": "Wiztant", "wiztant": "Wiztant",
    "pranav": "Pranav", "venkatesh": "Venkatesh",
    "postman": "Postman", "insomnia": "Insomnia", "hoppscotch": "Hoppscotch",
    "figma": "Figma", "sketch": "Sketch", "adobe xd": "Adobe XD",
    "linear": "Linear", "jira": "Jira", "trello": "Trello", "asana": "Asana",
    "notion": "Notion", "obsidian": "Obsidian", "logseq": "Logseq",
    "slack": "Slack", "discord": "Discord", "teams": "Teams", "zoom": "Zoom",
    "tmux": "tmux", "screen": "screen", "htop": "htop", "top": "top",
}

# Operating Systems & Platforms
_OS = {
    "linux": "Linux", "linucks": "Linux", "ubuntu": "Ubuntu", "debian": "Debian",
    "fedora": "Fedora", "arch": "Arch Linux", "arch linux": "Arch Linux",
    "manjaro": "Manjaro", "mint": "Linux Mint", "pop os": "Pop!_OS",
    "centos": "CentOS", "rhel": "RHEL", "red hat": "Red Hat",
    "windows": "Windows", "win": "Win", "win11": "Windows 11", "win10": "Windows 10",
    "macos": "macOS", "mac os": "macOS", "os x": "macOS", "osx": "macOS",
    "ios": "iOS", "android": "Android", "chromeos": "ChromeOS",
    "freebsd": "FreeBSD", "openbsd": "OpenBSD", "netbsd": "NetBSD",
    "wsl": "WSL", "wsl2": "WSL2",
}

# File formats & Extensions
_FILES = {
    "json": "JSON", "xml": "XML", "yaml": "YAML", "yml": "YML",
    "toml": "TOML", "ini": "INI", "cfg": "cfg", "conf": "conf",
    "csv": "CSV", "tsv": "TSV", "xlsx": "xlsx", "xls": "xls",
    "pdf": "PDF", "doc": "doc", "docx": "docx", "txt": "txt",
    "md": "md", "markdown": "Markdown",
    "org": "org", "org mode": "org-mode", "org-mode": "org-mode",
    "rst": "rst", "adoc": "adoc", "asciidoc": "AsciiDoc",
    "png": "PNG", "jpg": "JPG", "jpeg": "JPEG", "gif": "GIF", "svg": "SVG",
    "webp": "WebP", "bmp": "BMP", "ico": "ico", "tiff": "TIFF", "tif": "TIFF",
    "mp3": "MP3", "mp4": "MP4", "wav": "WAV", "ogg": "OGG", "flac": "FLAC",
    "aac": "AAC", "m4a": "m4a", "wma": "WMA",
    "avi": "AVI", "mkv": "MKV", "mov": "MOV", "wmv": "WMV", "flv": "FLV",
    "zip": "ZIP", "tar": "TAR", "gz": "gz", "gzip": "gzip", "rar": "RAR",
    "7z": "7z", "bz2": "bz2", "xz": "xz",
    "exe": "exe", "dll": "DLL", "so": "so", "dylib": "dylib",
    "deb": "deb", "rpm": "RPM", "appimage": "AppImage",
    "snap": "snap", "flatpak": "Flatpak",
    "iso": "ISO", "img": "img", "dmg": "DMG",
    "sql": "SQL", "db": "db", "sqlite": "SQLite", "mdb": "mdb",
    "py": "py", "js": "js", "ts": "ts", "java": "java", "cpp": "cpp", "c": "c",
    "go": "go", "rs": "rs", "rb": "rb", "php": "php", "swift": "swift",
    "kt": "kt", "scala": "scala", "r": "r", "m": "m", "mm": "mm",
    "html": "HTML", "htm": "HTM", "css": "CSS", "scss": "SCSS", "sass": "Sass",
    "jsx": "JSX", "tsx": "TSX", "vue": "vue", "svelte": "svelte",
}

# Git & Version Control
_GIT = {
    "repo": "repo", "repos": "repos", "repository": "repository",
    "commit": "commit", "commits": "commits", "committing": "committing",
    "branch": "branch", "branches": "branches", "branching": "branching",
    "merge": "merge", "merging": "merging", "merges": "merges",
    "rebase": "rebase", "rebasing": "rebasing", "rebases": "rebases",
    "cherry-pick": "cherry-pick", "cherry pick": "cherry-pick",
    "stash": "stash", "stashing": "stashing", "pop": "pop",
    "clone": "clone", "cloning": "cloning", "fork": "fork", "forking": "forking",
    "pull": "pull", "pulling": "pulling", "push": "push", "pushing": "pushing",
    "fetch": "fetch", "fetching": "fetching", "checkout": "checkout",
    "diff": "diff", "patch": "patch", "patches": "patches",
    "tag": "tag", "tags": "tags", "tagging": "tagging",
    "release": "release", "releases": "releases",
    "pr": "PR", "pull request": "pull request", "pull requests": "pull requests",
    "issue": "issue", "issues": "issues",
    "readme": "README", "readme.md": "README.md", "license": "LICENSE",
    "changelog": "CHANGELOG", "contributing": "CONTRIBUTING",
    "gitignore": ".gitignore", "gitignore": ".gitignore",
    "origin": "origin", "upstream": "upstream", "remote": "remote", "remotes": "remotes",
    "master": "master", "main": "main", "develop": "develop", "dev": "dev",
    "HEAD": "HEAD", "detached": "detached",
}

# Build & Package Terms
_BUILD = {
    "dist": "dist", "build": "build", "target": "target", "out": "out",
    "bin": "bin", "lib": "lib", "libs": "libs", "include": "include",
    "src": "src", "source": "source", "sources": "sources",
    "test": "test", "tests": "tests", "testing": "testing",
    "spec": "spec", "specs": "specs",
    "benchmark": "benchmark", "benchmarks": "benchmarks", "bench": "bench",
    "example": "example", "examples": "examples", "demo": "demo", "demos": "demos",
    "docs": "docs", "doc": "doc", "documentation": "documentation",
    "assets": "assets", "static": "static", "public": "public",
    "node_modules": "node_modules", "venv": "venv", "env": "env",
    "virtualenv": "virtualenv", "pipenv": "pipenv", "poetry": "Poetry",
    "requirements": "requirements", "setup.py": "setup.py",
    "package.json": "package.json", "cargo.toml": "Cargo.toml",
    "makefile": "Makefile", "cmake": "CMake", "meson": "Meson",
    "gradle": "Gradle", "maven": "Maven", "pom.xml": "pom.xml",
    "webpack": "webpack", "rollup": "rollup", "esbuild": "esbuild",
    "vite": "Vite", "parcel": "Parcel",
}

# Common pronoun fixes
_GRAMMAR = {
    "i": "I", "i'm": "I'm", "i've": "I've", "i'll": "I'll", "i'd": "I'd",
    "dont": "don't", "wont": "won't", "cant": "can't", "isnt": "isn't",
    "wasnt": "wasn't", "werent": "weren't", "hasnt": "hasn't", "havent": "haven't",
    "hadnt": "hadn't", "doesnt": "doesn't", "didnt": "didn't", "couldnt": "couldn't",
    "wouldnt": "wouldn't", "shouldnt": "shouldn't", "arent": "aren't",
    "im": "I'm", "ill": "I'll", "id": "I'd", "ive": "I've",
    "thats": "that's", "theres": "there's", "whats": "what's", "wheres": "where's",
    "whos": "who's", "hows": "how's", "heres": "here's", "shes": "she's",
    "hes": "he's", "its": "it's", "lets": "let's", "thats": "that's",
    "wanna": "want to", "gonna": "going to", "gotta": "got to",
    "kinda": "kind of", "sorta": "sort of", "lemme": "let me",
    "gimme": "give me", "dunno": "don't know", "cmon": "come on",
    "ya": "you", "ye": "yeah", "nah": "no", "yep": "yes", "nope": "no",
}

# Combine all dictionaries
WORD_FIXES = {}
for d in [_AI_TERMS, _FRAMEWORKS, _LANGUAGES, _WEB, _DEVOPS, _TOOLS, _OS, _FILES, _GIT, _BUILD, _GRAMMAR]:
    WORD_FIXES.update(d)

_MULTI_FIXES  = {k: v for k, v in WORD_FIXES.items() if " " in k}
_SINGLE_FIXES = {k: v for k, v in WORD_FIXES.items() if " " not in k}

if _SINGLE_FIXES:
    _WORD_PATTERN = re.compile(
        r'\b(' + '|'.join(re.escape(k) for k in _SINGLE_FIXES) + r')\b',
        re.IGNORECASE
    )
else:
    _WORD_PATTERN = None


# Sequences of 3+ single letters separated by "-", ".", ",", or spaces —
# e.g. "S-H-I-V-O-R-A", "S H I V O R A", "S. H. I. V. O. R. A." — collapse
# to a single uppercase word and register the lowercase form in the vocab
# store so future mentions keep the same spelling.
_SPELL_OUT_PATTERN = re.compile(r'(?<![A-Za-z])[A-Za-z](?:[-.\s,]+[A-Za-z]){2,}(?![A-Za-z])')


def _collapse_spelled_out(text: str) -> str:
    def _repl(match: re.Match) -> str:
        letters = re.findall(r'[A-Za-z]', match.group(0))
        if len(letters) < 3:
            return match.group(0)
        # Title Case: first letter uppercase, rest lowercase.
        raw = ''.join(letters)
        word = raw[0].upper() + raw[1:].lower() if raw else raw
        try:
            from core.vocab import add_correction, find_phonetic_match, update_correction
            from core.ws_bridge import send_pill_notice
            existing = find_phonetic_match(word)
            if existing:
                existing_actual = existing.get("actual", "")
                # Different word entirely → update mapping.
                if existing_actual.lower() != word.lower():
                    if update_correction(existing_actual, word):
                        send_pill_notice(
                            "memory_updated",
                            "Spelling updated",
                            f"{existing_actual} → {word}",
                        )
                # Same letters but different case (e.g. old all-caps APPLE → new Apple)
                elif existing_actual != word:
                    if update_correction(existing_actual, word):
                        send_pill_notice(
                            "memory_updated",
                            "Spelling updated",
                            f"{existing_actual} → {word}",
                        )
                # else: exact same spelling already stored → no notice, no-op.
            else:
                # Brand-new spelled-out term: remember it and flash the pill.
                add_correction(word.lower(), word, case_sensitive=False)
                send_pill_notice("memory_added", "Spelling saved", word)
        except Exception:
            try:
                from core.vocab import add_correction
                add_correction(word.lower(), word, case_sensitive=False)
            except Exception:
                pass
        return word
    return _SPELL_OUT_PATTERN.sub(_repl, text)


def _apply_word_fixes(text: str) -> str:
    for wrong, right in _MULTI_FIXES.items():
        text = re.sub(r'\b' + re.escape(wrong) + r'\b', right, text, flags=re.IGNORECASE)
    if _WORD_PATTERN:
        text = _WORD_PATTERN.sub(
            lambda m: _SINGLE_FIXES.get(m.group(0).lower(), m.group(0)),
            text
        )
    return text


# =============================================================
#  Layer 3: Phonetic matching + Grammar + Smart fixes
# =============================================================

def _phonetic_match(text: str) -> str:
    """Use Metaphone to find similar-sounding words in vocab."""
    try:
        from metaphone import doublemetaphone
        from core.vocab import _vocab_entries
        
        words = text.split()
        corrected = []
        
        for word in words:
            word_clean = re.sub(r'[^\w]', '', word).lower()
            if not word_clean or len(word_clean) < 3:
                corrected.append(word)
                continue
            
            # Get metaphone code for this word
            code1, code2 = doublemetaphone(word_clean)
            if not code1:
                corrected.append(word)
                continue
            
            # Find phonetic matches in vocab
            for entry in _vocab_entries():
                target = entry.get("target", "").lower()
                if not target or len(target) < 3:
                    continue
                
                target_code1, target_code2 = doublemetaphone(target)
                # Strong phonetic match
                if code1 == target_code1 or (code2 and code2 == target_code2):
                    # Check similarity - must be close
                    from rapidfuzz import fuzz
                    similarity = fuzz.ratio(word_clean, target)
                    if similarity >= 70:  # 70% similar
                        # Preserve original capitalization pattern
                        if word.isupper():
                            word = target.upper()
                        elif word[0].isupper():
                            word = target.capitalize()
                        else:
                            word = target
                        break
            
            corrected.append(word)
        
        return " ".join(corrected)
    except Exception:
        return text


def _smart_punctuation(text: str) -> str:
    """Add/fix punctuation and capitalization."""
    # Ensure first letter is capitalized
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    
    # Capitalize after sentence endings
    text = re.sub(r'([.!?])\s+([a-z])', lambda m: m.group(1) + ' ' + m.group(2).upper(), text)
    
    # Add period at end if missing and it looks like a complete sentence
    if text and not text.endswith(('.', '!', '?', ':', ';', '-', '...')):
        # Don't add period if it's a code snippet, command, or question fragment
        if not any(text.endswith(x) for x in ['...', '--', '+++', '---']):
            if len(text) > 20 and text.count(' ') >= 2:
                text += '.'
    
    # Fix spaces around punctuation
    text = re.sub(r'\s+([.,!?;:/])', r'\1', text)  # Remove space before
    text = re.sub(r'([.,!?;:])([^\s])', r'\1 \2', text)  # Add space after
    text = re.sub(r'\.{3,}', '...', text)  # Normalize ellipsis
    # Collapse spaces in dot-slash path sequences (".windsurf /rules" → ".windsurf/rules")
    text = re.sub(r'(\.\w+)\s+(/[\w./-]+)', r'\1\2', text)
    
    # Fix quotes
    text = re.sub(r'"\s*(.+?)\s*"', r'"\1"', text)  # Smart spacing in quotes
    text = re.sub(r"'\s*(.+?)\s*'", r"'\1'", text)  # Single quotes
    
    return text


def _normalize_numbers(text: str) -> str:
    """Normalize number formats."""
    # Written-out numbers (basic ones)
    number_map = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'ten': '10', 'twenty': '20', 'thirty': '30', 'forty': '40', 'fifty': '50',
        'hundred': '100', 'thousand': '1000', 'million': '1000000',
    }
    
    # Replace standalone written numbers
    for word, num in number_map.items():
        text = re.sub(rf'\b{word}\b', num, text, flags=re.IGNORECASE)
    
    return text


def _detect_code_snippets(text: str) -> str:
    """Detect and properly format likely code snippets."""
    # If it looks like code (contains common patterns), don't over-correct
    code_indicators = [
        r'\b(def|class|function|var|let|const|import|from|require)\b',
        r'[{};]$',  # Ends with brace or semicolon
        r'\(.*\)',  # Function call pattern
        r'[=+\-*/<>!]=?',  # Operators
        r'\b(if|for|while|return|async|await)\b',
    ]
    
    is_code = any(re.search(pattern, text) for pattern in code_indicators)
    
    if is_code:
        # For code, preserve case and minimize changes
        # Just fix obvious misspellings of keywords
        code_fixes = {
            r'\bimprt\b': 'import', r'\bimoprt\b': 'import',
            r'\bfunciton\b': 'function', r'\bdefn\b': 'def',
            r'\bclss\b': 'class', r'\bretunr\b': 'return',
            r'\bretun\b': 'return', r'\basync\b': 'async',
            r'\bawait\b': 'await', r'\bconst\b': 'const',
            r'\blet\b': 'let', r'\bvar\b': 'var',
        }
        for pattern, fix in code_fixes.items():
            text = re.sub(pattern, fix, text, flags=re.IGNORECASE)
    
    return text


def clean_transcript(raw: str) -> str:
    if not raw:
        return raw
    
    original = raw
    text = raw
    
    # Layer 0: Detect code and handle specially
    text = _detect_code_snippets(text)
    
    # Layer 1: Spoken patterns (symbols, URLs, etc.)
    for pattern, replacement in _COMPILED_PATTERNS:
        text = pattern.sub(replacement, text)
    text = text.replace("BKSL", "\\")
    
    # Layer 2: Spelled out words (S-H-I-V-O-R-A)
    text = _collapse_spelled_out(text)
    
    # Layer 3: Number normalization
    text = _normalize_numbers(text)
    
    # Layer 4: Word fixes (exact matches)
    text = _apply_word_fixes(text)
    
    # Layer 5: Phonetic matching for unknown words
    text = _phonetic_match(text)
    
    # Layer 6: User vocab corrections
    text = _apply_vocab_corrections(text)
    
    # Layer 7: Smart punctuation and grammar
    text = _smart_punctuation(text)
    
    # Layer 8: LLM polish (if enabled)
    if state.USE_LLM_POLISH:
        text = _llm_polish(text)
    
    if text != original:
        print(f"[Fix] {original!r}\n   ->  {text!r}")
    return text


def _llm_polish(corrected: str) -> str:
    try:
        from core.agent import call_llm
        result = call_llm(
            messages=[{
                "role": "user",
                "content": (
                    "Fix ONLY spelling, punctuation, and proper noun capitalisation "
                    "in this voice transcript. Do NOT rephrase or change meaning. "
                    f"Return ONLY the corrected text.\n\nTranscript: {corrected}"
                )
            }],
            max_tokens=200
        )
        result = result.strip()
        if abs(len(result) - len(corrected)) > len(corrected) * 0.4:
            return corrected
        return result
    except Exception as e:
        print(f"[Polish] Skipped: {e}")
        return corrected


# =============================================================
#  TRANSCRIPTION — Groq Cloud
# =============================================================

def transcribe_groq(audio_bytes: bytes) -> str:
    """Sends audio to Groq Whisper Large v3 Turbo, returns transcribed text."""
    client = _get_groq_client()
    if client is None:
        raise RuntimeError("Groq API key not configured")

    temp_path = _PROJECT_ROOT / "data" / "temp_audio.wav"
    temp_path.parent.mkdir(exist_ok=True)
    temp_path.write_bytes(audio_bytes)

    try:
        with open(temp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=("audio.wav", audio_file.read()),
                model=WHISPER_MODEL,
                response_format="text",
                language="en",
                temperature=0.0,
            )
        return transcription.strip()
    finally:
        temp_path.unlink(missing_ok=True)


# =============================================================
#  TRANSCRIPTION — Local Fallback
# =============================================================

def transcribe_local(_audio_bytes: bytes) -> str:
    """Local fallback removed — Groq cloud is the only STT provider."""
    print("[STT] Local fallback is disabled. Set GROQ_API_KEY and WHISPER_PROVIDER=groq.")
    return ""


# =============================================================
#  MAIN TRANSCRIPTION ENTRY
# =============================================================

def transcribe(audio_bytes: bytes) -> str:
    """Transcribes audio via Groq cloud STT."""
    from core.stt_engine import _update_context

    if WHISPER_PROVIDER == "groq" and GROQ_API_KEY:
        try:
            text = transcribe_groq(audio_bytes)
            text = clean_transcript(text)
            if text:
                _update_context(text)
            return text
        except Exception as e:
            print(f"[Groq] Transcription failed: {e}")
            return ""

    print("[STT] Groq not configured. Set GROQ_API_KEY and WHISPER_PROVIDER=groq.")
    return ""


# Legacy compat — hotkeys.py still uses this for chat/agent modes
def transcribe_wav(wav_path: str) -> str:
    """Transcribe a WAV file on disk. Used by the sounddevice recording path."""
    with open(wav_path, "rb") as f:
        audio_bytes = f.read()
    return transcribe(audio_bytes)


# =============================================================
#  TTS — Kokoro (local neural)
# =============================================================

_kokoro_pipeline = None
_kokoro_speaking = False
_kokoro_stop_event = threading.Event()


def _get_kokoro_pipeline():
    """Lazy-load Kokoro pipeline."""
    global _kokoro_pipeline
    if _kokoro_pipeline is None:
        try:
            from kokoro import KPipeline
            # 'a' = American English
            _kokoro_pipeline = KPipeline(lang_code="a")
        except Exception as e:
            print(f"[TTS] Failed to load Kokoro: {e}")
    return _kokoro_pipeline


def _speak_kokoro(text: str, voice: str | None = None, blocking: bool = False) -> None:
    """Speak text using Kokoro local TTS."""
    global _kokoro_speaking
    if not text or not text.strip():
        return

    pipeline = _get_kokoro_pipeline()
    if pipeline is None:
        print("[TTS] Kokoro not available — skipping speech")
        return

    voice = voice or os.getenv("KOKORO_VOICE", "af_nova")
    speed = float(os.getenv("KOKORO_SPEED", "1.0"))

    def _run():
        global _kokoro_speaking
        _kokoro_speaking = True
        _kokoro_stop_event.clear()
        try:
            import sounddevice as sd
            import torch
            generator = pipeline.generate_from_tokens(text, voice=voice, speed=speed)
            for result in generator:
                if _kokoro_stop_event.is_set():
                    break
                audio = result.audio
                if isinstance(audio, torch.Tensor):
                    audio = audio.numpy()
                # audio is float32 numpy array at 24kHz
                sd.play(audio, samplerate=24000)
                sd.wait()
                if _kokoro_stop_event.is_set():
                    break
        except Exception as e:
            print(f"[TTS] Speak error: {e}")
        finally:
            _kokoro_speaking = False

    if blocking:
        _run()
    else:
        threading.Thread(target=_run, daemon=True, name="kokoro-tts").start()


def _stop_kokoro() -> None:
    """Stop any ongoing Kokoro speech."""
    global _kokoro_speaking
    _kokoro_stop_event.set()
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass
    _kokoro_speaking = False
