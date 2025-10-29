from collections import namedtuple
from unittest import mock

from django.utils import timezone

import pytest
import requests_mock
from freezegun import freeze_time

from basket.news.backends import braze
from basket.news.backends.braze import Braze


@pytest.fixture
def braze_client():
    return braze.BrazeInterface("http://test.com", "test_api_key")


def test_braze_client_no_api_key():
    with pytest.warns(UserWarning, match="Braze API key is not configured"):
        braze_client = braze.BrazeInterface("http://test.com", "")
    assert braze_client.active is False
    assert braze_client.track_user("test@test.com") is None


def test_braze_client_no_base_url():
    with pytest.raises(ValueError):
        braze.BrazeInterface("", "test_api_key")


def test_braze_client_invalid_base_url():
    with pytest.raises(ValueError):
        braze.BrazeInterface("test.com", "test_api_key")


def test_braze_client_headers(braze_client):
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", json={})
        braze_client.track_user("test@test.com")
        assert m.last_request.headers["Content-Type"] == "application/json"
        assert m.last_request.headers["Authorization"] == "Bearer test_api_key"


def test_braze_track_user(braze_client):
    email = "test@test.com"
    expected = {
        "attributes": [
            {
                "_update_existing_only": False,
                "user_alias": {"alias_name": email, "alias_label": "email"},
                "email": email,
            }
        ],
    }
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", json={})
        braze_client.track_user(email)
        assert m.last_request.json() == expected


def test_braze_track_user_with_event(braze_client):
    dt = timezone.now()
    email = "test@test.com"
    expected = {
        "attributes": [
            {
                "_update_existing_only": False,
                "user_alias": {"alias_name": email, "alias_label": "email"},
                "email": email,
            },
        ],
        "events": [
            {
                "user_alias": {"alias_name": email, "alias_label": "email"},
                "name": "test_event",
                "time": dt.isoformat(),
            }
        ],
    }
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", json={})
        with freeze_time(dt):
            braze_client.track_user(email, "test_event")
        assert m.last_request.json() == expected


def test_braze_track_user_with_event_and_token(braze_client):
    dt = timezone.now()
    email = "test@test.com"
    expected = {
        "attributes": [
            {
                "_update_existing_only": False,
                "user_alias": {"alias_name": email, "alias_label": "email"},
                "email": email,
                "basket_token": "abc123",
            },
        ],
        "events": [
            {
                "user_alias": {"alias_name": email, "alias_label": "email"},
                "name": "test_event",
                "time": dt.isoformat(),
            }
        ],
    }
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", json={})
        with freeze_time(dt):
            braze_client.track_user(email, "test_event", user_data={"basket_token": "abc123"})
        assert m.last_request.json() == expected


def test_braze_track_user_with_event_and_token_and_email_id(braze_client):
    dt = timezone.now()
    email = "test@test.com"
    email_id = "fed654"
    expected = {
        "attributes": [
            {
                "external_id": "fed654",
                "email": email,
                "basket_token": "abc123",
            },
        ],
        "events": [
            {
                "external_id": "fed654",
                "name": "test_event",
                "time": dt.isoformat(),
            }
        ],
    }
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", json={})
        with freeze_time(dt):
            braze_client.track_user(email, "test_event", user_data={"basket_token": "abc123", "email_id": email_id})
        assert m.last_request.json() == expected


def test_braze_export_users(braze_client):
    email = "test@test.com"
    expected = {
        "user_aliases": [{"alias_name": email, "alias_label": "email"}],
        "email_address": email,
        "fields_to_export": ["external_id"],
    }
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/export/ids", json={})
        braze_client.export_users(email, ["external_id"])
        assert m.last_request.json() == expected


def test_get_user_subscriptions(braze_client):
    email = "test@test.com"
    external_id = ("fed654",)
    params = {
        "email": [email],
        "external_id": ["fed654"],
    }
    with requests_mock.mock() as m:
        m.register_uri("GET", "http://test.com/subscription/user/status", json={})
        braze_client.get_user_subscriptions(external_id, email)
        assert m.last_request.qs == params


def test_braze_save_user(braze_client):
    data = {"email": "test@test.com", "first_name": "foo", "last_name": "bar"}
    expected = data
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", json={})
        braze_client.save_user(data)
        assert m.last_request.json() == expected


def test_braze_send_campaign(braze_client):
    email = "test@test.com"
    campaign_id = "test_campaign_id"
    expected = {
        "campaign_id": campaign_id,
        "broadcast": False,
        "recipients": [
            {
                "user_alias": {
                    "alias_label": "email",
                    "alias_name": email,
                }
            },
        ],
    }
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/campaigns/trigger/send", json={})
        braze_client.send_campaign(email, campaign_id)
        assert m.last_request.json() == expected


def test_braze_delete_user(braze_client):
    email = "test@example.com"
    expected = {
        "email_addresses": [
            {
                "email": email,
                "prioritization": ["most_recently_updated"],
            },
        ]
    }
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/delete", json={})
        braze_client.delete_user(email)
        assert m.last_request.json() == expected


def test_braze_exception_400(braze_client):
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", status_code=400, json={})
        with pytest.raises(braze.BrazeBadRequestError):
            braze_client.track_user("test@test.com")


def test_braze_exception_401(braze_client):
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", status_code=401, json={})
        with pytest.raises(braze.BrazeUnauthorizedError):
            braze_client.track_user("test@test.com")


def test_braze_exception_403(braze_client):
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", status_code=403, json={})
        with pytest.raises(braze.BrazeForbiddenError):
            braze_client.track_user("test@test.com")


def test_braze_exception_404(braze_client):
    mock.patch("basket.news.backends.braze.BrazeEndpoint.USERS_TRACK", "/does/not/exist")
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", status_code=404, json={})
        with pytest.raises(braze.BrazeNotFoundError):
            braze_client.track_user("test@test.com")


def test_braze_exception_429(braze_client):
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", status_code=429, json={})
        with pytest.raises(braze.BrazeRateLimitError):
            braze_client.track_user("test@test.com")


def test_braze_exception_418(braze_client):
    # We aren't catching 418 teapot errors, so this should raise a generic BrazeClientError.
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", status_code=418, json={})
        with pytest.raises(braze.BrazeClientError):
            braze_client.track_user("test@test.com")


def test_braze_exception_500(braze_client):
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", status_code=500, json={})
        with pytest.raises(braze.BrazeInternalServerError):
            braze_client.track_user("test@test.com")


mock_basket_user_data = {
    "email": "test@example.com",
    "email_id": "123",
    "id": "456",
    "first_name": "Test",
    "last_name": "User",
    "country": "US",
    "lang": "en",
    "newsletters": ["foo-news"],
    "created_date": "2022-01-01",
    "last_modified_date": "2022-02-01",
    "optin": True,
    "optout": False,
    "token": "abc",
    "fxa_service": "test",
    "fxa_lang": "en",
    "fxa_primary_email": "test2@example.com",
    "fxa_create_date": "2022-01-02",
}

mock_braze_user_data = {
    "email": "test@example.com",
    "external_id": "123",
    "braze_id": "456",
    "first_name": "Test",
    "last_name": "User",
    "country": "US",
    "language": "en",
    "email_subscribe": "opted_in",
    "custom_attributes": {
        "user_attributes_v1": [
            {
                "mailing_country": "us",
                "email_lang": "en",
                "created_at": "2022-01-01",
                "updated_at": "2022-02-01",
                "basket_token": "abc",
                "fxa_first_service": "test",
                "fxa_lang": "en",
                "fxa_primary_email": "test2@example.com",
                "fxa_created_at": "2022-01-02",
                "has_fxa": True,
            }
        ]
    },
}

mock_braze_user_subscription_groups = [
    {"id": "234c9b4a-1785-4cd5-b839-5dbc134982eb", "status": "Subscribed"},
    {"id": "78fe6671-9f94-48bd-aaf3-7e873536c3e6", "status": "Unsubscribed"},
]

mock_newsletters = {
    "by_vendor_id": {
        "234c9b4a-1785-4cd5-b839-5dbc134982eb": namedtuple("Newsletter", ["slug"])("foo-news"),
        "78fe6671-9f94-48bd-aaf3-7e873536c3e6": namedtuple("Newsletter", ["slug"])("bar-news"),
    },
    "by_name": {
        "foo-news": namedtuple("Newsletter", ["vendor_id"])("234c9b4a-1785-4cd5-b839-5dbc134982eb"),
        "bar-news": namedtuple("Newsletter", ["vendor_id"])("78fe6671-9f94-48bd-aaf3-7e873536c3e6"),
    },
}


@mock.patch(
    "basket.news.newsletters._newsletters",
    return_value=mock_newsletters,
)
def test_from_vendor(braze_client):
    braze_instance = Braze(braze_client)

    assert braze_instance.from_vendor(mock_braze_user_data, mock_braze_user_subscription_groups) == mock_basket_user_data


@mock.patch(
    "basket.news.newsletters._newsletters",
    return_value=mock_newsletters,
)
@mock.patch(
    "basket.news.newsletters.newsletter_languages",
    return_value=["en"],
)
def test_to_vendor_with_user_data_and_no_updates(mock_newsletter_languages, mock_newsletters, braze_client):
    braze_instance = Braze(braze_client)
    dt = timezone.now()
    expected = {
        "attributes": [
            {
                "_update_existing_only": True,
                "email": "test@example.com",
                "external_id": "123",
                "email_subscribe": "opted_in",
                "subscription_groups": [],
                "update_timestamp": dt.isoformat(),
                "user_attributes_v1": [
                    {
                        "mailing_country": "us",
                        "email_lang": "en",
                        "created_at": {
                            "$time": "2022-01-01",
                        },
                        "basket_token": "abc",
                        "fxa_first_service": "test",
                        "fxa_lang": "en",
                        "fxa_primary_email": "test2@example.com",
                        "fxa_created_at": "2022-01-02",
                        "has_fxa": True,
                        "updated_at": {
                            "$time": dt.isoformat(),
                        },
                    }
                ],
            }
        ]
    }
    with freeze_time(dt):
        assert braze_instance.to_vendor(mock_basket_user_data) == expected


@mock.patch(
    "basket.news.newsletters._newsletters",
    return_value=mock_newsletters,
)
@mock.patch(
    "basket.news.newsletters.newsletter_languages",
    return_value=["en"],
)
def test_to_vendor_with_updates_and_no_user_data(mock_newsletter_languages, mock_newsletters, braze_client):
    braze_instance = Braze(braze_client)
    dt = timezone.now()
    update_data = {"newsletters": {"bar-news": True}, "email": "test@example.com", "token": "abc", "email_id": "123"}
    expected = {
        "attributes": [
            {
                "_update_existing_only": True,
                "email": "test@example.com",
                "external_id": "123",
                "email_subscribe": "subscribed",
                "subscription_groups": [
                    {"subscription_group_id": "78fe6671-9f94-48bd-aaf3-7e873536c3e6", "subscription_state": "subscribed"},
                ],
                "update_timestamp": dt.isoformat(),
                "user_attributes_v1": [
                    {
                        "email_lang": "en",
                        "created_at": {
                            "$time": dt.isoformat(),
                        },
                        "basket_token": "abc",
                        "fxa_first_service": None,
                        "fxa_lang": None,
                        "fxa_primary_email": None,
                        "fxa_created_at": None,
                        "has_fxa": False,
                        "mailing_country": None,
                        "updated_at": {
                            "$time": dt.isoformat(),
                        },
                    }
                ],
            }
        ]
    }
    with freeze_time(dt):
        assert braze_instance.to_vendor(None, update_data) == expected


@mock.patch(
    "basket.news.newsletters._newsletters",
    return_value=mock_newsletters,
)
@mock.patch(
    "basket.news.newsletters.newsletter_languages",
    return_value=["en"],
)
def test_to_vendor_with_both_user_data_and_updates(mock_newsletter_languages, mock_newsletters, braze_client):
    braze_instance = Braze(braze_client)
    dt = timezone.now()
    update_data = {"newsletters": {"bar-news": True, "foo-news": False}, "first_name": "Foo", "country": "CA", "optin": False}
    expected = {
        "attributes": [
            {
                "_update_existing_only": True,
                "email": "test@example.com",
                "external_id": "123",
                "email_subscribe": "subscribed",
                "first_name": "Foo",
                "country": "ca",
                "subscription_groups": [
                    {"subscription_group_id": "78fe6671-9f94-48bd-aaf3-7e873536c3e6", "subscription_state": "subscribed"},
                    {"subscription_group_id": "234c9b4a-1785-4cd5-b839-5dbc134982eb", "subscription_state": "unsubscribed"},
                ],
                "update_timestamp": dt.isoformat(),
                "user_attributes_v1": [
                    {
                        "mailing_country": "ca",
                        "email_lang": "en",
                        "created_at": {
                            "$time": "2022-01-01",
                        },
                        "basket_token": "abc",
                        "fxa_first_service": "test",
                        "fxa_lang": "en",
                        "fxa_primary_email": "test2@example.com",
                        "fxa_created_at": "2022-01-02",
                        "has_fxa": True,
                        "updated_at": {
                            "$time": dt.isoformat(),
                        },
                    }
                ],
            }
        ]
    }
    with freeze_time(dt):
        assert braze_instance.to_vendor(mock_basket_user_data, update_data) == expected


@mock.patch(
    "basket.news.newsletters._newsletters",
    return_value=mock_newsletters,
)
@mock.patch(
    "basket.news.newsletters.newsletter_languages",
    return_value=["en"],
)
def test_to_vendor_with_custom_attributes_and_events(mock_newsletters, braze_client):
    braze_instance = Braze(braze_client)
    dt = timezone.now()
    events = [
        {
            "name": "test event",
            "time": dt,
            "external_id": "123",
        }
    ]
    expected = {
        "attributes": [
            {
                "_update_existing_only": False,
                "email": "test@example.com",
                "external_id": "123",
                "email_subscribe": "opted_in",
                "subscription_groups": [],
                "update_timestamp": dt.isoformat(),
                "user_attributes_v1": [
                    {
                        "mailing_country": "us",
                        "email_lang": "en",
                        "created_at": {
                            "$time": "2022-01-01",
                        },
                        "basket_token": "abc",
                        "fxa_first_service": "test",
                        "fxa_lang": "en",
                        "fxa_primary_email": "test2@example.com",
                        "fxa_created_at": "2022-01-02",
                        "has_fxa": True,
                        "updated_at": {
                            "$time": dt.isoformat(),
                        },
                    }
                ],
            }
        ],
        "events": events,
    }
    with freeze_time(dt):
        assert (
            braze_instance.to_vendor(
                basket_user_data=mock_basket_user_data, update_data=None, custom_attributes={"_update_existing_only": False}, events=events
            )
            == expected
        )


@mock.patch(
    "basket.news.newsletters._newsletters",
    return_value=mock_newsletters,
)
def test_braze_get(mock_newsletters, braze_client):
    email = mock_braze_user_data["email"]
    braze_instance = Braze(braze_client)
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/export/ids", json={"users": [mock_braze_user_data]})
        m.register_uri(
            "GET", "http://test.com/subscription/user/status", json={"users": [{"subscription_groups": mock_braze_user_subscription_groups}]}
        )
        assert braze_instance.get(email=email) == mock_basket_user_data

        api_requests = m.request_history
        assert api_requests[0].url == "http://test.com/users/export/ids"
        assert api_requests[0].json() == {
            "email_address": email,
            "fields_to_export": [
                "braze_id",
                "country",
                "created_at",
                "custom_attributes",
                "email",
                "email_subscribe",
                "external_id",
                "first_name",
                "language",
                "last_name",
            ],
            "user_aliases": [
                {
                    "alias_label": "email",
                    "alias_name": email,
                },
            ],
        }
        assert api_requests[1].url == "http://test.com/subscription/user/status?external_id=123&email=test%40example.com"


@mock.patch(
    "basket.news.newsletters._newsletters",
    return_value=mock_newsletters,
)
def test_braze_add(mock_newsletters, braze_client):
    braze_instance = Braze(braze_client)
    new_user = {
        "email": "test@example.com",
        "email_id": "123",
        "basket_token": "abc",
        "newsletters": {"foo-news": True},
        "country": "US",
    }
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", json={})
        expected = {"email": {"email_id": new_user["email_id"]}}
        with freeze_time():
            response = braze_instance.add(new_user)
            assert response == expected
            assert m.last_request.json() == braze_instance.to_vendor(None, new_user, {"_update_existing_only": False})


@mock.patch(
    "basket.news.newsletters._newsletters",
    return_value=mock_newsletters,
)
@mock.patch(
    "basket.news.newsletters.newsletter_languages",
    return_value=["en"],
)
def test_braze_update(mock_newsletter_languages, mock_newsletters, braze_client):
    braze_instance = Braze(braze_client)
    update_data = {"country": "CA"}
    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/track", json={})
        with freeze_time():
            braze_instance.update(mock_basket_user_data, update_data)
            assert m.last_request.json() == braze_instance.to_vendor(mock_basket_user_data, update_data)


def test_braze_delete(braze_client):
    braze_instance = Braze(braze_client)
    email = mock_braze_user_data["email"]
    expected = [{"email_id": mock_braze_user_data["external_id"]}]

    with requests_mock.mock() as m:
        m.register_uri("POST", "http://test.com/users/export/ids", json={"users": [{"external_id": mock_braze_user_data["external_id"]}]})
        m.register_uri("POST", "http://test.com/users/delete", json={})
        response = braze_instance.delete(email)
        api_requests = m.request_history
        assert api_requests[0].url == "http://test.com/users/export/ids"
        assert api_requests[1].url == "http://test.com/users/delete"
        assert response == expected
