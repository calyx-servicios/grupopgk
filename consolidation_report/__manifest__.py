# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Consildation Report",
    "summary": """
        This module generates and stores consolidated monthly reports.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.2.1.0",
    "application": False,
    "installable": True,
    "depends": [
        "account_analytic_currency",
    ],
    "data": [
        "security/permissions.xml",
        "security/ir.model.access.csv",
        "views/consolidation_report.xml",
        "views/consolidation_period.xml",
    ],
}
