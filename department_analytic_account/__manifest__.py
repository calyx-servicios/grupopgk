# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Department Analytic Account",
    "summary": """
        Assign analytic account to each department.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["marcooegg", "PerezGabriela"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Sign",
    "version": "15.0.0.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "base",
        "hr",
        "account"
    ],
    "data": [
        "views/hr_department.xml",
    ],
}