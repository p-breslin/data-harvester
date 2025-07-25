from typing import Any, Dict, List

from agno.agent import Agent
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat
from agno.team import Team
from pydantic import BaseModel


def get_model(model_id: str):
    """Returns the correct model instance based on model_id prefix."""
    if "gemini" in model_id.lower():
        return Gemini(id=model_id)
    return OpenAIChat(id=model_id)


def create_agent(
    *,
    cfg: Dict[str, Any],
    tools: List[Any],
    response_model: BaseModel,
) -> Agent:
    """Creates a configured Agno agent from config dictionary.

    Args:
        cfg (Dict[str, Any]): agent configuration
        tools (List[Any]): list of tool instances
        response_model (BaseModel): Pydantic response schema

    Returns:
        Agent: configured Agno agent
    """
    model = get_model(cfg["model_id"])
    parser_model = get_model(cfg["parser_model_id"])

    return Agent(
        name=cfg["name"],
        role=cfg["role"],
        description=cfg["description"],
        instructions=cfg["instructions"],
        model=model,
        tools=tools,
        parser_model=parser_model,
        response_model=response_model,
        markdown=cfg.get("markdown", False),
    )


def create_team(
    *,
    cfg: Dict[str, Any],
    members: List[Agent],
    response_model: BaseModel,
) -> Team:
    """Creates a configured Agno Team from config dictionary.

    Args:
        cfg (Dict[str, Any]): team configuration
        members (List[Agent]): list of agents in the team
        response_model (BaseModel): target schema model

    Returns:
        Team: configured Agno Team
    """
    model = get_model(cfg["model_id"])

    return Team(
        name=cfg["name"],
        mode=cfg.get("mode", "coordinate"),
        model=model,
        members=members,
        instructions=cfg["instructions"],
        response_model=response_model,
        success_criteria=cfg["success_criteria"],
        show_tool_calls=cfg.get("show_tool_calls", True),
        show_members_responses=cfg.get("show_members_responses", True),
        markdown=cfg.get("markdown", False),
        debug_mode=cfg.get("debug_mode", True),
    )
