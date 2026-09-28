{
    "name": "Project Task Configurations Hierarchy",
    "summary": "Four-level task hierarchy with shared hours caps",
    "author": "Calyx Servicios S.A.",
    "license": "AGPL-3",
    "category": "Project",
    "version": "15.0.1.0.0",
    "installable": True,
    "application": False,
    "depends": [
        "project_hours_request",
        "calyx_sale_project_from_order",
        "hr_timesheet",
    ],
    "data": [
        "views/project_task_views.xml",
    ],
    "post_init_hook": "post_init_hook",
}