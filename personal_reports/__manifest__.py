# pylint: disable=missing-module-docstring,pointless-statement
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Personal Reports",
    "summary": """
        Personal Invoicing and Payments Reports
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["marcooegg"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "13.0.1.0.2",
    "development_status": "Production/Stable",
    "application": False,
    "installable": True,
    "external_dependencies": {
        "python": [],
        "bin": [],
    },
    "depends": ["base", "account", "personal_pay_account", "l10n_ar_reports"],
    "data": [
        "wizards/personal_subledger_report_wizard.xml",
        "reports/layouts.xml",
        "reports/invoicing_subledger_report_txt.xml",
        "reports/invoicing_subledger_report.xml",
        "reports/payment_subledger_report_txt.xml",
        "reports/payment_subledger_report.xml",
        "reports/reports.xml",
    ],
}
