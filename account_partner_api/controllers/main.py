# -*- coding: utf-8 -*-
import datetime
import hashlib
import json
import logging

from odoo import fields, http
from odoo.addons.datareader_customer_receipts.utils.cuit_alias import normalize_text
from odoo.http import Response, request

_logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Whitelist of Odoo models that can be queried through this API.
# Add new models here when needed.
# ──────────────────────────────────────────────────────────────────────────────
ALLOWED_MODELS = frozenset(
    {
        "res.partner",
        "account.move",
        "account.tax",
    }
)

# ──────────────────────────────────────────────────────────────────────────────
# OpenAPI 3.0 specification — served at GET /api/odoo/openapi.json
# ──────────────────────────────────────────────────────────────────────────────
_OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Account Partner API",
        "description": (
            "REST API protegida por API Key para consultar socios, "
            "facturas e impuestos en Odoo 15."
        ),
        "version": "1.0.0",
    },
    "components": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": (
                    "Clave registrada en Ajustes → API Keys. "
                    "Se almacena como SHA-256; la clave en texto plano nunca se persiste."
                ),
            }
        },
        "schemas": {
            "Error": {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "example": "Unauthorized"},
                    "message": {"type": "string"},
                },
            },
            "ListResponse": {
                "type": "object",
                "required": ["total", "limit", "offset", "records"],
                "properties": {
                    "total": {"type": "integer", "example": 142},
                    "limit": {"type": "integer", "example": 80},
                    "offset": {"type": "integer", "example": 0},
                    "records": {"type": "array", "items": {"type": "object"}},
                },
            },
            "RecordResponse": {
                "type": "object",
                "required": ["id", "model", "record"],
                "properties": {
                    "id": {"type": "integer", "example": 1},
                    "model": {"type": "string", "example": "res.partner"},
                    "record": {"type": "object"},
                },
            },
        },
    },
    "security": [{"ApiKeyAuth": []}],
    "paths": {
        "/api/odoo/{model}": {
            "get": {
                "summary": "Listar registros",
                "description": "Retorna una lista paginada de registros del modelo indicado.",
                "operationId": "listRecords",
                "parameters": [
                    {
                        "name": "model",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "enum": sorted(ALLOWED_MODELS)},
                        "description": "Nombre técnico del modelo Odoo.",
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 80, "minimum": 0},
                        "description": "Máximo de registros a retornar.",
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "schema": {"type": "integer", "default": 0, "minimum": 0},
                        "description": "Registros a saltar (paginación).",
                    },
                    {
                        "name": "fields",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": "Campos separados por coma. Omitir para todos.",
                        "example": "id,name,email",
                    },
                    {
                        "name": "domain",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": 'Dominio Odoo en JSON. Ej: [["active","=",true]]',
                    },
                    {
                        "name": "alias",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": "Solo res.partner. Nombre o alias registrado en normalized.text.",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Lista de registros.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ListResponse"}}},
                    },
                    "400": {
                        "description": "Parámetros inválidos o modelo no permitido.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                    },
                    "401": {
                        "description": "API Key ausente o inválida.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                    },
                    "500": {
                        "description": "Error interno.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                    },
                },
            }
        },
        "/api/odoo/{model}/{id}": {
            "get": {
                "summary": "Obtener un registro por ID",
                "operationId": "getRecordById",
                "parameters": [
                    {
                        "name": "model",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "enum": sorted(ALLOWED_MODELS)},
                        "description": "Nombre técnico del modelo Odoo.",
                    },
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "description": "ID del registro.",
                    },
                    {
                        "name": "fields",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": "Campos separados por coma. Omitir para todos.",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Registro encontrado.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/RecordResponse"}}},
                    },
                    "400": {
                        "description": "Modelo no permitido.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                    },
                    "401": {
                        "description": "API Key ausente o inválida.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                    },
                    "404": {
                        "description": "Registro no encontrado.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                    },
                    "500": {
                        "description": "Error interno.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                    },
                },
            }
        },
    },
}


class _OdooJsonEncoder(json.JSONEncoder):
    """
    Extended JSON encoder that handles types returned by Odoo's search_read.

    Handles:
    - ``datetime.datetime`` / ``datetime.date`` → ISO-8601 string.
    - Odoo's ``False`` for empty Many2one fields is already handled
      natively by the standard encoder (serialised as ``false``).
    """

    def default(self, obj):
        """Serialize additional types not covered by the base encoder."""
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        return super().default(obj)


def _json_response(data: dict, status: int = 200) -> Response:
    """
    Build a Werkzeug Response with JSON content type.

    Parameters:
        data (dict): Payload to serialize.
        status (int): HTTP status code. Default: 200.

    Returns:
        Response: HTTP response ready to be returned from a controller.
    """
    body = json.dumps(data, cls=_OdooJsonEncoder)
    return Response(body, status=status, content_type="application/json")


class OdooDataApiController(http.Controller):
    """
    REST-like API controller for querying Odoo model data.

    All endpoints require a valid ``X-API-Key`` header whose value
    matches an active record in the ``api.key`` table (comparison is
    done against the stored SHA-256 hash; the plain key is never stored).
    """

    # ──────────────────────────────────────────────────────────────────────────
    # Authentication helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _get_api_model(self, model_name: str):
        """Return model env configured for API reads.

        Uses ``sudo()`` and disables ``active_test`` to avoid implicit filtering
        of archived records when requests come from public/no-session contexts.
        """
        return request.env[model_name].with_context(active_test=False).sudo()

    def _get_partner_aliases_map(self, partner_ids: list) -> dict:
        """
        Build a mapping of ``res.partner`` id -> list of registered aliases.

        Aliases come from ``normalized.text.items`` through ``normalized.text``.
        Rows repeating both name and normalized name are collapsed.

        Returns:
            dict: ``{partner_id: [{"item_name": str, "normalized_name": str}, ...]}``
        """
        if not partner_ids:
            return {}

        normalized_texts = (
            request.env["normalized.text"]
            .sudo()
            .search_read(
                [("res_partner_id", "in", partner_ids)],
                fields=["res_partner_id"],
            )
        )
        if not normalized_texts:
            return {}

        partner_by_normalized_id = {
            nt["id"]: nt["res_partner_id"][0] for nt in normalized_texts
        }
        items = (
            request.env["normalized.text.items"]
            .sudo()
            .search_read(
                [("normalized_id", "in", list(partner_by_normalized_id.keys()))],
                fields=["name", "normalized_name", "normalized_id"],
            )
        )

        aliases_map: dict = {}
        seen = set()
        for item in items:
            partner_id = partner_by_normalized_id.get(item["normalized_id"][0])
            if partner_id is None:
                continue
            key = (partner_id, item["name"], item["normalized_name"])
            if key in seen:
                continue
            seen.add(key)
            aliases_map.setdefault(partner_id, []).append(
                {
                    "item_name": item["name"],
                    "normalized_name": item["normalized_name"],
                }
            )
        return aliases_map

    def _partner_ids_by_alias(self, alias: str) -> list:
        """
        Resolve a raw alias string to the ids of the linked ``res.partner``.

        Matches ``normalized.text.items`` by ``name`` (the alias as it was
        registered) or by ``normalized_name`` (normalized server-side), so the
        caller may send the text in either form.
        """
        items = (
            request.env["normalized.text.items"]
            .sudo()
            .search_read(
                [
                    "|",
                    ("name", "=ilike", alias),
                    ("normalized_name", "=", normalize_text(alias)),
                    ("normalized_id.res_partner_id", "!=", False),
                ],
                fields=["normalized_id"],
            )
        )
        if not items:
            return []

        normalized_texts = (
            request.env["normalized.text"]
            .sudo()
            .search_read(
                [("id", "in", [i["normalized_id"][0] for i in items])],
                fields=["res_partner_id"],
            )
        )
        return [
            nt["res_partner_id"][0]
            for nt in normalized_texts
            if nt["res_partner_id"]
        ]

    def _authenticate(self):
        """
        Validate the ``X-API-Key`` request header.

        Flow:
            1. Extract the raw key from the ``X-API-Key`` header.
            2. Compute its SHA-256 hex digest.
            3. Search for a matching active record in ``api.key``.
            4. On success → update ``last_used_at`` and return the record.
            5. On failure → return ``None``.

        Returns:
            api.key record if the key is valid and active, ``None`` otherwise.
        """
        raw_key = request.httprequest.headers.get("X-API-Key")
        if not raw_key:
            return None

        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        api_key_record = (
            request.env["api.key"]
            .sudo()
            .search(
                [("key_hash", "=", key_hash), ("is_active", "=", True)],
                limit=1,
            )
        )

        if not api_key_record:
            return None

        # Update last usage timestamp without triggering full ORM signals.
        api_key_record.sudo().write(
            {"last_used_at": fields.Datetime.now()}
        )
        return api_key_record

    # ──────────────────────────────────────────────────────────────────────────
    # Endpoints
    # ──────────────────────────────────────────────────────────────────────────

    @http.route(
        "/api/odoo/openapi.json",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_openapi_spec(self, **kwargs) -> Response:
        """Return the OpenAPI 3.0 specification for this API (no auth required)."""
        return _json_response(_OPENAPI_SPEC)

    @http.route(
        "/api/odoo/<string:model>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_model_records(self, model: str, **kwargs) -> Response:
        """
        Query records from an allowed Odoo model.

        Path params:
            model (str): Odoo model technical name (e.g. ``res.partner``).

        Query params:
            limit  (int): Maximum number of records to return. Default: 80.
            offset (int): Number of records to skip. Default: 0.
            fields (str): Comma-separated field names to include in results.
                          Omit to return all fields.
            domain (str): JSON-encoded Odoo domain list. Default: ``[]``.
                          Example: ``[["active","=",true]]``
            alias  (str): ``res.partner`` only. Registered name/alias from
                          ``normalized.text``; normalized server-side and
                          combined with ``domain``.

        Headers:
            X-API-Key: Valid API key registered in the api.key table.

        Returns:
            200: ``{"total": int, "limit": int, "offset": int,
                     "records": [{"id": ..., ...}]}``
                     For ``res.partner``, each record also includes a
                     ``normalized_aliases`` list with the registered
                     name/alias variants (``normalized.text.items``).
            400: Invalid query parameters.
            401: Missing or invalid API Key.
            403: Model not in the allowed whitelist.
            500: Unexpected server error.
        """
        # ── 1. Authentication ─────────────────────────────────────────────────
        api_key_record = self._authenticate()
        if api_key_record is None:
            _logger.warning(
                "API request rejected: invalid or missing X-API-Key "
                "for model '%s'.",
                model,
            )
            return _json_response(
                {
                    "error": "Unauthorized",
                    "message": (
                        "API Key ausente, inválida o inactiva. "
                        "Incluya un header 'X-API-Key' válido."
                    ),
                },
                status=401,
            )

        # ── 2. Model whitelist ────────────────────────────────────────────────
        if model not in ALLOWED_MODELS:
            return _json_response(
                {
                    "error": "Bad Request",
                    "message": (
                        f"El modelo '{model}' no está habilitado. "
                        f"Modelos permitidos: {sorted(ALLOWED_MODELS)}."
                    ),
                },
                status=400,
            )

        # ── 3. Parse pagination params ────────────────────────────────────────
        try:
            limit = int(kwargs.get("limit", 80))
            offset = int(kwargs.get("offset", 0))
        except (ValueError, TypeError):
            return _json_response(
                {
                    "error": "Bad Request",
                    "message": (
                        "Los parámetros 'limit' y 'offset' deben ser enteros."
                    ),
                },
                status=400,
            )

        if limit < 0 or offset < 0:
            return _json_response(
                {
                    "error": "Bad Request",
                    "message": (
                        "'limit' y 'offset' no pueden ser negativos."
                    ),
                },
                status=400,
            )

        # ── 4. Parse fields param ─────────────────────────────────────────────
        fields_param = kwargs.get("fields")
        field_list = (
            [f.strip() for f in fields_param.split(",") if f.strip()]
            if fields_param
            else None
        )

        # ── 5. Parse domain param ─────────────────────────────────────────────
        domain_param = kwargs.get("domain", "[]")
        try:
            domain = json.loads(domain_param)
            if not isinstance(domain, list):
                raise ValueError("Domain must be a JSON array.")
        except (ValueError, TypeError, json.JSONDecodeError):
            return _json_response(
                {
                    "error": "Bad Request",
                    "message": (
                        "'domain' debe ser un arreglo JSON válido. "
                        "Ejemplo: [[\"active\",\"=\",true]]"
                    ),
                },
                status=400,
            )

        # ── 6. Parse alias param (res.partner only) ───────────────────────────
        alias = (kwargs.get("alias") or "").strip()
        order = None
        if alias:
            if model != "res.partner":
                return _json_response(
                    {
                        "error": "Bad Request",
                        "message": (
                            "El parámetro 'alias' solo aplica al modelo "
                            "'res.partner'."
                        ),
                    },
                    status=400,
                )
            domain.append(("id", "in", self._partner_ids_by_alias(alias)))
            # An alias may resolve to several partners; fix the order so the
            # same request always yields the same record.
            order = "active desc, id asc"

        # ── 7. Query Odoo ─────────────────────────────────────────────────────
        try:
            env_model = self._get_api_model(model)
            total = env_model.search_count(domain)
            records = env_model.search_read(
                domain=domain,
                fields=field_list,
                limit=limit,
                offset=offset,
                order=order,
            )
            if model == "res.partner":
                aliases_map = self._get_partner_aliases_map(
                    [r["id"] for r in records]
                )
                for record in records:
                    record["normalized_aliases"] = aliases_map.get(
                        record["id"], []
                    )
        except Exception:
            _logger.exception(
                "Error al consultar el modelo '%s' con domain=%s.",
                model,
                domain_param,
            )
            return _json_response(
                {
                    "error": "Internal Server Error",
                    "message": "Ocurrió un error al procesar la consulta.",
                },
                status=500,
            )

        _logger.info(
            "API query: model=%s client=%s total=%d limit=%d offset=%d",
            model,
            api_key_record.client_name,
            total,
            limit,
            offset,
        )

        return _json_response(
            {
                "total": total,
                "limit": limit,
                "offset": offset,
                "records": records,
            }
        )

    @http.route(
        "/api/odoo/<string:model>/<int:record_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def get_model_record_by_id(
        self, model: str, record_id: int, **kwargs
    ) -> Response:
        """
        Return a single record from an allowed Odoo model by its ID.

        Path params:
            model     (str): Odoo model technical name (e.g. ``res.partner``).
            record_id (int): Database ID of the record to retrieve.

        Query params:
            fields (str): Comma-separated field names to include in the
                          response. Omit to return all fields.

        Headers:
            X-API-Key: Valid API key registered in the api.key table.

        Returns:
            200: ``{"id": int, "model": str, "record": {...}}``
                 For ``res.partner``, ``record`` also includes a
                 ``normalized_aliases`` list with the registered
                 name/alias variants (``normalized.text.items``).
            400: Invalid query parameters.
            401: Missing or invalid API Key.
            403: Model not in the allowed whitelist.
            404: No record found for the given ID.
            500: Unexpected server error.
        """
        # ── 1. Authentication ─────────────────────────────────────────────────
        api_key_record = self._authenticate()
        if api_key_record is None:
            _logger.warning(
                "API request rejected: invalid or missing X-API-Key "
                "for model '%s' id=%s.",
                model,
                record_id,
            )
            return _json_response(
                {
                    "error": "Unauthorized",
                    "message": (
                        "API Key ausente, inválida o inactiva. "
                        "Incluya un header 'X-API-Key' válido."
                    ),
                },
                status=401,
            )

        # ── 2. Model whitelist ────────────────────────────────────────────────
        if model not in ALLOWED_MODELS:
            return _json_response(
                {
                    "error": "Bad Request",
                    "message": (
                        f"El modelo '{model}' no está habilitado. "
                        f"Modelos permitidos: {sorted(ALLOWED_MODELS)}."
                    ),
                },
                status=400,
            )

        # ── 3. Parse fields param ─────────────────────────────────────────────
        fields_param = kwargs.get("fields")
        field_list = (
            [f.strip() for f in fields_param.split(",") if f.strip()]
            if fields_param
            else None
        )

        # ── 4. Query Odoo ─────────────────────────────────────────────────────
        try:
            records = (
                self._get_api_model(model)
                .search_read(
                    domain=[("id", "=", record_id)],
                    fields=field_list,
                    limit=1,
                )
            )
        except Exception:
            _logger.exception(
                "Error al consultar %s id=%s.", model, record_id
            )
            return _json_response(
                {
                    "error": "Internal Server Error",
                    "message": "Ocurrió un error al procesar la consulta.",
                },
                status=500,
            )

        if not records:
            return _json_response(
                {
                    "error": "Not Found",
                    "message": (
                        f"No se encontró un registro con id={record_id} "
                        f"en el modelo '{model}'."
                    ),
                },
                status=404,
            )

        if model == "res.partner":
            aliases_map = self._get_partner_aliases_map([record_id])
            records[0]["normalized_aliases"] = aliases_map.get(record_id, [])

        _logger.info(
            "API query by id: model=%s id=%d client=%s",
            model,
            record_id,
            api_key_record.client_name,
        )

        return _json_response(
            {
                "id": record_id,
                "model": model,
                "record": records[0],
            }
        )
