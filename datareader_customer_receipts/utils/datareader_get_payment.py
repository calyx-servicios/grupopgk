import requests
import logging

class DatareaderClient:
    def __init__(self, base_url):
        self.base_url = base_url

    def get_payment_orders(self):
        try:
            url = f"{self.base_url}/api/payment_orders"
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error al obtener órdenes de pago desde DataReader: {e}")
            return []