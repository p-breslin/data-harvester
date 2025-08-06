from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class LatestRevenue(BaseModel):
    """Most-recent reported revenue for the company."""

    numeric_value: float = Field(
        ...,
        description="Revenue amount in USD.",
        example=394_328_000_000.0,
    )
    period_end: date = Field(
        ...,
        description="The end date of the revenue period (YYYY-MM-DD).",
        example="2023-09-30",
    )

    class Config:
        model_config = {
            "extra": "forbid",
            "json_schema_extra": {
                "examples": [
                    {"numeric_value": 394_328_000_000.0, "period_end": "2023-09-30"}
                ]
            },
        }


class CompanyProfile(BaseModel):
    """High-level company profile including identifiers, classification, and key metrics."""

    company_name: str = Field(
        ...,
        description="Official company name (e.g., 'Apple Inc.').",
        example="Apple Inc.",
    )
    ticker: str = Field(
        ...,
        description="Stock ticker symbol (e.g., 'AAPL').",
        example="AAPL",
    )
    cik: str = Field(
        ...,
        description="SEC Central Index Key.",
        example="0000320193",
    )
    industry: Optional[str] = Field(
        None,
        description="Industry classification.",
        example="Technology Hardware, Storage & Peripherals",
    )
    location: Optional[str] = Field(
        None,
        description="Headquarters location (city, state or country).",
        example="Cupertino, CA",
    )
    website: Optional[str] = Field(
        None,
        description="Official company website URL.",
        example="https://www.apple.com/",
    )
    sic_code: Optional[str] = Field(
        None,
        description="Standard Industrial Classification code.",
        example="3571",
    )
    fiscal_year_end: Optional[str] = Field(
        None,
        description="Fiscal year-end date (YYYY-MM-DD).",
        example="2023-09-30",
    )
    exchanges: Optional[List[str]] = Field(
        None,
        description="List of exchanges where the stock is listed.",
        example=["NASDAQ"],
    )
    shares_outstanding: Optional[int] = Field(
        None,
        description="Total shares outstanding.",
        example=15_728_600_000,
    )
    public_float: Optional[int] = Field(
        None,
        description="Shares available to public investors.",
        example=15_686_400_000,
    )
    latest_revenue: Optional[LatestRevenue] = Field(
        None, description="Structured latest revenue data."
    )

    class Config:
        model_config = {
            "extra": "forbid",
            "json_schema_extra": {
                "examples": [
                    {
                        "company_name": "Apple Inc.",
                        "ticker": "AAPL",
                        "cik": "0000320193",
                        "industry": "Technology Hardware, Storage & Peripherals",
                        "location": "Cupertino, CA",
                        "sic_code": "3571",
                        "fiscal_year_end": "2023-09-30",
                        "exchanges": ["NASDAQ"],
                        "shares_outstanding": 15728600000,
                        "public_float": 15686400000,
                        "latest_revenue": {
                            "numeric_value": 394328000000.0,
                            "period_end": "2023-09-30",
                        },
                    }
                ]
            },
        }
