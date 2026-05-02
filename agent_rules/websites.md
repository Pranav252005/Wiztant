# Website Rules

# Browser Navigation Reference — Whiztant Agent Spec
> **Purpose:** Agent-facing reference for autonomous browser control across Chrome, Edge, Firefox, Brave, Opera, Arc, and Vivaldi. Covers universal patterns, per-browser specifics, keyboard shortcuts, UI element grounding descriptions, and recommended action sequences.

---

## Table of Contents

1. [Universal Browser Concepts](#1-universal-browser-concepts)
2. [Address Bar Navigation](#2-address-bar-navigation)
3. [Tab Management](#3-tab-management)
4. [Page Navigation](#4-page-navigation)
5. [Find on Page](#5-find-on-page)
6. [Bookmarks and Favorites](#6-bookmarks-and-favorites)
7. [History](#7-history)
8. [Downloads](#8-downloads)
9. [Settings and Preferences](#9-settings-and-preferences)
10. [Developer Tools](#10-developer-tools)
11. [Extensions and Add-ons](#11-extensions-and-add-ons)
12. [Zoom and Display](#12-zoom-and-display)
13. [Reading and Focus Modes](#13-reading-and-focus-modes)
14. [Profiles and Accounts](#14-profiles-and-accounts)
15. [Browser-Specific Layouts](#15-browser-specific-layouts)
16. [AI Interface Navigation (Claude, ChatGPT, Gemini)](#16-ai-interface-navigation)
17. [Form Interaction Patterns](#17-form-interaction-patterns)
18. [Scroll and Page Control](#18-scroll-and-page-control)
19. [Right-Click Context Menus](#19-right-click-context-menus)
20. [Agent Decision Tree — Best Course of Action](#20-agent-decision-tree)
21. [Fallback Strategies](#21-fallback-strategies)
22. [Cross-Browser Keyboard Shortcut Master Table](#22-cross-browser-shortcut-master-table)

---

## 1. Universal Browser Concepts

These patterns are identical or near-identical across every major browser. The agent should always try universal approaches first.

### Chrome Engine Browsers (Chromium-based)
The following browsers share the same underlying engine and therefore behave identically for most interactions:
- **Google Chrome** — reference implementation
- **Microsoft Edge** — minor UI differences, same shortcuts
- **Brave** — identical UI layout to Chrome, Shields button added
- **Opera** — sidebar-first layout, same engine
- **Vivaldi** — most customizable, all shortcuts configurable
- **Arc** — completely redesigned UI, same engine underneath

### Gecko Engine
- **Firefox** — different engine, slightly different DevTools, most shortcuts identical

### Universal UI Zones (all browsers)
Every browser has these zones regardless of skin:

```
┌─────────────────────────────────────────────────────────┐
│  [←][→][↺]  [    Address Bar / Omnibox    ]  [⋮ Menu]  │  ← Toolbar
├─────────────────────────────────────────────────────────┤
│  [Tab 1] [Tab 2] [Tab 3]  [+]                           │  ← Tab Bar
├─────────────────────────────────────────────────────────┤
│                                                         │
│                    Page Content                         │  ← Viewport
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Universal Principles for Agent Actions

1. **Prefer keyboard shortcuts over clicking** — faster, more reliable, no coordinate dependency
2. **Address bar is always reachable via `Ctrl+L` or `F6`** — never rely on clicking it
3. **New tab is always `Ctrl+T`** — universal across all browsers
4. **Reload is always `F5` or `Ctrl+R`**
5. **If a click fails, try `Tab` key to focus elements**
6. **`Escape` cancels most dialogs and dismisses dropdowns**
7. **`Enter` confirms most dialogs and submits forms**

---

## 2. Address Bar Navigation

### Opening and Using the Address Bar

| Action | All Chromium Browsers | Firefox |
|--------|----------------------|---------|
| Focus address bar | `Ctrl+L` or `F6` or `Alt+D` | `Ctrl+L` or `F6` or `Alt+D` |
| Go to URL typed | `Enter` | `Enter` |
| Open URL in new tab | Type URL then `Alt+Enter` | Type URL then `Alt+Enter` |
| Search (not URL) | Type query + `Enter` | Type query + `Enter` |
| Clear address bar | `Ctrl+A` then `Delete` | `Ctrl+A` then `Delete` |
| Paste and go | `Ctrl+Shift+L` (Chrome/Edge) | — |
| Select all address bar text | `Ctrl+L` (auto-selects) | `Ctrl+L` (auto-selects) |

### UI-TARS Element Descriptions for Address Bar
```
"the address bar at the top of the browser"
"the URL input field showing the current website address"
"the omnibox search and address bar"
"the long text input at the top center of the browser window"
```

### Recommended Agent Action Sequence — Navigate to URL
```
1. keypress: Ctrl+L              ← focus address bar (universal)
2. keypress: Ctrl+A              ← select all existing text
3. type: [full URL or search query]
4. keypress: Enter
5. wait: 1.5s                    ← wait for page load
6. screenshot                    ← verify navigation succeeded
```

### Recommended Agent Action Sequence — Search Something
```
1. keypress: Ctrl+L
2. type: [search query]          ← browser auto-uses default search engine
3. keypress: Enter
4. wait: 2.0s
5. screenshot
```

### Reading the Current URL
When the agent needs to know what page is open:
```
1. keypress: Ctrl+L              ← focuses and selects address bar text
2. keypress: Ctrl+C              ← copies current URL
   (then read it from clipboard or take screenshot)
```

---

## 3. Tab Management

### Universal Tab Shortcuts

| Action | Shortcut | Works In |
|--------|----------|----------|
| New tab | `Ctrl+T` | All |
| Close current tab | `Ctrl+W` | All |
| Reopen closed tab | `Ctrl+Shift+T` | All |
| Next tab | `Ctrl+Tab` | All |
| Previous tab | `Ctrl+Shift+Tab` | All |
| Go to tab 1–8 | `Ctrl+1` through `Ctrl+8` | All |
| Go to last tab | `Ctrl+9` | All |
| Duplicate tab | `Ctrl+Shift+K` (Firefox) / right-click tab → Duplicate (Chrome) | Varies |
| Move tab to new window | Drag tab out (or right-click → Move to new window) | All |
| Pin tab | Right-click tab → Pin | All |
| Mute tab | Right-click tab → Mute | All |

### UI-TARS Element Descriptions for Tabs
```
"the tab at the top of the browser showing [page title]"
"the active tab highlighted at the top of the browser"
"the new tab button, a plus sign at the right end of the tab bar"
"the close button on the tab, an X on the right side of the tab"
"the tab showing [favicon description] and the text [title]"
```

### Recommended Agent Action Sequence — Open a Specific Site in New Tab
```
1. keypress: Ctrl+T
2. type: [URL or search]
3. keypress: Enter
4. wait: 2.0s
```

### Recommended Agent Action Sequence — Switch to a Specific Tab
```
Option A (if tab number is known):
  keypress: Ctrl+[1-8]

Option B (if searching by title):
  1. screenshot
  2. Look at tab bar for matching title/favicon
  3. click: "the tab showing [title keyword]"

Option C (many tabs — use tab search):
  Chrome/Edge: Ctrl+Shift+A  (opens tab search)
  Firefox: Ctrl+Shift+A (or type @ in address bar)
  1. keypress: Ctrl+Shift+A
  2. type: [tab title keyword]
  3. click: matching result
```

### Recommended Agent Action Sequence — Close All Tabs Except Current
```
Right-click current tab → "Close other tabs"
  OR
  click: "right-click the active tab to get tab context menu"
  click: "Close other tabs option in the context menu"
```

---

## 4. Page Navigation

### Universal Navigation Shortcuts

| Action | Shortcut |
|--------|----------|
| Go back | `Alt+Left` or `Backspace` (on non-input page) |
| Go forward | `Alt+Right` |
| Reload | `F5` or `Ctrl+R` |
| Hard reload (bypass cache) | `Ctrl+Shift+R` or `Ctrl+F5` |
| Stop loading | `Escape` |
| Go to top of page | `Ctrl+Home` |
| Go to bottom of page | `Ctrl+End` |
| Scroll down one screen | `Space` or `Page Down` |
| Scroll up one screen | `Shift+Space` or `Page Up` |
| Scroll down | `↓` or `J` (some sites) |

### UI-TARS Element Descriptions for Navigation
```
"the back button, a left-pointing arrow at the top left of the browser"
"the forward button, a right-pointing arrow next to the back button"
"the refresh/reload button, a circular arrow next to the address bar"
"the stop loading button, an X that appears while the page is loading"
```

### Recommended Agent Action Sequence — Go Back to Previous Page
```
Option A (fastest):  keypress: Alt+Left
Option B (reliable): click: "the back arrow button at top left of browser"
Option C (if both fail): keypress: Backspace (only works when not in input)
```

---

## 5. Find on Page

| Action | Shortcut |
|--------|----------|
| Open find bar | `Ctrl+F` or `F3` |
| Find next | `Enter` or `F3` |
| Find previous | `Shift+Enter` or `Shift+F3` |
| Close find bar | `Escape` |

### UI-TARS Element Descriptions
```
"the find bar that appeared at the bottom or top of the browser"
"the search input in the find bar showing 'Find in page'"
"the find next button (right arrow) in the find bar"
"the find previous button (left arrow) in the find bar"
"the match count showing X of Y in the find bar"
```

### Recommended Agent Action Sequence — Find Text on Page
```
1. keypress: Ctrl+F
2. type: [text to find]
3. read screenshot for match count and highlights
4. keypress: Enter              ← jump to next match if needed
5. keypress: Escape             ← close find bar when done
```

---

## 6. Bookmarks and Favorites

### Universal Bookmark Shortcuts

| Action | Chrome/Brave/Edge/Vivaldi | Firefox |
|--------|--------------------------|---------|
| Bookmark current page | `Ctrl+D` | `Ctrl+D` |
| Open bookmarks bar | `Ctrl+Shift+B` | `Ctrl+Shift+B` |
| Open bookmarks manager | `Ctrl+Shift+O` | `Ctrl+Shift+O` |
| Add to reading list | Edge: `Ctrl+Shift+D` | — |

### UI-TARS Element Descriptions
```
"the bookmark star icon at the right side of the address bar"
"the bookmarks bar below the address bar showing saved sites"
"the Bookmarks menu at the top"
"the Add bookmark dialog box that appeared"
"the bookmark name input field in the save bookmark dialog"
"the Done button in the bookmark dialog"
"the Bookmarks manager page showing all saved bookmarks"
```

### Recommended Agent Action Sequence — Bookmark Current Page
```
1. keypress: Ctrl+D
2. wait: 0.5s
3. screenshot                   ← verify dialog appeared
4. (optional) click: "the bookmark name field" → type: [custom name]
5. keypress: Enter              ← confirm / Done
```

---

## 7. History

| Action | Shortcut |
|--------|----------|
| Open history page | `Ctrl+H` |
| Open history sidebar (Edge) | `Ctrl+Shift+H` |
| Clear browsing data | `Ctrl+Shift+Delete` |

### UI-TARS Element Descriptions
```
"the History page showing a list of previously visited sites"
"the search history input field at the top of the History page"
"the Clear browsing data button"
"the time range dropdown in the clear browsing data dialog"
"the Clear data or Clear now button in the clear browsing dialog"
```

### Recommended Agent Action Sequence — Find a Previously Visited Site
```
1. keypress: Ctrl+H
2. wait: 1.0s
3. click: "the search history input field"
4. type: [site name or keyword]
5. click: matching result in history list
```

### Recommended Agent Action Sequence — Clear History
```
1. keypress: Ctrl+Shift+Delete
2. wait: 0.5s
3. screenshot — verify dialog appeared
4. click: "the time range dropdown" → select desired range
5. ensure desired checkboxes are checked
6. click: "the Clear data button"
```

---

## 8. Downloads

| Action | Shortcut |
|--------|----------|
| Open downloads page | `Ctrl+J` |
| Show downloads panel | `Ctrl+J` (Chrome shows bar at bottom, Edge shows sidebar) |

### UI-TARS Element Descriptions
```
"the downloads bar that appeared at the bottom of the browser"
"the Downloads page showing a list of downloaded files"
"the Open file button next to a completed download"
"the Show in folder button next to a download"
"the Clear all button on the Downloads page"
"the download progress bar showing percentage complete"
```

### Recommended Agent Action Sequence — Open Downloaded File
```
1. keypress: Ctrl+J
2. wait: 0.5s
3. screenshot — find the download
4. click: "the Open file button or the filename of the completed download"
```

---

## 9. Settings and Preferences

| Browser | Open Settings | Settings URL |
|---------|--------------|--------------|
| Chrome | `Ctrl+,` or ⋮ → Settings | `chrome://settings` |
| Edge | `Ctrl+,` or … → Settings | `edge://settings` |
| Firefox | `Ctrl+,` or ☰ → Settings | `about:preferences` |
| Brave | `Ctrl+,` | `brave://settings` |
| Opera | `Ctrl+,` | `opera://settings` |
| Vivaldi | `Ctrl+,` | Vivaldi Settings panel |
| Arc | Click user icon or `Cmd+,` | Arc Settings panel |

### Common Settings Sections (All Browsers)

| Setting | Chrome path | Firefox path |
|---------|-------------|--------------|
| Default search engine | Settings → Search engine | Preferences → Search |
| Homepage | Settings → On startup | Preferences → Home |
| Passwords | Settings → Autofill → Passwords | Preferences → Privacy → Logins |
| Privacy/Cookies | Settings → Privacy and security | Preferences → Privacy & Security |
| Downloads location | Settings → Downloads | Preferences → General → Downloads |
| Fonts and appearance | Settings → Appearance | Preferences → General → Fonts |
| Notifications | Settings → Privacy → Site Settings → Notifications | Preferences → Privacy → Notifications |
| JavaScript | Settings → Privacy → Site Settings → JavaScript | via about:config |

### UI-TARS Element Descriptions for Settings
```
"the three dot menu button at the top right of the browser"
"the three line hamburger menu at the top right of Firefox"
"the Settings option in the browser menu"
"the search settings input field at the top of the Settings page"
"the left sidebar of Settings showing category sections"
"the Privacy and security section in Settings"
"the toggle switch for [setting name] in browser settings"
```

### Recommended Agent Action Sequence — Change a Setting
```
1. keypress: Ctrl+,                   ← open settings (universal)
2. wait: 1.0s
3. click: "the search settings input"
4. type: [setting keyword e.g. 'notifications' or 'downloads']
5. screenshot — find matching setting
6. click or toggle the relevant control
7. (settings usually auto-save in Chrome-family browsers)
```

### Recommended Agent Action Sequence — Navigate to Specific Settings URL
```
1. keypress: Ctrl+L
2. type: chrome://settings/privacy    (or edge://settings/privacy etc.)
3. keypress: Enter
4. wait: 1.0s
```

---

## 10. Developer Tools

| Action | Shortcut |
|--------|----------|
| Open DevTools | `F12` or `Ctrl+Shift+I` |
| Open Console directly | `Ctrl+Shift+J` |
| Open Network tab | `F12` then click Network |
| Inspect element | `Ctrl+Shift+C` |
| Open DevTools to Elements | `Ctrl+Shift+I` → Elements tab |
| Toggle device emulation | `Ctrl+Shift+M` (inside DevTools) |
| Close DevTools | `F12` or `Ctrl+Shift+I` again |

### UI-TARS Element Descriptions
```
"the DevTools panel that opened at the bottom or right of the browser"
"the Console tab in the DevTools panel"
"the Elements tab in the DevTools panel"
"the Network tab in the DevTools panel"
"the JavaScript console input at the bottom of the DevTools console"
"the close button for the DevTools panel, an X at the top right of DevTools"
```

### Recommended Agent Action Sequence — Run JavaScript in Console
```
1. keypress: Ctrl+Shift+J          ← opens DevTools directly to console
2. wait: 0.5s
3. click: "the console input line at the bottom of the DevTools panel"
4. type: [JavaScript code]
5. keypress: Enter
6. screenshot — read output
```

---

## 11. Extensions and Add-ons

| Browser | Open Extensions | URL |
|---------|----------------|-----|
| Chrome | ⋮ → Extensions → Manage Extensions | `chrome://extensions` |
| Edge | … → Extensions | `edge://extensions` |
| Firefox | ☰ → Add-ons and themes | `about:addons` |
| Brave | ⋮ → Extensions | `brave://extensions` |

### UI-TARS Element Descriptions
```
"the Extensions page showing installed browser extensions"
"the toggle switch to enable or disable an extension"
"the Remove button to uninstall an extension"
"the extension icon in the browser toolbar to the right of the address bar"
"the Extensions puzzle piece icon in the toolbar"
"the pin button next to an extension to show it in the toolbar"
```

---

## 12. Zoom and Display

| Action | Shortcut |
|--------|----------|
| Zoom in | `Ctrl++` or `Ctrl+Scroll Up` |
| Zoom out | `Ctrl+-` or `Ctrl+Scroll Down` |
| Reset zoom to 100% | `Ctrl+0` |
| Full screen | `F11` |
| Exit full screen | `F11` or `Escape` |

### UI-TARS Element Descriptions
```
"the zoom level indicator in the address bar showing e.g. 110%"
"the zoom in button (plus sign) in the browser menu"
"the zoom out button (minus sign) in the browser menu"
"the reset zoom button in the browser menu"
```

---

## 13. Reading and Focus Modes

| Browser | Feature | How to Activate |
|---------|---------|----------------|
| Edge | Immersive Reader | `F9` or click book icon in address bar |
| Firefox | Reader View | Click reader icon in address bar (looks like lines) |
| Safari (macOS) | Reader Mode | Address bar reader icon |
| Chrome | Reading mode | Enabled via `chrome://flags` then View menu |
| Brave | SpeedReader | Click SpeedReader icon in address bar |

### UI-TARS Element Descriptions
```
"the reader mode icon in the address bar, looks like a page with lines"
"the Immersive Reader button in the Edge address bar"
"the reader view icon in Firefox address bar"
"the Immersive Reader toolbar showing text size and background options"
```

---

## 14. Profiles and Accounts

| Action | Chrome | Edge | Firefox |
|--------|--------|------|---------|
| Open profile menu | Click avatar top right | Click avatar top right | Click avatar / Profile |
| Add new profile | Profile menu → Add | Profile menu → Add profile | Profile menu → Manage |
| Switch profile | Profile menu → click name | Profile menu → click name | Profile menu |
| Sign in | Profile menu → Sign in | Profile menu → Sign in | Preferences → Sync |
| Open incognito/private | `Ctrl+Shift+N` | `Ctrl+Shift+N` | `Ctrl+Shift+P` |

### UI-TARS Element Descriptions
```
"the profile avatar icon at the top right of the browser, shows a person or photo"
"the profile menu that opened showing account options"
"the Add new profile option in the profile menu"
"the Manage profiles button in the profile menu"
"the incognito or private mode indicator, browser has dark theme with spy icon"
```

### Recommended Agent Action Sequence — Open Incognito/Private Window
```
Chrome/Edge/Brave: keypress: Ctrl+Shift+N
Firefox:           keypress: Ctrl+Shift+P
```

---

## 15. Browser-Specific Layouts

### Google Chrome

**Toolbar elements left to right:**
Back → Forward → Reload → Address Bar → Bookmark Star → Extensions Puzzle Icon → Profile Avatar → More (⋮)

**Unique features:**
- Chrome flags: `chrome://flags`
- Task manager: `Shift+Escape`
- Cast/share: `chrome://cast`
- Apps page: `chrome://apps`

**UI-TARS specific to Chrome:**
```
"the three dot menu at the very top right corner of Chrome"
"the Google Chrome new tab page with search bar and shortcuts"
"the Chrome tab strip showing multiple tabs"
```

---

### Microsoft Edge

**Toolbar elements:**
Back → Forward → Reload → Address Bar → Shopping/Copilot → Favorites Star → Collections → Extensions → Profile → Settings (…)

**Unique features:**
- Copilot sidebar: `Ctrl+Shift+.` or click Copilot icon
- Collections: `Ctrl+Shift+Y`
- Immersive Reader: `F9`
- Web Capture (screenshot): `Ctrl+Shift+S`
- Vertical tabs: click grid icon top left
- Drop (file sharing): Edge sidebar feature
- PDF tools built in (annotate without extension)

**UI-TARS specific to Edge:**
```
"the three dot menu at the top right of Edge labeled Settings and more"
"the Copilot button in the Edge toolbar, shows a star or copilot icon"
"the Edge sidebar on the right side of the browser"
"the Collections button in the Edge toolbar"
"the vertical tabs panel on the left side of Edge"
"the Immersive Reader button in the Edge address bar"
```

**Recommended Agent Action Sequence — Use Edge Copilot:**
```
1. keypress: Ctrl+Shift+.           ← toggle Copilot sidebar
2. wait: 0.5s
3. click: "the Copilot chat input field in the sidebar"
4. type: [your message]
5. keypress: Enter
```

---

### Mozilla Firefox

**Toolbar elements:**
Back → Forward → Reload → Home → Address Bar → Downloads → Extensions → More (☰)

**Unique features:**
- Container tabs: Isolate logins per tab
- Enhanced Tracking Protection: Shield icon in address bar
- Firefox View: sidebar tab/history overview
- `about:config`: advanced settings
- Pocket: save articles (Ctrl+Shift+S)
- Screenshot tool: right-click → Take Screenshot

**UI-TARS specific to Firefox:**
```
"the hamburger menu, three horizontal lines at the top right of Firefox"
"the Firefox shield icon in the address bar showing tracking protection"
"the Firefox reader view icon in the address bar"
"the Firefox tab search button, a chevron at the end of the tab bar"
"the container tab colored bar indicator under a tab"
"the Firefox sidebar showing bookmarks or history"
```

**Recommended Agent Action Sequence — Use Firefox Tab Search:**
```
1. click: "the tab search chevron button at the far right of the Firefox tab bar"
   OR keypress: Ctrl+Shift+A
2. type: [tab title keyword]
3. click: matching tab in dropdown
```

---

### Brave Browser

**Toolbar elements:**
Back → Forward → Reload → Address Bar → Brave Shields → Brave Wallet → VPN → Extensions → Profile → More (⋮)

**Unique features:**
- Brave Shields: block ads/trackers, click shield icon in address bar
- Brave Rewards: BAT token earning
- Brave Talk: built-in video calls
- Brave Wallet: crypto wallet
- Tor window: `Ctrl+Shift+N` for private + `Ctrl+Alt+N` for Tor
- `brave://settings/shields`: global shield settings

**UI-TARS specific to Brave:**
```
"the Brave Shields icon in the address bar, looks like a lion head"
"the Shields panel showing tracker and ad block counts"
"the Brave Wallet icon in the toolbar"
"the Brave menu, three dots at top right same as Chrome"
```

**Recommended Agent Action Sequence — Toggle Brave Shields:**
```
1. click: "the Brave Shields lion icon in the address bar"
2. wait: 0.3s
3. click: "the Shields toggle to turn on or off"
```

---

### Opera

**Toolbar elements:**
Opera icon (menu) → Sidebar (left): Tabs, Messenger, WhatsApp, Instagram, Speed Dial, Bookmarks, History → Address Bar → Extensions → Profile

**Unique features:**
- Built-in VPN: enabled in settings, VPN badge in address bar
- Built-in ad blocker: settings → Basic → Block ads
- Speed Dial: new tab page with quick access tiles
- Sidebar messaging: Messenger, WhatsApp, Telegram baked in
- Workspaces: group tabs into named workspaces
- Opera One AI: sidebar AI assistant

**UI-TARS specific to Opera:**
```
"the Opera sidebar on the left showing app icons"
"the VPN badge in the Opera address bar showing VPN status"
"the Opera Speed Dial new tab page with tile shortcuts"
"the Opera menu, the red O icon at the top left"
"the Workspaces icon in the Opera sidebar"
```

---

### Vivaldi

**Unique features:**
- Panels: left sidebar panels for bookmarks, notes, mail, feeds
- Tab stacking: drag one tab onto another to group
- Tab tiling: view multiple tabs side-by-side
- Notes: built-in note-taking (`Ctrl+Shift+N` to open notes panel)
- Web panels: pin any website as a sidebar panel
- All shortcuts configurable in `vivaldi://settings/keyboard`
- Command chain: automate sequences of actions

**UI-TARS specific to Vivaldi:**
```
"the Vivaldi sidebar on the left with panel icons"
"the Vivaldi status bar at the very bottom of the browser"
"the tab stack showing stacked tabs in Vivaldi"
"the tile icon to tile tabs side by side in Vivaldi"
"the Notes panel in the Vivaldi sidebar"
```

---

### Arc Browser (Windows/macOS)

Arc has the most different UI of all browsers — important for the agent to know.

**Layout:**
- **No traditional tab bar at top** — tabs live in the left sidebar
- Sidebar contains: Spaces, Pinned tabs, Today tabs, Archive
- Address bar opens as a command palette overlay (Cmd+T / Ctrl+T)
- Split view: two pages side by side

**Unique features:**
- Spaces: named groups of tabs (like workspaces)
- Pinned tabs: permanent tabs that don't close
- Boosts: custom CSS/JS per website
- Air Traffic Control: auto-route URLs to specific spaces
- Little Arc: mini browser popup for quick links

**Keyboard shortcuts (Arc-specific):**
| Action | Shortcut |
|--------|----------|
| New tab | `Ctrl+T` |
| Open command bar | `Ctrl+L` |
| New window | `Ctrl+N` |
| Toggle sidebar | `Ctrl+S` |
| Switch space | `Ctrl+1/2/3` |
| Archive current tab | `Ctrl+W` |
| Split view | `Ctrl+Shift+Enter` |

**UI-TARS specific to Arc:**
```
"the Arc sidebar on the left showing tabs and spaces"
"the Arc command bar that opened as an overlay in the center of the browser"
"the Spaces icons at the top of the Arc sidebar"
"the pinned tabs section in the Arc sidebar"
"the today's tabs section in the Arc sidebar"
"the Arc new tab command input in the center overlay"
```

**Recommended Agent Action Sequence — Navigate in Arc:**
```
1. keypress: Ctrl+L              ← opens command bar overlay
2. type: [URL or search]
3. keypress: Enter
```

---

## 16. AI Interface Navigation

Critical for Whiztant agent mode — controlling AI interfaces autonomously.

### Claude (claude.ai)

**Page layout:**
- Left sidebar: conversation list, New Chat button, Project selector
- Center: chat thread with messages
- Bottom: input textarea + send button + attachment + model selector

**Key interactions:**

| Action | Method |
|--------|--------|
| Start new chat | Click "New chat" in sidebar, or `Ctrl+Shift+O` |
| Focus input | Click textarea at bottom, or `Tab` to reach it |
| Send message | Click send button (arrow) or `Shift+Enter` (no, actually just `Enter`) |
| New line in message | `Shift+Enter` |
| Attach file | Click paperclip icon in input area |
| Select model | Click model name above input |
| Open a past chat | Click conversation in left sidebar |

**UI-TARS element descriptions for Claude:**
```
"the New chat button in the top left of Claude sidebar"
"the message input textarea at the bottom center of Claude"
"the send button, an upward arrow at the right of the input"
"the model selector showing the current model name above the input"
"the left sidebar of Claude showing past conversations"
"the stop button, a square that appears while Claude is responding"
"the copy button that appears when hovering over a Claude response"
"the thumbs up button below a Claude response"
"the thumbs down button below a Claude response"
"the regenerate or retry button below a Claude response"
"the attachment paperclip icon in the Claude input area"
"the Claude.ai logo and brand name at the top left"
```

**Recommended Agent Action Sequence — Send a Message to Claude:**
```
1. keypress: Ctrl+L
2. type: claude.ai
3. keypress: Enter
4. wait: 2.0s
5. click: "the message input textarea at the bottom of Claude"
6. type: [message]
7. keypress: Enter
8. wait: 5.0s+                  ← wait for full response
9. screenshot — read response
```

---

### ChatGPT (chatgpt.com)

**Page layout:**
- Left sidebar: chat history, New chat, GPT selector, plan info
- Center: conversation thread
- Bottom: input with voice, attach, search toggles

| Action | Method |
|--------|--------|
| New chat | Click "New chat" at top of sidebar |
| Focus input | Click textarea at bottom |
| Send | Click paper plane or press `Enter` |
| New line | `Shift+Enter` |
| Select GPT model | Click model name in top center dropdown |
| Toggle web search | Click globe icon in input area |
| Voice input | Click microphone icon |
| Upload file | Click paperclip icon |

**UI-TARS element descriptions for ChatGPT:**
```
"the New chat button at the top left of the ChatGPT sidebar"
"the message input field at the bottom of ChatGPT"
"the send button with paper plane icon to the right of the input"
"the model selector at the very top center of ChatGPT showing GPT version"
"the ChatGPT left sidebar showing conversation history"
"the stop generating button that appears while ChatGPT is responding"
"the copy icon that appears on hover next to a ChatGPT message"
"the regenerate button below the last ChatGPT response"
"the web search globe icon in the ChatGPT input toolbar"
"the attach files paperclip icon in the ChatGPT input toolbar"
"the microphone icon for voice input in ChatGPT"
"the GPT-4o or model name shown at top of ChatGPT interface"
```

**Recommended Agent Action Sequence — Send a Message to ChatGPT:**
```
1. keypress: Ctrl+L
2. type: chatgpt.com
3. keypress: Enter
4. wait: 2.0s
5. click: "the message input at the bottom of ChatGPT"
6. type: [message]
7. keypress: Enter
8. wait: 5.0s+
9. screenshot
```

---

### Google Gemini (gemini.google.com)

| Action | Method |
|--------|--------|
| New chat | Click pencil/new icon in sidebar |
| Focus input | Click input at bottom |
| Send | Click send button or `Enter` |
| Upload image | Click image icon in input |
| Use Gemini Advanced | Requires Google One subscription |
| Google extensions | Click extension icon (Drive, Gmail, etc.) |

**UI-TARS element descriptions for Gemini:**
```
"the new chat pencil icon at the top of the Gemini sidebar"
"the message input field at the bottom of Gemini"
"the send button to the right of the Gemini input"
"the image or file upload icon in the Gemini input toolbar"
"the Gemini left sidebar showing past conversations"
"the show drafts button to see alternative Gemini responses"
"the Google apps extension icons in the Gemini interface"
```

---

### Perplexity (perplexity.ai)

**UI-TARS element descriptions:**
```
"the search input at the center of the Perplexity home page"
"the new thread button in the Perplexity sidebar"
"the focus selector showing Web, Academic, Writing, etc."
"the sources panel on the right side of a Perplexity answer"
"the follow-up question input at the bottom of a Perplexity thread"
```

---

## 17. Form Interaction Patterns

Forms are the most common agent interaction after navigation.

### Text Inputs
```
Sequence:
1. click: "the [field name] input field"
2. keypress: Ctrl+A              ← select any existing text
3. type: [new value]
```

### Dropdowns / Select Elements
```
Option A — Native HTML select:
1. click: "the [dropdown name] dropdown"
2. click: "the [option name] option in the dropdown list"

Option B — Custom dropdown:
1. click: "the [dropdown name] selector button"
2. wait: 0.3s
3. screenshot — see options
4. click: "the [option] option in the dropdown menu"

Option C — Using keyboard:
1. click: "the dropdown"
2. type: first letter of option (for native selects, jumps to match)
   OR keypress: Arrow Down/Up to navigate
3. keypress: Enter to confirm
```

### Checkboxes
```
1. click: "the [label] checkbox"
   (clicking label also usually works for native checkboxes)

Verify: screenshot — checkbox should show checkmark
```

### Radio Buttons
```
1. click: "the [option name] radio button"
   OR click the label text next to the radio button
```

### Date Pickers
```
Option A (if text input):
1. click: "the date input field"
2. type: [date in MM/DD/YYYY or YYYY-MM-DD format]

Option B (if calendar picker appears):
1. click: "the date input"
2. click: "[month] [year] header to navigate"
3. click: "the [day number] on the calendar"
```

### File Upload
```
1. click: "the Choose file or Upload button"
2. wait: 0.5s — file dialog opens
3. keypress: Ctrl+L (in file dialog) — focus path bar
   OR click: "the file name input bar in the file dialog"
4. type: [full file path e.g. C:\Users\Username\Documents\file.pdf]
5. keypress: Enter
```

### Form Submission
```
Option A: keypress: Enter (if cursor in a text field)
Option B: click: "the Submit or Save or Continue button"
Option C: keypress: Tab to reach submit button, then Enter
```

---

## 18. Scroll and Page Control

### Scrolling Methods

| Method | When to Use |
|--------|------------|
| `keypress: Space` | Scroll down one viewport — reliable on most pages |
| `keypress: Shift+Space` | Scroll up one viewport |
| `keypress: Ctrl+End` | Jump to bottom of page |
| `keypress: Ctrl+Home` | Jump to top of page |
| `scroll: down` (pyautogui) | Fine control, works in any element |
| `keypress: Arrow Down` | Scroll small amount (page must be focused, not input) |
| `keypress: Page Down` | One page down |

### Scrolling Inside a Specific Element
```
1. click: [the scrollable element to give it focus]
2. scroll: down/up (pyautogui scroll on that element's coordinates)
```

### Infinite Scroll Pages (Twitter/X, LinkedIn, Instagram feeds)
```
Loop:
1. keypress: End                 ← jump to bottom
2. wait: 2.0s                   ← wait for new content to load
3. screenshot                   ← check if target content appeared
4. repeat until found or max iterations
```

---

## 19. Right-Click Context Menus

Right-click menus are reliable fallbacks when toolbar buttons are unclear.

### On a Link
```
"Open link in new tab"
"Open link in new window"
"Save link as"
"Copy link address"
"Inspect" (opens DevTools on element)
```

### On an Image
```
"Save image as"
"Copy image"
"Copy image address"
"Search image with Google Lens" (Chrome)
"Open image in new tab"
"Inspect"
```

### On Selected Text
```
"Copy"
"Search Google for [selected text]"
"Look up [text]" (Edge/macOS)
"Print"
```

### On a Page (no selection)
```
"Save as"
"Print"
"Cast/Send to"
"View page source" (Ctrl+U)
"Inspect"
"Translate to English"
```

### Recommended Agent Action Sequence — Right-Click to Open in New Tab
```
1. right_click: "the link to [destination]"
2. wait: 0.3s
3. click: "Open link in new tab option in the context menu"
```

---

## 20. Agent Decision Tree

Best course of action when the agent receives a browser task.

```
RECEIVED BROWSER TASK
        │
        ▼
Is the browser already open?
  NO  → launch browser (type browser name in Windows search + Enter)
  YES → proceed
        │
        ▼
Is the correct page already loaded?
  YES → skip navigation
  NO  → keypress: Ctrl+L → type URL → Enter
        │
        ▼
Does the task require:
  ├── FIND SOMETHING ON CURRENT PAGE?
  │     → keypress: Ctrl+F → type search term
  │
  ├── FILL A FORM?
  │     → Tab through fields OR click each field
  │     → Use Ctrl+A before typing to clear existing content
  │     → Enter to submit
  │
  ├── CLICK A BUTTON/LINK?
  │     → Prefer: identify via UI-TARS description
  │     → Fallback: Tab to focus, Enter to click
  │     → Last resort: Ctrl+F to find button text, then click
  │
  ├── EXTRACT TEXT/DATA FROM PAGE?
  │     → Ctrl+A → Ctrl+C (copy all page text)
  │     OR Ctrl+F to locate section, then manual selection
  │     OR DevTools Console: document.querySelector('...').innerText
  │
  ├── SCROLL TO FIND CONTENT?
  │     → Ctrl+F first (fastest)
  │     → If not found: Space/Page Down scroll + screenshot loop
  │
  ├── OPEN NEW TAB FOR PARALLEL TASK?
  │     → Ctrl+T → navigate
  │     → Ctrl+Tab to return to original
  │
  └── INTERACT WITH AI INTERFACE?
        → Focus input: click textarea or Tab to it
        → Type message
        → Enter to send
        → Wait for response (screenshot loop until response complete)
```

---

## 21. Fallback Strategies

When the primary approach fails, use these in order.

### Fallback 1 — Element Not Found by UI-TARS
```
1. Try Ctrl+F to search for the element's visible text
2. Tab through interactive elements to find it by keyboard focus
3. Try right-clicking the area near where the element should be
4. Zoom in (Ctrl++) and retry UI-TARS grounding
5. Try a different element description (more or less specific)
```

### Fallback 2 — Page Didn't Load
```
1. keypress: F5 (reload)
2. wait: 3.0s
3. If still loading: keypress: Escape then F5 again
4. If error page: keypress: Alt+Left (go back) → try different approach
```

### Fallback 3 — Click Didn't Register
```
1. Verify element is visible (not behind dropdown/modal)
2. keypress: Escape (dismiss any overlay)
3. scroll to bring element into view, then retry
4. Try double-click instead of single click
5. Try keyboard alternative (Tab + Enter)
```

### Fallback 4 — Typing Didn't Work
```
1. click the input field again to ensure focus
2. keypress: Ctrl+A to select all
3. keypress: Delete to clear
4. try pyperclip copy + Ctrl+V paste approach
```

### Fallback 5 — Page Requires Login
```
1. screenshot — identify login form
2. click: "the username or email input field"
3. type: [credential from secure context]
4. keypress: Tab
5. type: [password from secure context]
6. keypress: Enter
7. wait: 3.0s — verify login succeeded
```

### Fallback 6 — Popup or Dialog Blocking Interaction
```
1. screenshot — identify the popup
2. keypress: Escape (closes most dialogs)
3. If permission dialog: click "Allow" or "Block" as appropriate
4. If cookie consent: click "Accept all" or "Reject all"
5. If notification request: click "Block"
6. If overlay ad: find and click X close button
```

### Fallback 7 — Browser Froze or Tab Crashed
```
Chrome/Edge: Shift+Escape → Task Manager → End process for crashed tab
Firefox: close and reopen tab
All: Ctrl+Shift+T to reopen last closed tab
```

---

## 22. Cross-Browser Keyboard Shortcut Master Table

| Action | Chrome | Edge | Firefox | Brave | Opera | Vivaldi | Arc |
|--------|--------|------|---------|-------|-------|---------|-----|
| **Navigation** | | | | | | | |
| Focus address bar | Ctrl+L | Ctrl+L | Ctrl+L | Ctrl+L | Ctrl+L | Ctrl+L | Ctrl+L |
| Open URL in new tab | Alt+Enter | Alt+Enter | Alt+Enter | Alt+Enter | Alt+Enter | Alt+Enter | Alt+Enter |
| Go back | Alt+← | Alt+← | Alt+← | Alt+← | Alt+← | Alt+← | Alt+← |
| Go forward | Alt+→ | Alt+→ | Alt+→ | Alt+→ | Alt+→ | Alt+→ | Alt+→ |
| Reload | F5 | F5 | F5 | F5 | F5 | F5 | F5 |
| Hard reload | Ctrl+Shift+R | Ctrl+Shift+R | Ctrl+Shift+R | Ctrl+Shift+R | Ctrl+Shift+R | Ctrl+Shift+R | Ctrl+Shift+R |
| Stop loading | Escape | Escape | Escape | Escape | Escape | Escape | Escape |
| **Tabs** | | | | | | | |
| New tab | Ctrl+T | Ctrl+T | Ctrl+T | Ctrl+T | Ctrl+T | Ctrl+T | Ctrl+T |
| Close tab | Ctrl+W | Ctrl+W | Ctrl+W | Ctrl+W | Ctrl+W | Ctrl+W | Ctrl+W |
| Reopen closed tab | Ctrl+Shift+T | Ctrl+Shift+T | Ctrl+Shift+T | Ctrl+Shift+T | Ctrl+Shift+T | Ctrl+Shift+T | — |
| Next tab | Ctrl+Tab | Ctrl+Tab | Ctrl+Tab | Ctrl+Tab | Ctrl+Tab | Ctrl+Tab | Ctrl+Tab |
| Previous tab | Ctrl+Shift+Tab | Ctrl+Shift+Tab | Ctrl+Shift+Tab | Ctrl+Shift+Tab | Ctrl+Shift+Tab | Ctrl+Shift+Tab | Ctrl+Shift+Tab |
| Go to tab N | Ctrl+N | Ctrl+N | Ctrl+N | Ctrl+N | Ctrl+N | Ctrl+N | Ctrl+N |
| Last tab | Ctrl+9 | Ctrl+9 | Ctrl+9 | Ctrl+9 | Ctrl+9 | Ctrl+9 | — |
| Tab search | Ctrl+Shift+A | Ctrl+Shift+A | Ctrl+Shift+A | Ctrl+Shift+A | — | — | — |
| **Windows** | | | | | | | |
| New window | Ctrl+N | Ctrl+N | Ctrl+N | Ctrl+N | Ctrl+N | Ctrl+N | Ctrl+N |
| Incognito/Private | Ctrl+Shift+N | Ctrl+Shift+N | Ctrl+Shift+P | Ctrl+Shift+N | Ctrl+Shift+N | Ctrl+Shift+N | — |
| Close window | Ctrl+Shift+W | Ctrl+Shift+W | Ctrl+Shift+W | Ctrl+Shift+W | Ctrl+Shift+W | Ctrl+Shift+W | — |
| **Page** | | | | | | | |
| Find on page | Ctrl+F | Ctrl+F | Ctrl+F | Ctrl+F | Ctrl+F | Ctrl+F | Ctrl+F |
| Zoom in | Ctrl++ | Ctrl++ | Ctrl++ | Ctrl++ | Ctrl++ | Ctrl++ | Ctrl++ |
| Zoom out | Ctrl+- | Ctrl+- | Ctrl+- | Ctrl+- | Ctrl+- | Ctrl+- | Ctrl+- |
| Reset zoom | Ctrl+0 | Ctrl+0 | Ctrl+0 | Ctrl+0 | Ctrl+0 | Ctrl+0 | Ctrl+0 |
| Full screen | F11 | F11 | F11 | F11 | F11 | F11 | — |
| View source | Ctrl+U | Ctrl+U | Ctrl+U | Ctrl+U | Ctrl+U | Ctrl+U | Ctrl+U |
| Print | Ctrl+P | Ctrl+P | Ctrl+P | Ctrl+P | Ctrl+P | Ctrl+P | Ctrl+P |
| Save page | Ctrl+S | Ctrl+S | Ctrl+S | Ctrl+S | Ctrl+S | Ctrl+S | Ctrl+S |
| Select all | Ctrl+A | Ctrl+A | Ctrl+A | Ctrl+A | Ctrl+A | Ctrl+A | Ctrl+A |
| Copy | Ctrl+C | Ctrl+C | Ctrl+C | Ctrl+C | Ctrl+C | Ctrl+C | Ctrl+C |
| Paste | Ctrl+V | Ctrl+V | Ctrl+V | Ctrl+V | Ctrl+V | Ctrl+V | Ctrl+V |
| **Tools** | | | | | | | |
| Settings | Ctrl+, | Ctrl+, | Ctrl+, | Ctrl+, | Ctrl+, | Ctrl+, | — |
| History | Ctrl+H | Ctrl+H | Ctrl+H | Ctrl+H | Ctrl+H | Ctrl+H | — |
| Downloads | Ctrl+J | Ctrl+J | Ctrl+J | Ctrl+J | Ctrl+J | Ctrl+J | — |
| Bookmarks bar | Ctrl+Shift+B | Ctrl+Shift+B | Ctrl+Shift+B | Ctrl+Shift+B | Ctrl+Shift+B | Ctrl+Shift+B | — |
| Bookmark page | Ctrl+D | Ctrl+D | Ctrl+D | Ctrl+D | Ctrl+D | Ctrl+D | — |
| Bookmark manager | Ctrl+Shift+O | Ctrl+Shift+O | Ctrl+Shift+O | Ctrl+Shift+O | Ctrl+Shift+O | Ctrl+Shift+O | — |
| DevTools | F12 | F12 | F12 | F12 | F12 | F12 | F12 |
| DevTools Console | Ctrl+Shift+J | Ctrl+Shift+J | Ctrl+Shift+K | Ctrl+Shift+J | Ctrl+Shift+J | Ctrl+Shift+J | — |
| Inspect element | Ctrl+Shift+C | Ctrl+Shift+C | Ctrl+Shift+C | Ctrl+Shift+C | Ctrl+Shift+C | Ctrl+Shift+C | — |
| **Scroll** | | | | | | | |
| Page down | Space | Space | Space | Space | Space | Space | Space |
| Page up | Shift+Space | Shift+Space | Shift+Space | Shift+Space | Shift+Space | Shift+Space | Shift+Space |
| Top of page | Ctrl+Home | Ctrl+Home | Ctrl+Home | Ctrl+Home | Ctrl+Home | Ctrl+Home | Ctrl+Home |
| Bottom of page | Ctrl+End | Ctrl+End | Ctrl+End | Ctrl+End | Ctrl+End | Ctrl+End | Ctrl+End |

---

## Quick Reference — Agent Priority Rules

1. **Always use `Ctrl+L` to reach address bar** — never click it based on coordinates
2. **Always use `Ctrl+T` for new tabs** — never click the `+` button
3. **Always describe elements semantically to UI-TARS** — "the blue Login button" not "button at coordinate 450,200"
4. **Prefer keyboard over mouse** for navigation, tabs, scrolling, and form submission
5. **Use `Ctrl+F` before scrolling** — if you're looking for text, find is 10x faster
6. **Wait after navigation** — 1.5s minimum, 3.0s for complex apps like Claude/ChatGPT
7. **Screenshot after every action** — verify state before next step
8. **`Escape` is the universal cancel** — dismiss menus, dialogs, find bar, overlays
9. **`Ctrl+Z` is universal undo** — if a type action went wrong
10. **If stuck: `Ctrl+L` then navigate fresh** — reloading is faster than debugging a bad state

---

*This file is part of the Whiztant agent reference system. Store at `C:\whis\whiztant-app\agent_browser_spec.md`.*
*Cross-reference with `agent_navigation_spec.md` for Windows app navigation patterns.*
