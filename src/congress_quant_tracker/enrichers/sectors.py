"""Shared ticker → sector map used by scoring, terminal desk, and enrich jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

# Yahoo-style GICS-ish labels. Keep values stable — scorer committee map
# expects Healthcare / Information Technology / Financial Services / Energy / etc.
# We store a short desk label on Trade.sector and normalize at score time.
TICKER_SECTOR: dict[str, str] = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "GOOGL": "Technology",
    "GOOG": "Technology", "META": "Technology", "AMZN": "Technology", "AMD": "Technology",
    "AVGO": "Technology", "TSM": "Technology", "ASML": "Technology", "ORCL": "Technology",
    "CRM": "Technology", "PLTR": "Technology", "MU": "Technology", "INTC": "Technology",
    "TSLA": "Technology", "NFLX": "Technology", "ADBE": "Technology", "CSCO": "Technology",
    "QCOM": "Technology", "IBM": "Technology", "NOW": "Technology", "SNOW": "Technology",
    "PANW": "Technology", "CRWD": "Technology", "NET": "Technology", "SHOP": "Technology",
    "AMAT": "Technology", "LRCX": "Technology", "KLAC": "Technology", "SNPS": "Technology",
    "CDNS": "Technology", "ANSS": "Technology", "INTU": "Technology", "ADP": "Technology",
    "ACN": "Technology", "TXN": "Technology", "ADI": "Technology", "AMZN": "Technology",
    "UBER": "Technology", "ABNB": "Technology", "SQ": "Technology", "COIN": "Technology",
    "HOOD": "Technology", "SMCI": "Technology", "ARM": "Technology", "DELL": "Technology",
    "HPQ": "Technology", "HPE": "Technology", "SAP": "Technology", "SONY": "Technology",
    "APP": "Technology", "DDOG": "Technology", "ZS": "Technology", "OKTA": "Technology",
    "FTNT": "Technology", "TEAM": "Technology", "WDAY": "Technology", "ADSK": "Technology",
    "KEYS": "Technology", "MCHP": "Technology", "NXPI": "Technology", "ON": "Technology",
    "MRVL": "Technology", "ARM": "Technology", "GFS": "Technology", "ANET": "Technology",
    "MSTR": "Technology", "RBLX": "Technology", "U": "Technology", "PATH": "Technology",
    "S": "Technology", "ESTC": "Technology", "MDB": "Technology", "CFLT": "Technology",
    "BABA": "Technology", "JD": "Technology", "PDD": "Technology", "BIDU": "Technology",
    "TCEHY": "Technology", "NTES": "Technology", "SE": "Technology", "GRAB": "Technology",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy", "EOG": "Energy",
    "OXY": "Energy", "MPC": "Energy", "PSX": "Energy", "VLO": "Energy", "KMI": "Energy",
    "WMB": "Energy", "HAL": "Energy", "BKR": "Energy", "DVN": "Energy", "FANG": "Energy",
    "OKE": "Energy", "HES": "Energy", "PXD": "Energy", "APA": "Energy", "CTRA": "Energy",
    "TRGP": "Energy", "LNG": "Energy", "EQT": "Energy", "AR": "Energy", "RRC": "Energy",
    "ENB": "Energy", "SU": "Energy", "CNQ": "Energy", "PBR": "Energy", "E": "Energy",
    "BP": "Energy", "SHEL": "Energy", "TTE": "Energy", "EQNR": "Energy",
    # Financials
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials", "MS": "Financials",
    "WFC": "Financials", "BLK": "Financials", "V": "Financials", "MA": "Financials",
    "AXP": "Financials", "C": "Financials", "SCHW": "Financials", "PYPL": "Financials",
    "BRK.B": "Financials", "BRKB": "Financials", "BRK-B": "Financials", "USB": "Financials",
    "PNC": "Financials", "COF": "Financials", "TFC": "Financials", "SPGI": "Financials",
    "BK": "Financials", "MET": "Financials", "PRU": "Financials", "AIG": "Financials",
    "AFL": "Financials", "ALL": "Financials", "PGR": "Financials", "TRV": "Financials",
    "CB": "Financials", "MMC": "Financials", "AON": "Financials", "ICE": "Financials",
    "CME": "Financials", "MCO": "Financials", "MSCI": "Financials", "TROW": "Financials",
    "BX": "Financials", "KKR": "Financials", "APO": "Financials", "CG": "Financials",
    "SOFI": "Financials", "AFRM": "Financials", "NU": "Financials", "IBKR": "Financials",
    "RJF": "Financials", "AMP": "Financials", "BEN": "Financials", "IVZ": "Financials",
    # Healthcare
    "UNH": "Healthcare", "JNJ": "Healthcare", "LLY": "Healthcare", "PFE": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "TMO": "Healthcare", "ABT": "Healthcare",
    "DHR": "Healthcare", "BMY": "Healthcare", "AMGN": "Healthcare", "GILD": "Healthcare",
    "ISRG": "Healthcare", "SYK": "Healthcare", "MDT": "Healthcare", "BSX": "Healthcare",
    "VRTX": "Healthcare", "REGN": "Healthcare", "MRNA": "Healthcare", "BNTX": "Healthcare",
    "CVS": "Healthcare", "CI": "Healthcare", "ELV": "Healthcare", "HUM": "Healthcare",
    "CNC": "Healthcare", "MOH": "Healthcare", "HCA": "Healthcare", "THC": "Healthcare",
    "DXCM": "Healthcare", "IDXX": "Healthcare", "IQV": "Healthcare", "A": "Healthcare",
    "EW": "Healthcare", "ZBH": "Healthcare", "ALGN": "Healthcare", "PODD": "Healthcare",
    "OPCH": "Healthcare", "STE": "Healthcare", "RMD": "Healthcare", "BAX": "Healthcare",
    "ZTS": "Healthcare", "ELAN": "Healthcare", "WST": "Healthcare", "TECH": "Healthcare",
    "INCY": "Healthcare", "BIIB": "Healthcare", "ALNY": "Healthcare", "ARGX": "Healthcare",
    # Consumer
    "HD": "Consumer", "WMT": "Consumer", "COST": "Consumer", "MCD": "Consumer",
    "NKE": "Consumer", "SBUX": "Consumer", "TGT": "Consumer", "LOW": "Consumer",
    "TJX": "Consumer", "DG": "Consumer", "DLTR": "Consumer", "ROST": "Consumer",
    "ORLY": "Consumer", "AZO": "Consumer", "CMG": "Consumer", "YUM": "Consumer",
    "DPZ": "Consumer", "DRI": "Consumer", "BKNG": "Consumer", "MAR": "Consumer",
    "HLT": "Consumer", "DAL": "Consumer", "UAL": "Consumer", "AAL": "Consumer",
    "LUV": "Consumer", "RCL": "Consumer", "CCL": "Consumer", "NCLH": "Consumer",
    "GM": "Consumer", "F": "Consumer", "TM": "Consumer", "HMC": "Consumer",
    "LTH": "Consumer", "DIS": "Consumer", "CMCSA": "Consumer", "NFLX": "Technology",
    "PARA": "Consumer", "WBD": "Consumer", "FOX": "Consumer", "NWSA": "Consumer",
    "PG": "Consumer", "KO": "Consumer", "PEP": "Consumer", "PM": "Consumer",
    "MO": "Consumer", "CL": "Consumer", "KMB": "Consumer", "GIS": "Consumer",
    "KHC": "Consumer", "MDLZ": "Consumer", "HSY": "Consumer", "STZ": "Consumer",
    "EL": "Consumer", "CLX": "Consumer", "CHD": "Consumer", "KR": "Consumer",
    "SYY": "Consumer", "ADM": "Consumer", "BG": "Consumer", "TSN": "Consumer",
    # Industrials
    "BA": "Industrials", "CAT": "Industrials", "GE": "Industrials", "HON": "Industrials",
    "LMT": "Industrials", "RTX": "Industrials", "UPS": "Industrials", "UNP": "Industrials",
    "CSX": "Industrials", "NSC": "Industrials", "FDX": "Industrials", "DE": "Industrials",
    "MMM": "Industrials", "EMR": "Industrials", "ETN": "Industrials", "ITW": "Industrials",
    "PH": "Industrials", "ROK": "Industrials", "CMI": "Industrials", "PCAR": "Industrials",
    "GD": "Industrials", "NOC": "Industrials", "LHX": "Industrials", "HII": "Industrials",
    "TDG": "Industrials", "AXON": "Industrials", "HEI": "Industrials", "TXT": "Industrials",
    "CHRW": "Industrials", "ODFL": "Industrials", "XPO": "Industrials", "JBHT": "Industrials",
    "WM": "Industrials", "RSG": "Industrials", "URI": "Industrials", "GWW": "Industrials",
    "FAST": "Industrials", "CTAS": "Industrials", "CPRT": "Industrials", "VRSK": "Industrials",
    "GEV": "Industrials", "CARR": "Industrials", "OTIS": "Industrials", "IR": "Industrials",
    # Materials
    "LIN": "Materials", "APD": "Materials", "SHW": "Materials", "ECL": "Materials",
    "FCX": "Materials", "NEM": "Materials", "GOLD": "Materials", "NUE": "Materials",
    "STLD": "Materials", "VMC": "Materials", "MLM": "Materials", "DD": "Materials",
    "DOW": "Materials", "PPG": "Materials", "ALB": "Materials", "SQM": "Materials",
    "VALE": "Materials", "RIO": "Materials", "BHP": "Materials", "SCCO": "Materials",
    # Utilities / Real Estate / Comm
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities", "D": "Utilities",
    "AEP": "Utilities", "EXC": "Utilities", "SRE": "Utilities", "XEL": "Utilities",
    "AMT": "Real Estate", "PLD": "Real Estate", "CCI": "Real Estate", "EQIX": "Real Estate",
    "SPG": "Real Estate", "O": "Real Estate", "WELL": "Real Estate", "DLR": "Real Estate",
    "T": "Communication Services", "VZ": "Communication Services", "TMUS": "Communication Services",
    "CHTR": "Communication Services",
    # ETFs / indices as "ETF"
    "SPY": "ETF", "QQQ": "ETF", "IWM": "ETF", "DIA": "ETF", "VOO": "ETF", "VTI": "ETF",
    "IVV": "ETF", "VEA": "ETF", "VWO": "ETF", "EFA": "ETF", "EEM": "ETF", "IEMG": "ETF",
    "AGG": "ETF", "BND": "ETF", "TLT": "ETF", "IEF": "ETF", "LQD": "ETF", "HYG": "ETF",
    "GLD": "ETF", "SLV": "ETF", "USO": "ETF", "UNG": "ETF", "XLE": "Energy",
    "XLF": "Financials", "XLK": "Technology", "XLV": "Healthcare", "XLI": "Industrials",
    "XLY": "Consumer", "XLP": "Consumer", "XLU": "Utilities", "XLB": "Materials",
    "XLRE": "Real Estate", "XLC": "Communication Services", "SMH": "Technology",
    "SOXX": "Technology", "ARKK": "Technology", "ARKW": "Technology", "BOTZ": "Technology",
    "TAN": "Energy", "ICLN": "Energy", "JETS": "Consumer", "XBI": "Healthcare",
    "IBB": "Healthcare", "KWEB": "Technology", "VNQ": "Real Estate", "SCHD": "ETF",
    "VIG": "ETF", "VUG": "ETF", "VTV": "ETF", "IWF": "ETF", "IWD": "ETF",
    # Frequently disclosed names missing from the first pass
    "DASH": "Consumer", "BRO": "Financials", "HUBB": "Industrials", "TSCO": "Consumer",
    "ENTG": "Technology", "PWR": "Industrials", "PAYX": "Industrials", "SCI": "Consumer",
    "FN": "Technology", "SGI": "Consumer", "WAB": "Industrials", "BWXT": "Industrials",
    "EME": "Industrials", "FLEX": "Technology", "KVUE": "Consumer", "VIK": "Consumer",
    "BJ": "Consumer", "FIS": "Financials", "MKL": "Financials", "MORN": "Financials",
    "NDAQ": "Financials", "CAG": "Consumer", "CDW": "Technology", "CLH": "Industrials",
    "CPAY": "Financials", "FIX": "Industrials", "VRT": "Industrials", "TT": "Industrials",
    "JCI": "Industrials", "CARR": "Industrials", "IR": "Industrials", "AME": "Industrials",
    "ROK": "Industrials", "DOV": "Industrials", "XYL": "Industrials", "IEX": "Industrials",
    "GNRC": "Industrials", "AYI": "Industrials", "LECO": "Industrials", "PNR": "Industrials",
    "GGG": "Industrials", "IWM": "ETF", "RSP": "ETF", "MDY": "ETF", "IJH": "ETF",
    "IJR": "ETF", "VB": "ETF", "VO": "ETF", "VGT": "Technology", "VHT": "Healthcare",
    "VFH": "Financials", "VIS": "Industrials", "VAW": "Materials", "VDE": "Energy",
    "VCR": "Consumer", "VDC": "Consumer", "VOX": "Communication Services",
    "LULU": "Consumer", "DECK": "Consumer", "CROX": "Consumer", "ONON": "Consumer",
    "TPR": "Consumer", "RL": "Consumer", "CPRI": "Consumer", "PVH": "Consumer",
    "HSY": "Consumer", "MKC": "Consumer", "SJM": "Consumer", "HRL": "Consumer",
    "CPB": "Consumer", "K": "Consumer", "GIS": "Consumer", "TAP": "Consumer",
    "SAM": "Consumer", "CELH": "Consumer", "MNST": "Consumer", "KO": "Consumer",
    "CRWD": "Technology", "NET": "Technology", "DDOG": "Technology", "SNOW": "Technology",
    "TTD": "Technology", "ZG": "Communication Services", "Z": "Communication Services",
    "PINS": "Communication Services", "SNAP": "Communication Services", "RDDT": "Communication Services",
    "SPOT": "Communication Services", "ROKU": "Communication Services", "LYV": "Communication Services",
    "EA": "Communication Services", "TTWO": "Communication Services", "RBLX": "Technology",
}

# Map short desk labels → scorer committee sectors
SCORER_SECTOR_ALIAS: dict[str, str] = {
    "Technology": "Information Technology",
    "Financials": "Financial Services",
    "Consumer": "Consumer Discretionary",
    "Communication Services": "Communication Services",
    "Healthcare": "Healthcare",
    "Energy": "Energy",
    "Industrials": "Industrials",
    "Materials": "Materials",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
    "ETF": "Financial Services",
}


def resolve_sector(
    ticker: Optional[str],
    trade_sector: Optional[str] = None,
    company_sector: Optional[str] = None,
) -> Optional[str]:
    if trade_sector and str(trade_sector).strip():
        return str(trade_sector).strip()
    if company_sector and str(company_sector).strip():
        return str(company_sector).strip()
    if ticker:
        return TICKER_SECTOR.get(ticker.upper().strip().replace(" ", ""))
    return None


def scorer_sector(label: Optional[str]) -> str:
    if not label:
        return ""
    return SCORER_SECTOR_ALIAS.get(label, label)


def apply_sectors_to_session(session) -> dict[str, int]:
    """Fill Trade.sector and Company.sector from the static map + existing companies."""
    from congress_quant_tracker.database.models import Company, Trade

    stats = {"trades_updated": 0, "companies_updated": 0, "companies_created": 0}

    companies = {c.ticker.upper(): c for c in session.query(Company).all()}
    tickers_seen: set[str] = set()

    for trade in session.query(Trade).all():
        tkr = (trade.ticker or "").upper().strip()
        if not tkr:
            continue
        tickers_seen.add(tkr)
        company = companies.get(tkr)
        sector = resolve_sector(tkr, trade.sector, company.sector if company else None)
        if sector and trade.sector != sector:
            trade.sector = sector
            stats["trades_updated"] += 1
        if company and sector and not company.sector:
            company.sector = sector
            stats["companies_updated"] += 1

    for tkr in tickers_seen:
        if tkr in companies:
            continue
        sector = TICKER_SECTOR.get(tkr)
        session.add(
            Company(
                ticker=tkr,
                name=tkr,
                sector=sector,
                last_updated=datetime.utcnow(),
            )
        )
        stats["companies_created"] += 1

    session.commit()
    return stats
