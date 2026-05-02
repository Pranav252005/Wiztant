# Universal Research → Execute Pipeline — Whiztant Agent
> **Scope:** ANY game, ANY software, ANY performance goal. This spec never hard-codes a game name. Every section uses `[TARGET]` as a placeholder — the agent fills it in at runtime from the user's request.
>
> **Cross-reference:** `agent_browser_spec.md`, `agent_navigation_spec.md`, `agent_browser_spec.md`

---

## Table of Contents

1. [Target Extraction — What Is the User Asking About?](#1-target-extraction)
2. [Target Classification — Game vs Software vs System vs Hardware](#2-target-classification)
3. [Pre-Flight System Detection](#3-pre-flight-system-detection)
4. [Research Pipeline — Universal YouTube Strategy](#4-research-pipeline)
5. [Step Extraction and Parsing](#5-step-extraction-and-parsing)
6. [Execution Layer Map — Every Change Type](#6-execution-layer-map)
7. [Registry Editor — Universal Navigation](#7-registry-editor)
8. [NVIDIA Control Panel — Universal Settings](#8-nvidia-control-panel)
9. [AMD Adrenalin Software — Universal Settings](#9-amd-adrenalin)
10. [Intel Arc Control](#10-intel-arc-control)
11. [Windows Performance Settings — Universal](#11-windows-performance-settings)
12. [Software-Specific Config File Locations — Universal Pattern](#12-config-file-locations)
13. [In-Game Settings — Universal Navigation Pattern](#13-in-game-settings)
14. [IDE / Dev Tool Optimization (Windsurf, VSCode, etc.)](#14-ide-optimization)
15. [Browser Optimization](#15-browser-optimization)
16. [The Full Universal Chained Pipeline](#16-full-pipeline)
17. [Safety Rules and Backup](#17-safety-rules)
18. [Undo and Rollback](#18-undo-rollback)
19. [Universal Registry Key Reference for Any Target](#19-universal-registry-reference)
20. [Agent Phase Prompts](#20-agent-phase-prompts)

---

## 1. Target Extraction

The very first thing the agent does is extract the target from the user's request.

### Extraction Rules

```
User says:                                 Extracted target:
"make Fortnite run better"           →     TARGET = "Fortnite", GOAL = "fps/performance"
"optimize Warzone"                   →     TARGET = "Warzone", GOAL = "fps/performance"
"Windsurf is slow"                   →     TARGET = "Windsurf", GOAL = "speed/responsiveness"
"VSCode lags when typing"            →     TARGET = "Visual Studio Code", GOAL = "input latency"
"Chrome uses too much RAM"           →     TARGET = "Google Chrome", GOAL = "memory usage"
"make my PC faster for editing"      →     TARGET = "PC/System", GOAL = "general performance"
"Blender keeps crashing"             →     TARGET = "Blender", GOAL = "stability/crash fix"
"my mic has latency in OBS"          →     TARGET = "OBS Studio", GOAL = "audio latency"
"reduce input lag for all games"     →     TARGET = "System", GOAL = "global input latency"
"make Premiere Pro faster"           →     TARGET = "Adobe Premiere Pro", GOAL = "render speed"
"Unity editor is slow"               →     TARGET = "Unity Editor", GOAL = "editor performance"
"Spotify skips when I game"          →     TARGET = "Spotify + Gaming", GOAL = "audio + resource conflict"
```

### If Target Is Ambiguous

If the user says "make it run better" with no target:
```
agent asks: "What would you like me to optimize? A game, an app, or your whole PC?"
wait for voice response
extract target from response
proceed
```

---

## 2. Target Classification

Once target is extracted, classify it to know which execution layers apply.

### Classification Table

| Target Type | Examples | Layers That Apply |
|-------------|----------|------------------|
| **AAA Game** | Fortnite, Warzone, Apex, Valorant, CS2, PUBG, GTA V, RDR2, Cyberpunk | All layers 1–5 |
| **Indie/Light Game** | Minecraft, Roblox, Stardew Valley, Among Us | Layers 1, 3 (no heavy GPU tweaks) |
| **Competitive FPS** | CS2, Valorant, Overwatch 2, R6 Siege | All layers, focus on input latency |
| **Open World RPG** | Cyberpunk, Witcher 3, Elden Ring | All layers, focus on GPU/VRAM |
| **Dev IDE / Editor** | Windsurf, VSCode, JetBrains, Android Studio | Layers 1, 4 (JVM/Electron settings), no GPU |
| **Creative Software** | Premiere, After Effects, Blender, DaVinci | Layers 1, 3, 4 (GPU rendering, RAM) |
| **Browser** | Chrome, Edge, Firefox | Layers 1, 4 (flags, hardware accel) |
| **Streaming/Recording** | OBS, Streamlabs, NVIDIA Shadowplay | Layers 1, 3 (encoder settings) |
| **Communication** | Discord, Teams, Zoom | Layers 1, 4 (disable GPU accel if buggy) |
| **System-wide** | "my PC", "Windows", "everything" | All layers, no game-specific steps |

### Layer Application by Target Type

```
Layer 1 — Windows Core Settings:    Apply to EVERY target type
Layer 2 — Registry Edits:           Apply to Games + Dev IDEs + Creative
Layer 3 — GPU Control Panel:        Apply to Games + Creative + Streaming
Layer 4 — App-Specific Config:      Apply to EVERY target type (different files)
Layer 5 — In-App Settings:          Apply to EVERY target type (different menus)
```

---

## 3. Pre-Flight System Detection

Run this before research and before any execution. Results affect every decision.

### Detection Sequence

```
STEP A — GPU Vendor Detection:
  keypress: Win+R → type: dxdiag → Enter → wait: 2.0s
  click: "Display tab in dxdiag"
  screenshot — read GPU name
  
  If name contains "NVIDIA" or "GeForce" or "RTX" or "GTX":
    GPU_VENDOR = "NVIDIA"
    GPU_PANEL = "NVIDIA Control Panel"
    
  If name contains "AMD" or "Radeon" or "RX ":
    GPU_VENDOR = "AMD"
    GPU_PANEL = "AMD Software Adrenalin Edition"
    
  If name contains "Intel" or "Arc" or "Iris" or "UHD":
    GPU_VENDOR = "Intel"
    GPU_PANEL = "Intel Arc Control" or "Intel Graphics Command Center"
    
  If laptop shows two GPUs (integrated + dedicated):
    GPU_TYPE = "hybrid"
    Primary GPU = the dedicated one (NVIDIA/AMD)
    Note: some games run on integrated by default — check GPU assignment

STEP B — Storage Type Detection:
  keypress: Win → type: defrag → click: "Defragment and Optimize Drives"
  screenshot — read "Media type" column for system drive (C:)
  
  If "Solid State Drive":     STORAGE = "SSD" → SysMain can be disabled
  If "Hard Disk Drive":       STORAGE = "HDD" → Keep SysMain enabled
  If "NVMe SSD":              STORAGE = "NVMe" → Fastest, SysMain disable safe

STEP C — RAM Amount:
  keypress: Win+R → type: msinfo32 → Enter → wait: 1.5s
  screenshot — read "Installed Physical Memory (RAM)"
  STORE: RAM_GB = [number]
  
  RAM guidance:
  < 8GB:  Conservative changes only, don't disable page file
  8-16GB: Standard optimization safe
  > 16GB: All optimizations safe, can disable virtual memory for games

STEP D — Windows Version:
  keypress: Win+R → type: winver → Enter
  screenshot — read version number
  STORE: WIN_VERSION = "10" or "11", WIN_BUILD = [build number]
  
  Affects: HAGS availability (Win10 2004+), VRR settings, Game Mode features

STEP E — CPU Detection:
  In msinfo32 window (already open from Step C)
  screenshot — read "Processor" field
  
  If "Intel Core i[5/7/9]" or "Intel Core Ultra":   CPU_VENDOR = "Intel"
  If "AMD Ryzen":                                    CPU_VENDOR = "AMD"
  
  Affects: Core parking settings, scheduler registry keys

STEP F — Check if Target App Is Installed:
  keypress: Win → type: [TARGET name]
  screenshot — if app appears in results: INSTALLED = true
  If not found: ask user "I couldn't find [TARGET] installed. Is it installed somewhere specific?"

STEP G — Check if Target App Is Running:
  keypress: Ctrl+Shift+Esc → Task Manager
  screenshot — check Processes tab for [TARGET] process name
  If running: NOTE "will close and reopen after config changes if needed"
  Close Task Manager
```

### Detection Output JSON (internal agent memory)
```json
{
  "target": "[TARGET]",
  "target_type": "game|ide|creative|browser|system|streaming",
  "gpu_vendor": "NVIDIA|AMD|Intel",
  "gpu_panel": "[panel app name]",
  "storage": "SSD|HDD|NVMe",
  "ram_gb": 16,
  "win_version": "11",
  "win_build": "26100",
  "cpu_vendor": "Intel|AMD",
  "app_installed": true,
  "app_running": false
}
```

---

## 4. Research Pipeline — Universal YouTube Strategy

### Universal Search Query Formula

```
[TARGET_NAME] + [GOAL_KEYWORD] + "guide" + [CURRENT_YEAR]

GOAL mapping:
  fps / performance issues      → "fps boost performance guide"
  lag / stutter / drops         → "lag fix stutter fix guide"  
  crash / not launching         → "crash fix not launching fix"
  slow / unresponsive (app)     → "slow performance fix speed up"
  high CPU / RAM                → "high cpu ram fix optimize"
  input lag                     → "input lag fix low latency guide"
  render speed (creative)       → "render speed optimization guide"
  memory usage                  → "memory leak fix ram usage guide"
  loading times                 → "loading time fix fast loading guide"

Examples:
  "Fortnite"  + fps       → "fortnite fps boost performance guide 2025"
  "Windsurf"  + slow      → "windsurf ide slow performance fix 2025"
  "Cyberpunk" + stutter   → "cyberpunk 2077 stutter fix performance guide 2025"
  "Blender"   + render    → "blender render speed optimization guide 2025"
  "Chrome"    + ram       → "chrome high ram memory fix optimization 2025"
  "OBS"       + quality   → "obs recording settings optimization guide 2025"
  "System"    + gaming    → "windows 11 gaming optimization complete guide 2025"
```

### Alternative Research Sources (use if YouTube insufficient)

If YouTube video has no description steps and transcript is unclear:

```
Source 2 — Reddit:
  Search query: site:reddit.com/r/[relevant_subreddit] [TARGET] optimization settings

  Subreddit mapping:
    FPS Games     → r/FPSAimTrainer, r/GlobalOffensive, r/Competitiveoverwatch
    General Games → r/pcgaming, r/pcmasterrace, r/hardware
    Fortnite      → r/FortNiteBR
    Apex          → r/apexlegends
    Valorant      → r/VALORANT
    CS2           → r/GlobalOffensive
    Warzone       → r/CODWarzone
    Creative apps → r/blender, r/premiere, r/davinciresolve
    IDEs          → r/vscode, r/cursor_ai, r/programming
    OBS           → r/obs
    Windows       → r/Windows11, r/Windows10

Source 3 — Official Documentation:
  Navigate directly to:
    [software_name] + "performance settings" + "official docs" OR "support"
  
  Known official optimization pages:
    Fortnite:    epicgames.com/help → search "performance"
    Valorant:    playvalorant.com/en-us/news → search "performance"
    Chrome:      support.google.com → search "speed up chrome"
    Blender:     docs.blender.org → search "performance"
    VSCode:      code.visualstudio.com/docs → search "performance"

Source 4 — GitHub Issues / Discussions:
  For software tools (IDEs, apps, not games):
  github.com/[repo_name] → Issues → search "performance" "slow" "lag"
```

### Video Selection Criteria (in priority order)
```
1. Views > 50K (games) or > 10K (software/apps — smaller community)
2. Uploaded within last 18 months
3. Title contains: "[TARGET]" + goal keyword
4. Duration: 5–30 minutes (too short = surface level, too long = padded)
5. Channel focus: gaming tech, PC optimization, software tutorials
6. Avoid: channels with "no commentary" only, foreign language (unless user speaks it)
```

---

## 5. Step Extraction and Parsing

### Extraction Priority Order
```
1. Video description (expanded — click "Show more")
2. Pinned creator comment
3. Video transcript (always try — most complete)
4. Top comments sorted by "Top" (community-validated steps)
5. Linked resources in description (Pastebin, GitHub, Google Docs)
```

### Transcript Search Terms by Target Type

After opening transcript, search these terms in order:

```
For GAMES:
  "registry" → find registry key paths
  "HKEY"     → confirm registry paths
  "nvidia" or "amd" → GPU control panel steps
  "settings" → in-game settings steps
  "config"   → config file locations
  "fps"      → frame rate related steps
  "disable"  → services/features to turn off

For IDEs / Dev Tools:
  "settings" or "preferences" → app settings changes
  "memory" or "heap" or "ram" → memory allocation settings
  "extension" or "plugin"     → disable heavy extensions
  "hardware" or "gpu"         → hardware acceleration toggle
  "cache" or "index"          → cache/index settings
  "startup" or "boot"         → startup behavior

For Creative Software:
  "gpu" or "cuda" or "opencl" → GPU rendering settings
  "cache" or "media cache"    → cache settings
  "memory" or "ram"           → RAM allocation
  "preview" or "render"       → render quality settings
  "codec" or "format"         → export/preview codec

For Browsers:
  "flags" or "chrome://flags" → experimental flags
  "hardware acceleration"      → GPU acceleration toggle
  "extension"                  → extensions to disable
  "cache" or "memory"          → cache settings
```

### Universal Step Parser

Parse extracted content into this structure regardless of target:

```json
[
  {
    "step_number": 1,
    "category": "windows_settings | registry | gpu_panel | app_config | app_settings | service | startup",
    "description": "human readable description",
    "action": {
      "type": "navigate | set_value | toggle | create_value | edit_file | run_command",
      "location": "where to go (app name, path, URL, registry path)",
      "target": "what to change (setting name, key name, config line)",
      "value": "what to set it to",
      "current_value": "read before changing (filled at runtime)"
    },
    "impact": "high | medium | low",
    "risk": "safe | caution | risky",
    "requires_restart": true
  }
]
```

### Skip Rules (Universal — Never Execute These)

```
ALWAYS SKIP:
  - Any step requiring third-party software not already installed
    (exception: MSI Afterburner, HWiNFO64, CPU-Z are safe to mention to user)
  - "Disable antivirus" or "turn off Windows Defender"
  - "Disable driver signature enforcement"
  - Overclocking steps (GPU/CPU/RAM) — user must do manually, risk of damage
  - Steps involving BIOS/UEFI changes
  - "Download and run this .exe from [unknown site]"
  - Steps that say "delete System32" or modify core Windows DLLs
  - Any step requiring a paid tool or subscription
  - "Use code [creator]" or any affiliate promotion
  - Steps that are vague: "tweak your PC" with no specifics
  
SKIP AND WARN USER:
  - Steps that disable Windows Update permanently
  - Steps that disable Windows Security Center
  - Any step the agent cannot verify via screenshot after execution
```

---

## 6. Execution Layer Map

Execute ALL layers in this exact order — never skip ahead.

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1 — BACKUP (always first, no exceptions)                 │
│   Export registry keys → C:\whis\backups\registry\             │
│   Backup app config files → C:\whis\backups\configs\           │
│   Log to Whiztant undo stack                                    │
└─────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2 — WINDOWS CORE SETTINGS                                │
│   Power plan, Game Mode, HAGS, Visual Effects,                 │
│   Background apps, Game DVR, Xbox Game Bar                     │
└─────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 3 — REGISTRY EDITS                                       │
│   CPU priority, Network tweaks, GPU scheduling,                │
│   App-specific IFEO entries, Timer resolution                  │
└─────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 4 — GPU CONTROL PANEL                                    │
│   Power mode, Low latency, VSync, Shader cache,                │
│   Per-app profile for [TARGET]                                 │
└─────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 5 — SERVICES AND STARTUP                                 │
│   Disable unnecessary services, Remove startup bloat,          │
│   Scheduled task cleanup                                       │
└─────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 6 — APP-SPECIFIC CONFIG FILES                            │
│   Edit .ini / .cfg / .json / .xml config files,                │
│   JVM args, electron flags, engine.ini, etc.                   │
└─────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 7 — IN-APP SETTINGS                                      │
│   Graphics, audio, input settings inside the app itself        │
│   (requires app to be open)                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Registry Editor — Universal Navigation

### Opening (Same for All Targets)
```
keypress: Win+R → type: regedit → Enter → UAC: Yes
```

### Universal App Priority Registry Key (Works for ANY .exe)

**This single pattern works for any game or software to boost its CPU priority:**

```
Path: HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\[app_executable.exe]\PerfOptions

How to find app executable name:
  Ctrl+Shift+Esc → Task Manager → find [TARGET] process → right-click → Properties
  Read "Name" field → that's the .exe name

Create this key path if it doesn't exist:
  1. Navigate to: HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options
  2. right_click: left panel → New → Key
  3. type: [app_executable.exe] e.g. FortniteClient-Win64-Shipping.exe
  4. Press Enter → expand new key → right_click in right panel → New → Key
  5. type: PerfOptions → Enter
  6. right_click right panel → New → DWORD (32-bit) Value
  7. Name: CpuPriorityClass
  8. Value: 3 (High) — for games and creative apps
            2 (Above Normal) — for IDEs and browsers (safer)
            8 (Above Normal realtime) — only for ultra-competitive games

Common exe names by target:
  Fortnite:          FortniteClient-Win64-Shipping.exe
  Valorant:          VALORANT-Win64-Shipping.exe
  Apex Legends:      r5apex.exe
  CS2:               cs2.exe
  Warzone:           cod.exe
  GTA V:             GTA5.exe
  Cyberpunk 2077:    Cyberpunk2077.exe
  Minecraft (Java):  javaw.exe  ← careful, affects all Java
  Roblox:            RobloxPlayerBeta.exe
  Blender:           blender.exe
  Premiere Pro:      Adobe Premiere Pro.exe
  DaVinci Resolve:   Resolve.exe
  OBS:               obs64.exe
  VSCode:            Code.exe
  Windsurf:          Windsurf.exe
  Chrome:            chrome.exe
  Firefox:           firefox.exe
```

### Universal CPU Priority Separation (All Games)
```
Path: HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\PriorityControl
Value: Win32PrioritySeparation
Gaming value: 26 (decimal) — foreground apps get maximum CPU burst
Dev/IDE value: 38 (decimal) — balanced, prevents IDE from stuttering
Default: 2
```

### Universal GPU Hardware Scheduling
```
Path: HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\GraphicsDrivers
Value: HwSchMode
Enable: 2 | Disable: 1
Apply to: all games, creative apps, IDEs using GPU rendering
```

### Universal Disable Game DVR (Any Situation)
```
Path: HKEY_CURRENT_USER\System\GameConfigStore
Value: GameDVR_Enabled → 0

Path: HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\Windows\GameDVR
Create if missing: AllowGameDVR → DWORD → 0
```

### Universal Mouse Precision Disable
```
Path: HKEY_CURRENT_USER\Control Panel\Mouse
Values:
  MouseSpeed → 0
  MouseThreshold1 → 0
  MouseThreshold2 → 0
Apply to: all games, especially FPS/competitive
```

### Universal Network Latency Reduction
```
Path: HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\
  → Expand to find adapter GUIDs → look for the one with your IP address

In the correct interface GUID folder:
  New DWORD: TcpAckFrequency → 1
  New DWORD: TCPNoDelay → 1

Apply to: all online games, streaming apps
```

### Universal Timer Resolution (Competitive Games / Low Latency Apps)
```
Path: HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\kernel
Value: GlobalTimerResolutionRequests → DWORD → 1
Apply to: FPS games, rhythm games, DAWs, any latency-sensitive app
```

### App-Specific Registry Sections

#### For Java-Based Apps (Minecraft Java, Android Studio, IntelliJ)
```
Path: HKEY_LOCAL_MACHINE\SOFTWARE\JavaSoft\Java Runtime Environment
  → Find version subkey → check RuntimeLib path
Note: Java heap is controlled via JVM args, not registry — see Layer 6
```

#### For Electron Apps (VSCode, Windsurf, Discord, Slack, Notion)
```
Path: HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\[electron_app.exe]\PerfOptions
  CpuPriorityClass → 2 (Above Normal — don't set High for IDEs, causes system jank)
Note: Electron GPU acceleration is controlled via app flags — see Layer 6
```

---

## 8. NVIDIA Control Panel — Universal Settings

### Universal Settings for Any Target

Always navigate to: Manage 3D Settings

#### Global Settings (baseline for everything)
```
Power management mode       → Prefer maximum performance
Low Latency Mode            → Ultra (games, audio, streaming)
                            → Off (if app has rendering issues)
Texture filtering - Quality → High Performance
Vertical sync               → Off (let app handle it)
Shader Cache Size           → 10 GB or Unlimited
Threaded optimization       → On
Max Frame Rate              → Monitor refresh rate (games) or Unlimited (creative)
Background App Frame Rate   → 30 fps
```

#### Per-Application Profile — How to Add Any App
```
1. Manage 3D Settings → Program Settings tab
2. click: "Add"
3. In file browser: navigate to app executable
   
   Finding executables for any app:
     Method A: Win → type: [app name] → right-click → Open file location → find .exe
     Method B: Task Manager → find process → right-click → Open file location
     Method C: C:\Program Files\ or C:\Program Files (x86)\ → browse to app folder
   
4. Select .exe → click: "Add Selected Program"
5. Set per-app overrides
6. click: "Apply"
```

#### Settings by Target Type

```
COMPETITIVE FPS GAMES (CS2, Valorant, Overwatch, R6, Apex):
  Low Latency Mode → Ultra
  Power management → Prefer maximum performance
  Texture filtering → High Performance
  VSync → Off
  Max Frame Rate → Monitor cap or 0 (uncapped)

OPEN WORLD / AAA GAMES (Cyberpunk, GTA, RDR2, Elden Ring):
  Power management → Prefer maximum performance
  Shader Cache → Unlimited (reduces stutter)
  Texture filtering → Quality or Performance (balance)
  Max Frame Rate → Monitor refresh rate

CREATIVE / RENDERING (Blender, Premiere, DaVinci):
  Power management → Prefer maximum performance
  CUDA - GPUs → Select your GPU
  OpenGL rendering GPU → Select your GPU
  Texture filtering → Quality
  VSync → Off or Application controlled

STREAMING / RECORDING (OBS, Shadowplay):
  Low Latency Mode → Off (encoder needs buffering)
  Texture filtering → Quality
  Power management → Prefer maximum performance

IDEs / ELECTRON APPS (VSCode, Windsurf):
  Low Latency Mode → Off
  Power management → Optimal Power or Prefer max (your choice)
  Note: Electron GPU accel is often more stable when NVCP is left at defaults
```

---

## 9. AMD Adrenalin Software — Universal Settings

### Opening AMD Software
```
Method A: right_click desktop → AMD Software: Adrenalin Edition
Method B: Win → type: AMD Software → Enter
Method C: System tray → AMD icon → Open
```

### UI-TARS Element Descriptions for AMD Software
```
"the AMD Software Adrenalin Edition window with tabs at the top"
"the Gaming tab at the top of AMD Software"
"the Performance tab at the top of AMD Software"
"the Global Graphics section in the Gaming tab"
"the Add a game button in the Gaming tab"
"the Radeon Anti-Lag setting in Global Graphics"
"the Radeon Boost setting"
"the AMD Fluid Motion Frames toggle"
"the Power section in the Performance tab"
"the Tuning tab in AMD Software"
"the Apply button in AMD Software"
```

### Universal AMD Performance Settings
```
Gaming Tab → Global Graphics:
  Radeon Anti-Lag         → Enabled (reduces input lag)
  Radeon Anti-Lag+        → Enabled (if available)
  Radeon Boost            → Enabled for competitive, Disabled for visual fidelity
  Image Sharpening        → Enabled, Sharpness 80%
  Texture Filtering Quality → Performance
  Tessellation Mode       → Override → 8x
  Wait for Vertical Refresh → Always Off
  
Performance Tab → Tuning:
  Auto Tuning → Disabled (unless user wants it)
  Power Limit → +20% (more stable performance)
  
Per-game profile: same pattern as NVIDIA — add executable
```

---

## 10. Intel Arc Control

### Opening
```
Win → type: Intel Arc Control → Enter
OR: System tray → Intel Arc icon
```

### UI-TARS Element Descriptions
```
"the Intel Arc Control application window"
"the Gaming tab in Intel Arc Control"
"the Performance tab in Intel Arc Control"
"the System tab in Intel Arc Control"
"the XeSS Upscaling setting"
"the Adaptive Sync toggle in Intel Arc Control"
```

### Key Settings
```
Gaming → Per-game settings:
  Power profile → Maximum Performance
  XeSS → Quality or Performance mode

System → Driver Settings:
  Gaming Mode → On
```

---

## 11. Windows Performance Settings — Universal

### Complete Checklist (Apply to All Target Types)

```
A. Power Plan → High Performance or Ultimate Performance
   Win+R → powercfg.cpl
   
   Enable Ultimate Performance (one-time setup):
   Win+X → Terminal (Admin) → 
   powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61
   
   → Select: Ultimate Performance

B. Game Mode → On (for games) or Off (for creative apps — can cause stutter)
   Win+I → Gaming → Game Mode

C. Hardware-Accelerated GPU Scheduling (HAGS) → On
   Win+I → System → Display → Graphics → Change default graphics settings
   Requires: GPU driver support (NVIDIA 2000+ series, AMD 5000+, Intel Iris/Arc)
   
D. Variable Refresh Rate (VRR) → On (if monitor supports it)
   Same location as HAGS

E. Visual Effects → Adjust for best performance
   Win+R → sysdm.cpl → Advanced → Performance → Settings
   → "Adjust for best performance"
   Restore: check "Show thumbnails instead of icons" (makes folders usable)

F. Xbox Game Bar → Off
   Win+I → Gaming → Xbox Game Bar → Off

G. Game DVR Background Recording → Off
   Win+I → Gaming → Captures → Off

H. Storage Sense → On (SSD only — maintains performance)
   Win+I → System → Storage → Storage Sense

I. Virtual Memory (for RAM-starved systems < 16GB)
   Win+R → sysdm.cpl → Advanced → Performance → Settings → Advanced → Virtual Memory
   Change → Uncheck "Automatically manage"
   Custom size: Initial = 1.5x RAM in MB, Maximum = 3x RAM in MB
   (e.g. 8GB RAM → Initial: 12288, Maximum: 24576)

J. Focus Assist → Off (prevents notification interruptions)
   Win+I → System → Focus or Notification settings

K. Transparency Effects → Off (minor GPU savings)
   Win+I → Personalization → Colors → uncheck Transparency effects

L. Animation Effects → Off (reduces UI lag feel)
   Win+I → Accessibility → Visual Effects → Animation effects Off
```

---

## 12. Config File Locations — Universal Pattern

### How to Find ANY App's Config Location

```
PATTERN A — AppData (most Windows apps):
  %AppData%\[Company]\[AppName]\         (Roaming)
  %LocalAppData%\[Company]\[AppName]\    (Local — more common)
  %LocalAppData%\[AppName]\              (if no company folder)

  Navigate: Win+R → type the path → Enter
  Expand %AppData% = C:\Users\[Username]\AppData\Roaming
  Expand %LocalAppData% = C:\Users\[Username]\AppData\Local

PATTERN B — Documents (games especially):
  Documents\[AppName]\
  Documents\My Games\[AppName]\
  Documents\[Publisher]\[AppName]\

PATTERN C — Installation folder:
  C:\Program Files\[AppName]\
  C:\Program Files (x86)\[AppName]\
  Steam games: C:\Program Files (x86)\Steam\steamapps\common\[GameName]\

PATTERN D — ProgramData (system-wide app data):
  C:\ProgramData\[AppName]\

PATTERN E — Registry-defined path:
  Check: HKLM\SOFTWARE\[AppName] → "InstallDir" or "ConfigPath" value
```

### Config Files by Target Type

#### Games (Unreal Engine — Fortnite, Valorant, Layers of Fear, etc.)
```
%LocalAppData%\[GameName]\Saved\Config\WindowsClient\
Files:
  GameUserSettings.ini  → graphics, resolution, keybinds
  Engine.ini            → advanced engine overrides
  Input.ini             → input settings

Key Engine.ini performance overrides (works for ALL UE games):
  [SystemSettings]
  r.MaxAnisotropy=0
  r.SkeletalMeshLODBias=0
  r.ParticleLODBias=2
  foliage.LODDistanceScale=0.1
  r.ViewDistanceScale=0.1
  r.Streaming.LimitPoolSizeToVRAM=1
  r.Streaming.PoolSize=1024
  [/Script/Engine.RendererSettings]
  r.DefaultFeature.MotionBlur=False
  r.DefaultFeature.Bloom=False
  r.DefaultFeature.LensFlare=False
```

#### Games (Source Engine — CS2, Dota 2, TF2)
```
Location: Steam\steamapps\common\[GameName]\[game]\cfg\
Files:
  config.cfg    → key bindings, cvars
  video.txt     → graphics settings (CS2)
  autoexec.cfg  → runs on launch (create if missing)

Common autoexec.cfg performance lines (CS2):
  fps_max 0                   // uncapped
  cl_showfps 1                // show fps counter
  r_dynamic 0                 // disable dynamic lighting
  mat_queue_mode 2            // multi-threaded rendering
  -high in launch options     // (not cfg — Steam launch options)
  -threads [core_count]       // use all CPU cores
```

#### Games (Steam — Launch Options, All Games)
```
How to set Steam launch options for ANY game:
  1. keypress: Ctrl+L → type: steam:// → (open Steam is easier)
     OR open Steam from taskbar/desktop
  2. click: "Library in Steam"
  3. right_click: "[game name] in library list"
  4. click: "Properties"
  5. click: "General tab"
  6. Find: "Launch Options" text field
  7. type: [launch flags]

Universal performance launch flags:
  -high              → sets process priority to High
  -novsync           → disables VSync at launch
  -nod3d9ex          → (older games) forces DX9
  +fps_max 0         → uncaps frame rate (Source games)
  -fullscreen        → force fullscreen
  -w [width] -h [height]  → force resolution
```

#### Games (Epic Games Launcher — All Epic Games)
```
Launch options: Epic Games Library → [game] → three dots → Manage → Additional command line args
Same flags as Steam where applicable
```

#### Games (Battle.net — WoW, Warzone, Overwatch, Diablo)
```
Config locations:
  Warzone/CoD:      Documents\Call of Duty\players\adv_options.ini
  WoW:              Documents\World of Warcraft\_retail_\WTF\Config.wtf
  Overwatch 2:      Documents\Overwatch\Settings\Settings_v0.ini
  Diablo IV:        Documents\Diablo IV\
```

#### Games (Roblox)
```
Config: %LocalAppData%\Roblox\GlobalSettings_13.xml
  or:   %LocalAppData%\Roblox\ClientSettings\ClientAppSettings.json

Performance flags via ClientAppSettings.json:
  {
    "FFlagDebugGraphicsDisableDirect3D11": false,
    "DFIntTaskSchedulerTargetFps": 144,
    "FFlagHandleAltEnterFullscreenManually": false
  }
```

#### Games (Minecraft Java Edition)
```
Launcher: %AppData%\.minecraft\
  options.txt        → all settings
  JVM arguments in launcher: -Xmx[RAM]G -Xms[RAM]G -XX:+UseG1GC

Performance JVM args (paste in Minecraft Launcher → Installations → Edit → More Options):
  -Xmx4G -Xms4G -XX:+UnlockExperimentalVMOptions -XX:+UseG1GC
  -XX:G1NewSizePercent=20 -XX:G1ReservePercent=20
  -XX:MaxGCPauseMillis=50 -XX:G1HeapRegionSize=32M
  
  Adjust -Xmx and -Xms: half of total RAM, max 8G
  (8GB RAM system → -Xmx4G | 16GB RAM → -Xmx8G)
```

#### Games (Minecraft Bedrock Edition)
```
Config: %LocalAppData%\Packages\Microsoft.MinecraftUWP_[hash]\LocalState\games\com.mojang\
Note: UWP — limited config access, mostly in-game settings only
```

#### IDEs — VSCode
```
Settings files:
  %AppData%\Code\User\settings.json   → user settings
  %AppData%\Code\User\keybindings.json

Performance settings.json keys:
  "editor.renderWhitespace": "none"
  "editor.minimap.enabled": false
  "editor.renderControlCharacters": false
  "editor.hover.delay": 500
  "search.followSymlinks": false
  "files.watcherExclude": {
    "**/node_modules/**": true,
    "**/.git/**": true,
    "**/dist/**": true
  }
  "extensions.autoUpdate": false
  "git.autoRepositoryDetection": false
  "typescript.disableAutomaticTypeAcquisition": true
  "editor.formatOnSave": false    (enable only if needed)
```

#### IDEs — Windsurf
```
Same as VSCode (built on same base):
  %AppData%\Windsurf\User\settings.json
  Same performance settings.json keys as VSCode above

Additional Windsurf-specific:
  Disable unused AI features if not using them
  settings.json: "windsurf.enableInlineSuggestions": false  (if causing lag)
  
Memory: Windsurf is Electron — it runs Chromium + Node.js
  Check: Task Manager → Windsurf process tree
  If > 2GB RAM: disable heavy extensions one by one to find culprit
```

#### IDEs — JetBrains (IntelliJ, PyCharm, WebStorm, Android Studio)
```
Config: %AppData%\JetBrains\[AppName][Version]\
  [AppName].vmoptions   → JVM heap settings

Edit .vmoptions for performance:
  -Xmx4096m          → max heap (set to 50-75% of RAM)
  -Xms2048m          → initial heap
  -XX:+UseG1GC       → better GC for large heaps
  -XX:SoftRefLRUPolicyMSPerMB=50

Navigate: Help → Edit Custom VM Options → edit file → restart
```

#### Creative — Blender
```
Config: %AppData%\Blender Foundation\Blender\[version]\config\
  userpref.blend  → user preferences (binary, edit in-app)
  
In-app performance settings:
  Edit → Preferences → System:
    Cycles Render Devices → CUDA or OptiX (NVIDIA) or HIP (AMD)
    Memory & Limits → Undo steps: 32 (reduce from 256)
    
  Edit → Preferences → Interface:
    Pie menu timeout: 50ms
    
Viewport performance:
  Overlays → disable: Statistics, Face Orientation, etc.
  Viewport Shading → Solid mode for modeling (not Material Preview)
```

#### Creative — Adobe Premiere Pro
```
Config: %AppData%\Adobe\Premiere Pro\[version]\
  
Performance settings (Edit → Preferences):
  Media Cache: set to fast SSD path
  Memory: Set to leave 4GB for OS, rest for Premiere
  GPU: Enable Mercury Playback Engine GPU Acceleration
  
  Preferences → Memory:
    RAM Reserved for other applications: 4096 MB (rest goes to Premiere)
  Preferences → Media:
    Indeterminate Media Timebase: 60fps for smooth preview
  Preferences → Playback:
    Preroll: 2 seconds
    Postroll: 2 seconds
```

#### Creative — DaVinci Resolve
```
Performance settings (DaVinci Resolve → Preferences → System):
  GPU Processing Mode → CUDA (NVIDIA) or OpenCL (AMD)
  GPU Selection → select your GPU
  Memory Settings → check "Limit GPU memory" only if crashing
  
  Project Settings → Master Settings:
    Optimized Media → ProRes Proxy or DNxHR LB (fast preview)
    Render Cache → Smart
    
  Playback → Render Cache → User
```

#### Streaming — OBS Studio
```
Config: %AppData%\obs-studio\
  basic\profiles\[profile]\\
    basic.ini   → encoder, output settings
  basic\scenes\ → scene files

Performance settings (Settings → Output → Advanced):
  Encoder: NVIDIA NVENC H.264 (GPU, low CPU impact)
           AMD AMF H.264 (AMD equivalent)
           x264 (CPU — only if GPU encoder unavailable)
  Rate Control: CQP (constant quality, best for recordings)
  CQP value: 18-23 (lower = better quality, more file size)
  
Settings → Advanced:
  Process Priority: High
  
Settings → Video:
  Output resolution: 1920x1080 or 1280x720 for streaming
  FPS: 60 for recording, 60 for streaming (if upload allows)
```

#### Browser — Chrome/Edge Performance Config
```
chrome://flags/ or edge://flags/ useful flags:
  #enable-gpu-rasterization        → Enabled
  #enable-zero-copy                → Enabled
  #enable-vulkan                   → Enabled (test for stability)
  #smooth-scrolling                → Enabled
  #enable-parallel-downloading     → Enabled
  #enable-throttle-display-none-andvisibility-hidden-cross-origin-iframes → Enabled

Memory saving (Chrome):
  chrome://settings/performance
  Memory Saver → On
  Energy Saver → On (on battery)
  
Extensions: Disable all unused extensions
  chrome://extensions → toggle off everything not actively used
  Each extension adds 50-200MB RAM
```

#### Communication — Discord
```
Performance: Settings → Voice & Video:
  Hardware acceleration → Off if causing black screen/crashes
  Video codec → turn off VP9 if video calls stutter
  
Settings → Appearance:
  Hardware Acceleration → Off (significant GPU savings)
  
Settings → Windows Settings:
  Open Discord with system startup → Off (if not needed)
  Minimize to system tray → On
```

---

## 13. In-Game Settings — Universal Navigation Pattern

### Universal Pattern to Reach Graphics Settings in Any Game

```
PATTERN A — Main menu escape:
  1. Launch game or go to main menu
  2. keypress: Escape
  3. Look for: Settings / Options / Configuration icon
  4. click: "Settings or Options button"
  5. click: "Video or Graphics or Display tab"
  6. Make changes
  7. click: "Apply or Save button"

PATTERN B — In-game overlay:
  Fortnite: Escape → Settings gear icon
  Apex: Escape → Settings
  CS2: Escape → Settings → Video
  Valorant: Escape → Settings → Video
  Overwatch: Escape → Options → Video
  GTA V: Escape → Settings → Graphics
  Cyberpunk: Escape → Settings → Graphics
  Warzone: Escape → Settings → Graphics
  
PATTERN C — Launcher settings (some games):
  Epic Games Launcher / Battle.net → game settings before launch
  Minecraft Launcher → Java settings panel

PATTERN D — Config file only (no in-game menu):
  CS2 video.txt, some older games
  Edit config file directly (see Layer 6)
```

### Universal Graphics Settings Priority for Performance

Apply in this order — always tradeoff quality for frames on low-end systems:

```
1. Resolution Scaling / Render Scale:
   Keep at 100% if GPU can handle it
   Reduce to 90-75% only if still GPU-limited after everything else

2. Shadow Quality → Low or Off (biggest fps gain)

3. Anti-Aliasing → Off or lowest option (big fps gain)

4. Post-Processing → Low or Off (motion blur, depth of field, lens flare)

5. Ambient Occlusion → Off

6. Ray Tracing → Off (massive fps drain, keep off unless high-end GPU)

7. Textures → Medium (VRAM dependent — don't go lower unless VRAM limited)

8. View Distance / Level of Detail → Medium (affects how far objects render)

9. Effects Quality → Low

10. Foliage / Vegetation → Low or Off

11. V-Sync → Off (use monitor's VRR/G-Sync/FreeSync instead)

12. Frame Rate Cap → set to monitor refresh rate (prevents tearing without VSync overhead)

13. Window Mode → Fullscreen (lowest input latency)
    Exclusive Fullscreen if option exists

14. Resolution → Native monitor resolution (never lower for competitive games)
```

---

## 14. IDE / Dev Tool Optimization — Windsurf, VSCode, JetBrains

### Why IDEs Get Slow (root causes)

```
1. Too many extensions running in background
2. File watcher monitoring too many files (node_modules, .git, dist)
3. TypeScript language server indexing huge codebases
4. Git extension scanning large repos
5. Electron GPU rendering overhead (can be disabled)
6. Insufficient JVM heap (JetBrains only)
7. Low-priority process being starved by other apps
```

### Step-by-Step IDE Performance Fix

```
STEP 1 — Identify the bottleneck:
  Windsurf/VSCode: Help → Open Process Explorer (or Ctrl+Shift+P → "Process Explorer")
  screenshot — see which process uses most CPU/RAM
  (Extension Host? Main process? GPU Process?)

STEP 2 — Disable unused extensions:
  Ctrl+Shift+X → Extensions panel
  Sort by: activity bar shows "recently used"
  Disable any extension you don't actively use daily
  Each disabled extension = less startup time + less RAM

STEP 3 — Exclude heavy folders from file watching:
  settings.json: "files.watcherExclude" → add node_modules, .git, dist, build, .next

STEP 4 — Reduce TypeScript strictness on large repos:
  tsconfig.json: "skipLibCheck": true
  settings.json: "typescript.disableAutomaticTypeAcquisition": true

STEP 5 — Increase TS language server memory:
  settings.json: "typescript.tsserver.maxTsServerMemory": 4096

STEP 6 — For JetBrains — increase heap:
  Help → Edit Custom VM Options
  -Xmx4096m (set to 50% of total RAM)
  Restart IDE

STEP 7 — Set process priority (Registry IFEO — see Layer 3):
  Windsurf.exe / Code.exe → CpuPriorityClass → 2

STEP 8 — GPU acceleration (if UI is laggy):
  Try disabling: settings.json: "editor.smoothScrolling": false
  If still laggy: launch with --disable-gpu flag
  Add to shortcut: right-click IDE shortcut → Properties → Target → add --disable-gpu
```

---

## 15. Browser Optimization

### Universal Browser Performance Steps

```
STEP 1 — Check memory usage:
  Chrome: chrome://memory-internals or chrome://system
  Look for tabs using > 500MB — consider closing them

STEP 2 — Disable hardware acceleration (if crashes):
  Chrome: Settings → System → Use hardware acceleration → Off → Relaunch
  Edge: Settings → System and performance → Use hardware acceleration

STEP 3 — Enable memory saver (Chrome/Edge):
  Chrome: Settings → Performance → Memory saver → On
  Edge: Settings → System → Sleeping tabs → On

STEP 4 — Disable unused extensions:
  chrome://extensions → toggle off everything not needed

STEP 5 — Clear cache:
  Ctrl+Shift+Delete → Last 4 weeks → Cached images and files → Clear

STEP 6 — Reset flags if unstable:
  chrome://flags → Reset all → Relaunch

STEP 7 — Profile for performance flags:
  See Section 12 Browser config above
```

---

## 16. Full Universal Chained Pipeline

This is the agent's complete execution flow for ANY task of the form:
**"Make [TARGET] run/work better"**

### Phase 0 — Extract and Detect (1–2 minutes)
```
0.1  Extract TARGET and GOAL from user request
0.2  Classify target type (game / IDE / creative / browser / system)
0.3  Run pre-flight system detection (GPU, storage, RAM, Windows version)
0.4  Determine which layers apply
0.5  Determine which research sources to use
0.6  Speak: "I'm going to optimize [TARGET]. Let me first check your system and research the best settings."
```

### Phase 1 — Research (2–4 minutes)
```
1.1  Open new browser tab (Ctrl+T)
1.2  Go to YouTube
1.3  Search: [TARGET] + [GOAL_KEYWORD] + guide + 2025
1.4  Select best video (views, recency, comprehensiveness)
1.5  Pause video immediately (K)
1.6  Extract steps from: description → pinned comment → transcript
1.7  If insufficient: try Reddit or official docs
1.8  Parse all steps into structured JSON with categories
1.9  Speak: "I found a guide with [X] optimization steps for [TARGET]. Starting now."
```

### Phase 2 — Backup (always, no exceptions)
```
2.1  Create backup folders:
     mkdir C:\whis\backups\registry
     mkdir C:\whis\backups\configs\[TARGET_sanitized]
2.2  Export relevant registry keys to backup folder
2.3  Copy app config files to backup folder
2.4  Log planned changes to Whiztant undo stack
2.5  Speak: "Backups created. All changes can be undone."
```

### Phase 3 — Windows Core Settings
```
For each step in category "windows_settings":
  Execute the change
  Screenshot to verify
  Log to undo stack
```

### Phase 4 — Registry Edits
```
For each step in category "registry":
  Export the key first (individual backup)
  Navigate to key path via address bar
  Read and log current value
  Make the change
  Screenshot to verify
  Log to undo stack
```

### Phase 5 — GPU Control Panel
```
Open the correct GPU panel (NVIDIA/AMD/Intel based on detection)
For each step in category "gpu_panel":
  Navigate to setting
  Make change
  Screenshot to verify
Apply all (click Apply button)
Close GPU panel
```

### Phase 6 — Services and Startup
```
For each step in category "service":
  Win+R → services.msc
  Find service by name
  Stop → set Disabled
  Screenshot to verify
  Log to undo stack
For startup programs:
  Ctrl+Shift+Esc → Startup tab → disable non-essential items
```

### Phase 7 — App Config Files
```
For each step in category "app_config":
  Navigate to config file location (see Section 12)
  Open file (Notepad or default editor)
  Use Ctrl+H (Find & Replace) for each value change
  Save (Ctrl+S)
  Set to read-only if applicable (right-click → Properties → Read-only)
```

### Phase 8 — In-App Settings (requires app open)
```
If app not running: launch it
For each step in category "app_settings":
  Navigate to settings menu (using universal pattern from Section 13)
  Make change
  Screenshot to verify
Apply / Save settings
Close settings menu
```

### Phase 9 — Report and Restart
```
9.1  Compile list of all changes made
9.2  Compile list of any skipped steps (and why)
9.3  Speak complete summary:
     "I've finished optimizing [TARGET]. Here's what I changed:
      [Layer 2: X Windows settings]
      [Layer 3: X registry edits]
      [Layer 4: X GPU settings]
      [Layer 5: X services disabled]
      [Layer 6: X config file changes]
      [Layer 7: X in-app settings]
      
      All changes are backed up at C:\whis\backups\
      You can say 'undo [TARGET] optimization' to revert everything.
      
      [Skipped steps if any: skipped [X] steps that require manual action or are risky]
      
      A restart is recommended for registry and driver changes to take full effect.
      Should I restart now?"

9.4  Wait for voice response
9.5  If yes: Win → Restart → Confirm
9.6  If no: idle, log session complete
```

---

## 17. Safety Rules

### Mandatory Before Every Execution

```
RULE 1 — Backup first, always:
  Never modify registry, config files, or system settings without backup.
  Backup path: C:\whis\backups\

RULE 2 — Read before write:
  Always screenshot and note the CURRENT value before changing it.
  Log: old_value → new_value in undo stack.

RULE 3 — One change, one screenshot:
  After every single change, take a screenshot to verify it was applied.
  If verification fails: log the failure, skip to next step, report at end.

RULE 4 — Never delete registry keys, only values:
  right_click → Delete only on VALUE entries in the right panel.
  Never delete a KEY (folder) in the left panel unless research specifically says so.

RULE 5 — Skip overclocking entirely:
  Never change GPU/CPU/RAM clock speeds, voltages, or power limits beyond 
  the slider the GPU panel exposes as "safe."
  Tell user: "I've skipped overclocking steps — those should be done manually 
  with monitoring software."

RULE 6 — Never disable Windows Defender:
  Skip any step that says to disable antivirus, security center, or SmartScreen.

RULE 7 — Confirm before big changes:
  If a step is marked risk: "caution" or "risky" in parsed JSON:
  Speak: "The next step is [description]. This modifies [what]. Should I proceed?"
  Wait for voice confirmation.

RULE 8 — App-specific registry paths only:
  Only use IFEO paths for the specific target app's .exe.
  Never set blanket priorities on system executables (svchost.exe, etc.)
```

---

## 18. Undo and Rollback

### User says "undo [TARGET] changes" or "revert [TARGET] optimization"

```
STEP 1 — Find backups:
  keypress: Win+R → type: C:\whis\backups → Enter
  List: registry\ and configs\ folders
  screenshot — identify [TARGET]-related backup files

STEP 2 — Restore registry:
  For each .reg file in C:\whis\backups\registry\ related to [TARGET]:
    double_click: [backup.reg file]
    click: "Yes" in import confirmation
    click: "OK"

STEP 3 — Restore config files:
  Navigate to C:\whis\backups\configs\[TARGET]\
  Copy all files
  Navigate to original config location (see Section 12)
  If files are read-only: right-click → Properties → uncheck Read-only first
  Paste and overwrite

STEP 4 — Restore NVIDIA settings:
  NVIDIA Control Panel → Manage 3D Settings → Restore Defaults

STEP 5 — Restore power plan:
  powercfg.cpl → select Balanced (Windows default)

STEP 6 — Re-enable disabled services:
  Win+R → services.msc
  For each service disabled during optimization:
    Find service → set Startup type back to Automatic → Start

STEP 7 — Speak:
  "[TARGET] optimization has been fully reverted. Restart recommended."
```

---

## 19. Universal Registry Key Reference

### Works for ANY target — fill in [APP_EXE] at runtime

```
# Any app CPU priority:
HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\[APP_EXE]\PerfOptions
  CpuPriorityClass: 3=High (games), 2=Above Normal (IDEs/apps), 1=Normal

# Global CPU scheduling:
HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl
  Win32PrioritySeparation: 26 (games), 38 (balanced), 2 (default)

# GPU hardware scheduling:
HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers
  HwSchMode: 2=On, 1=Off

# Game DVR (affects all games):
HKCU\System\GameConfigStore
  GameDVR_Enabled: 0=Off, 1=On
HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR
  AllowGameDVR: 0=Off

# Mouse precision (all games):
HKCU\Control Panel\Mouse
  MouseSpeed: 0, MouseThreshold1: 0, MouseThreshold2: 0

# Network latency (all online games):
HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\{guid}
  TcpAckFrequency: 1
  TCPNoDelay: 1

# Timer resolution:
HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\kernel
  GlobalTimerResolutionRequests: 1

# Core parking (keeps all CPU cores available):
HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerSettings\
  54533251-82be-4824-96c1-47b60b740d00\0cc5b647-c1df-4637-891a-dec35c318583
  ValueMax: 0

# Disable NVIDIA telemetry (optional, minor performance):
HKLM\SYSTEM\CurrentControlSet\Services\NvTelemetryContainer
  Start: 4 (disabled)

# SysMain (Superfetch) — SSD only:
HKLM\SYSTEM\CurrentControlSet\Services\SysMain
  Start: 4 (disabled) — SSD only, improves responsiveness
        2 (automatic) — HDD, keep enabled
```

---

## 20. Agent Phase Prompts

### Phase 0 — Target and Goal Extraction Prompt
```
User request: "[USER_TEXT]"

Extract:
1. TARGET: the specific game, software, or system the user wants to optimize
   (be specific — not "game" but "Fortnite", not "editor" but "Visual Studio Code")
2. GOAL: what they want (fps, stability, speed, memory, latency, crash fix, render speed)
3. SCOPE: game_only | system_only | both | app_only

Output JSON only:
{
  "target": "...",
  "target_type": "aaa_game|indie_game|fps_game|rpg_game|ide|creative|browser|streaming|system|other",
  "goal": "fps|stability|speed|memory|latency|crash_fix|render_speed|general",
  "scope": "game_only|system_only|both|app_only",
  "executable_name": "best guess at .exe name, e.g. cs2.exe",
  "search_query": "optimized YouTube search query"
}
```

### Phase 1 — Step Extraction Prompt
```
I extracted this content from a guide about optimizing [TARGET]:

[EXTRACTED_CONTENT]

System context:
- GPU: [GPU_VENDOR] [GPU_MODEL]
- Storage: [SSD/HDD]
- RAM: [RAM_GB]GB
- Windows: [WIN_VERSION] build [WIN_BUILD]

Extract ONLY technical, executable steps. Skip: promotions, opinions, vague advice.
For each step output:
{
  "category": "windows_settings|registry|gpu_panel|app_config|app_settings|service|startup|launch_options",
  "description": "one line description",
  "location": "where to navigate",
  "setting_name": "what to change",
  "new_value": "what to set it to",
  "impact": "high|medium|low",
  "risk": "safe|caution|risky",
  "requires_restart": true|false,
  "skip_reason": null or "reason if should be skipped"
}

Output JSON array only.
```

### Phase 9 — Summary Speech Prompt
```
I just completed optimizing [TARGET] for the user.

Changes made:
[LIST_OF_CHANGES]

Skipped steps:
[LIST_OF_SKIPPED_WITH_REASONS]

Write a natural, conversational 4-6 sentence spoken summary.
- Start with what was done
- Mention the most impactful changes
- Note anything skipped
- End with restart recommendation
- Do NOT use technical jargon — say "I turned off background recording" not "I set GameDVR_Enabled to 0"
- Do NOT use bullet points — it will be spoken by TTS
```

---

*Store at: `C:\whis\whiztant-app\agent_universal_optimize_spec.md`*
*Replaces: `agent_research_execute_spec.md` (superset of that file)*
*Cross-reference: `agent_browser_spec.md`, `agent_navigation_spec.md`, `core/system_access.py`*
