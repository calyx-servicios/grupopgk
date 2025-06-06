from odoo import api, fields, models, _
import base64, xlsxwriter
from io import BytesIO
from odoo.exceptions import UserError


class AccountConsolidationReport(models.Model):
    _name = "account.consolidation.report"
    _description = "Export consolidation report"

    name = fields.Char(string="Name")
    period = fields.Char(compute="_compute_period", string="Period")
    consolidation_period = fields.Many2one(
        "account.consolidation.period", string="Select a period"
    )
    export_consolidation_data = fields.Text("File content")
    export_consolidation_file = fields.Binary(
        "Download File", compute="_compute_files", readonly=True
    )
    export_consolidation_filename = fields.Char(
        "File consolidation", compute="_compute_files", readonly=True
    )

    @api.depends("consolidation_period")
    def _compute_period(self):
        for record in self:
            if record.consolidation_period:
                record.period = record.consolidation_period.period
            else:
                record.period = "/"

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
                )
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

            daughter_account.append(
                {
                    "account_id": analytic_line.general_account_id.code,
                    "company": company,
                    "currency_origin": currency_origin if currency_origin else "",
                    "currency": new_currency if new_currency else "",
                    "rate": rate,
                    "description": analytic_line.name or "",
                    "amount": (
                        analytic_line.amount * rate
                        if not consolidation_period
                        or not consolidation_period.historical_rate
                        else analytic_line.amount
                    ),
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

    
    def generate_consolidation_report_view(self):
        # Elimino si es que existen lineas analiticas de redistribucion de gastos indirectos creadas anteriormente (en caso que el informe se pide mas de una vez) y lineas de account consolidation data por el mismo motivo
        self.delete_entries()

        # Creacion de lineas analiticas que surgen de asientos contables automaticos y no se crearon
        self.create_missing_analytic_lines()

        # Calculo el monto total de las lineas de 'Gastos Indirectos'
        total_amount_cost = self.calculate_total_amount_cost()

        # Crear diccionario facturacion por proyecto
        total_sales_for_project = self.sales_by_project()

        # Calculo el porcentaje de facturacion de cada projecto
        percentage_for_project = self.calculate_percentage(total_sales_for_project)

        analytic_lines = self.env["account.analytic.line"].search(
            [
                ("date", ">=", self.consolidation_period.date_from),
                ("date", "<=", self.consolidation_period.date_to),
            ]
        )

        consolidation_data_vals = []
        for analytic_line in analytic_lines:
            analytic_line.update_currency_id()

            current_account = analytic_line.account_id
            sector_account = None

            while current_account:
                if current_account.is_sector_group:
                    sector_account = current_account.id
                    break
                current_account = current_account.parent_id

            if sector_account:
                analytic_line.sector_account_id = sector_account

            consolidation_period = (
                self.consolidation_period.consolidation_companies.filtered(
                    lambda x: x.company_id == analytic_line.move_id.company_id
                )
            )
            currency_origin = analytic_line.currency_id.id
            new_currency = (
                consolidation_period.new_currency.id
                if consolidation_period
                else analytic_line.currency_id.id
            )
            rate = (
                consolidation_period.rate
                if consolidation_period and not consolidation_period.historical_rate
                else 1
            )
            # Busca el proyecto para cada linea analitica y permitir la agrupacion
            project_ids = self.env["project.project"].search(
                [
                    "|",
                    ("active", "=", False),
                    ("active", "=", True),
                    ("analytic_account_id", "=", analytic_line.account_id.id),
                ]
            )
            project_id = False if not project_ids else project_ids[0].id

            consolidation_data_vals.append(
                {
                    "name": self.name,
                    "main_group": analytic_line.parent_prin_group_id.id,
                    "project_id": project_id,
                    "business_group": analytic_line.bussines_group_id.id,
                    "sector_account_group": analytic_line.sector_account_id.id,
                    "managment_account_group": analytic_line.managment_account_id.id,
                    "company": analytic_line.company_id.ids,
                    "daughter_account": analytic_line.id,
                    "description": analytic_line.name or "",
                    "account_id": analytic_line.general_account_id.code,
                    "currency_origin": currency_origin if currency_origin else "",
                    "currency": new_currency if new_currency else "",
                    "rate": rate,
                    "amount": analytic_line.amount * rate
                }
            )

        # Aplico el porcentaje de la facturacion a los gastos indirectos y creo las lineas
        consolidation_data_vals_cost = self.cost_to_project(
            percentage_for_project, total_amount_cost
        )
        account_analytic_line_cost = self.analytic_line_cost(
            consolidation_data_vals_cost
        )
        consolidation_data = self.env["account.consolidation.data"]
        consolidation_data.create(consolidation_data_vals)
        consolidation_data.create(consolidation_data_vals_cost)
        

        view_id_tree = self.env.ref("consolidation_report.view_consolidation_data_tree")
        return {
            "name": "Consolidation Report",
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "tree,form",
            "res_model": "account.consolidation.data",
            "views": [(view_id_tree.id, "tree")],
            "context": {
                "tree_view_ref": "view_consolidation_data_tree",
                "group_by_no_leaf": 1,
                #'group_by': ['main_group', 'business_group',
                #            'sector_account_group',
                #            'managment_account_group','company',
                #            'currency', 'daughter_account']
            },
            "target": "current",
        }

    def delete_entries(self):
        self.env["account.consolidation.data"].search([]).unlink()

        lines_to_delete = self.env["account.analytic.line"].search(
            [
                ("consolidation_line", "=", True)
            ]
        )

        lines_to_delete.unlink()

    def sales_by_project(self):
        # Filtra las líneas analíticas para Calyx
        analytic_lines_calyx = self.env["account.analytic.line"].search(
            [
                ("date", ">=", self.consolidation_period.date_from),
                ("date", "<=", self.consolidation_period.date_to),
                ("general_account_id.code", "like", "4.1%"),
                ("general_account_id.user_type_id.name", "=", "Ingreso"),
                ("bussines_group_id.id", "=", 22) # ID Negocio Consolidacion / Tecnologia
            ]
        )

        # Filtra las líneas analíticas para las demas empresas
        analytic_lines_otros = self.env["account.analytic.line"].search(
            [
                ("date", ">=", self.consolidation_period.date_from),
                ("date", "<=", self.consolidation_period.date_to),
                ("general_account_id.code", "like", "4.1%"),
                ("general_account_id.user_type_id.name", "=", "Ingreso"),
                ("bussines_group_id.id", "=", 21) # ID Negocio Consolidacion / Servicios Profesionales
            ]
        )

        # Diccionario para acumular los montos por proyecto
        project_sales_calyx = {}
        project_sales_otros = {}
        total_sales_calyx = 0.0
        total_sales_otros = 0.0

        all_projects = self.env["project.project"].search(
            ["|", ("active", "=", False), ("active", "=", True)]
        )

        # Procesa las líneas analíticas para Calyx
        for line in analytic_lines_calyx:
            line.update_currency_id()
            project = all_projects.filtered(
                lambda p: p.analytic_account_id.id == line.account_id.id
            )
            amount = self._convert_amount(line)
            total_sales_calyx += amount
            if project and amount != 0.0:
                if project.id in project_sales_calyx:
                    project_sales_calyx[project.id] += amount
                else:
                    project_sales_calyx[project.id] = amount

        # Procesa las líneas analíticas para otras empresas
        for line in analytic_lines_otros:
            line.update_currency_id()
            project = all_projects.filtered(
                lambda p: p.analytic_account_id.id == line.account_id.id
            )
            amount = self._convert_amount(line)
            total_sales_otros += amount
            if project and amount != 0.0:
                if project.id in project_sales_otros:
                    project_sales_otros[project.id] += amount
                else:
                    project_sales_otros[project.id] = amount

        # Incluye los totales en los diccionarios
        project_sales_calyx["total_sales_calyx"] = round(total_sales_calyx, 2)
        project_sales_otros["total_sales_otros"] = round(total_sales_otros, 2)

        # Combina ambos diccionarios en uno solo
        project_sales = {
            "calyx": project_sales_calyx,
            "otros": project_sales_otros
        }

        return project_sales


    def calculate_total_amount_cost(self):
        # Filtra las líneas analíticas para Calyx
        analytic_lines_calyx = self.env["account.analytic.line"].search(
            [
                ("date", ">=", self.consolidation_period.date_from),
                ("date", "<=", self.consolidation_period.date_to),
                ("sector_account_id.id", "=", 5331) # ID Sector Gastos Indirectos (Calyx)
            ]
        )
    
        # Filtra las líneas analíticas para otras empresas
        analytic_lines_otros = self.env["account.analytic.line"].search(
            [
                ("date", ">=", self.consolidation_period.date_from),
                ("date", "<=", self.consolidation_period.date_to),
                ("sector_account_id.id", "=", 4114), # ID Sector Gastos Indirectos otros
                ("sector_account_id.id", "!=", 5331)  # Asegura que no incluye Calyx
            ]
        )
    
        # Inicializa los totales
        total_amount_cost_calyx = 0.0
        total_amount_cost_otros = 0.0
    
        # Procesa las líneas analíticas para Calyx
        for analytic_line in analytic_lines_calyx:
            amount = self._convert_amount(analytic_line)
            total_amount_cost_calyx += amount
            # Crear una nueva línea analítica con los campos especificados
            analytic_line.copy(default={
                "name": f"{analytic_line.name} - Linea consolidacion",
                "amount": -analytic_line.amount,
                "debit": -analytic_line.debit,
                "credit": -analytic_line.credit,
                "date": analytic_line.date,
                "general_account_id": False,
                "move_id": analytic_line.move_id.id,
                "consolidation_line": True,
                "currency_id": analytic_line.currency_id.id,
            })
    
        # Procesa las líneas analíticas para otras empresas
        for analytic_line in analytic_lines_otros:
            amount = self._convert_amount(analytic_line)
            total_amount_cost_otros += amount
            # Crear una nueva línea analítica con los campos especificados
            analytic_line.copy(default={
                "name": f"{analytic_line.name} - Linea consolidacion",
                "amount": -analytic_line.amount,
                "debit": -analytic_line.debit,
                "credit": -analytic_line.credit,
                "date": analytic_line.date,
                "general_account_id": False,
                "move_id": analytic_line.move_id.id,
                "consolidation_line": True,
                "currency_id": analytic_line.currency_id.id,
                "move_company_id": analytic_line.move_company_id.id,
            })
    
        # Redondea los totales a dos decimales
        total_amount_cost_calyx = round(total_amount_cost_calyx, 2)
        total_amount_cost_otros = round(total_amount_cost_otros, 2)
    
        # Devuelve un diccionario con los montos totales
        return {
            "total_amount_cost_calyx": total_amount_cost_calyx,
            "total_amount_cost_otros": total_amount_cost_otros
        }


    def calculate_percentage(self, sales_dict):
        percentages = {
            "calyx": [],
            "otros": []
        }

        # Calcular los porcentajes para Calyx
        total_sales_calyx = round(sales_dict["calyx"]["total_sales_calyx"], 2)
        for project, sales in sales_dict["calyx"].items():
            if project != "total_sales_calyx":  # Ignorar la clave 'total_sales_calyx'
                sales_rounded = round(sales, 2)
                percentage = round((sales_rounded / total_sales_calyx) * 100, 2)
                if percentage != 0.00:
                    percentages["calyx"].append(
                        {
                            "project_id": project,
                            "sales": sales_rounded,
                            "percentage": percentage,
                            "total_sales": total_sales_calyx
                        }
                    )

        # Calcular los porcentajes para Otros
        total_sales_otros = round(sales_dict["otros"]["total_sales_otros"], 2)
        for project, sales in sales_dict["otros"].items():
            if project != "total_sales_otros":  # Ignorar la clave 'total_sales_otros'
                sales_rounded = round(sales, 2)
                percentage = round((sales_rounded / total_sales_otros) * 100, 2)
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


    
    def get_management_id(self, analytic_line):
        current_account = analytic_line.account_id

        while current_account:
            if current_account.is_sector_group:
                return current_account.id
            current_account = current_account.parent_id

        return None

    def get_sector_id(self, project):
        current_account = project.analytic_account_id

        while current_account:
            if current_account.is_sector_group:
                return current_account.id
            current_account = current_account.parent_id

        return None

    def cost_to_project(self, percentage_for_project, total_amount_cost):
        all_projects = self.env["project.project"].search(
            ["|", ("active", "=", False), ("active", "=", True)]
        )
        consolidation_data_vals_cost = []

        # Procesar los datos para Calyx
        total_amount_cost_calyx = total_amount_cost['total_amount_cost_calyx']
        for project_data in percentage_for_project['calyx']:
            project_id = project_data["project_id"]
            percentage = project_data["percentage"]
            sales_project = project_data["sales"]
            total_sales = project_data["total_sales"]

            # Encuentra el proyecto usando el project_id
            project = all_projects.filtered(lambda p: p.id == project_id)

            if project.exists() and project.analytic_account_id:
                # Calcula el monto a asignar basado en el porcentaje y el costo total
                amount = (percentage / 100.0) * total_amount_cost_calyx

                # Crea un nuevo elemento consolidation data para ser visto en el informe
                consolidation_data_vals_cost.append(
                    {
                        "name": self.name,
                        "main_group": project.analytic_account_id.group_id.parent_prin_group.id or "",
                        "business_group": 22,
                        "sector_account_group": self.get_sector_id(project) or "", 
                        "managment_account_group": project.analytic_account_id.parent_id.id or "",
                        "project_id": project_id,
                        "company": project.company_id.ids or "",
                        "description": f"Porcentaje = (Facturacion proyecto: {sales_project} *100 / Total facturacion: {total_sales}) Total GI = {total_amount_cost_calyx}",
                        "amount": -abs(amount),
                        "currency": 19,
                        "rate": 1 
                    }
                )

        # Procesar los datos para Otros
        total_amount_cost_otros = total_amount_cost['total_amount_cost_otros']
        for project_data in percentage_for_project['otros']:
            project_id = project_data["project_id"]
            percentage = project_data["percentage"]
            sales_project = project_data["sales"]
            total_sales = project_data["total_sales"]

            # Encuentra el proyecto usando el project_id
            project = all_projects.filtered(lambda p: p.id == project_id)

            if project.exists() and project.analytic_account_id:
                # Calcula el monto a asignar basado en el porcentaje y el costo total
                amount = (percentage / 100.0) * total_amount_cost_otros

                # Crea un nuevo elemento consolidation data para ser visto en el informe
                consolidation_data_vals_cost.append(
                    {
                        "name": self.name,
                        "main_group": project.analytic_account_id.group_id.parent_prin_group.id or "",
                        "business_group": project.analytic_account_id.group_id.parent_id.id or "",
                        "sector_account_group": self.get_sector_id(project) or "",
                        "managment_account_group": project.analytic_account_id.parent_id.id or "",
                        "project_id": project_id,
                        "company": project.company_id.ids or "",
                        "description": f"Porcentaje = (Facturacion proyecto: {sales_project} *100 / Total facturacion: {total_sales}) Total GI = {total_amount_cost_otros}",
                        "amount": -abs(amount),
                        "currency": 19,
                        "rate": 1 
                    }
                )

        return consolidation_data_vals_cost


    def get_account_id(self, analytic_line):
        project = analytic_line.get("project_id")
        all_projects = self.env["project.project"].search(
            ["|", ("active", "=", False), ("active", "=", True)]
        )
        for proj in all_projects:
            if proj.id == project:
                return proj.analytic_account_id.id

        return None

    def analytic_line_cost(self, consolidation_data_vals_cost):
        analytic_line_cost_projet = self.env["account.analytic.line"]

        for analytic_line in consolidation_data_vals_cost:
            company = self.env["res.company"].search([('id','=', analytic_line.get("company")[0])])
            company_ids = analytic_line.get("company",[])

            vals = {
                "name": analytic_line.get("description"),
                "account_id": self.get_account_id(analytic_line),
                "bussines_group_id": analytic_line.get("business_group"),
                "sector_account_id": analytic_line.get("sector_account_group"),
                "managment_account_id": analytic_line.get("managment_account_group"),
                "amount": analytic_line.get("amount"),
                "date": self.consolidation_period.date_from,
                "company_id": [(6, 0, company_ids)],
                "currency_id": 19,
                "consolidation_line": True,
            }

            # Crea una nueva línea analítica con los valores proporcionados
            created_line = analytic_line_cost_projet.create(vals)

            # Agrega el ID de la línea analítica creada al diccionario original
            analytic_line["daughter_account"] = created_line.id

        return consolidation_data_vals_cost

    def _convert_amount(self, analytic_line):
        consolidation_period = (
                self.consolidation_period.consolidation_companies.filtered(
                    lambda x: x.company_id == analytic_line.move_id.company_id
                )
            )

        if consolidation_period and not consolidation_period.historical_rate:
            rate = consolidation_period.rate
        
        else:
            rate = 1
        
        total = analytic_line.amount * rate
        
        return total

    def create_missing_analytic_lines(self):
        # Lineas analiticas PGK y demas excepto Calyx
        missing_analytic_lines_pgk = self.env["account.move.line"].search(
        [
            ("date", ">=", self.consolidation_period.date_from),
            ("date", "<=", self.consolidation_period.date_to),
            "|",
            ("account_id.code", "=", "4.2.1.01.020"),
            ("account_id.code", "=", "5.8.1.01.016"),
            ("analytic_line_ids", "=", False),
            ("account_id.company_id.id", "!=", 3) # Excluyo Calyx Servicios
        ]
        )
        # Lista para almacenar los diccionarios de valores para las nuevas líneas analíticas
        vals_list_pgk = []

        # Crear un diccionario de valores para cada línea de movimiento contable
        for line in missing_analytic_lines_pgk:
            vals = {
                'name': line.name or '/',  # Usar el nombre de la línea de movimiento contable o '/' si está vacío
                'date': line.date,  # Usar la fecha de la línea de movimiento contable
                'account_id': 812,  # Ingresos Indirectos (PGK) / Diferencia de Cambio Comercial (PGK)
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
        missing_analytic_lines_calyx = self.env["account.move.line"].search(
        [
            ("date", ">=", self.consolidation_period.date_from),
            ("date", "<=", self.consolidation_period.date_to),
            ("account_id.code", "=", "4.2.1.01.020"),
            ("analytic_line_ids", "=", False),
            ("account_id.company_id.id", "=", 3) # Solo Calyx Servicios
        ]
        )
        # Lista para almacenar los diccionarios de valores para las nuevas líneas analíticas
        vals_list_calyx = []

        # Crear un diccionario de valores para cada línea de movimiento contable
        for line in missing_analytic_lines_calyx:
            vals = {
                'name': line.name or '/',  # Usar el nombre de la línea de movimiento contable o '/' si está vacío
                'date': line.date,  # Usar la fecha de la línea de movimiento contable
                'account_id': 5487,  # Ingresos Indirectos (Calyx) / Diferencia de Cambio Comercial (Calyx)
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
