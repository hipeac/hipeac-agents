"""Structured-output models for the digest node's judgement call.

Paired with ``DIGEST_STORIES`` in ``prompts.py``.
"""

from pydantic import BaseModel, Field


class Story(BaseModel):
    """One story: what is moving in a theme, told in a few sentences."""

    theme: str = Field(description="Id of the theme the story belongs to")
    title: str = Field(description="A short title, 3-6 words, no markdown")
    text: str = Field(description="2-3 sentences; cite findings inline as [short phrase](F<n>)")


class StoryDigest(BaseModel):
    """The week's digest: a headline, a bottom line, and stories per theme."""

    headline: str = Field(description="The week's headline, at most 8 words, no markdown — the email subject")
    this_week: str = Field(
        description="2-3 sentences: the bottom line of the week, pointing to its most important development"
    )
    stories: list[Story] = Field(default=[], description="At most 2 stories per theme, strongest first")
