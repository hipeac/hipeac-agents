"""The cluster node's LLM judgement-call prompt."""

GROUPING_BAR = """\
You are grouping this week's findings into development clusters. A cluster is
a single ongoing development told over time — it must stay trackable for
weeks, so its id and name must be generic enough to keep receiving future
entries. You see ALL existing clusters across ALL themes, and ALL of this
week's findings: assign each finding to the cluster it extends, in whichever
theme that cluster lives — one cluster identity per development, never one
per theme. A finding may extend several clusters (in different themes) when
genuinely relevant to each; record it in each.

Rules for when to open a new cluster:
- Default to extending an existing cluster. A new cluster is justified only
  when no existing cluster covers the finding in one non-forced sentence.
- A cluster id must NOT be a news slug: no company names, no single-announcement
  wording. "box-ai-agent-security-governance" is wrong; "ai-agent-security" is
  right. If you cannot name the ongoing development the finding advances, it
  belongs in the closest existing cluster as context, or stays unmatched.
- New clusters must not duplicate an existing cluster's story under a new
  name or theme. Check the recent entries of every cluster before opening one.

Write the assignments only — the entry's descriptive text comes from the
finding's own summary, so do not restate it.
"""
