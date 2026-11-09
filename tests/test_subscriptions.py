"""Subscription CRUD, validation and per-user isolation."""

from __future__ import annotations

from datetime import date, timedelta

from tests.helpers import (
    create_subscription,
    csrf_token,
    login,
    logout,
    main_html,
    signup,
    subscription_id,
    subscription_row,
)

FUTURE = (date.today() + timedelta(days=10)).isoformat()


def test_create_subscription_appears_with_formatted_price_and_reminder(client):
    signup(client)
    response = create_subscription(
        client,
        name="Netflix",
        category="Streaming",
        price="15.49",
        currency="USD",
        billing_cycle="monthly",
        next_renewal_date=FUTURE,
        reminder_days="3",
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/subscriptions"

    listing = client.get("/subscriptions")
    assert listing.status_code == 200
    assert "15.49 USD / month" in main_html(listing)
    assert "Reminder: 3 days before" in main_html(listing)
    # it survives a fresh request (persisted, not in-memory)
    assert "15.49 USD / month" in main_html(client.get("/subscriptions"))


def test_create_form_defaults_make_it_submittable_in_one_pass(client):
    login(client)
    form = client.get("/subscriptions/new")
    assert form.status_code == 200
    assert 'value="monthly" selected' in form.text
    assert 'value="USD" selected' in form.text
    assert 'value="7" selected' in form.text
    # the renewal date is pre-filled 30 days out, so only name and price are blank
    expected = (date.today() + timedelta(days=30)).isoformat()
    assert f'value="{expected}"' in form.text


def test_create_form_validation_keeps_typed_values(client):
    login(client)
    response = create_subscription(
        client,
        name="",
        price="0",
        next_renewal_date="",
    )
    assert response.status_code == 400
    assert "Enter a name for this subscription." in response.text
    assert "Price must be greater than 0." in response.text
    assert "Enter the next renewal date." in response.text
    # the submitted price survives the failed submit
    assert 'value="0"' in response.text


def test_create_rejects_bad_price_precision_cycle_and_date(client):
    login(client)
    response = create_subscription(
        client,
        name="Bad data",
        price="15.499",
        billing_cycle="fortnightly",
        currency="XYZ",
        next_renewal_date="not-a-date",
    )
    assert response.status_code == 400
    assert "at most two decimals" in response.text
    assert "Choose weekly, monthly or yearly." in response.text
    assert "Choose a supported currency." in response.text
    assert "Enter a real date" in response.text


def test_price_upper_bound_is_rejected_gracefully(client):
    login(client)
    response = create_subscription(client, name="Absurd", price="9999999.00")
    assert response.status_code == 400
    assert "Price must be at most" in response.text
    assert subscription_row("Absurd") is None


def test_duplicate_names_are_rejected(client):
    signup(client)
    create_subscription(client, name="DupePlan")
    response = create_subscription(client, name="DupePlan")
    assert response.status_code == 400
    assert "You already track a subscription with this name." in response.text


def test_edit_updates_the_saved_price(client):
    login(client)
    create_subscription(client, name="Figma")
    sub_id = subscription_id("Figma")

    token = csrf_token(client, f"/subscriptions/{sub_id}/edit")
    response = client.post(
        f"/subscriptions/{sub_id}",
        data={
            "csrf_token": token,
            "name": "Figma",
            "category": "SaaS",
            "price": "19.00",
            "currency": "EUR",
            "billing_cycle": "yearly",
            "next_renewal_date": FUTURE,
            "reminder_days": "14",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/subscriptions"

    listing = client.get("/subscriptions")
    assert "19.00 EUR / year" in listing.text
    assert "Reminder: 14 days before" in listing.text
    stored = subscription_row("Figma")
    assert stored is not None and stored["price_cents"] == 1900


def test_edit_form_is_prefilled(client):
    login(client)
    create_subscription(client, name="Notion", price="9.60", category="SaaS")
    sub_id = subscription_id("Notion")
    form = client.get(f"/subscriptions/{sub_id}/edit")
    assert form.status_code == 200
    assert 'value="Notion"' in form.text
    assert 'value="9.60"' in form.text


def test_delete_removes_the_row(client):
    login(client)
    create_subscription(client, name="ToDelete")
    sub_id = subscription_id("ToDelete")
    token = csrf_token(client, "/subscriptions")
    response = client.post(
        f"/subscriptions/{sub_id}/delete",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "ToDelete" not in main_html(client.get("/subscriptions"))
    assert subscription_row("ToDelete") is None


def test_cancel_and_resume_round_trip(client):
    login(client)
    create_subscription(client, name="Gym")
    sub_id = subscription_id("Gym")

    token = csrf_token(client, "/subscriptions")
    client.post(f"/subscriptions/{sub_id}/cancel", data={"csrf_token": token}, follow_redirects=False)
    listing = client.get("/subscriptions")
    assert "Cancelled" in listing.text
    assert "Cancelled on" in listing.text
    stored = subscription_row("Gym")
    assert stored is not None and stored["status"] == "cancelled"
    assert stored["cancelled_at"] is not None

    token = csrf_token(client, "/subscriptions")
    client.post(f"/subscriptions/{sub_id}/resume", data={"csrf_token": token}, follow_redirects=False)
    stored = subscription_row("Gym")
    assert stored is not None and stored["status"] == "active"
    assert stored["cancelled_at"] is None


def test_another_account_cannot_read_or_mutate_my_subscription(client):
    login(client)
    create_subscription(client, name="Private")
    sub_id = subscription_id("Private")
    logout(client)

    email, response = signup(client)
    assert response.status_code == 302
    token = csrf_token(client, "/dashboard")

    # read path: edit form
    assert client.get(f"/subscriptions/{sub_id}/edit").status_code == 404
    # write path: cancel / resume / delete
    for action in ("cancel", "resume", "delete"):
        denied = client.post(
            f"/subscriptions/{sub_id}/{action}",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        assert denied.status_code == 404
    # my row is untouched and still visible to me
    logout(client)
    login(client)
    listing = client.get("/subscriptions")
    assert "Private" in main_html(listing)
    stored = subscription_row("Private")
    assert stored is not None and stored["status"] == "active"


def test_cancel_without_csrf_is_rejected_with_400(client):
    login(client)
    create_subscription(client, name="CsrfCancel")
    sub_id = subscription_id("CsrfCancel")
    response = client.post(
        f"/subscriptions/{sub_id}/cancel", data={}, follow_redirects=False
    )
    assert response.status_code == 400
    stored = subscription_row("CsrfCancel")
    assert stored is not None and stored["status"] == "active"


def test_missing_subscription_id_renders_the_friendly_404(client):
    login(client)
    response = client.get("/subscriptions/999999/edit")
    assert response.status_code == 404
    assert "Page not found" in response.text
    assert 'href="/subscriptions"' in response.text


def test_filter_by_status(client):
    login(client)
    create_subscription(client, name="FilterActive")
    create_subscription(client, name="FilterCancelled")
    sub_id = subscription_id("FilterCancelled")
    token = csrf_token(client, "/subscriptions")
    client.post(f"/subscriptions/{sub_id}/cancel", data={"csrf_token": token}, follow_redirects=False)

    cancelled = client.get("/subscriptions?status=cancelled")
    cancelled_body = main_html(cancelled)
    assert "FilterCancelled" in cancelled_body
    assert "FilterActive" not in cancelled_body
