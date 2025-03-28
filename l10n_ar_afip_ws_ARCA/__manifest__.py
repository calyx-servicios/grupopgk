# -*- coding: utf-8 -*-
{
    'name': "l10n_ar_afip_ws_ARCA",
    'summary': """
        This module customizes the lot number labels.
    """,
    'author': "Calyx Servicios S.A",
    "maintainers": ["estebansam21"],
    "website": "https://odoo.calyx-cloud.com.ar/",
    "license": "AGPL-3",
    "category": "Account",
    "version": "15.0.1.0.0",
    "application": False,
    'depends': [
                'l10n_ar_afipws',
                'l10n_ar_afipws_fe'
                ],
    'data': [
        'views/res_config_settings.xml',
        'views/view_move_form.xml'
    ],
}
