#!/usr/bin/env python3
"""
Congress Trade Tracker - Data Seeder
Popula o database com dados de exemplo pra testar o dashboard
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))

from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import (
    Politician, Trade, OptionsTrade, Company, 
    get_engine, get_session, init_db
)

# Sample politicians
POLITICIANS = [
    {"name": "Nancy Pelosi", "chamber": "house", "party": "D", "state": "CA"},
    {"name": "Paul Pelosi", "chamber": "house", "party": "D", "state": "CA"},
    {"name": "Dan Crenshaw", "chamber": "house", "party": "R", "state": "TX"},
    {"name": "Ro Khanna", "chamber": "house", "party": "D", "state": "CA"},
    {"name": "Tommy Tuberville", "chamber": "senate", "party": "R", "state": "AL"},
    {"name": "Richard Burr", "chamber": "senate", "party": "R", "state": "NC"},
    {"name": "Dianne Feinstein", "chamber": "senate", "party": "D", "state": "CA"},
    {"name": "David Perdue", "chamber": "senate", "party": "R", "state": "GA"},
    {"name": "John Hickenlooper", "chamber": "senate", "party": "D", "state": "CO"},
    {"name": "Mark Kelly", "chamber": "senate", "party": "D", "state": "AZ"},
    {"name": "Ted Cruz", "chamber": "senate", "party": "R", "state": "TX"},
    {"name": "Josh Hawley", "chamber": "senate", "party": "R", "state": "MO"},
    {"name": "Alexandria Ocasio-Cortez", "chamber": "house", "party": "D", "state": "NY"},
    {"name": "Kevin McCarthy", "chamber": "house", "party": "R", "state": "CA"},
    {"name": "Mitch McConnell", "chamber": "senate", "party": "R", "state": "KY"},
]

# Sample stocks with sectors
STOCKS = [
    {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics"},
    {"ticker": "MSFT", "name": "Microsoft Corp", "sector": "Technology", "industry": "Software"},
    {"ticker": "GOOGL", "name": "Alphabet Inc.", "sector": "Technology", "industry": "Internet"},
    {"ticker": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer Cyclical", "industry": "E-Commerce"},
    {"ticker": "NVDA", "name": "NVIDIA Corp", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "META", "name": "Meta Platforms", "sector": "Technology", "industry": "Social Media"},
    {"ticker": "TSLA", "name": "Tesla Inc.", "sector": "Consumer Cyclical", "industry": "Auto Manufacturers"},
    {"ticker": "JPM", "name": "JPMorgan Chase", "sector": "Financial Services", "industry": "Banking"},
    {"ticker": "JNJ", "name": "Johnson & Johnson", "sector": "Healthcare", "industry": "Pharmaceuticals"},
    {"ticker": "V", "name": "Visa Inc.", "sector": "Financial Services", "industry": "Credit Services"},
    {"ticker": "PG", "name": "Procter & Gamble", "sector": "Consumer Defensive", "industry": "Household Products"},
    {"ticker": "UNH", "name": "UnitedHealth Group", "sector": "Healthcare", "industry": "Health Insurance"},
    {"ticker": "HD", "name": "Home Depot", "sector": "Consumer Cyclical", "industry": "Home Improvement"},
    {"ticker": "BAC", "name": "Bank of America", "sector": "Financial Services", "industry": "Banking"},
    {"ticker": "XOM", "name": "Exxon Mobil", "sector": "Energy", "industry": "Oil & Gas"},
    {"ticker": "PFE", "name": "Pfizer Inc.", "sector": "Healthcare", "industry": "Pharmaceuticals"},
    {"ticker": "ABBV", "name": "AbbVie Inc.", "sector": "Healthcare", "industry": "Pharmaceuticals"},
    {"ticker": "COST", "name": "Costco Wholesale", "sector": "Consumer Defensive", "industry": "Retail"},
    {"ticker": "DIS", "name": "Walt Disney Co", "sector": "Communication Services", "industry": "Entertainment"},
    {"ticker": "NFLX", "name": "Netflix Inc.", "sector": "Communication Services", "industry": "Entertainment"},
    {"ticker": "CRM", "name": "Salesforce Inc.", "sector": "Technology", "industry": "Software"},
    {"ticker": "AMD", "name": "Advanced Micro Devices", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "INTC", "name": "Intel Corp", "sector": "Technology", "industry": "Semiconductors"},
    {"ticker": "PYPL", "name": "PayPal Holdings", "sector": "Financial Services", "industry": "Credit Services"},
    {"ticker": "SQ", "name": "Block Inc.", "sector": "Financial Services", "industry": "Credit Services"},
]

# Value ranges (in dollars)
VALUE_RANGES = [
    (1001, 15000),
    (15001, 50000),
    (50001, 100000),
    (100001, 250000),
    (250001, 500000),
    (500001, 1000000),
    (1000001, 5000000),
    (5000001, 25000000),
    (25000001, 50000000),
]

def seed_database():
    """Seed database with sample data"""
    print("🌱 Seeding database with sample data...")
    
    # Initialize database
    engine = get_engine(settings.DATABASE_URL)
    init_db(settings.DATABASE_URL)
    session = get_session(engine)
    
    # Clear existing data
    session.query(OptionsTrade).delete()
    session.query(Trade).delete()
    session.query(Company).delete()
    session.query(Politician).delete()
    session.commit()
    
    # Add companies
    print("📊 Adding companies...")
    for stock in STOCKS:
        company = Company(
            ticker=stock["ticker"],
            name=stock["name"],
            sector=stock["sector"],
            industry=stock["industry"],
            market_cap=random.uniform(10e9, 3e12),
            beta=random.uniform(0.5, 2.0),
            last_updated=datetime.utcnow(),
        )
        session.add(company)
    session.commit()
    print(f"  ✅ Added {len(STOCKS)} companies")
    
    # Add politicians
    print("👤 Adding politicians...")
    politicians = []
    for pol_data in POLITICIANS:
        politician = Politician(
            name=pol_data["name"],
            chamber=pol_data["chamber"],
            party=pol_data["party"],
            state=pol_data["state"],
            active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(politician)
        politicians.append(politician)
    session.commit()
    print(f"  ✅ Added {len(politicians)} politicians")
    
    # Add trades
    print("📈 Adding trades...")
    trade_count = 0
    option_count = 0
    
    for politician in politicians:
        # Each politician gets 5-30 random trades
        num_trades = random.randint(5, 30)
        
        for _ in range(num_trades):
            stock = random.choice(STOCKS)
            value_range = random.choice(VALUE_RANGES)
            trade_type = random.choice(["buy", "buy", "buy", "sell", "sell", "exchange"])
            
            # Random date in last 2 years (never in future)
            days_ago = random.randint(2, 730)
            trade_date = datetime.now() - timedelta(days=days_ago)
            
            # Filing date is 15-45 days after trade, never exceeding current date
            filing_delay = random.randint(15, 45)
            filing_date = min(datetime.now(), trade_date + timedelta(days=filing_delay))
            if filing_date < trade_date:
                filing_date = trade_date
            
            trade = Trade(
                politician_id=politician.id,
                ticker=stock["ticker"],
                asset_name=stock["name"],
                asset_type="stock",
                transaction_type=trade_type,
                trade_date=trade_date.date(),
                filing_date=filing_date.date(),
                value_min=value_range[0],
                value_max=value_range[1],
                value_range=f"${value_range[0]:,} - ${value_range[1]:,}",
                report_type="Periodic Transaction Report",
                notes=f"Sample trade for {politician.name}",
                created_at=datetime.utcnow(),
            )
            session.add(trade)
            session.flush()
            trade_count += 1
            
            # 30% chance of options trade
            if random.random() < 0.3:
                option_type = random.choice(["call", "put"])
                strike = random.uniform(50, 500)
                expiration = trade_date + timedelta(days=random.randint(30, 365))
                
                option = OptionsTrade(
                    trade_id=trade.id,
                    option_type=option_type,
                    strike=round(strike, 2),
                    expiration_date=expiration.date(),
                    contracts_min=random.randint(1, 10),
                    contracts_max=random.randint(10, 100),
                    premium_min=value_range[0],
                    premium_max=value_range[1],
                    premium_range=f"${value_range[0]:,} - ${value_range[1]:,}",
                    underlying_asset=stock["ticker"],
                    notes=f"Sample {option_type} option",
                )
                session.add(option)
                option_count += 1
    
    session.commit()
    print(f"  ✅ Added {trade_count} trades")
    print(f"  ✅ Added {option_count} options trades")
    
    session.close()
    
    print(f"\n{'='*60}")
    print(f"✅ Database seeded successfully!")
    print(f"   Politicians: {len(politicians)}")
    print(f"   Companies: {len(STOCKS)}")
    print(f"   Trades: {trade_count}")
    print(f"   Options: {option_count}")
    print(f"{'='*60}")

if __name__ == "__main__":
    seed_database()
