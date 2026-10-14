{
    "name": "Timesheet Activity Management - Reclassification",
    "summary": "Conserva tipo y fecha de actividad al reclasificar horas SIGE",
    "author": "Calyx Servicios S.A.",
    "license": "AGPL-3",
    "category": "Timesheets",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "timesheet_activity_management",
        "timesheet_reclassify_odoo",
    ],
    "data": [
        "wizard/timesheet_reclassify_views.xml",
    ],
}
