from odoo import api, fields, models, _
import base64
import xlsxwriter
import time as _time
from io import BytesIO
from odoo.exceptions import UserError
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

# Sectores de Gastos Indirectos: quedan fuera de los pools GS y GG
GI_SECTOR_PGK_ID = 4114
GI_SECTOR_CALYX_ID = 5331
GI_SECTOR_IDS = (GI_SECTOR_PGK_ID, GI_SECTOR_CALYX_ID)
REPORT_CURRENCY_ID = 19  # PES

# Grupos de negocio bajo los que se reparte la bolsa de Gastos Indirectos
BUSINESS_GROUP_TECNOLOGIA_ID = 22
BUSINESS_GROUP_SERVICIOS_ID = 21

# Diferencia de cambio comercial: cuentas destino de las lineas que faltan crear
CALYX_COMPANY_ID = 3
EXCHANGE_DIFF_ACCOUNT_PGK_ID = 812
EXCHANGE_DIFF_ACCOUNT_CALYX_ID = 5487
EXCHANGE_DIFF_CODE = "4.2.1.01.020"
EXCHANGE_DIFF_CODE_ALT = "5.8.1.01.016"

# Textos de la descripcion de cada distribucion: prefijo y rotulo del total
POOL_TEXTS = {
    "GI": ("Dist. Gtos. Indirectos", "Total fact.:"),
    "GS": ("Dist. Gtos. Sector", "Total fact. S:"),
    "GG": ("Dist. Gtos. Gcia.", "Total fact. G:"),
}


class AccountConsolidationReport(models.Model):
    _name = "account.consolidation.report"
    _description = "Export consolidation report"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Name",
        tracking=True
    )
    period = fields.Char(
        compute="_compute_period",
        string="Period"
    )
    consolidation_period = fields.Many2one(
        "account.consolidation.period",
        string="Select a period",
        tracking=True
    )
    export_consolidation_data = fields.Text(
        string="File content"
    )
    export_consolidation_file = fields.Binary(
        string="Download File",
        compute="_compute_files",
        readonly=True
    )
    export_consolidation_filename = fields.Char(
        string="File consolidation",
        compute="_compute_files",
        readonly=True
    )
    has_period_data = fields.Boolean(
        compute="_compute_has_period_data",
    )

    @api.depends("consolidation_period")
    def _compute_period(self):
        for record in self:
            if record.consolidation_period:
                record.period = record.consolidation_period.period
            else:
                record.period = "/"

    @api.depends("consolidation_period")
    def _compute_has_period_data(self):
        data_obj = self.env["account.consolidation.data"]
        for record in self:
            record.has_period_data = bool(record.consolidation_period) and bool(
                data_obj.search_count([
                    ("consolidation_period_id", "=", record.consolidation_period.id),
                ])
            )

    @api.onchange("consolidation_period")
    def _onchange_consolidation_period(self):
        for record in self:
            if record.consolidation_period:
                record.name = (
                    _("Consolidation Report: ")
                    + str(record.consolidation_period.date_from)
                    + " "
                    + str(record.consolidation_period.date_to)
                )
            else:
                record.name = "/"

    def compute_consolidation_data(self):
        for record in self:
            data = {}
            totals = {}
            if record.consolidation_period.consolidation_companies:
                data = record.prepare_excel_data()
                totals = record.get_totals(data)
                # Create Excel file
                output = BytesIO()
                workbook = xlsxwriter.Workbook(output)
                worksheet = workbook.add_worksheet(_("Consolidated Report"))

                # Add headers
                bold = workbook.add_format(
                    {
                        "bold": True,
                        "align": "center",
                    }
                )
                merge_format = workbook.add_format(
                    {
                        "bold": 1,
                        "border": 1,
                        "align": "left",
                        "valign": "vleft",
                        "fg_color": "gray",
                    }
                )
                total_format = workbook.add_format(
                    {
                        "bold": 1,
                        "border": 1,
                        "align": "left",
                        "valign": "vleft",
                        "fg_color": "gray",
                        "num_format": "$#,##0.00",
                    }
                )
                currency_format = workbook.add_format({"num_format": "$#,##0.00"})
                headers = [
                    _("Description"),
                    _("Account Name"),
                    _("Companies"),
                    _("Target Currency"),
                    _("Currency"),
                    _("Rate"),
                    _("Amount"),
                    _("Total"),
                ]

                worksheet.set_column("A:A", 1)
                worksheet.set_column("A:A", 50)
                worksheet.set_column("B:B", 1)
                worksheet.set_column("B:B", 30)
                worksheet.set_column("C:C", 1)
                worksheet.set_column("C:C", 18)
                worksheet.set_column("D:D", None, None, {"hidden": True})
                worksheet.set_column("E:E", 1)
                worksheet.set_column("E:E", 18)
                worksheet.set_column("F:F", 1)
                worksheet.set_column("F:F", 18)
                worksheet.set_column("G:G", 1)
                worksheet.set_column("G:G", 18)
                worksheet.set_column("H:H", 1)
                worksheet.set_column("H:H", 18)

                for i, header in enumerate(headers):
                    worksheet.write(0, i, header, bold)

                row = 1
                for grandfather_group, mother_groups in data.items():
                    for mother_group, grandmother_accounts in mother_groups.items():
                        for (
                            grandmother_account,
                            mother_accounts,
                        ) in grandmother_accounts.items():
                            for mother_account, companies in mother_accounts.items():
                                for company, daughter_accounts in companies.items():
                                    for (
                                        daughter_account,
                                        vals,
                                    ) in daughter_accounts.items():
                                        worksheet.merge_range(
                                            row,
                                            0,
                                            row,
                                            6,
                                            grandfather_group,
                                            merge_format,
                                        )
                                        worksheet.write(
                                            row,
                                            7,
                                            totals[grandfather_group]["total"],
                                            total_format,
                                        )
                                        row += 1
                                        worksheet.merge_range(
                                            row,
                                            0,
                                            row,
                                            6,
                                            grandfather_group + " / " + mother_group,
                                            merge_format,
                                        )
                                        worksheet.write(
                                            row,
                                            7,
                                            totals[grandfather_group][mother_group][
                                                "total"
                                            ],
                                            total_format,
                                        )
                                        row += 1
                                        worksheet.merge_range(
                                            row,
                                            0,
                                            row,
                                            6,
                                            grandfather_group
                                            + " / "
                                            + mother_group
                                            + " / "
                                            + grandmother_account,
                                            merge_format,
                                        )
                                        worksheet.write(
                                            row,
                                            7,
                                            totals[grandfather_group][mother_group][
                                                grandmother_account
                                            ]["total"],
                                            total_format,
                                        )
                                        row += 1
                                        worksheet.merge_range(
                                            row,
                                            0,
                                            row,
                                            6,
                                            grandfather_group
                                            + " / "
                                            + mother_group
                                            + " / "
                                            + grandmother_account
                                            + " / "
                                            + mother_account,
                                            merge_format,
                                        )
                                        worksheet.write(
                                            row,
                                            7,
                                            totals[grandfather_group][mother_group][
                                                grandmother_account
                                            ][mother_account]["total"],
                                            total_format,
                                        )
                                        row += 1
                                        worksheet.merge_range(
                                            row,
                                            0,
                                            row,
                                            6,
                                            grandfather_group
                                            + " / "
                                            + mother_group
                                            + " / "
                                            + grandmother_account
                                            + " / "
                                            + mother_account
                                            + "/"
                                            + company,
                                            merge_format,
                                        )
                                        worksheet.write(
                                            row,
                                            7,
                                            totals[grandfather_group][mother_group][
                                                grandmother_account
                                            ][mother_account][company]["total"],
                                            total_format,
                                        )
                                        row += 1
                                        worksheet.merge_range(
                                            row,
                                            0,
                                            row,
                                            6,
                                            grandfather_group
                                            + " / "
                                            + mother_group
                                            + " / "
                                            + grandmother_account
                                            + " / "
                                            + mother_account
                                            + "/"
                                            + company
                                            + "/"
                                            + daughter_account,
                                            merge_format,
                                        )
                                        row += 1
                                        for val in vals:
                                            worksheet.write(row, 0, val["description"])
                                            worksheet.write(row, 1, val["account_id"])
                                            worksheet.write(row, 2, val["company"])
                                            worksheet.write(
                                                row, 3, val["currency_origin"]
                                            )
                                            worksheet.write(row, 4, val["currency"])
                                            worksheet.write(row, 5, val["rate"])
                                            worksheet.write(
                                                row, 6, val["amount"], currency_format
                                            )
                                            row += 1

                # Save and encode file
                workbook.close()
                output.seek(0)
                file_data = output.read()
                encoded_file = base64.encodebytes(file_data)

                # Set values on model
                record.export_consolidation_data = encoded_file

    def prepare_excel_data(self):
        data = {}

        analytic_lines = self.env["account.analytic.line"].search(
            [
                ("date", ">=", self.consolidation_period.date_from),
                ("date", "<=", self.consolidation_period.date_to),
            ]
        )

        for analytic_line in analytic_lines:
            if analytic_line.debit == 0 and analytic_line.credit == 0:
                _logger.info(f"Línea descartada, ID {analytic_line.id}")
                continue

            analytic_line.update_currency_id()

            group_key = analytic_line.parent_prin_group_id.name or "Undefined"
            mother_key = analytic_line.bussines_group_id.name or "Undefined"
            grandmother_key = analytic_line.sector_account_id.name or "Undefined"
            mother_account_key = analytic_line.managment_account_id.name or "Undefined"
            daughter_account_key = analytic_line.name or "Undefined"
            company = analytic_line.move_company_id.name or "Undefined"

            consolidation_period = (
                self.consolidation_period.consolidation_companies.filtered(
                    lambda x: x.company_id == analytic_line.move_id.company_id
                )[:1]  # Toma solo el primer registro si hay múltiples
            )
            currency_origin = (
                consolidation_period.currency_id.symbol
                if consolidation_period
                else analytic_line.currency_id.symbol
            )
            new_currency = (
                consolidation_period.new_currency.symbol
                if consolidation_period
                else analytic_line.currency_id.symbol
            )
            rate = (
                consolidation_period.rate
                if consolidation_period and not consolidation_period.historical_rate
                else 1
            )

            daughter_account = (
                data.setdefault(group_key, {})
                .setdefault(mother_key, {})
                .setdefault(grandmother_key, {})
                .setdefault(mother_account_key, {})
                .setdefault(company, {})
                .setdefault(daughter_account_key, [])
            )

            raw_amount = (
                analytic_line.amount * rate
                if not consolidation_period
                or not consolidation_period.historical_rate
                else analytic_line.amount
            )
            daughter_account.append(
                {
                    "account_id": analytic_line.general_account_id.code,
                    "company": company,
                    "currency_origin": currency_origin if currency_origin else "",
                    "currency": new_currency if new_currency else "",
                    "rate": rate,
                    "description": analytic_line.name or "",
                    "amount": raw_amount,
                }
            )

        return data

    @api.depends("export_consolidation_data", "period")
    def _compute_files(self):
        for record in self:
            filename = _("Consolidation-%s.xls") % (record.period)
            record.export_consolidation_filename = filename
            if record.export_consolidation_data:
                record.export_consolidation_file = record.export_consolidation_data
            else:
                record.export_consolidation_file = False

    def get_totals(self, data):
        totals = {}

        for group_key, group_value in data.items():
            group_total = 0
            group_dict = {"total": group_total}

            for mother_key, mother_value in group_value.items():
                mother_dict = self.calculate_mother_totals(mother_value)
                group_total += mother_dict["total"]
                group_dict[mother_key] = mother_dict

            group_dict["total"] = group_total
            totals[group_key] = group_dict

        return totals

    def calculate_mother_totals(self, mother_value):
        mother_total = 0
        mother_dict = {"total": mother_total}

        for grandmother_key, grandmother_value in mother_value.items():
            grandmother_dict = self.calculate_grandmother_totals(grandmother_value)
            mother_total += grandmother_dict["total"]
            mother_dict[grandmother_key] = grandmother_dict

        mother_dict["total"] = mother_total
        return mother_dict

    def calculate_grandmother_totals(self, grandmother_value):
        grandmother_total = 0
        grandmother_dict = {"total": grandmother_total}

        for mother_account_key, mother_account_value in grandmother_value.items():
            mother_account_dict = self.calculate_mother_account_totals(
                mother_account_value
            )
            grandmother_total += mother_account_dict["total"]
            grandmother_dict[mother_account_key] = mother_account_dict

        grandmother_dict["total"] = grandmother_total
        return grandmother_dict

    def calculate_mother_account_totals(self, mother_account_value):
        mother_account_total = 0
        mother_account_dict = {"total": mother_account_total}

        for (
            daughter_account_key,
            daughter_account_value,
        ) in mother_account_value.items():
            daughter_account_dict = self.calculate_daughter_account_totals(
                daughter_account_value
            )
            mother_account_total += daughter_account_dict["total"]
            mother_account_dict[daughter_account_key] = daughter_account_dict

        mother_account_dict["total"] = mother_account_total
        return mother_account_dict

    def calculate_daughter_account_totals(self, daughter_account_value):
        daughter_account_total = 0
        daughter_account_dict = {"total": daughter_account_total}

        for company_key, company_value in daughter_account_value.items():
            company_total = sum(entry["amount"] for entry in company_value)
            daughter_account_total += company_total
            company_dict = {"entry": {"total": company_total}}
            daughter_account_dict[company_key] = company_dict

        daughter_account_dict["total"] = daughter_account_total
        return daughter_account_dict

    ###########
    # REPORTE #
    ###########

    def validate_employees_departments(self):
        """
        Valida que todos los empleados tengan departamento asignado y configuración correcta.
        Recolecta empleados por nombre y línea analítica por ID sin romper el flujo.
        """

        timesheets = self.env["timesheet.sige"].search([
            ("start_of_period", ">=", self.consolidation_period.date_from),
            ("end_of_period", "<=", self.consolidation_period.date_to),
        ])

        # Listas de errores separadas por tipo
        employees_without_department = []
        employees_without_analytic_account = []
        employees_with_department = []
        analytic_lines_info = []

        for timesheet in timesheets:
            employee = timesheet.employee_id
            if employee:
                employee_info = {
                    'employee_id': employee.id,
                    'employee_name': employee.name,
                    'department_id': employee.department_id.id if employee.department_id else False,
                    'department_name': (employee.department_id.name
                                        if employee.department_id else 'Sin departamento'),
                    'analytic_account_id': (
                        employee.department_id.analytic_account.id
                        if employee.department_id and employee.department_id.analytic_account
                        else False
                    ),
                    'analytic_account_name': (
                        employee.department_id.analytic_account.name
                        if employee.department_id and employee.department_id.analytic_account
                        else 'Sin cuenta analítica'
                    ),
                }

                # Validación 1: Empleado sin departamento
                if not employee.department_id:
                    employees_without_department.append(employee_info)
                else:
                    # Validación 2: Empleado sin cuenta analítica en departamento
                    if not employee.department_id.analytic_account:
                        employees_without_analytic_account.append(employee_info)
                    else:
                        employees_with_department.append(employee_info)

                # Recolectar información de líneas analíticas
                for analytic_line in timesheet.timesheet_ids:
                    analytic_lines_info.append({
                        'analytic_line_id': analytic_line.id,
                        'analytic_line_name': analytic_line.name,
                        'employee_name': employee.name,
                        'account_id': analytic_line.account_id.id,
                        'account_name': analytic_line.account_id.name,
                        'amount': analytic_line.amount,
                        'date': analytic_line.date
                    })

        # Construir mensaje de error con todos los problemas encontrados
        error_messages = []

        if employees_without_department:
            employee_names = [emp['employee_name'] for emp in employees_without_department]
            error_messages.append(
                "1. EMPLEADOS SIN DEPARTAMENTO (%d empleados):\n   • %s" % (
                    len(employees_without_department),
                    '\n   • '.join(employee_names)
                )
            )

        if employees_without_analytic_account:
            employee_names = [emp['employee_name'] for emp in employees_without_analytic_account]
            error_messages.append(
                "2. EMPLEADOS SIN CUENTA ANALÍTICA EN DEPARTAMENTO (%d empleados):\n   • %s" % (
                    len(employees_without_analytic_account),
                    '\n   • '.join(employee_names)
                )
            )

        # Si hay errores, lanzar UserError con todos los problemas
        if error_messages:
            full_error_message = (
                "ERRORES ENCONTRADOS EN LA CONFIGURACIÓN DE EMPLEADOS:\n\n"
                + "\n\n".join(error_messages)
            )
            full_error_message += (
                "\n\nPor favor, corrija estos problemas "
                "antes de continuar con el reporte de consolidación."
            )
            raise UserError(_(full_error_message))

        return {
            'employees_without_department': employees_without_department,
            'employees_without_analytic_account': employees_without_analytic_account,
            'employees_with_department': employees_with_department,
            'analytic_lines_info': analytic_lines_info
        }

    def generate_consolidation_report_view(self):
        # Mensaje de prueba en el chatter
        self.message_post(
            body=(
                "Inicio de generación del reporte de consolidación - "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            subject="Inicio del proceso"
        )

        # Diccionario para rastrear cuentas analíticas ya registradas en el chatter
        logged_multiple_projects_main = set()

        # Validar empleados y departamentos antes de continuar
        _t = _time.time()
        self.validate_employees_departments()
        _logger.warning(
            "[TIMING] validate_employees_departments: %.2fs",
            _time.time() - _t,
        )
        _t = _time.time()

        # Elimino si es que existen lineas analiticas de redistribucion de gastos indirectos
        # creadas anteriormente (en caso que el informe se pide mas de una vez) y lineas de
        # account consolidation data por el mismo motivo
        self.delete_entries()
        _logger.warning("[TIMING] delete_entries: %.2fs", _time.time() - _t)
        _t = _time.time()

        # Creacion de lineas analiticas que surgen de asientos contables automaticos y no se crearon
        self.create_missing_analytic_lines()
        _logger.warning(
            "[TIMING] create_missing_analytic_lines: %.2fs",
            _time.time() - _t,
        )
        _t = _time.time()

        # Crear lineas analiticas a partir del parte de horas excluyendo las no facturables que
        # luego se redistribuiran a los proyectos a partir de su porcentaje en el metodo anterior
        self.create_analytic_lines_from_timesheets()
        _logger.warning(
            "[TIMING] create_analytic_lines_from_timesheets: %.2fs",
            _time.time() - _t,
        )
        _t = _time.time()

        # Calculo el monto total de las lineas de 'Gastos Indirectos'
        total_amount_cost = self.calculate_total_amount_cost()
        _logger.warning(
            "[TIMING] calculate_total_amount_cost: %.2fs",
            _time.time() - _t,
        )
        _t = _time.time()

        # entre estos cuatro pasos no se crean lineas: comparten la misma foto
        convert_cache = self._build_convert_amount_cache()

        # Bolsas de gastos de sector (GS) y de gerencia (GG)
        total_amount_cost_sector = self.calculate_total_amount_cost_sector(convert_cache)
        total_amount_cost_management = self.calculate_total_amount_cost_management(
            convert_cache
        )
        _logger.warning(
            "[TIMING] pools GS (%d) y GG (%d): %.2fs",
            len(total_amount_cost_sector),
            len(total_amount_cost_management),
            _time.time() - _t,
        )
        _t = _time.time()

        # Crear diccionario facturacion por proyecto
        total_sales_for_project = self.sales_by_project(convert_cache)
        sales_by_sector, sales_by_management = self.sales_by_level(convert_cache)
        _logger.warning("[TIMING] sales_by_project: %.2fs", _time.time() - _t)
        _t = _time.time()

        # Recien aca se vacian las bolsas GS y GG: solo las que se pueden repartir
        total_amount_cost_sector = self._dischargeable_pools(
            total_amount_cost_sector, sales_by_sector, "GS"
        )
        total_amount_cost_management = self._dischargeable_pools(
            total_amount_cost_management, sales_by_management, "GG"
        )
        _logger.warning(
            "[TIMING] descarga bolsas GS (%d) y GG (%d): %.2fs",
            len(total_amount_cost_sector),
            len(total_amount_cost_management),
            _time.time() - _t,
        )
        _t = _time.time()

        # Calculo el porcentaje de facturacion de cada projecto
        percentage_for_project = self.calculate_percentage(total_sales_for_project)
        _logger.warning(
            "[TIMING] calculate_percentage: %.2fs", _time.time() - _t,
        )
        _t = _time.time()

        self.env.cr.execute(
            """
            UPDATE account_analytic_line aal
            SET currency_id = aml.currency_id
            FROM account_move_line aml
            WHERE aal.move_id = aml.id
              AND aal.currency_id != aml.currency_id
              AND aal.date >= %s AND aal.date <= %s
            """,
            (self.consolidation_period.date_from, self.consolidation_period.date_to)
        )
        _logger.warning(
            "[TIMING] UPDATE currency_id SQL: %.2fs", _time.time() - _t,
        )
        _t = _time.time()

        analytic_lines = self.env["account.analytic.line"].search(
            [
                ("date", ">=", self.consolidation_period.date_from),
                ("date", "<=", self.consolidation_period.date_to),
            ]
        )
        _logger.warning(
            "[TIMING] search analytic_lines (%d registros): %.2fs",
            len(analytic_lines),
            _time.time() - _t,
        )
        _t = _time.time()

        all_projects = self.env["project.project"].search(
            ["|", ("active", "=", False), ("active", "=", True)]
        )
        projects_by_account = {}
        for _p in all_projects:
            projects_by_account.setdefault(_p.analytic_account_id.id, []).append(_p)

        move_data, comp_to_period = self._build_convert_amount_cache()
        comp_by_company_id = {
            cp.company_id.id: cp for cp in self.consolidation_period.consolidation_companies
        }

        consolidation_data_vals = []
        multiple_projects_msgs = []

        _accounts = analytic_lines.account_id
        _debit_by_account = {a.id: a.debit for a in _accounts}
        _credit_by_account = {a.id: a.credit for a in _accounts}
        _logger.warning(
            "[TIMING] precompute debit/credit (%d cuentas): %.2fs",
            len(_accounts),
            _time.time() - _t,
        )
        _t = _time.time()

        for _f in (
            'parent_prin_group_id',
            'bussines_group_id',
            'sector_account_id',
            'managment_account_id',
        ):
            _t2 = _time.time()
            analytic_lines.mapped(_f)
            _logger.warning("[TIMING] recompute %s: %.2fs", _f, _time.time() - _t2)
        _t = _time.time()

        for analytic_line in analytic_lines:
            _acc = analytic_line.account_id.id
            if _debit_by_account.get(_acc, 0) == 0 and _credit_by_account.get(_acc, 0) == 0:
                _logger.info(f"Línea descartada, ID {analytic_line.id}")
                continue
            elif (
                analytic_line.general_account_id
                and analytic_line.general_account_id.code.startswith("4.2")
                and analytic_line.move_id
            ):
                if analytic_line.move_id.debit == 0 and analytic_line.move_id.credit == 0:
                    _logger.info(f"Línea descartada, ID {analytic_line.id}")
                    continue
            _row = move_data.get(analytic_line.id, {})
            _move_company_id = _row.get('move_company_id')
            _src_company_id = _row.get('src_move_company_id')
            consolidation_period = (
                comp_by_company_id.get(_move_company_id)
                or comp_by_company_id.get(_src_company_id)
            )
            currency_origin = analytic_line.currency_id.id
            new_currency = (
                consolidation_period.new_currency.id if consolidation_period
                else analytic_line.currency_id.id
            )
            is_historical = False
            rate = 1
            if analytic_line.consolidation_line and analytic_line.source_analytic_line_id:
                # Counterpart ya convertido por calculate_total_amount_cost o
                # create_analytic_lines_from_timesheets — no aplicar tasa de nuevo.
                is_historical = True
                rate = 1
            elif consolidation_period:
                if not consolidation_period.historical_rate:
                    rate = consolidation_period.rate
                elif (
                    _row.get('move_currency_id')
                    and _row.get('move_currency_id') != _row.get('company_currency_id')
                ):
                    is_historical = True
                    if _row.get('l10n_ar_rate'):
                        rate = _row['l10n_ar_rate']
                    elif _row.get('computed_rate'):
                        rate = _row['computed_rate']
                    else:
                        rate = 1
                else:
                    is_historical = True
                    rate = 1
            else:
                rate = 1
            # Busca el proyecto para cada linea analitica y permitir la agrupacion
            project_ids = projects_by_account.get(analytic_line.account_id.id, [])

            # Si hay múltiples proyectos, registrar en el chatter (una vez por cuenta analítica)
            if len(project_ids) > 1:
                if analytic_line.account_id.id not in logged_multiple_projects_main:
                    logged_multiple_projects_main.add(analytic_line.account_id.id)
                    multiple_projects_msgs.append(
                        self._multiple_projects_message(analytic_line, project_ids)
                    )

            project_id = False if not project_ids else project_ids[0].id

            management_account_id = analytic_line.managment_account_id.id

            line_amount = analytic_line.amount * rate if not is_historical else analytic_line.amount

            consolidation_data_vals.append(
                {
                    "name": self.name,
                    "consolidation_period_id": self.consolidation_period.id,
                    "main_group": analytic_line.parent_prin_group_id.id,
                    "project_id": project_id,
                    "business_group": analytic_line.bussines_group_id.id,
                    "sector_account_group": analytic_line.sector_account_id.id,
                    "managment_account_group": management_account_id,
                    # si es linea consolidada que no muestre compañias
                    "company": (
                        analytic_line.company_id.ids if analytic_line.consolidation_line else False
                    ),
                    "daughter_account": analytic_line.id,
                    "source_analytic_line_id": (
                        analytic_line.source_analytic_line_id.id
                        if (
                            analytic_line.consolidation_line
                            and analytic_line.source_analytic_line_id
                        )
                        else analytic_line.id
                    ),
                    "description": analytic_line.name or "",
                    # si es linea consolidada que no la muestre
                    "account_id": (
                        analytic_line.general_account_id.code
                        if analytic_line.consolidation_line
                        else False
                    ),
                    "currency_origin": currency_origin if currency_origin else "",
                    "currency": new_currency if new_currency else "",
                    "rate": rate,
                    "amount": line_amount
                }
            )

        _logger.warning(
            "[TIMING] loop principal (%d vals): %.2fs",
            len(consolidation_data_vals),
            _time.time() - _t,
        )
        _t = _time.time()

        self._post_multiple_projects(multiple_projects_msgs)
        _logger.warning(
            "[TIMING] message_post múltiples proyectos (%d avisos): %.2fs",
            len(multiple_projects_msgs),
            _time.time() - _t,
        )
        _t = _time.time()

        # Aplico el porcentaje de la facturacion a los gastos indirectos y creo las lineas
        consolidation_data_vals_cost = self.cost_to_project(
            percentage_for_project, total_amount_cost
        )
        consolidation_data_vals_cost += self.cost_to_project_by_level(
            total_amount_cost_sector, sales_by_sector, "GS"
        )
        consolidation_data_vals_cost += self.cost_to_project_by_level(
            total_amount_cost_management, sales_by_management, "GG"
        )
        _logger.warning("[TIMING] cost_to_project: %.2fs", _time.time() - _t)
        _t = _time.time()

        self.analytic_line_cost(consolidation_data_vals_cost)
        _logger.warning(
            "[TIMING] analytic_line_cost: %.2fs", _time.time() - _t,
        )
        _t = _time.time()

        consolidation_data = self.env["account.consolidation.data"]
        consolidation_data.create(consolidation_data_vals)
        consolidation_data.create(consolidation_data_vals_cost)
        _logger.warning(
            "[TIMING] create consolidation_data: %.2fs", _time.time() - _t,
        )
        _t = _time.time()

        return self._get_consolidation_data_action()

    def _get_consolidation_data_action(self):
        self.ensure_one()
        view_id_tree = self.env.ref("consolidation_report.view_consolidation_data_tree")
        return {
            "name": "Consolidation Report",
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "tree,form",
            "res_model": "account.consolidation.data",
            "views": [(view_id_tree.id, "tree")],
            "domain": [("consolidation_period_id", "=", self.consolidation_period.id)],
            "context": {
                "tree_view_ref": "view_consolidation_data_tree",
                "group_by_no_leaf": 1,
            },
            "target": "current",
        }

    def delete_entries(self):
        self.ensure_one()
        self.env.cr.execute("""
            DROP INDEX IF EXISTS account_analytic_line_consolidation_idx;
            CREATE INDEX IF NOT EXISTS account_analytic_line_consolidation_period_idx
            ON account_analytic_line (consolidation_line, date) WHERE consolidation_line = TRUE
        """)
        self.env.cr.execute(
            "DELETE FROM account_consolidation_data WHERE consolidation_period_id = %s",
            (self.consolidation_period.id,)
        )
        self.env.cr.execute(
            """
            DELETE FROM account_analytic_line
            WHERE consolidation_line = TRUE AND date >= %s AND date <= %s
            """,
            (self.consolidation_period.date_from, self.consolidation_period.date_to)
        )
        # Para limpiar lo anterior a la implementacion de periodos.
        self.env.cr.execute(
            "DELETE FROM account_consolidation_data WHERE consolidation_period_id IS NULL"
        )

    def _multiple_projects_message(self, analytic_line, projects):
        """Aviso de que una cuenta analitica tiene mas de un proyecto colgado."""
        project_names = ", ".join(f"{p.name} (ID: {p.id})" for p in projects)
        line_description = (
            analytic_line.name or f"Línea analítica ID: {analytic_line.id}"
        )
        account = analytic_line.account_id
        return (
            f"⚠️ Múltiples proyectos encontrados para la cuenta analítica "
            f"'{account.name}' (ID: {account.id}). "
            f"Línea analítica: {line_description} (ID: {analytic_line.id}). "
            f"Se seleccionó el primero: {projects[0].name} (ID: {projects[0].id}). "
            f"Proyectos encontrados: {project_names}"
        )

    def _post_multiple_projects(self, messages):
        """Un solo mensaje en el chatter con todos los avisos juntos."""
        if messages:
            self.message_post(
                body="<br/>".join(messages),
                subject="Múltiples proyectos para cuenta analítica",
            )

    def sales_by_project(self, cache=None):
        """Facturacion por proyecto, separada por grupo de negocio."""
        move_data, comp_to_period = cache or self._build_convert_amount_cache()

        all_projects = self.env["project.project"].search(
            ["|", ("active", "=", False), ("active", "=", True)]
        )
        _sbp_by_account = {}
        for _p in all_projects:
            _sbp_by_account.setdefault(_p.analytic_account_id.id, []).append(_p)

        multiple_projects_logged = set()  # Para evitar logs repetidos
        multiple_projects_msgs = []

        project_sales = {}
        for clave, grupo_id in (
            ("calyx", BUSINESS_GROUP_TECNOLOGIA_ID),
            ("otros", BUSINESS_GROUP_SERVICIOS_ID),
        ):
            analytic_lines = self.env["account.analytic.line"].search([
                ("date", ">=", self.consolidation_period.date_from),
                ("date", "<=", self.consolidation_period.date_to),
                ("general_account_id.code", "like", "4.1%"),
                ("general_account_id.user_type_id.name", "=", "Ingreso"),
                ("bussines_group_id", "=", grupo_id),
            ])

            sales = {}
            total = 0.0
            for line in analytic_lines:
                projects = _sbp_by_account.get(line.account_id.id, [])
                project = projects[0] if projects else self.env["project.project"]

                if (
                    len(projects) > 1
                    and line.account_id.id not in multiple_projects_logged
                ):
                    multiple_projects_logged.add(line.account_id.id)
                    multiple_projects_msgs.append(
                        self._multiple_projects_message(line, projects)
                    )

                amount = self._convert_amount(line, move_data, comp_to_period)
                if project and amount != 0.0:
                    total += amount
                    sales[project.id] = sales.get(project.id, 0.0) + amount

            # el total viaja dentro del mismo diccionario, sin redondeo
            sales[f"total_sales_{clave}"] = total
            project_sales[clave] = sales

        self._post_multiple_projects(multiple_projects_msgs)

        return project_sales

    def calculate_total_amount_cost(self):
        """Bolsa de Gastos Indirectos, separada por sector: Calyx y el resto."""
        move_data, comp_to_period = self._build_convert_amount_cache()

        totals = {}
        vals_list = []
        for clave, sector_id in (
            ("calyx", GI_SECTOR_CALYX_ID),
            ("otros", GI_SECTOR_PGK_ID),
        ):
            analytic_lines = self.env["account.analytic.line"].search([
                ("date", ">=", self.consolidation_period.date_from),
                ("date", "<=", self.consolidation_period.date_to),
                ("sector_account_id", "=", sector_id),
            ])

            total = 0.0
            for analytic_line in analytic_lines:
                amount = self._convert_amount(analytic_line, move_data, comp_to_period)
                total += amount
                vals_list.append({
                    "name": f"{analytic_line.name} - Línea consolidación",
                    "account_id": analytic_line.account_id.id,
                    # hereda la gerencia de la linea que cancela
                    "managment_account_id": analytic_line.managment_account_id.id,
                    "amount": -1 * amount,
                    "unit_amount": analytic_line.unit_amount,
                    "product_id": (
                        analytic_line.product_id.id if analytic_line.product_id else False
                    ),
                    "date": analytic_line.date,
                    "currency_id": (
                        analytic_line.currency_id.id if analytic_line.currency_id else False
                    ),
                    "company_id": (
                        [(6, 0, analytic_line.company_id.ids)]
                        if analytic_line.company_id
                        else False
                    ),
                    "consolidation_line": True,
                    "source_analytic_line_id": analytic_line.id,
                })
            totals[f"total_amount_cost_{clave}"] = total

        if vals_list:
            self.env["account.analytic.line"].create(vals_list)

        # Devuelve un diccionario con los montos totales sin redondeo
        return totals

    def calculate_percentage(self, sales_dict):
        percentages = {
            "calyx": [],
            "otros": []
        }

        # Calcular los porcentajes para Calyx (sin redondeo en los cálculos)
        total_sales_calyx = sales_dict["calyx"]["total_sales_calyx"]
        for project, sales in sales_dict["calyx"].items():
            if project != "total_sales_calyx":  # Ignorar la clave 'total_sales_calyx'
                sales_rounded = sales
                percentage = (sales_rounded / total_sales_calyx) * 100 if total_sales_calyx else 0.0
                if percentage != 0.00:
                    percentages["calyx"].append(
                        {
                            "project_id": project,
                            "sales": sales_rounded,
                            "percentage": percentage,
                            "total_sales": total_sales_calyx
                        }
                    )

        # Calcular los porcentajes para Otros (sin redondeo en los cálculos)
        total_sales_otros = sales_dict["otros"]["total_sales_otros"]
        for project, sales in sales_dict["otros"].items():
            if project != "total_sales_otros":  # Ignorar la clave 'total_sales_otros'
                sales_rounded = sales
                percentage = (sales_rounded / total_sales_otros) * 100 if total_sales_otros else 0.0
                if percentage != 0.00:
                    percentages["otros"].append(
                        {
                            "project_id": project,
                            "sales": sales_rounded,
                            "percentage": percentage,
                            "total_sales": total_sales_otros
                        }
                    )

        return percentages

    def create_analytic_lines_from_timesheets(self):
        analytic_line_obj = self.env["account.analytic.line"]
        timesheets = self.env["timesheet.sige"].search([
            ("start_of_period", ">=", self.consolidation_period.date_from),
            ("end_of_period", "<=", self.consolidation_period.date_to),
        ])
        not_project_ids = []
        sum = 0

        all_projects_ts = self.env["project.project"].search(
            ["|", ("active", "=", False), ("active", "=", True)]
        )
        projects_by_account_ts = {}
        for _p in all_projects_ts:
            if _p.analytic_account_id.id not in projects_by_account_ts:
                projects_by_account_ts[_p.analytic_account_id.id] = _p

        all_timesheet_lines = analytic_line_obj.search([
            ("date", ">=", self.consolidation_period.date_from),
            ("date", "<=", self.consolidation_period.date_to),
            ("consolidation_line", "=", False),
            ("move_id", "=", False),
            ("amount", "!=", 0),
            "|",
            ("timesheet_id", "!=", False),
            ("employee_id", "!=", False),
        ])

        vals_to_create = []
        for analytic_line in all_timesheet_lines:
            project = projects_by_account_ts.get(analytic_line.account_id.id)
            if not project:
                sum += analytic_line.amount
                not_project_ids.append(analytic_line.amount)
                continue
            if analytic_line.project_id.is_non_billable:
                # la hora no facturable se cancela sobre su propia cuenta:
                # la gerencia del empleado no recibe credito por ella
                account_id = analytic_line.account_id.id
            else:
                employee = (
                    analytic_line.employee_id
                    or analytic_line.timesheet_id.employee_id
                )
                account = getattr(
                    employee.department_id,
                    'analytic_account',
                    False
                )
                account_id = account.id if account else False
            if not account_id:
                continue
            vals_to_create.append({
                "name": f"Costo laboral - {analytic_line.name} - Línea consolidación",
                "account_id": account_id,
                "managment_account_id": account_id,
                "amount": -1 * analytic_line.amount,
                "unit_amount": analytic_line.unit_amount,
                "product_id": (
                    analytic_line.product_id.id if analytic_line.product_id else False
                ),
                "date": analytic_line.date,
                "currency_id": (
                    analytic_line.currency_id.id if analytic_line.currency_id else False
                ),
                "company_id": (
                    [(6, 0, analytic_line.company_id.ids)]
                    if analytic_line.company_id else False
                ),
                "consolidation_line": True,
                "source_analytic_line_id": analytic_line.id,
            })
        if vals_to_create:
            analytic_line_obj.with_context(only_active_employees=True).create(vals_to_create)
        total_not_billable = timesheets.timesheet_ids.filtered(
            lambda line: not line.project_id.allow_billable and line.amount != 0
        ).mapped('amount')
        _logger.info(f"Total no facturable:{total_not_billable}")
        return total_not_billable

    def get_sector_id(self, project):
        current_account = project.analytic_account_id

        while current_account:
            if current_account.is_sector_group:
                return current_account.id
            current_account = current_account.parent_id

        return None

    def _sector_of_account(self, account):
        current_account = account
        while current_account:
            if current_account.is_sector_group:
                return current_account.id
            current_account = current_account.parent_id
        return None

    def _create_pool_counterparts(self, totals_by_account):
        """Contrapartida que vacia cada bolsa de sector o de gerencia."""
        # company_id es Many2many y currency_id se calcula desde ella
        fallback_company = self.env["res.company"].search(
            [("currency_id", "=", REPORT_CURRENCY_ID)], limit=1
        ) or self.env.company

        vals_list = []
        for account, amount in totals_by_account.items():
            if not amount:
                continue
            company = account.company_id.filtered(
                lambda c: c.currency_id.id == REPORT_CURRENCY_ID
            )[:1] or fallback_company
            vals_list.append({
                "name": f"{account.name} - Línea consolidación",
                "account_id": account.id,
                "managment_account_id": (
                    account.id if account.is_management_group else False
                ),
                "amount": -1 * amount,
                "date": self.consolidation_period.date_from,
                "company_id": company.id,
                "consolidation_line": True,
            })
        if vals_list:
            self.env["account.analytic.line"].create(vals_list)

    def calculate_total_amount_cost_sector(self, cache=None):
        """Bolsa de gastos cargados directo a una cuenta de sector, sin proyecto."""
        move_data, comp_to_period = cache or self._build_convert_amount_cache()
        analytic_lines = self.env["account.analytic.line"].search([
            ("date", ">=", self.consolidation_period.date_from),
            ("date", "<=", self.consolidation_period.date_to),
            ("account_id.is_sector_group", "=", True),
            ("account_id", "not in", list(GI_SECTOR_IDS)),
        ])

        totals = {}
        accounts = {}
        for analytic_line in analytic_lines:
            account = analytic_line.account_id
            accounts[account.id] = account
            totals[account.id] = totals.get(account.id, 0.0) + self._convert_amount(
                analytic_line, move_data, comp_to_period
            )

        return totals

    def calculate_total_amount_cost_management(self, cache=None):
        """Bolsa por gerencia: sueldos menos el costo laboral que recupera."""
        move_data, comp_to_period = cache or self._build_convert_amount_cache()
        analytic_lines = self.env["account.analytic.line"].search([
            ("date", ">=", self.consolidation_period.date_from),
            ("date", "<=", self.consolidation_period.date_to),
            ("managment_account_id.is_management_group", "=", True),
        ])
        project_account_ids = {
            p.analytic_account_id.id
            for p in self.env["project.project"].search(
                ["|", ("active", "=", False), ("active", "=", True)]
            )
        }

        totals = {}
        accounts = {}
        for analytic_line in analytic_lines:
            management = analytic_line.managment_account_id
            if self._sector_of_account(management) in GI_SECTOR_IDS:
                continue
            account = analytic_line.account_id
            # lo que tiene proyecto propio se queda en el proyecto
            if account.id in project_account_ids and not account.is_management_group:
                continue
            accounts[management.id] = management
            totals[management.id] = totals.get(management.id, 0.0) + self._convert_amount(
                analytic_line, move_data, comp_to_period
            )

        return totals

    def _dischargeable_pools(self, pools, sales_by_level, label):
        """Descarga solo las bolsas que tienen proyectos donde repartirse."""
        accounts_by_id = {
            a.id: a
            for a in self.env["account.analytic.account"].browse(list(pools))
        }
        dischargeable = {}
        for level_id, amount in pools.items():
            if not amount:
                continue
            if not sum((sales_by_level.get(level_id) or {}).values()):
                _logger.warning(
                    "[%s] Bolsa de '%s' sin facturacion donde repartirse, "
                    "queda sin distribuir: %s",
                    label, accounts_by_id[level_id].name, amount,
                )
                continue
            dischargeable[level_id] = amount
        self._create_pool_counterparts(
            {accounts_by_id[k]: v for k, v in dischargeable.items()}
        )
        return dischargeable

    def sales_by_level(self, cache=None):
        """Facturacion por sector y por gerencia, base de reparto de GS y GG."""
        move_data, comp_to_period = cache or self._build_convert_amount_cache()
        # A diferencia del pool GI, incluye Otros Ingresos (recupero de gastos).
        # internal_group no depende del idioma, el nombre del tipo si.
        analytic_lines = self.env["account.analytic.line"].search([
            ("date", ">=", self.consolidation_period.date_from),
            ("date", "<=", self.consolidation_period.date_to),
            ("general_account_id.user_type_id.internal_group", "=", "income"),
        ])
        projects_by_account = {}
        for project in self.env["project.project"].search(
            ["|", ("active", "=", False), ("active", "=", True)]
        ):
            projects_by_account.setdefault(project.analytic_account_id.id, project)

        by_sector = {}
        by_management = {}
        for analytic_line in analytic_lines:
            project = projects_by_account.get(analytic_line.account_id.id)
            if not project:
                continue
            amount = self._convert_amount(analytic_line, move_data, comp_to_period)
            if not amount:
                continue
            sector_id = self._sector_of_account(project.analytic_account_id)
            management_id = project.analytic_account_id.parent_id.id
            if sector_id:
                sector_sales = by_sector.setdefault(sector_id, {})
                sector_sales[project.id] = sector_sales.get(project.id, 0.0) + amount
            if management_id:
                management_sales = by_management.setdefault(management_id, {})
                management_sales[project.id] = (
                    management_sales.get(project.id, 0.0) + amount
                )
        return by_sector, by_management

    def cost_to_project_by_level(self, pools, sales_by_level, label):
        """Reparte cada bolsa entre los proyectos de su propio sector o gerencia."""
        all_projects = self.env["project.project"].search(
            ["|", ("active", "=", False), ("active", "=", True)]
        )
        projects_by_id = {p.id: p for p in all_projects}
        prefijo, rotulo_total = POOL_TEXTS[label]

        consolidation_data_vals_cost = []
        for level_id, pool_amount in pools.items():
            if not pool_amount:
                continue
            sales = sales_by_level.get(level_id) or {}
            total_sales = sum(sales.values())
            if not total_sales:
                continue
            for project_id, project_sales in sales.items():
                project = projects_by_id.get(project_id)
                if not project or not project.analytic_account_id:
                    continue
                amount = (project_sales / total_sales) * pool_amount
                consolidation_data_vals_cost.append({
                    "name": self.name,
                    "consolidation_period_id": self.consolidation_period.id,
                    "main_group": (
                        project.analytic_account_id.group_id.parent_prin_group.id or ""
                    ),
                    "business_group": (
                        project.analytic_account_id.group_id.parent_id.id or ""
                    ),
                    "sector_account_group": self.get_sector_id(project) or "",
                    "managment_account_group": (
                        project.analytic_account_id.parent_id.id or ""
                    ),
                    "project_id": project_id,
                    "company": project.company_id.ids or "",
                    "description": (
                        f"{prefijo} = (Fact. proyecto: {project_sales} *100 / "
                        f"{rotulo_total} {total_sales}) Total {label} = "
                        f"{pool_amount}"
                    ),
                    "amount": amount,
                    "currency": REPORT_CURRENCY_ID,
                    "rate": 1,
                })
        return consolidation_data_vals_cost

    def cost_to_project(self, percentage_for_project, total_amount_cost):
        _t_sector = 0.0
        all_projects = self.env["project.project"].search(
            ["|", ("active", "=", False), ("active", "=", True)]
        )
        projects_by_id = {p.id: p for p in all_projects}
        prefijo, rotulo_total = POOL_TEXTS["GI"]
        consolidation_data_vals_cost = []

        # Calyx lleva el grupo de negocio fijo; el resto lo deduce del proyecto
        for clave, grupo_fijo in (
            ("calyx", BUSINESS_GROUP_TECNOLOGIA_ID),
            ("otros", None),
        ):
            total_bolsa = total_amount_cost[f"total_amount_cost_{clave}"]
            for project_data in percentage_for_project[clave]:
                project_id = project_data["project_id"]
                percentage = project_data["percentage"]
                sales_project = project_data["sales"]
                total_sales = project_data["total_sales"]

                # Encuentra el proyecto usando el project_id
                project = projects_by_id.get(project_id)
                if not project or not project.analytic_account_id:
                    continue

                cuenta = project.analytic_account_id
                # Calcula el monto a asignar basado en el porcentaje y el costo total
                amount = (percentage / 100.0) * total_bolsa

                _ts = _time.time()
                _sector = self.get_sector_id(project)
                _t_sector += _time.time() - _ts

                # Crea un nuevo elemento consolidation data para ser visto en el informe
                consolidation_data_vals_cost.append({
                    "name": self.name,
                    "consolidation_period_id": self.consolidation_period.id,
                    "main_group": cuenta.group_id.parent_prin_group.id or "",
                    "business_group": (
                        grupo_fijo if grupo_fijo
                        else cuenta.group_id.parent_id.id or ""
                    ),
                    "sector_account_group": _sector or "",
                    "managment_account_group": cuenta.parent_id.id or "",
                    "project_id": project_id,
                    "company": project.company_id.ids or "",
                    "description": (
                        f"{prefijo} = (Fact. proyecto: {sales_project} *100 / "
                        f"{rotulo_total} {total_sales}) Total GI = "
                        f"{total_bolsa}"
                    ),
                    "amount": amount,
                    "currency": REPORT_CURRENCY_ID,
                    "rate": 1,
                    "is_indirect_expense": True,
                })

        _logger.warning(
            "[TIMING] cost_to_project get_sector_id: %.2fs", _t_sector,
        )
        return consolidation_data_vals_cost

    def get_account_id(self, analytic_line, projects_by_id=None):
        project_id = analytic_line.get("project_id")
        if projects_by_id is not None:
            project = projects_by_id.get(project_id)
            return project.analytic_account_id.id if project else None
        all_projects = self.env["project.project"].search(
            ["|", ("active", "=", False), ("active", "=", True)]
        )
        for proj in all_projects:
            if proj.id == project_id:
                return proj.analytic_account_id.id
        return None

    def analytic_line_cost(self, consolidation_data_vals_cost):
        analytic_line_cost_projet = self.env["account.analytic.line"]

        all_projects_cost = self.env["project.project"].search(
            ["|", ("active", "=", False), ("active", "=", True)]
        )
        projects_by_id = {p.id: p for p in all_projects_cost}

        vals_list = []
        for analytic_line in consolidation_data_vals_cost:
            company_ids = analytic_line.get("company", [])
            vals_list.append({
                "name": analytic_line.get("description"),
                "account_id": self.get_account_id(analytic_line, projects_by_id),
                "bussines_group_id": analytic_line.get("business_group"),
                "sector_account_id": analytic_line.get("sector_account_group"),
                "managment_account_id": analytic_line.get("managment_account_group"),
                "amount": analytic_line.get("amount"),
                "date": self.consolidation_period.date_from,
                "company_id": [(6, 0, company_ids)],
                "currency_id": REPORT_CURRENCY_ID,
                "consolidation_line": True,
                # se saca del dict: despues alimenta account.consolidation.data,
                # que no tiene este campo
                "is_indirect_expense": analytic_line.pop("is_indirect_expense", False),
            })

        created_lines = analytic_line_cost_projet.create(vals_list)
        for analytic_line, created_line in zip(consolidation_data_vals_cost, created_lines):
            analytic_line["daughter_account"] = created_line.id

        return consolidation_data_vals_cost

    def _build_convert_amount_cache(self):
        move_fields = self.env['account.move']._fields
        has_l10n_ar_rate = (
            'l10n_ar_currency_rate' in move_fields
            and getattr(move_fields['l10n_ar_currency_rate'], 'store', False)
        )
        has_computed_rate = (
            'computed_currency_rate' in move_fields
            and getattr(move_fields['computed_currency_rate'], 'store', False)
        )
        l10n_col = "COALESCE(am.l10n_ar_currency_rate, 0)" if has_l10n_ar_rate else "0"
        computed_col = "COALESCE(am.computed_currency_rate, 0)" if has_computed_rate else "0"
        self.env.cr.execute(f"""
            SELECT
                aal.id,
                am.company_id        AS move_company_id,
                am.currency_id       AS move_currency_id,
                comp.currency_id     AS company_currency_id,
                {l10n_col}           AS l10n_ar_rate,
                {computed_col}       AS computed_rate,
                am2.company_id       AS src_move_company_id
            FROM account_analytic_line aal
            LEFT JOIN account_move_line aml  ON aml.id  = aal.move_id
            LEFT JOIN account_move am        ON am.id   = aml.move_id
            LEFT JOIN res_company comp       ON comp.id = am.company_id
            LEFT JOIN account_analytic_line aal2 ON aal2.id = aal.source_analytic_line_id
            LEFT JOIN account_move_line aml2 ON aml2.id = aal2.move_id
            LEFT JOIN account_move am2       ON am2.id  = aml2.move_id
            WHERE aal.date >= %s AND aal.date <= %s
        """, (self.consolidation_period.date_from, self.consolidation_period.date_to))
        move_data = {row['id']: row for row in self.env.cr.dictfetchall()}
        comp_to_period = {
            cp.company_id.id: cp
            for cp in self.consolidation_period.consolidation_companies
        }
        return move_data, comp_to_period

    def _convert_amount(self, analytic_line, move_data, comp_to_period):
        data = move_data.get(analytic_line.id, {})
        move_company_id = data.get('move_company_id')
        move_currency_id = data.get('move_currency_id')
        company_currency_id = data.get('company_currency_id')
        l10n_ar_rate = data.get('l10n_ar_rate') or 0
        computed_rate = data.get('computed_rate') or 0
        src_move_company_id = data.get('src_move_company_id')

        consolidation_period = comp_to_period.get(move_company_id) if move_company_id else None
        is_historical = False
        rate = 1

        if consolidation_period:
            if not consolidation_period.historical_rate:
                rate = consolidation_period.rate
            elif move_currency_id and move_currency_id != company_currency_id:
                is_historical = True
                rate = l10n_ar_rate or computed_rate or 1
            else:
                is_historical = True
                rate = 1
        elif src_move_company_id:
            consolidation_period = comp_to_period.get(src_move_company_id)
            if consolidation_period:
                if not consolidation_period.historical_rate:
                    rate = consolidation_period.rate
                else:
                    rate = 1

        return analytic_line.amount * rate if not is_historical else analytic_line.amount

    def create_missing_analytic_lines(self):
        # Lineas analiticas PGK y demas excepto Calyx
        missing_analytic_lines_pgk = self.env["account.move.line"].search([
            ("date", ">=", self.consolidation_period.date_from),
            ("date", "<=", self.consolidation_period.date_to),
            "|",
            ("account_id.code", "=", EXCHANGE_DIFF_CODE),
            ("account_id.code", "=", EXCHANGE_DIFF_CODE_ALT),
            ("analytic_line_ids", "=", False),
            ("account_id.company_id", "!=", CALYX_COMPANY_ID),
        ])
        # Lista para almacenar los diccionarios de valores para las nuevas líneas analíticas
        vals_list_pgk = []

        # Crear un diccionario de valores para cada línea de movimiento contable
        for line in missing_analytic_lines_pgk:
            vals = {
                # Usar el nombre de la línea de movimiento contable o '/' si está vacío
                'name': line.name or '/',
                'date': line.date,  # Usar la fecha de la línea de movimiento contable
                'account_id': EXCHANGE_DIFF_ACCOUNT_PGK_ID,
                'move_id': line.id,  # Usar el ID del movimiento contable
                'amount': line.credit - line.debit,
                'company_id': line.move_id.company_id.id,
                'currency_id': line.move_id.currency_id.id,
                'general_account_id': line.account_id.id,
                "consolidation_line": True
            }
            vals_list_pgk.append(vals)

        # Crear las nuevas líneas analíticas
        self.env["account.analytic.line"].create(vals_list_pgk)

        # Lineas analiticas Calyx
        missing_analytic_lines_calyx = self.env["account.move.line"].search([
            ("date", ">=", self.consolidation_period.date_from),
            ("date", "<=", self.consolidation_period.date_to),
            ("account_id.code", "=", EXCHANGE_DIFF_CODE),
            ("analytic_line_ids", "=", False),
            ("account_id.company_id", "=", CALYX_COMPANY_ID),
        ])
        # Lista para almacenar los diccionarios de valores para las nuevas líneas analíticas
        vals_list_calyx = []

        # Crear un diccionario de valores para cada línea de movimiento contable
        for line in missing_analytic_lines_calyx:
            vals = {
                # Usar el nombre de la línea de movimiento contable o '/' si está vacío
                'name': line.name or '/',
                'date': line.date,  # Usar la fecha de la línea de movimiento contable
                'account_id': EXCHANGE_DIFF_ACCOUNT_CALYX_ID,
                'move_id': line.id,  # Usar el ID del movimiento contable
                'amount': line.amount_currency,
                'company_id': line.move_id.company_id.id,
                'currency_id': line.move_id.currency_id.id,
                'general_account_id': line.account_id.id,
                "consolidation_line": True,
            }
            vals_list_calyx.append(vals)

        # Crear las nuevas líneas analíticas
        self.env["account.analytic.line"].create(vals_list_calyx)

    def last_consolidation_report_view(self):
        return self._get_consolidation_data_action()
