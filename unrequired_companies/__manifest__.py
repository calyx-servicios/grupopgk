# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Unrequired Company On Account Analytic Line",
    "summary": """
        This module removes required on the "company_id" field in Analytic Account Lines
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "account_analytic_main_multi_company",
    ],
}
