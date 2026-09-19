from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.models import PackingItem, Trip

# Write operations
def save_packing_list(trip_id: int, items: list[dict]) -> list[PackingItem]:
    PackingItem.query.filter_by(
        trip_id=trip_id,
        is_custom=False,
    ).delete(synchronize_session="fetch")

    saved = []
    for item_dict in items:
        item = PackingItem(
            trip_id          = trip_id,
            category         = item_dict.get("category", "extras"),
            item_name        = item_dict.get("item_name", ""),
            item_key         = item_dict.get("item_key"),
            dest_legs        = item_dict.get("dest_legs", []),
            advisor_quantity = item_dict.get("advisor_quantity", 1),
            user_quantity    = None,          # always starts as advisor default
            is_checked       = False,
            is_custom        = False,
            sort_order       = item_dict.get("sort_order", 0),
            zone_label       = item_dict.get("zone_label"),
            note             = item_dict.get("note", "") or "",
        )
        db.session.add(item)
        saved.append(item)

    db.session.commit()
    return saved


def add_custom_item(
        trip_id:  int,
        item_name: str,
        category:  str = "extras",
) -> PackingItem:
    # Place custom items after all advisor-generated items
    max_order = db.session.query(
        db.func.max(PackingItem.sort_order)
    ).filter_by(trip_id=trip_id).scalar() or 0

    item = PackingItem(
        trip_id          = trip_id,
        category         = category,
        item_name        = item_name[:200].strip(),
        item_key         = None,         # no slug for custom items
        dest_legs        = [],           # applies to all legs
        advisor_quantity = 1,
        user_quantity    = None,
        is_checked       = False,
        is_custom        = True,
        sort_order       = max_order + 100,
        zone_label       = None,
        note             = "",
    )
    db.session.add(item)
    db.session.commit()
    return item


def delete_custom_item(item_id: int, trip_id: int) -> bool:
    item = PackingItem.query.filter_by(
        id=item_id,
        trip_id=trip_id,
        is_custom=True,
    ).first()

    if item is None:
        return False

    db.session.delete(item)
    db.session.commit()
    return True

# Update operations
def toggle_checked(item_id: int, trip_id: int, checked: bool) -> Optional[dict]:
    item = PackingItem.query.filter_by(id=item_id, trip_id=trip_id).first()
    if item is None:
        return None

    item.is_checked = checked
    db.session.commit()

    return get_counts(trip_id)


def update_quantity(
        item_id:  int,
        trip_id:  int,
        quantity: Optional[int],
) -> Optional[dict]:
    item = PackingItem.query.filter_by(id=item_id, trip_id=trip_id).first()
    if item is None:
        return None

    if quantity is not None:
        quantity = max(1, int(quantity))     # enforce minimum of 1

    item.user_quantity = quantity
    db.session.commit()

    return {
        "item_id":          item.id,
        "display_quantity": item.display_quantity,
        "advisor_quantity": item.advisor_quantity,
        "user_quantity":    item.user_quantity,
    }


def reset_items(
        trip_id:  int,
        category: str = "all",
) -> dict:
    query = PackingItem.query.filter_by(trip_id=trip_id, is_custom=False)

    if category != "all":
        query = query.filter_by(category=category)

    items = query.all()

    for item in items:
        item.is_checked    = False
        item.user_quantity = None

    db.session.commit()

    return {
        "reset_count": len(items),
        "category":    category,
        **get_counts(trip_id),
    }

# Read operations
def get_packing_list(
        trip_id:  int,
        category: Optional[str] = None,
        leg_id:   Optional[int] = None,
) -> list[dict]:
    query = PackingItem.query.filter_by(trip_id=trip_id)

    if category and category != "all":
        query = query.filter_by(category=category)

    if leg_id is not None:
        # JSONB containment query - fast because of the GIN index
        query = query.filter(
            PackingItem.dest_legs.contains([leg_id])
        )

    items = query.order_by(PackingItem.sort_order).all()
    return [item.to_dict() for item in items]


def get_counts(trip_id: int) -> dict:
    items = PackingItem.query.filter_by(trip_id=trip_id).all()

    total        = len(items)
    packed       = sum(1 for i in items if i.is_checked)
    total_pieces = sum(i.display_quantity for i in items if i.is_checked)
    percent      = int((packed / total * 100)) if total > 0 else 0

    return {
        "packed":       packed,
        "total":        total,
        "total_pieces": total_pieces,
        "percent":      percent,
    }


def get_item(item_id: int, trip_id: int) -> Optional[dict]:
    item = PackingItem.query.filter_by(id=item_id, trip_id=trip_id).first()
    if item is None:
        return None
    return item.to_dict()

# Ownership verification
def verify_trip_owner(trip_id: int, user_id: Optional[int], session_token: Optional[str]) -> bool:
    query = Trip.query.filter_by(id=trip_id, deleted_at=None)

    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    elif session_token is not None:
        query = query.filter_by(session_token=session_token)
    else:
        return False

    return query.first() is not None



# Summary helpers
def get_category_summary(trip_id: int) -> list[dict]:
    items = PackingItem.query.filter_by(trip_id=trip_id).all()

    CATEGORY_ORDER = ["tops", "bottoms", "layers", "shoes", "extras", "activity"]
    summary: dict[str, dict] = {}

    for item in items:
        cat = item.category
        if cat not in summary:
            summary[cat] = {"category": cat, "packed": 0, "total": 0}
        summary[cat]["total"] += 1
        if item.is_checked:
            summary[cat]["packed"] += 1

    # Return in display order, unknown categories at the end
    result = []
    for cat in CATEGORY_ORDER:
        if cat in summary:
            result.append(summary[cat])
    for cat, data in summary.items():
        if cat not in CATEGORY_ORDER:
            result.append(data)

    return result


def get_destination_summary(trip_id: int, legs: list) -> list[dict]:
    all_items = PackingItem.query.filter_by(trip_id=trip_id).all()
    result    = []

    for leg in legs:
        leg_id    = leg.id
        leg_items = [i for i in all_items if leg_id in (i.dest_legs or [])]
        total     = len(leg_items)
        packed    = sum(1 for i in leg_items if i.is_checked)
        percent   = int(packed / total * 100) if total > 0 else 0

        result.append({
            "leg_id":  leg_id,
            "city":    leg.city,
            "packed":  packed,
            "total":   total,
            "percent": percent,
        })

    return result