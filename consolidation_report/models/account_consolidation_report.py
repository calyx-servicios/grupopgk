from odoo import api, fields, models, _
import base64, xlsxwriter
from io import BytesIO
from odoo.exceptions import UserError

class AccountConsolidationReport(models.Model):
    _name = 'account.consolidation.report'
    _description = 'Export consolidation report'


    name = fields.Char(string='Name')
    period = fields.Char(compute="_compute_period", string='Period')
    consolidation_period = fields.Many2one('account.consolidation.period', string='Select a period')
    export_consolidation_data = fields.Text('File content')
    export_consolidation_file = fields.Binary('Download File', compute="_compute_files", readonly=True)
    export_consolidation_filename = fields.Char('File consolidation', compute="_compute_files", readonly=True)
    
    @api.depends('consolidation_period')
    def _compute_period(self):
        for record in self:
            if record.consolidation_period:
                record.period = record.consolidation_period.period
            else:
                record.period = '/'

    @api.onchange('consolidation_period')
    def _onchange_consolidation_period(self):
        for record in self:
            if record.consolidation_period:
                record.name =  _('Consolidation Report: ') + str(record.consolidation_period.date_from) +  ' ' + str(record.consolidation_period.date_to)
            else:
                record.name = '/'

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
                worksheet = workbook.add_worksheet(_('Consolidated Report'))

                # Add headers
                bold = workbook.add_format({
                'bold': True,
                'align': 'center',
                })
                merge_format = workbook.add_format(
                {
                    "bold": 1,
                    "border": 1,
                    "align": "left",
                    "valign": "vleft",
                    "fg_color": "gray",
                })
                total_format = workbook.add_format(
                {
                    "bold": 1,
                    "border": 1,
                    "align": "left",
                    "valign": "vleft",
                    "fg_color": "gray",
                    "num_format": "$#,##0.00",
                })
                currency_format = workbook.add_format({'num_format': '$#,##0.00'})
                headers = [_('Description'), _('Account Name'), _('Companies'), _('Target Currency'), _('Currency'), _('Rate'), _('Amount'), _('Total')]

                worksheet.set_column('A:A', 1)
                worksheet.set_column('A:A', 50)
                worksheet.set_column('B:B', 1)
                worksheet.set_column('B:B', 30)
                worksheet.set_column('C:C', 1)
                worksheet.set_column('C:C', 18)
                worksheet.set_column('D:D', None, None, {'hidden': True})
                worksheet.set_column('E:E', 1)
                worksheet.set_column('E:E', 18)
                worksheet.set_column('F:F', 1)
                worksheet.set_column('F:F', 18)
                worksheet.set_column('G:G', 1)
                worksheet.set_column('G:G', 18)
                worksheet.set_column('H:H', 1)
                worksheet.set_column('H:H', 18)

                for i, header in enumerate(headers):
                    worksheet.write(0, i, header, bold)

                row = 1
                for grandfather_group, mother_groups in data.items():
                    for mother_group, grandmother_accounts in mother_groups.items():
                        for grandmother_account, mother_accounts in grandmother_accounts.items():
                            for mother_account, companies in mother_accounts.items():
                                for company, daughter_accounts in companies.items():
                                    for daughter_account, vals in daughter_accounts.items():
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group, merge_format)
                                        worksheet.write(row, 7, totals[grandfather_group]['total'], total_format)
                                        row += 1
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group + ' / ' + mother_group, merge_format)
                                        worksheet.write(row, 7, totals[grandfather_group][mother_group]['total'], total_format)
                                        row += 1
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group + ' / ' + mother_group + ' / ' + grandmother_account, merge_format)
                                        worksheet.write(row, 7, totals[grandfather_group][mother_group][grandmother_account]['total'], total_format)
                                        row += 1
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group + ' / ' + mother_group + ' / ' + grandmother_account + ' / ' + mother_account, merge_format)
                                        worksheet.write(row, 7, totals[grandfather_group][mother_group][grandmother_account][mother_account]['total'], total_format)
                                        row += 1
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group + ' / ' + mother_group + ' / ' + grandmother_account + ' / ' + mother_account + '/' + company, merge_format)
                                        worksheet.write(row, 7, totals[grandfather_group][mother_group][grandmother_account][mother_account][company]['total'], total_format)
                                        row += 1
                                        worksheet.merge_range(row, 0, row, 6, grandfather_group + ' / ' + mother_group + ' / ' + grandmother_account + ' / ' + mother_account + '/' + company + '/' + daughter_account, merge_format)
                                        row += 1
                                        for val in vals:
                                            worksheet.write(row, 0, val['description'])
                                            worksheet.write(row, 1, val['account_id'])
                                            worksheet.write(row, 2, val['company'])
                                            worksheet.write(row, 3, val['currency_origin'])
                                            worksheet.write(row, 4, val['currency'])
                                            worksheet.write(row, 5, val['rate'])
                                            worksheet.write(row, 6, val['amount'], currency_format)
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

        analytic_lines = self.env['account.analytic.line'].search([
            ('date', '>=', self.consolidation_period.date_from),
            ('date', '<=', self.consolidation_period.date_to)
        ])

        for analytic_line in analytic_lines:
            analytic_line.update_currency_id()

            group_key = analytic_line.parent_prin_group_id.name or 'Undefined'
            mother_key = analytic_line.bussines_group_id.name or 'Undefined'
            grandmother_key = analytic_line.sector_account_id.name or 'Undefined'
            mother_account_key = analytic_line.managment_account_id.name or 'Undefined'
            daughter_account_key = analytic_line.name or 'Undefined'
            company = analytic_line.move_company_id.name or 'Undefined'

            consolidation_period = self.consolidation_period.consolidation_companies.filtered(lambda x: x.company_id == analytic_line.move_id.company_id)
            currency_origin = consolidation_period.currency_id.symbol if consolidation_period else analytic_line.currency_id.symbol
            new_currency = consolidation_period.new_currency.symbol if consolidation_period else analytic_line.currency_id.symbol
            rate = consolidation_period.rate if consolidation_period and not consolidation_period.historical_rate else 1

            daughter_account = data.setdefault(group_key, {}).setdefault(mother_key, {}).setdefault(grandmother_key, {}).setdefault(mother_account_key, {}).setdefault(company, {}).setdefault(daughter_account_key, [])

            daughter_account.append({
                'account_id': analytic_line.general_account_id.code,
                'company': company,
                'currency_origin': currency_origin if currency_origin else '',
                'currency': new_currency if new_currency else '',
                'rate': rate,
                'description': analytic_line.name or '',
                'amount': analytic_line.amount * rate if not consolidation_period or not consolidation_period.historical_rate else analytic_line.amount,
            })

        return data

    @api.depends('export_consolidation_data', 'period')
    def _compute_files(self):
        for record in self:
            filename = _('Consolidation-%s.xls') % (record.period)
            record.export_consolidation_filename = filename
            if record.export_consolidation_data:
                record.export_consolidation_file = record.export_consolidation_data
            else:
                record.export_consolidation_file = False

    def get_totals(self, data):
        totals = {}

        for group_key, group_value in data.items():
            group_total = 0
            group_dict = {'total': group_total}

            for mother_key, mother_value in group_value.items():
                mother_dict = self.calculate_mother_totals(mother_value)
                group_total += mother_dict['total']
                group_dict[mother_key] = mother_dict

            group_dict['total'] = group_total
            totals[group_key] = group_dict

        return totals

    def calculate_mother_totals(self, mother_value):
        mother_total = 0
        mother_dict = {'total': mother_total}

        for grandmother_key, grandmother_value in mother_value.items():
            grandmother_dict = self.calculate_grandmother_totals(grandmother_value)
            mother_total += grandmother_dict['total']
            mother_dict[grandmother_key] = grandmother_dict

        mother_dict['total'] = mother_total
        return mother_dict

    def calculate_grandmother_totals(self, grandmother_value):
        grandmother_total = 0
        grandmother_dict = {'total': grandmother_total}

        for mother_account_key, mother_account_value in grandmother_value.items():
            mother_account_dict = self.calculate_mother_account_totals(mother_account_value)
            grandmother_total += mother_account_dict['total']
            grandmother_dict[mother_account_key] = mother_account_dict

        grandmother_dict['total'] = grandmother_total
        return grandmother_dict

    def calculate_mother_account_totals(self, mother_account_value):
        mother_account_total = 0
        mother_account_dict = {'total': mother_account_total}

        for daughter_account_key, daughter_account_value in mother_account_value.items():
            daughter_account_dict = self.calculate_daughter_account_totals(daughter_account_value)
            mother_account_total += daughter_account_dict['total']
            mother_account_dict[daughter_account_key] = daughter_account_dict

        mother_account_dict['total'] = mother_account_total
        return mother_account_dict

    def calculate_daughter_account_totals(self, daughter_account_value):
        daughter_account_total = 0
        daughter_account_dict = {'total': daughter_account_total}

        for company_key, company_value in daughter_account_value.items():
            company_total = sum(entry['amount'] for entry in company_value)
            daughter_account_total += company_total
            company_dict = {'entry': {'total': company_total}}
            daughter_account_dict[company_key] = company_dict

        daughter_account_dict['total'] = daughter_account_total
        return daughter_account_dict

    def generate_consolidation_report_view(self):
        # Crear diccionario facturacion por proyecto
        total_sales_for_project = self.sales_by_project()

        indirect_expense_lines = self.analytic_line_indirect_expense()

        # Calculo el monto total de las lineas de 'Gastos Indirectos'
        total_amount_cost = self.calculate_total_amount_cost(indirect_expense_lines)

        # Calculo el porcentaje de facturacion de cada projecto
        percentage_for_project = self.calculate_percentage(total_sales_for_project)

        # Aplico el porcentaje de la facturacion a los gastos indirectos y creo las lineas
        account_analytic_line_cost_for_project = self.cost_to_project(percentage_for_project, total_amount_cost)

        self.delete_entries()
        analytic_lines = self.env['account.analytic.line'].search([
            ('date', '>=', self.consolidation_period.date_from),
            ('date', '<=', self.consolidation_period.date_to)
        ])

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
            
            if analytic_line.sector_account_id.name == 'Gastos Indirectos':
                continue
              
            consolidation_period = self.consolidation_period.consolidation_companies.filtered(lambda x: x.company_id == analytic_line.move_id.company_id)
            currency_origin = analytic_line.currency_id.id
            new_currency = consolidation_period.new_currency.id if consolidation_period else analytic_line.currency_id.id
            rate = consolidation_period.rate if consolidation_period and not consolidation_period.historical_rate else 1
            # Busca el proyecto para cada linea analitica y permitir la agrupacion
            project_ids = self.env['project.project'].search([('analytic_account_id', '=', analytic_line.account_id.id)])
            project_id = False if not project_ids else project_ids[0].id

            consolidation_data_vals.append({
                'name': self.name,
                'main_group': analytic_line.parent_prin_group_id.id,
                'project_id': project_id,
                'business_group': analytic_line.bussines_group_id.id,
                'sector_account_group': analytic_line.sector_account_id.id,
                'managment_account_group': analytic_line.managment_account_id.id,
                'company': analytic_line.move_company_id.name or analytic_line.company_id.name,
                'daughter_account': analytic_line.id,
                'description': analytic_line.name or '',
                'account_id': analytic_line.general_account_id.code,
                'currency_origin': currency_origin if currency_origin else '',
                'currency': new_currency if new_currency else '',
                'rate': rate,
                'amount': analytic_line.amount * rate if not consolidation_period or not consolidation_period.historical_rate else analytic_line.amount,
            })
        
        consolidation_data = self.env['account.consolidation.data']
        consolidation_data.create(consolidation_data_vals)

        view_id_tree = self.env.ref('consolidation_report.view_consolidation_data_tree')
        return {
            'name': 'Consolidation Report',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.consolidation.data',
            'views': [(view_id_tree.id, 'tree')],
            'context': {'tree_view_ref': 'view_consolidation_data_tree', 'group_by_no_leaf': 1,
                        'group_by': ['main_group', 'business_group', 'sector_account_group', 'managment_account_group','company',
                                    'currency', 'daughter_account']},
            'target': 'current',
        }

    def delete_entries(self):
        self.env['account.consolidation.data'] \
            .search([]).unlink()

    def sales_by_project(self):
        analytic_lines = self.env['account.analytic.line'].search([
            ('date', '>=', self.consolidation_period.date_from),
            ('date', '<=', self.consolidation_period.date_to),
            ('general_account_id.code', 'like', '4.1%'),  # Filtra los códigos que comienzan con '4.1'
            ('general_account_id.user_type_id.name', '=', 'Ingreso'),  # Filtra por tipo de usuario 'Ingreso'
            ('parent_prin_group_id.id', 'not in', ['31','32','36','44']), # Filtro para no tener en cuenta los grupos Costos Indirectos, Gastos Indirectos, Costos Directos y Tablero 
        ])

        # Diccionario para acumular los montos por proyecto
        project_sales = {}
        missing_lines = {}

        # Itera sobre cada línea analítica encontrada
        for line in analytic_lines:
            # Obtén el proyecto asociado a la cuenta analitica de la linea
            project = self.env['project.project'].search([
                ('analytic_account_id', '=', line.account_id.id)
            ])
            # Verifico que el monto de la linea esta en $ y sino la convierto
            if line.currency_id:
                if line.currency_id.id != 19 and line.currency_id.name != 'PES':
                    amount = line.currency_id.rate_ids[0]['inverse_company_rate'] * line.amount
                else:
                    amount = line.amount
            if project:
            # Verifica si el proyecto ya está en el diccionario
                if project.id in project_sales:
                    # Suma al monto existente
                    project_sales[project.id] += amount
                else:
                    # Crea una nueva entrada en el diccionario con el monto inicial
                    project_sales[project.id] = amount
            else:
                # Almacena el account_id.name en la lista de proyectos faltantes
                missing_lines[line.id] = line.name

        # Si hay proyectos faltantes, levanta una excepción y devuelve la lista
        if missing_lines:
            error_message = "Los siguientes lineas analíticas no tienen una cuenta analitica asociada a un proyecto y han generado ventas:\n"
            error_message += "  ID       NOMBRE\n"
            for line_id, name in missing_lines.items():
                error_message += f"{line_id}: {name}\n"

            raise UserError(error_message)
        return project_sales

    def calculate_total_amount_cost(self, indirect_expense_lines):
        total_amount_cost = 0.0
        for line in indirect_expense_lines:
            if line.currency_id:
                if line.currency_id.id != 19 and line.currency_id.name != 'PES': # Verifico que el monto de la linea esta en $ y sino la convierto
                    amount = line.currency_id.rate_ids[0]['inverse_company_rate'] * line.amount
                else:
                    amount = line.amount
                total_amount_cost += amount
            total_amount_cost += line.amount
        return total_amount_cost

    def calculate_percentage(self, sales_dict):
        # Calculo el porcentaje de venta de cada projecto con respecto al total de ventas
        total_sales = sum(sales_dict.values())
        percentages = {project: (sales / total_sales) * 100 for project, sales in sales_dict.items()}
        return percentages


    def cost_to_project(self, percentage_for_project, total_amount_cost):
        # Itera sobre cada entrada en el diccionario de porcentajes por proyecto
        for project_id, percentage in percentage_for_project.items():
            # Encuentra el proyecto usando el project_id
            project = self.env['project.project'].browse(project_id)

            if project.exists() and project.analytic_account_id:
                # Calcula el monto a asignar basado en el porcentaje y el costo total
                amount = (percentage / 100.0) * total_amount_cost

                # Busca si ya existe una línea analítica con el mismo proyecto, nombre, fecha y monto
                existing_line = self.env['account.analytic.line'].search([
                    ('name', '=', 'Distribucion de costos indirectos por proyecto'),
                    ('account_id', '=', project.analytic_account_id.id),
                    ('date', '=', self.consolidation_period.date_from),
                    ('amount', '=', amount),
                ])

                if existing_line:
                    # Si la línea analítica ya existe, no es necesario hacer nada más
                    continue
                else:
                    # Si no existe, busca y elimina líneas analíticas con el mismo proyecto, nombre y fecha
                    self.env['account.analytic.line'].search([
                        ('name', '=', 'Distribucion de costos indirectos por proyecto'),
                        ('account_id', '=', project.analytic_account_id.id),
                        ('date', '=', self.consolidation_period.date_from),
                    ]).unlink()

                    # Crea una nueva línea analítica
                    new_line = self.env['account.analytic.line'].create({
                        'name': 'Distribucion de costos indirectos por proyecto',
                        'account_id': project.analytic_account_id.id,
                        'date': self.consolidation_period.date_from,
                        'amount': amount,
                        'company_id': project.company_id if project.company_id else False,
                    })
    



    def analytic_line_indirect_expense(self):
        # inicializo una lista para almacenar las líneas de gastos indirectos
        indirect_expense_lines = []

        analytic_lines = self.env['account.analytic.line'].search([
            ('date', '>=', self.consolidation_period.date_from),
            ('date', '<=', self.consolidation_period.date_to)
        ])
        
        for analytic_line in analytic_lines:
            if analytic_line.sector_account_id.name == 'Gastos Indirectos':
                indirect_expense_lines.append(analytic_line)
        
        return indirect_expense_lines