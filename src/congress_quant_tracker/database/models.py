"""SQLAlchemy ORM models for CongressQuantTracker."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class Politician(Base):
    __tablename__ = "politicians"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = Column(String(255), nullable=False, index=True)
    chamber: Mapped[str] = Column(
        Enum("house", "senate", name="chamber_type"), nullable=False
    )
    party: Mapped[str] = Column(
        Enum("D", "R", "I", name="party_type"), nullable=False
    )
    state: Mapped[str] = Column(String(2), nullable=False)
    district: Mapped[Optional[str]] = Column(String(10), nullable=True)
    committees: Mapped[Optional[str]] = Column(Text, nullable=True)
    external_id: Mapped[Optional[str]] = Column(String(50), nullable=True, index=True)
    bioguide_id: Mapped[Optional[str]] = Column(String(10), nullable=True)
    photo_url: Mapped[Optional[str]] = Column(Text, nullable=True)
    total_trades: Mapped[int] = Column(Integer, default=0)
    avg_score: Mapped[float] = Column(Float, default=0.0)
    active: Mapped[bool] = Column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    trades: Mapped[list["Trade"]] = relationship(
        "Trade", back_populates="politician", lazy="dynamic"
    )

    __table_args__ = (
        UniqueConstraint("name", "state", "district", name="uq_politician"),
    )

    def __repr__(self) -> str:
        chamber_label = "Rep." if self.chamber == "house" else "Sen."
        return f"<{chamber_label} {self.name} ({self.party}-{self.state})>"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = Column(String(10), nullable=False, unique=True, index=True)
    name: Mapped[str] = Column(String(255), nullable=False)
    sector: Mapped[Optional[str]] = Column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = Column(String(100), nullable=True)
    market_cap: Mapped[Optional[float]] = Column(Float, nullable=True)
    beta: Mapped[Optional[float]] = Column(Float, nullable=True)
    last_updated: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Company {self.ticker} ({self.sector})>"


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    politician_id: Mapped[int] = Column(
        Integer, ForeignKey("politicians.id"), nullable=False, index=True
    )
    ticker: Mapped[str] = Column(String(10), nullable=False, index=True)
    asset_name: Mapped[Optional[str]] = Column(String(255), nullable=True)
    asset_type: Mapped[Optional[str]] = Column(String(50), nullable=True)
    transaction_type: Mapped[str] = Column(
        Enum("buy", "sell", "exchange", name="transaction_type"), nullable=False
    )
    trade_date: Mapped[date] = Column(Date, nullable=False, index=True)
    filing_date: Mapped[Optional[date]] = Column(Date, nullable=True, index=True)
    value_min: Mapped[Optional[int]] = Column(Integer, nullable=True)
    value_max: Mapped[Optional[int]] = Column(Integer, nullable=True)
    value_range: Mapped[Optional[str]] = Column(String(50), nullable=True)
    shares_min: Mapped[Optional[Decimal]] = Column(Numeric(18, 4), nullable=True)
    shares_max: Mapped[Optional[Decimal]] = Column(Numeric(18, 4), nullable=True)
    report_type: Mapped[Optional[str]] = Column(String(100), nullable=True)
    source_url: Mapped[Optional[str]] = Column(Text, nullable=True)
    pdf_url: Mapped[Optional[str]] = Column(Text, nullable=True)
    notes: Mapped[Optional[str]] = Column(Text, nullable=True)
    score: Mapped[int] = Column(Integer, default=0)
    tag: Mapped[Optional[str]] = Column(String(20), nullable=True)
    reason: Mapped[Optional[str]] = Column(Text, nullable=True)
    owner: Mapped[Optional[str]] = Column(String(10), nullable=True)
    sector: Mapped[Optional[str]] = Column(String(100), nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    politician: Mapped["Politician"] = relationship(
        "Politician", back_populates="trades"
    )
    options: Mapped[list["OptionsTrade"]] = relationship(
        "OptionsTrade", back_populates="trade", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "politician_id", "ticker", "trade_date", "transaction_type",
            name="uq_trade",
        ),
    )

    def __repr__(self) -> str:
        return f"<Trade {self.transaction_type} {self.ticker} on {self.trade_date}>"


class OptionsTrade(Base):
    __tablename__ = "options_trades"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = Column(
        Integer, ForeignKey("trades.id"), nullable=False, index=True
    )
    option_type: Mapped[str] = Column(
        Enum("call", "put", name="option_type"), nullable=False
    )
    strike: Mapped[Optional[float]] = Column(Float, nullable=True)
    expiration_date: Mapped[Optional[date]] = Column(Date, nullable=True)
    contracts_min: Mapped[Optional[int]] = Column(Integer, nullable=True)
    contracts_max: Mapped[Optional[int]] = Column(Integer, nullable=True)
    premium_min: Mapped[Optional[int]] = Column(Integer, nullable=True)
    premium_max: Mapped[Optional[int]] = Column(Integer, nullable=True)
    premium_range: Mapped[Optional[str]] = Column(String(50), nullable=True)
    underlying_asset: Mapped[Optional[str]] = Column(String(10), nullable=True)
    notes: Mapped[Optional[str]] = Column(Text, nullable=True)

    trade: Mapped["Trade"] = relationship("Trade", back_populates="options")

    def __repr__(self) -> str:
        return f"<Option {self.option_type} {self.underlying_asset} ${self.strike}>"


class UpdateLog(Base):
    __tablename__ = "updates_log"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    update_type: Mapped[str] = Column(String(50), nullable=False, index=True)
    status: Mapped[str] = Column(
        Enum("started", "in_progress", "completed", "failed", name="update_status"),
        nullable=False,
        default="started",
    )
    started_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    records_processed: Mapped[int] = Column(Integer, default=0)
    error_message: Mapped[Optional[str]] = Column(Text, nullable=True)
    details: Mapped[Optional[str]] = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<UpdateLog {self.update_type} [{self.status}]>"


def get_engine(database_url: str):
    """Create SQLAlchemy engine."""
    return create_engine(database_url, echo=False)


def get_session(engine) -> Session:
    """Create a new database session."""
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def init_db(database_url: str) -> None:
    """Create all tables in the database."""
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
