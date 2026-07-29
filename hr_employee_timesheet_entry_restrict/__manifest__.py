# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "HR Employee Timesheet Entry Restrict",
    "summary": "Restrict employee timesheet sheets when entering from employee form.",
    "author": "Grupo PGK",
    "maintainers": ["Frankofe"],
    "website": "https://www.grupopgk.com.ar/",
    "license": "AGPL-3",
    "category": "Human Resources",
    "version": "15.0.1.0.0",
    "application": False,
    "installable": True,
    "depends": [
        "hr",
        "hr_timesheet",
        "hr_timesheet_sheet",
    ],
    "data": [
        "views/hr_employee_timesheet_entry_restrict_views.xml",
    ],
}
