# -*- coding: utf-8 -*-
import hashlib
import json
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_PATCH = "odoo.addons.account_partner_api.controllers.main.request"
_PATCH_RESP = "odoo.addons.account_partner_api.controllers.main.Response"


class _FakeResponse:
    """
    Minimal stand-in for odoo.http.Response that does NOT touch the werkzeug
    request local proxy, so it can be used safely inside TransactionCase tests.
    """

    def __init__(self, body, status=200, content_type=None):
        self.data = body.encode() if isinstance(body, str) else body
        self.status_code = status
        self.content_type = content_type


def _body(response):
    """Return the parsed JSON body of a _FakeResponse."""
    return json.loads(response.data)


# ──────────────────────────────────────────────────────────────────────────────
# api.key model tests
# ──────────────────────────────────────────────────────────────────────────────

@tagged("-at_install", "post_install")
class TestApiKeyModel(TransactionCase):
    """Unit tests for the api.key model (criterion: keys hashed, is_active)."""

    def test_plain_key_is_hashed_on_write(self):
        plain = "my-super-secret-key"
        record = self.env["api.key"].create(
            {"client_name": "TestClient", "key_plain": plain}
        )
        expected = hashlib.sha256(plain.encode()).hexdigest()
        self.assertEqual(record.key_hash, expected)

    def test_plain_key_is_not_readable(self):
        record = self.env["api.key"].create(
            {"client_name": "TestClient", "key_plain": "secret"}
        )
        # After creation the ORM cache still holds the written value;
        # invalidate it so _compute_key_plain runs and returns False.
        record.invalidate_cache(fnames=["key_plain"], ids=[record.id])
        self.assertFalse(record.key_plain)

    def test_is_active_defaults_to_true(self):
        record = self.env["api.key"].create({"client_name": "TestClient"})
        self.assertTrue(record.is_active)

    def test_revoke_sets_is_active_false(self):
        record = self.env["api.key"].create(
            {"client_name": "TestClient", "is_active": True}
        )
        record.is_active = False
        self.assertFalse(record.is_active)

    def test_empty_plain_key_does_not_overwrite_existing_hash(self):
        plain = "original-key"
        record = self.env["api.key"].create(
            {"client_name": "TestClient", "key_plain": plain}
        )
        original_hash = record.key_hash
        # Writing an empty key_plain must not erase the stored hash
        record.write({"key_plain": ""})
        self.assertEqual(record.key_hash, original_hash)


# ──────────────────────────────────────────────────────────────────────────────
# Controller tests
# ──────────────────────────────────────────────────────────────────────────────


@tagged("-at_install", "post_install")
class TestOdooDataApiController(TransactionCase):
    """
    Unit tests for OdooDataApiController.

    Uses unittest.mock to inject a fake ``request`` and a ``_FakeResponse`` so
    the controller methods can be called directly without a running HTTP server.
    """

    def setUp(self):
        super().setUp()
        # Replace odoo.http.Response with _FakeResponse for all tests in this
        # class so _json_response() never touches the werkzeug request proxy.
        resp_patcher = patch(_PATCH_RESP, _FakeResponse)
        resp_patcher.start()
        self.addCleanup(resp_patcher.stop)

        # Fresh api.key per test so last_used_at always starts at False
        self.plain_key = "test-api-key-for-controller-unit-tests"
        key_hash = hashlib.sha256(self.plain_key.encode()).hexdigest()
        self.api_key = self.env["api.key"].create(
            {
                "client_name": "Test Client",
                "key_hash": key_hash,
                "is_active": True,
            }
        )
        from odoo.addons.account_partner_api.controllers.main import (
            OdooDataApiController,
        )
        self.controller = OdooDataApiController()

    def _mock_request(self, api_key=None):
        """Return a mock ``request`` with the given X-API-Key header value."""
        mock_req = MagicMock()
        mock_req.env = self.env
        mock_req.httprequest.headers.get.side_effect = (
            lambda header, default=None: api_key if header == "X-API-Key" else default
        )
        return mock_req

    # ── Authentication — list endpoint ────────────────────────────────────────

    def test_list_missing_key_returns_401(self):
        with patch(_PATCH, self._mock_request()):
            resp = self.controller.get_model_records("res.partner")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(_body(resp)["error"], "Unauthorized")

    def test_list_invalid_key_returns_401(self):
        with patch(_PATCH, self._mock_request("completely-wrong-key")):
            resp = self.controller.get_model_records("res.partner")
        self.assertEqual(resp.status_code, 401)

    def test_list_inactive_key_returns_401(self):
        self.api_key.is_active = False
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_records("res.partner")
        self.assertEqual(resp.status_code, 401)

    # ── Authentication — detail endpoint ─────────────────────────────────────

    def test_detail_missing_key_returns_401(self):
        with patch(_PATCH, self._mock_request()):
            resp = self.controller.get_model_record_by_id("res.partner", 1)
        self.assertEqual(resp.status_code, 401)

    def test_detail_invalid_key_returns_401(self):
        with patch(_PATCH, self._mock_request("bad-key")):
            resp = self.controller.get_model_record_by_id("res.partner", 1)
        self.assertEqual(resp.status_code, 401)

    # ── Model whitelist (criterion 7: must return 400) ────────────────────────

    def test_list_disallowed_model_returns_400(self):
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_records("sale.order")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(_body(resp)["error"], "Bad Request")

    def test_detail_disallowed_model_returns_400(self):
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_record_by_id("sale.order", 1)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(_body(resp)["error"], "Bad Request")

    # ── Happy paths — all 3 allowed models ───────────────────────────────────

    def test_list_res_partner_returns_200(self):
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_records("res.partner", limit="5")
        self.assertEqual(resp.status_code, 200)
        data = _body(resp)
        self.assertIn("total", data)
        self.assertIn("records", data)
        self.assertLessEqual(len(data["records"]), 5)

    def test_list_account_move_returns_200(self):
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_records("account.move", limit="2")
        self.assertEqual(resp.status_code, 200)

    def test_list_account_tax_returns_200(self):
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_records("account.tax", limit="2")
        self.assertEqual(resp.status_code, 200)

    def test_detail_valid_id_returns_200(self):
        partner = self.env["res.partner"].sudo().search([], limit=1)
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_record_by_id("res.partner", partner.id)
        self.assertEqual(resp.status_code, 200)
        data = _body(resp)
        self.assertEqual(data["id"], partner.id)
        self.assertEqual(data["model"], "res.partner")
        self.assertIn("record", data)

    # ── 404 ───────────────────────────────────────────────────────────────────

    def test_detail_not_found_returns_404(self):
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_record_by_id("res.partner", 999_999_999)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(_body(resp)["error"], "Not Found")

    # ── Pagination ────────────────────────────────────────────────────────────

    def test_pagination_limit_and_offset_reflected_in_response(self):
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_records(
                "res.partner", limit="3", offset="0"
            )
        self.assertEqual(resp.status_code, 200)
        data = _body(resp)
        self.assertEqual(data["limit"], 3)
        self.assertEqual(data["offset"], 0)
        self.assertLessEqual(len(data["records"]), 3)

    def test_negative_limit_returns_400(self):
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_records("res.partner", limit="-1")
        self.assertEqual(resp.status_code, 400)

    def test_non_integer_limit_returns_400(self):
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_records("res.partner", limit="abc")
        self.assertEqual(resp.status_code, 400)

    # ── Domain filter ─────────────────────────────────────────────────────────

    def test_valid_domain_returns_200(self):
        domain = json.dumps([["id", ">", 0]])
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_records(
                "res.partner", limit="2", domain=domain
            )
        self.assertEqual(resp.status_code, 200)

    def test_invalid_domain_json_returns_400(self):
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_records(
                "res.partner", domain="not-valid-json"
            )
        self.assertEqual(resp.status_code, 400)

    def test_non_list_domain_returns_400(self):
        with patch(_PATCH, self._mock_request(self.plain_key)):
            resp = self.controller.get_model_records(
                "res.partner", domain='"just-a-string"'
            )
        self.assertEqual(resp.status_code, 400)

    # ── last_used_at ──────────────────────────────────────────────────────────

    def test_last_used_at_updated_on_valid_request(self):
        self.assertFalse(self.api_key.last_used_at)
        with patch(_PATCH, self._mock_request(self.plain_key)):
            self.controller.get_model_records("res.partner", limit="1")
        self.api_key.invalidate_cache()
        self.assertTrue(self.api_key.last_used_at)

    def test_last_used_at_not_updated_on_invalid_key(self):
        with patch(_PATCH, self._mock_request("wrong-key")):
            self.controller.get_model_records("res.partner", limit="1")
        self.api_key.invalidate_cache()
        self.assertFalse(self.api_key.last_used_at)
