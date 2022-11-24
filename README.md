# Grupo PGK Odoo 15.0

## Clone

`git clone --recurse-submodules --branch 15.0 https://github.com/calyx-servicios/grupopgk.git`

## odoo.conf File

This file is for reference of how is the `odoo.conf` addons path is configured in production.

## requirements.txt

This file has all the python packages using in production. It has the Odoo dependencies as well.

Useful to create a new python environment for development purposes.

Consider to add there if a module has new dependencies.

`pip3 install -r requirements.txt`

## .vscode.settings.json

This file has the suggested Python Pylint package configuration. To install the Odoo Pylint plugin:

`pip3 install --upgrade git+https://github.com/oca/pylint-odoo.git`

To disable errors that the developer doesn't want to consider, check the table here: