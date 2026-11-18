# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Informe Gestión de Proyectos CALYX",
    "summary": """
        Informe de gestión de proyectos (Tecnología) con rango de fechas,
        distribuciones de gastos de la consolidación y margen bruto.
    """,
    "author": "Calyx Servicios S.A.",
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Services/Project",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "project_management_report_pgk",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "wizards/project_management_report_calyx_wizard_views.xml",
    ],
}
