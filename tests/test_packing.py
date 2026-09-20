import pytest
from app import create_app
from app.extensions import db as _db
from app.models import User, Trip, PackingItem, AnonymousSession
from app.core import packing

# Test app + DB fixtures

@pytest.fixture(scope="module")
def app():
    #Create a test Flask app using TestingConfig.
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="module")
def db(app):
    #Return the db instance bound to the test app.
    return _db


@pytest.fixture(autouse=True)
def clean_tables(db):
    # Clear packing_items and trips before each test. autouse=True means this runs automatically for every test.
    yield
    db.session.query(PackingItem).delete()
    db.session.query(Trip).delete()
    db.session.query(AnonymousSession).delete()
    db.session.query(User).delete()
    db.session.commit()

# Helpers

def make_session(db) -> AnonymousSession:
    #Create and persist an anonymous session.
    session = AnonymousSession()
    db.session.add(session)
    db.session.commit()
    return session


def make_trip(db, session_token: str) -> Trip:
    #Create and persist a basic trip owned by an anonymous session.
    trip = Trip(
        session_token   = session_token,
        name            = "Test Trip",
        purpose         = "leisure",
        trip_mode       = "regular",
        bag_type        = "carry_on",
        activities      = [],
        laundry_access  = "some",
        travelling_with = "solo",
    )
    db.session.add(trip)
    db.session.commit()
    return trip


def make_item_dict(item_key: str = "fitted_tee", category: str = "tops",
                   quantity: int = 1, dest_legs: list = None,
                   sort_order: int = 0, must: bool = True) -> dict:
    #Build a minimal item dict as advisor.build_packing_list() would return.
    return {
        "item_key":         item_key,
        "item_name":        item_key.replace("_", " ").title(),
        "category":         category,
        "icon":             "ti-shirt",
        "advisor_quantity": quantity,
        "dest_legs":        dest_legs or [],
        "sort_order":       sort_order,
        "zone_label":       "middle",
        "note":             "",
        "must":             must,
    }


# save_packing_list

class TestSavePackingList:

    def test_saves_items_to_database(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            items   = [
                make_item_dict("fitted_tee", "tops"),
                make_item_dict("chinos",     "bottoms"),
                make_item_dict("loafers",    "shoes"),
            ]
            saved = packing.save_packing_list(trip.id, items)
            assert len(saved) == 3

    def test_saved_items_in_database(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            items   = [make_item_dict("fitted_tee")]
            packing.save_packing_list(trip.id, items)
            db_items = PackingItem.query.filter_by(trip_id=trip.id).all()
            assert len(db_items) == 1
            assert db_items[0].item_key == "fitted_tee"

    def test_is_checked_defaults_false(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            item = PackingItem.query.filter_by(trip_id=trip.id).first()
            assert item.is_checked is False

    def test_user_quantity_defaults_none(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            item = PackingItem.query.filter_by(trip_id=trip.id).first()
            assert item.user_quantity is None

    def test_is_custom_false(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            item = PackingItem.query.filter_by(trip_id=trip.id).first()
            assert item.is_custom is False

    def test_advisor_quantity_saved(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee", quantity=3)])
            item = PackingItem.query.filter_by(trip_id=trip.id).first()
            assert item.advisor_quantity == 3

    def test_dest_legs_saved(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict(dest_legs=[1, 2])])
            item = PackingItem.query.filter_by(trip_id=trip.id).first()
            assert item.dest_legs == [1, 2]

    def test_regeneration_replaces_advisor_items(self, app, db):
        #Calling save_packing_list twice replaces advisor items but not custom.
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)

            # First generation
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee"),
                make_item_dict("chinos"),
            ])

            # Add a custom item manually
            packing.add_custom_item(trip.id, "My lucky socks")

            # Regenerate -- only advisor items should be replaced
            packing.save_packing_list(trip.id, [make_item_dict("linen_shirt")])

            advisor_items = PackingItem.query.filter_by(
                trip_id=trip.id, is_custom=False
            ).all()
            custom_items = PackingItem.query.filter_by(
                trip_id=trip.id, is_custom=True
            ).all()

            assert len(advisor_items) == 1
            assert advisor_items[0].item_key == "linen_shirt"
            assert len(custom_items) == 1
            assert custom_items[0].item_name == "My lucky socks"

    def test_sort_order_saved(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee", sort_order=10),
                make_item_dict("chinos",     sort_order=20),
            ])
            items = PackingItem.query.filter_by(
                trip_id=trip.id
            ).order_by(PackingItem.sort_order).all()
            assert items[0].sort_order == 10
            assert items[1].sort_order == 20

    def test_empty_list_clears_advisor_items(self, app, db):
        #Saving an empty list removes all advisor items.
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            packing.save_packing_list(trip.id, [])
            items = PackingItem.query.filter_by(
                trip_id=trip.id, is_custom=False
            ).all()
            assert len(items) == 0


# add_custom_item
class TestAddCustomItem:

    def test_adds_item_to_database(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            item    = packing.add_custom_item(trip.id, "My charger")
            assert item.id is not None
            assert item.item_name == "My charger"

    def test_is_custom_true(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            item    = packing.add_custom_item(trip.id, "My charger")
            assert item.is_custom is True

    def test_default_category_extras(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            item    = packing.add_custom_item(trip.id, "My charger")
            assert item.category == "extras"

    def test_custom_category(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            item    = packing.add_custom_item(trip.id, "Rain boots", category="shoes")
            assert item.category == "shoes"

    def test_is_checked_false(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            item    = packing.add_custom_item(trip.id, "My charger")
            assert item.is_checked is False

    def test_long_name_truncated(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            long_name = "x" * 300
            item    = packing.add_custom_item(trip.id, long_name)
            assert len(item.item_name) <= 200

    def test_appears_after_advisor_items(self, app, db):
        #Custom item sort_order should be higher than advisor items.
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee", sort_order=10),
            ])
            custom = packing.add_custom_item(trip.id, "My charger")
            assert custom.sort_order > 10


# delete_custom_item

class TestDeleteCustomItem:

    def test_deletes_custom_item(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            item    = packing.add_custom_item(trip.id, "My charger")
            result  = packing.delete_custom_item(item.id, trip.id)
            assert result is True
            assert PackingItem.query.get(item.id) is None

    def test_returns_false_for_nonexistent_item(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            result  = packing.delete_custom_item(99999, trip.id)
            assert result is False

    def test_cannot_delete_advisor_item(self, app, db):
        #Advisor-generated items must not be deletable via this function.
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            advisor_item = PackingItem.query.filter_by(
                trip_id=trip.id, is_custom=False
            ).first()
            result = packing.delete_custom_item(advisor_item.id, trip.id)
            assert result is False
            assert PackingItem.query.get(advisor_item.id) is not None

    def test_cannot_delete_other_trips_item(self, app, db):
        #Cross-trip deletion should be prevented.
        with app.app_context():
            session = make_session(db)
            trip1   = make_trip(db, session.token)
            trip2   = make_trip(db, session.token)
            item    = packing.add_custom_item(trip1.id, "My charger")
            result  = packing.delete_custom_item(item.id, trip2.id)
            assert result is False



# toggle_checked

class TestToggleChecked:

    def test_sets_checked_true(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            item    = PackingItem.query.filter_by(trip_id=trip.id).first()
            result  = packing.toggle_checked(item.id, trip.id, True)
            assert result is not None
            assert PackingItem.query.get(item.id).is_checked is True

    def test_sets_checked_false(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            item    = PackingItem.query.filter_by(trip_id=trip.id).first()
            packing.toggle_checked(item.id, trip.id, True)
            packing.toggle_checked(item.id, trip.id, False)
            assert PackingItem.query.get(item.id).is_checked is False

    def test_returns_counts(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            item    = PackingItem.query.filter_by(trip_id=trip.id).first()
            result  = packing.toggle_checked(item.id, trip.id, True)
            assert "packed" in result
            assert "total"  in result
            assert result["packed"] == 1
            assert result["total"]  == 1

    def test_returns_none_for_nonexistent_item(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            result  = packing.toggle_checked(99999, trip.id, True)
            assert result is None


# update_quantity

class TestUpdateQuantity:

    def test_sets_user_quantity(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            item    = PackingItem.query.filter_by(trip_id=trip.id).first()
            result  = packing.update_quantity(item.id, trip.id, 3)
            assert result is not None
            assert PackingItem.query.get(item.id).user_quantity == 3

    def test_display_quantity_reflects_override(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee", quantity=1)])
            item    = PackingItem.query.filter_by(trip_id=trip.id).first()
            packing.update_quantity(item.id, trip.id, 4)
            assert PackingItem.query.get(item.id).display_quantity == 4

    def test_none_restores_advisor_default(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee", quantity=2)])
            item    = PackingItem.query.filter_by(trip_id=trip.id).first()
            packing.update_quantity(item.id, trip.id, 5)
            packing.update_quantity(item.id, trip.id, None)
            updated = PackingItem.query.get(item.id)
            assert updated.user_quantity    is None
            assert updated.display_quantity == 2   # back to advisor_quantity

    def test_minimum_quantity_is_1(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            item    = PackingItem.query.filter_by(trip_id=trip.id).first()
            packing.update_quantity(item.id, trip.id, 0)
            assert PackingItem.query.get(item.id).user_quantity == 1

    def test_returns_none_for_nonexistent_item(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            result  = packing.update_quantity(99999, trip.id, 3)
            assert result is None

# reset_items

class TestResetItems:

    def test_full_reset_unchecks_all(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee", "tops"),
                make_item_dict("chinos",     "bottoms"),
            ])
            # Check both items
            for item in PackingItem.query.filter_by(trip_id=trip.id).all():
                packing.toggle_checked(item.id, trip.id, True)

            result = packing.reset_items(trip.id, "all")
            assert result["reset_count"] == 2
            for item in PackingItem.query.filter_by(trip_id=trip.id).all():
                assert item.is_checked is False

    def test_category_reset_only_affects_category(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee", "tops"),
                make_item_dict("chinos",     "bottoms"),
            ])
            for item in PackingItem.query.filter_by(trip_id=trip.id).all():
                packing.toggle_checked(item.id, trip.id, True)

            packing.reset_items(trip.id, "tops")

            tops    = PackingItem.query.filter_by(trip_id=trip.id, category="tops").first()
            bottoms = PackingItem.query.filter_by(trip_id=trip.id, category="bottoms").first()
            assert tops.is_checked    is False
            assert bottoms.is_checked is True   # untouched

    def test_reset_restores_user_quantity_to_none(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee", quantity=2)])
            item    = PackingItem.query.filter_by(trip_id=trip.id).first()
            packing.update_quantity(item.id, trip.id, 5)
            packing.reset_items(trip.id, "all")
            updated = PackingItem.query.get(item.id)
            assert updated.user_quantity    is None
            assert updated.display_quantity == 2

    def test_reset_never_touches_custom_items(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            custom  = packing.add_custom_item(trip.id, "My charger")
            packing.toggle_checked(custom.id, trip.id, True)
            packing.reset_items(trip.id, "all")
            assert PackingItem.query.get(custom.id).is_checked is True

    def test_returns_counts(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            result  = packing.reset_items(trip.id, "all")
            assert "packed"      in result
            assert "total"       in result
            assert "reset_count" in result

# get_packing_list

class TestGetPackingList:

    def test_returns_all_items(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee", "tops"),
                make_item_dict("chinos",     "bottoms"),
                make_item_dict("loafers",    "shoes"),
            ])
            result = packing.get_packing_list(trip.id)
            assert len(result) == 3

    def test_returns_list_of_dicts(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee")])
            result  = packing.get_packing_list(trip.id)
            assert isinstance(result, list)
            assert isinstance(result[0], dict)

    def test_category_filter(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee", "tops"),
                make_item_dict("chinos",     "bottoms"),
            ])
            tops = packing.get_packing_list(trip.id, category="tops")
            assert len(tops)  == 1
            assert tops[0]["category"] == "tops"

    def test_leg_filter(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee", dest_legs=[1]),
                make_item_dict("chinos",     dest_legs=[2]),
                make_item_dict("loafers",    dest_legs=[1, 2]),
            ])
            leg1_items = packing.get_packing_list(trip.id, leg_id=1)
            # Should return fitted_tee (leg 1) and loafers (legs 1+2)
            keys = [i["item_key"] for i in leg1_items]
            assert "fitted_tee" in keys
            assert "loafers"    in keys
            assert "chinos"     not in keys

    def test_ordered_by_sort_order(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("chinos",     sort_order=20),
                make_item_dict("fitted_tee", sort_order=10),
            ])
            result = packing.get_packing_list(trip.id)
            assert result[0]["item_key"] == "fitted_tee"
            assert result[1]["item_key"] == "chinos"

    def test_empty_trip_returns_empty_list(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            result  = packing.get_packing_list(trip.id)
            assert result == []

# get_counts

class TestGetCounts:

    def test_all_zeros_on_empty_trip(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            counts  = packing.get_counts(trip.id)
            assert counts["packed"]  == 0
            assert counts["total"]   == 0
            assert counts["percent"] == 0

    def test_total_reflects_all_items(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee"),
                make_item_dict("chinos"),
                make_item_dict("loafers"),
            ])
            counts = packing.get_counts(trip.id)
            assert counts["total"] == 3

    def test_packed_increments_on_check(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee"),
                make_item_dict("chinos"),
            ])
            item = PackingItem.query.filter_by(trip_id=trip.id).first()
            packing.toggle_checked(item.id, trip.id, True)
            counts = packing.get_counts(trip.id)
            assert counts["packed"] == 1
            assert counts["total"]  == 2

    def test_percent_computed_correctly(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee"),
                make_item_dict("chinos"),
                make_item_dict("loafers"),
                make_item_dict("sunglasses"),
            ])
            items = PackingItem.query.filter_by(trip_id=trip.id).all()
            # Check 2 of 4 items
            packing.toggle_checked(items[0].id, trip.id, True)
            packing.toggle_checked(items[1].id, trip.id, True)
            counts = packing.get_counts(trip.id)
            assert counts["percent"] == 50

    def test_total_pieces_sums_checked_quantities(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee", quantity=3),
                make_item_dict("chinos",     quantity=2),
            ])
            items = PackingItem.query.filter_by(trip_id=trip.id).all()
            packing.toggle_checked(items[0].id, trip.id, True)  # 3 pieces
            packing.toggle_checked(items[1].id, trip.id, True)  # 2 pieces
            counts = packing.get_counts(trip.id)
            assert counts["total_pieces"] == 5

# verify_trip_owner
class TestVerifyTripOwner:

    def test_session_owner_verified(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            assert packing.verify_trip_owner(trip.id, None, session.token) is True

    def test_wrong_session_denied(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            assert packing.verify_trip_owner(trip.id, None, "wrong-token") is False

    def test_no_owner_denied(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            assert packing.verify_trip_owner(trip.id, None, None) is False

    def test_nonexistent_trip_denied(self, app, db):
        with app.app_context():
            session = make_session(db)
            assert packing.verify_trip_owner(99999, None, session.token) is False


# get_category_summary

class TestGetCategorySummary:

    def test_returns_list(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [make_item_dict("fitted_tee", "tops")])
            result  = packing.get_category_summary(trip.id)
            assert isinstance(result, list)

    def test_summary_has_correct_counts(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee", "tops"),
                make_item_dict("linen_shirt","tops"),
                make_item_dict("chinos",     "bottoms"),
            ])
            result = packing.get_category_summary(trip.id)
            tops = next(r for r in result if r["category"] == "tops")
            assert tops["total"] == 2
            assert tops["packed"] == 0

    def test_packed_count_updates(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            packing.save_packing_list(trip.id, [
                make_item_dict("fitted_tee", "tops"),
                make_item_dict("linen_shirt","tops"),
            ])
            item = PackingItem.query.filter_by(trip_id=trip.id).first()
            packing.toggle_checked(item.id, trip.id, True)
            result = packing.get_category_summary(trip.id)
            tops   = next(r for r in result if r["category"] == "tops")
            assert tops["packed"] == 1

    def test_empty_trip_returns_empty_list(self, app, db):
        with app.app_context():
            session = make_session(db)
            trip    = make_trip(db, session.token)
            result  = packing.get_category_summary(trip.id)
            assert result == []