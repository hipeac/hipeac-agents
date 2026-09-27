"""LangGraph wiring for the vision-watch agent: harvest -> cluster -> digest."""

from functools import partial
from typing import Any

from langgraph.graph import START, StateGraph

from hipeac_agents.llms import Models

from .nodes import cluster, digest, harvest, health, monthly
from .state import VisionWatchState


NODE_ORDER = ("harvest", "health", "cluster", "digest", "monthly")


def build_graph(nodes: list[str], services: Any, models: Models):
    """Build a StateGraph running the requested nodes in spec order.

    ``weekly-harvest`` runs ``["harvest", "health"]``; ``weekly-digest`` runs
    ``["cluster", "digest"]``. A node's service boundary is enforced by what
    it is wired with, not by what tools exist. Harvest makes hundreds of
    classification calls and runs on the small model; clustering (one call a
    week) on the base model; the digests, which the board reads, on the
    thinking model.

    :param nodes: The nodes to run, in order; subset of ``NODE_ORDER``.
    :param services: The wired service clients.
    :param models: The chat models, one per tier.
    :returns: The compiled graph.
    """
    graph = StateGraph(VisionWatchState)

    for name in nodes:
        if name == "harvest":
            graph.add_node("harvest", partial(harvest.harvest_node, services=services, llm=models.small))
        elif name == "health":
            graph.add_node("health", partial(health.health_node, services=services))
        elif name == "cluster":
            graph.add_node("cluster", partial(cluster.cluster_node, services=services, llm=models.base))
        elif name == "digest":
            graph.add_node("digest", partial(digest.digest_node, services=services, llm=models.thinking))
        elif name == "monthly":
            graph.add_node("monthly", partial(monthly.monthly_node, services=services, llm=models.thinking))
        else:
            raise ValueError(f"unknown node: {name}")

    graph.add_edge(START, nodes[0])

    for current, following in zip(nodes, nodes[1:], strict=False):
        graph.add_edge(current, following)

    graph.add_edge(nodes[-1], "__end__")
    return graph.compile()
