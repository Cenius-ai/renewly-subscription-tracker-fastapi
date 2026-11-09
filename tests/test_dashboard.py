"""Dashboard maths: totals, category breakdown, renewals and savings."""

from __future__ import annotations

from datetime import date, timedelta

from tests.helpers import (
    create_subscription,
    csrf_token,
    login,
    main_html,
    signup,
    subscription_id,
)


def test_monthly_and_yearly_totals_normalise_mixed_cycles(client):
    signup(client)
    create_subscription(
        client,
        name="MonthlyPlan",
        price="15.49",
        currency="USD",
        billing_cycle="monthly",
    )
    create_subscription(
        client,
        name="YearlyPlan",
        price="120.00",
        currency="USD",
        billing_cycle="yearly",
    )
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    # 15.49 + 120/12 = 25.49 per month; 305.88 per year
    assert "25.49" in dashboard.text
    assert "305.88" in dashboard.text
    assert "USD" in dashboard.text


def test_weekly_price_is_normalised_to_monthly(client):
    signup(client)
    create_subscription(
        client,
        name="WeeklyPlan",
        price="10.00",
        currency="USD",
        billing_cycle="weekly",
    )
    dashboard = client.get("/dashboard")
    # 10.00 * 52 / 12 = 43.33 per month, 520.00 per year
    assert "43.33" in dashboard.text
    assert "520.00" in dashboard.text


def test_upcoming_renewal_shows_the_countdown(client):
    signup(client)
    create_subscription(
        client,
        name="SoonPlan",
        price="9.99",
        currency="USD",
        next_renewal_date=(date.today() + timedelta(days=3)).isoformat(),
        reminder_days="7",
    )
    dashboard = client.get("/dashboard")
    assert "Upcoming renewals" in dashboard.text
    assert "SoonPlan" in dashboard.text
    assert "in 3 days" in dashboard.text


def test_renewal_outside_its_lead_time_is_not_upcoming(client):
    signup(client)
    create_subscription(
        client,
        name="LaterPlan",
        price="9.99",
        currency="USD",
        next_renewal_date=(date.today() + timedelta(days=20)).isoformat(),
        reminder_days="7",
    )
    dashboard = client.get("/dashboard")
    assert "LaterPlan" not in main_html(dashboard)


def test_stale_renewal_date_is_rolled_forward_not_dropped(client):
    signup(client)
    two_months_ago = date.today().replace(day=1) - timedelta(days=45)
    create_subscription(
        client,
        name="StaleMonthly",
        price="12.00",
        currency="USD",
        billing_cycle="monthly",
        next_renewal_date=two_months_ago.isoformat(),
        reminder_days="30",
    )
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "StaleMonthly" in dashboard.text
    assert "rolled forward" in dashboard.text
    # a rolled-forward date is never in the past
    assert "overdue by -" not in dashboard.text


def test_cancelled_subscription_leaves_spend_and_joins_savings(client):
    email, _ = signup(client)
    create_subscription(client, name="KeepPlan", price="10.00", currency="USD")
    create_subscription(
        client,
        name="DropPlan",
        price="6.00",
        currency="EUR",
        next_renewal_date=(date.today() + timedelta(days=2)).isoformat(),
        reminder_days="7",
    )
    sub_id = subscription_id("DropPlan", email=email)
    dashboard_before = client.get("/subscriptions")
    assert "DropPlan" in dashboard_before.text

    token = csrf_token(client, "/subscriptions")
    client.post(f"/subscriptions/{sub_id}/cancel", data={"csrf_token": token}, follow_redirects=False)

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Saved by cancelling" in dashboard.text
    assert "6.00 EUR" in dashboard.text
    assert "72.00 EUR" in dashboard.text
    # cancelled row is not in upcoming renewals
    upcoming = main_html(client.get("/dashboard")).split("Upcoming renewals")[1].split("Spend by category")[0]
    assert "DropPlan" not in upcoming


def test_empty_account_shows_zeroed_cards_and_invites_first_subscription(client):
    signup(client)
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "0.00" in dashboard.text
    assert "Add your first subscription" in dashboard.text
    assert "Nothing cancelled yet" in dashboard.text

    listing = client.get("/subscriptions")
    assert "No subscriptions yet" in listing.text
    assert "Add your first subscription" in listing.text


def test_category_breakdown_lists_each_category(client):
    signup(client)
    create_subscription(client, name="StreamCo", category="Streaming", price="10.00", currency="USD")
    create_subscription(client, name="SaaSCo", category="SaaS", price="20.00", currency="USD")
    dashboard = client.get("/dashboard")
    assert "Spend by category" in dashboard.text
    assert "Streaming" in dashboard.text
    assert "SaaS" in dashboard.text
    assert "USD / mo" in dashboard.text
    assert "USD / yr" in dashboard.text


def test_seeded_demo_dashboard_is_populated(client):
    login(client)
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Netflix" in dashboard.text  # upcoming renewals
    assert "Saved by cancelling" in dashboard.text
    assert "Dropbox Plus" in dashboard.text or "11.99 USD" in dashboard.text
    # multiple currencies are grouped, not converted
    assert "USD" in dashboard.text and "GBP" in dashboard.text
