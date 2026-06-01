# Phase R: analyst workflow polish

**Date:** 2026-05-29
**Goal:** Improve the day-to-day Vivisect UI experience for human analysts using Viv-AI.

## Current state audit

| Area | What exists | What's missing |
|------|-------------|----------------|
| **Dock widget** | `AIHelperDockWidget` — class stub only, no Qt layout, no visual content | A usable panel with result display, controls, and state indicators |
| **Result rendering** | `render_analysis_result()` — plain-text string formatter | Rich text / HTML rendering with visual hierarchy |
| **History** | `AIHelperPanel.history` — raw list of dicts, no browsing UI | History list widget, click-to-view, clearance on stale entries |
| **Result comparison** | Nothing | Side-by-side or diff view for two analysis results |
| **Proposal queue** | `ReviewApplyPanel._queue` — FIFO list with apply/preview | Queue widget showing pending actions with per-item controls |
| **Provenance** | `render_analysis_result()` prints `Cache: hit/miss` | Visual badge/icon/color distinguishing cached from fresh |
| **Background jobs** | `BackgroundJobRunner` — synchronous `run_pending()` only | Threaded/async execution, progress bar, status indicators |

## Task breakdown

### R1: Qt dock widget — proper layout and result viewer

Build a real `AIHelperDockWidget(QtWidgets.QWidget)` layout with:

- **Toolbar row**: scope selector dropdown (Function / Binary / Graph), "Explain" button, "Queue" button
- **Result pane** (`QTextEdit` read-only): rich text rendering of analysis output — section headers in bold, evidence as bullet lists, confidence badges, colored cache provenance
- **Status bar**: current provider/model, cache state icon
- **Stretch**: resize-able splitter between controls and result

Also upgrade `render_analysis_result()` to produce HTML instead of plain text, with:
- Summary in bold heading
- Confidence as a colored badge (green=high, yellow=medium, red=low)
- Cache provenance badge (blue ribbon for fresh, gray for cached, with model name)
- Evidence rendered as a styled bullet list
- Provider/model footer row

### R2: History browser with comparison

- Add `QListWidget` to left side of the dock (or toggle panel)
- Each entry shows: abbreviated task type + function address or scope + cache badge + timestamp
- Clicking loads that result into the main result pane
- Select two entries + "Compare" button shows a `QDockWidget` with side-by-side or unified diff
- Compare view uses difflib to highlight differences in summary/evidence/confidence

### R3: Queue inspection and editing

- Add a "Queue" tab in the dock widget showing `ReviewApplyPanel.preview_queue()` contents
- Each row: VA address + "rename: X" / "comment: Y" / both + "Apply" / "Skip" / "Remove" buttons
- "Apply All" and "Skip All" batch controls
- Queue count badge on the tab label
- Queue persists across analysis runs within the same session

### R4: Provenance visualization

- Cache-hit results render with a distinct visual style:
  - Gray/silver border or background tint
  - Badge text: "CACHED — {provider}/{model} — {timestamp}"
  - Footer showing "Click to refresh" affordance
- Fresh results render with:
  - Blue/primary border or background tint
  - Badge text: "FRESH — {provider}/{model} — {timestamp}"
- Provider status widget shows connection type, model, and health

### R5: Background job progress UX

- Replace synchronous `BackgroundJobRunner.run_pending()` with a `QThread`-based worker
- Add `QProgressBar` to the dock widget that updates via signal/slot
- Add "Running: ⌛ Explain 0x401000 (72%)" status line
- Completed jobs appear in history automatically
- Cancellation support: "Cancel" button for running jobs

## Implementation order

1. **R1** — layout + HTML renderer (gives immediate visible improvement)
2. **R4** — provenance (interleaves naturally with R1 rendering work)
3. **R2** — history browser + comparison
4. **R3** — queue widget
5. **R5** — threaded background jobs with progress bar

## Acceptance criteria

- [ ] Dock widget shows a usable result viewer with scope selector and action buttons
- [ ] Analysis results render as structured HTML with bold summary, colored confidence, provenance badge
- [ ] Cache vs fresh results visually distinct (badge + border tint)
- [ ] History list populated after each analysis; clicking re-displays the result
- [ ] "Compare" on two history entries shows a diff view in a separate panel
- [ ] Queue tab lists pending proposals with per-item Apply/Skip/Remove
- [ ] Background analysis jobs show a progress bar with percentage + status message
- [ ] All existing tests continue to pass; new tests cover HTML rendering, history CRUD, queue manipulation, and threaded job lifecycle
