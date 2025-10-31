# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Custom HR Jobs",
    "summary": "Extends HR Job by adding a related field to HR Applicant Category",
    "description": """
        This module extends the HR Job model by adding a field related to hr.applicant.category.
        It also updates the form, kanban, and search views to display this category with color badges,
        similar to how tags are displayed in contacts.
    """,
    "author": "Calyx Servicios S.A.",
    "maintainers": ["leandro090685"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Human Resources",
    "version": "15.0.1.1.0",
    "application": False,
    "installable": True,
    "depends": [
        'hr_recruitment',  # hr_job is part of hr_recruitment
    ],
    "data": [
        'views/hr_job_views.xml',
    ],
    "demo": [],
    "images": [],
}
