from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from core.models.metadata import Metadata


class ProductType(str, Enum):
    PRODUCT = "product"
    SERVICE = "service"
    BOTH = "both"


class Product(Metadata):
    """Represents a single product offered by a company.

    This schema is designed to capture core product information scraped from a web page.
    """

    name: str = Field(..., description="The official name of the product.")
    type: Optional[ProductType] = Field(
        None,
        description="Specifies whether the offering is a physical product, service, or both.",
    )
    description: Optional[str] = Field(
        None, description="Short summary of what the product/service is or does."
    )
    category: Optional[str] = Field(
        None,
        description="Primary category or classification (e.g., Smartphones, Computers).",
    )
    sku: Optional[str] = Field(
        None,
        description="The Stock Keeping Unit (SKU) or other unique product identifier used by the vendor.",
    )
    price: Optional[float] = Field(
        None,
        description="The numerical price of the product/service, excluding currency symbols.",
        gt=0,
    )
    currency: Optional[str] = Field(
        None,
        description="The currency of the price (e.g., USD, EUR, JPY).",
        max_length=3,
    )

    class Config:
        model_config = {
            "extra": "forbid",
            "json_schema_extra": {
                "examples": [
                    {
                        "name": "iPhone 12",
                        "type": "product",
                        "description": "Apple's 12th-generation smartphone featuring 5G, dual-camera system, and A14 Bionic chip.",
                        "category": "Smartphones",
                        "sku": "APL-IP12-BLK-64GB",
                        "price": 799.00,
                        "currency": "USD",
                        "source_url": "https://www.apple.com/iphone-12/",
                        "source_name": "Apple",
                        "scraped_at": "2025-07-19T16:30:00Z",
                    }
                ]
            },
        }


class ProductList(BaseModel):
    """List of discovered product information."""

    results: List[Product] = Field(
        default_factory=list,
        description="List of discovered product information.",
    )
    source_domain: Optional[str] = Field(
        None,
        description="The domain from which this batch of product data was extracted.",
    )
