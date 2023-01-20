{
    "name": "Split Invoices From Sale Order",
    "summary": """
        This module adds in the sales order the option to separate a sales order into several invoices.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.0.0",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "depends": [
        "sale_management",
        "account",
        "contacts",
        "sale_order_subscription",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/sale_order.xml",
    ],
}
