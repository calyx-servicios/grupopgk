# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Account Partner API",
    "summary": (
        "REST API protegida por API Key para consulta de socios, "
        "facturas e impuestos."
    ),
    "author": "GrupoPGK",
    "version": "15.0.1.0.1",
    "category": "Technical",
    "license": "AGPL-3",
    "depends": ["base", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/api_key_views.xml",
    ],
    "installable": True,
    "application": False,
}
