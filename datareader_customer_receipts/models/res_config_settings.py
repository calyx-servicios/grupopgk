from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    datareader_default_transfer_journal_id = fields.Many2one(related='company_id.datareader_default_transfer_journal_id', readonly=False)
    datareader_default_transfer_usd_journal_id = fields.Many2one(related='company_id.datareader_default_transfer_usd_journal_id', readonly=False)
    datareader_default_check_journal_id = fields.Many2one(related='company_id.datareader_default_check_journal_id', readonly=False)
    datareader_default_withholding_journal_id = fields.Many2one(related='company_id.datareader_default_withholding_journal_id', readonly=False)
    datareader_api_host = fields.Char(config_parameter="datareader_odoo.datareader_api_host")
    datareader_api_user = fields.Char(config_parameter="datareader_odoo.datareader_api_user")
    datareader_api_pass = fields.Char(config_parameter="datareader_odoo.datareader_api_pass")

    box_client_id = fields.Char(string="Box Client ID", config_parameter="datareader_odoo.box_client_id")
    box_client_secret = fields.Char(string="Box Client Secret", config_parameter="datareader_odoo.box_client_secret")
    box_subject_type = fields.Char(string="Box Subject Type", config_parameter="datareader_odoo.box_subject_type")
    box_subject_id = fields.Char(string="Box Subject ID", config_parameter="datareader_odoo.box_subject_id")
    box_folder_id_op = fields.Char(
        string="Box Folder ID (OP)",
        help="ID de la carpeta base en Box para las órdenes de pago",
        config_parameter="datareader_odoo.box_folder_id_op"
    )
    box_folder_id_withholding = fields.Char(
        string="Box Folder ID (RET)",
        help="ID de la carpeta base en Box para los archivos de retenciones",
        config_parameter="datareader_odoo.box_folder_id_withholding"
    )

    datareader_mode = fields.Selection(
        [
            ('production', 'Producción'),
            ('testing', 'Testing')
        ],
        string="Modo DataReader",
        default='production',
        config_parameter="datareader_odoo.mode",
        help="Define si DataReader opera en modo producción o testing."
    )
    datareader_download_files = fields.Boolean(
        string="Descargar Archivos PDF",
        default=False,
        config_parameter="datareader_odoo.download_files",
        help="Si está activado y el modo es Testing, descargará los archivos de Box; de lo contrario, se omite para acelerar el proceso."
    )
    datareader_download_first_batch = fields.Boolean(
        string="Descargar Solo el Primer Lote",
        default=False,
        config_parameter="datareader_odoo.download_first_batch",
        help="Si está activado, el proceso de descarga solo obtendrá el primer lote (batch) de registros desde DataReader."
    )
    datareader_tolerance_enabled = fields.Boolean(related='company_id.datareader_tolerance_enabled', readonly=False)
    datareader_tolerance_amount = fields.Float(related='company_id.datareader_tolerance_amount', readonly=False)
    datareader_tolerance_account_id = fields.Many2one(related='company_id.datareader_tolerance_account_id', readonly=False)
    datareader_tolerance_journal_id = fields.Many2one(related='company_id.datareader_tolerance_journal_id', readonly=False)
    datareader_tolerance_analytic_account_id = fields.Many2one(related='company_id.datareader_tolerance_analytic_account_id', readonly=False)
    