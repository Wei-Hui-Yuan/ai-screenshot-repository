# Design: AI Screenshot Repository

> **Status: spec, annotated with what was built.** Written on 2026-10-03 before any code. Sections 1 to 10 keep their original numbers because code and other docs cite them (`app/tagger.py` and `app/images.py` cite §6).
>
> The v1 UI is one page, `app/static/index.html`. Several features in the original design were **deferred, not dropped**. v1 exists to prove that Gemini's tags are good enough to search by, and phase 3 had 45 minutes, so the more advanced browsing and feedback features were postponed to a later version. Each section that was not built carries a **Designed but not built** note saying what it was and why it was designed that way, so the thinking is kept for when it is picked up.
>
> - The full original text is kept in Git: [design.md as first committed](https://github.com/Wei-Hui-Yuan/ai-screenshot-repository/blob/a02c83dbde4c44d1b0787cc82a7af9968fc39d87/planning/design/design.md).
> - What was built overall: [02-mvp-outcome.md](../project_plan/02-mvp-outcome.md).

How the app looks and behaves on screen. Scope, routes and data rules live in `planning/project_plan/01-full-plan.md`. This file covers only the UI.

| Designed feature | Section | Built in v1 instead |
|---|---|---|
| Category and place chips with counts | §4 | The search box. Tags in the detail dialog are clickable and run a search |
| "Load more" paging | §4 | The newest 40 |
| A separate `/image/{id}` page, filters kept in the URL, back/forward-cache handling | §3, §5 | A detail `<dialog>` on the one page |
| A toast stack with caps and timers | §6 | One status line and one alert line |
| Per-card polling | §6 | The grid re-fetches every 2 s while a card is pending and redraws only when something changed |
| A drag-over outline | §4 | Drops still work anywhere on the page |

## 1. Principles
- **Images first.** The screenshots are the content. Interface chrome stays quiet: no sidebars, banners or decoration.
- **Minimal, like a photo library.** White space, one accent colour, text only where it helps. No animation.
- **Follows the system theme.** Light or dark from `prefers-color-scheme`. No manual toggle in v1.
- **Quiet when normal, clear when not.** A tagged card needs no label. Pending, failed and flagged cards get one.
- **Data is text, never HTML.** Everything from the server (titles, summaries, tags, extracted text, messages) and every file name is inserted with `textContent` or DOM properties, never `innerHTML`. Screenshot text comes from Gemini and is untrusted. URL parts are built with `encodeURIComponent`.
- **Buildable in phase 3 (45 min).** One HTML file, vanilla CSS and JS, no web fonts, no external requests, no client-side router. Section 9 says what to build first and what to cut if time runs out.

## 2. Theme
Colours are CSS custom properties on `:root`, overridden in `@media (prefers-color-scheme: dark)`. Set `color-scheme: light dark` so native controls (checkbox, scrollbars, file picker) follow the theme.

Contrast was checked with a script, not by eye. Every text pair below passes WCAG AA (4.5:1), and every border and focus-ring pair passes 3:1, in both themes. Re-run the check if any value changes. (Correction #5: the first draft claimed this without computing it, and two pairs failed.)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#ffffff` | `#0c0a09` | Page background, search box background |
| `--surface` | `#f5f5f4` | `#1c1917` | Image placeholders, tag buttons, the extracted-text block |
| `--text` | `#1c1917` | `#f5f5f4` | Primary text |
| `--muted` | `#57534e` | `#a8a29e` | Place line, hints, metadata, privacy note, placeholder text |
| `--border` | `#e7e5e4` | `#292524` | Decorative dividers only (e.g. under the header) |
| `--border-strong` | `#78716c` | `#78716c` | Search box and secondary-button outlines, empty-state dashes |
| `--accent` | `#2563eb` | `#60a5fa` | Focus ring, primary button, links |
| `--on-accent` | `#ffffff` | `#0c0a09` | Text on the filled primary button |
| `--danger` | `#b91c1c` | `#f87171` | Failed text, Delete, the error box and the alert line's border |
| `--warning` | `#b45309` | `#fbbf24` | Flagged badge, flagged note border |

- **Type:** system font stack (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`). Base 15px. Card title 14px medium, place 13px, detail title 22px semibold.
- **Spacing:** 4, 8, 12, 16, 24, 32 px.
- **Shape:** 10px radius on images and cards, fully rounded tag buttons. No shadows. Borders separate things in both themes.
- **Links:** inline text links (e.g. "Clear all") are underlined, so they don't rely on colour alone.
- **Badges and notes are outlined, not filled:** coloured text or a 1px border in `--warning` / `--danger`, on a transparent or `--bg` background, with `--text` for body copy. This keeps them readable in both themes.
- **Motion:** none. Pending is shown by dimming plus a text label.

## 3. Navigation
**As built:** one page, no router and no second route. Clicking a card opens the detail in a `<dialog>` on top of the library. Drag and drop works anywhere on the page.

**Designed but not built (future work).** Every screenshot was to have its own page, `/image/{id}`, so that links, new tabs and the Back button work naturally:
- The server returns the same `index.html` for `/` and `/image/{id}`, and JS reads `location.pathname` to pick the view. The alternative, a client-side router, was ruled out as out of scope (correction #8).
- The library's query (`q`, `category`, `city`, `show_flagged`) lives in the URL via `history.replaceState`, and is also saved in `sessionStorage`, so "← Library" can be a real link that restores the same search. It never uses `history.back()`.
- Both views reload on `pageshow` when `event.persisted` is true. Browsers restore pages from the back/forward cache, so without this, Back after Retry or Delete would show out-of-date data (correction #9).
- Each view sets its own `document.title`.

Why deferred: a dialog on the one page needs none of this. The cost is that the search isn't in the URL, so a refresh clears it.

## 4. Library page (`/`)
```
AI Screenshot Repository                         [ ] Show flagged   [Add screenshots]
Screenshots are sent to Google Gemini (free tier) for tagging. Don't upload anything private.

[ Search screenshots...                                                           ]
Showing 12 screenshots.                      <- status line; the alert line sits below it

+--------+ +--------+ +--------+ +--------+
|        | |        | |        | |        |
|  img   | |  img   | |  img   | |  img   |
+--------+ +--------+ +--------+ +--------+
Ramen shop  Tagging...  Temple guide  Tagging failed
Tokyo, Japan            Kyoto, Japan  Rate limit reached
```

**Header.** App name on the left. On the right: the "Show flagged" checkbox (always visible, no count) and the "Add screenshots" primary button, which opens the file picker. The privacy note sits directly under the header in `--muted`, visible whenever the library is. Together with drop-anywhere, this is the plan's "dropzone with privacy warning".

**Search.** `<input type="search" aria-label="Search screenshots">`, full width, `--bg` background, 1px `--border-strong` outline, placeholder text in `--muted`. Results update 250 ms after typing stops. After each search, the status line reads "Showing 12 screenshots." (or the no-results message).

**Grid.**
- `repeat(auto-fill, minmax(180px, 1fr))`, 16px gap, max width 1200px, centred.
- Thumbnails sit in a fixed 3:4 frame cropped from the top (`object-fit: cover; object-position: top`), because the top of a screenshot usually carries the headline.
- Newest first, the newest 40 cards.

**Card states**
| State | Thumbnail | Text under the image |
|---|---|---|
| Pending | Dimmed (50% opacity) | "Tagging..." in `--muted` |
| Tagged | Normal | Title (one line, truncated; "Untitled screenshot" if empty), then the place line: "City, Country", "Country", or an empty line kept for alignment |
| Failed | Dimmed | "Tagging failed" in `--danger`, then the short reason in `--muted` (section 6 lists them) |
| Flagged (only shown when "Show flagged" is on) | Normal | Title and place, plus an outlined "Flagged" badge in `--warning` |

Each card is a single `<button>` that opens the detail dialog. The thumbnail has `alt=""`, because the card's visible text already names the button.

**Uploading.**
- Two ways in: the "Add screenshots" button, or dropping files anywhere on the page.
- More than 20 files chosen: send nothing, and show the error "You can add up to 20 screenshots at a time."
- Otherwise send them in one `POST /api/images`, with the status "Uploading 10 screenshots...". There are no type or size checks in the browser: the server's per-file results are the only source of truth.
- The server returns per-file results in the order the files were sent. The UI pairs each result with that file's `File.name`.
- When the response arrives: show one summary message (section 6), clear the search box, reset the pending set from the results, and re-fetch the grid (new pending cards come first).

**Empty library.** When there are no screenshots at all, the grid area shows a dashed `--border-strong` box: "Drop screenshots here, or use Add screenshots above." and "PNG, JPEG or WebP, up to 10 MB each, 20 at a time." Drops are handled by the same page-wide handler.

**No results.** 'No screenshots match "{q}".' when there's a query, otherwise "No screenshots match these filters." Followed by an underlined "Clear all" button, which empties the search box and unticks Show flagged. Any query, including odd characters like `"` or `*`, shows results or this message, never an error (AC-9).

**Designed but not built (future work).**
- **Category and place chips** (J3, "Click Travel, then Kyoto"). Two rows of toggle buttons, "All" / "All places" pressed by default, with counts from `GET /api/facets`. The category row is the five categories the tagger uses: Travel, Food, Article, Receipt, Other. The place row is cities. Counts covered tagged, unflagged images and did not narrow when a category was selected, so "Kyoto 3" could show fewer cards inside "Food". Why: browsing by group without typing, as the plan's F4. Built instead: search, plus clickable tags in the detail dialog.
- **"Load more".** It showed when the last request returned a full page, fetched the next 40, skipped cards already on screen and moved focus to the first new card. Why: libraries over 40. Built instead: the newest 40.
- **A drag-over outline.** A dashed `--accent` outline around the grid while files are dragged over the page, drawn by a class on `<body>` with no overlay element.

## 5. Detail view
Built as a `<dialog>` opened from a card. Native `<dialog>` behaviour (Esc to close) applies, and clicking the backdrop closes it too.
```
+----------------------------------------------------------+
| +----------------------+   Ramen shop near Shinjuku      |
| |                      |   Tokyo, Japan . food           |
| |        image         |                                 |
| |  (whole screenshot,  |   One or two summary sentences. |
| |     not cropped)     |                                 |
| |                      |   ramen   shinjuku   restaurant |
| +----------------------+   > Text in image               |
|                            Added 3 Oct 2026 . <model> .  |
|                            prompt v1                     |
|                            [Retry tagging] [Delete] [Close]
+----------------------------------------------------------+
```
- **Layout:** two columns (image about 60%), stacked below 760px. The image is shown whole (`object-fit: contain`, max height 80vh). Its alt text is the title, or "Screenshot, tagging in progress" / "Screenshot, tagging failed".
- **Fields:** title (the dialog's heading), place and category on one line, summary, tags, then extracted text in a collapsed `<details>` ("Text in image"). Empty fields are left out, not shown blank.
- **Tags** are buttons. Clicking one closes the dialog and runs that search.
- **Metadata line:** date added, model and prompt version, in `--muted`, shown once tagged. There for the eval.
- **Actions:** "Retry tagging" (outlined secondary button), "Delete" (text button in `--danger`) and "Close". Retry is disabled while pending. Delete asks "Delete this screenshot? This can't be undone." with the browser's `confirm()`, then closes the dialog and refreshes the grid. *As built: "Retry tagging" is shown only on failed images, not on tagged or pending ones (correction #40). Retrying a tagged image cleared its tags first, so a failed retry left it unsearchable. The mockup above shows the original design.*
- **Pending:** the title reads "Tagging..." and the dialog refreshes itself with the library's 2 s polling until tagging settles. Retry puts it back into this state.
- **Failed:** an error box above the fields (`--bg`, 1px `--danger` border, `--text`) shows the reason (section 6) and "Use Retry tagging to try again." There's only one retry control: the button in the actions row.
- **Flagged:** a note above the fields with a 1px `--warning` border: "Flagged: may contain personal info."
- **Not found** (a bad or deleted id): "This screenshot isn't in your library." with a Close button.

**Designed but not built:** the same content as a full page at `/image/{id}`, two columns from 900px, with a "← Library" link, tags as links to `/?q=…`, and Delete leaving via `location.replace` so Back can't return to the deleted screenshot. See section 3 for why it was deferred.

## 6. Feedback
**As built.** Two lines under the search box, siblings and never nested: a visible `role="status"` line for info and success messages, and a visible `role="alert"` line for errors. Each new message replaces the previous one. Errors start with "Error:" and have a 4px `--danger` left border.

**Designed but not built (future work): a toast stack.**
- Bottom-right on wide screens, bottom-centre on narrow ones, with room at the bottom of `main` so toasts can't cover the last row.
- Info and success toasts close after 5 s, with the timer paused while hovered or focused. "Uploading..." has no timer and is removed when the response arrives. Error toasts stay until dismissed.
- At most 3 visible. A fourth removes the oldest info or success toast, and an error is removed only when all 3 are errors.
- One grouped toast per poll, not one per failed image.
- A third, visually hidden `role="status"` element for screen-reader announcements that don't count as toasts.

Why it was designed that way: an error must not vanish before it is read (AC-6, AC-7), and the first draft's rules contradicted each other (correction #10). Why deferred: toasts are the most involved part of the UI (timers, caps, pause logic) for a polish gain, and one status line plus one alert line carry the same messages.

**Upload summary: one message built from the server's per-file results.** Each part appears only when its count isn't zero:
- "Added 7 screenshots."
- "2 already in your library."
- "Not added: holiday.gif (not PNG, JPEG or WebP), big.png (over 10 MB)."

It goes to the alert line if anything was rejected, and the status line otherwise.

| Event | Message |
|---|---|
| More than 20 files chosen | "You can add up to 20 screenshots at a time." (alert) |
| Upload sent | "Uploading 10 screenshots..." (status) |
| Upload finished | The summary above |
| Network error | "Upload failed. Check the app is running and try again." (alert) |
| The library can't be loaded | "Could not load the library. Is the app running?" (alert, retried every 5 s) |
| Tagging failed (seen by polling) | "Tagging failed for {n} screenshot(s)." (alert) |
| Newly flagged while "Show flagged" is off | "{n} screenshot(s) hidden: may contain personal info. Turn on Show flagged to see them." (status; the failure message wins if both happen in one poll) |

**Server messages.** The server sends these fixed messages and the UI shows them as-is. Raw exception details go to the server console only, never to the UI.

| Upload rejected because | Per-file error |
|---|---|
| Not PNG, JPEG or WebP | "not PNG, JPEG or WebP" |
| Over 10 MB | "over 10 MB" |
| Corrupt, or too many pixels | "unreadable image" |
| Anything else | "could not be added" |

| Tagging failed because | Stored in `error` |
|---|---|
| Gemini rate limit | "Rate limit reached" |
| Response failed validation | "Unreadable response from Gemini" |
| Server stopped mid-tagging | "Interrupted: the app was closed while tagging" |
| Anything else | "Tagging error" |

**Polling on the library, as built.**
- While any card is pending (or the open dialog is), the page re-fetches the library every 2 s, using the current search and Show flagged setting.
- It redraws the grid only when the list changed, so focus and loaded thumbnails survive polling.
- A slow answer to an older search is ignored: only the newest request may change the page.
- A failed fetch shows the error above and retries every 5 s. The error clears once the library loads again.
- The page keeps the set of pending IDs. An ID that is no longer pending is checked: if it failed it is counted for the failure message, and if it is missing from the list it is fetched by id, and counted as hidden when it turned out to contain personal info (AC-8). An ID deleted in the meantime is ignored.

**Designed but not built:** per-card polling. The page was to poll `GET /api/images?status=pending` every 2 s, then replace, remove or add single cards and never re-fetch the grid. Why: the first draft polled only while a visible card was pending, so with a search active new uploads never updated (correction #6), and per-card replacement keeps focus and thumbnails. The as-built change detection gets the same result with less code.

## 7. Accessibility
- All text, border and focus-ring colour pairs pass WCAG AA in both themes (section 2).
- Status is never shown by colour alone: every state has a text label, and inline links are underlined.
- Visible focus ring on every interactive element: 2px `--accent` outline, offset 2px.
- Everything works by keyboard:
  - "Add screenshots" is a real `<button>` driving a hidden `<input type="file" multiple accept="image/png,image/jpeg,image/webp">`.
  - Cards, tags, Retry, Delete and Close are buttons.
  - "Show flagged" is a labelled checkbox.
- Card thumbnails use `alt=""`. The detail image has descriptive alt text.
- Search results, upload results and tagging results are announced through the `role="status"` and `role="alert"` lines.

## 8. Responsive
- Grid columns follow the width. At phone width (600px and below) cards shrink to a 140px minimum (two columns).
- 16px side padding on small screens.
- The detail dialog stacks below 760px.

## 9. Build order and cuts
Phase 3 had 45 minutes, so the design came with an order and a cut list. The order:
1. Grid with all four card states, and the detail with its fields, Retry and Delete (J1, J2, F5, F6, AC-10).
2. Search box and chips (J2, J3, AC-9).
3. Upload by button and by drop, with the summary message (J1, J4, J7, AC-6).
4. Polling, with the tagging-failed and hidden messages (J1, J5, J6, AC-1, AC-7, AC-8).
5. The "Show flagged" toggle (J6, AC-8).

The planned cuts, if time ran out, in this order: "Load more", the toast timer pause, the search-result announcement, the drag outline. The rule: never cut anything mapped to a journey or acceptance criterion, and never cut the "data is text" rule.

**What happened.** The build went further than the cut list: the chips, the `/image/{id}` page, toasts and per-card polling were also deferred, and the drag outline and timer pause went with the features they belonged to. The search announcement was kept. Every journey except J3 works, and all 14 acceptance criteria still hold ([02-mvp-outcome.md](../project_plan/02-mvp-outcome.md)). Tags in the detail dialog stand in for J3.

## 10. Trade-offs and out of scope
- **No separate thumbnails.** The grid uses the stored 1600px WebP with `loading="lazy"`. That's heavier than real thumbnails but fine for hundreds of images. Thumbnails are future work.
- **One page, not a router or a second route.** Simplest to build. The cost: the search isn't in the URL, so a refresh clears it, and the grid shows only the newest 40.
- **Uploading clears the search box** (not the Show flagged checkbox), so new cards are visible.
- **Deferred, not cut for good:** the features in the table at the top are future work.
- **Out of scope for v1:** manual theme toggle, animation, keyboard shortcuts, a full-page drop overlay, masonry layout, lightbox or slideshow, bulk select and delete, infinite scroll, editing tags in the UI (stretch S1 only).
