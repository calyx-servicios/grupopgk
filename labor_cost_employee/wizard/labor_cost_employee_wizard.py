from odoo import fields, models, _, api
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import base64
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class LaborCostEmployeeWizard(models.TransientModel):
    _name = "labor.cost.employee.wizard"
    _description = _("Calculate labor cost wizard")

    def get_years():
        year_list = []
        for i in range(2000, 2100):
            year_list.append((str(i), str(i)))
        return year_list

    month = fields.Selection(
        [
            ("1", "January"),
            ("2", "February"),
            ("3", "March"),
            ("4", "April"),
            ("5", "May"),
            ("6", "June"),
            ("7", "July"),
            ("8", "August"),
            ("9", "September"),
            ("10", "October"),
            ("11", "November"),
            ("12", "December"),
        ],
        string="Month",
        default=str(date.today().month),
    )
    year = fields.Selection(get_years(), string="Year", default=str(date.today().year))
    name = fields.Char("Period", compute="_compute_period")
    period_sige = fields.Char("Period Sige")
    file_cost = fields.Binary("Attach")
    invoice_ids = fields.Many2many("account.move", string="Invoices")

    @api.depends("month", "year")
    def _compute_period(self):
        if self.month and self.year:
            month = _(
                dict(self.fields_get(allfields=["month"])["month"]["selection"])[
                    self.month
                ]
            )
            self.name = month + " " + self.year
            self.period_sige = self.year + self.month.zfill(2)
        else:
            self.name = "/"
            self.period_sige = "/"

    @api.onchange("month", "year")
    def onchange_period(self):
        if self.month and self.year:
            date_act = date.today().replace(month=int(self.month), year=int(self.year))
            date_from = date_act.replace(day=1)
            date_to = date_act + relativedelta(day=31)
            partners = (
                self.env["res.partner"]
                .search([])
                #.filtered(lambda emp: emp.user_partner_id != False)
                #.mapped("user_partner_id")
            )
            if partners:
                self.invoice_ids = False
                domain = [
                    ("invoice_date", ">=", date_from),
                    ("invoice_date", "<=", date_to),
                    ("move_type", "in", ["in_invoice", "in_refund"]),
                    ("partner_id", "in", partners.ids),
                    ("salary", "=", True),
                ]
                invoices = self.env["account.move"].search(domain)
                if invoices:
                    self.invoice_ids = [(6, 0, invoices.ids)]

    def calculate_labor_cost(self):
        tm_sige_obj = self.env["timesheet.sige"]
        lce_obj = self.env["labor.cost.employee"]
        values = []
        cost = []
        data_str = base64.b64decode(self.file_cost).decode("UTF-8")
        for line in data_str.split("\n"):
            if line != "":
                data = line.split(";")
                if len(data) >= 1:
                    exist = list(filter(lambda e: e["employee_id"] == data[0], cost))
                    if len(exist) != 0:
                        index_obj = cost.index(exist[0])
                        cost[index_obj]["amount"] = cost[index_obj]["amount"] + float(
                            data[1]
                        )
                        cost[index_obj]["calculation"] = "Salary: " + str(
                            cost[index_obj]["amount"]
                        )

                    else:
                        cost.append(
                            {
                                "employee_id": data[0],
                                "amount": float(data[1]),
                                "calculation": _("Salary: {}".format(data[1])),
                            }
                        )

        # Union de contacto con contacto asociado en txt
        laboral_cost = self._process_costs(cost)

        employees_not_found = []
        
        if self.invoice_ids:
            txt_invoice = _("Total amount invoiced: ")
            employee_model = self.env["hr.employee"]

            for invoice in self.invoice_ids:
                parent_partner_id = employee_model.search(
                    [("associated_contact_ids", "in", [invoice.partner_id.id])],
                    limit=1
                )

                if parent_partner_id:
                    cuil = parent_partner_id.identification_id
                else:
                    cuil = invoice.partner_id.vat
                    employees_not_found.append(invoice.partner_id.name)

                if cuil not in laboral_cost:
                    laboral_cost[cuil] = {
                        "amount": 0.0,
                        "calculation": ""
                    }

                laboral_cost[cuil]["amount"] += invoice.amount_untaxed
                laboral_cost[cuil]["calculation"] += f"{txt_invoice} {invoice.amount_untaxed}"

            if employees_not_found:
                empleyees_filtered_list = set(employees_not_found)
                _logger.warning("Empleados no encontrados para los siguientes Contactos o falta asignar un CUIT: %s", ', '.join(empleyees_filtered_list))
                raise UserError(_("No related employees were found for: %s") % ', '.join(empleyees_filtered_list))

        # Union de contactos asociados entre la informacion del txt y las facturas
        final_laboral_cost = self._process_final_costs(laboral_cost)

        employees_not_found = []
        employee_list = []
        for employee_key in laboral_cost.keys():
            employee_list.append(employee_key)
        employees = self.env["hr.employee"].search(
            [("identification_id", "in", employee_list)]
        )
        date_act = date.today().replace(month=int(self.month), year=int(self.year))
        start_of_period = date_act.replace(day=1)
        end_of_period = date_act + relativedelta(day=31)
        for employee in employees:
            tm_sige_emp = tm_sige_obj.search(
                [
                    ("employee_id", "=", employee.id),
                    ("state", "=", "close"),
                    ("start_of_period", ">=", start_of_period),
                    ("end_of_period", "<=", end_of_period),
                ],
                limit=1,
            )
            cuil = employee.identification_id
            if not cuil:
                employees_not_found.append(f"Falta asignar un CUIT al empleado {employee.name}")

            else:
                if tm_sige_emp:
                    amount = laboral_cost[cuil]["amount"]
                    labor_cost = amount / tm_sige_emp.register_hours
                    laboral_cost[cuil]["cost"] = labor_cost
                    laboral_cost[cuil]["employee_id"] = employee.id
                    laboral_cost[cuil]["name"] = self.name
                    laboral_cost[cuil]["calculation"] += _(
                        "\n Amount(Salary + Invoiced Amount) {} / {} (Register Hours) = {} (Labor cost)".format(
                            amount, tm_sige_emp.register_hours, labor_cost
                        )
                    )
                    employee.timesheet_cost = labor_cost
                    account_analytic_line_ids = tm_sige_emp.timesheet_ids
                    if account_analytic_line_ids:
                        for account_analytic_line_id in account_analytic_line_ids:
                            cost_total_in_project = account_analytic_line_id.unit_amount * labor_cost * -1
                            account_analytic_line_id.write({"amount": cost_total_in_project})

                    lce_obj.create(laboral_cost[cuil])
                else:
                    employees_not_found.append(employee.name)
                    _logger.warning(f"Falta asignar costo laboral al empleado {employee.name}")
                    #raise UserError(f"Falta asignar costo laboral al empleado {employee.name}")
        if employees_not_found:
            empleyees_filtered_list = set(employees_not_found)
            raise UserError(_(
                "Falta cargar parte de horas de los empleados: %s"
            ) % ', '.join(empleyees_filtered_list))
            
        employees_without_cost = []
        all_tm_sige = tm_sige_obj.search([
            ("state", "=", "close"),
            ("start_of_period", ">=", start_of_period),
            ("end_of_period", "<=", end_of_period),
        ])

        for tm in all_tm_sige:
            if not tm.timesheet_ids:
                continue  
            employee = tm.employee_id
            if not employee:
                continue
            if not employee.timesheet_cost or employee.timesheet_cost == 0:
                employees_without_cost.append(employee.name)

        if employees_without_cost:
            filtered = set(employees_without_cost)
            _logger.warning(
                "Empleados con partes de horas y sin costo laboral asignado: %s",
                ', '.join(filtered)
            )
            raise UserError(_(
                "Los siguientes empleados tienen partes de horas en el período pero no poseen costo laboral asignado: %s"
            ) % ', '.join(filtered))

        action = self.env.ref("labor_cost_employee.action_window_labor_cost").read()[0]
        return action

    def _process_costs(self, cost=[]):
        employee_model = self.env["hr.employee"]

        laboral_cost = {}
        # Recorro la lista de costos
        for item in cost:
            employee_cuil = item["employee_id"]
            # Busco el empleado con el numero de cuil
            employee_id = employee_model.search(
                [
                    ("identification_id", "=", employee_cuil),
                    ("user_partner_id", "!=", False),
                ],
                limit=1,
            )
            if employee_id:
                # Verifica si el empleado esta en contactos asociados
                parent_partner_id = employee_model.search(
                    [("associated_contact_ids", "in", [employee_id.user_partner_id.id])]
                )
                if parent_partner_id:
                    cuil = parent_partner_id.identification_id
                else:
                    cuil = employee_cuil

                if not cuil in laboral_cost:
                    laboral_cost[cuil] = {}
                    laboral_cost[cuil]["amount"] = 0.0
                    laboral_cost[cuil]["calculation"] = ""

                laboral_cost[cuil]["amount"] += item["amount"]
                laboral_cost[cuil]["calculation"] = _(
                    "Salary: {}".format(laboral_cost[cuil]["amount"])
                )

        return laboral_cost

    def _process_final_costs(self, laboral_cost):
        employee_model = self.env["hr.employee"]

        result = {}
        # Recorro el diccionario de costos
        for cuil, data in laboral_cost.items():
            # Busco el empleado con el número de CUIL
            employee_id = employee_model.search(
                [
                    ("identification_id", "=", cuil),
                    ("user_partner_id", "!=", False),
                ],
                limit=1,
            )
            if employee_id:
                # Verifica si el empleado está en contactos asociados
                parent_partner_id = employee_model.search(
                    [("associated_contact_ids", "in", [employee_id.user_partner_id.id])]
                )
                if parent_partner_id:
                    final_cuil = parent_partner_id.identification_id
                else:
                    final_cuil = cuil

                if final_cuil not in result:
                    result[final_cuil] = {"amount": 0.0, "calculation": ""}

                result[final_cuil]["amount"] += data["amount"]

                result[final_cuil]["calculation"] += data["calculation"] + "\n"

        return result
