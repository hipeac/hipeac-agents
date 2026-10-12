# Ideas

## #harvest

- Gate verdict is lenient: nearly every candidate reaching it passes, and the 4-per-source cap does the filtering. Consider stricter significance rules or a "not a signal" outcome. _(W39 test harvest, 2026-09-27)_
- The `direction` field is near-useless (664 strengthens / 54 weakens / 1 new over 14 weeks) and the digest no longer shows it: drop it, or rework the prompt. _(replay review, 2026-09-27)_
- Small model scores frontier-lab news higher (mean significance 3.12 vs 2.59; 28% vs 9% scored 4) despite the "consequence, not headline size" rule; it still drives the per-source cap. `digest-rank-without-significance` only removes it from story ranking. _(digest-skew analysis, 2026-09-28)_

- Newsletter items dated 1-2 days before the week window are rejected `out_of_window` although they arrive in that week's newsletters; W39 lost "Gemini accessed three real companies" this way. Accept a small grace for newsletter items. _(W39 phase comparison, 2026-09-28)_
- Next computing paradigm and Continuum infrastructure get almost no evidence (quiet 11 of 14 weeks even after new look_for terms); they need sources (Bytecode Alliance, LF Edge, Eclipse edge, EUDI wallet news). _(re-harvest W26–W39, 2026-09-29)_

## #digest

- Digests read thin: about one story per theme, 400–770 words, the limit of 2 per theme rarely reached. Revisit the 700-word target and "quiet is fine" for themes with 3+ signals. _(digest-skew analysis, 2026-09-28)_
- Many one-off "new topic" tags (82 of 369 items over W26–W39); only a few recur (research programmes, processor security, post-quantum, AI and work, sensors). Review recurring NEW clusters with the board every few months to grow `themes.yaml`. _(re-harvest W26–W39, 2026-09-29)_
