# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Subscription Package View Fix",
    "summary": "Normalize legacy subscription view before upgrades",
    "author": "Calyx Servicios S.A.",
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.2.0",
    "application": False,
    "installable": True,
    "depends": [
        "subscription_package",
    ],
    "data": [
        "data/subscription_package_view_fix_data.xml",
    ],
}
