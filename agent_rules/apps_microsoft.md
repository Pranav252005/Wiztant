# Microsoft Apps Rules

## Shared Microsoft App Principles

- Prefer `Win+S` to launch the app, then verify the window title or the main canvas before acting.
- Prefer app search boxes, ribbon tabs, sidebars, and dialog buttons over arbitrary clicks in blank canvas areas.
- When a file picker or save dialog appears, treat the dialog as the active surface until it is closed.
- Before saving, exporting, printing, sending, or closing with unsaved changes, verify the document/workbook/presentation state.

## Microsoft Word

- Launch/focus: `Win+S`, type `Word`, press `Enter`.
- Common shortcuts:
  - `Ctrl+N` new document
  - `Ctrl+O` open
  - `Ctrl+S` save
  - `F12` Save As
  - `Ctrl+P` print
  - `Ctrl+F` find
  - `Ctrl+H` replace
  - `Ctrl+B`, `Ctrl+I`, `Ctrl+U` formatting
- Prefer the ribbon tabs `Home`, `Insert`, `Layout`, `References`, and `Review` when a visible toolbar action is needed.

## Microsoft Excel

- Launch/focus: `Win+S`, type `Excel`, press `Enter`.
- Common shortcuts:
  - `Ctrl+N` new workbook
  - `Ctrl+O` open
  - `Ctrl+S` save
  - `F12` Save As
  - `Ctrl+F` find
  - `Ctrl+H` replace
  - `Ctrl+Arrow` move to data edge
  - `Ctrl+Shift+L` toggle filters
  - `Alt+=` autosum
- Prefer precise sheet, cell, formula bar, Name Box, and ribbon targets.
- Verify the active sheet tab and selected range before editing values.

## Microsoft PowerPoint

- Launch/focus: `Win+S`, type `PowerPoint`, press `Enter`.
- Common shortcuts:
  - `Ctrl+N` new presentation
  - `Ctrl+O` open
  - `Ctrl+S` save
  - `F12` Save As
  - `Ctrl+M` new slide
  - `F5` start slideshow
  - `Shift+F5` start from current slide
- Prefer the slide thumbnail sidebar for navigation and the ribbon for insert/layout/design changes.

## Microsoft Outlook

- Launch/focus: `Win+S`, type `Outlook`, press `Enter`.
- Common shortcuts:
  - `Ctrl+N` new item
  - `Ctrl+Shift+M` new email
  - `Ctrl+Enter` send current email
  - `F9` send/receive
  - `Ctrl+R` reply
  - `Ctrl+Shift+R` reply all
- Treat send actions as externally impactful and confirm before sending if user intent is not explicit.

## File and Dialog Handling

### Open or save a document
1. Trigger `Ctrl+O`, `Ctrl+S`, or `F12` as appropriate.
2. Wait for the file dialog.
3. Verify the filename field, folder path, and primary action button.
4. Confirm the file operation only after the correct target is visible.

### Export, print, or share
- Prefer the app's built-in `File` flow or the relevant shortcut.
- Confirm the destination, printer, format, or recipient surface before the final submit action.

## Verification Rules

- Word: verify the document canvas, title, and insertion point.
- Excel: verify workbook name, sheet tab, selected cell/range, and visible formula/value.
- PowerPoint: verify slide thumbnail selection and visible slide canvas.
- Outlook: verify recipient, subject, and compose body before send.
