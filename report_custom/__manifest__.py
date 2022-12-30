# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Report Sale Custom",
    "summary": """
        Report Sale Custom""",
    "author": "Calyx Servicios S.A.",
    "maintainers": ["GeorginaGuzman"],
    "website": "http://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "sales",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        'sale'
    ],
    "data": [
        "view/template_no_details.xml",
        "view/template_with_details.xml",
        "report/sale_report.xml",
        "view/sale_views.xml",
    ],
}