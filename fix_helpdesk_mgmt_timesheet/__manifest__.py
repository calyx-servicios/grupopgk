# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Fix Helpdesk Mgmt Timesheet",
    "summary": "Corrige validacion de vista en helpdesk_mgmt_timesheet",
    "author": "Calyx Servicios S.A.",
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Technical Settings",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "helpdesk_mgmt_timesheet",
    ],
    "data": [
        "views/helpdesk_ticket_view.xml",
    ],
}
