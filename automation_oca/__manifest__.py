# Copyright 2024 Dixmit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Automation Oca",
    "summary": """
        Automate actions in threaded models""",
    "version": "15.0.1.0.0",
    "license": "AGPL-3",
    "category": "Automation",
    "author": "Dixmit,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/automation",
    "depends": ["mail", "link_tracker", "base_sparse_field"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "wizards/automation_configuration_export.xml",
        "wizards/automation_configuration_import.xml",
        "views/menu.xml",
        "wizards/automation_configuration_test.xml",
        "views/automation_record.xml",
        "views/automation_record_step.xml",
        "views/automation_configuration_step.xml",
        "views/automation_configuration.xml",
        "views/link_tracker_clicks.xml",
        "views/automation_filter.xml",
        "views/automation_tag.xml",
        "data/cron.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
}
