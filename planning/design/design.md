# Design: AI Screenshot Repository

> **MVP scope (2026-10-03).** Built as one page (`app/static/index.html`). **Superseded:** §3 (one page, no second route, no `pageshow` handling), §4 chips and "Load more", §5 as a page (it is a `<dialog>`), §6 toasts, per-card polling and the cap rules (one status line and one alert line; the grid re-fetches every 2 s while a card is pending). Colour tokens, card states, "data is text, never HTML" and the fixed server messages are unchanged. See `planning/project_plan/02-mvp-outcome.md`.

How the app looks and behaves on screen. Scope, routes and data rules live in `planning/project_plan/01-full-plan.md`. This file covers only the UI.

## 1. Principles
- **Images first.** The screenshots are the content. Interface chrome stays quiet: no sidebars, banners or decoration.
- **Minimal, like a photo library.** White space, one accent colour, text only where it helps. No animation.
- **Follows the system theme.** Light or dark from `prefers-color-scheme`. No manual toggle in v1.
- **Quiet when normal, clear when not.** A tagged card needs no label. Pending, failed and flagged cards get one.
- **Data is text, never HTML.** Everything from the server (titles, summaries, tags, extracted text, messages) and every file name is inserted with `textContent` or DOM properties, never `innerHTML`. Screenshot text comes from Gemini and is untrusted. URL parts are built with `encodeURIComponent`.
- **Buildable in phase 3 (45 min).** One HTML file, vanilla CSS and JS, no web fonts, no external requests, no client-side router. Section 9 says what to build first and what to cut if time runs out.

## 2. Theme
Colours are CSS custom properties on `:root`, overridden in `@media (prefers-color-scheme: dark)`. Set `color-scheme: light dark` so native controls (checkbox, scrollbars, file picker) follow the theme.

Contrast was checked with a script, not by eye. Every text pair below passes WCAG AA (4.5:1), and every border and focus-ring pair passes 3:1, in both themes. Re-run the check if any value changes.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#ffffff` | `#0c0a09` | Page background, search box background |
| `--surface` | `#f5f5f4` | `#1c1917` | Chips, toasts, image placeholders |
| `--text` | `#1c1917` | `#f5f5f4` | Primary text |
| `--muted` | `#57534e` | `#a8a29e` | Place line, hints, metadata, privacy note, placeholder text |
| `--border` | `#e7e5e4` | `#292524` | Decorative dividers only (e.g. under the header) |
| `--border-strong` | `#78716c` | `#78716c` | Search box and secondary-button outlines, toast border, empty-state dashes |
| `--accent` | `#2563eb` | `#60a5fa` | Focus ring, selected chip, primary button, links, drag outline |
| `--on-accent` | `#ffffff` | `#0c0a09` | Text on a filled accent (selected chip, primary button) |
| `--danger` | `#b91c1c` | `#f87171` | Failed text, Delete, error box and error-toast border |
| `--warning` | `#b45309` | `#fbbf24` | Flagged badge, flagged note border |

- **Type:** system font stack (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`). Base 15px. Card title 14px medium, place 13px, detail title 22px semibold.
- **Spacing:** 4, 8, 12, 16, 24, 32 px.
- **Shape:** 10px radius on images and cards, fully rounded chips. No shadows. Borders separate things in both themes.
- **Links:** inline text links (e.g. "Clear all") are underlined, so they don't rely on colour alone.
- **Badges and notes are outlined, not filled:** coloured text or a 1px border in `--warning` / `--danger`, on a transparent or `--bg` background, with `--text` for body copy. This keeps them readable in both themes.
- **Motion:** none. Pending is shown by dimming plus a text label.

## 3. Navigation
- Every page change is a normal full page load through a real `<a href>`. There is no client-side router.
- The server returns the same `index.html` for `/` and `/image/{id}`. On load, JS reads `location.pathname` and renders the library or the detail view.
- **Always fresh data.** Browsers can restore a page from their back/forward cache without reloading it. Both views listen for `pageshow`, and if `event.persisted` is true they call `location.reload()`.
- Each view sets `document.title`: "Library – AI Screenshot Repository", or "{title} – AI Screenshot Repository".
- The library's URL query uses the API's own keys: `q`, `category`, `city`, `show_flagged`. Search, chips and the toggle re-fetch the first page in place, update the URL with `history.replaceState`, and pass the same query string to `GET /api/images`. The library also saves that query string in `sessionStorage`, so the detail page can link back to the same view.
- Drag and drop works on the library view only. The detail page ignores drops.

## 4. Library page (`/`)
```
AI Screenshot Repository                         [ ] Show flagged   [+ Add screenshots]
Screenshots are sent to Google Gemini (free tier) for tagging. Don't upload anything private.

[ Search screenshots...                                                           ]
(All) (Travel 12) (Food 8) (Article 4) (Receipt 2) (Other 3)          <- Category group
(All places) (Tokyo 6) (Kyoto 3) (London 2)                              <- Place group

+--------+ +--------+ +--------+ +--------+
|        | |        | |        | |        |
|  img   | |  img   | |  img   | |  img   |
+--------+ +--------+ +--------+ +--------+
Ramen shop  Tagging...  Temple guide  Tagging failed
Tokyo, Japan            Kyoto, Japan  Rate limit reached

                          [ Load more ]
```

**Header.** App name on the left. On the right: the "Show flagged" checkbox (always visible, no count) and the "Add screenshots" primary button, which opens the file picker. The privacy note sits directly under the header in `--muted`, visible whenever the library is. Together with drop-anywhere, this is the plan's "dropzone with privacy warning".

**Search.** `<input type="search" aria-label="Search screenshots">`, full width, `--bg` background, 1px `--border-strong` outline, placeholder text in `--muted`. Results update 250 ms after typing stops. After each search, the announcement region (section 6) reads "Showing 12 screenshots." or the no-results message.

**Chips.**
- Two rows, each a `role="group"`: `aria-label="Category"` and `aria-label="Place"`. Chips are buttons with `aria-pressed`. Exactly one per row is pressed: "All" / "All places" by default. Pressing the selected chip leaves it selected.
- The selected chip is filled with `--accent`, with `--on-accent` text.
- Place chips are cities and set `city`. A screenshot with only a country appears under "All places" only.
- Counts come from `GET /api/facets`. They cover tagged, unflagged images (the default view) and don't narrow when a category is selected.
- A row that overflows scrolls sideways, with 4px padding so focus rings aren't clipped.
- Facets load with the page and refresh when polling sees tagging finish.

**Grid.**
- `repeat(auto-fill, minmax(180px, 1fr))`, 16px gap, max width 1200px, centred.
- Thumbnails sit in a fixed 3:4 frame cropped from the top (`object-fit: cover; object-position: top`), because the top of a screenshot usually carries the headline.
- Newest first, 40 cards per page. "Load more" shows only when the last request returned a full page. It fetches the next 40, skips any card already on screen, and moves focus to the first new card. If nothing new arrives, it removes the button and focuses the last card.

**Card states**
| State | Thumbnail | Text under the image |
|---|---|---|
| Pending | Dimmed (50% opacity) | "Tagging..." in `--muted` |
| Tagged | Normal | Title (one line, truncated; "Untitled screenshot" if empty), then the place line: "City, Country", "Country", or an empty line kept for alignment |
| Failed | Dimmed | "Tagging failed" in `--danger`, then the short reason in `--muted` (section 6 lists them) |
| Flagged (only shown when "Show flagged" is on) | Normal | Title and place, plus an outlined "Flagged" badge in `--warning` |

Each card is a single `<a href="/image/{id}">`. The thumbnail has `alt=""`, because the card's visible text already names the link.

**Uploading.**
- Two ways in: the "Add screenshots" button, or dropping files anywhere on the library view. While files are dragged over the page, `<body>` gets a class that draws a dashed `--accent` outline around the grid. There's no overlay element.
- More than 20 files chosen: send nothing, and show the error toast "You can add up to 20 screenshots at a time."
- Otherwise send them in one `POST /api/images`, with the info toast "Uploading 10 screenshots...". There are no type or size checks in the browser: the server's per-file results are the only source of truth.
- The server returns per-file results in the order the files were sent. The UI pairs each result with that file's `File.name`.
- When the response arrives: remove the "Uploading" toast, add the new pending IDs to the polling set, clear search and filters, re-fetch the first page (new pending cards come first), and show one summary toast (section 6).

**Empty library.** When there are no screenshots at all, the grid area shows a dashed `--border-strong` box: "Drop screenshots here, or use Add screenshots above." and "PNG, JPEG or WebP, up to 10 MB each, 20 at a time." Drops are handled by the same page-wide handler.

**No results.** 'No screenshots match "{q}".' when there's a query, otherwise "No screenshots match these filters." Followed by an underlined "Clear all" link. Any query, including odd characters like `"` or `*`, shows results or this message, never an error (AC-9).

## 5. Detail page (`/image/{id}`)
```
<- Library

+----------------------+   Ramen shop near Shinjuku station
|                      |   Tokyo, Japan . Food
|                      |
|        image         |   One or two summary sentences from Gemini.
|  (whole screenshot,  |
|     not cropped)     |   ramen   shinjuku   restaurant
|                      |
|                      |   > Text in image
+----------------------+
                           Added 3 Oct 2026 . <model> . prompt v1
                           [Retry tagging]  [Delete]
```
- **Layout:** two columns at 900px and wider (image about 60%), stacked below that. The image is shown whole (`object-fit: contain`, max height 80vh). Its alt text is the title, or "Screenshot, tagging in progress" / "Screenshot, tagging failed".
- **Fields:** title (the page's `h1`), place and category on one line, summary, tags, then extracted text in a collapsed `<details>` ("Text in image"). Empty fields are left out, not shown blank.
- **Tags** are links to `/?q=` plus the URL-encoded tag.
- **Metadata line:** date added, model and prompt version, in `--muted`. There for the eval.
- **Actions:** "Retry tagging" (outlined secondary button) and "Delete" (text button in `--danger`). Retry is disabled while pending. Delete asks "Delete this screenshot? This can't be undone." with the browser's `confirm()`, then goes to the library with `location.replace`, so Back doesn't return to the deleted screenshot.
- **Pending:** fields show "Tagging..." and the page polls `GET /api/images/{id}` every 2 s. When it settles, the announcement region reads "Tagging finished." or "Tagging failed.". Retry puts the page back into this state.
- **Failed:** an error box above the fields (`--bg`, 1px `--danger` border, `--text`) shows the reason (section 6) and "Use Retry tagging to try again." There's only one retry control: the button in the actions row.
- **Flagged:** a note above the fields with a 1px `--warning` border: "Flagged: may contain personal info."
- **Not found** (a bad or deleted id): "This screenshot isn't in your library." with a link to the library.
- **"<- Library"** is a real link to `/` plus the library query saved in `sessionStorage`, so search and filters come back. With nothing saved, it's plain `/`. It never uses `history.back()`.

## 6. Feedback
**Live regions.** Three elements exist in the page from load:
- A visible `role="status"` container for info and success toasts.
- A visible `role="alert"` container for error toasts, a sibling of the first, never nested inside it.
- A visually hidden `role="status"` element for screen-reader announcements (search results, "Tagging finished."). Announcements are not toasts and don't count toward the toast limit.

**Toasts.**
- Bottom-right on wide screens, bottom-centre on narrow ones.
- Style: `--surface` background, 1px `--border-strong` border, `--text`. Error toasts add a 4px `--danger` left border and start with "Error:".
- Info and success toasts close after 5 seconds. The timer pauses while the toast is hovered or focused. The "Uploading..." toast has no timer and is removed when the response arrives.
- Error toasts stay until closed with their "Dismiss" button.
- At most 3 visible. When a fourth arrives, the oldest info or success toast goes first. An error toast is removed only when all 3 visible toasts are errors.
- On narrow screens, `main` has about 120px of bottom padding so toasts can't cover the last row or "Load more".

**Upload summary: one toast built from the server's per-file results.** Each part appears only when its count isn't zero:
- "Added 7 screenshots."
- "2 already in your library."
- "Not added: holiday.gif (not PNG, JPEG or WebP), big.png (over 10 MB)."

It uses the error style if anything was rejected, and the success style otherwise.

| Event | Toast |
|---|---|
| More than 20 files chosen | "You can add up to 20 screenshots at a time." (error) |
| Upload sent | "Uploading 10 screenshots..." (info, no timer) |
| Upload finished | The summary toast above |
| Network error | "Upload failed. Check the app is running and try again." (error) |
| Tagging failed (seen by polling) | "Tagging failed for {n} screenshot(s)." (error, at most one per poll) |
| Newly flagged while "Show flagged" is off | "{n} screenshot(s) hidden: may contain personal info. Turn on Show flagged to see them." (info, at most one per poll) |

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

**Polling on the library.**
- The page keeps a set of pending IDs. IDs are added from upload results and from pending cards that load. They leave the set only when they settle, so the set survives search and filter changes.
- While the set isn't empty, call `GET /api/images?status=pending` every 2 s. Stop when it's empty.
- When an ID is missing from that response, fetch `GET /api/images/{id}`:
  - Still pending: keep it in the set. This covers more pending images than fit in one page.
  - Tagged: replace that card if it's on screen.
  - Failed: replace the card if it's on screen, and count it for this poll's tagging-failed toast.
  - Flagged while "Show flagged" is off: remove the card if it's on screen, and count it for this poll's hidden toast (AC-8).
  - Gone (404): remove the card if it's on screen.
- After a poll that changed anything, show at most one tagging-failed toast and one hidden toast, then refresh the chip counts once.
- Polling only ever replaces or removes single cards. It never re-fetches the grid.

## 7. Accessibility
- All text, border and focus-ring colour pairs pass WCAG AA in both themes (section 2).
- Status is never shown by colour alone: every state has a text label, and inline links are underlined.
- Visible focus ring on every interactive element: 2px `--accent` outline, offset 2px.
- Everything works by keyboard:
  - "Add screenshots" is a real `<button>` driving a hidden `<input type="file" multiple accept="image/png,image/jpeg,image/webp">`.
  - Chips are buttons in labelled groups.
  - "Show flagged" is a labelled checkbox.
  - Error toasts have a Dismiss button.
- Card thumbnails use `alt=""`. The detail image has descriptive alt text.
- Each view has its own `document.title`, and the detail title is the page's `h1`.
- Search results and tagging results are announced through the hidden announcement region. Toasts are announced through their own live regions.

## 8. Responsive
- Grid columns follow the width. At phone width cards shrink to a 140px minimum (two columns).
- 16px side padding on small screens. No horizontal page scroll: only the chip rows scroll sideways.
- The detail page stacks below 900px.

## 9. Build order
Phase 3 has 45 minutes. Build in this order:
1. Grid with all four card states, and the detail page with its fields, Retry and Delete (J1, J2, F5, F6, AC-10).
2. Search box and both chip rows, with URL sync (J2, J3, AC-9).
3. Upload by button and by drop, with the summary toast (J1, J4, J7, AC-6).
4. Polling, with the tagging-failed and hidden toasts (J1, J5, J6, AC-1, AC-7, AC-8).
5. The "Show flagged" toggle (J6, AC-8).

If time runs out, cut in this order: "Load more" (show the newest 40 only), the toast timer pause, the search-result announcement, the drag outline. Never cut anything mapped to a journey or acceptance criterion, and never cut the "data is text" rule.

## 10. Trade-offs and out of scope
- **No separate thumbnails.** The grid uses the stored 1600px WebP with `loading="lazy"`. That's heavier than real thumbnails but fine for hundreds of images. Thumbnails are future work.
- **Full page loads, not a client-side router.** Simpler to build, but coming back to the library shows only the first 40 results again.
- **Chip counts are global and leave out flagged images.** They don't narrow when a category is selected, so "Kyoto 3" can show fewer cards inside "Food".
- **Uploading clears search and filters,** so new cards are always visible.
- **Out of scope for v1:** manual theme toggle, animation, keyboard shortcuts, a full-page drop overlay, masonry layout, lightbox or slideshow, bulk select and delete, infinite scroll, editing tags in the UI (stretch S1 only).
