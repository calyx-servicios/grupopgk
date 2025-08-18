# pylint: disable=too-complex

import json
import logging
import time
import traceback
from datetime import datetime
from typing import Dict, List, Tuple, Union

import requests

_MAX_ATTEMPTS = 5
_RETRY_TIME = 1
_NA_VALUE = "na"


class DatareaderError:
    ERROR_INTEGRIDAD = "1"
    ERROR_CUIT_INVALIDO = "3"
    ERROR_TOTAL = "4"
    ERROR_LPG_LSG = "5"
    ERROR_DOCUMENTO_INVALIDO = "6"
    ERROR_CUIT_PROVEEDOR = "7"
    ERROR_CUIT_SOCIEDAD_INVALIDO = "8"
    ERROR_FECHA_NO_RECONOCIDA = "9"
    ERROR_API = "10"


class DatareaderConnector:
    def __init__(self, user, password, url) -> None:
        self._base_url = url
        self._api_user = user
        self._api_pass = password
        self._token = "0"

    @classmethod
    def create_from_environment(cls, env):
        sudo = env["ir.config_parameter"].sudo()
        host = sudo.get_param("datareader_odoo.datareader_api_host")
        user = sudo.get_param("datareader_odoo.datareader_api_user")
        password = sudo.get_param("datareader_odoo.datareader_api_pass")
        return cls(user, password, host)

    def _convert_pedido(self, vals_list: List[Dict]):
        new_lines = []
        for line in vals_list:
            new_line = dict()
            for field, value in line.items():
                if line[field] == _NA_VALUE:
                    continue
                elif field == "quantity":
                    new_line[field.lower()] = int(value or 0)
                else:
                    new_line[field.lower()] = value
            new_lines.append(new_line)
        return new_lines

    def login(self) -> None:
        """It authenticates itself in the API and generates the token

        Args:
            user (str): _description_
            password (str): _description_

        Raises:
            ex: _description_
        """
        try:
            attemps = 0
            while attemps < _MAX_ATTEMPTS:
                header = {"Content-Type": "application/json"}

                payload = json.dumps({"username": self._api_user, "password": self._api_pass})

                logging.info("Realizando autenticacion con API.")

                session = requests.Session()
                session.max_redirects = 60

                response = session.post(f"{self._base_url}/api/auth", headers=header, data=payload)

                if response.status_code == 200:
                    message = json.loads(response.text)
                    self._token = message["token"]
                    logging.info("Autenticacion realizada con exito.")
                    break
                else:
                    logging.info(f"Error {response.status_code}. Se intentara nuevamente")
                    time.sleep(_RETRY_TIME)
                    attemps += 1

        except Exception as ex:
            logging.error("Ocurrio un error al intentar obtener el token.")
            raise ex

    def get_payment_orders(self) -> List[dict]:
        """
        Fetches payment orders from the API.
        Returns a list of payment order dictionaries.
        """
        attempts = 0
        while attempts < _MAX_ATTEMPTS:
            try:
                headers = {"Authorization": f"Bearer {self._token}"}
                response = requests.get(f"{self._base_url}/api/payment_orders/", headers=headers)

                if response.status_code == 200:
                    return response.json() or []
                elif response.status_code in (403, 422):
                    logging.warning("Token expirado o inválido. Reautenticando.")
                    self.login()
                    attempts += 1
                elif response.status_code in (502, 503, 504):
                    logging.error(f"Error {response.status_code}. Reintentando...")
                    time.sleep(5)
                    attempts += 1
                else:
                    logging.error(f"Error inesperado: {response.status_code} - {response.text}")
                    break
            except Exception:
                logging.error(traceback.format_exc())
                attempts += 1
                time.sleep(5)

        raise Exception("No se pudieron obtener las órdenes de pago después de varios intentos.")
    
    def set_payment_order_readed(self, payment_order_id: int) -> bool:
        """
        Marca una orden de pago como leída (readed = True).
        """
        attempts = 0
        while attempts < _MAX_ATTEMPTS:
            try:
                headers = {"Authorization": f"Bearer {self._token}"}
                url = f"{self._base_url}/api/payment_orders/{payment_order_id}/readed"
                response = requests.patch(url, headers=headers)

                if response.status_code == 200:
                    logging.info(f"Orden de pago {payment_order_id} marcada como leída.")
                    return True
                elif response.status_code in (403, 422):
                    logging.warning("Token expirado o inválido. Reautenticando.")
                    self.login()
                    attempts += 1
                elif response.status_code in (502, 503, 504):
                    logging.error(f"Error {response.status_code}. Reintentando...")
                    time.sleep(5)
                    attempts += 1
                elif response.status_code == 404:
                    logging.error(f"Orden de pago {payment_order_id} no encontrada.")
                    return False
                else:
                    logging.error(f"Error inesperado: {response.status_code} - {response.text}")
                    return False
            except Exception:
                logging.error(traceback.format_exc())
                attempts += 1
                time.sleep(5)

        raise Exception(f"No se pudo marcar la orden {payment_order_id} como leída después de varios intentos.")
