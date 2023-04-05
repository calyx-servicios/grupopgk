# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Report Analytic Account",
    "summary": """
       Report Analytic Account""",
    "author": "Calyx Servicios S.A.",
    "maintainers": ["GeorginaGuzman"],
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Account",
    "version": "15.0.1.1.3",
    "application": False,
    "installable": True,
    "depends": [ 'account', 'analytic'],
    "data": [
        "views/analityc_report.xml"
    ],
}