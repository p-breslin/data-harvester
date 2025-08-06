from typing import Dict, List

from pydantic import BaseModel, Field


class EdgePayload(BaseModel):
    to_node_type: str = Field(..., description="The type of the target node.")
    to_lookup_key: str = Field(
        ..., description="The unique key identifying the target node."
    )
    edge_type: str = Field(
        ..., description="The type or label of the edge relationship."
    )

    model_config = {"extra": "forbid"}


class NodePayload(BaseModel):
    node_type: str = Field(..., description="The type/category of the node.")
    sub_type: str = Field(
        ..., description="Secondary classification (e.g. Company, Product)"
    )
    lookup_key: str = Field(..., description="A unique identifier for this node.")
    data: Dict[str, str] = Field(
        ..., description="Structured key-value data representing the node's attributes."
    )
    edges: List[EdgePayload] = Field(
        default_factory=list, description="List of outgoing edges from this node."
    )

    model_config = {"extra": "forbid"}


class NodePayloadList(BaseModel):
    payloads: List[NodePayload] = Field(
        ..., description="List of node payloads to be inserted into the graph."
    )

    model_config = {"extra": "forbid"}
