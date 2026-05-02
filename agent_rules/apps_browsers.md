# Browser App Rules

## Universal Browser Fast Paths

- Focus the address bar with `Ctrl+L` before typing a URL or search.
- Open a new tab with `Ctrl+T`.
- Reopen the last closed tab with `Ctrl+Shift+T`.
- Close the current tab with `Ctrl+W`.
- Reload with `Ctrl+R` or `F5`.
- Find text on the page with `Ctrl+F`.
- Open downloads with `Ctrl+J`.
- Open history with `Ctrl+H`.
- Open developer tools with `F12` or `Ctrl+Shift+I`.

## Browser Execution Rules

- Prefer shortcut-first navigation before visual clicking.
- Use the address bar for direct routes to sites, browser settings pages, and internal URLs.
- When switching tabs, prefer `Ctrl+1` to `Ctrl+8`, `Ctrl+9`, or tab search before clicking a tab.
- When a page is loading, wait briefly and verify the new page title, URL pattern, or visible hero/header before acting again.
- If a popup, permission prompt, or download shelf appears, treat it as the active surface and resolve it before continuing.

## Google Chrome

- Launch/focus strategy: `Win+S`, type `Chrome`, press `Enter`.
- Settings URL: `chrome://settings`
- Extensions URL: `chrome://extensions`
- Downloads URL: `chrome://downloads`
- History URL: `chrome://history`
- Profile-heavy flows should verify the avatar/profile button in the top right before proceeding.

## Microsoft Edge

- Launch/focus strategy: `Win+S`, type `Edge`, press `Enter`.
- Settings URL: `edge://settings`
- Extensions URL: `edge://extensions`
- Downloads URL: `edge://downloads`
- History URL: `edge://history/all`
- Edge-specific surfaces to recognize: the Copilot button, Collections button, and the `Settings and more` three-dot menu in the top right.

## Mozilla Firefox

- Launch/focus strategy: `Win+S`, type `Firefox`, press `Enter`.
- Settings URL: `about:preferences`
- Add-ons URL: `about:addons`
- Downloads shortcut: `Ctrl+J`
- Firefox-specific surfaces to recognize: hamburger menu, reader view icon, and tab search/menu controls near the tab strip.

## Brave

- Launch/focus strategy: `Win+S`, type `Brave`, press `Enter`.
- Settings URL: `brave://settings`
- Extensions URL: `brave://extensions`
- Brave-specific surface to recognize: the Shields lion icon in the address bar.

## Reliable Task Patterns

### Open a website
1. Focus the browser or open one.
2. Press `Ctrl+L`.
3. Type the full URL or search query.
4. Press `Enter`.
5. Verify the destination page loaded before interacting.

### Search within a site or page
1. Use the site search box if visible.
2. If searching page content, use `Ctrl+F`.
3. If searching browser history or downloads, use the dedicated page and its search input.

### Log in or complete sensitive actions
- Verify the exact site and account/profile surface first.
- Do not submit credentials, payments, sends, or deletes without confirmation if the action is externally impactful.

### Download and open a file
1. Trigger the download.
2. Use `Ctrl+J` if needed.
3. Verify the file name and status.
4. Open the file or show it in folder only after confirming the correct item.
