# AGENT PROMPT — Economy God Mode

> Paste this entire document into a coding agent as its brief. The agent must
> follow it task by task, in order, and must not skip a task's acceptance
> criteria to move on. If any instruction in this document conflicts with a
> library default, a shortcut, or the agent's own preference, this document
> wins.

## 0. What you are building

Build **Economy God Mode**: a visually stunning, playable world-economy
simulator for governments and businesses.

A user opens the app, sees a globe floating in space, picks a country,
picks a city from pins that appear for that country, writes a plain-language
question about that city, and watches a living miniature-model city react as
simulated households, firms, banks, and government agents earn, spend,
borrow, hire, fail, and adapt.

San Francisco, USA is the sole demo city and the judged demo path. The architecture stays global-capable, but this demo builds one city only. Do not build other cities for this demo.

**The judged story, in order, and the UI must make it unmistakable: healthy economy → bank shock → cascading consequences → AI intervention → compare futures.** The main screen is a dark, polished financial command center: a dark canvas with the animated city as the main visual, and the light-grey translucent side panel to the side (Section 3), never over the city. A judge must be able to, without opening a terminal: create a world, trigger a bank crisis, inspect why a business is struggling, watch the AI test interventions, and compare three futures.

**The simulation is stylized, not a forecast.** Every screen that shows
simulated results must carry the label: "Stylized simulation — not a
forecast of a real city." Never present a simulated outcome as a prediction
about a real place, a real company, or a real policy.

## 0A. Division of labor — UI first, backend as context only

Read this before starting any task. H is working on the UI. The backend
in this document — simulation engine, ledger, branching engine, Nemotron
proxy, and x402 — is CONTEXT ONLY for the UI build. It exists to tell
the UI exactly what data it will receive, in what shape, and in what
states. It is not to be implemented now, and UI work must never wait
for it.

Rules that follow from this:

- Build the UI against fixtures, not against a live backend. Every
  backend response the UI needs is defined as a fixture in Section 19A.
  The UI reads fixtures through one data layer,
  `apps/web/src/data/fixtures.ts`, with functions like
  `getSnapshot(tick, branch)`, `getFeed(tick)`,
  `getProposal()`, and `getInspector(actorId)`. A real backend
  later replaces only that layer. No UI component may import
  from `sim/`, `server/`, or call a live LLM endpoint directly.
- Do not implement `sim/engine.ts`, `sim/ledger.ts`,
  `sim/branch.ts`, or `server/` beyond empty stubs with the
  type signatures from this document. Stubs exist so the UI
  compiles and so a future backend implementer knows the
  contract. Stubs must never contain real simulation logic
  disguised as UI logic, and UI code must never contain
  simulation formulas copied in to "make it work for now".
- Simulation, branching, and Nemotron sections (12, 13, 17)
  are specifications of the data the UI displays, not tasks
  to build now. Read them to get field names, value ranges,
  and state transitions right. Do not turn them into a
  backend build.
- The demo must run fully from fixtures. Globe, pins, prompt,
  transition, San Francisco city, KPIs, feed, inspector,
  timeline, and branch comparison must all work with no
  server, no network, and no LLM call. If a UI feature only
  works when a backend is running, it is not done.
- **Agent integration must be seamless.** The agent is not a separate
  feature, page, tab, chat window, or modal. It lives inside the
  existing right panel, in the same visual language as the feed,
  and it must feel like a natural step in the simulation, not an
  interruption to it. See Section 17.0 for the exact rules.
- UI polish is the deliverable. When time is short, cut
  backend fidelity first, never UI polish. A beautiful,
  fixture-driven San Francisco UI that shows exactly the
  right states beats a half-built backend with a rough UI.
- **Connecting the backend later changes only the data layer, not the UI.** Build against mock data first, then a backend adapter implements exactly the same functions as `fixtures.ts` (`getSnapshot`, `getFeed`, `getProposal`, `getInspector`, plus `getFork`, `getNetwork`, `getPayment`, `getCrisisOptions` in Section 19A). The backend provides balances, metrics, outcomes, and action statuses; live events replace fixture feed items with the same `FeedItem` shape. Frontend animation must reflect backend results, never invent its own balances, metrics, or outcomes. Do not invent backend endpoint URLs in UI code; the adapter is the single place that knows them, and it is out of scope for the UI build.

## 1. Non-negotiables — read these first, violate none of them

1. **Visuals are the product.** If the globe does not look good in a
   screenshot with zero interaction, if the globe-to-city transition is
   a hard cut, or if the city looks dead, the build has failed, even if
   the simulation is correct. Polish the visuals before adding any
   sponsor integration.
2. **No fake metrics.** Every number in the KPI strip and side feed must
   come from the simulation ledger or a simulation aggregate. Never
   hand-write a trend, never animate a chart to a pre-chosen endpoint,
   never invent a household, firm, or transaction that is not in the
   world state.
3. **No LLM call inside the simulation tick loop.** The tick function
   must be synchronous, deterministic, and runnable with no network.
   LLM calls happen only at the decision points listed in Section 16,
   through the proxy in Section 17, and their results are cached in the
   branch snapshot.
4. **No San Francisco-specific branches in the engine.** There must be no
   `if (city === "San Francisco")` in `sim/`, `city/`, or `globe/`. San Francisco is
   one config file. Every other city is the same code reading a
   different config.
5. **No random city on every load.** A city with the same seed must
   produce the same layout on every load. Layout seed and simulation
   seed are separate values, stored separately, and branches share the
   layout seed.
6. **No API key in the browser.** The Nemotron key lives only in server
   environment variables. The browser talks only to your own proxy
   endpoints. If the proxy is not configured, the UI must say so
   clearly and must never fake a Nemotron response.
7. **UI first, backend as context only.** H works on the UI. Backend code in this document is context: data shapes, states, and contracts for the UI to build against, implemented as fixtures in Section 19A. Do not build a real backend, simulation engine, or LLM proxy as part of UI work, and do not let UI work wait for one. The core demo must work offline, from fixtures, with no server and no LLM call.

8. **Colour is never the only signal.** Every green/red indicator must
   also carry an arrow (▲ / ▼) and wording ("spending up" / "spending
   down"), so the feed is readable without colour vision.

## 2. Tech stack — use exactly this unless a task says otherwise

- Vite + React + TypeScript. Scaffold with:
  `npm create vite@latest economy-god-mode -- --template react-ts`
- Three.js for the globe. Use `three-globe` for polygons, hover, pins,
  and camera moves unless you can justify a replacement in a comment.
- Plain Canvas 2D for the city. Do not introduce a 3D city engine.
- Zustand for app state. Do not put 60fps animation values in React
  state or in Zustand. Animation reads refs and tick snapshots directly.
- Vitest for tests. No database, no ORM, no server process for the
  core demo. World state is plain serializable JSON.
- Install: `npm install three three-globe zustand` and
  `npm install -D vitest`.

Core demo run commands must be exactly:

```
npm run dev
npm run build
npm test
```

## 3. Visual design system — exact values

Use these values. Do not invent a second palette halfway through.

- Background, space: `#05070F`. Starfield: white points, varying
  opacity 0.3–1.0, varying size 1–2px, slow parallax drift.
- Globe: realistic Earth, not a stylised dark map. The base globe
  is a STYLIZED, modern, sleek, minimalist Earth in the style of the reference image: flat muted blue oceans, flat muted green and tan land, thin clean white country borders, minimal small ocean/continent labels, white polar ice caps, and visible continents that are instantly recognisable. At a glance it must read as clean modern Earth, NOT photorealistic, NOT noisy satellite texture, NOT heavy clouds.
- Earth texture: use a stylized flat Earth texture / vector-style globe material placed locally (for example a cleaned, muted Blue Marble style map flattened to flat colours) referenced locally. Do not fetch a photorealistic texture from a live URL at runtime for the demo. Never ship a noisy photorealistic satellite globe or a flat dark-blue globe and call it done — the target is the clean reference style above.
- Clouds: a second, slightly larger transparent sphere
  (radius 1.01x) with at most a very subtle, flat cloud layer, rotating slowly — or no cloud layer at all if it adds noise. Clouds must never dominate or make the globe photorealistic.
- Lighting: a directional "sun" light plus soft ambient light,
  so one side of Earth is brightly lit and the terminator
  (day/night edge) is visible. Add a subtle atmosphere glow
  around the limb, blue-white, visible in a screenshot.
- Country overlays sit ON TOP of the Earth texture and must
  never replace it. Unselected countries: transparent fill,
  thin white country outline at 25% opacity. Hovered country:
  outline brightens to white at 90% opacity, fill stays
  transparent, cursor becomes a pointer. Selected country:
  translucent yellow fill `rgba(255, 215, 0, 0.45)` over the
  Earth texture plus a solid `#FFD700` outline at 2px, so the
  underlying land and ocean are still visible through the
  yellow. Do NOT dim the rest of the Earth to 35% — the rest
  of the planet must stay recognisably Earth while one country
  is highlighted.
- Pins: MINIMALIST. Small clean dots with a thin stem, no neon glow, no large map-pin icons. Active pin: small yellow dot, slightly larger than the others, with a thin subtle ring. Disabled pins: small grey dots.
  Active pin: solid `#FFD700` core, ring radius animating 14px → 26px
  over 1.2s, looping. Pin size scales by population: radius =
  `8 + 6 * (population / maxPopulationInCountry)`, clamped to 8–16px.
- City palette: dark slate roads `#1F2937`, footpaths `#374151`,
  parks `#14532D`, water `#0E7490`, building roofs sampled from a
  per-city palette (see Section 11), building sides shaded 20% darker
  than the roof, window lights `#FDE68A` at night.
- Panels: LIGHT GREY and translucent, NOT dark. Panel background
  `rgba(230, 233, 238, 0.85)`, backdrop blur 16px, 1px border
  `rgba(255, 255, 255, 0.65)`, border radius 16px, padding 16px,
  shadow `0 8px 32px rgba(0,0,0,0.25)`. Inner cards:
  `rgba(255, 255, 255, 0.65)`. This panel is a separate side
  column, never an overlay on the globe or city.
- Sidebar must look MODERN and SLEEK, like a premium product UI,
  NOT like a PowerPoint slide with stacked square textboxes.
  Forbidden: multiple stacked bordered rectangles, a separate
  box for every field, hard borders around the prompt textbox.
  Required: one tall softly rounded panel (28px corners), generous
  whitespace, large bold city heading with a small muted country
  label under it, prompt as ONE textbox only: a single soft
  rounded input field with a lighter background, containing the
  prompt in normal dark sans text that looks typed in, with a
  text cursor at the end (sans, not italic), a pill-shaped primary button,
  parsed scenario as small pill chips, and KPI/feed rows separated
  only by thin hairline dividers, no boxed cards.
- Text: system sans stack, falling back to Inter if available.
  Headings 600 weight, dark charcoal `#111827`. Body text
  `#111827`, secondary text `#374151` minimum, so text is easy
  to read on light grey. Never use light grey or white text on
  this panel. Country label: 28px, 600. City name: 22px, 600.
  Feed items: 14px body, 12px timestamp/label. KPI values: 20px, 600.
  KPI labels: 11px, uppercase, letter-spacing 0.08em, `#374151`.
- Positive: `#22C55E` with ▲. Negative: `#EF4444` with ▼. Neutral:
  `#E5E7EB`. Do not use any other green/red for economic direction.
- Animations: panel slide-in 300ms `ease-out`. Feed item fade-in
  400ms `ease-out`, starting opacity 0 and translateY 6px. Pin drop:
  staggered 80ms per pin, 350ms `ease-out` from 20px above its final
  position, plus a ripple ring expanding over 600ms. Globe fade-out
  and city fade-in: 2000ms `easeInOutCubic`, overlapping, never
  sequential with a blank frame between them.
- Layout, desktop: SIDE-BY-SIDE, NO OVERLAP. The app is a flex row: globe/city area takes the remaining width (about 62%), sidebar is a separate column on the right, 400–420px wide, full height, with a clear gap between them. The sidebar must NEVER cover, overlay, or sit on top of the globe or city. The globe/city is centred within its own area, not within the full viewport.
  Country label is fixed top-right, 24px from top and 24px from right,
  above the panel's top edge when the panel is closed, and it must
  remain visible when the panel is open. KPI strip is fixed top-centre
  in city view only, not in globe view. Timeline is fixed bottom-centre
  in city view only. On narrow screens (<900px), the right panel
  becomes a bottom sheet covering the lower 55% of the screen; do not
  ship a broken desktop-only layout and call it responsive.

## 4. State machine — implement exactly these states

The app has exactly these states. No extra top-level screens.

| State | What is visible | How you enter it | How you leave it |
|---|---|---|---|
| `GLOBE` | Globe centred, starfield, country label top-right (empty until hover) | App start, or Back from `COUNTRY` | Click a country → `COUNTRY` |
| `COUNTRY` | Globe zoomed to country, country yellow, pins visible, country label shows country name | Click a country | Click empty space or Back → `GLOBE`. Click a pin → `PIN_SELECTED` |
| `PIN_SELECTED` | Globe still centred, active pin highlighted, right prompt panel open | Click a pin | Close panel or click another pin (stays in state, swaps city). Back → `COUNTRY` |
| `TRANSITION` | Globe zooming into pin and fading out, city fading in, prompt panel persists | Submit a confirmed prompt | Automatically after 2000ms → `CITY` |
| `CITY` | City canvas in its own area, side panel is now the sim console with prompt pinned on top, top control bar (Create World, Play/Pause, Speed, Reset, current tick, City/Network toggle), metrics strip top-centre, timeline bottom-centre | End of `TRANSITION` | Back → `GLOBE` (discards current run, asks nothing; a run is cheap to restart). Follow-up prompt → new branch, stays in `CITY`. City/Network toggle stays in `CITY` (see Section 15B) |

Rules:

- The globe must stay centred within its own left area in `GLOBE`, `COUNTRY`, and `PIN_SELECTED`. When the panel opens, the globe area shrinks to the remaining width and the globe recentres in that area — it is never covered by the panel.
- The prompt panel must persist across `TRANSITION` into `CITY`
  without remounting. Its header changes from "Ask a question" to
  "Running scenario" and the original prompt stays pinned at the top.
- Back navigation must always work, including during `TRANSITION`
  (cancel the transition, restore the globe at the pin's country view).
- Network view is NOT a new top-level state. It is a view mode inside `CITY`. Toggling City ↔ Network must never lose the current tick, branch, selection, or simulation state (Section 15B).
- The timeline must never be visible in globe states. The country
  label must never be visible in city view except as part of the
  panel header ("San Francisco, USA").

## 5. Globe — implementation checklist

Implement in `apps/web/src/globe/`. Do not skip a step.

1. Create a full-viewport Three.js scene with a black space background,
   a starfield of at least 2,000 points, and a directional light plus
   ambient light so country polygons read as an object, not a flat
   disc.
1A. Render Earth first, before any country overlay. Base sphere
    with the bundled Earth day texture from Section 3, plus a
    cloud sphere at 1.01x radius with a transparent cloud texture
    rotating slowly on its own, plus atmosphere glow around the
    limb. This is the globe the user sees. Country polygons are
    an interaction overlay on top of it, not the globe itself.
1B. Country polygons are a transparent hit/outline layer on top
    of the Earth texture: unselected fill transparent, outline
    white at 25% opacity; hover outline white at 90%; selected
    fill translucent yellow (Section 3) with a solid yellow
    outline. The Earth texture must remain visible under every
    overlay state, including the selected state.
2. Add an atmosphere glow: a slightly larger transparent sphere with
   a fresnel-style shader, or a radial-gradient sprite behind the
   globe. It must be visible in a screenshot. If it is not visible,
   increase its opacity until it is.
3. Load country polygons from a bundled static world GeoJSON file.
   Do not fetch it from a third-party URL at runtime. Convert
   TopoJSON to GeoJSON at build or commit time and commit the result
   to `apps/web/src/data/countries.geojson`.
4. Auto-rotate slowly (about 0.05 radians per second) until the user
   first drags. Drag rotates with inertia (damping factor 0.92 per
   frame). Scroll zooms, clamped so the camera altitude stays between
   1.2 and 3.5 globe radii.
5. Hover: use the globe library's polygon hover callback. On hover,
   set the hovered country in state, brighten its outline per
   Section 3, set the cursor to pointer, and set the top-right label
   to the country's name. On hover end, clear the label unless a
   country is selected, in which case the label stays on the selected
   country.
6. Click a country: set state to `COUNTRY`, set that polygon to
   yellow, dim all others to 35%, animate the camera to that
   country's centroid with a 1200ms `easeInOutCubic` move, then
   render pins (Section 6). If the user clicks a different country
   while already in `COUNTRY`, swap the selection, recolour, and
   re-animate; do not require going back to `GLOBE` first.
7. Clean up on unmount: dispose geometries, materials, renderer,
   and remove all event listeners. A globe that leaks on every
   transition will crash the demo after two or three runs.
8. Acceptance: with no interaction, a screenshot looks like Earth
   from space — blue oceans, recognisable continents, white clouds
   and ice caps — not a flat map and not a dark abstract sphere. Hovering United States shows "United States" top-right.
   Clicking United States turns it yellow, zooms in, and shows pins.

## 6. Pins — implementation checklist

Implement in `apps/web/src/globe/CityPins.tsx` and
`apps/web/src/data/cities.json`.

1. Pins exist only for the selected country. Never render pins for
   all countries at once.
2. Data per pin, all required: `city`, `country`, `countryCode`,
   `lat`, `lng`, `population`, `geography` (one of `harbour`,
   `river`, `inland`, `dense`), `seed` (see Section 11).
3. On entering `COUNTRY`, pins drop in staggered by 80ms each, in
   descending population order, largest first. Each pin has a
   pulsing ring per Section 3.
4. Hover a pin: grow it by 20%, show a mini card next to the pin with
   city name, population, median rent (stylized units), mortgage
   character (for example "mostly variable-rate"), and top two
   sectors. The card must not cover the pin itself.
5. Click the San Francisco pin: set it as active (solid yellow
   core), fade other pins to 50% opacity, set state to
   `PIN_SELECTED`, and open the right prompt panel with San
   Francisco's profile loaded.
6. Disabled US pins (Los Angeles, New York, Chicago, Seattle):
   greyed to 50% opacity, no pulse ring, cursor `not-allowed`,
   and on click show only "Coming soon in this demo — only San
   Francisco is playable". They must not open the prompt panel
   and must not change state away from `COUNTRY`.
7. If the selected country is not the United States, show zero
   pins and the not-available notice in Section 14. Never invent
   cities to fill a quota, and never show a pin with no city
   config behind it.
8. Acceptance: United States shows San Francisco, Los Angeles,
   New York, Chicago, and Seattle pins. Hovering San Francisco
   shows its mini card. Clicking San Francisco opens the prompt
   panel and keeps the globe centred. Clicking Los Angeles or
   New York shows the coming-soon pill and does nothing else.

## 7. Prompt panel and prompt parsing — exact behaviour

Implement in `apps/web/src/ui/PromptPanel.tsx` and
`apps/web/src/sim/scenarios.ts`.

Panel layout, top to bottom, in `PIN_SELECTED`:

1. City header: city name, country name, population, and the
   stylized-simulation label.
2. Prompt textarea, placeholder:
   "Ask how a scenario would affect this city…"
   Example chips underneath, clickable, filling the textarea:
   - "How will heightened interest rates affect demand and supply
     in San Francisco?"
   - "What happens if rents rise 20% for a year?"
   - "What happens if banks tighten credit for small firms?"
3. On submit, parse the prompt into a `Scenario` (schema below),
   then show a parsed-scenario card for confirmation. Do not run
   the simulation before confirmation. The card shows, with sliders
   to edit: shock type, direction, magnitude, duration in months,
   and target sector if named, otherwise "All sectors".
4. Confirm button label: "Run this scenario". Cancel returns to
   editing the prompt.

`Scenario` schema — use exactly these field names:

```ts
type ShockType =
  | "interest_rate"
  | "rent"
  | "wages"
  | "credit"
  | "tax"
  | "prices";

type Scenario = {
  shockType: ShockType;
  direction: "up" | "down";
  magnitude: number;      // percentage points for interest_rate,
                          // percent for all other shock types
  durationMonths: number; // default 24, clamp 6–60
  targetSector: string | null; // null = all sectors
  promptText: string;     // the user's original prompt, verbatim
};
```

Parsing rules, in order:

1. Lowercase the prompt. Extract the first number with an optional
   `%`, `percent`, `percentage points`, or `pp` after it, using a
   regex. If no number is found, use the defaults in step 4.
2. Map keywords to shock type, first match wins, in this order:
   `interest`, `rate`, `mortgage` → `interest_rate`;
   `rent`, `landlord` → `rent`;
   `wage`, `salary`, `pay` → `wages`;
   `credit`, `loan`, `lending`, `bank` → `credit`;
   `tax` → `tax`;
   `price`, `inflation`, `cost of living` → `prices`.
   If no keyword matches, default to `interest_rate` and show that
   assumption in the parsed card.
3. Direction: `rise`, `rising`, `higher`, `heightened`, `increase`,
   `up`, `surge` → `up`. `fall`, `falling`, `lower`, `decrease`,
   `cut`, `down` → `down`. If neither is found, default to `up`.
4. Defaults when a value is missing: interest_rate magnitude 2
   (percentage points), all other magnitudes 20 (percent),
   duration 24 months, target sector null.
5. Target sector: match sector names in the prompt (`hospitality`,
   `retail`, `construction`, `finance`, `tech`, `services`, plus
   `cafes`, `restaurants` → `hospitality`). If none matches, null.
6. The parsed card must display the user's original prompt verbatim
   above the sliders, so the user can see exactly what was parsed
   from what they wrote.

Required parse test cases — all must pass as unit tests:

- "How will heightened interest rates affect demand and supply in
  San Francisco?" → `{ shockType: "interest_rate", direction: "up",
  magnitude: 2, durationMonths: 24, targetSector: null }`
- "What happens if rents rise 20% for a year?" →
  `{ shockType: "rent", direction: "up", magnitude: 20,
  durationMonths: 12, targetSector: null }`
- "What if interest rates fall 1.5 percentage points?" →
  `{ shockType: "interest_rate", direction: "down",
  magnitude: 1.5, durationMonths: 24, targetSector: null }`

If the LLM parser in Section 17 is enabled, it must return the same
`Scenario` shape, and the regex parser above is the fallback when
it fails, times out, or returns an invalid shape. Never let a failed
LLM call block the prompt panel.

## 8. Transition — exact behaviour

Implement in `apps/web/src/globe/GlobeCamera.ts` and the App state
machine. This transition is a judged moment. Do not rush it and do
not make it a hard cut.

1. On "Run this scenario", set state to `TRANSITION`. The selected
   pin pulses once, larger than its hover state, for 400ms.
2. Animate the camera from the country view to the pin's lat/lng
   over 1200ms `easeInOutCubic`, ending at the closest zoom the
   globe allows.
3. Over the full 2000ms transition, animate the globe container
   from opacity 1 to 0, scale 1 to 1.15, and blur 0 to 8px, while
   the city container animates from opacity 0 to 1 and scale 0.96
   to 1. The two containers must overlap for the whole transition.
   There must be no frame where both are invisible.
4. At 2000ms, unmount the globe, set state to `CITY`, and start the
   simulation at tick 0. The city must already be generated and
   drawn at opacity 0 underneath, so it does not pop in after the
   globe disappears.
5. If the user presses Back during `TRANSITION`, cancel all
   animations, restore the globe at the country view, restore pins,
   and return to `PIN_SELECTED`. Do not leave the app in a
   half-faded state.
6. Acceptance: run the San Francisco demo three times in a row. The
   transition must look identical and smooth every time, with no
   blank frame, no globe leak, and no city pop-in.

## 9. City generation — seeded, deterministic, step by step

Implement in `apps/web/src/city/cityGenerator.ts`. Follow these
steps in order. Do not reorder them, because later steps depend on
earlier random draws, and reordering changes the layout for a given
seed.

Inputs: `cityConfig` (Section 14) plus `layoutSeed: number`.
Output: `CityLayout` with districts, roads, blocks, buildings,
parks, and water, all in grid coordinates.

1. Hash the seed: `layoutSeed = hash(countryCode + "|" + cityName)`
   using FNV-1a or an equivalent stable string hash. Store the
   resulting number in the layout. Do not use `Math.random()` anywhere
   in this file. Every random draw must come from the seeded
   generator in Section 10 of the sim notes: `mulberry32`.
2. Place districts: start from a jittered grid of 5–7 district
   centres. Each district gets a type from the city config:
   `cbd`, `residential`, `retail`, `industrial`, `harbour` (only
   for harbour geography), `suburban`. Jitter each centre by up to
   25% of the grid spacing, using the seeded generator.
3. Draw main roads: connect district centres in a minimum spanning
   tree, then add 1–2 ring or cross roads through the centre.
   Roads are polylines on the grid, not straight lines: insert a
   midpoint jittered by up to 15% of the segment length.
4. Subdivide each district into blocks: grid blocks of 3–6 units,
   with block size varying by district density (CBD smallest and
   densest, suburban largest and sparsest).
5. Place buildings per block: for each block, draw 1–4 buildings.
   Height = base height for the district type, multiplied by a
   seeded factor 0.6–1.6, multiplied by the city density factor.
   CBD buildings are tallest, suburban shortest. Footprint fills
   50–80% of the block cell.
6. Place water from the geography archetype, before buildings are
   finalised, and remove any building that falls in water:
   - `harbour`: a large water ellipse on the eastern edge, plus a
     harbour inlet reaching toward the CBD.
   - `river`: a river polyline from north to south, width 3–5
     units, with a seeded meander.
   - `inland`: no large water, only 1–2 small lakes.
   - `dense`: no large water, a small river or canal if the seed
     draws one (50% chance).
7. Place parks: 1 park per 3 districts, seeded position, size
   2–4 units, never overlapping a road or water.
8. Assign a palette: pick from the city's palette list in its
   config, or, for fallback cities, from a palette derived from
   the geography archetype. Roof colours must vary per building
   within the palette, not be a single colour for the whole city.
9. Assign district names: use the config's real names for hero and
   curated cities. For fallback cities, use generic names in this
   order: Downtown, Riverside, Old Town, Northside, West End,
   Industrial Zone, Suburbs. Never leave a district unnamed.
10. Return the layout plus a `layoutHash` (hash of the serialized
    layout). The test in Section 20 must prove that the same seed
    produces the same `layoutHash` on every run.

## 9A. San Francisco as a miniature model — landmarks first, rest miniature

The San Francisco city is a miniature model / diorama, not a
full-scale, photorealistic, or end-to-end detailed city. This is
a deliberate design choice, and it is what makes the demo
feasible and readable: stylisation is the look, not a missing
feature.

Aesthetic, exact:

- Tabletop miniature / diorama feel: an angled, slightly
  tilted view of a small physical model city, with warm
  sunlight, soft shadows, saturated colours, and toy-like
  proportions. The city sits as one coherent model, not as a
  satellite photo and not as a street-level 3D world.
- Tilt-shift treatment: centre of the view sharp, edges
  softly blurred and vignetted (a radial-gradient overlay,
  darkening and slightly blurring the outer 15% of the view).
  This single effect sells "miniature" more than any amount
  of extra building detail, and it must be present in city view.
- Landmarks are exaggerated 1.5–2x relative to true scale,
  as physical miniature models do, so they read instantly at
  city zoom. Do not scale them realistically and lose them.

Iconic landmarks — hand-built, not procedural. Draw each as
a fixed vector shape on the static layer, with a label on
hover and a click that opens the inspector for its district.
Build these six, in these relative positions, and no others
for this demo:

1. Golden Gate Bridge — north-west edge, spanning the water
   inlet. International Orange towers, suspension cables as
   arcs between towers, deck with tiny cars crossing. This is
   the hero landmark; it must be recognisable in a screenshot
   with no label.
2. Transamerica Pyramid — Financial District cluster. White
   tapering pyramid with a pointed top, distinct from every
   other downtown block.
3. Salesforce Tower — Financial District cluster, tallest
   downtown shape, curved glass tower with a rounded top.
4. Ferry Building — east waterfront. Low arched building with
   a clock tower, at the end of a main downtown corridor.
5. Coit Tower — on a hill in the north-east residential area.
   Slender cylindrical tower, visible above surrounding
   low-rise houses.
6. Alcatraz — small island in the bay, east of the Golden
   Gate. Low prison block plus a small lighthouse dot. Keep
   it small and simple; it is a recognisable silhouette, not
   a detailed island.

Everything else is miniature kit, not end-to-end detail:

- Downtown blocks: simple extruded prisms, varied heights.
- Residential areas: small pitched-roof houses and pastel
  Victorian row houses, repeated from a small kit of 4–6
  house shapes and colours, not individually designed houses.
- Trees: small green blobs on a trunk dot. Parks: flat green
  shapes with a few tree blobs.
- Roads: flat miniature streets with tiny toy cars. People:
  tiny dots/figures on footpaths.
- District labels and landmark labels only. No street names
  for every street, no interiors, no per-building window
  detail beyond lit dots at night, no exact real street grid,
  no individual 3D building models.

Explicitly NOT in scope for the city, even though it would
be "more realistic": street-level views, building interiors,
every house unique, exact real-world geography, or a
photorealistic San Francisco. The miniature model is the
realism: recognisable landmarks plus a coherent, lively
miniature city around them.

Transition into the miniature: when the globe fades out,
the diorama fades in with a slight scale-up (0.96 → 1.0)
and the tilt-shift vignette fades in with it, so the user
feels they have zoomed from a planet to a tabletop model,
not just switched screens.

## 10. City rendering and liveliness — exact behaviour

Implement in `apps/web/src/city/CityCanvas.tsx`,
`cityRenderer.ts`, `movers.ts`, and `activity.ts`.

Projection, use exactly this:

```
screenX = originX + (x - y) * tileWidth / 2
screenY = originY + (x + y) * tileHeight / 2 - buildingHeight
tileWidth = 64, tileHeight = 32
```

Miniature treatment, mandatory in city view: render the
city as the diorama in Section 9A, then apply a tilt-shift
overlay — a radial vignette darkening and slightly blurring
the outer 15% of the view, centre sharp. Landmarks from
Section 9A are drawn on the static layer as fixed vector
shapes, exaggerated 1.5–2x, and must remain recognisable
without labels. The rest of the city uses the miniature kit
in Section 9A, not detailed individual buildings.

Rendering layers, in draw order, every frame:

1. Static layer, drawn once to an offscreen canvas on layout
   change only: water, parks, roads, footpaths, building prisms
   (top face, left face 20% darker, right face 35% darker), and
   shadows (offset 4px right, 6px down, black at 25% opacity).
   Never redraw this layer per frame.
2. Dynamic layer, redrawn every frame: cars, pedestrians, shop
   queues, window lights, and transaction particles.
3. Overlay layer: district labels at low zoom, building highlight
   on hover, and the inspector highlight ring on selection.

Movers, exact rules:

- Render a sampled 300–500 visual agents, pooled and reused. Do
  not create or destroy objects per frame. Do not render one
  visual agent per simulated household.
- Each visual agent has: home district, current destination type
  (`work`, `shop`, `leisure`, `home`), a path along the road or
  footpath graph, a progress value 0–1 along that path, and a
  speed in grid units per second.
- Cars: rectangles 10px long, 5px wide, aligned to their path
  direction, drawn on roads, with two headlight dots at night.
  Cars travel between districts. People: circles 3px radius, drawn
  on footpaths, travelling within a district to a shop or
  workplace. Do not draw people on roads and do not draw cars on
  footpaths.
- No collision detection, no traffic AI. Movers follow their path
  and lane offset. If two movers overlap, that is acceptable.
  Overlapping movers must never block the frame loop.
- Destination choice is weighted by the simulation, not random:
  a visual agent heading to `shop` must correspond to a district
  whose retail demand is above zero, and a shop that is closed
  in the simulation must attract zero visual agents.

Visual day cycle, independent of the simulation tick:

- The visual clock loops every 60 seconds: 0–20s morning commute
  (most movers heading to `work`, CBD-bound traffic heaviest),
  20–40s midday (most movers heading to `shop`, retail districts
  busiest), 40–55s evening (most movers heading to `leisure`,
  then `home`), 55–60s night (few movers, window lights on,
  headlights on).
- The simulation tick is one month. The day cycle is ambient
  animation. The simulation controls the amplitude of each period
  through Section 12, never the clock itself.

Click behaviour: clicking a building selects that firm if the
building is a firm, or the dominant household group for that
district if it is residential. Clicking a mover selects its
archetype group, not a single simulated household, and the
inspector must say so ("Representative mortgaged household,
Western Suburbs") so the UI never pretends a dot is a real person.

## 11. How simulation changes what the city looks like

Implement in `apps/web/src/city/activity.ts`. This mapping is
mandatory. A simulation change that does not change the city
visually has not been implemented correctly.

For each district and each tick, compute:

```
employmentRate, disposableIncomeIndex (100 = tick 0 baseline),
retailDemandIndex, firmOpenRate, defaultRate
```

Then apply, lerping between ticks over 800ms so the city never
jumps:

- Retail demand down 10% or more vs. baseline: shop trip
  probability down proportionally, shop queues shorten, 1 in 5
  shopfronts in that district dim.
- Retail demand down 25% or more: some shopfronts show closed
  shutters, and closed firms in the simulation show as dark
  buildings with a "Closed" label on hover.
- Employment down 10% or more: morning commute mover count down
  proportionally, more movers remain in residential districts
  during the day period.
- Firm open rate below 85%: at least one building per affected
  district is dark at night, with no window lights, even during
  the evening period.
- Default rate above 5%: bank buildings in that district pulse
  red once per 3 seconds, and the side feed must contain at
  least one bank-related micro event for that tick.
- Boom conditions (retail demand up 15% and employment up 5%):
  car speed drops by 20% to simulate congestion, shop queues
  lengthen by 30%, and shopfront brightness increases.

Acceptance: run San Francisco baseline for 6 ticks, then apply a +2 point
rate hike. At the same visual time of day, the post-shock city
must have visibly thinner traffic, shorter shop queues, and at
least one dimmed or closed shopfront, before any chart is read.
If a reviewer cannot see the difference, the activity mapping is
not wired up, regardless of what the charts say.

## 12. Simulation — entities, tick order, and formulas

Implement in `apps/web/src/sim/`. All tunable numbers live in
one file, `apps/web/src/sim/constants.ts`. Do not scatter magic
numbers through the tick function.

Entities, TypeScript shapes — use exactly these field names:

```ts
type Household = {
  id: string; district: string; archetype:
    | "mortgaged" | "renter" | "outright" | "saver";
  income: number; savings: number;
  mortgageBalance: number; mortgageRate: number;
  mortgageVariable: boolean; rent: number; debt: number;
  employerId: string | null; bankId: string;
  bufferTarget: number; riskAversion: number; // 0–1
};

type Firm = {
  id: string; district: string; sector: string;
  cash: number; inventory: number; staff: number;
  price: number; revenueLastTick: number; loanBalance: number;
  bankId: string; open: boolean;
};

type Bank = {
  id: string; district: string; deposits: number;
  loansOut: number; capital: number; baseRate: number;
};

type LedgerEntry = {
  id: string; tick: number; fromId: string; toId: string;
  amount: number; kind:
    | "wage" | "rent" | "mortgage" | "purchase" | "loan"
    | "interest" | "tax" | "transfer";
  eventId: string;
};
```

Scale for the core demo: 2,000 households, 240 firms, 4 banks,
1 government. Do not simulate fewer than 1,000 households and
call the result emergent, and do not simulate more than 5,000 in
the browser without moving the tick loop to a Web Worker and
proving it in a performance test.

Tick order, every tick, in this exact order:

1. Income and benefits land. Firms pay wages to employed
   households. Government pays transfers to eligible households.
   Each payment is a ledger entry.
2. Interest, mortgage, and rent are paid. Mortgage payment uses
   the standard amortizing formula:
   `payment = balance * r / (1 - (1 + r) ^ -n)`, where `r` is
   the monthly rate and `n` is remaining months. Variable-rate
   mortgages use the current base rate plus bank margin.
   Fixed-rate mortgages use their locked rate.
3. Households spend. Essentials first, then discretionary.
4. Firms collect revenue, adjust price, inventory, and staffing.
5. Banks collect interest, assess defaults, and adjust credit.
6. Government collects tax and pays transfers.
7. Ledger is validated: sum of debits must equal sum of credits
   for the tick, every entry must have a valid counterparty, and
   every entry must have an idempotency key (`eventId + fromId +
   toId + kind`). If validation fails, the tick must throw in
   development and tests, never silently continue.

Household spending formula, implement exactly this shape, with
coefficients from `constants.ts`:

```
essentials = baseEssentials * (1 + priceLevelChange)
fixedCosts = mortgagePayment + rent + debtService + tax
disposable = income - fixedCosts - essentials
bufferMonths = savings / max(essentials, 1)
confidence = 1.0
if (bufferMonths < 1) confidence = 0.5
if (bufferMonths < 0.5) confidence = 0.2
discretionary = max(0, disposable * propensity * confidence)
```

`propensity` is per archetype: mortgaged 0.55, renter 0.60,
outright 0.70, saver 0.35. `riskAversion` scales `bufferTarget`
and therefore how quickly confidence falls. If `disposable` is
negative, discretionary is 0, savings are drawn down, and if
savings reach 0, the household records a missed payment, which
increments its bank's default count for that tick.

Firm update formula, implement exactly this shape:

```
demandForecast = 0.7 * revenueLastTick + 0.3 * revenuePrevTick
if (inventory > targetInventory * 1.2) price *= 0.98
if (inventory < targetInventory * 0.8) price *= 1.02
price = clamp(price, minPrice, maxPrice)
wageBill = staff * avgWage
if (revenueLastTick < wageBill * 1.1 && staff > 1) staff -= 1
if (revenueLastTick > wageBill * 1.5 && staff < maxStaff) staff += 1
if (cash < 0 && loanBalance > cash * 2) open = false
```

A closed firm stops hiring, stops attracting shop trips, and
its building renders dark per Section 11.

Bank update formula, implement exactly this shape:

```
interestCollected = sum(loanBalance * monthlyRate) over loans
defaultsThisTick = count of missed payments for this bank
if (defaultsThisTick / totalLoans > 0.05) creditTightening = 1.5
else if (defaultsThisTick / totalLoans > 0.02) creditTightening = 1.2
else creditTightening = 1.0
newLoanApproved = debtToIncome < 0.40 / creditTightening
  && capitalRatio > 0.10
```

Government: tax rate from city config, transfers to households
with income below the config's transfer threshold. Government
spending is a ledger entry like any other.

San Francisco hero starting values, stylized, not real-world data: base rate 4.0, bank margin 1.5, variable mortgage share 0.35 (US fixed-rate majority, stylized), median rent index 100, tech sector weight high, transfer threshold at the 25th income percentile. No other city is built in this demo; do not invent other city configs.

## 13. Ledger, snapshots, and branching

- Every settled transaction creates exactly one `LedgerEntry`
  per side in the internal representation, or one entry with
  explicit `fromId` and `toId` that the validator can check as
  balanced. Pick one representation and use it consistently.
  Do not mix representations.
- Snapshots: a snapshot is `structuredClone(world)` at a tick
  boundary, never mid-tick. Store snapshots per tick per branch
  so the timeline can scrub. A snapshot must include tick,
  households, firms, banks, government, ledger up to that tick,
  and the scenario that produced it.
- Branching: on "Run this scenario", snapshot the world at the
  shock tick, then run three branches from that identical
  snapshot with the same simulation seed: baseline (no shock),
  shock (the confirmed scenario), and shock-plus-policy if a
  policy has been proposed and accepted. Branches share layout
  seed and simulation seed. Only the scenario differs.
- Branch comparison view: same KPI charts, same tick axis, one
  line per branch, with the shock tick marked by a vertical line.
  The comparison must never compare branches with different
  starting snapshots. If the snapshots differ, show an error
  instead of a chart.
- Reproducibility test: run the same city, seed, and scenario
  twice. The final tick's KPI values and ledger hash must match
  exactly. If they do not, the tick function has a hidden source
  of randomness, and that is a bug, not a feature.

## 13A. Fork Reality — the centerpiece, not an extra chart

A prominent **“Fork Reality”** button must be visible in `CITY` (top control bar and sim console, not buried in a menu), enabled once a crisis has been triggered. Clicking it does not start a new world and does not change the current run.

- **Fork point:** the crisis snapshot — the exact world state at the tick the crisis was triggered (Section 13). All three futures below run from that identical snapshot with the same simulation seed. Only the intervention differs. If the starting snapshots differ, show an error instead of a comparison, per Section 13.
- **The three futures, exactly these, in this order:**
  1. **No intervention** — let the crisis unfold, no public intervention, intervention cost 0.
  2. **Emergency bank lending** — support bank liquidity.
  3. **Direct household support** — support household spending.
- **Charts, visually comparable:** for each branch, the same four charts with the same axes, same tick axis, same colours per branch across all charts: Employment, Business Defaults, Bank Stress, Public Intervention Cost. Same chart size per branch, same scale, one line per branch per chart, crisis tick marked by a vertical line. A synchronized timeline scrubs all branches together — scrubbing one moves all three to the same tick.
- **AI central bank recommendation:** one recommendation card above or beside the charts, naming exactly one recommended branch, with a short explanation of the tradeoff that references actual final-tick values from the charts (for example, which branch ends with lowest bank stress and at what intervention cost, and what it gives up). The recommendation must be derived from branch data, never a generic paragraph, and it must state the tradeoff plainly (for example, bank lending stabilises banks but leaves household spending squeezed; household support protects spending but bank stress persists longer — only if the data show that).
- **Acceptance:** three branches share the crisis snapshot; charts are synchronized; the recommendation names one branch and cites final-tick numbers; the view works from fixtures (`sfFork.json`, Section 19A) with no backend.

The earlier prompt-scenario branches in Section 13 (baseline / shock / shock-plus-policy) are the scenario branches for a prompt. Fork Reality is the post-crisis intervention comparison and uses the three branches above. Do not merge the two sets into one list and do not rename Fork Reality branches to baseline/shock/policy.

## 14. Demo data — San Francisco only, USA pins only

Files:

- `apps/web/src/data/countries.json`: one entry per country for
  globe highlighting only: `code`, `name`, `currencySymbol`.
  Highlighting must work for every country. No country except
  the United States gets pins in this demo.
- `apps/web/src/data/cities.json`: United States only.
  San Francisco is playable. Los Angeles, New York, Chicago,
  and Seattle are visible but disabled (see Section 6).
  Each entry: `city`, `countryCode`, `lat`, `lng`,
  `population`, `geography`, `playable` (true only for
  San Francisco).
- `apps/web/src/data/cityTemplates.ts`: one config only,
  San Francisco. Districts, in order of prominence:
  Financial District, SoMa, Mission District, Chinatown,
  Hayes Valley, Marina, Richmond, Sunset, Castro.
  Geography: bay on the east, Pacific on the west, hills
  through the centre. No other city config is built for
  this demo.

Behaviour, exact:

- Clicking any country highlights it yellow and zooms to it.
- Clicking the United States shows its pins.
- Clicking any other country shows zero pins and a small
  notice: "Demo city not available yet — try United States
  → San Francisco". It must never crash, show a blank panel,
  or open a city.
- Clicking a disabled US pin shows "Coming soon in this demo
  — only San Francisco is playable" and does nothing else.
  It does not open the prompt panel and does not change state
  away from `COUNTRY`.
- Do not build any city other than San Francisco for this demo.
  Do not invent city configs to fill a quota.

Acceptance: globe highlighting works for any country; only
the USA shows pins; only San Francisco opens the prompt and
city; every other US pin shows the coming-soon pill and does
nothing else; every non-US country shows the not-available
notice and zero pins.

## 15. Side feed — macro and micro, exact behaviour

Implement in `apps/web/src/ui/SideFeed.tsx` and
`apps/web/src/ui/Inspector.tsx`.

Feed item schema — use exactly these field names:

```ts
type FeedItem = {
  id: string; tick: number; level: "macro" | "micro";
  text: string; delta: number; // signed percent change, 0 if not applicable
  direction: "up" | "down" | "flat";
  actorId: string | null; district: string | null;
  ledgerEventIds: string[];
};
```

Rules:

- Macro items are computed once per tick, at most 5 per tick,
  in this priority order: unemployment, discretionary spending,
  median rent, business failures, loan defaults. Each shows the
  current value and the change vs. the previous tick.
- Micro items are created only for events above a threshold:
  a household cutting discretionary spending by more than 50%
  in one tick, a firm cutting staff, a firm closing, a bank
  tightening credit, a household missing a payment. At most 8
  micro items per tick, highest magnitude first. Do not flood
  the feed with every household purchase.
- Each new item fades in over 400ms per Section 3, newest on
  top, with timestamp "Month N". Items older than 30 entries
  are removed from the DOM, not just hidden.
- Colour rule: `direction === "up"` and the change is good for
  the economy (for example spending up, employment up) → green
  ▲. `direction === "down"` and the change is bad (spending
  down, employment down, defaults up, failures up) → red ▼.
  Note the subtlety: defaults up is direction "up" but colour
  red, because it is bad. Implement a `isGood` flag per metric
  and colour by `isGood`, not by raw direction. Neutral items
  are grey/white with no arrow.
- Clicking a feed item opens the inspector for its `actorId`
  if present, otherwise for its district. The inspector is a right-side drawer and shows:
  name/type, district, cash, assets, debt, and obligations (all as separate fields, never merged into one balance number), relationships as appropriate — employer, bank, borrowers, or suppliers — each clickable to open that institution's inspector, recent transactions (last 5 ledger entries for
  that actor), and a one-sentence reason for its last decision
  derived from its state (for example "Mortgage payment rose,
  buffer fell below 1 month, discretionary spending cut by 60%").
  The reason must be generated from state values, never
  hand-written per actor. For AI agents, the inspector also shows: observations, proposed action, explanation, validation result, and settlement status (Section 15C for the payment workflow). This is where a judge verifies that actions have real financial consequences — an approved action must change a balance, an obligation, or a settlement status, and the inspector must show that change.
- The feed header must show the pinned prompt at the top in
  `CITY` state, verbatim, with a "Follow-up question" input
  underneath it. A follow-up creates a new branch from the
  current tick snapshot, it does not restart the city.

KPI strip — the compact metrics strip for the command center — city view only, top-centre, exactly these five
metrics, in this order: Employment, Household Cash, Business Defaults, Bank Stress, Public Intervention Cost. Each shows
current value, change vs. previous tick with arrow and colour
per the rule above, and the tick number. No other KPIs in the
strip. The earlier metrics (Disposable income index, Median rent index, Loan defaults, Unemployment) are not in the strip; they belong in the feed, the inspector, or the Fork Reality comparison charts, not in the strip.

Top control bar, city view only, across the top of the city area: **Create World, Play/Pause, Speed, Reset**, and the current simulation tick, plus the City/Network toggle (Section 15B) and the Fork Reality button (Section 13A). Create World starts a new healthy world at tick 0. Reset returns the current run to its starting state (tick 0, or the crisis snapshot if a crisis run is being replayed — label which one it does). Play/Pause and Speed in the top bar and in the timeline are the same state, not two independent controls; changing one updates the other.

Timeline, city view only, bottom-centre: play/pause button,
speed selector (1x, 2x, 4x), tick scrubber from tick 0 to current
max tick, and a branch selector (Baseline / Shock /
Shock + Policy, plus Fork Reality branches No intervention / Emergency bank lending / Direct household support when a Fork Reality comparison exists) when more than one branch exists. Scrubbing must
restore the exact snapshot for that tick, including city activity
values, not just the charts.

## 15A. Crisis controls — Trigger Crisis panel

A visible **“Trigger Crisis”** panel in the `CITY` sim console, not hidden in a menu. It has:

- **Bank selector:** Bank 1, Bank 2, Bank 3, Bank 4 (the 4 banks in Section 12). Default bank for the demo: **Bank 2**.
- **Asset category selector:** one asset category per the fixture/backend (for example commercial loans). The demo default is one category only — do not apply the loss across all assets.
- **Loss input:** default **40% loss in that one asset category**. The user may change the percentage, but the demo script uses 40%.

On trigger, at the next tick boundary, that bank suffers the asset loss. The city must show it immediately per Section 11: the bank building pulses red, lending contracts, and connected firms dim. The feed must show the cascading chain as linked, clickable micro items, in this demo shape:

> Bank 2 suffers an asset loss → lending contracts → Café 14 cannot refinance → payroll is missed.

Each item in the chain is clickable to its institution (Bank 2, Café 14, and the affected households/employees where the data provide them), and Café 14's inspector must explain why it is struggling: loan balance, bank credit tightening, cash below payroll, and the missed payroll ledger entry. A crisis is one demo crisis per run; Reset (Section 15) restores the healthy world and the crisis can be triggered again.

## 15B. Financial network view — City / Network toggle

A toggle in the top control bar, **City | Network**, inside `CITY` state. Both views use the same selected institution and the same simulation state (same tick, same branch, same inspector).

- **Nodes:** banks and businesses only (the 4 banks and firms with loans, obligations, or payments). Do not draw 2,000 households as nodes; households appear only as grouped residential districts in City view, and as inspector relationships in Network view.
- **Edges:** loans, obligations, and payments between nodes. Edge thickness may encode exposure size, but the exact exposure amount is shown only on selection, never guessed from thickness alone.
- **Selection:** selecting a node highlights its counterparties (connected nodes and edges bright, all others dimmed to 35%). Selecting a connection shows: from, to, kind (loan / obligation / payment), exposure amount, and status. Deselecting restores the full view.
- **Defaults propagate visibly:** a defaulting node pulses red, its edges turn red, and connected nodes show bank/firm stress colour per Section 11. The feed item for that default links to the same node.
- **Acceptance:** toggle City → Network → City without losing tick, branch, or selection; node selection highlights exactly its counterparties; edge selection shows an exposure amount; a default in City view is the same default, same colour, in Network view.

## 15C. Agentic payment demo — inside the business inspector

Inside the business inspector (Section 15), for a firm with an inventory need — the demo firm is **Café 14** — show one compact step-by-step activity card for this workflow, in this order:

1. **Café needs inventory** — need stated, amount and item from the fixture/backend.
2. **Two supplier offers** — both offers shown with terms (price, delivery, payment terms). No more, no fewer, for the demo.
3. **Agent selects terms** — the selected offer is highlighted, the other is marked rejected, with the selection reason from the agent's observations.
4. **Backend validates** — validation result shown (pass or fail, with reason: cash, credit, counterparty exists, obligation limit). A failed validation stops the workflow at this step; it must not settle anyway.
5. **Payment settles** — settlement status, ledger entry id, and amount, shown only after a passing validation.
6. **Future obligation appears** — the new obligation (amount, due tick, counterparty) appears in the inspector's obligations list for that firm.

Each step shows its status as text plus an icon, never colour alone: `proposed`, `approved`, `rejected`, or `settled`. This is a simulation settlement in the virtual ledger. It is labelled as such and is separate from the real-money x402 flow in Section 17.11, which must never be merged into this card's numbers.

## 16. Prompt parsing with AI — optional enhancement, same shape

The regex parser in Section 7 is the baseline and must always
work. This section adds an LLM parser on top of it. It must
never replace the baseline, and it must never block it.

If the LLM parser is enabled, it must return the exact
`Scenario` shape from Section 7, plus a one-sentence explanation
of what it parsed. If it returns anything else, times out, or
errors, discard its output silently in code, show the regex
result in the parsed card, and log the failure to the console.
The user must never see a broken parsed card because an LLM
call failed.

## 17. AI agent integration — CONTEXT ONLY for UI work (do not implement the proxy now)

This section is CONTEXT ONLY for UI work. Read it fully to get the UI right — proposal card, tool trace, states, and source labels — but do NOT implement the proxy, the Nebius call, or the validation gate now. The UI consumes the mock fixture in Section 19A, which has exactly the response shape in Section 17.3. A decorative LLM call that only writes text does not satisfy this section when the backend is eventually built, but for UI work the fixture is the deliverable.

### 17.0 Seamless agent integration — UX and technical rules (mandatory)

Seamless means: the user never leaves the city view, never opens
a second agent surface, and never waits on a blocking screen for
the agent. If any of these rules is broken, the integration is
not seamless, even if the proposal itself is correct.

UX rules, all mandatory:

1. No separate agent page, tab, chat window, popup, or modal.
   The agent lives inside the existing right panel, directly
   under the pinned prompt and above the side feed, in the
   same glass panel style, same font, same fade-in animation
   (400ms) as a feed item.
2. No blocking loading screen. When the agent is triggered,
   show an inline thinking row in that same panel position:
   a pulsing dot, the text "Nemotron is checking the city…",
   and the live tool trace as it arrives, collapsed to one
   line per tool. The city canvas keeps animating throughout
   — day cycle, cars, and pedestrians continue. Only tick
   advancement for that branch pauses; the visuals never freeze.
3. The proposal arrives in place. When it is ready, the
   thinking row transforms into the proposal card in the
   same position, with the same 400ms fade/slide-in as a feed
   item. No toast, no popup, no navigation, no reload.
4. Accept and Reject are inline buttons on the card itself.
   Accept immediately creates the new branch view in the same
   panel and updates the timeline branch selector in place.
   Reject dismisses the card in place and resumes tick
   advancement. Neither action navigates away from the city.
5. The tool trace is collapsible inline, default collapsed to
   one summary line ("Checked 3 sources: city summary, sector
   state, bank balance sheet"), expandable in place to the
   full trace. It must never open a separate log view.
6. The agent also appears in the side feed as a normal micro
   feed item ("Nemotron proposed rent relief…"), with the
   same green/red and arrow styling as other feed items.
   There must be exactly one proposal card and one feed
   reference to it — never a card plus a toast plus a modal
   for the same proposal.
7. Failure is inline and quiet, not an error page. Timeout,
   invalid proposal, or unconfigured provider shows a muted
   inline row in the same panel position ("Nemotron is not
   available right now — showing a rule-based option"),
   with the rule-based fallback card directly underneath it.
   The city, feed, and timeline keep working.
8. Prefetch where it costs nothing: as soon as a shock branch
   is created, start the agent call in the background for
   that branch (if configured), so that by the time the user
   opens the proposal area it is often already ready. A
   background call must never block tick playback or city
   animation, and its result must still arrive as the inline
   card in rule 3, never as a surprise popup.

Technical rules, all mandatory:

- One hook, one card, one shape: `useAgent()` and
  `AgentProposalCard` from Section 17.10 are the only agent
  UI surfaces. Mock, rule-based, and real Nemotron responses
  must share the exact same `Proposal + toolTrace` shape.
  Only `sourceLabel` differs. Swapping providers must be an
  environment change only — no UI code change, no conditional
  UI branches per provider except the source label text.
- No UI code may branch on "is this mock or real" to show a
  different layout, a different card, or a different flow.
  The layout is identical; only the label and, if applicable,
  the latency shown in the trace differ.
- Agent state is part of panel state, not global app state
  that remounts the city. Changing agent state (thinking →
  done → accepted/rejected) must never remount the city
  canvas, reset the timeline, or lose the current tick.
- The agent call must be cancellable: pressing Reject while
  thinking cancels it in place and resumes the simulation,
  with no orphaned card appearing later for that trigger.

### 17.1 Architecture — three layers, no exceptions

```
Browser simulation (rules, ledger, snapshots)
  → Proxy server (key, validation, caching, rate limits)
    → Nebius (Nemotron, OpenAI-compatible API)
  → Proxy (validate, cache, return structured proposal)
→ Browser (show proposal + tool trace, user/counterparty accepts)
→ Simulation (execute only through the ledger)
```

- The browser never calls Nebius directly and never sees the
  API key.
- The proxy never runs the simulation. It only validates and
  forwards, and it executes read tools against a snapshot the
  browser sends it.
- Nemotron never moves money directly. It proposes. The
  simulation executes, through the ledger, after validation
  and acceptance.

### 17.2 Environment and configuration

Server environment variables, all required for real mode, all
read at server start, never from the browser:

```
NEBIUS_API_KEY=            # from Nebius console, server only
NEBIUS_BASE_URL=           # OpenAI-compatible base URL from Nebius console
NEBIUS_MODEL=              # Nemotron model ID from Nebius console
AGENT_TIMEOUT_MS=30000
AGENT_MAX_CALLS_PER_BRANCH=10
AGENT_TEMPERATURE=0
```

Do not hardcode a base URL or model ID from memory. Copy both
from the Nebius console (Token Factory / AI Studio) at build
time. If any of the first three variables is missing, the
server must start in `agent_not_configured` mode and every
agent endpoint must return HTTP 503 with body
`{ "error": "AGENT_NOT_CONFIGURED" }`. The frontend must
render "Nemotron not connected — connect Nebius to enable AI
proposals" and offer the rule-based fallback, labelled
"Rule-based proposal (not Nemotron)". Never fake a Nemotron
response when the provider is not configured.

For local development without a key, implement a mock provider
behind `AGENT_PROVIDER=mock` that returns a fixed, valid
proposal from a fixture file. The mock must be labelled
"Mock agent" in every UI surface that shows it. The mock and
real providers must implement the same interface, so swapping
them is a one-variable change and no frontend code changes.

### 17.3 Endpoints — implement exactly these

All endpoints are POST except health, all accept and return
JSON, all require a `branchId` and `tick` where relevant, and
all must complete within `AGENT_TIMEOUT_MS` or return 504.

```
GET  /api/agent/health
  → { "configured": boolean, "model": string | null,
      "provider": "nebius" | "mock" | "none" }
  Must never return a key, a key prefix, or a key length.

POST /api/agent/policy
  Request: {
    "branchId": string, "tick": number,
    "city": { "name": string, "country": string },
    "shock": Scenario,
    "objectiveWeights": {
      "employment": number, "defaults": number,
      "inequality": number, "publicCost": number
    },
    "worldSummary": WorldSummary
  }
  Response: {
    "proposal": PolicyProposal, "toolTrace": ToolCall[],
    "model": string, "latencyMs": number, "cached": boolean
  }

POST /api/agent/negotiate
  Request: {
    "triggerId": string, "branchId": string, "tick": number,
    "parties": [{ "id": string, "type": string,
                  "balanceSheet": object }],
    "context": { "reason": string, "worldSummary": WorldSummary }
  }
  Response: {
    "proposal": ContractProposal,
    "counterpartyAccepted": boolean,
    "counterpartyReason": string,
    "toolTrace": ToolCall[], "model": string,
    "latencyMs": number, "cached": boolean
  }
```

`WorldSummary` is the only world data sent to the model. It
must contain aggregates only, never the full household array:

```ts
type WorldSummary = {
  tick: number; unemployment: number;
  disposableIncomeIndex: number; medianRentIndex: number;
  discretionarySpendingIndex: number; businessFailures: number;
  loanDefaults: number;
  sectorState: Record<string, {
    demandIndex: number; inventoryIndex: number;
    priceIndex: number; staff: number; openFirms: number;
  }>;
  recentEvents: string[]; // at most 10, human-readable
  governmentBudget: number; bankCapitalTotal: number;
};
```

`PolicyProposal` and `ContractProposal` schemas:

```ts
type PolicyProposal = {
  type: "rent_relief" | "wage_subsidy" | "credit_support"
    | "tax_relief" | "transfer_boost";
  targetSector: string | null;
  magnitude: number; // percent, clamp 0–50
  durationMonths: number; // clamp 1–24
  estimatedCost: number;
  rationale: string; // at most 2 sentences
};

type ContractProposal = {
  type: "extend_payment_terms" | "restructure_loan"
    | "supplier_credit" | "rent_deferral";
  fromId: string; toId: string;
  amount: number; newTermsMonths: number;
  interestRate: number | null;
  rationale: string;
};
```

If the model returns a type outside these lists, a magnitude
outside the clamp, or a missing required field, the proxy must
reject it, attempt exactly one retry with the validation error
included in the prompt, and if the retry also fails, return
HTTP 422 with the validation errors. The frontend must show
the regex/rule fallback in that case, not a broken proposal.

### 17.4 Tools — the model must use tools, not just text

Define these tools for the Nemotron chat-completions call,
using OpenAI-compatible function/tool format. The proxy
executes read tools against the snapshot sent in the request.
Write tools execute nothing; they only return the proposal
shape, which the validation gate then checks.

```ts
const tools = [
  { name: "get_city_summary", description:
    "Return the WorldSummary for the current tick.",
    parameters: { type: "object", properties: {} } },
  { name: "get_agent_balance_sheet", description:
    "Return the balance sheet for one agent by ID.",
    parameters: { type: "object", properties: {
      agentId: { type: "string" } }, required: ["agentId"] } },
  { name: "get_sector_state", description:
    "Return demand, inventory, price, staff, and open firms for one sector.",
    parameters: { type: "object", properties: {
      sector: { type: "string" } }, required: ["sector"] } },
  { name: "propose_policy", description:
    "Return a PolicyProposal in the schema from Section 17.3.",
    parameters: { /* PolicyProposal JSON schema */ } },
  { name: "propose_contract", description:
    "Return a ContractProposal in the schema from Section 17.3.",
    parameters: { /* ContractProposal JSON schema */ } },
];
```

Tool loop, implement exactly:

1. Send system prompt (Section 17.5) + user context
   (city, shock, WorldSummary, objective weights, allowed
   types and caps) + tools, temperature from
   `AGENT_TEMPERATURE` (0), max tokens 1200.
2. If the model returns tool calls, execute each read tool
   against the snapshot, append the tool results to the
   conversation, and send it back to the model. Repeat for at
   most 4 tool rounds.
3. The final message must be a tool call to `propose_policy`
   or `propose_contract`, or a JSON object matching the
   proposal schema. Parse it, validate it (Section 17.6),
   and return it with the full `toolTrace`:
   `[{ tool, arguments, resultSummary, timestampMs }]`.
   `resultSummary` must be a short string, never the full
   world state, so the trace is readable in the UI.
4. If the model never calls a tool and just returns prose,
   treat that as a failed call and retry once with the
   instruction "You must call a read tool before proposing."
   If it still does not call a tool, return 422. A proposal
   with an empty tool trace must never be shown as an
   "agent" proposal in the UI.

### 17.5 System prompt — use this text, do not paraphrase it away

Send this as the system message for every agent call, with
`{city}`, `{shock}`, and `{caps}` filled in from the request:

```
You are the policymaker and negotiation agent inside a stylized
city economy simulation for {city}. You do not control the
simulation directly. You inspect state with tools, then propose
one policy or one contract in the exact schema provided.

Rules:
- Call a read tool before proposing. Do not propose from the
  summary alone if a relevant balance sheet or sector state
  is available.
- Propose only types listed in the allowed vocabulary. Do not
  invent new policy or contract types.
- Respect all caps: magnitude, duration, budget, and bank
  capital. If a proposal would exceed a cap, reduce it, do not
  ignore the cap.
- Do not invent money, firms, households, or banks. Use only
  IDs and values returned by tools.
- Your rationale must be at most two sentences and must name
  the trade-off: who benefits, who pays, and what could go wrong.
- Return the proposal only through the propose_policy or
  propose_contract tool, in the exact schema provided.
- This is a stylized simulation, not a forecast or real policy
  advice. Do not present your proposal as a real-world
  recommendation.
```

User message template, fill in from the request:

```
City: {city}, {country}
Current shock: {shockType} {direction} {magnitude} for
{durationMonths} months, target: {targetSector or "all sectors"}
Tick: {tick} of 24
Objective weights: employment {w1}, defaults {w2},
inequality {w3}, public cost {w4}
World summary: {WorldSummary as JSON}
Allowed policy/contract types and caps: {caps as JSON}
Task: inspect the relevant state with tools, then propose one
policy or contract that best fits the objective weights.
```

### 17.6 Validation gate — check every item, in order

Before any proposal reaches the simulation, the proxy and the
frontend must both be able to run these checks. The proxy is
authoritative; the frontend check is for fast UI feedback only.

1. Schema: all required fields present, correct types, no
   extra type values.
2. Caps: magnitude 0–50, duration 1–24, estimated cost <=
   government budget for policies, amount <= counterparty
   cash plus loan headroom for contracts.
3. Existence: `fromId` and `toId` exist in the snapshot,
   target sector exists or is null.
4. Authorization: for contracts, the counterparty rule in
   Section 17.7 has accepted, or the user has clicked Accept
   in the UI. For policies, the user has clicked "Run as new
   branch". No proposal executes on model output alone.
5. Ledger feasibility: applying the proposal must not create
   a negative bank capital balance or a negative government
   budget in the same tick. Simulate the first tick of the
   proposal on a cloned snapshot and reject it if either
   goes negative.
6. If any check fails, return the list of failures to the
   caller. Do not silently clamp a proposal into validity and
   present it as what the model proposed. Clamping is allowed
   only inside a retry, where the model itself returns a new
   proposal within caps.

### 17.7 Counterparty acceptance rule (negotiations)

For `POST /api/agent/negotiate`, after the model proposes a
contract, run this rule-based counterparty check in the proxy
(or in the simulation, but in exactly one place, documented in
code):

```
counterpartySurvivalGain = estimatedCashSavedByCounterparty
  / max(counterpartyCash, 1)
counterpartyAccepted = counterpartySurvivalGain > 0.05
  && proposal.amount <= counterpartyLoanHeadroom
  && proposal.newTermsMonths <= 24
counterpartyReason = accepted
  ? "Terms improve counterparty cash position by more than 5%."
  : "Terms do not improve counterparty cash position enough, or exceed headroom."
```

Show `counterpartyAccepted` and `counterpartyReason` in the
UI next to the proposal. If rejected, the negotiation ends,
a feed item records the rejection, and the simulation
continues without the contract. Do not retry a rejected
negotiation automatically with a different model call in the
same tick; the user may trigger it again manually.

### 17.8 When the agent is called — exact triggers only

Call the agent only at these triggers. Do not add triggers
without updating this list and the tests:

1. User clicks "Ask Nemotron for a rescue policy" in city
   view. This creates a policy proposal for the current
   branch and tick.
2. A firm crosses distress: cash < 0 for 2 consecutive ticks
   and staff > 0. Trigger a supplier negotiation for that
   firm, at most once per firm per branch.
3. A bank's default rate exceeds 5% in a tick. Trigger a
   bank workout negotiation for its largest defaulting
   borrower, at most once per bank per branch.
4. User clicks "Run Nemotron branch" after a policy proposal
   has been accepted. This is not a new agent call; it runs
   the stored proposal as a new branch.

On trigger, pause tick advancement only for that branch — the city canvas, day cycle, and movers keep animating. Show the inline thinking row from Section 17.0 in the right panel (no modal, no spinner page, no separate agent view), with the live tool trace as tool calls arrive (or, if streaming is not implemented, show the trace when the call completes — do not show a fake streaming trace). On completion, show the
proposal card with: proposal details, rationale, tool trace
(collapsible), estimated cost, and Accept / Reject buttons.
Accept for a policy creates a new branch. Accept for a
contract executes it in the current branch from the next
tick. Reject discards it and resumes the simulation.

### 17.9 Caching, replay, and determinism

- Cache key: `sha256(branchId + "|" + triggerType + "|" +
  tick + "|" + stateHash)`, where `stateHash` is a hash of
  the WorldSummary plus the involved agents' balance sheets.
  Store the full response (proposal + tool trace + model)
  in the branch snapshot under `agentDecisions[triggerId]`.
- On replay, scrub, or branch comparison, reuse the cached
  decision. Never call Nebius again for the same cache key.
- Enforce `AGENT_MAX_CALLS_PER_BRANCH` (default 10). If the
  limit is reached, the UI must say "Agent call limit reached
  for this branch" and offer the rule-based fallback.
- Log every agent call to the console in development with:
  trigger, cache hit or miss, tool count, latency, model.
  Never log the API key, the full world state, or personal
  data. There is no personal data in this simulation, and
  that must stay true: never send real user data to the model.

### 17.10 Frontend integration — how a developer uses it

Provide exactly one hook and one component, so any developer
can use the agent without reading the proxy code:

```ts
// apps/web/src/agent/useAgent.ts
const { proposePolicy, negotiate, state } = useAgent();
// state: "idle" | "working" | "done" | "error" | "not_configured"
// proposePolicy(branchId, tick, shock, weights) → PolicyProposal + trace
// negotiate(triggerId, branchId, tick, parties) → ContractProposal + trace
```

```tsx
// apps/web/src/agent/AgentProposalCard.tsx
<AgentProposalCard
  proposal={proposal}
  toolTrace={trace}
  sourceLabel="Nemotron on Nebius" // or "Mock agent" or "Rule-based"
  onAccept={...}
  onReject={...}
/>
```

`sourceLabel` must always be truthful. If the proposal came
from the mock provider, it must say "Mock agent". If it came
from the rule fallback, it must say "Rule-based". Only a
successful Nebius call may say "Nemotron on Nebius".

### 17.11 Optional x402 agentic payment — separate, after 17.1–17.10

Do not start x402 until the Nemotron decision loop above
works end to end. When you do, implement exactly one flow:

- One agent, one endpoint, one capped budget. Budget cap:
  5.00 in the endpoint's currency, hard-coded in server config,
  editable only by changing server config, never by the model.
- Flow: agent requests a paid resource → server returns HTTP
  402 with payment instructions → agent pays with its wallet
  → agent retries with payment proof → server verifies →
  resource is returned with a receipt ID.
- The UI must show, in one place: amount, endpoint, receipt
  ID, and remaining budget. The virtual ledger and the real
  x402 payment must be labelled separately and must never be
  merged into one number.
- If x402 is not configured, hide the x402 UI entirely. Do
  not show a fake purchase.

## 18. File tree — create exactly this structure

```
economy-god-mode/
  AGENT_PROMPT.md
  BUILD_PROMPT.md
  apps/web/
    index.html
    package.json
    vite.config.ts
    src/
      main.tsx
      App.tsx
      state/store.ts
      data/
        countries.json
        cities.json
        countries.geojson
        cityTemplates.ts
      globe/
        Globe.tsx
        CountryLayer.tsx
        CityPins.tsx
        GlobeCamera.ts
      city/
        CityCanvas.tsx
        cityGenerator.ts
        cityRenderer.ts
        movers.ts
        activity.ts
      sim/
        constants.ts
        engine.ts
        rng.ts
        agents.ts
        ledger.ts
        markets.ts
        scenarios.ts
        branch.ts
      agent/
        useAgent.ts
        AgentProposalCard.tsx
        agentTypes.ts
      ui/
        CountryLabel.tsx
        PromptPanel.tsx
        SideFeed.tsx
        Inspector.tsx
        KpiStrip.tsx
        Timeline.tsx
        BranchCompare.tsx
        CrisisPanel.tsx
        NetworkView.tsx
        ForkReality.tsx
        PaymentActivityCard.tsx
        TopControls.tsx
      styles/theme.css
  server/                         # STUB ONLY - context, not implemented in UI build
    index.ts                    # stub: type signatures only, no logic
    nemotron.ts                 # stub: context only
  # fixtures are the UI's backend - see Section 19A
  # apps/web/src/data/fixtures.ts + fixtures/*.json
  tests/
    ledger.test.ts
    determinism.test.ts
    cityGenerator.test.ts
    scenarios.test.ts
    agentValidation.test.ts
```

Do not create extra top-level folders without a reason written
in the file that needs them. Do not put simulation code in
`ui/` and do not put rendering code in `sim/`.

## 19. Build order

**UI-first order for H's work.** Do tasks in this order:
T0, T1 (data shapes only), T2, T3, T4, T5, T6, T9, then T8, T10,
T12 as fixture-driven UI only.

**City-phase build priority, after the globe-to-city transition exists (from the backend-later brief, in this order):**
1. Main layout, controls, metrics, and clickable institutions.
2. Live events and inspector.
3. Crisis trigger and visible consequences.
4. Fork Reality comparison.
5. Network view and payment workflow polish.
This priority governs the city tasks T8–T12; it does not replace the globe tasks T0–T6. T7 (simulation engine), T10
(branching engine), and T11 (Nemotron proxy) are CONTEXT ONLY
in this build: do not implement them now. Their UI surfaces —
timeline scrubbing, branch comparison, proposal card, tool
trace — are built against the fixtures in Section 19A.

## 19A. Fixtures — the UI's backend (build these, not a backend)

Create `apps/web/src/data/fixtures/` with exactly these files.
Every file must match the schemas in this document, so a real
backend can replace `fixtures.ts` later without touching UI code.

- `sfSnapshots.json`: San Francisco snapshots for ticks 0–24
  for three branches: `baseline`, `shock`, `shockPlusPolicy`,
  plus Fork Reality branches `noIntervention`, `emergencyLending`,
  `householdSupport` from the crisis tick onward (Section 13A).
  Each snapshot: tick, KPI values (Section 15 strip: Employment, Household Cash, Business Defaults, Bank Stress, Public Intervention Cost), district
  activity values (Section 11), and a list of open/closed firms
  by district. Values must move in the Section 12 directions
  after the shock tick: disposable income down, spending down,
  defaults up. Do not hand-write a single endpoint; write a
  plausible 24-tick series per branch.
- `sfFeed.json`: feed items per tick, macro and micro, using
  the `FeedItem` schema in Section 15, with `isGood` colour
  logic already applied in the data (direction + isGood flag).
  At least 3 macro and 5 micro items across the shock ticks, including the linked crisis chain in Section 15A: Bank 2 asset loss → lending contracts → Café 14 cannot refinance → payroll missed, each item clickable via its `actorId`.
- `sfProposal.json`: one Nemotron-style proposal with a
  non-empty `toolTrace` (at least 3 tool calls: get_city_summary,
  get_sector_state, get_agent_balance_sheet), proposal details
  per Section 17.3, and `sourceLabel` set to "Mock agent" —
  never "Nemotron on Nebius" for fixture data. The fixture
  must also provide the seamless UI states from Section 17.0
  as data, not as separate screens: `thinking` (thinking row
  + partial trace), `done` (full proposal card), `error`
  (muted inline row + rule fallback), and `not_configured`
  (muted inline row + rule fallback). The UI switches
  between these states in place, in the same panel position.
- `sfInspector.json`: inspector data for at least one firm
  (including Café 14), one household group, and one bank (including Bank 2), each with cash, assets, debt, obligations, relationships (employer, bank, borrowers, suppliers as appropriate), last 5 ledger entries, a state-derived reason sentence, and, for AI agents, observations, proposed action, explanation, validation result, and settlement status (Sections 15 and 15C).
- `sfFork.json`: Fork Reality data (Section 13A): the three branches, matching charts for Employment, Business Defaults, Bank Stress, and Public Intervention Cost on a synchronized tick axis, and the AI central bank recommendation with tradeoff and final-tick values.
- `sfNetwork.json`: network data (Section 15B): bank and business nodes, loan/obligation/payment edges with exposure amounts, and counterparty lists per node.
- `sfPayment.json`: agentic payment workflow for Café 14 (Section 15C): inventory need, two supplier offers, selected terms, validation result, settlement status and ledger entry, and the resulting future obligation.
- `sfCrisis.json`: crisis trigger options (Section 15A): banks 1–4, asset categories, default Bank 2, default 40% loss in one asset category.
- `sfCityLayout.json`: the San Francisco layout from Section 9
  (districts, roads, buildings, water, parks) for one fixed seed.
  The city canvas reads this file; it does not generate a new
  layout at runtime in the UI build.

`fixtures.ts` must export only these functions, and UI code
must use only these functions for backend data:
`getSnapshot(tick, branch)`, `getFeed(tick)`,
`getProposal()`, `getInspector(actorId)`,
`getCityLayout()`, `getFork()`, `getNetwork()`,
`getPayment(actorId)`, `getCrisisOptions()`. No other data source is allowed in UI code. A backend adapter later implements these same functions; UI code does not change when the backend connects (Section 0A).

 — tasks, in order, with acceptance criteria

Work through these tasks in order. Do not start a later task
until the current task's acceptance criteria pass. Each task
ends with a manual check, not just a passing build.

**T0. Scaffold.**
Create the Vite React TypeScript app and the file tree in
Section 18 with empty placeholder components. Install the
Section 2 dependencies. Acceptance: `npm run dev` serves a
blank page, `npm run build` succeeds, `npm test` runs with
zero tests and exits 0.

**T1. Data.**
Write `countries.json` (all countries for highlighting, pins for the USA only), `cities.json` (USA only: San Francisco playable, Los Angeles, New York, Chicago, Seattle disabled), and `cityTemplates.ts` (San Francisco only). Acceptance: the USA has San Francisco plus disabled pins, a non-US country shows the not-available notice with zero pins and does not crash.

**T2. Globe.**
Implement Section 5 and Section 6. Acceptance: the Section 5
and Section 6 acceptance checks pass, three runs in a row,
with no console errors on unmount.

**T3. Prompt panel and parser.**
Implement Section 7, including the three parse test cases as
unit tests. Acceptance: all three parse tests pass, the parsed
card shows the original prompt verbatim, sliders edit the
scenario, and Cancel returns to editing.

**T4. Transition.**
Implement Section 8. Acceptance: the Section 8 acceptance
check passes, Back during transition restores the globe
cleanly, and there is no blank frame.

**T5. City generation.**
Implement Section 9. Acceptance: the layout hash test passes,
Re-running San Francisco produces the identical layout.

**T6. City rendering and movers.**
Implement Section 10, with a static city and movers running
on a fixed, non-simulated activity vector first. Acceptance:
the city looks Sims-like in a screenshot, cars stay on roads,
people stay on footpaths, the day cycle is visible, and the
frame rate stays above 50fps with 400 movers on a typical
laptop.

**T7. Simulation and ledger.**
Implement Section 12 and Section 13, excluding branching.
Acceptance: ledger validation passes for 24 ticks, the
determinism test passes, and a +2 point rate hike in San Francisco
moves disposable income, spending, and defaults in the
expected directions (down, down, up) without any hand-written
trend.

**T8. Activity mapping.**
Implement Section 11. Acceptance: the Section 11 acceptance
check passes — the post-shock city is visibly different at
the same visual time of day, before any chart is read.

**T9. Side feed, KPIs, timeline, inspector.**
Implement Section 15. Acceptance: macro and micro items
appear as ticks run, colours and arrows match the `isGood`
rule, clicking a feed item opens the correct inspector, and
scrubbing the timeline restores exact snapshots.

**T10. Branching and comparison.**
Implement Section 13 branching and the comparison view.
Acceptance: baseline, shock, and shock-plus-policy branches
share the same starting snapshot, the comparison chart has
one line per branch with the shock tick marked, and a branch
with a different starting snapshot shows an error, not a
chart.

**T11. Nemotron UI, fixture only (CONTEXT ONLY backend).** Implement the proposal card, tool trace, Accept/Reject states, and source labels from Section 17 using `sfProposal.json` only. Do NOT implement the proxy, the Nebius call, or validation. Acceptance: the card shows a non-empty tool trace, source label reads "Mock agent", Accept creates the `shockPlusPolicy` branch view from fixtures, Reject discards it, and unconfigured/real-provider states are shown as UI states from fixtures, not from a live call.

**T12. Polish, x402 (optional), demo insurance.**
Polish visuals per Section 3, implement Section 17.11 only
if T11 is fully done, then record a backup video of the
3-minute demo in Section 21. Acceptance: the demo runs
end to end with no network except the optional Nemotron call,
and the recorded backup exists before any judging run.

## 20. Tests — implement all of these, no exceptions

Unit tests, in `tests/`:

1. `ledger.test.ts`: randomized event replay over 24 ticks,
   ledger imbalance count must be 0, duplicate settlement
   rate must be 0.
2. `determinism.test.ts`: same city, seed, and scenario run
   twice → final KPIs and ledger hash match exactly.
3. `cityGenerator.test.ts`: same seed → same layout hash;
   different seed → different layout hash; the San Francisco
   layout hash for one seed differs from its hash for another seed.
4. `scenarios.test.ts`: the three parse test cases in
   Section 7, plus one test for each keyword mapping and
   one test for missing-number defaults.
5. `agentValidation.test.ts`: a proposal with magnitude 99
   is rejected; a proposal with an unknown type is rejected;
   a proposal exceeding government budget is rejected; a
   valid proposal passes; a contract with a non-existent
   counterparty is rejected.

Manual QA, run before every demo:

- Globe screenshot looks like Earth from space: blue oceans, recognisable continents, clouds, ice caps.
- Hover United States → "United States" top-right. Click → yellow,
  zoom, pins.
- Click San Francisco pin → prompt panel opens, globe stays centred.
- Submit the San Francisco rate-hike example → parsed card shows
  interest_rate, up, 2, 24 months → confirm → zoom into pin,
  globe fades out, city fades in, no blank frame.
- City is alive for 60 seconds: cars, people, day cycle.
- Run 6 baseline ticks, then the shock: city visibly changes
  at the same visual time of day.
- Feed shows macro and micro items, green/red with arrows,
  fading in. Clicking one opens the correct inspector.
- Branch comparison shows baseline vs. shock from the same
  snapshot.
- Pick a non-US country: it highlights, shows the not-available notice, and shows zero pins. Pick Los Angeles: it shows the coming-soon pill and does nothing else.
- Create World, Play/Pause, Speed, Reset, and the current tick work from the top control bar; Reset restores the healthy world.
- Trigger Crisis with Bank 2 at 40% shows the Bank 2 → Café 14 chain in the feed, each item clickable, and Café 14's inspector explains the missed payroll.
- Fork Reality shows No intervention, Emergency bank lending, and Direct household support from the same crisis snapshot, with synchronized charts and an AI recommendation citing final-tick values.
- City/Network toggle preserves tick, branch, and selection; a node selection highlights only its counterparties and an edge selection shows its exposure amount.
- Café 14's payment activity card shows all six steps with proposed/approved/rejected/settled statuses, and the settled payment's future obligation appears in its obligations list.
- With Nemotron unconfigured: agent UI says not connected,
  offers a labelled rule fallback, core demo still works.
- With Nemotron configured: a policy proposal shows a
  non-empty tool trace and the label "Nemotron on Nebius".

## 21. Three-minute demo script — the build must support this exactly

Minute 0:00–0:30 — Globe in space, rotating slowly. Hover
United States, label appears top-right. Click United States, it turns
yellow, camera zooms, pins drop in.

Minute 0:30–1:00 — Click the San Francisco pin. Prompt panel opens
on the right. Type or select: "How will heightened interest
rates affect demand and supply in San Francisco?" Confirm the parsed
card: interest rate, up, 2 points, 24 months.

Minute 1:00–1:30 — Camera zooms into the San Francisco pin, globe
fades out, miniature San Francisco fades in, alive with cars and
people. Use Create World, then run 6 baseline months so the city looks healthy. The top metrics strip reads Employment, Household Cash, Business Defaults, Bank Stress, Public Intervention Cost.

Minute 1:30–2:15 — Open Trigger Crisis, select Bank 2, 40% loss in one asset category. The shock lands: Bank 2 pulses red, lending contracts, Café 14 dims. Read the side feed chain: Bank 2 suffers an asset loss → lending contracts → Café 14 cannot refinance → payroll is missed. Click Café 14 to open its inspector and show cash, debt, obligations, and why payroll was missed.

Minute 2:15–3:00 — Click Fork Reality. Compare the three futures from the same crisis snapshot, with synchronized charts for Employment, Business Defaults, Bank Stress, and Public Intervention Cost, plus the AI central bank recommendation and its tradeoff. Toggle City → Network to show Bank 2's counterparties and Café 14's exposure, then open Café 14's payment activity card (inventory need → two supplier offers → selected terms → validation → settlement → future obligation). End on the Fork Reality comparison: same starting world, different outcomes, proven by the shared snapshot and the ledger, not by a scripted animation, with no terminal opened.

If any minute of this script cannot be performed with the
current build, that minute's task is not done, regardless of
how many other features exist.

## 22. Forbidden — do not do any of these, even if asked mid-build

- Do not fetch country polygons, city data, or census data
  from a live URL at runtime for the core demo.
- Do not use `Math.random()` in city generation, simulation,
  or branching. All randomness comes from a seeded generator
  with a stored seed.
- Do not put an LLM call, a network call, or a timer-based
  animation inside the tick function.
- Do not write a second simulation for the visuals. The city
  activity vector comes from the real simulation aggregates.
- Do not add a feature that only works for a city other than
  San Francisco in this demo. San Francisco is the demo city;
  other cities are out of scope until the demo is done.
- Do not hide a mock agent behind a Nemotron label, and do
  not hide a rule fallback behind an agent label.
- Do not present simulated results as forecasts, and do not
  remove the stylized-simulation label to make a screenshot
  look cleaner.
- Do not add authentication, a database, or user accounts.
  They are out of scope for this hackathon build.

## 23. Final verification — before saying "done"

The agent must run, in order, and report the result of each:

1. `npm test` — all tests in Section 20 pass.
2. `npm run build` — succeeds with no TypeScript errors.
3. Manual QA in Section 20 — every item passes, including a non-US country and a disabled US pin.
4. Demo script in Section 21 — performed end to end, timed,
   with no step skipped.
5. Agent check — mock mode labelled correctly, unconfigured
   mode labelled correctly, real mode (if configured) shows
   a non-empty tool trace and the correct source label.
6. Visual check — screenshots of the stylized Earth globe, the yellow
   country with pins, the prompt panel, the transition
   midpoint, and the living city, all attached or linked in
   the final report.

If any item fails, the build is not done. Report exactly
which item failed, what was observed, and what is needed to
fix it. Do not report a partial build as complete, and do
not claim a feature works because its code exists. A feature
works only when its acceptance check in this document passes.
