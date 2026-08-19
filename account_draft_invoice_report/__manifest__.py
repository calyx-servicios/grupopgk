# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Account Draft Invoice Report",
    "summary": """
        Reporte de facturas y notas de crédito en borrador por rango de fechas.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["Zamora Javier"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Accounting/Reporting",
    "version": "15.0.1.0.2",
    "development_status": "Beta",
    "application": False,
    "installable": True,
    "depends": [
        "account",
        "account_financial_report",
        "sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/draft_invoice_report_wizard_views.xml",
        "report/draft_invoice_report_templates.xml",
    ],
}
