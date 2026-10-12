## MODIFIED Requirements

### Requirement: Digest layout

The digest SHALL contain, in order: a title "HiPEAC Vision Watch — Week <week>: <headline>" (headline at most 8 words); a bottom line of one paragraph, 3-4 sentences, on the 2-3 open questions that moved most this week and which way, each sentence leading with what changed rather than the question's wording, without hedges, citing 1-2 findings for each; the theme sections; "Board tips", when any; "Newly converged", when any; one line naming the quiet themes; and a closing line with the number of stories, of short items and of the week's findings, naming the signals log.

#### Scenario: A normal week

- **WHEN** three themes have stories, one of them a new topic, and one board tip was verified
- **THEN** the digest shows the bottom line, three theme sections with each story's tag, the tip, the quiet themes in one line and the closing count

#### Scenario: Bottom line links its evidence

- **WHEN** the bottom line says new findings show that parsing can undermine agent oversight, citing that finding
- **THEN** the phrase stating it links to that finding's URL

### Requirement: Links only to findings

The prose call SHALL cite findings only by id, in the stories and in the bottom line. Only citations of findings it was given SHALL become links. An unknown id, or any link to a URL it was not given, keeps its words without a link. A bare citation becomes a link on the source's domain. A story that cites no finding SHALL be dropped. A bottom line that cites no finding SHALL still be printed.

#### Scenario: Invented link

- **WHEN** a story or the bottom line contains a markdown link to a URL that is not one of the week's findings
- **THEN** the words stay and the link is removed

#### Scenario: Story without evidence

- **WHEN** a story cites no finding
- **THEN** it is not printed

#### Scenario: Bottom line without evidence

- **WHEN** the bottom line cites no finding
- **THEN** it is printed without links

### Requirement: Write-once digest

The digest SHALL be written once to `digests/weekly/digest-<week>.md`. A week that already has a digest SHALL not be recomposed. The only in-place change allowed SHALL be an intro-only rewrite of its bottom line.

#### Scenario: Digest run twice

- **WHEN** `weekly-digest` runs for a week that already has a digest
- **THEN** it prints "already has a digest; skipping composition" and makes no prose calls

## ADDED Requirements

### Requirement: Rewriting the bottom line

`weekly-digest --on <date> --intro-only` SHALL rewrite only the bottom line of the week's recorded digest. The prose call SHALL be given the week's candidate stories, rebuilt from the cluster logs as for composition, and the printed digest, and SHALL return only the bottom line, under the same rules and link guard as at composition. Before the digest is changed, it SHALL be copied to `_backup/<week>-<timestamp>/`. The title, sections, closing line, ledger, signals log and sent marker SHALL stay unchanged, and nothing SHALL be emailed. The flag SHALL be refused with `--send` or `--redo`. A week without a digest SHALL fail, naming the command to compose it. A week with no candidate stories SHALL be left unchanged without a prose call.

#### Scenario: Past week rewritten

- **WHEN** the operator runs `weekly-digest --on 2026-09-25 --intro-only` and W39 has a digest
- **THEN** the W39 bottom line is replaced by a cited 3-4 sentence one, the previous digest is in `_backup/2026-W39-<timestamp>/`, and every other line of the digest is unchanged

#### Scenario: Sent week rewritten

- **WHEN** the rewritten week's digest was already sent
- **THEN** its sent marker stays and no email is sent

#### Scenario: Combined with send

- **WHEN** the operator runs `weekly-digest --intro-only --send`
- **THEN** the run exits with a usage error and nothing is changed

#### Scenario: No digest yet

- **WHEN** the operator runs `--intro-only` for a week with no digest
- **THEN** the run fails, naming `weekly-digest` to compose it, and makes no prose call

#### Scenario: Quiet week

- **WHEN** the week has no candidate stories
- **THEN** the digest is left unchanged and no prose call is made
