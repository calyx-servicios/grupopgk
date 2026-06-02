{
    "name": "Contacts RRHH Filter",
    "summary": (
        "Restringe la creación y edición de empleados a administradores RRHH, "
        "el acceso a ciertos menús del módulo de empleados y las restricciones "
        "de calendario para usuarios RRHH."
    ),
    "author": "Grupo PGK",
    "maintainers": ["Frankofe"],
    "website": "https://www.grupopgk.com.ar/",
    "license": "AGPL-3",
    "category": "Human Resources",
    "version": "15.0.1.1.2",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": [
        "contacts",
        "hr",
        "calendar",
    ],
    "data": [
        "views/calendar_event_views.xml",
        "views/hr_employee_views.xml",
        "views/hr_menu_restrict.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "contacts_rrhh_filter/static/src/js/calendar_model_patch.js",
        ],
    },
}
