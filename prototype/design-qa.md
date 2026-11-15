# Design QA — TradePilot Interactive MVP

- source visual truth path: `C:\Users\zy\Documents\Codex\2026-11-14\tradepilot-inquiry-workspace-interaction-design-tradepilot\prototype\source-option-1.png`
- implementation screenshot path: `C:\Users\zy\Documents\Codex\2026-11-14\tradepilot-inquiry-workspace-interaction-design-tradepilot\prototype\implementation-1440x1024.png`
- focused implementation screenshot: `C:\Users\zy\Documents\Codex\2026-11-14\tradepilot-inquiry-workspace-interaction-design-tradepilot\prototype\implementation-focus.png`
- implementation URL: http://localhost:4173/
- viewport: 1440 × 1024 CSS px; device density 1
- source pixels: 1487 × 1058; normalized by comparing the same full desktop composition and visible default Snapshot state
- implementation pixels: 1440 × 1024
- state: Nordlicht GmbH / Business Snapshot / default light theme

## Full-view comparison evidence

The selected visual and implementation both use the same three-region structure: compact inquiry navigation, flexible center workspace, and fixed action panel. The implementation preserves the reference hierarchy, bright neutral canvas, indigo emphasis, small semantic pills, compact business table, current-priority action, and evidence-to-action chain. Major region proportions and above-the-fold content are equivalent at 1440 × 1024.

## Focused region comparison evidence

The center-region capture verifies readable 14–16px product typography, field-row rhythm, restrained semantic tokens, product candidate density, NEEDS_CONFIRMATION presentation, and the evidence-to-action sequence. Focused evidence was necessary because full-view labels are too small to judge status hierarchy reliably.

## Required fidelity surfaces

- **Fonts and typography:** Inter + Noto Sans SC provide comparable neutral enterprise proportions. Heading hierarchy, body weight, wrapping, and compact labels remain readable.
- **Spacing and layout rhythm:** 286px / flexible / 326px grid, 54px header, 20–26px work-area spacing, and lightweight dividers match the source's density without clipping.
- **Colors and visual tokens:** White canvas, cool-gray separators, indigo primary, green confirmed, amber confirmation-needed, and blue inferred states preserve the source balance and accessible distinction.
- **Image and asset quality:** The selected default screen's information design does not require hero imagery. Product thumbnails were intentionally omitted from the compact prototype table rather than replaced by placeholders; Phosphor icons provide consistent UI iconography.
- **Copy and content:** Nordlicht, ANC, Germany, 1,000 units, OEM Logo, CE scope, candidate names, and actions remain consistent across screens. DEMO knowledge sources are explicitly labeled.

## Interaction verification

Tested in the in-app browser:
- import modal opens and closes
- product matching screen opens and match status can be changed
- knowledge screen opens, evidence can be added, and Zhihu source can be disabled/re-enabled
- communication screen generates a reply, saves a version, and returns to Snapshot
- evidence drawer opens from Snapshot/action panel
- inquiry navigation, search/filter controls, and next-step checkboxes are interactive
- production build and Sites worker tests pass
- no new console errors after key fixes and reload

## Comparison history

Initial browser pass found React missing-key warnings in Snapshot and Matching. Keys were added to rendered collections, the production build was rerun, and the page was reloaded. The final 1440 × 1024 capture shows no visual regression.

## Findings

No actionable P0, P1, or P2 fidelity issues remain.

## Follow-up polish

- P3: replace the temporary compact “T” brand mark with an approved TradePilot vector asset when brand assets exist.
- P3: optional product packshots can be added when approved product imagery is available.

## final result

final result: passed

