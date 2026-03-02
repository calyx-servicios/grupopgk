# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "DMS Employee Auto Classification",
    "summary": "Clasificación automática de documentos de empleados en DMS.",
    "author": "Grupo PGK",
    "maintainers": ["Frankofe"],
    "website": "https://www.grupopgk.com.ar/",
    "license": "AGPL-3",
    "category": "Document Management",
    "version": "15.0.1.6.0",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": [
        "hr",
        "hr_dms_field",
        "dms_auto_classification",
        "dms_field_auto_classification",
        "web",
        "sign_oca",
        "custom_hr_holidays",
        "report_xlsx",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/hr_employee_document_views.xml",
        "views/dms_classification_template_views.xml",
        "wizards/wizard_dms_classification_views.xml",
        "wizards/wizard_signature_control_views.xml",
        "reports/signature_control_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "dms_employee_classification/static/src/js/signature_prefill.js",
        ],
        "web.assets_frontend": [
            "dms_employee_classification/static/src/js/signature_prefill.js",
        ],
        "sign_oca.sign_assets": [
            "dms_employee_classification/static/src/js/signature_prefill.js",
        ],
    },
}
