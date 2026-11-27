from odoo import fields, models, tools


class TimesheetManagementReport(models.Model):
    _name = "timesheet.management.report"
    _description = "Detalle de horas de gestión"
    _auto = False
    _rec_name = "name"
    _order = "activity_date desc, id desc"

    activity_date = fields.Date(string="Fecha de actividad", readonly=True)
    date = fields.Date(string="Fecha SIGE", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    employee_id = fields.Many2one("hr.employee", string="Empleado", readonly=True)
    client_id = fields.Many2one("res.partner", string="Cliente", readonly=True)
    project_id = fields.Many2one("project.project", string="Proyecto", readonly=True)
    task_id = fields.Many2one("project.task", string="Tema", readonly=True)
    hour_type_id = fields.Many2one(
        "timesheet.hour.type",
        string="Tipo de hora",
        readonly=True,
    )
    unit_amount = fields.Float(string="Horas", readonly=True)
    name = fields.Char(string="Justificación", readonly=True)
    project_manager_id = fields.Many2one(
        "res.users",
        string="PM",
        readonly=True,
    )
    technical_leader_id = fields.Many2one(
        "res.users",
        string="Líder técnica",
        readonly=True,
    )
    functional_user_ids = fields.Many2many(
        related="project_id.workflow_functional_ids",
        string="Funcionales",
        readonly=True,
    )
    timesheet_state = fields.Selection(
        [
            ("open", "Abierto"),
            ("sent", "Enviado"),
            ("close", "Cerrado"),
        ],
        string="Estado SIGE",
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        project_model = self.env["project.project"]
        manager_expression = (
            "COALESCE(project.calyx_project_manager_id, project.user_id)"
            if "calyx_project_manager_id" in project_model._fields
            else "project.user_id"
        )
        consolidation_filter = ""
        if "consolidation_line" in self.env["account.analytic.line"]._fields:
            consolidation_filter = "AND analytic.consolidation_line IS NOT TRUE"
        allocation_project = self.env.ref(
            "timesheet_odoo.hours_to_allocate",
            raise_if_not_found=False,
        )
        allocation_filter = ""
        if allocation_project:
            allocation_filter = (
                "AND analytic.project_id != %s" % allocation_project.id
            )
        query = """
            CREATE VIEW %s AS (
                SELECT
                    analytic.id,
                    analytic.activity_date,
                    analytic.date,
                    COALESCE(
                        analytic.company_id,
                        project.company_id,
                        employee.company_id
                    ) AS company_id,
                    analytic.employee_id,
                    project.partner_id AS client_id,
                    analytic.project_id,
                    analytic.task_id,
                    analytic.hour_type_id,
                    analytic.unit_amount,
                    analytic.name,
                    %s AS project_manager_id,
                    project.technical_leader_id,
                    timesheet.state AS timesheet_state
                FROM account_analytic_line analytic
                JOIN project_project project
                    ON project.id = analytic.project_id
                LEFT JOIN hr_employee employee
                    ON employee.id = analytic.employee_id
                LEFT JOIN timesheet_sige timesheet
                    ON timesheet.id = analytic.timesheet_id
                WHERE analytic.unit_amount != 0
                    AND analytic.move_id IS NULL
                    %s
                    %s
            )
        """ % (
            self._table,
            manager_expression,
            consolidation_filter,
            allocation_filter or "",
        )
        self.env.cr.execute(query)
