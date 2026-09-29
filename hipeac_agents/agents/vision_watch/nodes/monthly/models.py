"""Structured-output models for the monthly digest node's judgement call.

Paired with ``MONTHLY_QUESTIONS`` in ``prompts.py``. The id fields are
narrowed per run by ``monthly_model`` to the ids that passed the gate.
"""

from typing import Literal

from pydantic import BaseModel, Field, create_model


class QuestionAnswer(BaseModel):
    """Where one open question stands after the month's evidence."""

    question: str = Field(description="The id of the qualifying open question, e.g. agentic-ai.1")
    lean: str = Field(description="2-5 words: which way the month's evidence pushes the answer")
    evidence: str = Field(
        description="2-4 sentences: what the signals show together, weeks named only when the order matters. "
        "Cite signals inline as [short phrase](F<n>)"
    )
    for_2027: str = Field(description="1-2 sentences: a draft position the 2027 Vision could take")
    still_open: str = Field(description="One sentence: what the board would most need to know next")


class NewTopic(BaseModel):
    """A qualifying topic outside the open questions, proposed to the board."""

    topic: str = Field(description="The qualifying topic's key, e.g. T1")
    title: str = Field(description="A short title, 3-6 words, sentence case, no markdown")
    evidence: str = Field(
        description="1-3 sentences: the evidence across the weeks. Cite signals inline as [short phrase](F<n>)"
    )
    proposed_question: str = Field(description="An open question the board could add, as one sentence")


class MonthlyDigest(BaseModel):
    """The month's digest: a bottom line, then where each qualifying question and topic stands."""

    bottom_line: str = Field(description="2-3 sentences: the most settled answers and the biggest surprise")
    answers: list[QuestionAnswer] = Field(default=[], description="One per qualifying question")
    new_topics: list[NewTopic] = Field(
        default=[], description="One per qualifying topic whose signals share one development"
    )


def _narrowed[M: BaseModel](model: type[M], field: str, ids: list[str]) -> type[M]:
    if not ids:
        return model
    kind = Literal[tuple(ids)]
    return create_model(model.__name__, __base__=model, **{field: (kind, model.model_fields[field])})


def monthly_model(question_ids: list[str], topic_keys: list[str]) -> type[MonthlyDigest]:
    """Build the month's output model, its ids restricted to the qualifying ones.

    An id field typed as free text came back holding question texts, which
    code then dropped; a ``Literal`` keeps the model on the given ids.

    :param question_ids: The qualifying question ids.
    :param topic_keys: The qualifying NEW topics' keys.
    :returns: A ``MonthlyDigest`` subclass.
    """
    answer = _narrowed(QuestionAnswer, "question", question_ids)
    topic = _narrowed(NewTopic, "topic", topic_keys)
    return create_model(
        MonthlyDigest.__name__,
        __base__=MonthlyDigest,
        answers=(list[answer], MonthlyDigest.model_fields["answers"]),
        new_topics=(list[topic], MonthlyDigest.model_fields["new_topics"]),
    )
