# pylint: disable=missing-module-docstring,pointless-statement
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3).
{
    "name": "Quoter - Service Configuration",
    "summary": "Cotizador de servicios profesionales con productos por nivel de complejidad",
    "author": "Calyx Servicios S.A.",
    "maintainers": ["YourName"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Sales",
    "version": "15.0.6.0.87",
    "development_status": "Beta",
    "application": False,
    "installable": True,
    "depends": [
        "base",
        "web",
        "sale",
        "sale_management",
        "product",
    ],
    "data": [
        "security/quoter_groups.xml",
        "security/ir.model.access.csv",
        "security/quoter_security_rules.xml",
        "data/quoter_cleanup.xml",
        "data/sequence_data.xml",
        "data/pricelist_data.xml",
        "data/quoter_product_attribute.xml",
        "views/quoter_service_views.xml",
        "views/quoter_product_level_range_views.xml",
        "views/quoter_product_views.xml",
        "views/quoter_product_menu_views.xml",
        "views/sale_order_views.xml",
        "views/quoter_menu.xml",
        "views/quoter_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "quoter/static/src/js/quoter_tab_labels.js",
            "quoter/static/src/js/quoter_range_columns.js",
        ],
    },
}
