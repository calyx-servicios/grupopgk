import requests
from boxsdk import Client, OAuth2
import os
from pprint import pprint
import logging
import base64
from io import BytesIO

_logger = logging.getLogger(__name__)

def _get_box_config(env):
    """Obtiene los parámetros de Box desde Odoo."""
    ir_config = env['ir.config_parameter'].sudo()
    config = {
        "grant_type": ir_config.get_param("datareader_odoo.grant_type", "client_credentials"),
        "client_id": ir_config.get_param("datareader_odoo.box_client_id"),
        "client_secret": ir_config.get_param("datareader_odoo.box_client_secret"),
        "box_subject_type": ir_config.get_param("datareader_odoo.box_subject_type"),
        "box_subject_id": ir_config.get_param("datareader_odoo.box_subject_id"),
    }
    if not all([config["client_id"], config["client_secret"], config["box_subject_type"], config["box_subject_id"]]):
        raise ValueError("Faltan datos de configuración de Box en Odoo.")
    return config

def get_access_token(env):
    """Obtiene el access token desde Box API usando la configuración de Odoo."""
    config = _get_box_config(env)
    auth_url = "https://api.box.com/oauth2/token/"
    payload = {
        "grant_type": config["grant_type"],
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "box_subject_type": config["box_subject_type"],
        "box_subject_id": config["box_subject_id"],
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(auth_url, data=payload, headers=headers)
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in")
        if access_token:
            return access_token, expires_in

    return None, None


def get_client(env):
    access_token, expires_in = get_access_token(env)
    if access_token:
        config = _get_box_config(env)
        oauth2 = OAuth2(
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            access_token=access_token
        )
        client = Client(oauth2)
        return client, expires_in
    return None, None

def download_and_attach_file(self, file_name, folder_field='box_folder_id_op', download_path="/tmp/datareader_box"):
    client, _ = get_client(self.env)
    if not client:
        raise ValueError("No se pudo obtener cliente Box.")

    ir_config = self.env['ir.config_parameter'].sudo()
    folder_id = ir_config.get_param(f"datareader_odoo.{folder_field}")
    if not folder_id:
        raise ValueError(f"No está configurado {folder_field} en Configuración.")

    os.makedirs(download_path, exist_ok=True)

    pending_folders = [folder_id]
    while pending_folders:
        current_folder_id = pending_folders.pop(0)
        for item in client.folder(folder_id=current_folder_id).get_items():
            if item.type == 'folder':
                pending_folders.append(item.id)
                continue

            if item.type != 'file' or item.name.lower() != file_name.lower():
                continue

            file_stream = BytesIO()
            client.file(file_id=item.id).download_to(file_stream)
            file_content = file_stream.getvalue()

            attachment = self.env['ir.attachment'].create({
                'name': item.name,
                'type': 'binary',
                'datas': base64.b64encode(file_content),
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            self.attachment_op_id = attachment
            return attachment

    _logger.warning(f"No se encontró el archivo {file_name} en Box.")
    return None


def download_and_attach_retentions(self, op_filename, folder_field='box_folder_id_ret', download_path="/tmp/datareader_box"):
    """
    Descarga hasta 4 archivos de retenciones asociados a la OP.
    El matcheo se hace por el identificador de la OP (único, primer segmento
    del nombre antes del primer '-'), ya que el resto del nombre (mail, etc.)
    puede variar de formato entre el archivo de OP y los de retenciones.
    """
    client, _ = get_client(self.env)
    if not client:
        raise ValueError("No se pudo obtener cliente Box.")

    ir_config = self.env['ir.config_parameter'].sudo()
    folder_id = ir_config.get_param(f"datareader_odoo.{folder_field}")
    if not folder_id:
        raise ValueError(f"No está configurado {folder_field} en Configuración.")

    op_id = op_filename.strip().split("-", 1)[0]
    os.makedirs(download_path, exist_ok=True)

    # Recorre subcarpetas (ej. organización por año_mes) además del nivel raíz.
    ret_attachments = []
    pending_folders = [folder_id]
    while pending_folders and len(ret_attachments) < 4:
        current_folder_id = pending_folders.pop(0)
        for item in client.folder(folder_id=current_folder_id).get_items():
            if len(ret_attachments) >= 4:
                break

            if item.type == 'folder':
                pending_folders.append(item.id)
                continue

            item_name = item.name.strip()
            if item.type != 'file' or item_name.split("-", 1)[0] != op_id:
                continue

            try:
                file_stream = BytesIO()
                client.file(file_id=item.id).download_to(file_stream)
                file_content = file_stream.getvalue()

                attachment = self.env['ir.attachment'].create({
                    'name': item_name,
                    'type': 'binary',
                    'datas': base64.b64encode(file_content),
                    'res_model': self._name,
                    'res_id': self.id,
                    'mimetype': 'application/pdf',
                })
            except Exception as e:
                _logger.error(f"Error descargando retención '{item_name}' para la OP {op_filename}: {e}")
                continue

            ret_attachments.append(attachment)
            setattr(self, f"attachment_ret{len(ret_attachments)}_id", attachment)

    if not ret_attachments:
        _logger.info(f"No se encontraron retenciones para la OP {op_filename}")

    return ret_attachments
