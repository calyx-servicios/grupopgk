# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Contact Fields",
    "summary": """
        It extends the partner/client fields.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["lucianobaleani", "PerezGabriela"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "base", 
        "contacts"
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/add_child_company_wizard.xml",
        "views/res_partner_views.xml",
    ],
}
