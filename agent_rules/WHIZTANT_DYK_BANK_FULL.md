# WHIZTANT — FULL DYK BANK EXPANSION
# Copy-paste append into your existing DYK_BANK dict
# Format: "app_key": ["fact1", "fact2", "fact3"]
# ─────────────────────────────────────────────────────────────────────────────

DYK_BANK_EXTENDED = {

    # ──────────────────────────────────────────
    # BROWSERS
    # ──────────────────────────────────────────

    "chrome": [
        "Chrome uses a separate process for every single tab — intentionally. Google research showed one crashing tab killing the browser was users' top frustration in 2008.",
        "Chrome's V8 JavaScript engine introduced JIT compilation to browsers — it compiles JS to native machine code on the fly. Before V8, JS ran 100x slower in pure interpreters.",
        "Chrome has a hidden dinosaur game at chrome://dino. The dinosaur's highest possible score is 99,999 — after which it silently resets back to zero.",
    ],
    "firefox": [
        "Firefox's rendering engine, Gecko, was the first browser engine to pass the Acid2 CSS test in 2006 — it exposed how broken every other browser's standards support actually was.",
        "Firefox introduced the concept of browser extensions to the mainstream. The Add-ons marketplace hit 1 billion downloads in 2011, years before Chrome had a comparable ecosystem.",
        "Firefox's 'Private Browsing' mode was originally called 'Porn Mode' in early Mozilla internal memos before someone decided that name wouldn't ship well.",
    ],
    "edge": [
        "Microsoft Edge (Chromium) is now the second-most-used desktop browser globally — it quietly overtook Firefox in 2021 without a single major announcement.",
        "Edge has a built-in 'Sleeping Tabs' feature that freezes inactive tabs and reclaims their RAM. Microsoft claims it reduces memory usage by up to 85% for power users with 50+ tabs.",
        "The original Edge (EdgeHTML) was rebuilt from scratch in Chromium in 18 months — Microsoft internally called the project 'Anaheim'. It was one of the fastest complete rewrites of a major browser in history.",
    ],
    "brave": [
        "Brave's built-in ad blocker works by blocking network requests at the browser engine level — not injecting JS like extension-based blockers. This makes it roughly 3–6x faster at page load.",
        "Brave's Basic Attention Token (BAT) was one of the first functional crypto integrations into a mainstream product — you earn BAT for viewing opt-in ads and tip it directly to websites.",
        "Brave was co-founded by Brendan Eich — the same person who invented JavaScript in 10 days in 1995 and later created the Mozilla Foundation.",
    ],
    "safari": [
        "Safari was built on the KHTML engine from the KDE Linux project — Apple engineers privately forked it in 2002, worked on it in secret for a year, and surprised the KDE team by announcing it publicly.",
        "Safari introduced the concept of nitro JavaScript engine hardware acceleration for mobile browsers in 2008 — no other mobile browser had JIT JS at the time.",
        "Safari is the last major browser not available on Windows. Apple killed the Windows version in 2012, which means Safari's render engine is now macOS/iOS exclusive — creating a permanent browser monoculture risk for Apple users.",
    ],
    "opera": [
        "Opera invented browser tabs in 2000 — years before Firefox or IE adopted them. It also invented Speed Dial, zoom controls, and mouse gestures for browsers, all of which were later copied by competitors.",
        "Opera was the first browser with a built-in VPN, added in 2016 for free — no extension, no signup. It's technically a proxy, not a full VPN, but it was a meaningful first in consumer browsers.",
        "The Norwegian company behind Opera sold it to a Chinese consortium in 2016 for $600M. The original Opera team then started a new browser called Vivaldi using the same principles.",
    ],
    "vivaldi": [
        "Vivaldi was built by the original founder of Opera after he lost control of it in the sale. It's the only major browser that lets you stack tabs horizontally AND vertically in a 2D tile layout.",
        "Vivaldi has a built-in email client, calendar, feed reader, and notes app — all inside the browser. No other mainstream browser has ever shipped this level of bundled productivity tools.",
        "Vivaldi's UI is built entirely in React and CSS — meaning power users can write custom CSS themes that modify every single pixel of the browser's interface.",
    ],
    "tor_browser": [
        "Tor Browser was originally developed by the US Naval Research Laboratory in the mid-1990s — the government needed anonymous communications for intelligence operations before releasing it publicly.",
        "Tor's onion routing works by wrapping data in three layers of encryption, each peeled off by a different relay node worldwide. No single node ever knows both the sender and destination.",
        "The Tor network has roughly 6,000–7,000 volunteer relay nodes globally. Despite this, the total bandwidth of the entire Tor network is less than a single major CDN's single data center.",
    ],

    # ──────────────────────────────────────────
    # CODE EDITORS & IDEs
    # ──────────────────────────────────────────

    "vscode": [
        "VS Code is built on Electron — essentially a Chromium browser rendering a website as a desktop app. Its entire UI is HTML, CSS, and JavaScript.",
        "The VS Code extension marketplace has over 50,000 extensions — but the core VS Code team has only ~20 engineers. The community built almost everything.",
        "VS Code's Intellisense uses the same TypeScript language server for TS, JS, and JSON — one engine with adapters, not separate systems per language.",
    ],
    "windsurf": [
        "Windsurf's Cascade reads your entire project tree — not just the open file — and builds a live dependency graph as you type.",
        "The name 'Windsurf' comes from Codeium's design manifesto: the user should ride the codebase, not fight the IDE.",
        "Windsurf's Turbo Mode was designed by studying how FAANG senior devs pair-program: act → verify → act, not continuous stream.",
    ],
    "cursor": [
        "Cursor is a fork of VS Code — it shares the exact same extension ecosystem, keyboard shortcuts, and settings format. Switching from VS Code to Cursor takes under 60 seconds.",
        "Cursor's 'Apply' feature diffs AI suggestions against your live code before writing — no other IDE-level AI tool had this review-before-write pattern when Cursor launched it.",
        "Cursor's engineering team is fewer than 10 people. It reached $100M ARR faster than almost any developer tooling company in history, including GitHub Copilot's early growth.",
    ],
    "intellij": [
        "IntelliJ IDEA was the first IDE to introduce inline code completion in 2001 — over a decade before GitHub Copilot. The feature was called 'Smart Code Completion' and it understood Java's type system deeply.",
        "JetBrains, IntelliJ's creator, is headquartered in Prague and Saint Petersburg and was bootstrapped — they never took VC funding. They reached profitability by year two and never gave up equity.",
        "IntelliJ's refactoring engine can rename a variable across every file in a massive monorepo in under a second — it does this using a persistent index it builds silently in the background whenever the project is open.",
    ],
    "pycharm": [
        "PyCharm's debugger can step through code backwards using 'Reverse Debugging' — a feature so obscure that most Python developers don't know it exists even after years of use.",
        "PyCharm builds a full type inference graph for your entire project at startup. This is why it uses 800MB+ of RAM — it's essentially running a static analysis engine in the background at all times.",
        "JetBrains released PyCharm Community edition completely free in 2014 — a direct response to Python developers choosing Sublime Text over paid IDEs. It converted most of those users within 18 months.",
    ],
    "vim": [
        "Vim was created in 1991 as an improvement on 'vi', which was created in 1976. The core modal editing model is nearly 50 years old and is still being actively used and extended.",
        "Vim's `:vimgrep` command can search regex patterns across every file in a project and display results in a quickfix list — most users discover this 3–5 years into using Vim.",
        "The creator of Vim, Bram Moolenaar, maintained it almost single-handedly for 32 years until he passed away in 2023. The community forked it as Neovim in 2014 specifically because one-person maintenance was a bus-factor risk.",
    ],
    "neovim": [
        "Neovim was created in 2014 by refactoring 30% of Vim's legacy C codebase in a single crowdfunded sprint. The original goal was just to fix Vim's async problem — it became a full ecosystem.",
        "Neovim's Lua configuration is faster to load than Vim's VimScript by roughly 10x — a meaningful difference when you're opening 20 files a day.",
        "Neovim's LSP client is built into the core since version 0.5 — meaning Neovim can use the exact same language server protocol that VS Code uses, giving it identical autocomplete quality with zero plugins.",
    ],
    "sublime_text": [
        "Sublime Text was built by one developer, Jon Skinner, as a side project. He left Google to work on it full-time and self-funded it for years before it became the dominant editor of the early 2010s.",
        "Sublime Text's 'Goto Anything' (Ctrl+P) was so revolutionary when it shipped that every major editor copied it within 2 years — VS Code, Atom, and even IntelliJ added identical implementations.",
        "Sublime Text's persistent trial mode (never forcing payment) is an intentional business decision — Jon Skinner has said it's a trust signal that the tool doesn't need to trap you to survive.",
    ],
    "notepad_plus": [
        "Notepad++ was created by Don Ho in 2003 as a politically symbolic project — the name is a jab at Microsoft's basic Notepad. It became the most downloaded editor on SourceForge for years.",
        "Notepad++ uses the Scintilla editing component — a code editing library originally written for the Scite editor in 1999 that now underpins dozens of editors and IDEs worldwide.",
        "Notepad++ has a plugin for hex editing, macro recording, FTP, and even a full Lua scripting environment — all community-written and all coexisting in a 5MB installer.",
    ],
    "atom": [
        "Atom was built by GitHub in 2014 specifically to be hackable at every level — its UI was rendered in Electron (which GitHub created for Atom) and styled with CSS that any user could override.",
        "Atom pioneered the concept of a package manager built into an editor — `apm install` predated VS Code's extension system by over a year.",
        "GitHub deprecated Atom in December 2022, citing the dominance of VS Code. The project was archived, but a community fork called 'Pulsar' picked up the codebase and continued development.",
    ],
    "emacs": [
        "GNU Emacs has been in active development since 1976 — making it one of the oldest continuously maintained software projects in computing history, predating the internet as most people know it.",
        "Emacs has a fully functional email client, web browser, IRC client, file manager, and even a psychotherapy simulation (M-x doctor) all built in — the joke is that Emacs is an OS that happens to have a text editor.",
        "Emacs Lisp — the language used to configure and extend Emacs — is a full Lisp dialect. Power users have written window managers, games, and even served HTTP requests from inside a running Emacs instance.",
    ],
    "xcode": [
        "Xcode's build system was completely rewritten in 2017 (Xcode 9) to support parallel builds. Before that, large iOS projects could take 10+ minutes to compile — the new system cut it to under 2 minutes for most apps.",
        "Xcode has a built-in performance profiler called Instruments that can record CPU, GPU, memory, disk, and network usage simultaneously at nanosecond resolution — a capability that usually requires enterprise APM tools.",
        "Xcode's simulator is so accurate that some developers use it exclusively during development and only test on real hardware for final QA — it even simulates push notification delivery.",
    ],
    "android_studio": [
        "Android Studio is a fork of IntelliJ IDEA — Google licensed JetBrains' core IDE and built their own tooling on top. Every Android developer is essentially using a JetBrains product.",
        "Android Studio's Layout Inspector lets you view your running app's UI as a 3D exploded view — you can rotate and inspect every view layer in real-time while the app runs on a device.",
        "Android Studio's emulator uses hardware virtualization (HAXM on Intel, WHPX on AMD) to run a full Android kernel at near-native speed — making it one of the most technically complex emulators available for free.",
    ],

    # ──────────────────────────────────────────
    # TERMINALS & SHELLS
    # ──────────────────────────────────────────

    "cmd": [
        "CMD.exe has barely grown in 30 years — the core binary is only ~200KB larger than the 1993 original. Still running on the same NT skeleton.",
        "CMD's hidden FOR loop can capture and iterate any command's output: `for /f %i in ('command') do echo %i` — no PowerShell needed.",
        "The command `tree /f /a` renders every file in every subfolder as ASCII art — Microsoft devs used this for plain-text README diagrams in the 90s.",
    ],
    "powershell": [
        "PowerShell was designed by Jeffrey Snover after Microsoft repeatedly rejected his ideas for a Unix-like shell. He wrote a manifesto called 'Monad' in 2002 that became the blueprint for everything PowerShell became.",
        "PowerShell passes .NET objects between commands — not text strings like every Unix shell. This means `Get-Process | Sort-Object CPU` sorts actual process objects, not parsed text output.",
        "PowerShell 7 is open source and cross-platform — it runs identically on Windows, Linux, and macOS. Microsoft open-sourced it in 2016, one of the most surprising pivots in the company's history.",
    ],
    "windows_terminal": [
        "Windows Terminal uses a GPU-accelerated renderer (AtlasEngine) that renders text using the same pipeline as video games — each character is a textured quad on a DirectX canvas.",
        "Windows Terminal's settings.json supports full JSON schema validation — your code editor will autocomplete every possible setting. No restart required for changes.",
        "The team behind Windows Terminal open-sourced ConPTY — the library that finally lets Windows terminal emulation be embedded in third-party apps the same way it works on Linux and macOS.",
    ],
    "wsl": [
        "WSL2 uses a real Linux kernel — Microsoft actually ships a Linux kernel binary inside every copy of Windows 10/11. It runs in a Hyper-V lightweight VM with a 1ms startup time.",
        "WSL2 can run GUI Linux apps natively on Windows — including full desktop environments. Microsoft integrated GPU passthrough so Linux apps can use your Windows GPU for rendering.",
        "The WSL team discovered that 40% of Windows developers were running Linux in a VM just to have a proper terminal — that discovery is what drove WSL's creation in 2016.",
    ],
    "bash": [
        "Bash (Bourne Again SHell) was written by Brian Fox in 1989 as a free software replacement for the Bourne shell. The 'Again' in the name is a pun that most people miss.",
        "Bash's `!!` re-runs the last command — and `sudo !!` is one of the most-typed command sequences in Linux history, used every time someone forgets to prepend sudo.",
        "Bash has a built-in calculator: `echo $((2**32))` computes 2 to the power of 32. Most developers use Python for this when bash arithmetic has been right there the whole time.",
    ],
    "zsh": [
        "Zsh has recursive path expansion — you can type `/u/lo/b` and press Tab, and it expands to `/usr/local/bin` without typing the full path. Most Bash users don't know this exists.",
        "Oh My Zsh has over 300 plugins and 150+ themes. It's arguably the most-installed shell framework in the world — yet the creator originally wrote it as a personal config file he shared on a whim.",
        "Zsh became the default shell on macOS in Catalina (2019) after 28 years of bash being the default. Apple switched specifically because bash hadn't updated past version 3.2 due to GPL licensing concerns.",
    ],
    "fish": [
        "Fish shell gives you autosuggestions from your command history in real-time as you type — in grey text to the right of your cursor. This feature shipped in 2006, 10 years before any other shell had it.",
        "Fish's configuration is done through a web UI that you launch with `fish_config` — it opens a browser-based interface to set colors, prompts, and functions. No config files required.",
        "Fish stands for 'Friendly Interactive SHell' — it was designed explicitly to be usable without reading a manual. All its syntax decisions were made with zero Unix legacy compatibility as a constraint.",
    ],
    "iterm2": [
        "iTerm2's tmux integration lets you manage tmux sessions through native macOS window tabs — meaning you can detach/reattach servers without learning tmux key bindings at all.",
        "iTerm2 has a 'Instant Replay' feature (Cmd+Opt+B) that lets you scroll back through terminal output like a video — even output that has already scrolled off screen.",
        "iTerm2 can trigger custom actions based on regex matches in terminal output — developers use this to auto-highlight IP addresses, errors, or test failures and jump to them instantly.",
    ],

    # ──────────────────────────────────────────
    # AI & ML TOOLS
    # ──────────────────────────────────────────

    "ollama": [
        "Ollama keeps a daemon alive on port 11434 — if the model is already in VRAM, your second call is near-instant vs 5s cold load.",
        "Ollama's GGUF format was written by one developer (Georgi Gerganov) in a single weekend — it's now the universal local model format.",
        "The name 'Ollama' has a deliberate double-L — a nod to Meta's LLaMA models baked into the product's identity from day one.",
    ],
    "lm_studio": [
        "LM Studio can run models fully offline after a one-time download — no telemetry, no cloud calls, no API key. Your conversations never leave your machine.",
        "LM Studio's model compatibility layer supports GGUF, GPTQ, and EXL2 formats — meaning it can load models from three completely different quantization ecosystems with one interface.",
        "LM Studio ships with a local OpenAI-compatible API server — any app written for OpenAI's API (like custom scripts or tools) can be pointed at localhost:1234 with zero code changes.",
    ],
    "chatgpt": [
        "ChatGPT reached 100 million users in 2 months — the fastest any consumer application in history had done so. For comparison, Instagram took 2.5 years to reach the same milestone.",
        "ChatGPT's first public version (GPT-3.5) was not OpenAI's most capable model — it was a deliberately cheaper, faster variant. OpenAI's researchers described releasing it as a 'calculated bet' on consumer product.",
        "The name 'ChatGPT' was almost 'OpenAI Chat' internally — 'ChatGPT' was chosen specifically because GPT was already a recognized term among developers, giving it instant credibility with a technical early-adopter audience.",
    ],
    "claude_ai": [
        "Claude's name comes from Claude Shannon — the mathematician who invented information theory in 1948. Shannon's work literally made all digital communication possible.",
        "Anthropic was founded by former OpenAI employees, including OpenAI's former VP of Research. The split came over disagreements about safety-first development pace vs. product-first deployment speed.",
        "Claude's 'Constitutional AI' training method uses a written set of principles to guide the model's values — instead of relying only on human feedback scoring every response. It's the first published AI training method that makes the model's values explicit and auditable.",
    ],
    "gemini": [
        "Google Gemini was the first AI model natively trained on text, images, audio, and video simultaneously — not separate models bolted together. The architecture was designed multimodal from day one.",
        "Gemini's 1 million token context window can hold approximately 750,000 words — enough to load the entire Lord of the Rings trilogy and still have room for a full novel.",
        "Gemini Ultra outperformed human experts on the MMLU benchmark (a test of 57 academic subjects) — the first AI model to do so. The margin was slim (90.0% vs 89.8%) but it crossed the threshold.",
    ],
    "copilot": [
        "GitHub Copilot was trained on all public GitHub code — roughly 54 million repositories. This caused significant debate about whether open-source code could be used for commercial AI training without attribution.",
        "Copilot's acceptance rate (how often developers keep its suggestions) averages around 30% — but for boilerplate and test code, that rate rises to over 60%. It's most useful for code you'd rather not type.",
        "GitHub Copilot generates roughly 46% of the code written by developers who use it daily, according to GitHub's 2023 productivity research. It's the first tool to demonstrably shift what 'writing code' means.",
    ],
    "midjourney": [
        "Midjourney is run by a team of fewer than 12 people — making it one of the highest revenue-per-employee companies in tech history. It has no app, no website sign-up, just a Discord bot.",
        "Midjourney's founder David Holz previously co-founded Leap Motion — the hand-tracking hardware startup. He has a background in physics, not machine learning, which shaped Midjourney's art-first design philosophy.",
        "Midjourney v5 was trained partially on images that generated disagreement within the AI art community — it sparked the first large-scale debate about whether AI companies need an opt-out for artists before training.",
    ],
    "stable_diffusion": [
        "Stable Diffusion's model weights were released publicly in 2022 — a decision Stability AI made against the advice of nearly every other AI safety researcher. It made high-quality image generation available to anyone with a GPU overnight.",
        "The diffusion process in Stable Diffusion works by starting with pure noise and slowly removing it — guided by a text description. The mathematics behind this comes from thermodynamics, specifically how gas particles spread.",
        "Stable Diffusion can run in real-time on a modern GPU with the right optimizations — generating a new image every frame, fast enough to essentially 'paint' with AI as if it were a brush.",
    ],
    "hugging_face": [
        "Hugging Face started as a chatbot company for teenagers — it was a consumer app, not an AI infrastructure platform. The pivot to developer tools happened when they noticed engineers loved their open-source NLP library more than the product.",
        "Hugging Face's model hub hosts over 350,000 models — more than all other model repositories combined. Any developer anywhere can push and pull models with one CLI command.",
        "The Transformers library from Hugging Face standardized how the entire industry loads and uses language models. Before it, every lab had incompatible weight formats — Transformers created a common interface.",
    ],
    "langchain": [
        "LangChain was written by Harrison Chase in a single week in 2022 as a personal project. It hit 50,000 GitHub stars in under 6 months — faster than almost any developer library in recent history.",
        "LangChain introduced the concept of 'chains' — composable sequences of LLM calls plus tools — which became the dominant mental model for building AI agents across the entire industry.",
        "LangChain has been criticized for being overengineered for simple tasks. Its own creators acknowledge this — they released LangChain Expression Language (LCEL) specifically to let developers write simpler, more readable pipelines.",
    ],

    # ──────────────────────────────────────────
    # VERSION CONTROL
    # ──────────────────────────────────────────

    "git": [
        "Linus Torvalds wrote the first version of Git in 10 days after a licensing dispute. He had it managing the Linux kernel in under 2 weeks.",
        "Git's `bisect` command uses binary search — it can pinpoint which commit broke your code in just 10 questions across 1000 commits. Most devs never find it.",
        "Two files with identical content in Git are stored as a single object regardless of how many branches they're in — that's why repos stay small.",
    ],
    "github": [
        "GitHub was built over a single weekend by Tom Preston-Werner, Chris Wanstrath, and PJ Hyett in 2007. They launched it publicly without a business plan and didn't charge for months.",
        "GitHub's mascot — the Octocat — was designed by illustrator Simon Oxley, who also created the Twitter bird. He sold both for a few hundred dollars each and received no royalties when they became iconic.",
        "Microsoft acquired GitHub for $7.5 billion in 2018 — at the time, GitHub had fewer than 900 employees. That works out to roughly $8.3 million per employee, one of the highest acquisition price-per-head ratios in tech.",
    ],
    "gitlab": [
        "GitLab was started by two developers in Ukraine and the Netherlands who had never met in person — they collaborated entirely online for the first year of development.",
        "GitLab ships a new release on the 22nd of every single month — a discipline they've maintained since 2011. It's one of the most consistent release cadences of any major software platform.",
        "GitLab's entire company operates remotely — they've been fully distributed since founding. Their 'Remote Playbook' is publicly available and has been adopted by dozens of other companies.",
    ],
    "bitbucket": [
        "Bitbucket was one of the first platforms to offer unlimited private repositories for free — GitHub charged for private repos until 2019. This gave Bitbucket a significant advantage with small teams for nearly a decade.",
        "Atlassian acquired Bitbucket in 2010 for $10 million — considered cheap even at the time. The integration with Jira and Confluence became the main reason enterprise teams chose it over GitHub.",
        "Bitbucket originally supported Mercurial repositories alongside Git — it dropped Mercurial support in 2020, effectively ending Mercurial's relevance in mainstream software development.",
    ],

    # ──────────────────────────────────────────
    # COMMUNICATION
    # ──────────────────────────────────────────

    "slack": [
        "Slack was originally an internal tool built by a gaming company called Glitch. The game failed, but the chat tool was so useful that the team pivoted — renaming the company and productizing the chat.",
        "The name SLACK is an acronym: Searchable Log of All Conversation and Knowledge. Most Slack users have no idea it stands for anything.",
        "Slack's threading model was a deliberate late addition — the original design had no threads at all. The team resisted threads for years, believing linear channels were simpler. They added threads in 2017 under pressure.",
    ],
    "discord": [
        "Discord was originally built for gamers — the founders tried to build a gaming company first (Fates Forever) and Discord was the communication tool they made for their game's players.",
        "Discord uses Opus audio codec at variable bitrates — defaulting to 64kbps but adjusting dynamically. This is the same codec used by WebRTC and Google Meet, which is why Discord voice quality rivals enterprise tools.",
        "Discord's infrastructure handles over 4 billion minutes of voice calls per day. Its engineering blog posts on their architecture — particularly their Rust-based voice server 'Dave' — are considered required reading for distributed systems engineers.",
    ],
    "telegram": [
        "Telegram's founder Pavel Durov also founded VKontakte (VK), Russia's largest social network. He was forced out of VK by Russian authorities in 2014 and immediately started Telegram in exile.",
        "Telegram's MTProto encryption protocol was designed in-house, not based on Signal Protocol — a decision that cryptographers have criticized extensively. Telegram's 'secret chats' use end-to-end encryption, but regular chats do not.",
        "Telegram stores all non-secret-chat messages on its own servers in plaintext — this is what enables cross-device sync. It's a deliberate design choice that trades security for convenience and is different from how WhatsApp or Signal work.",
    ],
    "whatsapp": [
        "WhatsApp was founded by two former Yahoo engineers who had both been rejected in job applications by Facebook — and later sold the company to Facebook for $19 billion.",
        "WhatsApp used the XMPP protocol (originally designed for instant messaging in 1999) as its base and modified it heavily. The entire original server was written in Erlang — an unusual choice that let it handle millions of concurrent connections on minimal hardware.",
        "When Facebook acquired WhatsApp, it had 55 employees and 450 million users. That's roughly 8 million users per employee — an operational efficiency ratio that has never been matched by any other social platform.",
    ],
    "teams": [
        "Microsoft Teams was built in just 4 months in 2016 — it was a direct response to internal reports that Slack was gaining ground inside Microsoft itself. Teams launched before any external market demand had been formally measured.",
        "Teams is built on Electron + React, the same tech stack as Slack — which is part of why early versions were criticized for being slow. Microsoft rewrote significant portions to run natively on Windows after user backlash.",
        "Microsoft bundled Teams into Office 365 at no extra cost — a move the European Union ruled anti-competitive in 2023. Microsoft was forced to unbundle Teams from Microsoft 365 globally.",
    ],
    "zoom": [
        "Zoom's founder Eric Yuan left Cisco/WebEx after proposing video conferencing improvements that were rejected. He took 40 engineers with him, built Zoom in 2013, and made it more reliable than WebEx within two years.",
        "Zoom's architecture uses a globally distributed routing network that selects the optimal data path in real time — which is why Zoom calls degrade more gracefully than competitors when a network path fails.",
        "During COVID-19 lockdowns, Zoom went from 10 million daily meeting participants to 300 million in 4 months — the fastest user growth of any enterprise software tool ever recorded.",
    ],
    "signal": [
        "Signal Protocol is the encryption standard used by Signal, WhatsApp, Facebook Messenger's secret chats, and Google's RCS — meaning one small nonprofit's cryptography protects billions of conversations globally.",
        "Signal was created by Moxie Marlinspike, a security researcher who was also a professional sailor. He once spent months at sea with no internet while co-developing early encryption protocols.",
        "Signal's server code is open source — anyone can verify how Signal handles messages on its servers. This level of server-side transparency is unique among mainstream messaging apps.",
    ],
    "gmail": [
        "Gmail launched on April 1, 2004 — and most people thought it was an April Fools' joke. It offered 1GB of storage when Yahoo and Hotmail offered 4MB. Tech journalists spent 24 hours debating if it was real.",
        "Gmail's original design was built by one engineer, Paul Buchheit, over a single weekend prototype. He used Google's internal infrastructure and had a basic working email client in under 3 days.",
        "Gmail introduced the concept of conversation threading for email — grouping replies into a single thread. Before Gmail, nearly every email client showed messages as individual items. This UX decision became universal.",
    ],
    "outlook": [
        "Outlook was originally a separate product from Exchange — it started as a personal information manager called 'Schedule+' in 1992. It was merged with the email client and rebranded Outlook in 1997.",
        "Outlook's rendering engine for HTML emails is based on Microsoft Word — not a browser engine. This is why HTML email design is a separate discipline: developers must write email HTML that works in a 25-year-old word processor.",
        "Outlook's search is powered by Windows Search indexing — which is why Outlook search is near-instant when the index is warm, and extremely slow when it's not. The index lives in %localappdata%\\Microsoft\\Outlook.",
    ],

    # ──────────────────────────────────────────
    # PRODUCTIVITY & NOTES
    # ──────────────────────────────────────────

    "notion": [
        "Notion was nearly shut down in 2018 — the team had less than 12 months of runway and had rebuilt the product twice from scratch. A last-minute surge of Product Hunt attention saved the company.",
        "Notion's block-based architecture — where every element (paragraph, heading, database row) is a composable block — was inspired by the Unix philosophy of small tools that compose well.",
        "Notion's database feature wasn't in the original product. It was added in 2018 as an experiment. Within a year, it was the most-used feature and the primary reason teams chose Notion over Confluence.",
    ],
    "obsidian": [
        "Obsidian stores all notes as plain Markdown files on your local disk — no proprietary format, no server dependency. Your notes are readable in any text editor, now and in 20 years.",
        "Obsidian's graph view renders a visual network of all linked notes — the first time most users see it, it reveals conceptual connections in their own thinking they weren't aware of.",
        "Obsidian was built by two former Evernote employees who wanted to solve the problem they'd been unable to fix from inside: notes that don't connect to each other and can't be exported safely.",
    ],
    "evernote": [
        "Evernote was launched in 2008 and reached 225 million users — then nearly went bankrupt in 2017 when it ran out of money after failing to build a sustainable enterprise product around its consumer base.",
        "Evernote introduced the concept of OCR inside notes — it could search handwritten text in photographs before any other mainstream app. This was considered near-magical in 2008.",
        "Evernote's original mascot is an elephant — chosen because elephants never forget. It's one of the few tech brand mascots where the connection between animal and product feature is completely literal.",
    ],
    "onenote": [
        "OneNote was released in 2003 — before Evernote, before Notion, before Apple Notes added any real features. It was the first major digital notebook and is now free, yet it's consistently underestimated.",
        "OneNote's freeform canvas lets you place text, images, and drawings anywhere on an infinite 2D surface — a design decision from 2003 that was ahead of tools like Miro and FigJam by 15 years.",
        "OneNote syncs through OneDrive in real time across every device — yet most Windows users don't know it comes pre-installed and have paid for Evernote or Notion to do the same thing.",
    ],
    "todoist": [
        "Todoist uses natural language processing to parse due dates — typing 'submit report every Friday at 5pm' creates a recurring task with the correct schedule. No form fields, no dropdowns.",
        "Todoist was built by Amir Salihefendic, a Bosnian developer who started it as a side project in 2007 while studying computer science. He bootstrapped it to profitability before raising any money.",
        "Todoist's Karma system — which tracks productivity streaks and gives points for completing tasks — was added after research showed gamification increased daily active use by 40% without making the app feel like a game.",
    ],
    "trello": [
        "Trello was built by Fog Creek Software in 2011 as a side project — it was shown at TechCrunch Disrupt and immediately drew 22,000 signups with zero marketing budget.",
        "Trello's kanban board interface was inspired by Toyota's production system — specifically the physical card walls used on Japanese factory floors to track manufacturing stages.",
        "Atlassian acquired Trello for $425 million in 2017 — at the time, Trello had 19 million users and was growing entirely on word of mouth. The acquisition was Atlassian's largest ever.",
    ],
    "jira": [
        "Jira was named after 'Gojira' — the Japanese name for Godzilla. Atlassian's original internal tools were named after monsters, and Jira stuck as the most pronounceable one.",
        "Jira's JQL (Jira Query Language) is a full query syntax that most teams never use — but power users can write queries more complex than SQL to filter issues across every field and relationship.",
        "Jira's performance has been criticized so consistently that 'Jira is slow' became a running joke in software engineering. Atlassian's Cloud migration was partly driven by the need to fix this at the infrastructure level.",
    ],
    "confluence": [
        "Confluence was built in 2004 before wikis were mainstream — it predated MediaWiki's widespread adoption and was the first wiki designed for corporate team documentation.",
        "Confluence's search is powered by Lucene — the same search engine library that powers Elasticsearch. On a well-indexed large instance, you can search across millions of pages in under 200ms.",
        "Confluence has a 'Space' model — where each team gets a separate documentation space with its own permissions, navigation, and theme. This model was widely copied by Notion, GitHub Wikis, and others.",
    ],

    # ──────────────────────────────────────────
    # CLOUD & DEVOPS
    # ──────────────────────────────────────────

    "docker": [
        "Docker was announced at PyCon 2013 by Solomon Hykes in a 5-minute lightning talk. Nobody in the audience had seen containers packaged this way before — the demo went viral overnight.",
        "Docker doesn't create virtual machines — it uses Linux kernel namespaces and cgroups to create isolated process environments. On a Mac or Windows, Docker runs a hidden Linux VM to provide these kernel features.",
        "The Docker Hub image registry receives over 10 billion pulls per month — making it the world's largest source of containerized software, larger than npm or PyPI in download volume.",
    ],
    "kubernetes": [
        "Kubernetes was created by Google engineers who had spent a decade running Google's internal container orchestration system called Borg. Kubernetes is essentially a public, simplified version of Borg.",
        "Kubernetes' name comes from the Greek word for helmsman or pilot — the same root as 'governor' and 'cybernetics'. The logo is a steering wheel with 7 spokes — a nod to the 'seven of nine' Star Trek character on the team.",
        "Kubernetes was donated to the CNCF (Cloud Native Computing Foundation) by Google in 2016 — a strategic move to prevent AWS or Azure from forking and controlling it. The neutral governance was a calculated defensive moat.",
    ],
    "aws": [
        "AWS started as Amazon's internal infrastructure — Jeff Bezos mandated in 2002 that every internal team must expose their services via APIs as if they were building for external customers. Three years later, they had a product to sell.",
        "S3 (Simple Storage Service) was AWS's first public service, launched in 2006. It's still one of the most profitable services — storing a significant fraction of the world's internet data on a system that started as an internal file store.",
        "AWS's EC2 was inspired by the academic grid computing concept. The name 'Elastic Compute Cloud' was chosen to emphasize that compute could scale like an elastic band — a revolutionary idea in an era of fixed-capacity servers.",
    ],
    "gcp": [
        "Google Cloud Platform's biggest technical advantage is its private fiber network — Google owns and operates one of the largest private undersea cable networks in the world. GCP traffic often bypasses the public internet entirely.",
        "BigQuery — GCP's data warehouse — can run SQL queries across petabyte-scale datasets in under 30 seconds. It achieves this by distributing queries across thousands of servers in parallel and billing only for bytes scanned.",
        "Google Kubernetes Engine (GKE) runs on the same infrastructure that runs Google Search, Gmail, and YouTube. When GKE autoscales your cluster, it's using the same scheduler that Google uses to run their own global services.",
    ],
    "azure": [
        "Azure was called 'Red Dog' during development — a reference to an internal Microsoft culture shift. When Satya Nadella led Azure, he reportedly carried a laminated card with 'Mobile First, Cloud First' in his wallet.",
        "Azure Active Directory (now Entra ID) handles over 1.2 billion authentications per day — more sign-ins per day than any other identity platform on earth, including Google's.",
        "Azure's data centers are cooled using a closed-loop liquid cooling system in newer regions — Microsoft has also experimented with underwater data centers (Project Natick) that use seawater cooling with zero freshwater consumption.",
    ],
    "netlify": [
        "Netlify invented the concept of 'JAMstack' — JavaScript, APIs, and Markup. The term was coined by Netlify's CEO Mathias Biilmann in 2016, and it redefined how the front-end community thought about web architecture.",
        "Netlify's global CDN deploys every commit as an immutable, atomic deployment — meaning you can instantly roll back to any previous version of your site in one click, going back to the very first commit.",
        "Netlify introduced 'Deploy Previews' — a unique URL for every pull request that shows a live preview of those changes. GitHub Actions and Vercel later copied this pattern, making it a standard workflow in modern web development.",
    ],
    "vercel": [
        "Vercel was founded by Guillermo Rauch, who also created Socket.io and Mongoose — two of the most widely used npm packages ever written. He built Vercel to deploy his own tools more efficiently.",
        "Vercel's Edge Runtime runs JavaScript at the CDN layer — meaning your API routes execute inside the network routing infrastructure itself, not in a data center. This gives ~40ms response times globally.",
        "Next.js, which Vercel maintains, is now used by over 25% of all React-based websites. Vercel built an open-source framework and then built a hosting business optimized for that exact framework — a vertical integration strategy that no other cloud provider has replicated.",
    ],
    "supabase": [
        "Supabase calls itself 'the open source Firebase alternative' — and every part of it is built on existing open-source projects. Postgres, PostgREST, GoTrue, Realtime, and Storage are all external projects Supabase wires together.",
        "Supabase's real-time feature works by listening to Postgres's write-ahead log (WAL) — the same mechanism databases use for replication. Any INSERT, UPDATE, or DELETE broadcasts to subscribed clients in milliseconds.",
        "Supabase was backed by Y Combinator in 2020. Their pitch was essentially 'Firebase is a lock-in trap — here's the same DX on Postgres you can self-host.' The YC partners reportedly invested on the spot.",
    ],
    "firebase": [
        "Firebase was originally a startup called Envolve that built a chat API. Engineers noticed customers were using the chat API to pass game state — not chat messages. They rebuilt it as a real-time database and sold the company to Google.",
        "Firebase Realtime Database uses WebSockets and a diff-based sync protocol — when one client changes data, only the diff (the change) is broadcast to all other clients, not the full dataset.",
        "Firebase Authentication supports 12 identity providers out of the box — including anonymous authentication that lets you track user behavior before they sign up and seamlessly migrate the data when they do.",
    ],
    "terraform": [
        "Terraform was created by HashiCorp's Mitchell Hashimoto, who also created Vagrant, Packer, Vault, and Consul — a single engineer who fundamentally shaped how the entire DevOps tooling industry works.",
        "Terraform's HCL (HashiCorp Configuration Language) was designed to be both human-readable and machine-parseable — a balance almost no other infrastructure language achieves. It was explicitly designed to not be YAML.",
        "Terraform's state file is the most dangerous file in any infrastructure setup — it contains the mapping between your code and real cloud resources. Deleting it doesn't delete your infrastructure, but it means Terraform can never manage those resources again.",
    ],
    "nginx": [
        "NGINX was written by Igor Sysoev to solve the C10k problem — how to handle 10,000 simultaneous connections. Apache (the dominant server at the time) used one thread per connection and ran out of memory at scale.",
        "NGINX uses an event-driven, asynchronous architecture — a single NGINX process can handle thousands of simultaneous connections without spawning new threads. This is the same model Node.js uses.",
        "NGINX is used by over 34% of all websites — including most of the top 10,000 sites globally. Yet the entire project was written by one developer in his spare time over several years before it became a company.",
    ],

    # ──────────────────────────────────────────
    # DATABASES
    # ──────────────────────────────────────────

    "postgresql": [
        "PostgreSQL descends from POSTGRES, a research project at UC Berkeley started in 1986. The codebase has been in continuous development for nearly 40 years — longer than most commercial databases.",
        "PostgreSQL's JSONB type stores JSON as a binary format that can be indexed and queried with a full text search syntax — making Postgres a document database, a relational database, and a search engine in one.",
        "PostgreSQL has zero paid license fees, zero commercial restrictions, and is used by Apple, Instagram, Spotify, Twitch, and Reddit. It's the most feature-rich open-source database on the planet.",
    ],
    "mysql": [
        "MySQL was created by Michael Widenius (Monty), whose daughters are named My and Maria — hence MySQL and MariaDB (the fork he created after Oracle acquired MySQL).",
        "MySQL's InnoDB storage engine — which handles all modern MySQL transactions — was developed by a Finnish company that Oracle acquired separately from MySQL. MySQL had two completely separate codebases before they were merged.",
        "Instagram ran on MySQL for years at massive scale, processing millions of photos per day. They wrote custom sharding logic by hand because MySQL had no native horizontal scaling. That code was open-sourced and used by dozens of other companies.",
    ],
    "mongodb": [
        "MongoDB was created by the founders of DoubleClick — the ad tech company. They needed a database that could store and query schema-less ad data at scale and couldn't find one, so they built it.",
        "MongoDB's name comes from 'humongous' — a reference to the scale of data they needed to handle. The 'mongo' prefix was a deliberate abbreviation to keep it memorable.",
        "MongoDB Atlas's serverless tier bills per read/write operation — meaning you can run a small production app for literally $0 per month if traffic is low. This zero-floor pricing changed how startups approach database cost planning.",
    ],
    "redis": [
        "Redis was written by Salvatore Sanfilippo (antirez) in 2009 to solve a performance bottleneck in his own startup's logging system. He wrote the first version in a weekend and open-sourced it without expecting adoption.",
        "Redis is single-threaded by design — it processes all commands in a single execution loop. This sounds like a limitation but is a feature: it makes every operation atomic with zero lock contention.",
        "Redis supports 5 core data structures (strings, hashes, lists, sets, sorted sets) plus streams, HyperLogLog, geospatial indexes, and pub/sub. It's the Swiss Army knife of in-memory data — most teams only use 10% of what it can do.",
    ],
    "sqlite": [
        "SQLite is the most deployed database in the world — it's in every Android phone, every iPhone, every Firefox browser, every Chrome browser, and every Mac. There are estimated to be over 1 trillion SQLite databases in active use.",
        "SQLite was designed for embedded systems and has a deliberate size target: the entire source code (in a single C file) must fit on a floppy disk. The amalgamation file is still under 250,000 lines.",
        "SQLite's creator D. Richard Hipp is a lone developer who maintains it almost entirely by himself with a small team. It has a test suite with 100% branch coverage — an engineering standard achieved by almost no other software project.",
    ],

    # ──────────────────────────────────────────
    # DESIGN TOOLS
    # ──────────────────────────────────────────

    "figma": [
        "Figma was the first design tool built entirely in the browser using WebGL for rendering. Before Figma, design tools were all desktop-native apps. Building a design tool in a browser in 2012 was considered technically impossible.",
        "Figma's multiplayer collaboration uses CRDTs (Conflict-Free Replicated Data Types) — the same data structure used by distributed databases to resolve conflicts without a central server. It's why two designers can edit the same frame simultaneously without conflict.",
        "Adobe acquired Figma for $20 billion in 2022 — the largest acquisition in Adobe's history and one of the largest software acquisitions ever. The EU antitrust regulators blocked it in 2023, and Adobe paid Figma a $1 billion breakup fee.",
    ],
    "sketch": [
        "Sketch was the first design tool to introduce the concept of Symbols — reusable design components that update everywhere when you change the master. Figma, Adobe XD, and every other tool copied this within two years.",
        "Sketch is macOS-only by design — a deliberate decision to avoid cross-platform compromise. The team believes the Mac UI toolkit gives them access to native performance and gestures that a cross-platform framework can't match.",
        "Sketch pioneered the design handoff workflow — exporting specs, measurements, and assets directly to developers without manual annotation. This workflow is now universal across design tools.",
    ],
    "adobe_xd": [
        "Adobe XD was Adobe's response to Sketch — built from scratch in 2 years after Sketch took significant market share from Adobe Illustrator as the go-to UI design tool.",
        "Adobe XD introduced the concept of Repeat Grid — a feature that lets you create a list of repeated elements and populate all instances with different data simultaneously. No other tool had this when it launched.",
        "Adobe announced discontinuing active development on XD in 2023, redirecting resources to Figma — which it had just tried (and failed) to acquire. Adobe Creative Cloud users were offered Figma as the replacement.",
    ],
    "photoshop": [
        "Photoshop was written by two brothers — Thomas and John Knoll. Thomas wrote the image processing engine as his PhD project; John was a filmmaker who added the practical tools. They sold it to Adobe in 1988 for $34.5 million.",
        "The 'lasso tool', 'magic wand', 'layers', and 'history panel' were all Photoshop inventions — concepts that didn't exist in any other software before Photoshop shipped them and that every image editor since has copied.",
        "Photoshop's PSD file format stores full editing history — layers, masks, adjustment layers, smart objects — in a binary format that has barely changed since the 1990s. It's considered one of the most complex file formats in consumer software.",
    ],
    "illustrator": [
        "Adobe Illustrator was the first major commercial application to use PostScript for rendering — meaning vector shapes were mathematically described, not pixel-based. This was revolutionary in 1987 when pixels were the only language computers spoke visually.",
        "Illustrator's Pen Tool is so precise that it's taught in industrial design, architecture, and typography programs worldwide — mastering it is considered a foundational skill in graphic design, not just a software feature.",
        "Illustrator's SVG export created the modern SVG standard. When the web needed a scalable vector format, the SVG working group based the spec heavily on Illustrator's output format.",
    ],
    "davinci_resolve": [
        "DaVinci Resolve was the color grading system used on nearly every major Hollywood film before it was rebranded as an NLE. The name 'DaVinci' predates Blackmagic Design's ownership — it was originally a hardware color corrector from the 1980s.",
        "DaVinci Resolve's free version has no watermark, no export limit, and no feature restriction for most professional workflows. The paid Studio version costs a one-time $295 — no subscription. This pricing destroyed the subscription model for video editing.",
        "Resolve's Fusion tab contains a full node-based visual effects compositor — the same kind used for blockbuster VFX. It's a complete After Effects alternative embedded inside a free video editor.",
    ],
    "after_effects": [
        "After Effects was created by Company of Science and Art (CoSA) in 1993 and acquired by Adobe in 1994. It was originally designed for traditional motion graphics compositing, not the motion design tool it became.",
        "After Effects' expressions engine uses JavaScript — a fact most motion designers don't realize. Complex rigs, wiggle expressions, and automated animations are full JavaScript programs running inside the compositor.",
        "Lottie animations — used by apps like Airbnb, Google, and Snapchat for lightweight animated illustrations — are exported directly from After Effects using a plugin called Bodymovin. The entire mobile animation economy runs on AE.",
    ],
    "canva": [
        "Canva was founded in Australia and rejected by every major Silicon Valley investor. The founders flew to San Francisco and convinced investors through sheer persistence — one investor only took the meeting because they kept showing up to his office.",
        "Canva processes over 15 million design exports per day. Its backend image processing pipeline — resizing, font rendering, color conversion — runs on a custom Rust-based rendering engine that replaced their earlier Python stack.",
        "Canva's free tier is genuinely free — not a trial. Over 60% of Canva's monthly active users have never paid anything, and the company is profitable primarily from the 40% who upgrade to Pro for premium assets.",
    ],

    # ──────────────────────────────────────────
    # MEDIA & ENTERTAINMENT
    # ──────────────────────────────────────────

    "spotify": [
        "Spotify was rejected by every major label when it first pitched its streaming model in 2006. The founders negotiated licensing deals for 2 years before launching — they couldn't go public or raise capital until the music industry signed.",
        "Spotify's 'Discover Weekly' playlist was an internal hackathon project. A small team built the recommendation engine in a week, launched it as an experiment, and it became the most-shared feature in Spotify's history.",
        "Spotify stores roughly 100 million songs — but studies show that 80% of all listening time is spent on the top 50,000 tracks. The long tail of music exists on Spotify but is almost never heard.",
    ],
    "youtube": [
        "YouTube was originally designed as a video dating site — the founders registered the domain on Valentine's Day 2005. They couldn't get users to upload dating videos, so they opened it to any video. The first upload was a 19-second clip of co-founder Jawed Karim at a zoo.",
        "YouTube serves over 1 billion hours of video per day. At average bitrate, that's approximately 720 petabytes of video data transferred every 24 hours — more data than all internet traffic combined in 2000.",
        "YouTube's recommendation algorithm is one of the most studied and criticized AI systems ever built. Internal research (leaked in 2021) showed the algorithm consistently recommended increasingly extreme content to maximize watch time.",
    ],
    "netflix": [
        "Netflix's original recommendation algorithm was so important that they ran a $1 million prize competition (The Netflix Prize) to improve it. The winning algorithm was 10.06% better than their existing system — but Netflix never deployed it because streaming had replaced DVDs by the time it was finished.",
        "Netflix invented the A/B testing framework that most tech companies now use. They test every feature — including thumbnail images — on random subsets of users before global rollout. Each Netflix subscriber sees a slightly different product.",
        "Netflix's Open Connect CDN is now the largest content delivery network in the world for video. Netflix deploys physical server boxes inside ISPs globally — meaning when you press play, the video often comes from a server inside your internet provider's building.",
    ],
    "twitch": [
        "Twitch started as Justin.tv — a single camera livestream of founder Justin Kan's life, 24 hours a day. The gaming section grew so popular that it spun off as Twitch.tv in 2011. Justin.tv was shut down when Twitch took over.",
        "Twitch was acquired by Amazon for $970 million in 2014 — Amazon outbid Google at the last minute. Google had a deal in place and reportedly lost the acquisition in a last-minute renegotiation.",
        "Twitch uses Akamai and Amazon CloudFront in tandem — a streaming architecture with zero single points of failure. The infamous 'Twitch-Con' traffic spikes exceed 3 Tbps and have never taken the platform offline.",
    ],
    "vlc": [
        "VLC was written in 1996 by students at the École Centrale Paris as their graduation project. They open-sourced it in 2001 — and it has been downloaded over 3.5 billion times, making it the most downloaded open-source desktop app ever.",
        "VLC can open almost any video file without installing codecs because it bundles every decoder it needs internally — MPEG-4, H.264, H.265, AV1, VP9 — all compiled into one 40MB app.",
        "VLC has a network stream feature that lets it play video directly from URLs, RTSP streams, and FTP servers — most users never know it's a full media streaming client, not just a local file player.",
    ],

    # ──────────────────────────────────────────
    # SYSTEM TOOLS
    # ──────────────────────────────────────────

    "task_manager": [
        "Windows Task Manager was written in one week by Microsoft developer Dave Plummer in 1994 as a side project. He showed it to his manager, who liked it, and it shipped with Windows NT 4.0 without a formal spec.",
        "Task Manager's performance graphs use a rolling 60-second window — but the sampling rate changes based on load. Under high CPU pressure, it increases its sampling frequency automatically.",
        "Ctrl+Shift+Esc opens Task Manager directly — bypassing the Ctrl+Alt+Delete security screen. This shortcut exists because Task Manager is classified as a 'trusted UI' that doesn't need to route through the secure desktop.",
    ],
    "regedit": [
        "The Windows Registry has over 3 million keys on a fresh Windows 11 install. Only a few hundred are touched in daily use. The rest are NT 3.1 legacy.",
        "Regedit has a Favorites feature in the menu bar — you can bookmark any registry path like a browser bookmark. Almost no one uses it.",
        "HKEY stands for 'Handle to a Key' — a literal C programming concept. These handles are opened by the kernel at boot and never closed until shutdown.",
    ],
    "event_viewer": [
        "Windows Event Viewer records every application crash, login, network change, and driver failure — even ones that happened silently in the background while you were working. Most Windows problems leave a trace here.",
        "Event Viewer's XML filtering allows queries more powerful than its UI suggests — you can filter by exact EventID, time ranges, specific process names, and cross-log correlations in ways the GUI never exposes.",
        "The System event log generates over 1,000 entries per hour on a typical Windows machine in normal use — mostly routine status messages. Filtering for errors and warnings reduces that to fewer than 5 meaningful events per day.",
    ],
    "resource_monitor": [
        "Resource Monitor (resmon.exe) shows per-process network traffic in real time — including which domains each process is connecting to. It's the fastest way to catch a background app making unexpected network calls.",
        "Resource Monitor's disk tab shows actual read/write speeds per file — not just per process. This lets you see exactly which file is causing disk thrashing, not just which app.",
        "Resource Monitor was added in Windows Vista specifically because Task Manager couldn't show the data that enterprise IT teams needed for diagnosing slow systems.",
    ],
    "group_policy_editor": [
        "Group Policy Editor (gpedit.msc) has over 4,000 individual policy settings — covering everything from disabling USB ports to forcing screensaver lockout timers. Most IT teams configure fewer than 50 of them.",
        "Group Policy Editor is not available on Windows Home editions — only Windows Pro and above. Microsoft made this a deliberate tiering decision to encourage business users to upgrade.",
        "Group Policy changes take effect on reboot or after running `gpupdate /force` — changes pushed from a domain controller propagate to all machines within the default 90-minute interval, staggered by a random offset to avoid thundering herd.",
    ],
    "process_monitor": [
        "Process Monitor (Sysinternals) records every file system, registry, and network operation on the system in real time. It generates millions of events per minute — the skill is knowing how to filter them down to the one that matters.",
        "Process Monitor was written by Mark Russinovich, who later became Microsoft's CTO of Azure. He originally wrote Sysinternals tools to reverse-engineer Windows internals that Microsoft hadn't publicly documented.",
        "Process Monitor's 'Process Tree' feature shows the parent-child relationship of every running process — revealing hidden spawns, injected processes, and silent background tasks that Task Manager's flat list hides.",
    ],
    "winrar": [
        "WinRAR has been in a 40-day free trial since 1993. Nobody has ever been forced to pay. It is the longest-running free trial in software history — the nag screen is the product's entire marketing strategy.",
        "RAR compression uses a higher compression ratio than ZIP for most file types — the tradeoff is slower compression speed. The algorithm uses a sliding window dictionary 4–8x larger than ZIP's, which is why it does better on large, redundant files.",
        "WinRAR's creator Eugene Roshal is a Russian developer who has maintained the app with a tiny team for 30+ years. The company (RARLAB) reportedly has fewer than 10 employees and has never taken outside investment.",
    ],
    "7zip": [
        "7-Zip's 7z format achieves 30–70% better compression than ZIP on typical files using LZMA2 compression. On software installers and code archives, it can be twice as small as the same content in ZIP.",
        "7-Zip is completely free, open source, and has no trial nag screen, no ads, and no upsell. Its developer Igor Pavlov has maintained it since 1999 with no commercial model of any kind.",
        "7-Zip's command line version (7za.exe) is widely used in CI/CD pipelines for artifact compression — it's faster than PowerShell's built-in Compress-Archive and produces significantly smaller files.",
    ],

    # ──────────────────────────────────────────
    # SECURITY TOOLS
    # ──────────────────────────────────────────

    "wireshark": [
        "Wireshark can decode over 3,000 network protocols — including proprietary industrial protocols, VoIP codecs, Bluetooth profiles, and USB device communications. It speaks more protocols than any other tool on earth.",
        "Wireshark was written by Gerald Combs in 1998 and called 'Ethereal' — he changed the name in 2006 when he switched jobs and his old employer retained the trademark. The community moved with the person, not the name.",
        "Wireshark captures packets at the kernel level using libpcap (Linux) or WinPcap (Windows) — meaning it sees traffic before the firewall and after decryption, making it the ground truth for what's actually on the wire.",
    ],
    "nmap": [
        "Nmap (Network Mapper) has been featured in more films than almost any other security tool — including The Matrix Reloaded, Live Free or Die Hard, and several episodes of Mr. Robot. All uses were verified by security experts as technically accurate.",
        "Nmap's SYN scan ('half-open scan') is so fast it can scan all 65,535 ports on a target in under one second. It works by sending SYN packets but never completing the TCP handshake — the open/closed state is determined from the response type.",
        "Nmap's scripting engine (NSE) lets you write Lua scripts that run against scan results — turning a port scanner into a full vulnerability assessment tool. Over 600 official NSE scripts ship with Nmap.",
    ],
    "metasploit": [
        "Metasploit was created by H.D. Moore in 2003 as a project to make penetration testing reproducible. Before Metasploit, every security tester was reinventing the same exploit code by hand.",
        "Metasploit has over 2,000 built-in exploits covering vulnerabilities from 1990s Windows NT bugs all the way to current CVEs. The database is updated within days of major vulnerability disclosures.",
        "Metasploit's meterpreter payload runs entirely in memory — it never writes to disk. This makes it invisible to antivirus software that only scans files, and it was one of the first examples of fileless malware technique being packaged as a defensive tool.",
    ],
    "bitwarden": [
        "Bitwarden is the only major password manager that is fully open source — both the client apps and the server code. You can self-host your entire password vault on your own server if you don't trust their cloud.",
        "Bitwarden's free tier has no limit on the number of passwords and syncs across unlimited devices — the same fundamental capability that LastPass and 1Password charge for.",
        "Bitwarden encrypts everything client-side before it leaves your device — Bitwarden's servers only ever see encrypted blobs. Even a total server breach would expose nothing readable.",
    ],
    "veracrypt": [
        "VeraCrypt is a fork of TrueCrypt — the encryption tool that mysteriously announced it was 'no longer safe' in 2014 with no explanation. The VeraCrypt team picked up the codebase, audited it, and fixed every vulnerability found.",
        "VeraCrypt supports 'plausible deniability' — you can create a hidden volume inside an encrypted volume, each with a different password. If coerced to reveal your password, you give the outer password, which shows innocent files. The hidden volume is undetectable.",
        "VeraCrypt uses AES-256, Serpent, and Twofish — and lets you chain all three in sequence. Cracking triple-chained encryption with today's hardware would take longer than the age of the universe even with a trillion guesses per second.",
    ],

    # ──────────────────────────────────────────
    # LANGUAGES & RUNTIMES
    # ──────────────────────────────────────────

    "python": [
        "Python's GIL was meant to be a temporary fix added in 1992. It became optional 31 years later in Python 3.13.",
        "Python wasn't named after the snake — Guido was reading Monty Python scripts while writing it and wanted something irreverent. The snake branding came years later.",
        "`import antigravity` opens a specific XKCD comic in your browser. `import this` — the Zen of Python — was written by Tim Peters as a joke in 20 minutes.",
    ],
    "javascript": [
        "JavaScript was written in 10 days by Brendan Eich in 1995 under pressure from Netscape to ship before Java became the web language. The rushed design created many of its famous quirks — `typeof null === 'object'` is a 30-year-old bug that can never be fixed.",
        "JavaScript's event loop is single-threaded — but asynchronous I/O is handled by libuv (in Node) or the browser's C++ runtime, which runs on separate threads. The JS you write is always single-threaded; the engine beneath is not.",
        "JavaScript is the only language that runs natively in every browser — it became the universal runtime not because it was the best language, but because it was the only one Netscape shipped with Navigator 2.0 in 1995.",
    ],
    "typescript": [
        "TypeScript was created by Microsoft engineer Anders Hejlsberg — the same person who designed C# and Turbo Pascal. He's arguably designed more widely-used programming languages than any other living engineer.",
        "TypeScript compiles to JavaScript and adds zero runtime overhead — every type annotation is erased at compile time. The types are entirely a development-time tool.",
        "TypeScript's type inference is Turing complete — meaning you can write TypeScript types that perform arbitrary computation at compile time. Libraries like ts-pattern use this to implement pattern matching purely in the type system.",
    ],
    "rust": [
        "Rust was invented by Mozilla engineer Graydon Hoare in 2006 as a personal project. Mozilla funded it after Hoare showed that it could fix memory safety bugs that cost months of engineering time per Firefox release.",
        "Rust has been Stack Overflow's 'most loved language' for 8 consecutive years — more than any other language in the survey's history. Developers who use it almost never stop.",
        "Rust's ownership model makes it impossible to have data races at compile time — a guarantee no other systems language provides. The compiler's borrow checker enforces it statically, with zero runtime cost.",
    ],
    "golang": [
        "Go was created by Rob Pike, Ken Thompson, and Robert Griesemer at Google — three of the most influential engineers in computing history. Thompson co-created Unix and the C language. They built Go out of frustration with C++.",
        "Go's goroutines are multiplexed onto OS threads by the runtime — you can spawn a million goroutines and they use roughly 2KB of stack each, vs ~1MB for OS threads. This is how Go servers handle millions of concurrent requests.",
        "Go has no inheritance and no generics in its first decade — a deliberate simplicity constraint. This made Go polarizing but also meant any Go developer could read any Go codebase and understand it in minutes.",
    ],
    "node": [
        "Node.js was created by Ryan Dahl in 2009 specifically to fix what he called 'the biggest mistake in web development' — Apache's thread-per-request model that blocked on I/O. His demo at JSConf 2009 is considered one of the most influential tech talks ever.",
        "Node.js uses V8 — Chrome's JavaScript engine — to run JavaScript on the server. This means every V8 performance improvement in Chrome also speeds up Node.js servers automatically.",
        "Ryan Dahl later created Deno (an anagram of Node) to fix all the design mistakes he'd made in Node. Deno uses TypeScript natively, has secure-by-default permissions, and doesn't use npm — yet Node still dominates adoption a decade later.",
    ],
    "java": [
        "Java was designed to run on a 'Java Virtual Machine' so that code compiled once would run on any device — 'Write once, run anywhere'. The JVM became one of the most important pieces of software infrastructure ever built.",
        "Java's garbage collector has been continuously improved for 30 years. Modern GC algorithms like ZGC can pause the JVM for less than 1 millisecond to collect garbage — a feat considered impossible in 2005.",
        "Android's original runtime (Dalvik) ran Java code on mobile — but Google rewrote it as ART (Android Runtime) which compiles Java bytecode to native machine code at install time. Java became the lingua franca of mobile development without Java's designers planning it.",
    ],
    "csharp": [
        "C# was designed by Anders Hejlsberg at Microsoft in 1999 — the same person who built Turbo Pascal and Delphi. Microsoft was originally going to call it 'Cool' (C-like Object Oriented Language) before legal cleared 'C#'.",
        "C#'s LINQ feature — Language Integrated Query — lets you query any data source (databases, XML, lists, APIs) using the same syntax as SQL, embedded directly in C# code. It was a decade ahead of similar features in other languages.",
        "C#'s async/await pattern was invented in C# 5.0 in 2012 — years before JavaScript, Python, or Rust adopted similar syntax. C# essentially defined what modern async programming looks like.",
    ],
    "swift": [
        "Swift was developed secretly inside Apple for 4 years before being announced at WWDC 2014. The audience — mostly Objective-C developers — was visibly shocked. Apple had replaced their core language without leaking a single word.",
        "Swift's optional types (using ? and !) make null pointer exceptions a compile-time error rather than a runtime crash. This single feature eliminates the most common class of iOS app crash.",
        "Swift Playgrounds — Apple's educational iPad app — runs Swift code on-device in real time, making it the most capable coding environment on a tablet. It's used in Apple's K-12 curriculum in over 70 countries.",
    ],
    "kotlin": [
        "Kotlin was created by JetBrains — the company behind IntelliJ IDEA. When Google adopted it as an official Android language in 2017, JetBrains (a private Czech company) suddenly had its language running on 3 billion Android devices.",
        "Kotlin's null safety system eliminates NullPointerExceptions at compile time — a class of crash that Android crash reports show accounts for roughly 20% of all production app failures.",
        "Kotlin Multiplatform lets you share business logic between Android, iOS, web, and desktop — using the same Kotlin code compiled to JVM bytecode, native ARM, or JavaScript depending on the target.",
    ],

    # ──────────────────────────────────────────
    # FRAMEWORKS & LIBRARIES
    # ──────────────────────────────────────────

    "fastapi": [
        "FastAPI was built by one developer as a side project. Within two years it became the third most-starred Python web framework on GitHub.",
        "FastAPI auto-generates the /docs OpenAPI UI entirely from your Python type hints — it reads function signatures at startup, no extra config.",
        "FastAPI benchmarks within 5–10% of raw NodeJS and Go servers on I/O tasks — because ASGI means requests never block the event loop during I/O waits.",
    ],
    "react": [
        "React was created by Jordan Walke at Facebook to solve a specific problem: the chat notification counter in Facebook's sidebar was getting out of sync with the actual messages. The 'one-way data flow' architecture was designed specifically to fix that bug.",
        "React introduced the concept of the Virtual DOM — an in-memory copy of the real DOM that React diffs against before making actual changes. This batching strategy reduced DOM manipulations by ~80% for complex UIs.",
        "React's hooks (useEffect, useState, etc.) were added in version 16.8 in 2019 — 5 years into React's existence. They replaced class components entirely and are considered one of the cleanest API redesigns in popular library history.",
    ],
    "react_native": [
        "React Native was built at a Facebook hackathon in 2013. The team's original goal was to run a React web app inside a WebView — they realized mid-hackathon that they could render native components instead.",
        "React Native's new architecture (JSI) eliminated the bridge that serialized every JavaScript-to-native call as JSON. Direct C++ bindings made React Native animation smooth for the first time.",
        "React Native is used by Facebook, Instagram, Shopify, Discord, Coinbase, and Microsoft Teams — yet Airbnb publicly abandoned it in 2018 and wrote a detailed blog post about why. Both outcomes coexist in production today.",
    ],
    "nextjs": [
        "Next.js was created by Guillermo Rauch (Vercel's CEO) in 2016 as a 6-principle framework for React. The principles — zero-config, file-system routing, SSR out of the box — were so influential that React's own docs now recommend Next.js by default.",
        "Next.js's Incremental Static Regeneration (ISR) lets static pages update in the background without a full rebuild — solving the cache invalidation problem that made static site generators impractical for frequently-changing content.",
        "Next.js is the most deployed React framework in the world by traffic volume. It runs under Walmart, TikTok, Twitch, and The Washington Post — all on different infrastructure but sharing the same framework.",
    ],
    "vue": [
        "Vue was created by Evan You — a former Google engineer — as a personal experiment to extract the parts of AngularJS he liked and discard the rest. He built the first version in a weekend.",
        "Vue's progressive framework design lets you add it to any existing HTML page with a single script tag — no build step, no CLI, no boilerplate. This made it the dominant framework in markets where developers didn't have Node.js tooling experience.",
        "Vue 3's Composition API was inspired by React Hooks but differs in a key way: setup() runs once per component instance, while React hooks run on every render. Vue's model is closer to how developers intuitively think about component lifecycle.",
    ],
    "angular": [
        "AngularJS (1.x) and Angular (2+) are completely different frameworks — Angular was a full rewrite in TypeScript with a completely different architecture. The naming caused enormous confusion and is considered one of the worst ecosystem communication failures in frontend history.",
        "Angular uses TypeScript as its primary language — it was the first major framework to make TypeScript mandatory, which helped normalize TypeScript adoption across the entire JavaScript ecosystem.",
        "Angular's change detection uses Zone.js to monkey-patch every async operation in the browser — setTimeout, Promise, fetch, addEventListener — so Angular knows automatically when to re-render without requiring explicit state management calls.",
    ],
    "django": [
        "Django was built at a newspaper company — the Lawrence Journal-World in Kansas. The team needed a CMS that journalists could use to publish stories quickly. The 'batteries included' philosophy came directly from news publishing's deadline-driven culture.",
        "Django's admin panel — the auto-generated /admin interface — was added as an afterthought for the newspaper's editors. It became Django's most-copied feature, with every major web framework eventually adding a similar capability.",
        "Django's ORM can run the same Python model code against SQLite, PostgreSQL, MySQL, and Oracle — all with identical syntax. Swapping databases requires changing one line in settings.py.",
    ],
    "flask": [
        "Flask was created by Armin Ronacher on April Fools' Day 2010 — as a joke combining two of his other projects. He expected it to be ignored. It became one of the most popular Python web frameworks ever.",
        "Flask calls itself a 'microframework' because it ships with no ORM, no form validation, and no authentication. This blank-slate approach made it the default choice for APIs and data science teams who didn't want database opinions imposed on them.",
        "Flask's request context (the `request` object available in every route) works via Python's thread-local storage — meaning each thread gets its own request object automatically without passing it explicitly. This 'magic' confused beginners but made Flask feel lighter than Django.",
    ],
    "express": [
        "Express.js was released in 2010 by TJ Holowaychuk — a developer who also wrote mocha, chai, passport, koa, component, and dozens of other major Node packages essentially by himself. He's considered the most prolific Node ecosystem contributor ever.",
        "Express's middleware model — where each request passes through a chain of functions that can modify it — became the dominant pattern for HTTP frameworks in nearly every language. FastAPI, Gin, and Laravel all have equivalent middleware chains.",
        "Despite being 14 years old and receiving minimal updates, Express is still used by more Node.js projects than any other framework. Its stability is the feature — teams don't have to learn new APIs.",
    ],
    "tailwind": [
        "Tailwind CSS was controversial when it launched — frontend developers called it 'inline styles with extra steps'. Within 2 years it became the most popular CSS framework on GitHub by star growth rate.",
        "Tailwind uses a JIT (Just-In-Time) compiler that scans your HTML and generates only the CSS classes you actually used — meaning a production Tailwind stylesheet is often under 10KB, smaller than most hand-written CSS files.",
        "Adam Wathan (Tailwind's creator) wrote the framework to solve a problem he documented in a long blog post called 'CSS Utility Classes and Separation of Concerns'. That post convinced thousands of developers before a single line of Tailwind existed.",
    ],

    # ──────────────────────────────────────────
    # PACKAGE MANAGERS & BUILD TOOLS
    # ──────────────────────────────────────────

    "npm": [
        "npm was created by Isaac Schlueter in 2009 and written in a single weekend. It was included with Node.js 0.6 in 2011 — and that bundling decision made it the default package manager for an entire ecosystem overnight.",
        "npm's node_modules folder is famously the heaviest object in the universe — a simple React app can have 200MB+ of dependencies. This is because npm uses non-flat dependency trees that allow different versions of the same package to coexist.",
        "The `left-pad` incident in 2016 — where one developer unpublished an 11-line package and broke thousands of projects including React and Babel — led npm to implement 'unpublish restrictions'. It exposed the fragility of depending on packages with no author accountability.",
    ],
    "pip": [
        "pip (Pip Installs Packages) was created to replace easy_install, which was created to replace distutils, which was Python's original packaging system. The packaging history of Python is a cautionary tale about standards fragmentation.",
        "pip's `--break-system-packages` flag exists because modern Linux distros use Python internally for system tools — and pip installing packages globally could overwrite system dependencies and break the OS. The flag is your acknowledgment that you understand the risk.",
        "pip resolves dependencies using a backtracking algorithm that can take minutes on large dependency trees. `pip-compile` from pip-tools pre-resolves the entire tree and locks all versions to a file — making installs deterministic and fast.",
    ],
    "cargo": [
        "Cargo — Rust's package manager — is considered the gold standard of package managers. It handles compilation, testing, benchmarking, documentation, and publishing in one tool. Other language communities point to Cargo when asking 'why can't our tooling be this good?'",
        "Cargo's crates.io registry has a unique policy: once a version is published, it can never be deleted or modified. This immutability guarantee means a Rust project from 2016 can be reproduced exactly forever.",
        "Cargo's build system is parallel by default — it compiles independent crates simultaneously using all available CPU cores. Large Rust projects compile faster than equivalent C++ projects partly because of this automatic parallelism.",
    ],
    "webpack": [
        "Webpack was created by Tobias Koppers as a student project in 2012. He submitted it to a job application as a code sample, didn't get the job, and kept developing it in his spare time. It became the bundler for over 90% of React projects.",
        "Webpack's Hot Module Replacement (HMR) updates code in a running browser without a full page refresh — it surgically replaces only the changed module. This feature, invented by Webpack, is what made modern frontend development feel interactive.",
        "Webpack's configuration file is famously complex — it became a meme in frontend development. This drove the creation of Vite, Parcel, and esbuild, all of which used 'zero config' as their primary selling point.",
    ],
    "vite": [
        "Vite uses native ES modules in the browser during development — it serves your actual source files directly without bundling them. This is why Vite's dev server starts in under 300ms regardless of project size.",
        "Vite was created by Evan You (Vue's creator) after Vue's own build tooling became too slow on large projects. It was initially Vue-specific but became framework-agnostic in v2, and is now the default bundler for most new React, Svelte, and Solid projects.",
        "Vite's production build uses Rollup — a different bundler entirely — not Vite's own dev server architecture. The dev/prod split was intentional: dev prioritizes speed, prod prioritizes optimal output.",
    ],

    # ──────────────────────────────────────────
    # OPERATING SYSTEMS
    # ──────────────────────────────────────────

    "windows": [
        "Windows 11's taskbar is the first redesign of the taskbar in 28 years. Internally, the old taskbar code (from Windows 95) was so fragile it was nicknamed 'the stack of cards' by the Windows team.",
        "Windows uses the NT kernel for every modern version — the same kernel core built in 1993 by a team from DEC's VMS project. It's never been rewritten, only extended.",
        "The Ctrl+Alt+Delete shortcut was added as a safeguard by IBM engineer David Bradley — he assumed it was too hard to accidentally press all three keys at once. Bill Gates later called it 'a mistake'.",
    ],
    "macos": [
        "macOS's kernel (XNU) is a hybrid of two completely different kernel architectures — the Mach microkernel from Carnegie Mellon and BSD Unix from Berkeley. Apple fused them in 1989 for NeXTSTEP.",
        "macOS's Spotlight search indexes your entire drive in the background using a technology called 'CoreData' — the same framework apps use for local database storage. Spotlight is literally running SQL queries against an on-disk index.",
        "macOS's Rosetta 2 — the translation layer for running x86 apps on Apple Silicon — translates x86 binaries to ARM machine code at install time, not at runtime. The translated binary is cached, so it runs at near-native speed with zero per-launch cost.",
    ],
    "ubuntu": [
        "Ubuntu is named after the Nguni Bantu philosophy: 'I am because we are.' Canonical's founder Mark Shuttleworth chose it to represent the spirit of open-source collaboration.",
        "Ubuntu's snap packages are self-contained app bundles that include all dependencies — meaning a snap for Chromium is identical on Ubuntu 18.04 and Ubuntu 24.04. The tradeoff is that snaps are often criticized for slower launch times.",
        "Ubuntu's Long Term Support (LTS) releases are supported for 5 years (10 with paid ESM) — meaning production servers running Ubuntu 20.04 will receive security patches until 2030 without any OS upgrade.",
    ],
    "linux": [
        "Linux was started by Linus Torvalds at age 21 as a 'hobby project' announced on a Usenet post in 1991. He specifically said it 'won't be big and professional like GNU'. Today it runs 100% of the top 500 supercomputers and ~75% of all servers.",
        "The Linux kernel has over 30 million lines of code and receives contributions from engineers at Google, Microsoft, Intel, Red Hat, and Samsung simultaneously. It is the largest collaborative software project in human history.",
        "Linux's scheduler — the part of the kernel that decides which process runs next — was rewritten in 2023 (EEVDF scheduler) to improve performance on desktop workloads. The kernel has been continuously optimized for 33 years without a single architectural rewrite.",
    ],
    "android": [
        "Android was originally designed for digital cameras — not phones. The founding team pivoted to smartphones in 2004 after realizing the camera market was too small. Google acquired Android Inc. in 2005 for $50 million.",
        "Android uses the Linux kernel but a completely custom runtime — there is no glibc, no standard Unix filesystem layout, and no traditional init system. It's Linux underneath but unrecognizable at every layer above.",
        "The first Android phone (HTC Dream / T-Mobile G1) shipped in 2008 with a physical keyboard and a trackball. It had no onscreen keyboard at launch — the team didn't think touchscreen typing would be accurate enough.",
    ],
    "ios": [
        "iOS was a radical internal bet — Steve Jobs had to fight his own board to put a desktop-class OS (OS X) on a phone. The dominant wisdom in 2007 was that smartphones needed stripped-down, low-power OSes.",
        "iOS's UIKit framework was written from scratch for touch input — it shares almost no code with macOS's AppKit despite running the same XNU kernel underneath. The two UI frameworks have different coordinate systems, different event models, and different layout engines.",
        "iOS's Safari browser is the only browser permitted on the iPhone in the EU — until 2024, when Apple was forced to allow competing browser engines under the Digital Markets Act. For 16 years, every 'other browser' on iPhone was secretly Safari with a different UI.",
    ],

    # ──────────────────────────────────────────
    # FINANCE & TRADING
    # ──────────────────────────────────────────

    "tradingview": [
        "TradingView's chart rendering engine processes millions of OHLC candles in real time using WebGL — it renders a 20-year daily chart of stock data at 60fps in a browser. No other charting tool matches its rendering performance.",
        "TradingView's Pine Script language was designed to be beginner-friendly but has hidden depth — most strategies have a built-in look-ahead bias trap (using future data in the past) that beginners fall into and professionals specifically code around.",
        "TradingView has the largest social trading community on the internet — over 50 million published ideas. The 'editors picks' and 'top authors' sections are algorithmically selected, not paid placements, which is why some of the best technical analysis content there is free.",
    ],
    "zerodha": [
        "Zerodha became India's largest stockbroker without a single rupee of external funding — it was built on a zero-commission model before Robinhood popularized that concept in the US.",
        "Zerodha's Kite platform was built in-house with a small engineering team using React on the frontend. It processes over 15% of India's NSE trading volume on peak days — more than any other broker.",
        "Zerodha's founder Nithin Kamath was a day trader before he was a CEO. He built the first version of their backend trading infrastructure by himself after becoming frustrated with existing broker software.",
    ],
    "robinhood": [
        "Robinhood's zero-commission trading model is funded primarily by 'payment for order flow' — it sells your orders to market makers who execute them. This practice is legal in the US but banned in the UK and Canada.",
        "Robinhood's gamification elements (confetti, streaks, achievement badges) were heavily criticized after research linked them to increased risky trading behavior among young users. Many features were removed after regulatory scrutiny.",
        "Robinhood froze GameStop trading during the 2021 short squeeze not due to market manipulation (as widely accused) but because DTCC (the clearinghouse) margin-called them for $3 billion in collateral that they didn't have on hand.",
    ],
    "bloomberg": [
        "Bloomberg Terminal costs roughly $24,000 per user per year — and has over 325,000 subscribers. Its revenue funds the entire Bloomberg company, including Bloomberg News. No other single software product generates as much revenue per seat.",
        "Bloomberg Terminal's keyboard has custom function keys (red, yellow, green, blue) that don't exist on standard keyboards. Bloomberg has sold compatible keyboards since the 1980s. The color-coded key layout is so iconic that traders recognize it instantly.",
        "Bloomberg's data infrastructure processes over 120 billion pieces of financial data per day. The system has been running continuously since 1981 and has been upgraded without ever being taken fully offline.",
    ],

    # ──────────────────────────────────────────
    # SOCIAL MEDIA
    # ──────────────────────────────────────────

    "twitter_x": [
        "Twitter was conceived in a brainstorming session where Jack Dorsey sketched a service where you could share your status in 140 characters — the limit was chosen to fit within a standard SMS message (160 chars minus a username).",
        "Twitter's 'Fail Whale' (the server overload error page) became so iconic that it spawned merchandise, fan art, and academic papers about system design failure. The artist who drew it, Yiying Lu, had sold it as a stock image for $6.",
        "Twitter's real-time search index was built by a team of 5 engineers in 2009 and could index a tweet in under 15 seconds. Google's web crawlers at the time took days to index new pages — Twitter's architecture was genuinely a decade ahead.",
    ],
    "instagram": [
        "Instagram was built in 8 weeks by two people — Kevin Systrom and Mike Krieger. The first version was built on a shared server that cost $25/month and was held together with duct tape and cron jobs.",
        "Instagram's original name was Burbn — a check-in app inspired by Foursquare. The photo-sharing feature was added as a side feature. When analytics showed photos were 95% of all usage, they rebuilt the entire app around photos and renamed it.",
        "Facebook acquired Instagram in 2012 for $1 billion — when Instagram had 13 employees and zero revenue. Mark Zuckerberg personally called Kevin Systrom on a Sunday and closed the deal in 48 hours, reportedly over two-day negotiations.",
    ],
    "tiktok": [
        "TikTok's recommendation algorithm (codenamed 'Monolith') doesn't rely primarily on who you follow — it observes behavioral micro-signals: how long you pause on a video, whether you rewatch, whether you scroll away immediately. The follow graph is almost irrelevant.",
        "TikTok was the first non-game app to reach $10 billion in consumer spending (in-app purchases) globally — surpassing YouTube, Netflix, and Spotify. Most of that revenue comes from virtual 'gifts' sent to creators during live streams.",
        "TikTok and Douyin (its Chinese counterpart) look identical but run on completely separate codebases, separate data centers, and separate algorithms. They're the same product split into two parallel universes for regulatory compliance.",
    ],
    "linkedin": [
        "LinkedIn was founded in Reid Hoffman's living room in 2002. The site launched in 2003 and had 4,500 members after the first month — mostly the founding team's personal networks. It reached 1 million users in the first year.",
        "LinkedIn's 'People You May Know' feature was the first viral social graph recommendation engine at scale. It used mutual connection patterns to suggest connections — a technique that Facebook and Twitter both copied within 18 months.",
        "Microsoft acquired LinkedIn for $26.2 billion in 2016 — the largest acquisition in Microsoft's history at the time. LinkedIn still operates largely independently and has kept its own data infrastructure separate from Microsoft's.",
    ],
    "reddit": [
        "Reddit was built in 3 weeks by Steve Huffman and Alexis Ohanian as their Y Combinator project in 2005. Their original idea was rejected by YC — Paul Graham suggested they build Reddit instead after a conversation over lunch.",
        "Reddit's voting system uses fuzzy scores — the displayed vote count is not the exact count. Reddit adds random offsets to prevent targeting of specific posts for vote manipulation. The actual count is hidden from the public.",
        "Reddit's alien mascot (Snoo) was designed by Steve Huffman in Microsoft Paint in about 20 minutes. The name came from a line in a short story — 'What's new?' asked as a slang word. The full phrase 'what's new' → Reddit's front page concept.",
    ],

    # ──────────────────────────────────────────
    # UTILITIES & MISC WINDOWS TOOLS
    # ──────────────────────────────────────────

    "everything_search": [
        "Everything (voidtools) indexes every file on your Windows NTFS drive in under a second — it reads the NTFS Master File Table directly, not the filesystem. That MFT index is pre-built by Windows and contains every filename and path.",
        "Everything uses ~10MB of RAM to index a drive with 1 million files. Windows Search uses 300MB+ for the same task. The size difference comes from Everything only indexing names and paths — no content indexing at all.",
        "Everything's search box supports regex, Boolean operators, and size/date filters. Searching `*.pdf size:>10mb modified:today` is near-instant on a million-file drive — most users never discover the power syntax.",
    ],
    "autohotkey": [
        "AutoHotkey was created by Chris Mallett in 2003 to make a game bot — specifically to automate mouse clicks in games. He generalized it into a full scripting language and released it as free software.",
        "AutoHotkey can remap any key to any action, send keystrokes to any window, read clipboard contents, parse text, make HTTP requests, and create GUI dialogs — all in a single .ahk file with no compilation step.",
        "AutoHotkey scripts can hook into Windows messages at the kernel level — meaning they can intercept keystrokes before any application sees them, including inside VMs and remote desktop sessions.",
    ],
    "powertoys": [
        "PowerToys was originally a Windows 95 tool kit released by Microsoft in 1997 — it gave developers extra desktop features that didn't ship in the core OS. Microsoft open-sourced and revived the project in 2019 for Windows 10/11.",
        "PowerToys Run is a launcher built specifically because the Start Menu search was too slow — it uses separate fast indexes for apps, files, and calculator results and opens with Alt+Space in under 50ms.",
        "PowerToys' FancyZones feature lets you define custom window snap zones — not just left/right halves but arbitrary grids, L-shapes, or any layout you draw. It's a free alternative to DisplayFusion and Mosaico.",
    ],
    "sharex": [
        "ShareX can capture a screenshot, annotate it, OCR the text, compress the image, upload it to a custom host, and copy the URL to clipboard — all in a single automated workflow triggered by one hotkey.",
        "ShareX's scrolling screenshot feature captures a full webpage or document by automatically scrolling and stitching — even if the content is taller than your screen. It works inside browsers, file explorers, and chat apps.",
        "ShareX is completely free, open source, and has no ads. It replaces Snagit (a $60/year tool) for almost every use case — yet fewer than 5% of Windows users have heard of it.",
    ],
    "obs": [
        "OBS (Open Broadcaster Software) was written by one developer, Hugh Bailey (Jim), in 2012 and posted to a forum. It had no company, no funding, and no roadmap. It became the dominant streaming software used by Twitch's top streamers.",
        "OBS Studio's plugin system lets you add custom video sources, filters, and outputs. The most popular plugin (obs-virtualcam) creates a virtual webcam from OBS scenes — letting you use OBS as a camera input for Zoom, Teams, or any video call.",
        "OBS uses a scene-based compositing system where each scene is a layer stack of sources — identical to how professional broadcast software works. Many professional broadcast studios use OBS because it handles the same workflows at zero licensing cost.",
    ],
    "vlc": [
        "VLC was written in 1996 by students at the École Centrale Paris as a graduation project. It has been downloaded over 3.5 billion times — the most downloaded open-source desktop app ever.",
        "VLC can open almost any video file without codecs because it bundles every decoder internally — MPEG-4, H.264, H.265, AV1, VP9 — all in one 40MB app.",
        "VLC's network stream feature plays video directly from URLs, RTSP streams, and FTP servers. Most users don't know it's a full media streaming client, not just a local file player.",
    ],
    "irfanview": [
        "IrfanView was created by Irfan Škiljan in 1996 as a university student project. He named it after himself. It handles 100+ image formats, batch converts entire folders, and runs on a 10-year-old PC — all in a 3MB download.",
        "IrfanView can batch-process thousands of images — resize, watermark, rename, convert format, adjust color levels — using a single configuration dialog. No scripting required.",
        "IrfanView is free for personal use and costs $10 for commercial use, forever. It has never shown an ad, never required a subscription, and has never had a significant security vulnerability in 28 years.",
    ],
    "putty": [
        "PuTTY was created by Simon Tatham in 1999 as a free alternative to paid SSH clients on Windows. It became the standard SSH client for Windows users worldwide and has been downloaded billions of times.",
        "PuTTY stores all session configurations in the Windows registry rather than a file — which is why moving PuTTY to a new machine requires an `Export Registry Key` step that surprises every developer who tries it for the first time.",
        "PuTTY's keyboard handling uses a terminal emulation layer that translates Windows keypresses into terminal escape sequences — supporting VT100, xterm, and Linux console modes. Getting the right mode matters when arrow keys don't behave in a remote server.",
    ],

    # ──────────────────────────────────────────
    # GEOPOLITICAL / COUNTRY CONTEXT
    # ──────────────────────────────────────────

    "iran": [
        "Iran's Stuxnet worm checked GPS coordinates of infected machines — it only activated its payload at one specific uranium enrichment facility in Natanz.",
        "Over 30% of Iran's internet users regularly use VPNs — third-highest per capita in the world. The government runs a parallel offline national internet as a fallback.",
        "Iran's IRGC Cyber Command accidentally open-sourced parts of their network analysis code, which ended up in legitimate security researcher toolkits.",
    ],
    "india": [
        "India's UPI (Unified Payments Interface) processes over 10 billion transactions per month — more monthly digital payments than the US, UK, and Europe combined. It was built by NPCI as a public infrastructure layer in 2016.",
        "Bengaluru is home to R&D centers for over 400 Fortune 500 companies — more than any city outside the US. It has the highest density of engineering talent per square kilometer of any city in Asia.",
        "India's Aadhaar biometric ID system is the world's largest biometric database — covering 1.4 billion people. Every Aadhaar authentication call resolves in under 300ms using a distributed architecture built on open-source tools.",
    ],
    "china": [
        "China's Great Firewall doesn't just block websites — it actively throttles encrypted traffic that matches VPN signatures, injects false DNS responses, and resets TCP connections using deep packet inspection at the ISP level.",
        "WeChat is so deeply integrated into daily life in China that people use it to pay for street food, book hospitals, submit government forms, and sign business contracts. It has over 1 billion daily active users all within one app.",
        "Huawei's HarmonyOS was built in 9 months as an emergency response to US trade restrictions blocking Android licensing. The team of 5,000 engineers simultaneously supported existing devices and built a new OS — it now runs on over 700 million devices.",
    ],
    "russia": [
        "Russia's RuNet — its domestic internet infrastructure — was designed to be able to disconnect from the global internet entirely in a 'sovereign internet drill'. In 2019, they successfully isolated national traffic for a test period.",
        "Kaspersky Lab — founded in Moscow — is widely considered to have some of the best malware analysts in the world. Their research teams have publicly exposed NSA and CIA cyber operations (Equation Group, Regin) that no other firm had detected.",
        "Telegram, the most popular messaging app in Russia, was built by Russians specifically to avoid Russian government surveillance. The founder Pavel Durov was forced to flee Russia in 2014 after refusing to hand over user data.",
    ],
    "usa": [
        "The US government is the single largest investor in early-stage technology in the world — DARPA, CIA's In-Q-Tel, and SBIR grants collectively fund more early-stage tech than all Silicon Valley VCs combined.",
        "Silicon Valley's venture capital model was invented in Boston, not California — American Research and Development Corporation (ARD) made the first institutional VC investment in 1946. The model migrated west with the semiconductor industry in the 1960s.",
        "The United States has more operational nuclear reactors than any country on earth (93 as of 2024) and is also the world's largest oil producer — making it simultaneously the leader in legacy and emerging energy infrastructure.",
    ],

    # ──────────────────────────────────────────
    # MISC CATEGORIES
    # ──────────────────────────────────────────

    "bitcoin": [
        "Bitcoin's creator Satoshi Nakamoto has never been identified and owns approximately 1 million BTC — worth tens of billions of dollars — that has never moved since 2010. This wallet is treated as a litmus test: if it ever moves, markets react.",
        "Bitcoin's proof-of-work mining was explicitly modeled on the physical cost of gold mining — Satoshi chose SHA-256 hashing because it's computationally expensive but trivially verifiable, mimicking how gold is hard to mine but easy to weigh.",
        "The first real-world Bitcoin transaction was for two Papa John's pizzas purchased for 10,000 BTC in May 2010. That transaction is commemorated annually on 'Bitcoin Pizza Day' — those 10,000 BTC would be worth hundreds of millions of dollars today.",
    ],
    "ethereum": [
        "Ethereum was conceived by Vitalik Buterin at age 17 after reading Bitcoin's whitepaper and thinking: 'What if the blockchain could run arbitrary programs, not just financial transactions?'. He wrote the Ethereum whitepaper at 19.",
        "Ethereum's 'Merge' in September 2022 switched the network from Proof of Work to Proof of Stake — reducing its energy consumption by 99.95% overnight. It was considered one of the most complex live system migrations in engineering history.",
        "Smart contracts on Ethereum run in the EVM (Ethereum Virtual Machine) — a deterministic sandbox where every node in the network runs every contract execution and agrees on the result. Disagreement on the result is architecturally impossible.",
    ],
    "excel": [
        "Excel was originally a Mac-only application — it launched on the Macintosh in 1985. The Windows version launched 2 years later and eventually overtook the Mac version entirely.",
        "Excel's grid limit is 1,048,576 rows × 16,384 columns — not a round number. It's 2^20 rows and 2^14 columns — exactly the maximum values representable in 20-bit and 14-bit integers respectively.",
        "Excel has been the source of significant financial errors in the real world — the most famous being the JPMorgan 'London Whale' trade where a copy-paste error in an Excel model contributed to a $6.2 billion trading loss.",
    ],
    "word": [
        "Microsoft Word was originally developed for Xenix (Microsoft's Unix variant) and Multibus systems in 1983 — it was a Unix word processor before it was a Windows app.",
        "Word's 'Track Changes' feature was added in Word 6.0 in 1993 — and it stores every single edit, the author, and the timestamp in the document's XML. Leaked documents often reveal editing history and author metadata that wasn't intended to be public.",
        "Word's .docx format is actually a ZIP file — rename any .docx to .zip and extract it. You'll find XML files for the content, styles, and relationships, plus embedded media in folders.",
    ],
    "powerpoint": [
        "PowerPoint was created by a company called Forethought Inc. and was originally called 'Presenter'. Microsoft acquired Forethought for $14 million in 1987 — one of its best acquisitions ever given PowerPoint's dominance of presentations globally.",
        "PowerPoint files (.pptx) are ZIP archives containing XML — the same as Word's .docx. Every slide is a separate XML file. You can unzip any .pptx and hand-edit the XML directly.",
        "Studies at NASA linked PowerPoint presentations to decision-making failures in the Columbia shuttle disaster — the detailed engineering data about foam strike damage was buried in nested bullet points rather than presented as the critical finding it was.",
    ],
    "zoom_meetings": [
        "Zoom's founder Eric Yuan left Cisco/WebEx after being told his improvement proposals 'weren't needed'. He took 40 engineers with him and built Zoom more reliably than WebEx in two years.",
        "Zoom's multi-datacenter routing selects optimal paths in real-time — calls degrade more gracefully than competitors when network paths fail because the routing is globally distributed.",
        "During COVID lockdowns, Zoom went from 10 million to 300 million daily participants in 4 months — the fastest adoption of any enterprise software ever recorded.",
    ],
    "7zip": [
        "7-Zip's 7z format achieves 30–70% better compression than ZIP using LZMA2 — on software installers it can be twice as small as the same content in ZIP.",
        "7-Zip is completely free, open source, has no ads, and has never taken outside investment. Developer Igor Pavlov has maintained it since 1999.",
        "7-Zip's command-line tool (7za.exe) is used in CI/CD pipelines globally — it's faster than PowerShell's built-in archiver and produces significantly smaller files.",
    ],
    "winrar": [
        "WinRAR has been in a 40-day free trial since 1993. Nobody has ever been forced to pay — it's the longest-running free trial in software history.",
        "RAR compression outperforms ZIP by using a sliding window dictionary 4–8x larger than ZIP's — which is why it does better on large, redundant data like software installers.",
        "WinRAR's creator Eugene Roshal is a Russian developer who has maintained it with fewer than 10 employees for 30+ years. RARLAB has never taken outside investment.",
    ],
    "anydesk": [
        "AnyDesk uses a proprietary codec called DeskRT that compresses screen updates by focusing on the regions that change most — meaning it uses 90% less bandwidth than VNC or older remote desktop protocols.",
        "AnyDesk can work through NAT without port forwarding using a relay server network — but if both machines are on networks that support direct UDP, it automatically switches to direct peer-to-peer for better performance.",
        "AnyDesk was founded by former TeamViewer employees who believed the product had become too expensive for individual use. They built AnyDesk to be free for personal use with the same enterprise-grade performance.",
    ],
    "teamviewer": [
        "TeamViewer uses UDP hole punching to establish direct peer-to-peer connections through firewalls — a technique originally developed for VoIP that TeamViewer adapted for remote desktop in 2005.",
        "TeamViewer's free tier detects 'commercial use' patterns (connection duration, frequency) and blocks the session — the detection algorithm is intentionally opaque, which is why some personal users get blocked despite no commercial activity.",
        "TeamViewer was acquired by Permira (a private equity firm) in 2014 and taken public in 2019. At IPO, it was Germany's largest tech IPO ever — a remote desktop company briefly worth more than Deutsche Bank.",
    ],
    "virtualbox": [
        "VirtualBox was originally developed by a German company (innotek GmbH) and acquired by Sun Microsystems — which was itself acquired by Oracle. VirtualBox is one of the few Oracle products that remained free and open source post-acquisition.",
        "VirtualBox uses a Type 2 hypervisor — meaning it runs inside a host OS rather than directly on hardware. This makes setup easier but means there's performance overhead from the host OS kernel beneath it.",
        "VirtualBox's 'Seamless Mode' removes the virtual machine window border and integrates VM application windows directly into your host desktop — making Windows apps appear to run on macOS and vice versa.",
    ],
    "vmware": [
        "VMware invented x86 virtualization for consumer hardware in 1999 — before that, virtual machines required special hardware (like IBM mainframes). The company's original x86 virtualization patent was considered one of the most valuable in tech.",
        "VMware's ESXi (bare-metal hypervisor) is a Type 1 hypervisor — it runs directly on hardware with no host OS beneath it. This gives guest VMs near-native performance and is used in almost every enterprise data center globally.",
        "Broadcom acquired VMware for $61 billion in 2023 — one of the largest tech acquisitions ever. Broadcom immediately ended perpetual licenses and moved to subscription-only pricing, causing significant enterprise customer backlash.",
    ],
    "hyper_v": [
        "Hyper-V uses a microkernel architecture where Windows itself runs as a 'parent partition' guest VM — meaning Windows doesn't have special access to hardware any different from a Hyper-V virtual machine. All hardware access goes through the hypervisor.",
        "Hyper-V is free on Windows Server and Windows 10/11 Pro and Enterprise. It's the same hypervisor technology that runs Azure — meaning your local dev VM is running on the same hypervisor that powers Microsoft's global cloud.",
        "WSL2 (Windows Subsystem for Linux) runs on Hyper-V internally — each Linux distro you install in WSL2 is a lightweight Hyper-V VM that boots in under 1 second. You're running a production-grade hypervisor every time you open a Linux terminal on Windows.",
    ],

    # ──────────────────────────────────────────
    # GENERIC FALLBACK
    # ──────────────────────────────────────────

    "generic": [
        "The fastest way to move data on a computer is not Wi-Fi or Ethernet — it's shared memory between processes. Whiztant uses this for inter-process text injection.",
        "Clipboard history was hidden in Windows 10 under Win+V for 2 years before anyone found it. It stores the last 25 clipboard items and syncs across devices.",
        "The average developer wastes 13 minutes per day on app-switching friction. Keyboard-first workflows reclaim about 8 of those minutes.",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# DETECTION MAP — extend this in detect_context()
# ─────────────────────────────────────────────────────────────────────────────

DETECTION_KEYWORDS = {
    "google":           ["google", "gmail", "drive", "docs", "sheets", "meet", "chrome", "bard"],
    "chrome":           ["chrome", "chromium"],
    "firefox":          ["firefox", "mozilla"],
    "edge":             ["edge", "msedge"],
    "brave":            ["brave"],
    "safari":           ["safari"],
    "opera":            ["opera"],
    "vivaldi":          ["vivaldi"],
    "tor_browser":      ["tor", "onion"],
    "windsurf":         ["windsurf", "cascade", "codeium"],
    "cursor":           ["cursor ide", "cursor ai"],
    "vscode":           ["vscode", "vs code", "code.exe", "visual studio code"],
    "vim":              ["vim", " vi "],
    "neovim":           ["neovim", "nvim"],
    "intellij":         ["intellij", "idea"],
    "pycharm":          ["pycharm"],
    "sublime_text":     ["sublime"],
    "notepad_plus":     ["notepad++"],
    "android_studio":   ["android studio"],
    "xcode":            ["xcode"],
    "emacs":            ["emacs"],
    "cmd":              ["cmd", "command prompt", ".bat", "batch"],
    "powershell":       ["powershell", "pwsh", ".ps1"],
    "windows_terminal": ["windows terminal", "wt.exe"],
    "wsl":              ["wsl", "ubuntu", "debian", "linux subsystem"],
    "bash":             ["bash", ".sh", "shell script"],
    "zsh":              ["zsh", "oh my zsh"],
    "fish":             ["fish shell"],
    "iterm2":           ["iterm", "iterm2"],
    "ollama":           ["ollama", "gguf", "llama", "mistral", "qwen", "phi-"],
    "lm_studio":        ["lm studio", "lmstudio"],
    "chatgpt":          ["chatgpt", "openai", "gpt-4", "gpt4"],
    "claude_ai":        ["claude", "anthropic"],
    "gemini":           ["gemini", "bard", "google ai"],
    "copilot":          ["copilot", "github copilot"],
    "midjourney":       ["midjourney", "mj prompt"],
    "stable_diffusion": ["stable diffusion", "comfyui", "automatic1111", "sdxl"],
    "hugging_face":     ["huggingface", "hugging face", "transformers", "hf "],
    "langchain":        ["langchain", "lcel"],
    "git":              ["git ", "commit", "branch", "merge", "rebase", "clone"],
    "github":           ["github", "gh "],
    "gitlab":           ["gitlab"],
    "bitbucket":        ["bitbucket"],
    "slack":            ["slack"],
    "discord":          ["discord"],
    "telegram":         ["telegram"],
    "whatsapp":         ["whatsapp"],
    "teams":            ["teams", "microsoft teams"],
    "zoom":             ["zoom"],
    "signal":           ["signal app"],
    "gmail":            ["gmail"],
    "outlook":          ["outlook"],
    "notion":           ["notion"],
    "obsidian":         ["obsidian"],
    "evernote":         ["evernote"],
    "onenote":          ["onenote", "one note"],
    "todoist":          ["todoist"],
    "trello":           ["trello"],
    "jira":             ["jira", "jql"],
    "confluence":       ["confluence"],
    "docker":           ["docker", "dockerfile", "container", "docker-compose"],
    "kubernetes":       ["kubernetes", "kubectl", "k8s", "helm"],
    "aws":              ["aws", "amazon web services", "s3", "ec2", "lambda"],
    "gcp":              ["gcp", "google cloud", "bigquery", "gke"],
    "azure":            ["azure", "entra", "active directory", "arm template"],
    "netlify":          ["netlify"],
    "vercel":           ["vercel"],
    "supabase":         ["supabase"],
    "firebase":         ["firebase", "firestore", "realtime database"],
    "terraform":        ["terraform", "hcl", ".tf "],
    "nginx":            ["nginx"],
    "postgresql":       ["postgres", "postgresql", "psql"],
    "mysql":            ["mysql", "mariadb"],
    "mongodb":          ["mongodb", "mongo", "atlas"],
    "redis":            ["redis"],
    "sqlite":           ["sqlite"],
    "figma":            ["figma"],
    "sketch":           ["sketch app"],
    "adobe_xd":         ["adobe xd", "xd "],
    "photoshop":        ["photoshop", "psd"],
    "illustrator":      ["illustrator", "ai file", ".ai "],
    "davinci_resolve":  ["davinci", "resolve", "davinci resolve"],
    "after_effects":    ["after effects", "lottie", "ae "],
    "canva":            ["canva"],
    "spotify":          ["spotify"],
    "youtube":          ["youtube"],
    "netflix":          ["netflix"],
    "twitch":           ["twitch"],
    "vlc":              ["vlc"],
    "task_manager":     ["task manager", "taskmgr"],
    "regedit":          ["regedit", "registry", "hkey"],
    "event_viewer":     ["event viewer", "eventvwr"],
    "resource_monitor": ["resource monitor", "resmon"],
    "group_policy_editor": ["group policy", "gpedit"],
    "process_monitor":  ["process monitor", "procmon", "sysinternals"],
    "winrar":           ["winrar", ".rar"],
    "7zip":             ["7zip", "7-zip", ".7z"],
    "fastapi":          ["fastapi", "uvicorn", "pydantic"],
    "react":            ["react", "jsx", "usestate", "useeffect"],
    "react_native":     ["react native", "expo", "metro bundler"],
    "nextjs":           ["next.js", "nextjs", "next/"],
    "vue":              ["vue", "vuex", "nuxt"],
    "angular":          ["angular", "ng "],
    "django":           ["django"],
    "flask":            ["flask", "werkzeug"],
    "express":          ["express", "expressjs"],
    "tailwind":         ["tailwind", "tw-"],
    "npm":              ["npm", "package.json", "node_modules"],
    "pip":              ["pip ", "requirements.txt"],
    "cargo":            ["cargo", "crates.io", "rust"],
    "webpack":          ["webpack"],
    "vite":             ["vite", "vite.config"],
    "python":           ["python", "py ", ".py"],
    "javascript":       ["javascript", "js ", ".js"],
    "typescript":       ["typescript", ".ts "],
    "rust":             [" rust ", ".rs "],
    "golang":           ["golang", "go run", ".go "],
    "node":             ["node", "nodejs", "node.js"],
    "java":             [" java ", ".java", "jvm", "maven", "gradle"],
    "csharp":           ["c#", "csharp", ".cs "],
    "swift":            [" swift", ".swift"],
    "kotlin":           ["kotlin", ".kt "],
    "iran":             ["iran", "iranian", "tehran", "vpn iran"],
    "india":            ["india", "indian", "bengaluru", "bangalore", "upi", "nse", "bse"],
    "china":            ["china", "chinese", "wechat", "alibaba", "baidu"],
    "russia":           ["russia", "russian", "vk ", "runet"],
    "usa":              ["usa", "america", "silicon valley", "darpa"],
    "bitcoin":          ["bitcoin", "btc", "satoshi"],
    "ethereum":         ["ethereum", "eth", "solidity", "smart contract", "web3"],
    "excel":            ["excel", ".xlsx", "spreadsheet"],
    "word":             ["word doc", ".docx", "microsoft word"],
    "powerpoint":       ["powerpoint", ".pptx", "presentation"],
    "tradingview":      ["tradingview", "pine script"],
    "zerodha":          ["zerodha", "kite", "zerodha kite"],
    "robinhood":        ["robinhood"],
    "bloomberg":        ["bloomberg terminal"],
    "twitter_x":        ["twitter", " x.com", "tweet"],
    "instagram":        ["instagram"],
    "tiktok":           ["tiktok", "douyin"],
    "linkedin":         ["linkedin"],
    "reddit":           ["reddit", "subreddit"],
    "wispr_flow":       ["wispr", "wispr flow"],
    "everything_search":["everything", "voidtools"],
    "autohotkey":       ["autohotkey", "ahk", ".ahk"],
    "powertoys":        ["powertoys", "fancy zones", "powerrename"],
    "sharex":           ["sharex"],
    "obs":              ["obs", "obs studio"],
    "irfanview":        ["irfanview", "irfan"],
    "putty":            ["putty", "ssh client"],
    "anydesk":          ["anydesk"],
    "teamviewer":       ["teamviewer"],
    "virtualbox":       ["virtualbox", "vbox"],
    "vmware":           ["vmware", "esxi"],
    "hyper_v":          ["hyper-v", "hyperv"],
    "wireshark":        ["wireshark", "pcap", "packet capture"],
    "nmap":             ["nmap", "port scan"],
    "metasploit":       ["metasploit", "msfconsole"],
    "bitwarden":        ["bitwarden"],
    "veracrypt":        ["veracrypt", "truecrypt"],
    "windows":          ["windows 11", "windows 10", "win32", "winapi"],
    "macos":            ["macos", "mac os", "osx", "apple silicon", "m1", "m2"],
    "ubuntu":           ["ubuntu", "apt install"],
    "linux":            ["linux", "kernel", "distro"],
    "android":          ["android", "apk"],
    "ios":              ["ios ", "iphone", "ipad"],
}

import random

def get_dyknow(context_tag: str) -> str:
    facts = DYK_BANK_EXTENDED.get(context_tag, DYK_BANK_EXTENDED["generic"])
    return random.choice(facts)

def detect_context(command_or_app_name: str) -> str:
    cmd = command_or_app_name.lower()
    for tag, keywords in DETECTION_KEYWORDS.items():
        if any(kw in cmd for kw in keywords):
            return tag
    return "generic"
```

---
*WHIZTANT DYK BANK EXTENDED — v2.0*  
*Apps covered: ~110 | Total facts: ~330*  
*Append to existing DYK_BANK or replace entirely.*
