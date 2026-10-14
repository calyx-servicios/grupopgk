{
    "name": "Project - Triage UAT Cliente",
    "summary": "Bug, Mejora y Malentendido con trazabilidad y presupuesto independiente",
    "description": "Triage de UAT Cliente con historial, retrabajo interno y doble aprobación de mejoras.",
    "version": "15.0.1.0.0",
    "author": "Calyx Servicios S.A.",
    "license": "AGPL-3",
    "category": "Project",
    "depends": ["project_hours_request_calyx", "sale_timesheet", "timesheet_odoo"],
    "data": [
        "security/ir.model.access.csv",
        "security/rules.xml",
        "wizard/uat_wizard_views.xml",
        "views/uat_views.xml",
    ],
    "installable": True,
}
