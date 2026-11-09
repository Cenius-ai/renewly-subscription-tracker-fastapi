"""Auth contract: sign-up, sign-in, session persistence, CSRF and logout."""

from __future__ import annotations

from tests.helpers import (
    DEMO_EMAIL,
    DEMO_PASSWORD,
    csrf_token,
    login,
    logout,
    signup,
)

GENERIC_ERROR = "Email or password is incorrect."


def test_root_redirects_anonymous_visitor_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login")


def test_login_page_shows_demo_credentials(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Demo: cenius@cenius.ai / cenius" in response.text
    assert 'action="/login"' in response.text


def test_login_with_demo_account_reaches_dashboard(client):
    response = login(client)
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert DEMO_EMAIL in dashboard.text
    assert "Log out" in dashboard.text
    assert "This month" in dashboard.text


def test_session_survives_another_page_load(client):
    login(client)
    assert client.get("/subscriptions").status_code == 200
    assert client.get("/dashboard").status_code == 200


def test_wrong_password_shows_one_generic_error_and_keeps_email(client):
    response = login(client, password="wrong-password")
    assert response.status_code == 400
    assert GENERIC_ERROR in response.text
    # the typed email is preserved, the password is not echoed
    assert f'value="{DEMO_EMAIL}"' in response.text
    assert "wrong-password" not in response.text


def test_logout_clears_the_session(client):
    login(client)
    logout(client)
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login")


def test_signed_in_visitor_is_redirected_away_from_login_and_signup(client):
    login(client)
    for path in ("/login", "/signup"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"


def test_signup_validation_errors_are_inline_and_keep_the_email(client):
    token = csrf_token(client, "/signup")
    response = client.post(
        "/signup",
        data={
            "csrf_token": token,
            "email": "keeper@example.com",
            "password": "short",
            "confirm_password": "different",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Use at least 8 characters." in response.text
    assert "Passwords do not match." in response.text
    assert 'value="keeper@example.com"' in response.text
    assert "short" not in response.text.split('name="password"')[1].split("<")[0]


def test_signup_rejects_invalid_email_shape(client):
    token = csrf_token(client, "/signup")
    response = client.post(
        "/signup",
        data={
            "csrf_token": token,
            "email": "not-an-email",
            "password": "sunshine123",
            "confirm_password": "sunshine123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Enter a valid email address." in response.text


def test_signup_creates_account_and_signs_in(client):
    email, response = signup(client)
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert email in dashboard.text


def test_signup_rejects_an_email_that_is_already_registered(client):
    email, _ = signup(client)
    logout(client)
    token = csrf_token(client, "/signup")
    response = client.post(
        "/signup",
        data={
            "csrf_token": token,
            "email": email,
            "password": "sunshine123",
            "confirm_password": "sunshine123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "An account with this email already exists." in response.text


def test_state_changing_posts_without_csrf_are_rejected(client):
    # login attempt without a CSRF token
    response = client.post(
        "/login",
        data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Your session expired" in response.text

    # sign-up without a CSRF token never writes an account
    response = client.post(
        "/signup",
        data={
            "email": "csrf-probe@example.com",
            "password": "sunshine123",
            "confirm_password": "sunshine123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400

    # a subscription create without a CSRF token never writes a row
    login(client)
    response = client.post(
        "/subscriptions",
        data={
            "name": "NoToken",
            "category": "Other",
            "price": "1.00",
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_renewal_date": "2030-01-01",
            "reminder_days": "7",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    listing = client.get("/subscriptions")
    assert "NoToken" not in listing.text
