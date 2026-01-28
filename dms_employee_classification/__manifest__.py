# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "DMS Employee Auto Classification",
    "summary": "Clasificación automática de documentos de empleados en DMS.",
    "author": "Grupo PGK",
    "maintainers": ["Frankofe"],
    "website": "https://www.grupopgk.com.ar/",
    "license": "AGPL-3",
    "category": "Document Management",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": [
        "hr",
        "dms_auto_classification",
    ],
    "data": [
        "wizards/wizard_dms_classification_views.xml",
    ],
}
