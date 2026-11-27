{
    "name": "Calyx - Proyectos desde orden de venta",
    "summary": "Genera un proyecto por OV y una tarea por línea en ventas Calyx",
    "author": "Calyx Servicios S.A.",
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Services/Project",
    "version": "15.0.1.0.0",
    "development_status": "Beta",
    "installable": True,
    "depends": [
        "project_for_each_sol",
        "project_contrated_hours",
        "sale_timesheet",
    ],
    "data": [
        "security/security.xml",
        "views/res_company_views.xml",
        "views/sale_order_views.xml",
        "views/project_views.xml",
    ],
}
