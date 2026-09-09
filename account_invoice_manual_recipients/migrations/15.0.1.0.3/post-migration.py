from odoo.addons.account_invoice_manual_recipients.hooks import post_init_hook


def migrate(cr, version):
    post_init_hook(cr, None)
