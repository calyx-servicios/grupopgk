{
    "name": "Calyx - Reserva UAT/Soporte",
    "summary": "Reserva contractual UAT y cupos independientes por tarea",
    "author": "Calyx Servicios S.A.",
    "license": "AGPL-3",
    "category": "Project",
    "version": "15.0.1.0.0",
    "installable": True,
    "application": False,
    "depends": [
        "project_hours_request",
        "calyx_sale_project_from_order",
    ],
    "data": [
        "views/sale_order_views.xml",
        "views/project_task_views.xml",
    ],
}