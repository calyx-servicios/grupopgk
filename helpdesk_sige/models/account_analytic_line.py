from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    charge_sige = fields.Boolean(string="Carga SIGE", default=False)

    def _search_timesheet(self, employee_id, date):
        timesheet_obj = self.env["timesheet.sige"]
        timesheet = timesheet_obj.search(
            [
                ("employee_id", "=", employee_id),
                ("start_of_period", "<=", date),
                ("end_of_period", ">=", date),
                ("state", "=", "open"),
            ],
            limit=1,
        )

        return timesheet.id if timesheet else False

    def write(self, vals):
        # Utilizar un contexto especial para evitar la recursión
        if self.env.context.get("prevent_recursion", False):
            return super(AccountAnalyticLine, self).write(vals)

        # Llamar al método super con un contexto especial
        res = super(
            AccountAnalyticLine, self.with_context(prevent_recursion=True)
        ).write(vals)

        for record in self:
            # Verificar si el registro está relacionado con un ticket de helpdesk
            if record.ticket_id:
                # Almacenar los registros que no se pudieron procesar correctamente
                unprocessed_records = []

                employee_id = record.user_id.employee_ids.id
                if not employee_id:
                    raise UserError(
                        _("The user %s is not associated with any employee.")
                        % record.user_id.name
                    )

                date_time = record.date_time
                date = date_time.date() if date_time else record.date

                timesheet_id = self._search_timesheet(employee_id, date)
                if timesheet_id:
                    # Actualizar el registro en timesheet_sige
                    record.with_context(prevent_recursion=True).write(
                        {"timesheet_id": timesheet_id, "charge_sige": True}
                    )

                else:
                    # Agregar el registro a la lista de no procesados
                    unprocessed_records.append(record)

                # Verificar si hay registros no procesados y tienen el campo charge_sige en False
                for record in unprocessed_records:
                    if not record.charge_sige:
                        record.ticket_id.message_post(
                            body=_(
                                "No open period found for the employee %s on the date %s description %s."
                            )
                            % (record.user_id.name, record.date, record.name)
                        )
                        
        return res
