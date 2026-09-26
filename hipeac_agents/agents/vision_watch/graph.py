"""LangGraph wiring for the vision-watch agent: harvest -> cluster -> digest."""

from functools import partial
from typing import Any

from langgraph.graph import START, StateGraph

from .nodes import cluster, digest, harvest, health, monthly
from .state import VisionWatchState


NODE_ORDER = ("harvest", "health", "cluster", "digest", "monthly")


def build_graph(nodes: list[str], services: Any, judgement_llm: Any, prose_llm: Any | None = None):
    """Build a StateGraph running the requested nodes in spec order.

    ``weekly-harvest`` runs ``["harvest", "health"]``; ``weekly-digest`` runs
    ``["cluster", "digest"]``. A node's service boundary is enforced by what
    it is wired with, not by what tools exist. Harvest runs on the judgement
    model; cluster and digest run on the prose model.

    :param nodes: The nodes to run, in order; subset of ``NODE_ORDER``.
    :param services: The wired service clients.
    :param judgement_llm: The chat model for the harvest's cheap judgement calls.
    :param prose_llm: The chat model for grouping and digest prose; defaults
        to the judgement model when not given.
    :returns: The compiled graph.
    """
    prose_llm = prose_llm or judgement_llm
    graph = StateGraph(VisionWatchState)

    for name in nodes:
        if name == "harvest":
            graph.add_node("harvest", partial(harvest.harvest_node, services=services, llm=judgement_llm))
        elif name == "health":
            graph.add_node("health", partial(health.health_node, services=services))
        elif name == "cluster":
            graph.add_node("cluster", partial(cluster.cluster_node, services=services, llm=prose_llm))
        elif name == "digest":
            graph.add_node("digest", partial(digest.digest_node, services=services, llm=prose_llm))
        elif name == "monthly":
            graph.add_node("monthly", partial(monthly.monthly_node, services=services, llm=prose_llm))
        else:
            raise ValueError(f"unknown node: {name}")

    graph.add_edge(START, nodes[0])

    for current, following in zip(nodes, nodes[1:], strict=False):
        graph.add_edge(current, following)

    graph.add_edge(nodes[-1], "__end__")
    return graph.compile()
