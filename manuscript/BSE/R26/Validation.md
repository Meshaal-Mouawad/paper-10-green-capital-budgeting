# Paper 10 R26 — Figure placement and integrity audit

Baseline: R25 final submission archive; all 11 listed checksums verified before editing.

## Source-to-action
Editage, How to Create Figures for a Research Paper: Examples and Tips (supplied PDF), pp. 3–5, 7–9, 11: match the figure type to the scientific message; provide standalone captions, near-claim callouts, sequential numbering, vector output, and reproducible source. Applied a single additional schematic because it explains the causal/analytical sequence rather than duplicating a numerical table. No new quantitative plot or data generation was necessary.

## Placement
- Figure 1: Methods 3.3, callout after Equation (4), displayed at top of reading-copy page 5, after the callout on page 4. Panel A distinguishes approved and reported eligibility under identical inputs, ceiling and budget. Panel B shows the successive optimal values underlying Equation (3). Arrows encode logical steps, not numerical magnitudes.
- Figure 2: Results 4.1, existing worked example, displayed page 7.
- Figure 3: Results 4.3, existing continuous policy maps, displayed page 8.
- Anonymous submission PDF: captions only, numbered 1–3; figure PDFs provided separately. The Wiley class controls float placement in reading copy.

## Verification
- Original R25 body restored exactly by removing the single new callout and conditional figure inclusion.
- Five equation environments identical; all original source members except body.tex, main.tex and README.md byte-identical, including tables, bibliography, figures and private author title-page source.
- Main.tex unchanged through the figure legends section; new caption inserted ahead of original legends.
- New diagram produced from editable Python code, with vector PDF and SVG; no numerical data retyped or inferred. Labels and arrow meanings defined. Colors are redundant with direct labels and positions; no dependence on red/green contrast. Source and figure rendered at actual manuscript size.
- Both manuscripts compiled to 11 pages, with no overfull boxes or unresolved-reference warnings found in final logs. Figure pages 5, 7, 8 visually inspected; new diagram spacing corrected after first pass.
- Harvard DOI 10.7910/DVN/ZSXX0E and existing GitHub URL verified as PDF link annotations in the reading copy. No new deposit or public repository changes.
- Author title-page PDF and anonymous title-page PDF preserved; private contact information remains outside the manuscript. Approved declarations unchanged.

Decision: R26 is an internally verified visual-only extension of R25. No new experiments or independent review performed. The original R25 archive is retained. Existing published replication data unchanged. Journal-specific artwork compliance was not independently rechecked in this visual pass; established Wiley packaging retained.
