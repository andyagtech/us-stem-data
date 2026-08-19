# PhD Demographics — Rich Chat Response Contract (v2)

Status: SPECIFICATION. Nothing here is implemented. Two implementers (backend / frontend)
build to this document.

Date: 2026-08-18
Author: study-and-specify pass over the two reference products + the current baseline.

---

## 0. TL;DR for implementers

- Wire format stays a **single buffered JSON POST response** from one Lambda. No SSE, no WebSocket.
- The response gains one new top-level key: **`blocks`** — an ordered array of render instructions.
- `reply` (the existing markdown string) stays, for back-compat and as the text-only fallback.
- `actions` (the existing `navigate`/`query` array) stays for one release, mirrored from `blocks`, then dies.
- Nine block types, all required for v2: `text`, `chart`, `table`, `stat`, `nav`, `link`, `query`,
  `suggest`, `notice`. A tenth, `page_action`, is specified but **deferred** (§4.5.11).
- **Navigation and links carry a site-relative URL, not a page/section pair.** Fragments are opaque:
  the contract never defines, parses or pattern-matches one (§4.5.5). This is deliberate — the site's
  anchor scheme is being rationalised in parallel.
- The model never emits HTML, never emits a Chart.js config, never emits a colour. It emits
  **data + a semantic role**; the widget owns all presentation.
- The model never invents chart numbers. Numbers come from **server-side data tools** reading
  artifacts bundled into the Lambda zip.
- Backend owns: tool schemas, tool execution, block construction, validation, clamping.
- Frontend owns: block rendering, Chart.js config synthesis, palette, sanitisation, navigation.

---

## 1. How the reference products do rich responses

### 1.1 Benefits Pal / Trinet — `/Users/andy/POST_PURLPAL/healthresourcepal`

**Wire format: deliberately minimal.** Both chat routes return a flat JSON object with a
single prose string. There is no block array and no structured payload on the wire.

- `src/app/api/demo-chat/route.ts` — `POST()`, final return is
  `NextResponse.json({ content, model })`. `content` is
  `response.choices?.[0]?.message?.content`. Nothing else.
- `src/app/api/chat/route.ts` — `POST()` returns `NextResponse.json({ content: response.content, model: response.model })`
  via the local `callChat(messages, model)` helper. Same two keys.
- Request shape (`src/app/api/demo-chat/route.ts`, top of `POST`):
  `{ message, conversationHistory = [], model = "gpt-4o", currentPage = "" }`.
  `currentPage` is turned into a system-prompt suffix, not a structured field:
  ```ts
  const contextNote = currentPage
    ? `\n[The user is currently viewing the "${currentPage}" page in the benefits portal.]`
    : "";
  ```

**Richness is achieved entirely client-side, by parsing the prose.** This is the key idea and the
one the user will expect to recognise.

- `src/app/demo/trinet/markdownParser.ts` — 134 lines, zero dependencies.
  - `parseBlocks(text): TextBlock[]` splits raw text into `{type:"paragraph"|"list"|"heading", text?, items?, level?}`.
    Headings are `/^(#{1,3})\s+(.+)$/`; list items are lines starting `"- "` or `"• "`; everything
    else accumulates into a paragraph until a blank line flushes it.
  - `parseInlineMarkdown(text): InlineToken[]` tokenises with `/(\*\*(.+?)\*\*|\*(.+?)\*)/g` into
    `{kind:"text"|"bold"|"italic", value}`. Bold is matched before italic on purpose.
  - The file header comments name the supported surface exactly: *"Block-level: paragraphs, bullet
    lists, headings. Inline: bold, italic. Navigation tokens: `[[page_id]]`."*
- `src/app/demo/trinet/page.tsx`:
  - `renderMessageContent(content)` calls `parseBlocks` and maps each block to a `<div>`/`<ul>`/`<p>`.
  - `renderInlineSegment(text, baseKey)` first splits on `/(\[\[[a-z_]+\]\])/g`, then applies
    `parseInlineMarkdown` to the non-token parts.
  - README.md lines 284–285 and 327–330 document this pipeline as the product's "Rich Rendering".

**Navigation is an inline token in the prose, not a tool call.**

- The model is instructed to emit `[[page_id]]` inline. From `DEMO_SYSTEM_PROMPT` in
  `src/app/api/demo-chat/route.ts`, section "## Navigation Instructions":
  > *"When the user asks about a specific benefit or you reference a plan, include the relevant
  > `[[page_id]]` tag so the portal can navigate there. Use exactly one set of double brackets with
  > the page ID. You may include multiple tags if referencing multiple pages."*
- The same prompt carries a "## Portal Site Navigation Map" listing every valid id
  (`[[my_benefits]]`, `[[carriers]]`, `[[medical]]`, `[[std]]`, `[[ltd]]`, …) with a one-line
  description of each page, plus a "Plan Documents Available on Each Page" table so the model knows
  which page holds which PDF.
- The frontend holds the authoritative id→page table: `PAGE_MAP` at the top of
  `src/app/demo/trinet/page.tsx`, `Record<string, {label: string; file: string}>`, 18 entries
  (`my_benefits → "My_Benefits.html"`, `medical → "aetna_medical.html"`, …).
- Render + trigger: in `renderInlineSegment`, a token matching `/^\[\[([a-z_]+)\]\]$/` **and present
  in `PAGE_MAP`** becomes an inline `<button>` with an `ExternalLink` icon and the page's `label`;
  `onClick={() => navigateTo(pageId)}`. Unknown ids fall through and render as literal text —
  a hallucinated page id is inert, never a broken link. That fail-safe is worth copying.
- `navigateTo` is `useCallback((pageId) => { if (PAGE_MAP[pageId]) setCurrentPage(pageId); }, [])`.
  The host page is an `<iframe src={`/trinet/${PAGE_MAP[currentPage].file}`}>`, so "navigation" is a
  React state change that swaps the iframe `src`. Navigation is **click-triggered only** — never
  automatic.

**Graphics: there are none inside the chat.** The rich visual surfaces are ordinary server-rendered
React on the host page, fed from static typed modules, with no involvement from the model:

- `src/components/plans-comparison.tsx` — `PlansComparison()` renders `MedicalCard`/`DentalCard`/
  `VisionCard` built from `CardShell` + `StatRow`, sourced from `MEDICAL_PLAN`, `DENTAL_PLAN`,
  `VISION_PLAN` in `src/lib/trinet-plans.ts`. Header comment: *"Server component — pure render, no
  client state. Data comes from src/lib/trinet-plans.ts (same source the voice agent's system prompt uses)."*
- `src/components/plan-shop.tsx` — `PlanShop()` maps `MEDICARE_PLANS` from `src/lib/medicare-plans.ts`
  into `PlanCard` with `StarBadge` and `ExtrasList`.
- `src/components/shop-cta.tsx` — a dismissible callout that deep-links to `/demo/voice/shop`.
- No charting library is used anywhere in the product. Rich = typed cards and stat rows, not plots.

**Tool calls exist but produce almost no UI.**

- `src/lib/tools/benefits-tools.ts` exports `BENEFITS_TOOLS`, seven OpenAI function definitions:
  `lookup_plan_details`, `calculate_oop_estimate`, `compare_plans`, `list_available_plans`,
  `check_fsa_hsa_eligible`, `get_enrollment_info`, `ask_benefits_expert`. `executeTool(toolName, args, organizationId)`
  is a `switch` returning a **JSON string**.
- `src/app/api/tools/execute/route.ts` — `POST` wraps that as `{ result: JSON.parse(result) }` for the
  browser-side voice client.
- In text chat the UI for a tool call is a chip: `src/app/[org]/[employee]/chat-interface.tsx`
  models `ToolCall {name, arguments, result}` and `Message.toolCalls?: ToolCall[]`, then renders
  `<Wrench/>` + `tc.name.replace(/_/g, " ")` in a pill whose `title={JSON.stringify(tc.result, null, 2)}`.
  The result is a tooltip. Nothing structured is drawn.
- Complex reasoning is delegated, not rendered: `ask_benefits_expert` → `askBenefitsExpert()` in
  `src/lib/tools/benefits-expert.ts`.

**Streaming: none.** `await fetch(...)` → `await response.json()` → one `setMessages`. During the
wait, `isLoading` renders three `animate-bounce` dots (`page.tsx`, the `{isLoading && ...}` block).
`scrollToBottom()` fires from a `useEffect` on `[messages]`.

**Errors: one generic assistant turn.** In `handleSubmit`:
`if (!response.ok) throw new Error("Failed to get response")`, and the `catch` appends an assistant
message `"I'm sorry, I encountered an error. Please try again."`. The server's `{error, details}`
body is never read. There is no rate limiting in this product at all.

**Suggested follow-ups: hardcoded client chips, not model output.**
`const quickQuestions = [...]` in `page.tsx` (4 strings) and again in `chat-interface.tsx`; each is a
button whose `onClick` does `setInput(q)` — it fills the box, it does not send. In `page.tsx` they are
gated on `speechPreference !== null && messages.length <= 2` so they disappear after the conversation
starts. `chat-interface.tsx` additionally renders a "Your Plans" card whose chips call
`setInput(`Tell me about my ${plan.name} plan`)` — data-derived prompt seeds.

**What to carry over:** `[[token]]`-in-prose navigation, a frontend-owned id→target map, inert
unknown ids, the tiny dependency-free markdown parser, the loading-dots + auto-scroll pattern, chips
that seed the input rather than auto-send.

**What not to carry over:** returning only `{content, model}` (no place for a chart), swallowing the
server's error body, hardcoding the follow-up chips, and rendering tool results as tooltip JSON.

### 1.2 Sunfire Pal — `/Users/andy/sunfire_pal_live`

Provenance note: the initial sweep of this repo (`api/index.py` is 9,171 lines) was delegated. Every
file, line number and snippet cited below was then **re-opened and verified directly** before being
written down. Where I could not verify something I have left it out rather than paraphrase.

**Wire format: one JSON object per turn, schema declared in the prompt, no tool calling.** This is
the single biggest structural difference from Benefits Pal, and it is the one to learn from.

- Every model call sets `"response_format": {"type": "json_object"}` — `api/index.py` lines 860,
  925, 1231, 1292, 1850, 5384, 8407, 8636. The model is not given OpenAI functions; it is told to
  return a specific object, and the server parses it.
- The response contract is documented in a comment block above the endpoint,
  `api/index.py` line 1617:
  ```python
  #   { profile: {...}, tips: [{title, body, script?, kind, icon?}], warnings: [] }
  ```
  and line 1628 pins the vocabulary:
  ```python
  #   kind   — info | warn | ok | bad
  ```
- The same shape is restated *inside the prompt* for the model (line 1649 onward, `"tips": [ ... ]`
  with line 1654 `"kind": "info" | "warn" | "ok" | "bad"`), and behavioural rules are written against
  it in prose — line 1690: *"If an APPLICABLE disclosure has not been said yet and the call is past
  30s, surface a `kind:'warn'` tip with the exact phrase to say."*; line 1805 instructs the model to
  *"emit a tip (kind \"bad\" for wrong name, \"warn\" for missing) with the correct name in the script."*
- The server defends the shape on the way out: line 1870 `"tips": data.get("tips") or []`, and the
  error paths at lines 1727 and 1783 return `{"profile": {}, "tips": [], ...}` — **always the
  declared keys, never a partial object**. Downstream (lines 2050–2051) merges `tips` into session
  state only when the key is not `None`.

So: an array of typed, kind-tagged UI objects, each with a title and a body, produced as JSON by the
model and rendered by a client that knows the type list. That is exactly the `blocks` design in §4,
and it is why the user will find it familiar.

**Graphics are hand-rolled, small, and inline — no charting library.**

- **Score bars.** `frontend/modules/bettyDemo.js` line 905:
  ```js
  function bar(label, score) {
    const v = Math.max(0, Math.min(100, Number(score) || 0));
    return `
      <div class="sc-bar">
        <div class="sc-bar-label">${label}</div>
        <div class="sc-bar-track"><div class="sc-bar-fill" style="width:${v}%"></div></div>
        <div class="sc-bar-val">${v}%</div>
      </div>
    `;
  }
  ```
  Note the clamp-and-coerce on the model-supplied number before it reaches a `style` attribute. Note
  also that it *is* string interpolation into HTML — safe here only because of the clamp. §4.5.4
  ports the structure but sets the width via `style.width`, which removes the reliance on the clamp
  being right.
- **Sparklines.** `frontend/modules/analyticsView.js` line 301, *"Phase 15A: inline SVG sparkline for
  a per-persona grade series"* — builds an `<svg class="analytics-sparkline" width viewBox
  aria-label="${series.length} grades trend">` (line 323) directly, with an em-dash placeholder for
  the empty case (line 305). No dependency.
- The heavier surfaces (`plansPanel.js`, 40 KB) are ordinary DOM built from fetched JSON.

The lesson for this project is a **divergence**, not a copy: Sunfire hand-rolls because it has no
charting library. This site already ships Chart.js 4.4.7 on every page that carries the widget, so
§4.5.2 uses it — but §4.5.4's `bar` and the table fallback keep Sunfire's "degrade to something
drawable" instinct.

**Navigation and page control: a coach-mark spotlight plus a global action dispatcher.**

- `frontend/modules/coachMarks.js` line 5 describes the technique — *"real element on the page (CSS
  box-shadow inverted overlay)"*. Line 148: *"The 'spotlight' is faked via box-shadow on a small
  overlay positioned…"*, and line 158 is the trick itself:
  ```js
  `box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.62)`
  ```
  Line 263 does the movement: `el.scrollIntoView({ behavior: "smooth", block: "center" })`.
  §4.5.6's arrival ring is this idea scaled down — a full-page scrim is too heavy for a chat answer,
  but *pointing at the thing you just navigated to* is the part worth keeping.
- **Host-page control by named global.** `frontend/modules/plansPanel.js` line 281 installs
  `window.__plansNarrowTo = (criteria, reason, source = "demo") => narrowToPlans(...)`, and
  `frontend/modules/coachingApp.js` line 113 dispatches against it:
  ```js
  function dispatchDemoAction(action) {
    if (!action || typeof action !== "object") return;
    switch (action.type) {
      case "narrowToPlans": window.__plansNarrowTo?.(action.criteria, action.reason, action.source || "demo"); break;
      case "showAllPlans":  window.__plansShowAll?.(); break;
      default: dlog("coach", `unknown demo action type: ${action.type}`);
    }
  }
  ```
  Three things to steal: the optional-call `?.()` so a missing handler is inert, the `default:` that
  **logs and continues** rather than throwing, and the comment at line 110 explaining the point —
  *"Dispatched against the canonical window accessors plansPanel installs … so the script speaks the
  same JSON the consumer Pal's WmcDemoRunner does."* One vocabulary, several front-ends. §4.5.11
  is the analogue here, and §4.5's "unknown `type` is skipped silently" rule is this `default:` case.
- **Decoupling by CustomEvent.** `frontend/modules/bettySession.js` line 112 and
  `frontend/modules/videoMode.js` line 241 both do
  `window.dispatchEvent(new CustomEvent("betty:compliance-pulse", { detail: turn.pulse }))` — two
  producers, one event name, no import between them. §4.5.6 rule 7 copies this with
  `phdchat:navigate`.

**Streaming: none for the JSON turns.** They are ordinary buffered `fetch` → `response.json()`.
(The product does have realtime *voice*, which is a separate transport and out of scope here.)

**Errors: a flat `{"error": "..."}` body plus an HTTP status, and a strong preference for degrading
instead of failing.**

- Server side, uniformly: `return JSONResponse({"error": "invalid JSON"}, status_code=400)`
  (`api/index.py` lines 799, 905, 945, 1200, 1261), `{"error": "OPENAI_API_KEY not configured"}` at
  503 (line 1586), `{"error": f"whisper transcription failed ({resp.status_code})"}` at 502
  (line 1605). One key, `error`, always a human-readable string. §4.4 keeps exactly this and only
  *adds* `error_code` alongside — which is also what preserves the current widget's
  `err.error || '…'`.
- **The degrade pattern**, `api/index.py` line 1701, with the comment *"No key — return a minimal
  canned response so the page still renders"*:
  ```python
  return {
      "profile": {},
      "tips": [{
          "title": "Coaching backend offline",
          "body": "Compliance scanning still works locally.",
          "kind": "info",
          "icon": "ℹ️",
      }],
      "warnings": ["OPENAI_API_KEY not configured"],
  }
  ```
  A backend outage arrives at the UI as **a valid response containing one `info` tip**, not as an
  error the renderer has to special-case. §4.4's "Degrade, don't fail" is this, verbatim in spirit.
- Client side, errors are classified into actionable copy rather than surfaced raw:
  `frontend/modules/bettyDemo.js` line 255 `classifyStartError(err)` returns
  `{kind, title, help}` — e.g. `{kind: "mic_denied", title: "Microphone access is blocked", help: "…set Microphone to Allow…then click Start Practice Call again."}` —
  and line 560 consumes it. The `help` string always names the next physical action. §6 requires the
  same `error_code → {title, help}` mapping.

**Stale-response guard.** `frontend/modules/coachingApp.js` line 82 declares `analyzeSeq: 0`; line
573 captures `const seq = ++state.analyzeSeq;` before the async call; line 591 bails:
```js
if (seq !== state.analyzeSeq) return;  // stale — newer call in flight
```
This is a small thing that matters a lot once turns are slow and visually heavy, and neither this
project nor Benefits Pal has it. §6 requires it.

**What to carry over from Sunfire:** the model-emits-JSON-blocks architecture, the
`info | ok | warn | bad` kind vocabulary, `{title, body}` on every block, the always-return-the-declared-keys
server discipline, degrade-to-a-valid-response instead of 5xx, the sequence guard, the
classified-error copy, the scroll-then-spotlight navigation, the `default:`-logs dispatcher, and
CustomEvent decoupling.

**What not to carry over:** `response_format: json_object` with the schema in prose (this project
already has working OpenAI tool calling in `_chat()`, and tool calling is what lets *data* tools
interleave with *render* tools — see §5.1); HTML-string interpolation of model values (§4.8); and
the 9,000-line single-module backend.

### 1.3 Where the two references agree

Both, independently, land on the same four choices — which is why this contract keeps all four:

1. **One buffered JSON response per turn.** No SSE, no streaming, in either product. The perceived
   latency fix is a typing indicator, not a token stream.
2. **The model emits structure; the client owns all presentation.** Neither product lets the model
   emit HTML, CSS, colours, or a chart config.
3. **A closed vocabulary of typed things**, declared in the prompt and enforced on the way out —
   Sunfire's `tips[].kind`, Benefits Pal's `PAGE_MAP` ids.
4. **Unknown/unresolvable values are inert, never fatal.** Benefits Pal renders an unknown
   `[[page_id]]` as literal text; Sunfire's dispatcher logs an unknown action type and continues.

They differ on exactly one axis that matters here — **how rich the payload is allowed to be**.
Benefits Pal ships prose with inline tokens; Sunfire ships an array of typed objects. This contract
takes Sunfire's array as the envelope and Benefits Pal's inline tokens *inside* the prose block, so
both idioms the user knows are present.

---

## 2. What this project already has, and what is missing

### 2.1 Baseline inventory

| Piece | Path | State |
| --- | --- | --- |
| Widget | `/Users/andy/usds_china_private/site/chat-widget.js` | 221 lines, IIFE, injects `<style>` + `#chat-bubble` + `#chat-panel`, no framework |
| Deployed Lambda | `/Users/andy/usds_china_private/infra/chat/lambda/index.py` | 510 lines. **This is the code that actually runs.** Has `TOOLS`, `_chat()` multi-round loop, `_log_chat()` |
| Repo copy of handler | `/Users/andy/usds_china/cloud/chat/handler.py` + `prompt.py` | 279 + 67 lines. **Drifted — has no tools at all**, returns `{"reply", "provider"}` only, and targets Bedrock. Reconcile or delete before starting |
| SAM template | `/Users/andy/usds_china_private/infra/chat/template.yaml` | python3.12, `Timeout: 30`, `MemorySize: 256`, Function URL `AuthType: NONE`, CORS locked to `AllowedOrigin` |
| Admin dashboard | `site/chat-admin.html` + `infra/chat/lambda/dashboard_api.py` | reads the chat-logs table |

### 2.2 How the current rich path works

Backend (`infra/chat/lambda/index.py`):

- `TOOLS` (line 177) defines exactly two OpenAI functions: `navigate_user{page, section_id?, label}`
  and `suggest_query{sql, explanation}`.
- `_chat(messages)` (line 411) loops up to `MAX_TOOL_ROUNDS = 3`. Each tool call is appended to a flat
  `actions` list as `{"type": "navigate", **args}` or `{"type": "query", **args}`, and a stub result
  (`{"status": "navigation_sent", ...}`) is fed back as the `role:"tool"` message. After the loop it
  makes a final `use_tools=False` call for the prose.
- `handler()` returns `{"reply": reply}` plus `"actions"` only when non-empty.
- Provider failover list `PROVIDERS` (openai → openrouter), keys from SSM, `_get_api_key`.
- `_check_rate` — DynamoDB `UpdateExpression` counter keyed `f"{ip}:{now // RATE_WINDOW}"`,
  `RATE_LIMIT = 10` per `RATE_WINDOW = 60`. Fails **open** on exception.
- `_log_chat` writes to `CHAT_LOGS_TABLE` — **which `template.yaml` never sets**, so analytics logging
  is currently a silent no-op in the deployed stack. Flag for the backend implementer.

Frontend (`site/chat-widget.js`):

- `window._chatSend()` POSTs `{message, conversationHistory}` with one retry on failure (cold start).
- `markdownToHtml(text)` handles `**bold**`, `[label](url)`, `` `code` ``, `\n`.
- The `data.actions` loop builds an HTML string per action: a `navigate` card (same-page smooth
  scroll vs cross-page `<a href>`) and a `query` card (`<pre>` of the SQL + a link to `/query.html`).
- Auto-navigation: if exactly one `navigate` action, after `setTimeout(..., 800)` it either
  `scrollIntoView` on `#id` / `#id-section`, or sets `window.location.href`.
- History is capped: `if (history.length > 40) history = history.slice(-20)`.

### 2.3 Gaps

**Rich content**
1. No chart block. The chat cannot draw anything, on a site that is essentially 200 charts.
2. No table block. Ranked/tabular answers are flattened into markdown bullets.
3. No stat/KPI block.
4. No link block — external sources (IPEDS, NSF, a university department page) can only appear as a
   raw markdown link, and `markdownToHtml` will happily emit whatever href the model produced.
5. No model-driven follow-up suggestions. Neither reference has them either, but the site's data has
   an obvious "next question" structure (university → department → visa stage) that begs for it.

**Data grounding**
6. **The model has no data.** Every number it can state is a hardcoded bullet in `SYSTEM_PROMPT`
   ("49,012 STEM PhDs awarded (2024), 32.3% to Non-Resident Aliens"). There is not one read tool.
   `suggest_query` writes SQL for the *user* to run; the assistant never sees a result. Any chart
   built on today's stack would be a hallucinated chart. This is the single largest gap.
7. `data/ipeds/nra_index.csv.gz` (1.2 MB, 260,171 rows) and `data/ipeds/nra_ground_truth/*.csv.gz`
   are new and completely unwired to the assistant.

**Navigation**
8. The site map lives as a prose blob inside `SYSTEM_PROMPT` and is partly wrong. Verified against the
   real files:
   - `data_sources.html` anchors claimed by the prompt (`#federal`, `#citizenship`, `#dissertations`,
     `#limitations`, `#links`, `#analytics`, `#name-classification`) — all real. Good.
   - `immigration.html#mit` — the prompt promises per-university anchors, but `immigration.html`
     line 203 does `card.id = key` **at runtime**. On a cold cross-page navigation the element does
     not exist when the hash is applied, so the scroll silently fails. The widget's auto-nav
     `document.getElementById(sectionId)` has the same race on same-page nav.
   - `overview.html` is not in the prompt's page list at all, and pages that exist and have anchors
     (`workforce.html`, `medical.html`, `quality.html`, `usaid.html`) are entirely absent.
   - Nothing validates a `page`/`section_id` the model returns. A hallucinated anchor produces a
     dead navigation card and, worse, an automatic `window.location.href` to a 404.
9. **The widget is only loaded on 103 of 135 pages**: `stem.html`, `non_stem.html`, and all 101
   `universities/*.html`. `pipeline.html`, `china.html`, `india.html`, `canada.html`, `uk.html`,
   `eu.html`, `mexico.html`, `vwp.html`, `immigration.html`, `query.html`, `ipeds_dashboard.html`,
   `data_sources.html`, `implementation.html`, `index.html`, `overview.html` — none have it. The
   assistant routinely navigates a user to a page where it then disappears.

**Security / correctness**
10. **XSS in `markdownToHtml`.** Model text is never HTML-escaped, and the output goes to
    `div.innerHTML` in `addMessage`. The link rule
    `.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>')`
    accepts any `$2`, including `javascript:` and `data:text/html`. `action.label`,
    `action.page` and `action.section_id` are also interpolated raw into an HTML string — and
    `section_id` additionally lands inside a `onclick="...'${sectionId}'..."` attribute, so a quote in
    it breaks out into script context. Every one of these is model-controlled and therefore
    prompt-injectable through page content the model may be fed later. Fix as part of v2.
11. Rate limiting fails open (`_check_rate` returns `True` on any exception) and the 429 body carries
    no `Retry-After` and no machine-readable code.
12. No `page` context is sent to the backend, so the assistant cannot say "the chart you're looking at".

**Operational**
13. `MemorySize: 256` and `Timeout: 30` are too tight once data tools + more tool rounds are added.
14. Two divergent copies of the handler (`cloud/chat/` vs `infra/chat/lambda/`).

---

## 3. Constraints that shape the contract

| Constraint | Consequence |
| --- | --- |
| Static HTML on S3 behind CloudFront; no build step for site pages | The widget must be one plain `.js` file, no bundler, no modules, no JSX. Any new shared data must be a plain JSON file fetched at runtime. |
| Pages already load `https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js` | Charts render client-side with Chart.js 4.4.7. The widget must **not** add a second copy: check `window.Chart` first, lazy-`<script>` the same pinned URL only if absent, and fall back to a table if the load fails. |
| Single Lambda, python3.12, buffered Function URL | **No streaming.** Python managed runtimes have no `streamifyResponse` equivalent; response streaming on Function URLs is Node-only. One request, one JSON body. Design the block list so a future Node rewrite can emit it as NDJSON without changing the contract. |
| `Timeout: 30`, `MemorySize: 256` | Raise to `Timeout: 45`, `MemorySize: 1024` (more memory ⇒ proportionally more CPU ⇒ faster gz parse and faster JSON). Budget: ≤ 3 model round-trips. |
| Per-university JSON under `site/data/stem/{key}.json` | Too big to fetch server-side per turn — `mit.json` is 2.9 MB, `_search.json` is 18 MB. Do **not** have the Lambda fetch these. Bundle a precomputed compact digest into the zip instead. |
| `data/ipeds/nra_index.csv.gz` is 1.2 MB / 260,171 rows, schema `year,unitid,cipcode,basis,total,nra` | Small enough to ship **inside the Lambda zip** and hold in memory across warm invocations. This is what makes real charts possible. |
| `scripts/query_nra_index.py` already implements the aggregation | The `nra_lookup` tool is a port of `load_index` / `aggregate` / `fmt_rows`, not new logic. Levels `national|subject|institution|cell`; flags `--cip --unitid --start --end --min-total --min-share --pooled --family --sort --top`. |
| `data/ipeds/nra_ground_truth/` (0.7–3.0 MB gz, sex + race breakdowns, doc'd in `_metadata.md`) | Ship `doctoral_nra_by_cip2.csv.gz` (1.6 MB) too; leave the 3.0 MB per-CIP file out of v2. |
| CORS locked to `https://phd-demographics.andy-barr.com` | Unchanged. Blocks stay same-origin; no cross-origin asset fetches from the widget. |
| Site already exposes `/catalog.json`, `/llms.txt`, `/data/taxonomy.json`, `/data/universities_index.json` and WebMCP tools (`list_universities`, `get_university_data`, `get_data_catalog`, `get_taxonomy`, `navigate_to_university` — `stem.html` line 7894 ff.) | Reuse these names. The chat's server tools should mirror the WebMCP tool names so the two surfaces stay conceptually one API. |
| **The anchor scheme is being rationalised right now** by a parallel workstream, to make universities, fields, years and panels directly addressable; `concentration.html` (slide deck) is new | The contract carries **URLs**, treats fragments as **opaque**, and puts anchor-enumerability in data (`SITE_MAP.anchors`), not in code. Neither implementer may hard-code a fragment format. Ship with every page `"anchors": "open"`. |
| Site palette (from `stem.html` chart configs) | `#38bdf8` sky, `#ef4444` red, `#a78bfa` violet, `#34d399` emerald, `#94a3b8` slate; panel `#1e293b`, ground `#0f172a`, border `#334155`, text `#e2e8f0`. The widget owns these; the model never sends a hex. |

---

## 4. THE CONTRACT

### 4.1 Endpoint

`POST https://<lambda-function-url>/` — unchanged. `Content-Type: application/json`.

### 4.2 Request

```json
{
  "v": 2,
  "message": "Which universities have the highest NRA share in electrical engineering?",
  "conversationHistory": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "page": {
    "path": "/universities/mit.html",
    "university_key": "mit",
    "section": "h1b-chart"
  },
  "client": {"widget": "2.0.0"}
}
```

- `v` — integer. Absent ⇒ treat as `1` and reply in v1 shape (`reply` + `actions` only).
- `message` — required string, clamped to 2000 chars server-side (existing `MAX_INPUT`).
- `conversationHistory` — last 20 turns, `role ∈ {user, assistant}`, each `content` clamped to 2000.
  Unchanged from today. The widget sends **prose only**; blocks are never echoed back.
- `page` — new, all fields optional. `path` is `location.pathname`. `university_key` is set only on
  `/universities/{key}.html`, derived by the widget from the filename. `section` is the current
  `location.hash` without `#`, if any. The backend turns this into a system-prompt suffix, the
  Benefits Pal way:
  `[The user is currently on {path}{, viewing the "{section}" section}{, which is the page for {name}}.]`
- `client.widget` — semver of `chat-widget.js`, for log-side rollout tracking.

**Warm-up ping.** `{"v": 2, "ping": true}` → `200 {"v": 2, "ok": true}`. No model call, no
rate-limit consumption, no logging. The widget fires this once when the bubble is first opened.

### 4.3 Success response envelope

```jsonc
{
  "v": 2,
  "reply": "Electrical engineering is the most NRA-concentrated doctoral field...",
  "blocks": [ /* ordered render list, see §4.5 */ ],
  "actions": [ /* v1 mirror, deprecated — see §4.9 */ ],
  "meta": {
    "provider": "openai",
    "model": "gpt-4o",
    "latency_ms": 2140,
    "tools_used": ["nra_lookup", "show_chart", "navigate_user"],
    "truncated": false
  }
}
```

- `reply` — the model's final prose, raw markdown. Always present. Also duplicated as the `text`
  block, so a v1 client renders the same words a v2 client does.
- `blocks` — always present in a v2 response, possibly `[]`.
- `meta` — advisory only; the widget must render correctly if it is missing entirely.
  `truncated: true` means the server dropped blocks to fit the caps in §4.7.

### 4.4 Error response

```json
{
  "v": 2,
  "error": "Rate limit exceeded. Try again in a minute.",
  "error_code": "rate_limited",
  "retry_after_s": 37
}
```

`error` stays a **plain human string at the top level** precisely because the current widget already
does `err.error || 'Something went wrong.'` — v1 clients keep working. `error_code` is the machine
key.

| HTTP | `error_code` | Widget behaviour |
| --- | --- | --- |
| 400 | `bad_request` | Show the message as an `error` bubble. |
| 400 | `too_long` | Show message; keep the user's text in the input so they can trim it. |
| 403 | `forbidden_origin` | Show a generic failure. Should never reach a real user. |
| 429 | `rate_limited` | Show message + a live countdown from `retry_after_s`; disable Send until it hits 0. Also honour the `Retry-After` response header. |
| 200 | *(none)* + `meta.degraded` | **Not an error.** Both providers failed — see "Degrade, don't fail" below. |
| 502 | `upstream_unavailable` | Show message; render a **Retry** chip that resends the same turn. |
| 504 | `upstream_timeout` | Same as above. |
| 200 | `refused_offtopic` | Not an error — a normal 200 with a `text` block plus a `suggest` block of on-topic prompts. |
| 500 | `internal` | Generic failure bubble. |

429 responses **must** carry a `Retry-After: <seconds>` header. `_check_rate` must stop failing open
silently: on a DynamoDB exception, allow the request but emit a CloudWatch metric.

**Degrade, don't fail.** When every provider in `PROVIDERS` fails, do **not** return 5xx. Return
`200` with a well-formed, empty-but-valid v2 envelope:

```json
{
  "v": 2,
  "reply": "I can't reach the model right now, so I can't answer that one. The data itself is all still on the site.",
  "blocks": [
    {"type": "notice", "kind": "warn", "title": "Assistant offline",
     "md": "The assistant backend is unreachable. Everything below is still live."},
    {"type": "nav", "url": "/stem.html", "label": "Browse the 101 university pages"},
    {"type": "nav", "url": "/query.html", "label": "Query the raw records yourself"}
  ],
  "meta": {"degraded": true}
}
```

This is Sunfire's pattern: when its coaching backend is down it returns a **valid-shaped** response
carrying a single `kind:"info"` tip rather than an error, so the UI never has to render a failure
state it did not design. Copy that here. The frontend's error path then exists only for the genuine
4xx cases, and a degraded turn still leaves the reader with somewhere to go.

`meta.degraded: true` must be logged so the condition is visible in `chat-admin.html` — a silent
degrade that nobody can see is worse than a 500.

### 4.5 Block catalog

Every block is `{"type": "<name>", ...}`. Blocks render top-to-bottom inside a single assistant
message bubble. **An unknown `type` MUST be skipped silently** — that is the forward-compat hinge
that lets the backend ship a new block before the widget knows it.

Optional on every block: `"id": "<string ≤32 chars>"` for analytics correlation.

---

#### 4.5.1 `text` — prose

```json
{
  "type": "text",
  "md": "**Electrical engineering** is the most NRA-concentrated doctoral field in IPEDS.\n\n- 2024 NRA share: **61.4%** of 4,812 research doctorates\n- Up from 44.1% in 2005\n\nMIT's own EE cohort runs above that — see [[nav:/universities/mit.html#completions-trend-chart|MIT completions trend]]."
}
```

Supported markdown (this is the whole surface — the parser is a port of Benefits Pal's
`markdownParser.ts`, so keep the same block/inline split):

| Syntax | Renders as |
| --- | --- |
| blank-line-separated lines | `<p>` |
| `# ` / `## ` / `### ` | `<div class="cb-h1|cb-h2|cb-h3">` |
| lines starting `- ` or `• ` | `<ul><li>` |
| `**bold**` | `<strong>` |
| `*italic*` | `<em>` |
| `` `code` `` | `<code>` |
| `[label](https://…)` | `<a>` — **https/http only**, `rel="noopener noreferrer" target="_blank"` |
| `[[nav:/URL\|Label]]` | inline navigation chip (see below) |
| `[[KEY]]` where KEY is a university key | inline chip to `/universities/KEY.html` |

**Inline nav tokens.** This is the Benefits Pal idiom, adapted to this site's `page.html#anchor`
world. Grammar:

```
[[nav:/<site-relative-url>]]           e.g. [[nav:/pipeline.html]]
[[nav:/<site-relative-url>]]           e.g. [[nav:/pipeline.html#eb-chart-section]]
[[nav:/<site-relative-url>|<Label>]]   e.g. [[nav:/vwp.html#overstay-chart-section|Overstay rates]]
[[<university_key>]]                  e.g. [[mit]]  →  /universities/mit.html
```

The token payload is a **site-relative URL**, addressed and validated exactly as `nav.url` is
(§4.5.5): the path must exist in `SITE_MAP`, the fragment is opaque. The `|` separator is what ends
the URL, so a fragment may contain any character except `|` and `]`.

Resolution and fail-safe, exactly as Benefits Pal does it: the widget looks the **path** up in
`SITE_MAP` (§4.10). **If the path is not in the map, the token renders as literal text** and no link
is produced — a hallucinated page is inert, never a broken link. An unknown *fragment* on a known
page still produces a working chip, because fragments are not enumerable in general (§4.5.5 rule 2)
and landing at the top of the right page is the correct degradation. If `<Label>` is omitted, the
`SITE_MAP` label for the fragment is used when it is enumerated, otherwise the page title.

Clicking a chip performs a `nav` action (§4.5.6) with `auto: false` semantics.

---

#### 4.5.2 `chart` — a Chart.js chart

The model supplies **data and intent**. The widget supplies the Chart.js config, the colours, the
fonts, the tooltip formatting, and the responsive behaviour.

```json
{
  "type": "chart",
  "chart": "line",
  "title": "STEM PhDs awarded, by citizenship status",
  "subtitle": "IPEDS Completions, research doctorates",
  "labels": ["2010","2011","2012","2013","2014","2015","2016","2017","2018","2019","2020","2021","2022","2023","2024"],
  "datasets": [
    {"label": "American (citizens + PR)", "data": [21623,22677,23457,24523,25770,26057,26668,27117,27883,28282,28309,27860,30106,31822,33198], "role": "domestic", "fill": true},
    {"label": "Non-Resident Alien",       "data": [11120,11580,12043,12785,13502,13450,13480,13749,14369,14655,14984,14673,16294,15957,15814], "role": "nra", "fill": true}
  ],
  "y": {"format": "compact", "begin_at_zero": false, "label": "Doctorates awarded"},
  "x": {"label": "Award year"},
  "source": "IPEDS Completions (C-series), 2010–2024",
  "nav": {"url": "/stem.html#nat-phd-chart", "label": "Open the full chart"}
}
```

| Field | Type | Rules |
| --- | --- | --- |
| `chart` | enum | `line` \| `bar` \| `hbar` \| `stacked_bar` \| `area` \| `doughnut` \| `scatter` |
| `title` | string ≤ 90 | required |
| `subtitle` | string ≤ 140 | optional |
| `labels` | string[] | required except for `scatter`; ≤ 40 items, each ≤ 24 chars |
| `datasets` | array | 1–4 items |
| `datasets[].label` | string ≤ 40 | required |
| `datasets[].data` | number[] \| `{x,y}[]` | `number[]` must be exactly `labels.length` long; `{x,y}[]` only for `scatter`. `null` allowed for gaps |
| `datasets[].role` | enum | `nra` \| `domestic` \| `total` \| `alt1` \| `alt2` \| `alt3` \| `neutral`. Drives colour. **No hex ever crosses the wire.** |
| `datasets[].fill` | bool | default `false` |
| `datasets[].dashed` | bool | default `false` |
| `datasets[].axis` | enum | `left` \| `right`, default `left` |
| `y`, `y2` | object | `{format, label?, begin_at_zero?}`; `format ∈ int, float1, pct, pct1, usd, usd_k, usd_m, compact` |
| `x` | object | `{label?}` |
| `source` | string ≤ 120 | rendered as a caption under the chart; **required** for any chart whose data came from a data tool |
| `nav` | object | optional; a `nav` block's fields (§4.5.6), rendered as a chip under the chart |
| `placement` | enum | `before_text` \| `after_text` (default) — see §4.6 |

Widget-side colour map (frontend implementer owns this table):

| `role` | border | fill |
| --- | --- | --- |
| `nra` | `#ef4444` | `rgba(239,68,68,0.14)` |
| `domestic` | `#38bdf8` | `rgba(56,189,248,0.14)` |
| `total` | `#94a3b8` | `rgba(148,163,184,0.10)` |
| `alt1` | `#a78bfa` | `rgba(167,139,250,0.14)` |
| `alt2` | `#34d399` | `rgba(52,211,153,0.14)` |
| `alt3` | `#fbbf24` | `rgba(251,191,36,0.14)` |
| `neutral` | `#64748b` | `rgba(100,116,139,0.10)` |

Fixed widget-side Chart.js options: `responsive: true`, `maintainAspectRatio: false`, container
`height: 190px` (`240px` for `doughnut`/`hbar` with > 6 categories), `interaction: {mode:'index', intersect:false}`,
legend top with `boxWidth: 12` and 10px font, grid `#334155` at 0.35 alpha, ticks `#94a3b8` 10px,
`tension: 0.3` for `line`/`area`, `pointRadius: 2`. Number formatting comes from `y.format`, not from
the model. Every chart gets `aria-label={title}` and a visually-hidden `<table>` of the same data for
screen readers.

**Fallback:** if `window.Chart` is undefined after the lazy load attempt, render the chart block as a
`table` block built from `labels` + `datasets`, prefixed with the `title`.

**Chart.js is destroyed on message removal.** The widget keeps a per-message array of Chart instances
and calls `.destroy()` when the panel is cleared, mirroring the `natCharts.push(...)` pattern used on
`stem.html`.

---

#### 4.5.3 `table` — a data table

```json
{
  "type": "table",
  "title": "Highest NRA share, electrical engineering doctorates (CIP 14.10), 2020–2024 pooled",
  "columns": [
    {"key": "institution", "label": "Institution", "align": "left"},
    {"key": "state",       "label": "St",          "align": "left"},
    {"key": "total",       "label": "Doctorates",  "align": "right", "format": "int"},
    {"key": "nra_share",   "label": "NRA %",       "align": "right", "format": "pct1", "emphasis": true}
  ],
  "rows": [
    {"institution": "New Jersey Institute of Technology", "state": "NJ", "total": 121, "nra_share": 91.7, "nav": {"url": "/universities/njit.html", "label": "NJIT"}},
    {"institution": "University of Texas at Dallas",      "state": "TX", "total": 214, "nra_share": 88.3, "nav": {"url": "/universities/utdallas.html", "label": "UT Dallas"}},
    {"institution": "Missouri University of Science and Technology", "state": "MO", "total": 88, "nra_share": 87.5, "nav": {"url": "/universities/missouri_st.html", "label": "Missouri S&T"}}
  ],
  "note": "Cohorts of 20+ pooled doctorates only.",
  "source": "IPEDS Completions via nra_index",
  "footer_nav": {"url": "/query.html", "label": "Explore the raw records"}
}
```

| Field | Rules |
| --- | --- |
| `columns` | 1–8. `key` matches row object keys. `align ∈ left, right, center` (default: `right` for numeric formats, else `left`). `format` as in §4.5.2 plus `text`. `emphasis: true` colours the cell `#38bdf8` |
| `rows` | 1–25 objects. Extra keys not in `columns` are ignored. Values are `string \| number \| null` |
| `rows[].nav` | optional per-row navigation, `{url, label}` per §4.5.6; renders the first `left`-aligned cell as a chip |
| `note` | ≤ 160 chars, rendered muted under the table |
| `source` | ≤ 120 chars |
| `footer_nav` | optional single nav chip under the table, `{url, label}` per §4.5.6 |
| `placement` | as §4.6 |

Rendering: `<table class="cb-table">` inside a `overflow-x: auto` wrapper so wide tables scroll
inside the 400px panel instead of blowing it out. Sticky header row. Zebra rows at
`rgba(148,163,184,0.05)`.

---

#### 4.5.4 `stat` — a KPI strip

```json
{
  "type": "stat",
  "items": [
    {"label": "STEM PhDs, 2024", "value": "49,012", "delta": "+2.6%", "delta_dir": "up"},
    {"label": "NRA share",       "value": "32.3%",  "delta": "-1.1pp", "delta_dir": "down", "emphasis": true},
    {"label": "MIT NRA share",   "value": "43.8%",  "note": "vs 32.3% national"}
  ],
  "source": "IPEDS Completions 2024"
}
```

1–4 items. `value` is a **pre-formatted string** (the model has already decided the units).
`delta_dir ∈ up, down, flat` chooses the arrow and colour (`up` → `#34d399`, `down` → `#ef4444`,
`flat` → `#94a3b8`) — the direction is purely visual; the model decides whether up is good.
Rendered as a horizontal flex strip that wraps to 2×2 below 360px.

An item may additionally carry **`bar`** — a number 0–100 — which renders a proportion track under
the value:

```json
{"label": "NRA share of MIT STEM doctorates", "value": "43.8%", "bar": 43.8, "emphasis": true}
```

This is Sunfire's score-bar idiom, ported: `frontend/modules/bettyDemo.js` line 905,
`bar(label, score)`, which clamps with `Math.max(0, Math.min(100, Number(score) || 0))` and emits
`.sc-bar` / `.sc-bar-track` / `.sc-bar-fill` with `style="width:{v}%"`. The widget reproduces the
same three-element structure under `cb-bar` / `cb-bar-track` / `cb-bar-fill`, with the identical
clamp — **and sets the width via `element.style.width`, never by interpolating into an HTML
string**, since that is a model-controlled number landing in a style attribute. Fill colour follows
`emphasis` (`#38bdf8`) or defaults to `#64748b`.

A `stat` with `bar` is the right block for a single share; a `chart` is the right block for a
series. Never use four `bar` items where one `hbar` chart would do.

---

#### 4.5.5 Addressing: URLs are the currency

**Every navigable thing on this site is identified by a URL, not by a page-and-section pair.**
The `nav` and `link` blocks both carry a `url` string, so the reader can copy and share the address
rather than only being scrolled to it.

This matters now because a sibling workstream is rationalising the anchor scheme so that
universities, fields, years and panels become directly addressable. A contract built on opaque
`{page, section_id}` pairs would have to change when that lands. One built on URLs does not.

**Checked state of `/concentration.html` as of 2026-08-18** (do not assume otherwise): the deck has
exactly three static ids — `deck`, `rail`, `count` — and **no fragment addressing at all**. Slide
position is pure JS state; there is no `location.hash` read, no `pushState`, no `replaceState`
(the only `slides[...]` reference is `slides[cur].scrollTop = 0` at line 412). So today the
assistant can link to the deck but **not** to a slide within it. That is a gap for the anchor
workstream to close, not something this contract can paper over — and it is precisely why the
contract must not invent a `#slide-N` grammar and hope. When hash-addressing lands, the deck's
`SITE_MAP` entry needs no change: it is already `"anchors": "open"`, and `link` blocks start
carrying fragments the day the page starts honouring them.

Three hard rules follow:

1. **The contract does not define fragment grammar and must never hard-code one.** Not
   `#{key}`, not `#{id}-section`, not `#slide-{n}`, not `#uni={key}&year={y}`. A fragment is an
   opaque string that the contract carries, escapes, length-caps and hands to the browser. The
   anchor scheme is still being finalised; whatever it becomes, this contract already supports it.
   Query strings are carried the same way — `stem.html` already reads `?funding=1`.
2. **Validation happens on the path, not the fragment.** The path (everything before `?` or `#`)
   must exist in `SITE_MAP.pages`. The fragment is validated *only* when that page declares
   `"anchors": "enumerated"` in `SITE_MAP`; a page declaring `"anchors": "open"` (which is what
   every page should declare until the new scheme is stable, and what `immigration.html` and
   `concentration.html` should keep permanently) accepts any well-formed fragment unchecked.
   This is the seam that lets the anchor scheme change without touching either implementation.
3. **A bad fragment degrades, it does not break.** If the target does not resolve in the DOM, the
   user lands at the top of a real page. That is an acceptable outcome; a dead link or a 404 is not.

Well-formed fragment: 1–128 chars matching `^[A-Za-z0-9._~!$&'()*+,;=:@/?%-]+$` (the RFC 3986
`fragment` production). Well-formed query: same set, ≤ 256 chars. Both are escaped before they ever
touch the DOM, per §4.8.

---

#### 4.5.6 `nav` — a navigation action

```json
{
  "type": "nav",
  "url": "/pipeline.html#eb-chart-section",
  "label": "See the EB green-card bottleneck",
  "auto": true,
  "highlight": true,
  "reason": "This chart shows exactly the China/India backlog you asked about."
}
```

| Field | Rules |
| --- | --- |
| `url` | **required**. A site-relative URL beginning `/`: `/<path>.html` plus optional `?query` and `#fragment`. Path must exist in `SITE_MAP.pages`. Never scheme-qualified, never another origin, never protocol-relative `//host`. |
| `label` | required, ≤ 60 chars, plain text (no markdown, no HTML). |
| `auto` | bool, default `false`. `true` = the widget moves the browser without a click. |
| `highlight` | bool, default `true` when `url` carries a fragment, else `false`. Briefly rings the target element on arrival (see below). |
| `reason` | optional ≤ 140 chars, shown muted under the label. |
| `placement` | as §4.6 |

The server additionally emits two **derived, advisory** fields so the widget does not have to parse
the URL twice: `"path"` (e.g. `"pipeline.html"`) and `"fragment"` (e.g. `"eb-chart-section"`, absent
if none). They are derived from `url`; `url` is authoritative and the widget may recompute them.

**Legacy tool input.** The existing `navigate_user` tool signature (`page`, `section_id`, `label`) is
still accepted. The server normalises it: `url = "/" + page + ("#" + section_id if section_id else "")`.
The *block* always carries `url`. No caller outside the Lambda ever sees `page`/`section_id` again.

**Auto-navigation rules** (frontend implementer — these replace the current unconditional
`window.location.href`):

1. At most **one** block per response may have `auto: true`. The server enforces it; the widget
   enforces it again (first wins, rest demoted).
2. **Same-page** (the `url` path equals the current filename): smooth-scroll after 600 ms, then
   `history.pushState(null, "", url)` — pushing the whole URL, query and fragment included, so the
   reader's address bar holds the shareable link. **Poll for the element** — up to 20 tries at
   150 ms — because anchors on several pages are created in JS after load (`immigration.html`
   line 203 does `card.id = key`), and the rationalised scheme will add more of these. Give up
   silently if it never appears; the clickable card remains.
3. **Cross-page: never auto-navigate.** Render the card and let the reader click. The widget is
   absent from 32 of the site's pages (§2.3 gap 9), so an automatic jump can strand the reader with
   no assistant, and an unrequested full-page load destroys the conversation. Revisit once the
   widget is universal and the transcript is in `sessionStorage`; it is deliberately a one-line
   change.
4. The card always renders whether or not `auto` fired, so the action is repeatable.
5. Cross-page cards keep today's secondary `↗` control that opens in a new tab.
6. **Highlight on arrival.** When `highlight` is true and the element resolves, add class
   `cb-target-ring` for 2500 ms then remove it — a `2px` `#38bdf8` outline plus
   `box-shadow: 0 0 0 4px rgba(56,189,248,0.18)`. This is the Sunfire coach-mark idiom
   (`frontend/modules/coachMarks.js` line 158 uses the inverted `box-shadow: 0 0 0 9999px` overlay
   and line 263 `scrollIntoView({behavior:"smooth", block:"center"})`), scaled down to a ring
   because a full-page scrim is too heavy for a chat answer. Suppressed under
   `prefers-reduced-motion: reduce`.
7. On every navigation the widget dispatches
   `window.dispatchEvent(new CustomEvent("phdchat:navigate", {detail: {url, path, fragment, auto}}))`
   so host pages can react — `stem.html` already registers a WebMCP `navigate_to_university` tool
   (line 7946) that could subscribe. Sunfire uses exactly this decoupling (`betty:compliance-pulse`).

Rendered card: `📊 <label>` in `#38bdf8` on a `#0f172a` panel with a `#334155` border — i.e. exactly
today's navigate card, so nothing regresses visually.

---

#### 4.5.7 `link` — a precise, shareable URL

Where `nav` moves the reader, `link` **hands them an address**. This is the block to use when the
answer is "here is exactly where that lives", and it is the one that gets more valuable as the
anchor scheme is rationalised: a link to a specific university's specific field in a specific year
is a citation, and the reader should be able to copy it into an email.

Site-internal deep link:

```json
{
  "type": "link",
  "kind": "site",
  "url": "/data_sources.html#name-classification",
  "label": "How name-origin classification works",
  "note": "Methodology, confidence thresholds, and known failure modes.",
  "copyable": true
}
```

Deep link carrying query + fragment (shape shown is illustrative — **the contract does not define
this grammar**, §4.5.5 rule 1):

```json
{
  "type": "link",
  "kind": "site",
  "url": "/universities/mit.html?funding=1#completions-trend-chart",
  "label": "MIT completions trend, funding overlay on",
  "copyable": true
}
```

External primary source:

```json
{
  "type": "link",
  "kind": "external",
  "url": "https://nces.ed.gov/ipeds/use-the-data",
  "label": "IPEDS — Use the Data",
  "note": "Primary source for every completions figure on this site.",
  "copyable": false
}
```

| Field | Rules |
| --- | --- |
| `url` | **required**. `kind: "site"` ⇒ site-relative, beginning `/`, path validated against `SITE_MAP`, fragment/query treated as opaque per §4.5.5. `kind: "external"` ⇒ an absolute URL whose scheme is **`https:` only**. Anything else ⇒ block dropped. |
| `kind` | `site` \| `external`. Required — do not infer it from the string, infer-and-mismatch is how `javascript:` gets through. If `kind` and the URL shape disagree, drop the block. |
| `label` | required, ≤ 70, plain text |
| `note` | optional, ≤ 160, plain text |
| `copyable` | bool. Default `true` for `kind: "site"`, `false` for `kind: "external"`. |
| `placement` | as §4.6 |

Rendering:

- `kind: "site"` → an `<a>` whose `href` is the `url` as given (so the browser resolves it
  relatively and same-page fragments do not reload). Clicking it runs the same `performNav` path as
  a `nav` block, including the arrival highlight.
- `kind: "external"` → an `<a target="_blank" rel="noopener noreferrer">` with a `↗` glyph and the
  hostname rendered muted beside the label. Never auto-navigated, never highlighted.
- `copyable: true` → a small 📋 button beside the label. It copies the **absolute** form —
  `"https://phd-demographics.andy-barr.com" + url` — via `navigator.clipboard.writeText`, then
  swaps to ✓ for 1200 ms. The absolute origin is a widget constant, not a wire field; the backend
  never sends an absolute self-referential URL.
- `copyable` is ignored (treated as `false`) when `navigator.clipboard` is unavailable, e.g. a
  non-secure context.

**`nav` vs `link`, decision rule for the model:** call `navigate_user` when the answer *is* a place
and the reader should end up there. Call `show_link` when the answer *cites* a place — when the
reader may want the address more than the trip. `link` is also the only block that may point
off-site.

#### 4.5.8 `query` — a runnable SQL suggestion (existing, kept)

```json
{
  "type": "query",
  "sql": "SELECT department, COUNT(*) AS n\nFROM stem_records\nWHERE university = 'mit' AND year >= 2020\nGROUP BY department\nORDER BY n DESC\nLIMIT 20",
  "explanation": "Counts MIT dissertations by department since 2020.",
  "table": "stem_records"
}
```

Unchanged from v1 apart from the optional `table` hint. Renders as the existing `<pre>` card plus a
"🔍 Run on Query Page" link to `/query.html`. The SQL is escaped, never executed anywhere.
Server-side validation: must start with `SELECT` (case-insensitive, after stripping whitespace and
comments), must contain `LIMIT`, must not contain `;`, `--`, `/*`, or any of
`INSERT UPDATE DELETE DROP ALTER CREATE ATTACH COPY PRAGMA`. Fails ⇒ block dropped.

---

#### 4.5.9 `suggest` — follow-up chips

```json
{
  "type": "suggest",
  "items": [
    {"label": "Compare MIT to Stanford", "prompt": "Compare MIT and Stanford on NRA share and H-1B filings"},
    {"label": "Which departments drive it?", "prompt": "Which MIT departments have the highest NRA share?"},
    {"label": "Show the H-1B trend", "prompt": "Show MIT's H-1B petition trend since 2010"}
  ]
}
```

1–4 items. `label` ≤ 40 chars (what the chip says), `prompt` ≤ 160 chars (what gets sent).
**A `suggest` block always renders last**, regardless of where it appears in `blocks` — the server
sorts it there, and the widget also forces it.

Behaviour, following Benefits Pal's `quickQuestions`: clicking a chip **fills the input and sends
immediately** (Benefits Pal only fills; on a data-exploration site the extra click is friction, and
the prompt text is fully model-authored and visible on the chip's `title`). Chips disappear as soon
as the next turn is sent. Only the most recent message's chips are shown.

---

#### 4.5.10 `notice` — inline caveat

```json
{
  "type": "notice",
  "kind": "warn",
  "title": "Small cohorts",
  "md": "Three of these institutions awarded fewer than 20 doctorates in the period, so their shares swing hard year to year. See [[nav:/data_sources.html#limitations|Limitations & caveats]]."
}
```

| Field | Rules |
| --- | --- |
| `kind` | `info` \| `ok` \| `warn` \| `bad`. Required. |
| `title` | optional, ≤ 60, plain text, rendered bold on its own line |
| `md` | required, ≤ 4000, restricted markdown exactly as `text` (§4.5.1) |
| `icon` | optional single emoji; defaults per `kind` |
| `placement` | as §4.6 |

The `kind` vocabulary is lifted verbatim from Sunfire's tip contract — `api/index.py` line 1628
documents `kind — info | warn | ok | bad`, and line 1617 gives the tip shape
`{title, body, script?, kind, icon?}`. Keeping the same four words means the user reads this block
as the thing he already knows. `body` is renamed `md` here only because this contract's prose fields
are uniformly markdown-typed and uniformly named `md`; `script` has no analogue on a data site.

Left border and icon tint: `info` `#38bdf8` ℹ️, `ok` `#34d399` ✓, `warn` `#fbbf24` ⚠️,
`bad` `#ef4444` ✕. Use it for data caveats, small-cohort warnings, the degraded-backend message
(§4.4), and the off-topic refusal.

---

#### 4.5.11 `page_action` — **DEFERRED to v2.1, do not implement**

Specified here only so that v2 leaves room for it and nobody designs it away. **Neither implementer
builds this now.**

```json
{
  "type": "page_action",
  "action": "select_university",
  "args": {"key": "mit"},
  "label": "Show MIT on this page"
}
```

The idea is Sunfire's `dispatchDemoAction` (§1.2): the host page installs named handlers, the chat
calls them by name, and an unregistered handler is inert. This site already has the handler surface
— `stem.html` line 7946 registers a WebMCP tool `navigate_to_university` alongside
`list_universities`, `get_university_data`, `get_data_catalog` and `get_taxonomy`. Wiring the chat to
those would let the assistant switch the selected university *without a page load*, which is
strictly better than navigating.

It is deferred because it needs a registry, an allowlist, and a per-page capability declaration in
`SITE_MAP`, and none of that is worth blocking v2 on. The forward-compat rule in §4.5 means the
backend can start emitting `page_action` the day the widget learns it, with no coordinated release:
until then every widget skips it silently.

---

### 4.6 Block ordering

The server assembles `blocks` deterministically:

1. `pre` = render blocks whose `placement == "before_text"`, in tool-call order.
2. `txt` = a single `{"type":"text","md": <final assistant prose>}` — omitted if the prose is empty
   or whitespace.
3. `post` = render blocks whose `placement == "after_text"` (the default), in tool-call order.
4. `suggest` blocks are lifted out of wherever they landed and appended last.

`blocks = pre + [txt] + post + [suggest]`.

Default `after_text` means "explain, then show", which is the right default for this site. A model
that wants "show, then explain" sets `placement: "before_text"` on the chart.

### 4.7 Caps and validation

Enforced **server-side before serialising**, and again **client-side before rendering**. Both sides
enforce; neither trusts the other.

| Limit | Value | On violation |
| --- | --- | --- |
| `blocks` length | 8 | drop from the end, set `meta.truncated = true` |
| `text.md` / `notice.md` length | 4000 chars | truncate at a word boundary + `…` |
| `chart.datasets` | 4 | drop extras |
| `chart` points per dataset | 40 | drop the block (a silently truncated series is a lying chart) |
| `chart` data/label length mismatch | — | drop the block |
| `table.columns` | 8 | drop extras |
| `table.rows` | 25 | truncate, append `note` "showing first 25 of N" |
| any table cell string | 120 chars | truncate + `…` |
| `stat.items` | 4 | drop extras |
| `suggest.items` | 4 | drop extras |
| `nav` blocks with `auto:true` | 1 | demote the rest |
| total serialised body | 128 KB | drop `chart`/`table` blocks from the end until it fits |
| `url` total length | 300 chars | drop the block |
| `url` fragment | 128 chars, RFC 3986 fragment charset | drop the block |
| `url` query | 256 chars | drop the block |
| unknown block `type` | — | server: never emits one. client: skip silently |
| unknown field inside a known block | — | ignore, both sides |

Validation failures are logged (`meta` is not the place for them) but never surfaced to the user as
an error — a dropped block just does not appear.

### 4.8 Security rules (non-negotiable, frontend)

1. **Escape before you format.** `escapeHtml(s)` (`& < > " '`) runs on every model-derived string
   *first*; markdown transforms run on the escaped text. This fixes the current
   `markdownToHtml` → `innerHTML` hole.
2. **No model string is ever interpolated into an HTML attribute.** Build nodes with
   `document.createElement` + `textContent` + `addEventListener`. In particular the current
   `onclick="...'${sectionId}'..."` construction must go.
3. **URL allowlist.** Resolve every `url` with `new URL(url, location.origin)` inside a
   `try/catch` and then check the **resolved** object, never the raw string:
   - `kind: "site"` (and every `nav.url`): resolved `origin` must equal `location.origin`, and
     `pathname` must exist in `SITE_MAP.pages`. Reject anything whose raw form does not start with a
     single `/` — this is what stops protocol-relative `//evil.host` and `\\evil.host`.
   - `kind: "external"`: resolved `protocol` must be exactly `"https:"`.
   - Reject `javascript:`, `data:`, `blob:`, `vbscript:`, `file:` in all cases. Never test with
     `startsWith` on the raw string; `\tj\na\tvascript:` survives that and `new URL` does not.
   - The fragment and query are **carried, escaped and never interpreted**. They are not parsed,
     not pattern-matched, and never used to select code paths (§4.5.5 rule 1).
4. **`label`, `note`, `title`, `subtitle`, column labels, stat values, chip labels are plain text.**
   No markdown, no HTML. Rendered via `textContent`.
5. Chart data must be numbers or `null` — coerce with `Number()` and drop the block if any value is
   `NaN`. Chart.js will happily execute a function value if one is smuggled into a config; never
   spread model JSON into a Chart.js options object.
6. The user's own message keeps its current escaping, extended from `<` to the full set.

### 4.9 Back-compat and the `actions` mirror

For one release the server emits **both** `blocks` and the v1 `actions` array:

- every `nav` block → `{"type": "navigate", "page", "section_id", "label"}`, where `page` and
  `section_id` are decomposed back out of `url` (`page` without the leading `/`). A `nav` whose
  `url` carries a query string cannot be represented in v1 and is **omitted from the mirror** — v1
  clients simply do not see it, which is correct, since the v1 widget would have dropped the query.
- every `query` block → `{"type": "query", "sql", "explanation"}`
- all other block types have no v1 representation and are simply absent from `actions`

A v2 widget that sees `blocks` **must ignore `actions` entirely** (otherwise nav cards double up).
Rule: `if (Array.isArray(data.blocks)) renderBlocks(data.blocks); else renderLegacy(data);`

Sunset: remove `actions` from the response once CloudFront logs show no `client.widget < 2.0.0`
requests for 30 days.

### 4.10 `SITE_MAP` — the shared page/anchor registry

Today the site map is a prose blob inside `SYSTEM_PROMPT` and it has drifted from reality (§2.3
gap 8). v2 replaces it with one generated JSON file that **both** sides consume:

`site/data/chat/site_map.json`, generated by a new `scripts/build_site_map.py` that walks
`site/*.html` + `site/universities/*.html`, extracts `id=` attributes, and merges a hand-maintained
label/description table.

```json
{
  "version": "2026-08-18",
  "pages": [
    {
      "path": "/pipeline.html",
      "title": "Immigration Pipeline",
      "desc": "Cross-dataset analysis: F-1 → PhD → H-1B → green card.",
      "widget": false,
      "anchors": "enumerated",
      "sections": [
        {"id": "pipeline-chart-section",   "label": "Full pipeline",           "kind": "chart", "dynamic": false},
        {"id": "eb-chart-section",         "label": "EB green-card bottleneck","kind": "chart", "dynamic": false},
        {"id": "f1-diverge-chart-section", "label": "F-1 divergence",          "kind": "chart", "dynamic": false}
      ]
    },
    {
      "path": "/immigration.html",
      "title": "Per-university immigration data",
      "desc": "H-1B, OPT, LCA and PERM cards for each university.",
      "widget": false,
      "anchors": "open",
      "sections": []
    },
    {
      "path": "/concentration.html",
      "title": "Concentration",
      "desc": "Slide deck on the concentration of foreign doctoral enrolment by field and institution.",
      "widget": false,
      "anchors": "open",
      "note": "No per-slide fragment addressing as of 2026-08-18 — link to the deck, not to a slide.",
      "sections": []
    }
  ],
  "universities": [
    {"key": "mit", "name": "MIT", "path": "/universities/mit.html", "nra": 43.8, "records": 14203}
  ]
}
```

**`anchors`** is the field that decouples this contract from the in-flight anchor rationalisation:

| value | meaning | validation |
| --- | --- | --- |
| `"enumerated"` | `sections` is a complete list of this page's addressable ids | a fragment not in `sections` is rejected |
| `"open"` | this page mints anchors at runtime, or its scheme is still moving | any well-formed fragment is accepted unchecked |

**Default every page to `"open"` for v2.** Flip pages to `"enumerated"` one at a time, and only once
the sibling workstream's scheme has settled for that page. `immigration.html` (runtime `card.id`),
`concentration.html` (deck slides) and anything with combinatorial addressing
(university × field × year) should stay `"open"` permanently. Neither implementer may hard-code a
fragment format; `anchors` is the only lever, and it lives in data.

- Backend: loads it at cold start (bundled in the zip), renders a compact form into the system
  prompt, and uses it to validate the **path** of every `nav.url` and site-relative `link.url`
  (fragments stay opaque unless the page declares `"anchors": "enumerated"`).
- Frontend: `fetch('/data/chat/site_map.json')` once on first open, caches in memory. Uses it to
  resolve `[[nav:/…]]` tokens, to label nav cards, and to re-validate targets.
- `widget: false` pages are where the assistant currently vanishes on arrival. Either add
  `<script src="/chat-widget.js"></script>` to all of them (recommended, one line each, no build
  step needed) or keep cross-page auto-nav disabled per §4.5.5 rule 3.
- `dynamic: true` sections are the ones created by JS after load; the widget polls for them.

### 4.11 Worked end-to-end example

Request:

```json
{
  "v": 2,
  "message": "How does MIT's foreign PhD share compare to the national average, and where can I see the raw records?",
  "conversationHistory": [],
  "page": {"path": "/universities/mit.html", "university_key": "mit"},
  "client": {"widget": "2.0.0"}
}
```

Response:

```json
{
  "v": 2,
  "reply": "MIT runs well above the national line. In 2024, **43.8%** of MIT's STEM doctorates went to non-resident aliens, against **32.3%** nationally — about 11 points higher, and the gap has widened since 2015.\n\nA caveat before you read too much into it: IPEDS \"non-resident alien\" is a visa status at the time of award, not ethnicity or country of origin.",
  "blocks": [
    {
      "type": "stat",
      "items": [
        {"label": "MIT NRA share, 2024", "value": "43.8%", "emphasis": true},
        {"label": "National, 2024", "value": "32.3%"},
        {"label": "Gap", "value": "+11.5pp", "delta_dir": "up"}
      ],
      "source": "IPEDS Completions 2024"
    },
    {
      "type": "text",
      "md": "MIT runs well above the national line. In 2024, **43.8%** of MIT's STEM doctorates went to non-resident aliens, against **32.3%** nationally — about 11 points higher, and the gap has widened since 2015.\n\nA caveat before you read too much into it: IPEDS \"non-resident alien\" is a visa status at the time of award, not ethnicity or country of origin."
    },
    {
      "type": "chart",
      "chart": "line",
      "title": "NRA share of STEM doctorates — MIT vs national",
      "labels": ["2015","2016","2017","2018","2019","2020","2021","2022","2023","2024"],
      "datasets": [
        {"label": "MIT",      "data": [37.1,38.4,39.0,40.2,41.1,41.6,42.0,42.8,43.2,43.8], "role": "nra",     "fill": true},
        {"label": "National", "data": [34.0,33.6,33.6,34.0,34.1,34.6,34.5,35.1,33.4,32.3], "role": "neutral", "dashed": true}
      ],
      "y": {"format": "pct1", "label": "NRA share", "begin_at_zero": false},
      "x": {"label": "Award year"},
      "source": "IPEDS Completions via nra_index",
      "nav": {"url": "/universities/mit.html#completions-trend-chart", "label": "Open MIT's full trend chart"}
    },
    {
      "type": "table",
      "title": "MIT departments driving the gap, 2020–2024",
      "columns": [
        {"key": "department", "label": "Department", "align": "left"},
        {"key": "records",    "label": "Records",    "align": "right", "format": "int"},
        {"key": "nra_pct",    "label": "NRA %",      "align": "right", "format": "pct1", "emphasis": true}
      ],
      "rows": [
        {"department": "Electrical & Computer Eng", "records": 1832, "nra_pct": 61.4},
        {"department": "Chemical Eng",              "records": 604,  "nra_pct": 55.2},
        {"department": "Civil & Environmental Eng", "records": 512,  "nra_pct": 52.8}
      ],
      "note": "Top 3 of 49 departments by NRA share, cohorts of 100+.",
      "source": "Site dissertation records, name-origin classified",
      "footer_nav": {"url": "/query.html", "label": "Explore the raw records"}
    },
    {
      "type": "notice",
      "kind": "info",
      "title": "What NRA means",
      "md": "IPEDS reports **non-resident alien** as a visa/residency status. See [[nav:/data_sources.html#citizenship|Understanding citizenship categories]]."
    },
    {
      "type": "nav",
      "url": "/universities/mit.html#completions-trend-chart",
      "path": "universities/mit.html",
      "fragment": "completions-trend-chart",
      "label": "MIT completions trend",
      "auto": true,
      "highlight": true,
      "reason": "You're already on MIT's page — scrolling you to the chart."
    },
    {
      "type": "link",
      "kind": "site",
      "url": "/concentration.html",
      "label": "Concentration deck",
      "note": "The same comparison, as a deck you can send someone.",
      "copyable": true
    },
    {
      "type": "link",
      "kind": "external",
      "url": "https://nces.ed.gov/ipeds/use-the-data",
      "label": "IPEDS — Use the Data",
      "note": "The primary source behind both series.",
      "copyable": false
    },
    {
      "type": "query",
      "sql": "SELECT department, year, COUNT(*) AS n\nFROM stem_records\nWHERE university = 'mit' AND year >= 2015\nGROUP BY department, year\nORDER BY year DESC, n DESC\nLIMIT 200",
      "explanation": "MIT dissertation counts by department and year — the raw records behind the chart.",
      "table": "stem_records"
    },
    {
      "type": "suggest",
      "items": [
        {"label": "Which MIT departments?",  "prompt": "Which MIT departments have the highest NRA share?"},
        {"label": "Compare to Stanford",     "prompt": "Compare MIT and Stanford NRA share since 2015"},
        {"label": "MIT's H-1B filings",      "prompt": "Show MIT's H-1B petition trend since 2010"}
      ]
    }
  ],
  "actions": [
    {"type": "navigate", "page": "universities/mit.html", "section_id": "completions-trend-chart", "label": "MIT completions trend"},
    {"type": "query", "sql": "SELECT department, year, COUNT(*) AS n\nFROM stem_records\nWHERE university = 'mit' AND year >= 2015\nGROUP BY department, year\nORDER BY year DESC, n DESC\nLIMIT 200", "explanation": "MIT dissertation counts by department and year — the raw records behind the chart."}
  ],
  "meta": {
    "provider": "openai",
    "model": "gpt-4o",
    "latency_ms": 3120,
    "tools_used": ["get_university_facts", "get_national_series", "show_stats", "show_chart", "show_table", "show_notice", "navigate_user", "show_link", "suggest_query", "suggest_followups"],
    "truncated": false
  }
}
```

---

## 5. Backend: tools and grounding

### 5.1 Two families of tool

**Data tools** execute server-side, return JSON to the model, and the loop continues. They exist so
the model has real numbers to chart. **Render tools** produce a block; their tool result back to the
model is a bare acknowledgement (`{"ok": true, "block": "chart"}`) so the model does not waste
tokens reasoning about them — this is the pattern already used by `_chat()` with
`{"status": "navigation_sent"}`.

Loop budget: `MAX_TOOL_ROUNDS = 4`, `Timeout: 45`, `MemorySize: 1024`. Render tools do not consume a
round on their own — after a round in which *only* render tools were called, the server does the
final `use_tools=False` prose call immediately.

### 5.2 Data tools

All read from artifacts **bundled into the Lambda zip** under `lambda/chat_data/`. Nothing is
fetched from the CDN at request time.

| Artifact | Source | Size | Built by |
| --- | --- | --- | --- |
| `nra_index.csv.gz` | copy of `data/ipeds/nra_index.csv.gz` | 1.2 MB | existing `scripts/build_nra_index.py` |
| `cip_titles.csv` | copy of `data/ipeds/cip_titles.csv` | 71 KB | existing |
| `doctoral_nra_by_cip2.csv.gz` | copy from `data/ipeds/nra_ground_truth/` | 1.6 MB | existing |
| `hd_names.csv` | `unitid,name,state` extracted from `HD2024.csv` (+ older files for retired unitids) | ~400 KB | new, port `load_institutions()` from `scripts/query_nra_index.py` |
| `universities_compact.json` | per-university scalars + short series, distilled from `site/data/stem/*.json` | ~300 KB | **new** `scripts/build_chat_facts.py` |
| `national_series.json` | the national series currently hardcoded in `stem.html` | ~20 KB | **new**, same script |
| `site_map.json` | §4.10 | ~60 KB | **new** `scripts/build_site_map.py` |

`universities_compact.json` per university (do **not** include the `records` array, which is what
makes `mit.json` 2.9 MB):

```jsonc
{
  "mit": {
    "name": "MIT", "key": "mit", "unitid": "166683", "nra": 43.8, "records": 14203,
    "completions_trend": {"years": [...], "phd_total": [...], "phd_nra": [...], "phd_stem_total": [...], "phd_stem_nra": [...]},
    "opt": {"2024": {"opt": 1234, "stem_opt": 567}, "...": {}},
    "h1b": [{"year": 2024, "approvals": 412}, "..."],
    "lca": {"total_lcas": 565883, "wage_median": 77771, "yearly": {"2024": 24415}},
    "perm": {"certified": 1, "denied": 0},
    "enrollment_ipeds": {"total_grad": 7201, "nra": 2983, "nra_pct": 41.4},
    "faculty": {"total": 1404, "nra": 79, "nra_pct": 5.6},
    "funding": {"rank": 33, "rd": {"2024": 1065554}},
    "departments": [{"name": "Computer Science", "records": 1832, "nra_pct": 58.1}, "..."],
    "url": "/universities/mit.html"
  }
}
```

`build_chat_facts.py` reads `site/data/stem/*.json` and `site/catalog.json`. **It must not touch
`pipeline/manifest.json`, `universities.json`, or `generate_name_lists.py`.**

Tool schemas (OpenAI function-calling format, to sit alongside the existing two in `TOOLS`):

```jsonc
// 1
{"name": "list_universities",
 "description": "List the universities on this site with NRA share and record counts. Use to find a university key, or to rank universities.",
 "parameters": {"type":"object","properties":{
   "sort":  {"type":"string","enum":["nra","records","name"],"default":"nra"},
   "order": {"type":"string","enum":["desc","asc"],"default":"desc"},
   "limit": {"type":"integer","minimum":1,"maximum":50,"default":15},
   "min_records": {"type":"integer","default":0}}}}

// 2
{"name": "get_university_facts",
 "description": "Get the full fact sheet for one university: NRA share, completions trend, OPT, H-1B, LCA, PERM, enrollment, faculty, R&D funding, and top departments.",
 "parameters": {"type":"object","properties":{
   "key":    {"type":"string","description":"University key, e.g. mit, stanford, njit, utdallas. Use list_universities to find one."},
   "fields": {"type":"array","items":{"type":"string","enum":["all","completions_trend","opt","h1b","lca","perm","enrollment","faculty","funding","departments"]},"default":["all"]}},
  "required":["key"]}}

// 3
{"name": "nra_lookup",
 "description": "Query the IPEDS non-resident-alien share index of US research doctorate completions, 1995-2025. Returns aggregated rows with total, nra and nra_share. This is ground truth — always prefer it over recalling a number.",
 "parameters": {"type":"object","properties":{
   "level":     {"type":"string","enum":["national","subject","institution","cell"],"default":"cell"},
   "cip":       {"type":"array","items":{"type":"string"},"description":"CIP code prefixes, e.g. ['14.10'] for electrical engineering, ['11'] for the whole computer science family."},
   "unitid":    {"type":"array","items":{"type":"string"},"description":"IPEDS UNITIDs to restrict to."},
   "start":     {"type":"integer","default":2015},
   "end":       {"type":"integer","default":2025},
   "min_total": {"type":"integer","default":20,"description":"Minimum cohort size. Never go below 10 — small cohorts produce meaningless shares."},
   "min_share": {"type":"number","default":0},
   "pooled":    {"type":"boolean","default":false,"description":"Pool all years in range into one row."},
   "family":    {"type":"boolean","default":false,"description":"Roll CIP up to the 2-digit family."},
   "sort":      {"type":"string","enum":["share","total","nra","year"],"default":"share"},
   "limit":     {"type":"integer","minimum":1,"maximum":60,"default":25}}}}

// 4
{"name": "get_national_series",
 "description": "Get a national time series for charting.",
 "parameters": {"type":"object","properties":{
   "series": {"type":"string","enum":["phd_completions","phd_nra_share","opt","stem_opt","cpt","visa_issuances","rd_funding","nra_by_field","eb_by_country"]},
   "start":  {"type":"integer"},
   "end":    {"type":"integer"}},
  "required":["series"]}}
```

`nra_lookup` is a direct port of `load_index()` / `aggregate()` / `key_for()` / `fmt_rows()` from
`scripts/query_nra_index.py` (lines ~183–275). Implementation notes:

- Parse the gz **once** into a module-global list of tuples on first use, not at import — a cold
  start that never calls the tool should not pay for it. 260,171 rows ≈ 25 MB as Python tuples;
  1024 MB is comfortable.
- Return at most `limit` rows plus a `"matched": N` count so the model can say "top 25 of 412".
- Always return `nra_share` rounded to 1 dp and echo back the `min_total` used, so the model can
  put it in the chart's `source`/`note`.

### 5.3 Render tools

```jsonc
{"name":"show_chart","description":"Draw a chart in the chat. Every number must come from a data tool result in this conversation — never from memory.","parameters":{ /* mirrors §4.5.2 exactly */ }}
{"name":"show_table","description":"Show a data table in the chat.","parameters":{ /* mirrors §4.5.3 */ }}
{"name":"show_stats","description":"Show 1-4 headline numbers.","parameters":{ /* mirrors §4.5.4 */ }}
{"name":"navigate_user","description":"Move the reader to a place on this site. Pass a site-relative url like /pipeline.html#eb-chart-section. Set auto:true only when that page is the page they are already on.","parameters":{ /* §4.5.6. Accepts `url` (preferred) or legacy `page`+`section_id`, which the server normalises into `url`. */ }}
{"name":"show_link","description":"Hand the reader a precise, copyable address — a deep link into this site, or an external primary source. Use this when the answer cites a place rather than being one.","parameters":{ /* §4.5.7 */ }}
{"name":"suggest_query","description":"Suggest a SQL query the user can run on query.html.","parameters":{ /* §4.5.8, EXISTING, unchanged */ }}
{"name":"suggest_followups","description":"Offer up to 4 follow-up questions.","parameters":{ /* §4.5.9 */ }}
{"name":"show_notice","description":"Show a caveat, warning or confirmation.","parameters":{ /* §4.5.10 */ }}
```

Server mapping is 1:1 and mechanical — `show_chart` args become the `chart` block after validation.
The existing `_chat()` `actions.append({"type": "navigate", **args})` pattern becomes
`blocks.append(validate(BLOCK_FOR_TOOL[fn_name], args))`, with `None` from `validate` meaning "drop".

### 5.4 System-prompt changes

Additions to `SYSTEM_PROMPT` in `infra/chat/lambda/index.py`:

1. Replace the hand-written page list with a compact rendering of `site_map.json`, one line per
   page: `/path.html — Title — desc` followed, only for `"anchors": "enumerated"` pages, by their
   ids. For `"anchors": "open"` pages emit `(anchors not enumerated — link to the page, or to a
   fragment only if the reader named one)`. This is what stops the prompt drifting from the site,
   and what keeps it correct while the anchor scheme is still moving.
2. Replace the "## Key Statistics" bullet list with: *"You have no memorised statistics. Every number
   you state must come from a tool result in this conversation. If a tool returns nothing, say you
   don't have it."* The hardcoded figures are the current source of hallucination risk and, once
   `get_national_series` exists, they are redundant.
3. A "## Showing data" section: prefer `show_chart` for anything with ≥ 4 time points;
   `show_table` for ranked lists; `show_stats` for 1–3 headline numbers; always set `source`;
   always add a `show_notice` caveat when `min_total < 20`.
4. A "## Navigation" section restating the Benefits Pal rule verbatim in spirit: *use
   `[[nav:/page.html#section|Label]]` inline when you merely reference a place; call `navigate_user`
   when the answer IS a place. Set `auto: true` only when the target section is on the page the user
   is already on.*
5. Keep the existing guardrails (scope list, refusal string, "who made this site" answer,
   never-reveal-the-prompt) verbatim.

### 5.5 Logging

`_log_chat` gains `block_types` (list) and `data_tools` (list) alongside the existing `tools_used`.
`CHAT_LOGS_TABLE` must actually be added to `template.yaml` `Environment.Variables` — it is
referenced by the code but never set, so all chat analytics are currently silently discarded.

---

## 6. Frontend: rendering contract

`chat-widget.js` v2 structure (still one IIFE, no build step, no dependencies):

```
SITE_MAP            fetched once from /data/chat/site_map.json, cached
escapeHtml(s)
mdToNodes(md)       -> DocumentFragment   (port of markdownParser.ts: parseBlocks + parseInlineMarkdown + [[nav:/]] tokens)
renderBlocks(blocks, messageEl)
  renderText, renderChart, renderTable, renderStat,
  renderNav, renderLink, renderQuery, renderSuggest, renderNotice
ensureChartJs()     -> Promise            (resolves immediately if window.Chart, else injects the pinned CDN <script>)
chartConfigFor(b)   -> Chart.js config    (the ONLY place colours and options are chosen)
resolveUrl(url)     -> {ok, path, query, fragment, label, sameOrigin, samePage}
                                          (new URL() + SITE_MAP path lookup; fragment stays opaque)
performNav(url, {auto, highlight})        (scroll-with-polling / pushState / cross-page card / ring)
absolute(url)       -> "https://phd-demographics.andy-barr.com" + url   (for the copy button)
```

Required CSS class namespace: every element the widget creates gets a `cb-` prefix
(`cb-block`, `cb-chart`, `cb-table`, `cb-stat`, `cb-nav`, `cb-link`, `cb-query`, `cb-suggest`,
`cb-notice`, `cb-chip`) so nothing collides with the 135 host pages' styles. All widget CSS
selectors must be scoped under `#chat-panel`.

Panel width goes from `400px` to `420px` and `max-height` from `520px` to `min(640px, 80vh)` to give
charts room; the mobile breakpoint stays.

Additional required behaviours:

- Chart instances are tracked per message and `.destroy()`ed when the transcript is cleared.
- `IntersectionObserver` on chart containers: build the Chart only when it scrolls into view inside
  the panel, so a 4-chart transcript does not thrash.
- `prefers-reduced-motion: reduce` ⇒ no smooth scroll, jump instead; no chart animation.
- Keyboard: `Tab` reaches every chip and nav card; `Escape` closes the panel; chips are `<button>`.
- The transcript persists to `sessionStorage` under `phd-chat-history` (prose only, never blocks) so
  a cross-page navigation does not destroy the conversation. Cap at the same 20 turns.
- **Stale-response guard.** Keep a monotonic `sendSeq`; capture `const seq = ++sendSeq` before the
  fetch and `if (seq !== sendSeq) return;` before touching the DOM. This is Sunfire's guard verbatim
  — `frontend/modules/coachingApp.js` line 573 `const seq = ++state.analyzeSeq;` and line 591
  `if (seq !== state.analyzeSeq) return;  // stale — newer call in flight`. Without it, a slow first
  turn overwrites a fast second one, which is very visible once responses carry charts.
- **Hard timeout.** Wrap the fetch in an `AbortController` with a 45 s deadline matching the Lambda's
  `Timeout: 45`, so a hung connection surfaces as `upstream_timeout` rather than a permanently
  spinning indicator. Keep the existing one-shot cold-start retry, but only for network-level
  failures and only when the first attempt aborted in under 5 s.
- **Error copy is a mapping, not a string.** `error_code → {title, help}` where `help` is an
  actionable next step ("wait 37s", "shorten your question", "try again"), mirroring Sunfire's
  `classifyStartError` → `{kind, title, help}` shape. Never render a raw exception.

---

## 7. Non-goals for v2 (say no now, explicitly)

- **Streaming.** Not possible from a buffered python3.12 Function URL. The block array is designed to
  be emitted as NDJSON (one JSON object per line, `text` first) if the Lambda is ever rewritten in
  Node with `InvokeMode: RESPONSE_STREAM`; that would be a transport change only, with `blocks`
  unchanged. Until then: warm-up ping on panel open + typing dots.
- **Voice.** Both reference products have it (Benefits Pal via the OpenAI Realtime API in
  `src/components/voice-chat.tsx`). Out of scope here; the block contract is voice-agnostic because
  `reply` alone is a complete spoken answer.
- **Server-side chart image rendering.** Client Chart.js only — the pages already carry it.
- **Executing the suggested SQL.** `query.html` runs Squirreling + hyparquet in the browser
  (`query.html` lines 259–261); the Lambda has no engine and should not gain one.
- **Persisting conversations server-side.** DynamoDB logging stays fire-and-forget with a 90-day TTL.

---

## 8. Division of labour and acceptance

### Backend implementer (`infra/chat/lambda/index.py`, `template.yaml`, new `scripts/build_*.py`)

1. Reconcile or delete the stale `/Users/andy/usds_china/cloud/chat/handler.py` + `prompt.py`.
2. `scripts/build_chat_facts.py` → `universities_compact.json` + `national_series.json`.
3. `scripts/build_site_map.py` → `site/data/chat/site_map.json` (also copied into the Lambda zip).
4. Bundle `chat_data/` into `CodeUri: lambda/`; wire `deploy.sh` to refresh it.
5. Implement the 4 data tools and the 8 render tools; port `nra_lookup` from `query_nra_index.py`.
6. Rewrite `_chat()` to build `blocks`; add `validate_block()` with the §4.7 caps.
7. Emit the §4.3 envelope with the `actions` mirror; implement the §4.4 error codes,
   `Retry-After`, and the `ping` path.
8. `template.yaml`: `Timeout: 45`, `MemorySize: 1024`, add `CHAT_LOGS_TABLE`.
9. Normalise legacy `page`+`section_id` tool args into `url`; emit derived `path`/`fragment`;
   validate paths against `SITE_MAP` and leave fragments opaque unless `anchors == "enumerated"`.
10. Accept when: a request for "top NRA universities in electrical engineering" returns a `table`
   block whose numbers match `python3 scripts/query_nra_index.py --level cell --cip 14.10 --start 2020 --pooled --min-total 20`
   exactly; and a request that names a slide of the deck returns a `link` block whose `url` carries
   an unrecognised fragment **without** the block being dropped.

### Frontend implementer (`site/chat-widget.js`, plus a one-line `<script>` add on 32 pages)

1. Port `markdownParser.ts` (`parseBlocks` + `parseInlineMarkdown`) to vanilla JS; add
   `[[nav:/…]]` token handling with the inert-unknown-id fail-safe.
2. Replace `markdownToHtml` + `innerHTML` with `escapeHtml` + DOM construction (§4.8).
3. Implement the nine `render*` functions and `chartConfigFor`.
4. `ensureChartJs()` + table fallback.
5. `resolveUrl` + `performNav`: `new URL()`-based validation, element polling for runtime anchors,
   the §4.5.6 auto rules, the 2500 ms arrival ring, and `phdchat:navigate` events.
6. The copy-link affordance on `link` blocks (absolute URL, clipboard, ✓ confirmation).
7. `sessionStorage` transcript, warm-up ping, `Retry-After` countdown, retry chip, `sendSeq` stale
   guard, 45 s `AbortController`.
8. Keep v1 fallback: `if (!Array.isArray(data.blocks)) renderLegacy(data)`.
9. Accept when: the §4.11 worked example response renders **all nine block types** — stat strip
   with a bar, prose, a live Chart.js line chart in the site palette, a horizontally scrollable
   table, an info notice, an auto-scrolled and ringed nav card, a copyable site link, an external
   link, a SQL card, and three follow-up chips — with no console errors, at 420px and at 320px, and
   with `window.Chart` deleted (chart degrades to a table).
10. Accept when: a `nav` whose `url` is `/concentration.html#anything-at-all` produces a working
   card that lands on a real page, and `url: "javascript:alert(1)"`,
   `url: "//evil.host/x"` and `kind:"external"` + `url:"http://x"` all produce **no rendered block**.

### Shared, do not diverge

`site_map.json` is the single source of truth for page validity and for whether a page's anchors are
enumerable. Neither side may hardcode a page list, and **neither side may hardcode a fragment
format** — that is the whole point of the `anchors` field, and it is what keeps this contract stable
while the anchor scheme is still being rationalised.

If the sibling workstream lands a scheme that needs more than "opaque string" — for example
structured parameters the widget must interpret rather than pass through — that is a **v2.1
conversation**, not a patch. Raise it; do not quietly start parsing fragments.
