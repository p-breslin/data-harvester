import pandas as pd
from edgar import Company, set_identity


def main(save_profile=False):
    # Required: Set your identity for SEC API access
    set_identity("peter.breslin@experienceflow.ai")

    # Get Apple company object
    print("Fetching Apple Inc. company data...")
    company = Company("AAPL")

    # Display basic company information
    print_basic_info(company)

    # Get and display financial facts
    print_financial_facts(company)

    # Get financial statements
    print_financial_statements(company)

    # Generate summary profile
    generate_company_profile(company, save_profile=save_profile)


def print_basic_info(company):
    """Print basic company information"""
    print("\n" + "=" * 60)
    print("BASIC COMPANY INFORMATION")
    print("=" * 60)

    print(f"Name: {company.data.name}")
    print(f"CIK: {company.cik}")
    print(f"Ticker: {company.get_ticker()}")
    print(f"Industry: {company.industry}")

    # Website
    website = getattr(company.data, "website", None) or getattr(
        company.data, "investor_website", None
    )
    if website:
        print(f"Website: {website}")

    # Location
    if hasattr(company.data, "business_address") and company.data.business_address:
        location = f"{company.data.business_address.city}, {company.data.business_address.state_or_country_desc}"
    elif hasattr(company.data, "mailing_address") and company.data.mailing_address:
        location = f"{company.data.mailing_address.city}, {company.data.mailing_address.state_or_country_desc}"
    else:
        location = None
    if location:
        print(f"Location: {location}")

    print(f"SIC Code: {company.sic}")
    print(f"Fiscal Year End: {company.fiscal_year_end}")
    print(f"Exchange: {company.get_exchanges()}")


def print_financial_facts(company):
    """Print key financial facts using the Facts API"""
    print("\n" + "=" * 60)
    print("KEY FINANCIAL METRICS")
    print("=" * 60)

    # Check if facts are available
    if not company.facts:
        print("No financial facts available for this company")
        return

    facts = company.facts

    # Get shares outstanding
    shares = company.shares_outstanding
    if shares:
        print(f"Shares Outstanding: {shares:,.0f}")

    # Get public float
    public_float = company.public_float
    if public_float:
        print(f"Public Float: ${public_float:,.0f}")

    # Get entity information
    entity_info = facts.entity_info()
    print(f"Entity Name: {entity_info.get('entity_name', 'N/A')}")

    # Query for revenue data
    try:
        revenue_facts = (
            facts.query()
            .by_concept("Revenue")
            .sort_by("period_end", ascending=False)
            .latest(1)
        )
        if revenue_facts:
            latest_revenue = revenue_facts[0]
            print(
                f"Latest Revenue: ${latest_revenue.numeric_value:,.0f} ({latest_revenue.period_end})"
            )
        else:
            print("No revenue data found")
    except Exception as e:
        print(f"Could not retrieve revenue data: {e}")


def print_financial_statements(company):
    """Print financial statement summaries using Company methods"""
    print("\n" + "=" * 60)
    print("FINANCIAL STATEMENTS SUMMARY")
    print("=" * 60)

    try:
        # Use company's built-in methods
        income_stmt = company.income_statement(periods=4)
        if income_stmt:
            print("\nIncome Statement:")
            print(income_stmt)

        balance_sheet = company.balance_sheet(periods=2)
        if balance_sheet:
            print("\nBalance Sheet:")
            print(balance_sheet)

    except Exception as e:
        print(f"Error retrieving financial statements: {e}")


def generate_company_profile(company, save_profile=False):
    """Generate a comprehensive company profile summary"""
    print("\n" + "=" * 60)
    print("COMPANY PROFILE SUMMARY")
    print("=" * 60)

    # Website - aligned with print_basic_info
    website = getattr(company.data, "website", None) or getattr(
        company.data, "investor_website", None
    )

    # Location - aligned with print_basic_info
    location = None
    if hasattr(company.data, "business_address") and company.data.business_address:
        location = f"{company.data.business_address.city}, {company.data.business_address.state_or_country_desc}"
    elif hasattr(company.data, "mailing_address") and company.data.mailing_address:
        location = f"{company.data.mailing_address.city}, {company.data.mailing_address.state_or_country_desc}"

    profile = {
        "Company Name": company.data.name,
        "Stock Ticker": company.get_ticker(),
        "CIK": company.cik,
        "Industry": company.industry,
        "Location": location if location else "N/A",
        "Website": website if website else "N/A",
        "Exchange": company.get_exchanges(),
        "Shares Outstanding": company.shares_outstanding,
        "Public Float": company.public_float,
        "Has Financial Facts": company.facts is not None,
    }

    # Print profile as formatted table
    for key, value in profile.items():
        if value is not None and value != "N/A":
            if isinstance(value, float) and value > 1000:
                print(f"{key:<20}: {value:,.0f}")
            else:
                print(f"{key:<20}: {value}")

    if save_profile:
        # Save to CSV for further analysis
        try:
            df = pd.DataFrame([profile])
            df.to_csv("apple_company_profile.csv", index=False)
            print("\nCompany profile saved to: apple_company_profile.csv")
        except Exception as e:
            print(f"Could not save to CSV: {e}")


if __name__ == "__main__":
    main(save_profile=False)
