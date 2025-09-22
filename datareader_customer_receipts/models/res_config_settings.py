from odoo import models, fields, api, _
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
        string=_("Box Folder ID (OP)"),
        help=_("Base folder ID in Box for payment orders"),
        config_parameter="datareader_odoo.box_folder_id_op"
    )
    box_folder_id_withholding = fields.Char(
        string=_("Box Folder ID (RET)"),
        help=_("Base folder ID in Box for withholding files"),
        config_parameter="datareader_odoo.box_folder_id_withholding"
    )

    datareader_mode = fields.Selection(
        [
            ('production', _('Production')),
            ('testing', _('Testing'))
        ],
        string=_('DataReader Mode'),
        default='production',
        config_parameter="datareader_odoo.mode",
        help=_('Define if DataReader operates in production or testing mode.')
    )
    datareader_download_files = fields.Boolean(
        string=_("Download PDF Files"),
        default=False,
        config_parameter="datareader_odoo.download_files",
        help=_("If enabled and mode is Testing, it will download files from Box; otherwise, it is omitted to speed up the process.")
    )
    datareader_download_first_batch = fields.Boolean(
        string=_("Download Only First Batch"),
        default=False,
        config_parameter="datareader_odoo.download_first_batch",
        help=_("If enabled, the download process will only get the first batch of records from DataReader.")
    )
    