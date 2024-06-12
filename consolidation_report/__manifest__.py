# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Consildation Report",
    "summary": """
        This module generates and stores consolidated monthly reports.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora, Javier", "leandro090685"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.8.1.0",
    "application": False,
    "installable": True,
    "depends": [
        "account_analytic_currency",
        "report_analytic_account",
        "analytic",
    ],
    "data": [
        "security/permissions.xml",
        "security/ir.model.access.csv",
        "views/consolidation_report.xml",
        "views/consolidation_period.xml",
        "views/account_consolidation_data.xml",
        "views/account_analytic_group.xml",
        "views/account_analytic_account.xml",
        "views/account_analytic_line.xml",
    ],
}
