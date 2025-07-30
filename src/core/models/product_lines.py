from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DomainProducts(BaseModel):
    """Holds the company's root domain and a list of key product or service lines."""

    domain: str = Field(
        ..., description="The company's official website domain (e.g. apple.com)"
    )
    products: List[str] = Field(
        ...,
        description="Top N flagship product or service lines sold by the company, expressed in their most canonical, high-level form (e.g. 'iPhone', 'MacBook Pro', 'Apple Watch')",
    )


class ProductType(str, Enum):
    PRODUCT = "product"
    SERVICE = "service"
    BOTH = "product and service"


class ProductLine(BaseModel):
    """Represents a high-level product or service line offered by a company.

    Product lines are canonical brand categories (e.g., 'iPhone', 'Apple Watch') rather than specific SKUs or configurations.
    """

    name: str = Field(
        ...,
        description="The official name of the product or service line (e.g., 'iPhone', 'Apple Watch').",
    )
    type: Optional[ProductType] = Field(
        None,
        description="Specifies whether this line is primarily a product, a service, or both (product and service).",
    )
    description: Optional[str] = Field(
        None,
        description="Short summary of what the product or service line represents.",
    )
    category: Optional[str] = Field(
        None,
        description="Broad classification of the line (e.g., 'Smartphones', 'Wearables', 'Cloud Services').",
    )

    class Config:
        model_config = {
            "extra": "forbid",
            "json_schema_extra": {
                "examples": [
                    {
                        "name": "iPhone",
                        "type": "product",
                        "description": "Apple's smartphone product line.",
                        "category": "Smartphones",
                    }
                ]
            },
        }


class ProductLineList(BaseModel):
    """List of discovered product or service lines for a given company."""

    company_name: str = Field(
        ..., description="The name of the company these product lines belong to."
    )
    product_lines: List[ProductLine] = Field(
        default_factory=list,
        description="List of high-level product or service lines.",
    )


class SeededProductLine(BaseModel):
    """Represents a product or service line and its discovered official URL."""

    product_line: str = Field(
        ..., description="The name of the product or service line (e.g. 'iPhone')."
    )
    url: Optional[str] = Field(
        None,
        description="The official URL for the product line's landing page. May be null if no suitable URL was found.",
    )


class SeededProductLineList(BaseModel):
    """Container for seeded URLs for multiple product lines on a given domain."""

    domain: str = Field(
        ...,
        description="The root domain where the product line URLs were discovered (e.g. 'apple.com').",
    )
    results: List[SeededProductLine] = Field(
        ..., description="List of product lines and their associated URLs."
    )
