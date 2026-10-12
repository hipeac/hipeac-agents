# monthly-digest Specification

## Purpose

The month-end digest for the editorial board: where each open question stands after the month's weekly signals, across themes and gated by evidence in code, with a draft position for the 2027 Vision per qualifying question, new topics the board could add, and the questions with thin or no evidence.

## Requirements

### Requirement: Weeks in a month

A month SHALL cover the editorial weeks that have most of their days in it: the weeks whose Thursday falls in that calendar month, as ISO does for years. Cluster tallies SHALL count entries up to and including the month's last such week. A month SHALL be composed only once its last week has closed. Without `--month`, `monthly-digest` SHALL target the latest complete month, so it can run every Monday after the weekly run: a month already composed is skipped at no cost. An explicit `--month` that is not complete SHALL be refused with exit code 2.

#### Scenario: July 2026

- **WHEN** the operator runs `monthly-digest --month 2026-07`
- **THEN** the month covers W27–W31, from Monday 29 June to Sunday 2 August 2026

#### Scenario: Week across two months

- **WHEN** a week runs from Monday 28 September to Sunday 4 October 2026
- **THEN** it belongs to October, which holds four of its days

#### Scenario: Monday run without a month

- **WHEN** `monthly-digest` runs on Monday 5 October 2026 without `--month`
- **THEN** it targets September 2026 (W36–W39), whose last week closed on 27 September

#### Scenario: Month already composed

- **WHEN** `monthly-digest` runs on Monday 12 October 2026 without `--month` and September already has a digest
- **THEN** it makes no prose call and writes nothing

#### Scenario: Month not complete

- **WHEN** the operator runs `monthly-digest --month 2026-10` on Monday 5 October 2026
- **THEN** the run refuses with exit code 2, because W44 closes on 1 November

### Requirement: Evidence gate

The monthly digest SHALL read the ledgers of the month's weeks. A question SHALL qualify when, in the month, it has three or more signals across two or more weeks. A NEW topic SHALL qualify when its story (cluster) has three or more NEW signals in the month, or two once the story is a candidate trend. A signal counts under a question only while the question's current text equals the text recorded in the ledger; signals on a changed or removed question are listed under "Earlier questions". The gate SHALL be computed in code; only qualifying questions and topics, with their signals, are given to the prose call.

#### Scenario: One early signal

- **WHEN** a question's only signal in the month is one early signal
- **THEN** it gets no answer section and is listed under "Thin evidence"

#### Scenario: Two signals

- **WHEN** a question has two signals in two weeks, neither early
- **THEN** it is listed under "Thin evidence"

#### Scenario: Recurring question

- **WHEN** a question has three signals across two weeks, all early
- **THEN** it qualifies

#### Scenario: Question reworded

- **WHEN** the board rewords `agentic-ai.1` after W36 and the ledger holds W35 signals on its old text
- **THEN** those signals are listed under "Earlier questions" and do not count for the new text

### Requirement: Where each question stands

One prose call SHALL write, for each qualifying question, its lean, the evidence across weeks naming them, a draft position the 2027 Vision could take, and what is still open; for each qualifying NEW topic, the evidence and a question the board could add; and a bottom line. The question field SHALL be restricted to the qualifying ids. When the digest is assembled, an answer for a question that did not qualify SHALL be dropped. Each answer SHALL show the number of signals and weeks behind it, counted in code. A month with nothing qualifying SHALL make no prose call.

#### Scenario: Answer for an unqualified question

- **WHEN** the prose call returns an answer for a question that did not qualify
- **THEN** it is not printed

#### Scenario: Nothing qualifies

- **WHEN** no question or topic qualifies in the month
- **THEN** the digest says so, lists the thin evidence and unanswered questions, and no prose call is made

### Requirement: Digest sections

The monthly digest SHALL contain:

- **Bottom line**: 2-3 sentences on the most settled answers and the biggest surprise;
- **Where the questions stand**: one section per qualifying question, across all lines, most evidence first (signals, then weeks, counted in code), each headed by the question with its line as a tag: lean, signals and weeks, evidence, "For 2027", "Still open";
- **New for the board**: qualifying NEW topics with a proposed question, when any;
- **Thin evidence**: questions with signals below the gate, one line per theme with each question's signal and week counts, when any;
- **No evidence this month**: the questions with no signal in the month, one line per theme, when any;
- **Earlier questions**, when any.

A qualifying question the prose call left unanswered SHALL still be printed, with its counts and its signals' texts. The closing line SHALL give the qualifying and total question counts, the new topics, the signals read, and any week of the month without a ledger.

#### Scenario: Dormant cluster

- **WHEN** a question received no signal in the month
- **THEN** it is listed under "No evidence this month"

### Requirement: Write-once monthly digest

The monthly digest SHALL be written once to `digests/monthly/digest-YYYY-MM.md`. A month that already has one SHALL not be synthesised again.

#### Scenario: Month run twice

- **WHEN** `monthly-digest` runs for a month that already has a digest
- **THEN** it skips synthesis and makes no prose calls

### Requirement: Sending to the board

With `--send`, and with mail, sending inbox and board address configured, the monthly digest SHALL be emailed to the board as text plus an HTML part, with the configured reply-to. Each month SHALL be sent at most once, and a month composed without `--send` SHALL be sendable later.

#### Scenario: Compose then send

- **WHEN** a month was composed without `--send` and the operator later runs it with `--send`
- **THEN** the recorded digest is emailed once
