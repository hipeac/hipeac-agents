## MODIFIED Requirements

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
