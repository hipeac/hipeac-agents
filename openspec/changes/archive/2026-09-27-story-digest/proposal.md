# Proposal

## Why

With recall fixed, the digest grew to ~3,000 words and ~100 links a week — unreadable for the editorial board. Experiments on W38–W39 showed that a few short stories per theme, with the findings linked inline, read well at 600–800 words, and that letting the model cite findings by id (code filling in the URLs) makes invented links impossible.

## Changes

- The digest is a bottom line, then at most two stories per theme, board tips, newly converged stories and a one-line list of quiet themes. One big thing, What's brewing, Also worth watching and Trending go.
- One prose call writes the stories from each theme's top candidates; code resolves citations to links, drops anything uncited, and enforces the budget.
- The model's headline becomes the email subject; every finding is kept in a signals log beside the digest.
- Themes get an optional display title for headings.
- Spec drift fixed: arXiv is read from the past-week listing with a per-category pick (the API host rejects Python clients), and `--only` limits the mailbox and sweep channels too.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/weekly-digest`, `vision-watch/candidate-verification`, `vision-watch/clustering`, `vision-watch/source-collection`, `vision-watch/runs`.
