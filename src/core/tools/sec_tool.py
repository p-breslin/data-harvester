import json
import logging
import os

from agno.tools import tool
from dotenv import load_dotenv
from edgar import Company, set_identity

from core.utils.logger import log_tools

log = logging.getLogger(__name__)
load_dotenv()


tool_name = "sec_profile_tool"


@tool(
    name=tool_name,
    description="Fetch the latest company profile from EDGAR by ticker",
    show_result=True,
)
def sec_tool(ticker: str) -> dict:
    """ticker: stock ticker symbol, e.g. 'AAPL'

    returns: dict with company metadata and latest revenue
    """
    sec_logs = log_tools("sec_tool")
    set_identity(os.getenv("EDGAR_IDENTITY"))
    company = Company(ticker)

    # If no facts at all, bail out early
    if not getattr(company, "facts", None):
        return {"error": "No financial facts available for this company"}

    # Try to fetch the latest revenue
    latest_revenue = None
    try:
        rev = (
            company.facts.query()
            .by_concept("Revenue")
            .sort_by("period_end", ascending=False)
            .latest(1)
        )
        if rev:
            latest_revenue = rev[0]
        else:
            log.warning("No revenue data found for %s", ticker)
    except Exception as e:
        log.error("Could not retrieve revenue data for %s: %s", ticker, e)

    # Pick best address available
    address = None
    for attr in ("business_address", "mailing_address"):
        addr = getattr(company.data, attr, None)
        if addr:
            address = f"{addr.city}, {addr.state_or_country_desc}"
            break

    profile = {
        "company_name": company.data.name,
        "ticker": company.get_ticker(),
        "cik": company.cik,
        "industry": company.industry,
        "location": address or "N/A",
        "sic_code": company.sic,
        "fiscal_year_end": company.fiscal_year_end,
        "exchanges": company.get_exchanges(),
        "shares_outstanding": company.shares_outstanding,
        "public_float": company.public_float,
        "latest_revenue": (
            f"${latest_revenue.numeric_value:,.0f} ({latest_revenue.period_end})"
            if latest_revenue
            else "N/A"
        ),
    }
    sec_logs.debug(json.dumps({"Company profile": profile}, indent=2, default=str))
    return profile
