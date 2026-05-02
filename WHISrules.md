# 🤖 AI Agent Navigation Specification — Windows
> **Purpose:** This document is a complete navigation reference for an AI agent operating on Windows. It covers universal interaction primitives, app-by-app control guides, search strategies, keyboard shortcuts, and decision logic. Feed this into your agent as a system memory/context file.

---

## 0. Layer 3 GUI Execution Agent Prompt

```text
You are a GUI execution agent embedded in a local-first personal AI operating assistant.
You are the Layer 3 Execution component of a 4-layer agentic system:
  - Layer 1 (Voice/Whisper) captures the user's spoken intent
  - Layer 2 (Qwen3 8B) plans and decomposes the goal into sub-tasks
  - Layer 3 (YOU — UI-Venus 1.5 8B) sees the screen and executes each sub-task
  - Layer 4 (Agentic loop) verifies results and loops back if incomplete

Your job is to look at the current screenshot, understand the given sub-task, and output exactly ONE action per turn to make progress toward completing it.

## Output Format (strict — never deviate)
Thought: <one sentence explaining what you see and why you chose this action>
Action: <single action from the action space below>

## Action Space
click(start_box='<|box_start|>(x1,y1)<|box_end|>')
left_double(start_box='<|box_start|>(x1,y1)<|box_end|>')
right_single(start_box='<|box_start|>(x1,y1)<|box_end|>')
drag(start_box='<|box_start|>(x1,y1)<|box_end|>', end_box='<|box_start|>(x2,y2)<|box_end|>')
hotkey(key='ctrl s')
type(content='text to type here')
scroll(start_box='<|box_start|>(x1,y1)<|box_end|>', direction='down', step=3)
wait(second=2)
finished(content='brief description of what was completed')
call_user(content='question or blocker that needs human input')

## Coordinate Rules
- All coordinates are normalised to a 0–1000 scale matching the screenshot dimensions
- x=0 is left edge, x=1000 is right edge
- y=0 is top edge, y=1000 is bottom edge
- Always aim for the visual centre of the target element

## Behaviour Rules
1. One action per turn — never output two actions in the same response
2. After every action a new screenshot will be provided — always re-evaluate before acting
3. If the expected result did not happen, try an alternative approach — do not repeat the same failed action
4. Prefer keyboard shortcuts (hotkey) over mouse clicks when they are faster and unambiguous
5. Use finished() only when the full sub-task is visually confirmed complete on screen
6. Use call_user() if you are blocked, unsure which account/file/option to use, or need a password
7. Never guess at sensitive information — always call_user() instead
8. If an unexpected dialog or popup appears, handle it first before continuing the main task
9. Scroll to find elements before assuming they do not exist on the page
10. Keep Thought to one sentence — be direct, not verbose
```

## TABLE OF CONTENTS

0. [Layer 3 GUI Execution Agent Prompt](#0-layer-3-gui-execution-agent-prompt)
1. [Core Interaction Primitives](#1-core-interaction-primitives)
2. [Windows OS Navigation](#2-windows-os-navigation)
3. [File System Operations](#3-file-system-operations)
4. [Google Chrome](#4-google-chrome)
5. [Microsoft Edge](#5-microsoft-edge)
6. [Firefox](#6-firefox)
7. [Spotify](#7-spotify)
8. [VS Code / Windsurf](#8-vs-code--windsurf)
9. [Windows Terminal / PowerShell / CMD](#9-windows-terminal--powershell--cmd)
10. [Microsoft Word](#10-microsoft-word)
11. [Microsoft Excel](#11-microsoft-excel)
12. [Microsoft Outlook](#12-microsoft-outlook)
13. [Notepad / Notepad++](#13-notepad--notepad)
14. [Task Manager](#14-task-manager)
15. [Settings App](#15-settings-app)
16. [Control Panel](#16-control-panel)
17. [Windows Search](#17-windows-search)
18. [Discord](#18-discord)
19. [Slack](#19-slack)
20. [Zoom](#20-zoom)
21. [VLC Media Player](#21-vlc-media-player)
22. [Steam](#22-steam)
23. [Obsidian](#23-obsidian)
24. [Notion (Browser/Desktop)](#24-notion-browserdesktop)
25. [Agent Decision Logic & Fallback Strategies](#25-agent-decision-logic--fallback-strategies)
26. [Universal Automation Patterns](#26-universal-automation-patterns)
27. [Error Recovery Procedures](#27-error-recovery-procedures)

---

## 1. Core Interaction Primitives

These are the building blocks every navigation action is composed of. The agent must always resolve a task into one or more of these primitives.

### 1.1 Mouse Actions
| Action | Method | Notes |
|--------|--------|-------|
| Left Click | `click(x, y)` | Select, activate, press buttons |
| Right Click | `right_click(x, y)` | Context menus |
| Double Click | `double_click(x, y)` | Open files, enter edit mode |
| Click & Drag | `drag(x1,y1, x2,y2)` | Move windows, resize, select text |
| Scroll Up/Down | `scroll(x, y, amount)` | Navigate lists, pages |
| Hover | `hover(x, y)` | Reveal tooltips, dropdown menus |

### 1.2 Keyboard Actions
| Action | Method | Notes |
|--------|--------|-------|
| Type text | `type("text")` | Into focused field |
| Press key | `key("Enter")` | Single keypress |
| Key combo | `hotkey("Ctrl", "C")` | Modifier + key |
| Hold key | `keydown("Shift")` + `key("End")` | Text selection |

### 1.3 Clipboard
```
Copy:   Ctrl+C
Cut:    Ctrl+X
Paste:  Ctrl+V
```
Agent pattern: `read_clipboard()` → process → `set_clipboard(text)` → `Ctrl+V` into target.

### 1.4 UI Element Targeting (Priority Order)
When deciding how to click something, use this priority:
1. **By accessibility name** (button label, ARIA name) — most reliable
2. **By coordinates** (screenshot-based x,y) — fallback
3. **By keyboard shortcut** — preferred when available
4. **By Tab navigation** — last resort for forms

### 1.5 Focus Management
- Always verify the correct window is in focus before typing
- Use `Alt+Tab` to cycle windows
- Use `Win+number` to activate taskbar apps by position
- Use `click(title_bar)` to bring a window to front

---

## 2. Windows OS Navigation

### 2.1 Launching Applications

**Method 1 — Windows Search (Recommended)**
```
Press: Win
Type:  <app name>
Wait:  For search results to populate (300–500ms)
Press: Enter (top result) OR arrow keys to select specific result
```

**Method 2 — Run Dialog**
```
Press: Win+R
Type:  <executable or command>
Press: Enter
```
Common run commands:
| App | Run Command |
|-----|------------|
| Chrome | `chrome` |
| Notepad | `notepad` |
| File Explorer | `explorer` |
| Task Manager | `taskmgr` |
| Calculator | `calc` |
| Settings | `ms-settings:` |
| Control Panel | `control` |
| Registry Editor | `regedit` |
| CMD | `cmd` |
| PowerShell | `powershell` |
| Spotify | `spotify` |
| Outlook | `outlook` |
| Word | `winword` |
| Excel | `excel` |

**Method 3 — Desktop/Taskbar**
```
Double-click desktop shortcut
OR
Single-click pinned taskbar icon
```

**Method 4 — File Path**
```
Win+R → type full path → Enter
Example: C:\Program Files\Spotify\Spotify.exe
```

### 2.2 Window Management
| Action | Shortcut |
|--------|----------|
| Minimize window | `Win+Down` (twice if maximized) |
| Maximize window | `Win+Up` |
| Snap left/right | `Win+Left / Win+Right` |
| Close window | `Alt+F4` |
| Switch windows | `Alt+Tab` |
| Switch same-app windows | `Win+Tab` or `Ctrl+Alt+Tab` |
| Show desktop | `Win+D` |
| Move window | `Alt+Space → M → arrow keys` |
| Resize window | `Alt+Space → S → arrow keys` |

### 2.3 Desktop & Taskbar
| Action | Shortcut |
|--------|----------|
| Open Start Menu | `Win` |
| Open Action Center | `Win+A` |
| Open Notification Center | `Win+N` |
| Open Quick Settings | `Win+A` |
| Lock screen | `Win+L` |
| Open emoji picker | `Win+.` or `Win+;` |
| Screenshot (full) | `Win+PrintScreen` (saves to Pictures\Screenshots) |
| Screenshot (region) | `Win+Shift+S` (opens snipping tool) |
| Screen record | `Win+G` (Xbox Game Bar) |

### 2.4 Virtual Desktops
```
Create new desktop:    Win+Ctrl+D
Close current:         Win+Ctrl+F4
Switch left/right:     Win+Ctrl+Left / Win+Ctrl+Right
View all desktops:     Win+Tab
Move app to desktop:   Win+Tab → right-click window → "Move to" → select desktop
```

---

## 3. File System Operations

### 3.1 File Explorer Navigation
```
Open File Explorer:   Win+E
Address bar focus:    Ctrl+L  (then type path, press Enter)
Search in folder:     Ctrl+F  or Ctrl+E
New folder:           Ctrl+Shift+N
Select all:           Ctrl+A
Copy:                 Ctrl+C
Cut:                  Ctrl+X
Paste:                Ctrl+V
Delete (recycle bin): Delete
Permanent delete:     Shift+Delete
Rename:               F2
Properties:           Alt+Enter
Undo action:          Ctrl+Z
Navigate back:        Alt+Left
Navigate forward:     Alt+Right
Navigate up one level:Alt+Up
```

### 3.2 Common Folder Paths
```
Desktop:          C:\Users\<username>\Desktop
Documents:        C:\Users\<username>\Documents
Downloads:        C:\Users\<username>\Downloads
Pictures:         C:\Users\<username>\Pictures
AppData (hidden): C:\Users\<username>\AppData
System32:         C:\Windows\System32
Program Files:    C:\Program Files
Program Files x86:C:\Program Files (x86)
```
> **Agent Tip:** Use `%USERPROFILE%`, `%APPDATA%`, `%TEMP%` environment variables in paths for portability.

### 3.3 File Search Strategy
1. Open File Explorer (`Win+E`)
2. Navigate to root folder to search in (e.g., `C:\`)
3. Press `Ctrl+F` → type filename or partial name
4. Wait for results to populate
5. **For content search:** Use Windows Search (`Win → type term → click "Documents" filter`)
6. **For advanced search:** `Win+S` → type term → filter by date/type using filter bar

### 3.4 Command-Line File Operations
```powershell
# List files
dir C:\path\to\folder

# Create folder
mkdir "C:\path\new_folder"

# Copy file
copy "source.txt" "C:\destination\"

# Move file
move "source.txt" "C:\destination\"

# Delete file
del "filename.txt"

# Search for file by name
dir /s /b "filename.txt"

# Search file content (PowerShell)
Select-String -Path "C:\folder\*" -Pattern "search term"
```

---

## 4. Google Chrome

### 4.1 Launching
```
Win → type "chrome" → Enter
OR Win+R → chrome → Enter
```

### 4.2 Navigation
| Action | Shortcut |
|--------|----------|
| Open URL / focus address bar | `Ctrl+L` or `F6` or `Alt+D` |
| New tab | `Ctrl+T` |
| Close tab | `Ctrl+W` |
| Reopen closed tab | `Ctrl+Shift+T` |
| Next tab | `Ctrl+Tab` |
| Previous tab | `Ctrl+Shift+Tab` |
| Jump to tab N | `Ctrl+1` through `Ctrl+8` |
| Last tab | `Ctrl+9` |
| New window | `Ctrl+N` |
| New incognito window | `Ctrl+Shift+N` |
| Back | `Alt+Left` |
| Forward | `Alt+Right` |
| Reload page | `F5` or `Ctrl+R` |
| Hard reload (no cache) | `Ctrl+Shift+R` |
| Stop loading | `Esc` |
| Scroll down | `Space` or `PgDn` |
| Scroll up | `Shift+Space` or `PgUp` |
| Go to top of page | `Ctrl+Home` |
| Go to bottom | `Ctrl+End` |
| Find on page | `Ctrl+F` |
| Find next | `F3` or `Enter` |
| Zoom in/out | `Ctrl++` / `Ctrl+-` |
| Reset zoom | `Ctrl+0` |
| Full screen | `F11` |
| Bookmark page | `Ctrl+D` |
| Open bookmarks | `Ctrl+Shift+B` (toggle bar) |
| History | `Ctrl+H` |
| Downloads | `Ctrl+J` |
| Extensions | Navigate to `chrome://extensions` |
| Settings | `Alt+F → S` or navigate to `chrome://settings` |
| Developer Tools | `F12` or `Ctrl+Shift+I` |
| View source | `Ctrl+U` |
| Print | `Ctrl+P` |

### 4.3 URL Bar Search Patterns
```
Direct URL:        type full URL → Enter
Google search:     type query → Enter
Specific site:     site:reddit.com query → Enter
Incognito search:  Ctrl+Shift+N → then search
```

### 4.4 Tab Management via Keyboard
```
Pin tab:           Right-click tab → "Pin"
Move tab to window:Right-click tab → "Move to window"
Duplicate tab:     Right-click tab → "Duplicate" OR Alt+D → Enter
Mute tab:          Right-click tab → "Mute site"
```

### 4.5 Chrome for Agent Tasks
```python
# Agent pattern for web research:
1. Ctrl+T                    # New tab
2. Ctrl+L                    # Focus address bar
3. type("search query")      # Type query
4. Enter                     # Go
5. Wait for page load        # 500-2000ms depending on connection
6. Ctrl+F → type term        # Find specific content on page
7. Ctrl+A → Ctrl+C           # Copy all text (then process)
```

---

## 5. Microsoft Edge

### 5.1 Launching
```
Win → type "edge" → Enter
```
Most Chrome shortcuts work identically. Additional Edge shortcuts:
| Action | Shortcut |
|--------|----------|
| Sidebar | `Ctrl+Shift+/` |
| Collections | `Ctrl+Shift+Y` |
| Immersive reader | `F9` |
| Web capture | `Ctrl+Shift+S` |
| Vertical tabs | Click the vertical tab icon top-left |
| Copilot sidebar | `Ctrl+Shift+.` |

---

## 6. Firefox

### 6.1 Launching
```
Win → type "firefox" → Enter
```
Core shortcuts are identical to Chrome. Additional:
| Action | Shortcut |
|--------|----------|
| Reader mode | `F9` |
| Picture-in-picture | Right-click video → PiP |
| Containers (if installed) | `Ctrl+.` |
| Sync | Open menu (Alt) → Sync |

---

## 7. Spotify

### 7.1 Launching
```
Win → type "spotify" → Enter
```

### 7.2 Playback Controls
| Action | Shortcut |
|--------|----------|
| Play / Pause | `Space` |
| Next track | `Ctrl+Right` |
| Previous track | `Ctrl+Left` |
| Volume up | `Ctrl+Up` |
| Volume down | `Ctrl+Down` |
| Mute | `Ctrl+Shift+Down` |
| Shuffle on/off | `Ctrl+S` |
| Repeat | `Ctrl+R` |
| Like song | `Alt+Shift+B` |
| Seek forward 15s | `Shift+Right` (in some versions) |

### 7.3 Navigation
| Action | Shortcut |
|--------|----------|
| Search | `Ctrl+L` or `Ctrl+K` |
| Home | `Alt+Home` |
| Back | `Alt+Left` |
| Forward | `Alt+Right` |
| Your Library | Click "Your Library" in left sidebar |
| Now Playing | `Ctrl+Shift+N` or click bottom bar |
| Queue | `Ctrl+Q` |
| Mini player | `Ctrl+Shift+Down` |

### 7.4 Search Patterns
```
1. Press Ctrl+L or click search bar
2. Type: artist name / song name / album / playlist name
3. Wait ~300ms for results
4. Results categories: Top result, Songs, Artists, Albums, Playlists, Podcasts
5. Press Enter for top result OR click desired category
6. To play immediately: press Enter on a song OR double-click
```

### 7.5 Playlist Management
```
Create playlist:      Click "+" next to "Your Library" → New Playlist
Add song to playlist: Right-click song → "Add to playlist" → select playlist
Remove from playlist: Right-click song in playlist → "Remove from this playlist"
Follow playlist:      Open playlist → click heart/Follow button
```

---

## 8. VS Code / Windsurf

> Windsurf is built on VS Code. All VS Code shortcuts apply.

### 8.1 Launching
```
Win → type "windsurf" or "code" → Enter
OR open folder: right-click folder → "Open with Windsurf/Code"
```

### 8.2 Core Navigation
| Action | Shortcut |
|--------|----------|
| Command Palette | `Ctrl+Shift+P` |
| Quick Open file | `Ctrl+P` |
| New file | `Ctrl+N` |
| Open file | `Ctrl+O` |
| Save file | `Ctrl+S` |
| Save all | `Ctrl+K → S` |
| Save As | `Ctrl+Shift+S` |
| Close file | `Ctrl+W` |
| Close all | `Ctrl+K → Ctrl+W` |
| Split editor | `Ctrl+\` |
| Toggle sidebar | `Ctrl+B` |
| Toggle terminal | `Ctrl+\`` |
| New terminal | `Ctrl+Shift+\`` |
| Explorer panel | `Ctrl+Shift+E` |
| Search panel | `Ctrl+Shift+F` |
| Source control | `Ctrl+Shift+G` |
| Extensions | `Ctrl+Shift+X` |
| Settings | `Ctrl+,` |
| Keyboard shortcuts | `Ctrl+K → Ctrl+S` |

### 8.3 Editing
| Action | Shortcut |
|--------|----------|
| Find | `Ctrl+F` |
| Find & Replace | `Ctrl+H` |
| Go to line | `Ctrl+G` |
| Go to definition | `F12` |
| Peek definition | `Alt+F12` |
| Rename symbol | `F2` |
| Format document | `Shift+Alt+F` |
| Comment/uncomment | `Ctrl+/` |
| Duplicate line | `Shift+Alt+Down` |
| Move line up/down | `Alt+Up/Down` |
| Delete line | `Ctrl+Shift+K` |
| Multi-cursor (mouse) | `Alt+Click` |
| Multi-cursor (column) | `Ctrl+Alt+Down` |
| Select all occurrences | `Ctrl+Shift+L` |
| Indent | `Tab` |
| Outdent | `Shift+Tab` |
| Fold region | `Ctrl+Shift+[` |
| Unfold region | `Ctrl+Shift+]` |

### 8.4 Windsurf-Specific (AI Features)
```
Open Cascade (AI panel): Ctrl+Shift+L  OR click Cascade icon in sidebar
New AI conversation:      Ctrl+Shift+L → click "New"
Inline AI edit:           Ctrl+I  (opens inline AI command bar)
Accept AI suggestion:     Tab
Reject AI suggestion:     Esc
Toggle Copilot:           Click Copilot icon in status bar
```

### 8.5 Terminal Commands (Inside VS Code/Windsurf)
```
Ctrl+`           → Open integrated terminal
cd path          → Navigate
npm install      → Install dependencies
npm run dev      → Start dev server
python script.py → Run Python script
git status       → Check git status
git add .        → Stage all
git commit -m "" → Commit
git push         → Push
```

---

## 9. Windows Terminal / PowerShell / CMD

### 9.1 Launching
```
Windows Terminal: Win → "terminal" → Enter
PowerShell:       Win → "powershell" → Enter (Shift+Enter for admin)
CMD:              Win+R → cmd → Enter (Ctrl+Shift+Enter for admin)
Admin Terminal:   Right-click Start → "Windows Terminal (Admin)"
```

### 9.2 Windows Terminal Navigation
| Action | Shortcut |
|--------|----------|
| New tab | `Ctrl+T` |
| Close tab | `Ctrl+W` |
| New PowerShell tab | `Ctrl+Shift+1` |
| New CMD tab | `Ctrl+Shift+2` |
| Split pane vertically | `Alt+Shift+Plus` |
| Split pane horizontally | `Alt+Shift+Minus` |
| Move between panes | `Alt+Arrow keys` |
| Zoom pane | `Ctrl+Shift+Plus/Minus` |
| Find | `Ctrl+Shift+F` |
| Settings | `Ctrl+,` |

### 9.3 Essential PowerShell Commands
```powershell
# Navigation
cd "C:\path"          # Change directory
cd ..                 # Up one level
ls / dir              # List contents
pwd                   # Current path
pushd / popd          # Stack-based navigation

# Files
New-Item -Name "file.txt" -ItemType File
New-Item -Name "folder" -ItemType Directory
Copy-Item "src" "dst"
Move-Item "src" "dst"
Remove-Item "file" -Recurse -Force
Get-Content "file.txt"
Set-Content "file.txt" "text"
Add-Content "file.txt" "appended text"

# Processes
Get-Process
Stop-Process -Name "chrome"
Start-Process "notepad"

# Network
Test-NetConnection google.com
ipconfig
ping google.com
Invoke-WebRequest -Uri "https://url" -OutFile "file"

# Search
Get-ChildItem -Recurse -Filter "*.txt"
Select-String -Path "." -Pattern "keyword" -Recurse

# Scripts
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser  # Allow scripts
.\script.ps1                                          # Run script
```

---

## 10. Microsoft Word

### 10.1 Launching
```
Win → "word" → Enter
Open document: Win+R → winword "C:\path\file.docx"
```

### 10.2 Core Shortcuts
| Action | Shortcut |
|--------|----------|
| New document | `Ctrl+N` |
| Open document | `Ctrl+O` |
| Save | `Ctrl+S` |
| Save As | `F12` |
| Print | `Ctrl+P` |
| Undo / Redo | `Ctrl+Z / Ctrl+Y` |
| Find | `Ctrl+F` |
| Find & Replace | `Ctrl+H` |
| Go to | `Ctrl+G` |
| Select All | `Ctrl+A` |
| Bold / Italic / Underline | `Ctrl+B / I / U` |
| Font size up/down | `Ctrl+Shift+> / <` |
| Align Left/Center/Right | `Ctrl+L / E / R` |
| Justify | `Ctrl+J` |
| Bullets | `Ctrl+Shift+L` |
| Increase/Decrease Indent | `Tab / Shift+Tab` |
| Spelling check | `F7` |
| Word count | `Ctrl+Shift+G` |
| Insert page break | `Ctrl+Enter` |
| Heading 1/2/3 | `Ctrl+Alt+1/2/3` |
| Normal text | `Ctrl+Alt+N` |
| Zoom | `Alt+W → Q` → type percentage |

### 10.3 Ribbon Navigation (Keyboard)
```
Alt → shows key tips on ribbon
Alt+H → Home tab
Alt+N → Insert tab
Alt+P → Layout tab (Page Layout)
Alt+M → References tab (Mailings)
Alt+R → Review tab
Alt+W → View tab
```

---

## 11. Microsoft Excel

### 11.1 Launching
```
Win → "excel" → Enter
```

### 11.2 Navigation
| Action | Shortcut |
|--------|----------|
| Move cell | `Arrow keys` |
| Jump to edge of data | `Ctrl+Arrow` |
| Go to A1 | `Ctrl+Home` |
| Go to last used cell | `Ctrl+End` |
| Go to specific cell | `Ctrl+G` or `F5` → type reference |
| Select entire row | `Shift+Space` |
| Select entire column | `Ctrl+Space` |
| Select to end | `Ctrl+Shift+End` |
| Name Box (cell reference) | `Alt+Enter` in Name Box |
| New worksheet | `Shift+F11` |
| Next sheet | `Ctrl+PgDn` |
| Previous sheet | `Ctrl+PgUp` |
| Enter edit mode | `F2` |
| Accept and move down | `Enter` |
| Accept and move right | `Tab` |

### 11.3 Data & Formulas
| Action | Shortcut |
|--------|----------|
| Sum formula | `Alt+=` |
| AutoFill down | `Ctrl+D` |
| AutoFill right | `Ctrl+R` |
| Format cells | `Ctrl+1` |
| Format as number | `Ctrl+Shift+1` |
| Format as date | `Ctrl+Shift+3` |
| Format as currency | `Ctrl+Shift+4` |
| Filter | `Ctrl+Shift+L` |
| Find | `Ctrl+F` |
| Replace | `Ctrl+H` |
| Sort ascending | `Alt+A → S+A` |

---

## 12. Microsoft Outlook

### 12.1 Launching
```
Win → "outlook" → Enter
```

### 12.2 Mail Navigation
| Action | Shortcut |
|--------|----------|
| New email | `Ctrl+N` |
| New email (any context) | `Ctrl+Shift+M` |
| Reply | `Ctrl+R` |
| Reply All | `Ctrl+Shift+R` |
| Forward | `Ctrl+F` |
| Send email | `Ctrl+Enter` |
| Save draft | `Ctrl+S` |
| Delete email | `Delete` |
| Mark as read/unread | `Ctrl+Q / Ctrl+U` |
| Search | `Ctrl+E` or `F3` |
| Switch to Mail | `Ctrl+1` |
| Switch to Calendar | `Ctrl+2` |
| Switch to Contacts | `Ctrl+3` |
| Switch to Tasks | `Ctrl+4` |
| Flag email | `Insert` |
| Open email | `Enter` |
| Next/Previous email | `Up/Down arrow` in list |
| Print email | `Ctrl+P` |

### 12.3 Calendar Navigation
| Action | Shortcut |
|--------|----------|
| New appointment | `Ctrl+N` |
| New meeting request | `Ctrl+Shift+Q` |
| Day view | `Ctrl+Alt+1` |
| Week view | `Ctrl+Alt+2` |
| Month view | `Ctrl+Alt+3` |
| Today | `Ctrl+T` |
| Next/Previous period | `Alt+Right / Alt+Left` |

---

## 13. Notepad / Notepad++

### 13.1 Notepad
```
Launch: Win+R → notepad → Enter
        OR Win → "notepad" → Enter
```
| Action | Shortcut |
|--------|----------|
| Find | `Ctrl+F` |
| Find Next | `F3` |
| Replace | `Ctrl+H` |
| Go to line | `Ctrl+G` |
| Word wrap toggle | `Alt+W → W` (Format menu) |
| Insert time/date | `F5` |

### 13.2 Notepad++
```
Launch: Win → "notepad++" → Enter
```
| Action | Shortcut |
|--------|----------|
| New tab | `Ctrl+N` |
| Open file | `Ctrl+O` |
| Close tab | `Ctrl+W` |
| Find | `Ctrl+F` |
| Find & Replace | `Ctrl+H` |
| Column mode select | `Alt+drag` |
| Duplicate line | `Ctrl+D` |
| Delete line | `Ctrl+Shift+L` |
| Toggle comment | `Ctrl+Q` |
| Launch in browser | `Alt+Shift+V` (for HTML) |
| Run script | `F5` |
| Switch syntax highlight | `Alt+L` |
| Multi-select (next) | `Ctrl+Alt+D` |

---

## 14. Task Manager

### 14.1 Launching
```
Ctrl+Shift+Esc     (direct launch — fastest)
Ctrl+Alt+Delete → Task Manager
Right-click taskbar → Task Manager
Win+R → taskmgr
```

### 14.2 Navigation
| Action | Shortcut |
|--------|----------|
| Switch tabs | `Ctrl+Tab` |
| End task (selected) | `Alt+E` or Delete |
| Run new task | `Alt+F → N` |
| Toggle always on top | `Alt+V → A` |
| Expand process tree | `+` key on selected row |
| Collapse | `-` key |

### 14.3 Tabs Overview
- **Processes:** Running apps + background processes, CPU/memory usage
- **Performance:** System resource graphs
- **App History:** Historical usage per app
- **Startup:** Programs that run on boot — disable here
- **Users:** Active user sessions
- **Details:** Low-level process info (PID, etc.)
- **Services:** Windows services management

### 14.4 Agent Kill Pattern
```
1. Ctrl+Shift+Esc
2. Click "Processes" tab
3. Find target process (by name or sort by CPU/Memory)
4. Click to select it
5. Click "End Task" (bottom right) OR press Delete
6. Confirm if prompted
```

---

## 15. Settings App

### 15.1 Launching
```
Win+I            (direct)
Win → "settings" → Enter
Start menu → gear icon
```

### 15.2 Navigation
```
All sections are in left sidebar:
- System          (display, sound, notifications, power)
- Bluetooth       (devices)
- Network         (WiFi, Ethernet, VPN)
- Personalization (backgrounds, themes, start menu)
- Apps            (installed apps, defaults)
- Accounts        (user accounts, sign-in)
- Time & Language
- Gaming
- Accessibility
- Privacy & Security
- Windows Update
```

### 15.3 Direct Settings Links (ms-settings: protocol)
```powershell
# Use Win+R → paste these → Enter
ms-settings:display
ms-settings:sound
ms-settings:network-wifi
ms-settings:bluetooth
ms-settings:appsfeatures
ms-settings:defaultapps
ms-settings:windowsupdate
ms-settings:privacy
ms-settings:accounts
ms-settings:power-sleep
ms-settings:nightlight
ms-settings:taskbar
```

---

## 16. Control Panel

### 16.1 Launching
```
Win+R → control → Enter
Win → "control panel" → Enter
```

### 16.2 Key Sections
| Section | What it controls |
|---------|-----------------|
| Programs and Features | Uninstall programs |
| Device Manager | Hardware drivers |
| Network and Sharing Center | Advanced network settings |
| System | System info, computer name |
| User Accounts | Local account management |
| Windows Defender Firewall | Firewall rules |
| Fonts | Installed fonts |
| Credential Manager | Saved passwords/creds |

### 16.3 Direct Control Panel Commands
```
Win+R → appwiz.cpl       # Programs & Features (uninstall)
Win+R → devmgmt.msc      # Device Manager
Win+R → ncpa.cpl         # Network Connections
Win+R → sysdm.cpl        # System Properties
Win+R → firewall.cpl     # Windows Firewall
Win+R → inetcpl.cpl      # Internet Options
Win+R → msconfig         # System Configuration
Win+R → services.msc     # Windows Services
Win+R → eventvwr         # Event Viewer
Win+R → diskmgmt.msc     # Disk Management
Win+R → compmgmt.msc     # Computer Management
```

---

## 17. Windows Search

### 17.1 Types of Search
| Search Type | How |
|-------------|-----|
| App search | `Win` → type app name |
| File search | `Win` → type filename → click "Documents" or "Folders" filter |
| Web search | `Win` → type query → click "Web" results |
| Settings search | `Win` → type setting name → click "Settings" result |
| Email search | `Win` → type → filter by "Email" |

### 17.2 Search Filters (in Start Menu)
After pressing `Win` and typing, click tabs:
- **All** — combined results
- **Apps** — installed applications
- **Documents** — files
- **Web** — Bing results (opens Edge)
- **More** → choose specific category

### 17.3 Cortana / Search Settings
```
Win+S → opens dedicated search panel
Win+Q → same as Win+S in newer Windows
```

### 17.4 Advanced File Search (File Explorer)
```
1. Win+E → navigate to target folder
2. Ctrl+F → search box focused
3. Type query
4. Refine with: Date modified, Kind, Size (toolbar appears after searching)
5. Add: kind:=folder (search only folders)
         ext:.pdf (search by extension)
         date:>2024-01-01 (by date)
         size:>10MB (by size)
```

---

## 18. Discord

### 18.1 Launching
```
Win → "discord" → Enter
```

### 18.2 Navigation
| Action | Shortcut |
|--------|----------|
| Quick Switcher (jump to server/DM/channel) | `Ctrl+K` |
| Mark server as read | `Escape` (in server view) |
| Unread navigation up/down | `Alt+Up / Alt+Down` |
| Upload file | `Ctrl+Shift+U` |
| Create DM | `Ctrl+Shift+T` |
| New line in message | `Shift+Enter` |
| Send message | `Enter` |
| Edit last message | `Up arrow` (when input empty) |
| Delete message | Hover → three dots → Delete |
| React with emoji | Hover → emoji icon |
| Search messages | `Ctrl+F` |
| Toggle mute | `Ctrl+Shift+M` |
| Toggle deafen | `Ctrl+Shift+D` |
| Open settings | `Ctrl+,` |
| Switch server (by position) | `Ctrl+Alt+Up/Down` |
| Toggle voice (Push to Talk) | configured key |
| Mention someone | `@username` in message |
| Create channel reference | `#channelname` |

### 18.3 Agent Navigation Pattern (Find a message)
```
1. Ctrl+K → type server or channel name → Enter
2. Ctrl+F → type search term
3. Filter: from:username / in:#channel / before:date / during:date
4. Press Enter to jump to message
```

---

## 19. Slack

### 19.1 Launching
```
Win → "slack" → Enter
```

### 19.2 Navigation
| Action | Shortcut |
|--------|----------|
| Jump to any channel/DM | `Ctrl+K` |
| Search | `Ctrl+F` (in channel) or `Ctrl+G` (global) |
| New message / DM | `Ctrl+N` |
| Mark as read | `Esc` |
| Next unread | `Alt+Shift+↑/↓` |
| Switch workspace | `Ctrl+Shift+[1-9]` |
| Toggle sidebar | `Ctrl+Shift+D` |
| Upload file | `Ctrl+U` or `+` button |
| Format bold | `Ctrl+B` |
| Format italic | `Ctrl+I` |
| Format code block | `Ctrl+Shift+C` |
| React to message | Hover → emoji icon → pick |
| Thread reply | Hover → "Reply in thread" |
| Pin message | Hover → `...` → Pin |
| Set status | Click profile → Set Status |
| Preferences | `Ctrl+,` |

---

## 20. Zoom

### 20.1 Launching
```
Win → "zoom" → Enter
```

### 20.2 Meeting Controls
| Action | Shortcut |
|--------|----------|
| Mute/Unmute | `Alt+A` |
| Start/Stop video | `Alt+V` |
| Share screen | `Alt+Shift+S` |
| Stop sharing | `Alt+Shift+S` (again) |
| Pause screen share | `Alt+T` |
| Open participants | `Alt+U` |
| Open chat | `Alt+H` |
| Raise/Lower hand | `Alt+Y` |
| Reactions | `Alt+Z` (for reaction panel) |
| Record | `Alt+R` |
| Leave/End meeting | `Alt+Q` |
| Toggle gallery/speaker view | `Alt+F2` |
| Push to talk (while muted) | `Space` (hold) |
| Spotlight participant | Host: right-click video → Spotlight |
| Virtual background | `Alt+N` → Video settings → Virtual BG |

---

## 21. VLC Media Player

### 21.1 Launching
```
Win → "vlc" → Enter
Open file: drag file onto VLC OR Ctrl+O
```

### 21.2 Playback Controls
| Action | Shortcut |
|--------|----------|
| Play / Pause | `Space` |
| Stop | `S` |
| Skip forward 10s | `Alt+Right` |
| Skip back 10s | `Alt+Left` |
| Skip forward 1min | `Ctrl+Right` |
| Skip back 1min | `Ctrl+Left` |
| Skip forward 5min | `Ctrl+Alt+Right` |
| Skip back 5min | `Ctrl+Alt+Left` |
| Volume up | `Ctrl+Up` |
| Volume down | `Ctrl+Down` |
| Mute | `M` |
| Fullscreen toggle | `F` |
| Always on top | `T` |
| Next track | `N` |
| Previous track | `P` |
| Subtitles toggle | `V` |
| Audio track switch | `B` |
| Playback speed up | `]` |
| Playback speed down | `[` |
| Normal speed | `=` |
| Take snapshot | `Shift+S` |
| Loop one | `L` |

---

## 22. Steam

### 22.1 Launching
```
Win → "steam" → Enter
```

### 22.2 Navigation
| Action | Shortcut |
|--------|----------|
| Open Store | Click "Store" tab |
| Open Library | Click "Library" tab |
| Search Library | `Ctrl+F` or click search bar |
| Install game | Click game → Install |
| Launch game | Double-click game in library |
| View game properties | Right-click game → Properties |
| Steam overlay (in-game) | `Shift+Tab` |
| Overlay screenshot | `F12` |
| Open Big Picture | `Shift+Tab` → Big Picture button |
| Friends list | Click "Friends & Chat" bottom right |
| Settings | `Steam menu → Settings` |
| Downloads | `Library → Downloads` |
| Update all | `Library → right-click game → Properties → Updates` |

### 22.3 Finding a Game to Install
```
1. Click "Store" tab
2. Use search bar (top right) → type game name
3. Click game page
4. Click "Add to Cart" or "Install" (if free/owned)
5. Complete purchase if required
6. Library → Find game → Click "Install"
7. Choose drive, check disk space, click "Install"
8. Game downloads → appears in library when done
```

---

## 23. Obsidian

### 23.1 Launching
```
Win → "obsidian" → Enter
```

### 23.2 Navigation
| Action | Shortcut |
|--------|----------|
| Quick switcher (open note) | `Ctrl+O` |
| Command palette | `Ctrl+P` |
| New note | `Ctrl+N` |
| Search vault | `Ctrl+Shift+F` |
| Toggle left sidebar | `Ctrl+B` |
| Toggle right sidebar | `Ctrl+Shift+B` |
| Open graph view | `Ctrl+G` |
| Follow link | `Ctrl+Enter` on `[[link]]` |
| Back | `Alt+Left` |
| Forward | `Alt+Right` |
| Split vertically | `Ctrl+\` |
| Close tab | `Ctrl+W` |
| Toggle edit/preview | `Ctrl+E` |
| Bold | `Ctrl+B` |
| Italic | `Ctrl+I` |
| Insert link | `Ctrl+K` |
| Insert internal link | `[[` then type note name |
| Toggle checkboxes | `Ctrl+L` |
| Indent list | `Tab` |
| Outdent list | `Shift+Tab` |

### 23.3 Agent Workflow (Creating a Note)
```
1. Ctrl+N               → New note
2. Type note title → Enter
3. Type content using Markdown
4. [[link name]]        → Link to other note
5. Ctrl+S               → Save (auto-saves)
6. Ctrl+P → "Move file" → Move to specific folder
```

---

## 24. Notion (Browser/Desktop)

### 24.1 Launching
```
Browser: Ctrl+T → type notion.so → Enter → sign in
Desktop: Win → "notion" → Enter
```

### 24.2 Navigation
| Action | Shortcut |
|--------|----------|
| Quick find (search) | `Ctrl+P` or `Ctrl+K` |
| New page | `Ctrl+N` (or click + in sidebar) |
| Bold | `Ctrl+B` |
| Italic | `Ctrl+I` |
| Underline | `Ctrl+U` |
| Strikethrough | `Ctrl+Shift+S` |
| Inline code | `Ctrl+E` |
| Insert link | `Ctrl+K` |
| Undo / Redo | `Ctrl+Z / Ctrl+Shift+Z` |
| Add block below | `Enter` |
| Convert to header | `/h1` or `/h2` or `/h3` |
| Toggle block type | `/` → type block name |
| Duplicate block | `Ctrl+D` |
| Delete block | `Backspace` on empty block OR select + Delete |
| Select block | `Esc` (then arrows to navigate) |
| Move block | `Ctrl+Shift+Up/Down` |
| Expand/collapse toggle | `Ctrl+Enter` on toggle block |
| Comment | `Ctrl+Shift+M` |
| Full page view | Click title → expand |

### 24.3 Slash Commands (/ Menu)
```
/text          → plain text
/h1, /h2, /h3 → headings
/todo          → checkbox
/bullet        → bulleted list
/numbered      → numbered list
/toggle        → collapsible
/code          → code block
/quote         → blockquote
/divider       → horizontal line
/table         → simple table
/database      → full database
/callout       → callout block
/image         → image upload
/file          → file upload
/date          → date mention
/page          → new sub-page
```

---

## 25. Agent Decision Logic & Fallback Strategies

### 25.1 App Launch Decision Tree
```
GOAL: Open <AppName>
│
├─ Is it pinned to taskbar?
│   └─ YES → Win+[position number] or click icon
│
├─ Does it have a desktop shortcut?
│   └─ YES → Double-click shortcut
│
├─ Try Win → type name → Enter
│   └─ If appears in results → Enter
│
├─ Try Win+R → type run command → Enter
│   └─ If known run command exists
│
└─ Navigate to install path
    └─ Win+E → navigate to C:\Program Files\ → find folder → run .exe
```

### 25.2 UI Element Not Found Strategy
```
Element not visible on screen?
│
├─ Scroll down/up (Space, PgDn, scroll wheel)
├─ Resize window (it may be off-screen)
├─ Try keyboard shortcut instead of clicking
├─ Check if it's behind another window (Alt+Tab)
├─ Check if menu/panel is collapsed (look for > or chevrons)
├─ Try Ctrl+F to find text on screen
└─ Restart the app (Alt+F4 → relaunch)
```

### 25.3 Action Confirmation Strategy
Before executing irreversible actions, agent should:
1. **Check for confirmation dialogs** — wait 300ms after triggering action
2. **Look for "Are you sure?" prompts** — press Enter for Yes, Esc for No
3. **File deletions** — verify path before Shift+Delete
4. **Form submissions** — re-read fields before Ctrl+Enter
5. **Downloads** — confirm save location before starting

### 25.4 When a Window Freezes
```
1. Wait 10 seconds (may be loading)
2. Click title bar once (to focus)
3. If still unresponsive:
   a. Ctrl+Shift+Esc → find process → End Task
   b. Win+R → taskkill /F /IM appname.exe → Enter
4. Relaunch application
5. Check for crash reports / autosaves
```

### 25.5 Pop-up / Dialog Handling
```
Confirmation dialogs:
  - Enter        = default/primary button (usually "OK" / "Yes")
  - Esc          = cancel / close
  - Tab          = cycle between buttons
  - Spacebar     = activate focused button
  - Alt+[letter] = keyboard shortcut (underlined letter in button label)

File overwrite dialog:
  - "Replace" → confirm overwrite
  - "Skip"    → keep existing
  - "Rename"  → auto-rename new file
  - Usually arrows + Enter to choose

UAC (Admin prompt):
  - Alt+Y = Yes
  - Alt+N = No
  - Enter = activates focused button
```

---

## 26. Universal Automation Patterns

### 26.1 Copy Text from Any App
```
1. Click in text area
2. Ctrl+A (select all) OR click+drag to select range
3. Ctrl+C (copy)
4. Process clipboard: read_clipboard()
```

### 26.2 Paste Text into Any Field
```
1. Click target text field
2. Ctrl+A (clear existing if needed)
3. set_clipboard("text to paste")
4. Ctrl+V
```

### 26.3 Fill a Form
```
1. Tab through fields (or click each)
2. For each field:
   a. Click field (or Tab to it)
   b. Ctrl+A (clear)
   c. Type value
3. Tab to submit button → Enter
   OR click submit button directly
```

### 26.4 Web Research Pattern
```
1. Open Chrome (Ctrl+T if already open)
2. Ctrl+L → type search query → Enter
3. Wait for results (~500ms)
4. Click most relevant result
5. Wait for page load (~1-2s)
6. Ctrl+F → search for specific info
7. Extract: Ctrl+A → Ctrl+C → process clipboard
   OR: highlight specific section → Ctrl+C
```

### 26.5 Screenshot and Analyze Pattern
```
1. Navigate to target app/screen
2. Win+Shift+S → drag to select region
3. Screenshot copied to clipboard
4. Paste into: Paint (Ctrl+V) → save → analyze
   OR: paste directly into Claude/AI prompt
```

### 26.6 Run a Script and Handle Output
```
1. Win → "terminal" → Enter (or Ctrl+` in VS Code)
2. cd to script directory
3. Run: python script.py OR node script.js
4. Wait for output
5. If error: read error message → fix → re-run
6. If success: copy output (Ctrl+Shift+C in terminal)
```

### 26.7 Save a Webpage as PDF
```
Chrome/Edge:
1. Ctrl+P
2. Destination: "Save as PDF"
3. Set options (pages, margins)
4. Click "Save"
5. Choose location → Save
```

### 26.8 Batch File Operations
```powershell
# Rename all files in folder
Get-ChildItem "C:\folder\*.txt" | Rename-Item -NewName { $_.Name -replace "old","new" }

# Move files matching pattern
Get-ChildItem "C:\source\*.pdf" | Move-Item -Destination "C:\dest\"

# Delete files older than 30 days
Get-ChildItem "C:\folder" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item
```

---

## 27. Error Recovery Procedures

### 27.1 Common Error States & Fixes

| Error | Symptom | Fix |
|-------|---------|-----|
| App frozen | Window not responding | `Ctrl+Shift+Esc` → End Task → Relaunch |
| Shortcut not working | Keypress has no effect | Check app has focus, try clicking window first |
| File locked | "File in use" error | Close other apps using the file, check Task Manager |
| Permission denied | Access error on file/folder | Right-click → Run as administrator |
| Window off-screen | App open but not visible | `Win+Shift+Arrow` (moves window to screen) OR `Alt+Space → M → arrow keys` |
| Clipboard empty | Paste produces nothing | Re-copy the content, try `Ctrl+C` again |
| Search not finding app | App installed but not in search | Navigate manually to `C:\Program Files\` |
| Dialog blocking | Popup preventing main app use | Look for it in `Alt+Tab` → handle dialog first |
| Browser page won't load | Blank/error page | `Ctrl+Shift+R` (hard reload) → check internet |
| Text not typing into field | Typing goes nowhere | Click directly on input field, check field isn't read-only |

### 27.2 System-Level Recovery
```
Explorer crashed (no taskbar):
  Ctrl+Shift+Esc → File → Run new task → explorer.exe → Enter

Start menu not working:
  Ctrl+Alt+Delete → Task Manager → Restart Windows Explorer
  OR PowerShell: Get-Process explorer | Stop-Process; Start-Process explorer

Unresponsive Windows:
  Ctrl+Alt+Delete → options appear
  → Lock / Switch User / Sign Out / Task Manager / Restart / Shut Down

Network not working:
  Win+I → Network → Troubleshoot
  OR PowerShell: netsh winsock reset → restart
```

### 27.3 App-Specific Recovery

**Chrome:** If tabs crash → `chrome://restart` in address bar  
**VS Code/Windsurf:** If extension causes crash → launch with `code --disable-extensions`  
**Spotify:** If audio glitches → Settings → Log out → Log back in  
**Discord:** If stuck connecting → `Ctrl+R` (reloads client)  
**Steam:** If update stuck → Steam → Settings → Downloads → Clear cache  

---

## APPENDIX A: Key Reference Card

### Most Important Global Shortcuts
```
Win             → Start / Search
Win+E           → File Explorer
Win+I           → Settings
Win+L           → Lock screen
Win+D           → Show/hide desktop
Win+Shift+S     → Screenshot region
Win+R           → Run dialog
Win+Tab         → Task view
Alt+Tab         → Switch windows
Alt+F4          → Close window/app
Ctrl+Shift+Esc  → Task Manager
Ctrl+Z          → Undo (most apps)
Ctrl+C/X/V      → Copy/Cut/Paste
Ctrl+A          → Select all
Ctrl+F          → Find (most apps)
Ctrl+P          → Print (most apps)
Ctrl+S          → Save (most apps)
F5              → Refresh
Esc             → Cancel / Close dialog
Tab             → Next field / element
Shift+Tab       → Previous field
Enter           → Confirm / Activate
Space           → Play/Pause (media) / Activate button
```

---

## APPENDIX B: Finding Any App on Windows

### Step-by-Step for Unknown App Location
```
1. Win → type app name → check if appears
2. If not found:
   a. Check desktop for shortcut
   b. Check taskbar (pinned or running)
   c. Open File Explorer → C:\Program Files\ → look for app folder
   d. Open File Explorer → C:\Program Files (x86)\ → look for app folder
   e. Win → "Apps & features" → search for app name
   f. Check: C:\Users\<username>\AppData\Local\
   g. Check: C:\Users\<username>\AppData\Roaming\
3. If found in folder: double-click .exe to launch
4. To pin for future: right-click .exe → Pin to Start / Pin to Taskbar
```

### Install a New App
```
Method 1 — Microsoft Store:
  Win → "store" → Enter → search app → Install

Method 2 — Direct download:
  Chrome → search "<app name> download" → official website → Download
  → Run installer (.exe or .msi) → follow wizard
  → Usually: Next → Next → Install → Finish

Method 3 — Winget (package manager):
  PowerShell: winget install <appname>
  Examples:
    winget install Google.Chrome
    winget install Spotify.Spotify
    winget install Discord.Discord
    winget install Microsoft.VisualStudioCode
    winget install Notepad++.Notepad++
    winget install VideoLAN.VLC
    winget install Obsidian.Obsidian
```

---

*Last updated: 2026 | For use with Personal AI Operating Assistant (Whisper + Ollama + Windsurf)*
