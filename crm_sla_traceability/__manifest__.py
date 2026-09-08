# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "CRM SLA & Trazabilidad",
    "summary": "Trazabilidad y automatización de SLA en oportunidades de CRM",
    "description": """
        Amplía crm.lead con 15 campos de trazabilidad y automatización de SLA:
        - 3 catálogos maestros configurables (Tipos de oportunidad, Clasificaciones,
          Orígenes de trazabilidad).
        - Cálculo automático de la fecha límite SLA en horas hábiles (lunes a viernes).
        - Semáforo SLA en la vista Kanban mantenido por cron.
        - Flujos de aprobación de preventa (socios) y DC con auditoría en el chatter.
        - Recordatorio automático al comercial mientras la oportunidad está en espera del cliente.
    """,
    "author": "Calyx Servicios S.A.",
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Sales/CRM",
    "version": "15.0.1.0.1",
    "application": False,
    "installable": True,
    "depends": [
        "crm",
        "res_users_partner_fields",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/crm_opportunity_type_views.xml",
        "views/crm_classification_views.xml",
        "views/crm_request_origin_views.xml",
        "views/crm_menus.xml",
        "views/crm_stage_views.xml",
        "views/crm_team_views.xml",
        "views/crm_lead_views.xml",
        "views/crm_lead_kanban_views.xml",
        "data/catalogs_data.xml",
        "data/mail_template_data.xml",
        "data/ir_cron_data.xml",
    ],
    "demo": [],
    "images": [],
}
