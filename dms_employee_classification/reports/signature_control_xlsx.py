# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class SignatureControlXlsx(models.AbstractModel):
    _name = "report.dms_employee_classification.signature_control_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Signature Control Excel Report"

    def generate_xlsx_report(self, workbook, data, objects):
        """Generate the signature control Excel report.

        Args:
            workbook: xlsxwriter workbook object
            data: report data dictionary
            objects: wizard.signature.control recordset
        """
        # Get the wizard record (should be single record)
        wizard = objects[0] if objects else None
        if not wizard:
            return

        # Create worksheet
        sheet = workbook.add_worksheet("Control de Firmas")

        # Define formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'bg_color': '#D3D3D3',
            'border': 1,
            'align': 'left',
            'valign': 'vcenter',
        })

        bold_format = workbook.add_format({
            'bold': True,
        })

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })

        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy',
            'align': 'center',
        })

        center_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
        })

        text_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
        })

        # Set column widths
        sheet.set_column('A:A', 10)  # LEGAJO
        sheet.set_column('B:B', 30)  # NOMBRE
        sheet.set_column('C:C', 12)  # FECHA
        sheet.set_column('D:D', 10)  # VISTO
        sheet.set_column('E:E', 10)  # FIRMADO

        # Row 1: Title
        sheet.merge_range(0, 0, 0, 2, "Reporte de control de firmas", title_format)

        # Row 2: Date range
        sheet.write(1, 0, "Fecha:", bold_format)
        sheet.write(1, 1, wizard.date_from, date_format)
        sheet.write(1, 2, wizard.date_to, date_format)

        # Row 7: Headers (row index 6)
        headers = ['LEGAJO', 'NOMBRE', 'FECHA', 'VISTO', 'FIRMADO']
        for col, header in enumerate(headers):
            sheet.write(6, col, header, header_format)

        # Get filtered employee documents
        domain = [
            ('classification_date', '>=', wizard.date_from),
            ('classification_date', '<=', wizard.date_to),
        ]
        documents = self.env['hr.employee.document'].search(
            domain,
            order='classification_date'
        )
        documents = documents.sorted(
            key=lambda r: (r.employee_id.legajo or 0, r.classification_date)
        )

        # Write data rows starting from row 8 (index 7)
        row = 7
        previous_employee_id = None

        for doc in documents:
            # Insert blank row when employee changes
            if previous_employee_id and doc.employee_id.id != previous_employee_id:
                row += 1  # Skip a row

            # Write data
            sheet.write(row, 0, doc.employee_id.legajo or '', center_format)
            sheet.write(row, 1, doc.employee_id.name or '', text_format)
            sheet.write(row, 2, doc.classification_date, date_format)
            sheet.write(row, 3, 'SI' if doc.viewed else 'NO', center_format)
            sheet.write(row, 4, 'SI' if doc.signed else 'NO', center_format)

            previous_employee_id = doc.employee_id.id
            row += 1
