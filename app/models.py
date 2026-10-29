from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from sqlalchemy import (
    Integer, String, Text, Boolean, Float, Date,
    DateTime, CheckConstraint, UniqueConstraint, Index,
    func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


def _thirty_days() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=30)

# User

class User(db.Model):

    __tablename__ = "users"

    id         : Mapped[int]            = mapped_column(Integer, primary_key=True)
    username   : Mapped[str]            = mapped_column(String(80), unique=True,
                                                        nullable=False, index=True)
    hash       : Mapped[str]            = mapped_column(Text, nullable=False)
    created_at : Mapped[datetime]       = mapped_column(DateTime(timezone=True),
                                                        default=_now, nullable=False)
    deleted_at : Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True),
                                                            nullable=True)

    # Relationships
    profile    : Mapped[Optional["Profile"]] = relationship(
        "Profile", back_populates="user",
        uselist=False, cascade="all, delete-orphan",
    )
    trips      : Mapped[list["Trip"]] = relationship(
        "Trip", back_populates="user",
        cascade="all, delete-orphan",
    )
    feedback   : Mapped[list["Feedback"]] = relationship(
        "Feedback", back_populates="user",
    )

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None

    def __repr__(self) -> str:
        return f"<User {self.username!r}>"

# AnonymousSession

class AnonymousSession(db.Model):

    __tablename__ = "anonymous_sessions"

    id         : Mapped[int]      = mapped_column(Integer, primary_key=True)
    token      : Mapped[str]      = mapped_column(String(36), unique=True,
                                                  nullable=False, default=_uuid, index=True)
    created_at : Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  default=_now, nullable=False)
    last_seen  : Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  default=_now, onupdate=_now, nullable=False)
    expires_at : Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  default=_thirty_days, nullable=False)

    # Relationships
    profile    : Mapped[Optional["Profile"]] = relationship(
        "Profile", back_populates="session",
        uselist=False, cascade="all, delete-orphan",
    )
    trips      : Mapped[list["Trip"]] = relationship(
        "Trip", back_populates="session",
        cascade="all, delete-orphan",
    )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self) -> str:
        return f"<AnonymousSession token={self.token[:8]}...>"

# Profile

class Profile(db.Model):

    __tablename__ = "profiles"

    id                 : Mapped[int]           = mapped_column(Integer, primary_key=True)
    user_id            : Mapped[Optional[int]] = mapped_column(
        Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, unique=True,
    )
    session_token      : Mapped[Optional[str]] = mapped_column(
        String(36),
        db.ForeignKey("anonymous_sessions.token", ondelete="CASCADE"),
        nullable=True, unique=True,
    )

    # Preference columns
    temp_sensitivity   : Mapped[str] = mapped_column(String(10),  default="neutral", nullable=False)
    wardrobe_pref      : Mapped[str] = mapped_column(String(15),  default="neutral", nullable=False)
    style_pref         : Mapped[str] = mapped_column(String(15),  default="smart_casual", nullable=False)
    layering_pref      : Mapped[str] = mapped_column(String(10),  default="minimal", nullable=False)
    default_trip_mode  : Mapped[str] = mapped_column(String(15),  default="regular", nullable=False)
    default_activities : Mapped[list] = mapped_column(JSONB,       default=list, nullable=False)
    updated_at         : Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now, onupdate=_now, nullable=False,
    )

    # Relationships
    user    : Mapped[Optional["User"]]             = relationship("User",
                                                                  back_populates="profile")
    session : Mapped[Optional["AnonymousSession"]] = relationship("AnonymousSession",
                                                                  back_populates="profile")

    __table_args__ = (
        CheckConstraint(
            "user_id IS NOT NULL OR session_token IS NOT NULL",
            name="profile_owner_check",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "temp_sensitivity":   self.temp_sensitivity,
            "wardrobe_pref":      self.wardrobe_pref,
            "style_pref":         self.style_pref,
            "layering_pref":      self.layering_pref,
            "default_trip_mode":  self.default_trip_mode,
            "default_activities": self.default_activities or [],
        }

    def __repr__(self) -> str:
        owner = f"user={self.user_id}" if self.user_id else f"session={self.session_token[:8]}..."
        return f"<Profile {owner} style={self.style_pref!r}>"

# Trip

class Trip(db.Model):

    __tablename__ = "trips"

    id              : Mapped[int]           = mapped_column(Integer, primary_key=True)
    user_id         : Mapped[Optional[int]] = mapped_column(
        Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    session_token   : Mapped[Optional[str]] = mapped_column(
        String(36),
        db.ForeignKey("anonymous_sessions.token", ondelete="CASCADE"),
        nullable=True,
    )
    name            : Mapped[str]     = mapped_column(String(200), nullable=False)
    purpose         : Mapped[str]     = mapped_column(String(20),  default="leisure", nullable=False)
    trip_mode       : Mapped[str]     = mapped_column(String(15),  default="regular", nullable=False)
    bag_type        : Mapped[str]     = mapped_column(String(20),  default="carry_on", nullable=False)
    activities      : Mapped[list]    = mapped_column(JSONB,        default=list, nullable=False)
    laundry_access  : Mapped[str]     = mapped_column(String(10),  default="some", nullable=False)
    travelling_with : Mapped[str]     = mapped_column(String(10),  default="solo", nullable=False)
    created_at      : Mapped[datetime]= mapped_column(DateTime(timezone=True),
                                                      default=_now, nullable=False)
    deleted_at      : Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    user          : Mapped[Optional["User"]]             = relationship("User",
                                                                        back_populates="trips")
    session       : Mapped[Optional["AnonymousSession"]] = relationship("AnonymousSession",
                                                                        back_populates="trips")
    legs          : Mapped[list["TripLeg"]]    = relationship(
        "TripLeg", back_populates="trip",
        cascade="all, delete-orphan",
        order_by="TripLeg.leg_order",
    )
    packing_items : Mapped[list["PackingItem"]] = relationship(
        "PackingItem", back_populates="trip",
        cascade="all, delete-orphan",
    )
    feedback      : Mapped[list["Feedback"]]   = relationship(
        "Feedback", back_populates="trip",
    )

    __table_args__ = (
        CheckConstraint(
            "user_id IS NOT NULL OR session_token IS NOT NULL",
            name="trip_owner_check",
        ),
        Index(
            "idx_trips_user_active",
            "user_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_trips_session_active",
            "session_token",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def is_multi_destination(self) -> bool:
        return len(self.legs) > 1

    @property
    def packed_count(self) -> int:
        return sum(1 for item in self.packing_items if item.is_checked)

    @property
    def total_count(self) -> int:
        return len(self.packing_items)

    def to_config_dict(self) -> dict:
        return {
            "trip_mode":       self.trip_mode,
            "bag_type":        self.bag_type,
            "activities":      self.activities or [],
            "laundry_access":  self.laundry_access,
            "travelling_with": self.travelling_with,
            "purpose":         self.purpose,
        }

    def __repr__(self) -> str:
        return f"<Trip {self.id} {self.name!r} legs={len(self.legs)}>"

# TripLeg

class TripLeg(db.Model):

    __tablename__ = "trip_legs"

    id                : Mapped[int]            = mapped_column(Integer, primary_key=True)
    trip_id           : Mapped[int]            = mapped_column(
        Integer, db.ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
    )
    leg_order         : Mapped[int]            = mapped_column(Integer, nullable=False)
    city              : Mapped[str]            = mapped_column(String(100), nullable=False)
    country           : Mapped[Optional[str]]  = mapped_column(String(100), nullable=True)
    lat               : Mapped[float]          = mapped_column(Float, nullable=False)
    lng               : Mapped[float]          = mapped_column(Float, nullable=False)
    start_date        : Mapped[str]            = mapped_column(String(10), nullable=False)
    end_date          : Mapped[str]            = mapped_column(String(10), nullable=False)
    forecast_snapshot : Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    context_flags     : Mapped[dict]           = mapped_column(
        JSONB,
        default=lambda: {
            "conservative": False,
            "high_altitude": False,
            "remote": False,
        },
        nullable=False,
    )
    created_at        : Mapped[datetime]       = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False,
    )

    # Relationships
    trip : Mapped["Trip"] = relationship("Trip", back_populates="legs")

    __table_args__ = (
        Index("idx_legs_trip_id", "trip_id"),
        UniqueConstraint("trip_id", "leg_order", name="uq_trip_leg_order"),
    )

    @property
    def duration_days(self) -> int:
        from datetime import date as date_type
        start = date_type.fromisoformat(self.start_date)
        end   = date_type.fromisoformat(self.end_date)
        return max((end - start).days, 1)

    @property
    def display_name(self) -> str:
        if self.country:
            return f"{self.city}, {self.country}"
        return self.city

    def to_dict(self) -> dict:
        signals = []
        if self.forecast_snapshot:
            from app.core.weather import signals_from_cache
            signals = signals_from_cache(self.forecast_snapshot)

        return {
            "id":             self.id,
            "leg_order":      self.leg_order,
            "city":           self.city,
            "country":        self.country,
            "lat":            self.lat,
            "lng":            self.lng,
            "start_date":     self.start_date,
            "end_date":       self.end_date,
            "duration_days":  self.duration_days,
            "forecast":       signals,
            "context_flags":  self.context_flags or {},
        }

    def __repr__(self) -> str:
        return f"<TripLeg {self.leg_order} {self.city!r} {self.start_date}->{self.end_date}>"

# PackingItem

class PackingItem(db.Model):

    __tablename__ = "packing_items"

    id               : Mapped[int]           = mapped_column(Integer, primary_key=True)
    trip_id          : Mapped[int]           = mapped_column(
        Integer, db.ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
    )
    category         : Mapped[str]           = mapped_column(String(20), nullable=False)
    item_name        : Mapped[str]           = mapped_column(String(200), nullable=False)
    item_key         : Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    # item_key is the slug used to look up the Tabler icon and outfit image. e.g. "linen_shirt", "chinos", "compact_umbrella"

    dest_legs        : Mapped[list]          = mapped_column(JSONB, default=list, nullable=False)
    advisor_quantity : Mapped[int]           = mapped_column(Integer, default=1, nullable=False)
    user_quantity    : Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_checked       : Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    is_custom        : Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    sort_order       : Mapped[int]           = mapped_column(Integer, default=0, nullable=False)
    zone_label       : Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    note             : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at       : Mapped[datetime]      = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False,
    )

    # Relationships
    trip : Mapped["Trip"] = relationship("Trip", back_populates="packing_items")

    __table_args__ = (
        Index("idx_items_trip_id", "trip_id"),
        Index("idx_items_trip_category", "trip_id", "category"),
        # GIN index on the JSONB array column. Enables fast containment queries: WHERE dest_legs @> '[2]' This is the primary reason Postgres was chosen over SQLite.
        Index(
            "idx_items_dest_legs_gin",
            "dest_legs",
            postgresql_using="gin",
        ),
    )

    @property
    def display_quantity(self) -> int:
        return self.user_quantity if self.user_quantity is not None else self.advisor_quantity

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "trip_id":          self.trip_id,
            "category":         self.category,
            "item_name":        self.item_name,
            "item_key":         self.item_key,
            "dest_legs":        self.dest_legs or [],
            "advisor_quantity": self.advisor_quantity,
            "user_quantity":    self.user_quantity,
            "display_quantity": self.display_quantity,
            "is_checked":       self.is_checked,
            "is_custom":        self.is_custom,
            "sort_order":       self.sort_order,
            "zone_label":       self.zone_label,
            "note":             self.note,
        }

    def __repr__(self) -> str:
        return f"<PackingItem {self.item_name!r} qty={self.display_quantity} checked={self.is_checked}>"

# ForecastCache

class ForecastCache(db.Model):

    __tablename__ = "forecast_cache"

    id         : Mapped[int]      = mapped_column(Integer, primary_key=True)
    city       : Mapped[str]      = mapped_column(String(100), nullable=False)
    lat        : Mapped[float]    = mapped_column(Float, nullable=False)
    lng        : Mapped[float]    = mapped_column(Float, nullable=False)
    date_range : Mapped[str]      = mapped_column(String(25), nullable=False)
    response   : Mapped[dict]     = mapped_column(JSONB, nullable=False)
    fetched_at : Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("city", "date_range", name="uq_forecast_cache"),
        Index("idx_cache_city_date", "city", "date_range"),
    )

    def is_fresh(self, ttl_seconds: int = 3600) -> bool:
        age = datetime.now(timezone.utc) - self.fetched_at
        return age.total_seconds() < ttl_seconds

    def __repr__(self) -> str:
        return f"<ForecastCache {self.city!r} {self.date_range} fresh={self.is_fresh()}>"

# Feedback

class Feedback(db.Model):

    __tablename__ = "feedback"

    id            : Mapped[int]           = mapped_column(Integer, primary_key=True)
    trip_id       : Mapped[Optional[int]] = mapped_column(
        Integer, db.ForeignKey("trips.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id       : Mapped[Optional[int]] = mapped_column(
        Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_token : Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    rating        : Mapped[int]           = mapped_column(Integer, nullable=False)
    comment       : Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    submitted_at  : Mapped[datetime]      = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False,
    )

    # Relationships
    trip : Mapped[Optional["Trip"]] = relationship("Trip", back_populates="feedback")
    user : Mapped[Optional["User"]] = relationship("User", back_populates="feedback")

    __table_args__ = (
        CheckConstraint("rating IN (1, -1)", name="feedback_rating_check"),
        Index("idx_feedback_trip", "trip_id"),
    )

    def __repr__(self) -> str:
        symbol = "+" if self.rating == 1 else "-"
        return f"<Feedback trip={self.trip_id} rating={symbol}>"

# LoginAttempt

class LoginAttempt(db.Model):

    __tablename__ = "login_attempts"

    id           : Mapped[int]           = mapped_column(Integer, primary_key=True)
    ip_address   : Mapped[str]           = mapped_column(String(45), nullable=False)
    username     : Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    success      : Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    attempted_at : Mapped[datetime]      = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False,
    )

    __table_args__ = (
        Index("idx_attempts_ip_time", "ip_address", "attempted_at"),
    )

    def __repr__(self) -> str:
        result = "ok" if self.success else "fail"
        return f"<LoginAttempt ip={self.ip_address} {result} at={self.attempted_at}>"

# GeoCache

class GeoCache(db.Model):

    __tablename__ = "geo_cache"

    id           : Mapped[int]      = mapped_column(Integer, primary_key=True)
    query        : Mapped[str]      = mapped_column(String(200), nullable=False, unique=True)
    lat          : Mapped[float]    = mapped_column(Float, nullable=False)
    lng          : Mapped[float]    = mapped_column(Float, nullable=False)
    short_name   : Mapped[str]      = mapped_column(String(200), nullable=False)
    display_name : Mapped[str]      = mapped_column(Text, nullable=False)
    fetched_at   : Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False,
    )

    __table_args__ = (
        Index("idx_geo_cache_query", "query"),
    )

    def is_fresh(self, ttl_seconds: int = 86400 * 30) -> bool:
        age = datetime.now(timezone.utc) - self.fetched_at
        return age.total_seconds() < ttl_seconds

    def __repr__(self) -> str:
        return f"<GeoCache {self.query!r} -> {self.short_name!r}>"