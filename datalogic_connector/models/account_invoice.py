# -*- coding: utf-8 -*-
from requests.models import Response
from odoo import fields, models, api, _
import requests
from xml.dom import minidom
from xml.sax.saxutils import escape
import re
from odoo.exceptions import Warning, UserError
import base64, os

class AccountInvice(models.Model):
    _inherit = "account.invoice"

    serie_cfe = fields.Char(copy=False)
    descargar = fields.Binary(copy=False)
    error_dgi = fields.Char(copy=False)
    tpo_cfe = fields.Char(copy=False)
    description_dgi = fields.Char(copy=False)
    hashcfe = fields.Char(copy=False)
    FchVenc = fields.Char(copy=False)
    nrocae = fields.Char(copy=False)
    comprobantecfe = fields.Char(copy=False)
    show_estado = fields.Char(copy=False)
    estado = fields.Char(copy=False)
    txt_send = fields.Text(copy=False)
    txt_rquest = fields.Text(copy=False)
    display_name = fields.Char(
        compute='_compute_display_name',
        string='Document Reference',
        store=True
    )
    origin_ref = fields.Char(copy=False)
    origin_date = fields.Date(copy=False)
    file_name = fields.Char("File Name", compute="_compute_name_file")
    
    def _compute_name_file(self):
        for rec in self:
            if rec.id:
                rec.file_name = "DGI-%s.pdf" % (rec.id)
            else:
                rec.file_name = 'DGI-%s-00.pdf' % (rec._name.replace('.', '_'))

    def scape_value(self,string):
        original_value = ["º","À","Á","Â","Ã","Ä","Å","Æ","Ç","È","É","Ê","Ë","Ì","Í","Î","Ï",
        "Ð","Ñ","Ò","Ó","Ô","Õ","Ö","Ø","Ù","Ú","Û","Ü","Ý","Þ","ß","à","á","â","ã","ä",
        "å","æ","ç","è","é","ê","ë","ì","í","î","ï","ð","ñ","ò","ó","ô","õ","ö","ø","ù",
        "ú","û","ü","ý","þ","ÿ"]
        scaped_value = ["&#186;","&#192;","&#193;","&#194;","&#195;","&#196;","&#197;","&#198;",
        "&#199;","&#200;","&#201;","&#202;","&#203;","&#204;","&#205;","&#206;","&#207;",
        "&#208;","&#209;","&#210;","&#211;","&#212;","&#213;","&#214;","&#216;","&#217;",
        "&#218;","&#219;","&#220;","&#221;","&#222;","&#223;","&#224;","&#225;","&#226;",
        "&#227;","&#228;","&#229;","&#230;","&#231;","&#232;","&#233;","&#234;","&#235;",
        "&#236;","&#237;","&#238;","&#239;","&#240;","&#241;","&#242;","&#243;","&#244;",
        "&#245;","&#246;","&#248;","&#249;","&#250;","&#251;","&#252;","&#253;","&#254;",
        "&#255;"]
        for (line,cap) in zip(original_value,scaped_value):
                string=string.replace(line,cap)
        return string
    @api.model
    def compute_defff(self):   
        if self.comprobantecfe and self.hashcfe:    
                doc = minidom.Document()
                Envelope = doc.createElement("xsd:Envelope")
                doc.appendChild(Envelope)
                Envelope.setAttribute("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")
                Envelope.setAttribute("xmlns:gfe", "GFE_Client")
                header = doc.createElement("xsd:Header")
                Envelope.appendChild(header)
                body = doc.createElement("xsd:Body")
                Envelope.appendChild(body)
                grabar = doc.createElement("gfe:WSExternoStandalone.CFE_GENERARPDF")
                body.appendChild(grabar)
                entrada = doc.createElement("gfe:Xmlentrada")
                grabar.appendChild(entrada)
                Xmlentrada = doc.createElement("Xmlentrada")
                Datos = doc.createElement("Datos")
                Xmlentrada.appendChild(Datos)
                Dato = doc.createElement("Dato")
                Datos.appendChild(Dato)
                Valor = doc.createElement("Valor")
                Dato.appendChild(Valor)
                XMLDocumento = doc.createElement("XMLDocumento")
                XMLDocumento.setAttribute("xmlns", "GFE_Client")

                EmpCod = doc.createElement("EmpCod")
                text_node = doc.createTextNode(str(self.company_id.empcod))
                EmpCod.appendChild(text_node)
                XMLDocumento.appendChild(EmpCod)

                CfeTpo = doc.createElement("CfeTpo")
                text_node = doc.createTextNode(self.tpo_cfe)
                CfeTpo.appendChild(text_node)
                XMLDocumento.appendChild(CfeTpo)

                CfeSer = doc.createElement("CfeSer")
                text_node = doc.createTextNode(self.serie_cfe)
                CfeSer.appendChild(text_node)
                XMLDocumento.appendChild(CfeSer)

                CfeNum = doc.createElement("CfeNum")
                text_node = doc.createTextNode(str(self.comprobantecfe))
                CfeNum.appendChild(text_node)
                XMLDocumento.appendChild(CfeNum)

                CfeImpTot = doc.createElement("CfeImpTot")
                text_node = doc.createTextNode(str(self.residual))
                CfeImpTot.appendChild(text_node)
                XMLDocumento.appendChild(CfeImpTot)

                CfeHash = doc.createElement("CfeHash")
                text_node = doc.createTextNode(str(self.hashcfe[:6]))
                CfeHash.appendChild(text_node)
                XMLDocumento.appendChild(CfeHash)

                xmldata = XMLDocumento.toprettyxml("   ")
                Data = doc.createCDATASection(xmldata)
                Valor.appendChild(Data)
                xmlescape = Xmlentrada.toprettyxml("   ")
                xmlescapedoc = doc.createTextNode(xmlescape)
                entrada.appendChild(xmlescapedoc)
                documentoXML = Envelope.toprettyxml("   ")
                url = self.company_id.url_key
                r = requests.post(
                url=url,
                data=documentoXML,
                headers={"Content-Type": "text/xml"},
                verify=False,
                )

                self.txt_compute_defff = r.text
                if len(r.text.split("CDATA[")) != 1:
                        test = r.text.split("CDATA[")[1].split("]]")[0]
                        self.descargar = test
                else:
                        self.descargar= "0"
        else:
                self.descargar= "0"

    @api.model
    def compute_estado(self):
        dict_estados = {
        "1": "Registrado en bandeja (estado inicial)",
        "2": "Registrado en bandeja ERROR",
        "3": "FirmadoOk",
        "4": "FirmadoError",
        "5": "Registrado en servidor",
        "6": "Acuse recibido DGI",
        "7": "Confirmado DGI",
        "8": "Rechazado DGI",
        "9": "Anulado ERP",
        "10": "Anulado Registrado en el servidor",
        "11": "Observado DGI",
        "12": "Confirmado ERP",
        "13": "Confirmado ERP Registrado en el servidor",
        "14": "Para Revisión",
        "15": "Anulado Interno",
        "16": "No requiere envío a DGI",               
        }
        
        doc = minidom.Document()
        Envelope = doc.createElement("xsd:Envelope")
        doc.appendChild(Envelope)
        Envelope.setAttribute("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")
        Envelope.setAttribute("xmlns:gfe", "GFE_Client")
        header = doc.createElement("xsd:Header")
        Envelope.appendChild(header)
        body = doc.createElement("xsd:Body")
        Envelope.appendChild(body)
        grabar = doc.createElement("gfe:WSExternoStandalone.CONSULTARCFE")
        body.appendChild(grabar)
        entrada = doc.createElement("gfe:Xmlentrada")
        grabar.appendChild(entrada)
        Xmlentrada = doc.createElement("Xmlentrada")
        Datos = doc.createElement("Datos")
        Xmlentrada.appendChild(Datos)
        Dato = doc.createElement("Dato")
        Datos.appendChild(Dato)
        Valor = doc.createElement("Valor")
        Dato.appendChild(Valor)
        XMLParametros = doc.createElement("XMLParametros")
        XMLParametros.setAttribute("xmlns", "GFE_Client")
# <!-- Empresa [String(10)] -->
        Empresa = doc.createElement("Empresa")
        text_node = doc.createTextNode(str(self.company_id.empcod))
        Empresa.appendChild(text_node)
        XMLParametros.appendChild(Empresa)

        RangoEnviados = doc.createElement("RangoEnviados")
        XMLParametros.appendChild(RangoEnviados)  

        ComprobanteCFEInicial = doc.createElement("ComprobanteCFEInicial")
        text_node = doc.createTextNode(str(self.comprobantecfe))
        ComprobanteCFEInicial.appendChild(text_node)        
        RangoEnviados.appendChild(ComprobanteCFEInicial)

        ComprobanteCFEFinal = doc.createElement("ComprobanteCFEFinal")
        text_node = doc.createTextNode(str(self.comprobantecfe))
        ComprobanteCFEFinal.appendChild(text_node)        
        RangoEnviados.appendChild(ComprobanteCFEFinal)

        Estados = doc.createElement("Estados")
        RangoEnviados.appendChild(Estados)  

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("1")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("2")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("3")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("4")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("5")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("6")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("7")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("8")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("9")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("10")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("11")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("12")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("13")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("14")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("15")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        Estado = doc.createElement("Estado")
        text_node = doc.createTextNode("16")
        Estado.appendChild(text_node)        
        Estados.appendChild(Estado)

        xmldata = XMLParametros.toprettyxml("   ")
        Data = doc.createCDATASection(xmldata)
        Valor.appendChild(Data)
        xmlescape = Xmlentrada.toprettyxml("   ")
        xmlescapedoc = doc.createTextNode(xmlescape)
        entrada.appendChild(xmlescapedoc)
        documentoXML = Envelope.toprettyxml("   ")
        url = self.company_id.url_key
        r = requests.post(
            url=url,
            data=documentoXML,
            headers={"Content-Type": "text/xml"},
            verify=False,
        )
        self.txt_compute_estado = r.text
        if len(r.text.split("Estado")) != 1:
                estado = r.text.split("Estado")[1].split(";")[1].split("&")[0]
                self.show_estado = dict_estados.get(estado,"error")
                self.estado = estado
        else:
                self.show_estado = "Error"
                self.estado = "Error"

    def update_invoice_status(self):
        self.compute_defff()
        self.compute_estado()

    def send_dgi_with_invoice(self):
        self.create_dgi_document(True)
    
    def send_dgi(self):
        self.create_dgi_document(False)

    def create_dgi_document(self,with_invoice):
        doc = minidom.Document()
        Envelope = doc.createElement("xsd:Envelope")
        doc.appendChild(Envelope)
        Envelope.setAttribute("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")
        Envelope.setAttribute("xmlns:gfe", "GFE_Client")
        header = doc.createElement("xsd:Header")
        Envelope.appendChild(header)
        body = doc.createElement("xsd:Body")
        Envelope.appendChild(body)
        grabar = doc.createElement("gfe:WSExternoStandalone.GRABAR")
        body.appendChild(grabar)
        entrada = doc.createElement("gfe:Xmlentrada")
        grabar.appendChild(entrada)
        Xmlentrada = doc.createElement("Xmlentrada")
        Datos = doc.createElement("Datos")
        Xmlentrada.appendChild(Datos)
        Dato = doc.createElement("Dato")
        Datos.appendChild(Dato)
        Valor = doc.createElement("Valor")
        Dato.appendChild(Valor)
        Bandeja = doc.createElement("Bandeja")
        Bandeja.setAttribute("xmlns", "GFE_Client")
# <!-- Empresa [String(10)] -->
        EmpCod = doc.createElement("EmpCod")
        text_node = doc.createTextNode(str(self.company_id.empcod))
        EmpCod.appendChild(text_node)
        Bandeja.appendChild(EmpCod)
# <!-- Codigo Documento ej DL-101-96660-01/01/2012 [String(100)] -->
        BanDocCodERP = doc.createElement("BanDocCodERP")
        text_node = doc.createTextNode(str(self.id))
        BanDocCodERP.appendChild(text_node)
        Bandeja.appendChild(BanDocCodERP)
# <!-- Versión del CFE [String(3)] -->
        BanVersionCFE = doc.createElement("BanVersionCFE")
        text_node = doc.createTextNode("1.0")
        BanVersionCFE.appendChild(text_node)
        Bandeja.appendChild(BanVersionCFE)
# <!-- Tipo CFE Se puede grabar el codigo del CFE o el tipo de    doc. del ERP, para esto debe existir la relación[Integer] -->
        # 111  e-Factura
        # 112  Nota de Crédito de e-Factura
        # 113  Nota de Débito de e-Factura
        # 121  e-Factura Exportación
        # 122  Nota de Crédito de e-Factura Exportación
        # 123  Nota de Débito de e-Factura Exportación
        cfe_type = "111"
        if self.journal_document_type_id.document_type_id.code in ["111","112","113","121","122","123"]:
            cfe_type = self.journal_document_type_id.document_type_id.code
        dni_name = self.partner_id.main_id_category_id.code
        document_dic = {"NIE":"1","RUC":"2","CIe":"3","Otros":"4","Pasaporte":"5","DNI":"6","NIFE":"7"}
        rec_doc = document_dic.get(dni_name,"4")
        BanTpoCFE = doc.createElement("BanTpoCFE")
        text_node = doc.createTextNode(cfe_type)
        BanTpoCFE.appendChild(text_node)
        Bandeja.appendChild(BanTpoCFE)
# <!-- Serie [String(2)] vacio -->
        BanSerCFE = doc.createElement("BanSerCFE")
        Bandeja.appendChild(BanSerCFE)
# <!-- Numero de CFE [Integer] vacio -->
        BanNumCFE = doc.createElement("BanNumCFE")
        Bandeja.appendChild(BanNumCFE)
# <!-- Fecha del CFE [Date] -->
        BanFchCFE = doc.createElement("BanFchCFE")
        text_node = doc.createTextNode(str(self.date))
        BanFchCFE.appendChild(text_node)
        Bandeja.appendChild(BanFchCFE)
# # <!-- Período desde [Date] -->
#         BanPerDesde = doc.createElement("BanPerDesde")
#         text_node = doc.createTextNode("")
#         BanPerDesde.appendChild(text_node)
#         Bandeja.appendChild(BanPerDesde)
# # <!-- Período hasta [Date] -->
#         BanPerHasta = doc.createElement("BanPerHasta")
#         text_node = doc.createTextNode("")
#         BanPerHasta.appendChild(text_node)
#         Bandeja.appendChild(BanPerHasta)
# <!-- Indica si los importes son iva incluido. Valores:
# 1: Líneas de detalle se expresan con IVA incluido,
# 2:Líneas de detalle se expresan con IMEBA y adicionales incluidos,
#  3: Líneas de detalle corresponden a ventasrealizadas por contribuyentes con obligación IVA mínimo,
#  Monotributo o Monotributo MIDES; en caso contrario nodebe pasarse el tag [Integer] -->
        BanIndMonBru = doc.createElement("BanIndMonBru")
        text_node = doc.createTextNode("1")
        BanIndMonBru.appendChild(text_node)
        Bandeja.appendChild(BanIndMonBru)
# <!-- Forma de Pago. Valores 1: Contado 2: Credito [Integer] -->
        BanForPag = doc.createElement("BanForPag")
        text_node = doc.createTextNode("1")
        BanForPag.appendChild(text_node)
        Bandeja.appendChild(BanForPag)
# <!-- Fecha Vencimiento [Date] -->
        BanFchVen = doc.createElement("BanFchVen")
        text_node = doc.createTextNode(str(self.date))
        BanFchVen.appendChild(text_node)
        Bandeja.appendChild(BanFchVen)
# <!-- RUC Emisior [String(12)] -->
        BanRucEmi = doc.createElement("BanRucEmi")
        text_node = doc.createTextNode(str(self.company_id.main_id_number))
        BanRucEmi.appendChild(text_node)
        Bandeja.appendChild(BanRucEmi)
# <!-- Nombre Emisor [String(150)] -->
        BanNomEmi = doc.createElement("BanNomEmi")
        text_node = doc.createTextNode(str(self.company_id.name))
        BanNomEmi.appendChild(text_node)
        Bandeja.appendChild(BanNomEmi)
# <!-- Nombre Comercial del emisor [String(30)] -->
        BanNomComEmi = doc.createElement("BanNomComEmi")
        text_node = doc.createTextNode(str(self.company_id.company_registry))
        BanNomComEmi.appendChild(text_node)
        Bandeja.appendChild(BanNomComEmi)
        
# <!-- Codigo Sucursal Principal Emisor [String(6)] nos lo dan ellos en algun momento-->
        # BanSucCodPriEmi = doc.createElement("BanSucCodPriEmi")
        # text_node = doc.createTextNode("")
        # BanSucCodPriEmi.appendChild(text_node)
        # Bandeja.appendChild(BanSucCodPriEmi)
# <!-- Indica Nombre Sucursal Principal Emisor [String(20)] -->
        BanSucNomPriEmi = doc.createElement("BanSucNomPriEmi")
        text_node = doc.createTextNode(str(self.company_id.partner_id.name))
        BanSucNomPriEmi.appendChild(text_node)
        Bandeja.appendChild(BanSucNomPriEmi)
# <!-- Dirección Fiscal Emisor [String(70)] -->
        BanDirFisEmi = doc.createElement("BanDirFisEmi")
        text_node = doc.createTextNode(str(self.company_id.street))
        BanDirFisEmi.appendChild(text_node)
        Bandeja.appendChild(BanDirFisEmi)
# <!-- Nombre Ciudad Emisor [String(30)] -->
        BanCiuNomEmi = doc.createElement("BanCiuNomEmi")
        text_node = doc.createTextNode(str(self.company_id.city))
        BanCiuNomEmi.appendChild(text_node)
        Bandeja.appendChild(BanCiuNomEmi)
# <!-- Nombre Departamento Emisor [String(30)] -->
        BanDepNomEmi = doc.createElement("BanDepNomEmi")
        text_node = doc.createTextNode(str(self.company_id.state_id.name))
        BanDepNomEmi.appendChild(text_node)
        Bandeja.appendChild(BanDepNomEmi)
# <!-- Código Tipo Documento Receptor. Valores: 2: RUC (Uruguay) 3: C.I. (Uruguay) 4: Otros
# 5: Pasaporte (todoslos países) 6: DNI (documento de identidad de Argentina, Brasil, Chile o Paraguay)
# 7: NIFE [Integer] -->
        if self.partner_id.main_id_number:
                BanCodTpoDocRec = doc.createElement("BanCodTpoDocRec")
                text_node = doc.createTextNode(rec_doc)
                BanCodTpoDocRec.appendChild(text_node)
                Bandeja.appendChild(BanCodTpoDocRec)
# <!--Codigo pais del receptor [String(50)] -->
        if self.partner_id.country_id.code:
                BanCodPaisRec = doc.createElement("BanCodPaisRec")
                text_node = doc.createTextNode(self.partner_id.country_id.code)
                BanCodPaisRec.appendChild(text_node)
                Bandeja.appendChild(BanCodPaisRec)
# <!-- Nº Documento Receptor [String(12)] -->
        if self.partner_id.main_id_number:
                if rec_doc in ["1","2","3"]:
                        BanNumDocRec = doc.createElement("BanNumDocRec")
                        text_node = doc.createTextNode(str(self.partner_id.main_id_number))
                        BanNumDocRec.appendChild(text_node)
                        Bandeja.appendChild(BanNumDocRec)
                else:
                        BanNumDocRecExt = doc.createElement("BanNumDocRecExt")
                        text_node = doc.createTextNode(str(self.partner_id.main_id_number))
                        BanNumDocRecExt.appendChild(text_node)
                        Bandeja.appendChild(BanNumDocRecExt)   
# <!-- Nombre del receptor [String(150)] -->
        if self.partner_id.name:
                BanNomRec = doc.createElement("BanNomRec")
                text_node = doc.createTextNode(str(self.partner_id.name))
                BanNomRec.appendChild(text_node)
                Bandeja.appendChild(BanNomRec)
# <!-- Direccion del receptor [String(70)] -->
        if self.partner_id.street:
                BanDirRec = doc.createElement("BanDirRec")
                text_node = doc.createTextNode(str(self.partner_id.street))
                BanDirRec.appendChild(text_node)
                Bandeja.appendChild(BanDirRec)
# <!-- Ciudad de receptor [String(30)] -->
        if self.partner_id.country_id.code:
                if self.partner_id.country_id.code == "MX":
                        BanCiuRec = doc.createElement("BanCiuRec")
                        text_node = doc.createTextNode(str(self.partner_id.city_id.name))
                        BanCiuRec.appendChild(text_node)
                        Bandeja.appendChild(BanCiuRec)
                else:
                        BanCiuRec = doc.createElement("BanCiuRec")
                        text_node = doc.createTextNode(str(self.partner_id.city))
                        BanCiuRec.appendChild(text_node)
                        Bandeja.appendChild(BanCiuRec)
# <!-- Departamento, Provincia o Estado del receptor [String(30)] -->
        if self.partner_id.state_id.name:
                BanDepRec = doc.createElement("BanDepRec")
                text_node = doc.createTextNode(str(self.partner_id.state_id.name))
                BanDepRec.appendChild(text_node)
                Bandeja.appendChild(BanDepRec)
# <!-- Codigo Pais de receptor [String(30)] -->
        if self.partner_id.country_id.name:
                BanPaisRec = doc.createElement("BanPaisRec")
                text_node = doc.createTextNode(str(self.partner_id.country_id.name))
                BanPaisRec.appendChild(text_node)
                Bandeja.appendChild(BanPaisRec)
# <!-- iva min -->
        BanTasaIVAMin = doc.createElement("BanTasaIVAMin")
        text_node = doc.createTextNode(str(10.000))
        BanTasaIVAMin.appendChild(text_node)
        Bandeja.appendChild(BanTasaIVAMin)
# <!-- iva base -->
        BanTasaIVABas = doc.createElement("BanTasaIVABas")
        text_node = doc.createTextNode(str(22.000))
        BanTasaIVABas.appendChild(text_node)
        Bandeja.appendChild(BanTasaIVABas)
#<!-- Cláusula de venta (Incoterms: FOB, CIF, etc) [String(3)] -->
        if self.journal_document_type_id.document_type_id.code in ["121","122","123"]:
                BanClaVen = doc.createElement("BanClaVen")
                text_node = doc.createTextNode("N/A")
                BanClaVen.appendChild(text_node)
                Bandeja.appendChild(BanClaVen)
#<!-- Indica el medio de transporte en que se traslada la mercadería [String(20)]-->
                BanModVen = doc.createElement("BanModVen")
                text_node = doc.createTextNode("90")
                BanModVen.appendChild(text_node)
                Bandeja.appendChild(BanModVen)
#<!-- Indica el medio de transporte en que se traslada la mercadería [String(20)]-->
                BanViaTra = doc.createElement("BanViaTra")
                text_node = doc.createTextNode("8")
                BanViaTra.appendChild(text_node)
                Bandeja.appendChild(BanViaTra)

# <!-- Renglones del producto-->
        BanLin = doc.createElement("BanLin")
        monto_no_grabado = 0
        monto_iva_min = 0
        monto_iva_base = 0
        line_cont = 1
        for line in self.invoice_line_ids:
            BanLinItem = doc.createElement("BanLinItem")
            BanLin.appendChild(BanLinItem)
# <!-- Numero de Renglon [Integer] -->
            NumLin = doc.createElement("NumLin")
            text_node = doc.createTextNode(str(line_cont))
            NumLin.appendChild(text_node)
            BanLinItem.appendChild(NumLin)
# <!-- Indicador de facturación. Valores: 1: Exento de IVA 2: Gravado a Tasa Mínima
# 3: Gravado a Tasa Básica 4:Gravado a “Otra Tasa” 5: Entrega Gratuita. Por ejemplo docenas de trece
# 6: Producto o servicio no facturable 7:Producto o servicio no facturable negativo
# 8: Solo para remitos: Ítem a rebajar en remitos. En área de referenciase debe indicar el N° de remito que ajusta
# 9: Solo para resguardos: Ítem a ajustar en resguardos. En área dereferencia se debe indicar el N° de resguardo que ajusta
# 10: Exportación y asimiladas 11: Impuesto percibido 12:IVA en suspenso [Integer] VALORES PLIS-->
            ind_fact = "1"
            if line.invoice_line_tax_ids.name == "IVA Ventas (22%)":
                ind_fact = "3"
                monto_iva_base += line.price_subtotal
                price_unit = line.price_unit * 1.22
            if line.invoice_line_tax_ids.name == "IVA Ventas (10%)":
                ind_fact = "2"
                monto_iva_min += line.price_subtotal
                price_unit = line.price_unit * 1.10
            if ind_fact == "1":
                price_unit = line.price_unit
                monto_no_grabado += line.price_subtotal
                if self.journal_document_type_id.document_type_id.code not in ["111","112","113"]:
                        ind_fact = "10"

            IndFac = doc.createElement("IndFac")
            text_node = doc.createTextNode(ind_fact)
            IndFac.appendChild(text_node)
            BanLinItem.appendChild(IndFac)
# <!-- Nombre del producto o servicio [String(80)] -->
        #     dict_servicios = {
        #         "Honorarios profesionales por gestión de recupero": "Professional fees for legal recovery",
        #         "Honorarios profesionales": "Professional Fees",
        #         "Honorarios profesionales por asesoramiento": "Professional fees for consultancy",
        #         "Gastos Administrativos varios": "Administrative costs",
        #         "Costos bancarios": "Banking Costs",
        #         "Gastos de terceros": "Third Parties Expenses",
        #         "Retenciones": "Withholdings",
        #         "Honorarios profesionales por seminario": "Professional fees for seminar",
        #         "Honorarios profesionales por ahorro de contribución por avería gruesa": "Professional fees over claimed general average contribution savings / reduction",
        #         "Honorarios profesionales por ahorro de contribución por salvamento": "Professional fees over claimed salvage contribution savings / reduction",
        #         "Honorarios profesionales por ahorro de contribución por avería gruesa y salvamento": "Professional fees over claimed general average & salvage contributions savings / reductions",
        #         "Honorarios profesionales por asesoramiento en tema de garantías por avería gruesa": "Legal consultancy fees on general average bonds & guarantees issuance / cargo release",
        #         "Honorarios profesionales por asesoramiento en tema de garantías por salvamento": "Legal consultancy fees on salvage guarantees issuance / cargo release",
        #         "Honorarios profesionales por asesoramiento en tema de garantías por avería gruesa y salvamento": "Legal consultancy fees on general average / salvage bonds & guarantees issuance / cargo release",
        #         "Costo de garantías por avería gruesa": "General average guarantees issuance fee",
        #         "Costo de garantías por salvamento": "Salvage guarantee issuance fee",
        #         "Costo de garantías por avería gruesa y salvamento": "General average & salvage guarantee issuance fee",
        #         "Honorarios profesionales por venta de rezago": "Professional fees over salvage sale",
        #         "Honorarios profesionales por ajuste / liquidación de siniestro": "Professional fees for adjustment / casualty settlement",
        #         "Honorarios profesionales por gestión de siniestro (con acuerdo)": "Professional fees for liability (with agreement)",
        #         "Honorarios profesionales por gestión de siniestro (sin acuerdo)": "Professional fees for liability (without agreement)",
        #         "Container": "Container",               
        #         }
        #     if self.partner_id.lang == "en_US":
        #         ItemNom = doc.createElement("ItemNom")
        #         text_node = doc.createTextNode(str(dict_servicios.get(line.product_id.name,line.product_id.name)))
        #         ItemNom.appendChild(text_node)
        #         BanLinItem.appendChild(ItemNom)
        #     else:
        #         ItemNom = doc.createElement("ItemNom")
        #         text_node = doc.createTextNode(str(line.product_id.name))
        #         ItemNom.appendChild(text_node)
        #         BanLinItem.appendChild(ItemNom)
            ItemNom = doc.createElement("ItemNom")
            text_node = doc.createTextNode(str(line.product_id.name))
            ItemNom.appendChild(text_node)
            BanLinItem.appendChild(ItemNom)
# <!-- Cantidad del ítem. Se admite negativo solo para eliminar un item del propio CFE.
#  Para prestación deservicios no es obligatorio imprimir [Currency(14,3)] -->
            ItemCan = doc.createElement("ItemCan")
            text_node = doc.createTextNode(str(line.quantity))
            ItemCan.appendChild(text_node)
            BanLinItem.appendChild(ItemCan)
# <!-- Unidad de medida [String(4)] -->
            ItemUniMed = doc.createElement("ItemUniMed")
            text_node = doc.createTextNode("N/A")
            ItemUniMed.appendChild(text_node)
            BanLinItem.appendChild(ItemUniMed)
# <!-- Precio unitario [Currency(11,6)] -->
            ItemPreUni = doc.createElement("ItemPreUni")
            text_node = doc.createTextNode(str(price_unit))
            ItemPreUni.appendChild(text_node)
            BanLinItem.appendChild(ItemPreUni)
# <!-- Monto Ítem [Currency(15,2)] -->
            ItemMon = doc.createElement("ItemMon")
            text_node = doc.createTextNode(str(price_unit*line.quantity))
            ItemMon.appendChild(text_node)
            BanLinItem.appendChild(ItemMon)

            ItemDes = doc.createElement("ItemDes")
            text_node = doc.createTextNode(str(line.name))
            ItemDes.appendChild(text_node)
            BanLinItem.appendChild(ItemDes)

            line_cont += 1
# <!-- Tipo de Moneda de la Transacción. Se utiliza codificación según el Estándar  Internacional ISO 4217.[String(3)] -->
        BanTpoMonTra = doc.createElement("BanTpoMonTra")
        text_node = doc.createTextNode(str(self.currency_id.name))
        BanTpoMonTra.appendChild(text_node)
        Bandeja.appendChild(BanTpoMonTra)
#  <!-- Tipo de Cambio [Currency(4,3)] -->
        if self.currency_id.name != 'UYU':
           BanTpoCam = doc.createElement("BanTpoCam")
           text_node = doc.createTextNode(str(self.currency_id.inverse_rate))
           BanTpoCam.appendChild(text_node)
           Bandeja.appendChild(BanTpoCam)
# <!-- monto sin iva -->
        if self.journal_document_type_id.document_type_id.code in ["111","112","113"]:
                BanTMonNoGra = doc.createElement("BanTMonNoGra")
                text_node = doc.createTextNode(str(monto_no_grabado))
                BanTMonNoGra.appendChild(text_node)
                Bandeja.appendChild(BanTMonNoGra)
        else:
                BanTMonExpAsi = doc.createElement("BanTMonExpAsi")
                text_node = doc.createTextNode(str(monto_no_grabado))
                BanTMonExpAsi.appendChild(text_node)
                Bandeja.appendChild(BanTMonExpAsi)
# <!-- monto con iva min-->
        BanTMonNetIMin = doc.createElement("BanTMonNetIMin")
        text_node = doc.createTextNode(str(monto_iva_min))
        BanTMonNetIMin.appendChild(text_node)
        Bandeja.appendChild(BanTMonNetIMin)
# <!-- monto con iva base-->
        BanTMonNetIBas = doc.createElement("BanTMonNetIBas")
        text_node = doc.createTextNode(str(monto_iva_base))
        BanTMonNetIBas.appendChild(text_node)
        Bandeja.appendChild(BanTMonNetIBas)
# <!-- iva min a pagar -->
        BanTotIVAMin = doc.createElement("BanTotIVAMin")
        text_node = doc.createTextNode(str(monto_iva_min*0.10))
        BanTotIVAMin.appendChild(text_node)
        Bandeja.appendChild(BanTotIVAMin)
# <!-- iva base a pagar -->
        BanTotIVABas = doc.createElement("BanTotIVABas")
        text_node = doc.createTextNode(str(monto_iva_base*0.22))
        BanTotIVABas.appendChild(text_node)
        Bandeja.appendChild(BanTotIVABas)
# <!-- Total Monto Total [Currency(15,2)] calcular -->
        BanTotMonTot = doc.createElement("BanTotMonTot")
        text_node = doc.createTextNode(str(monto_no_grabado + monto_iva_min*1.10 + monto_iva_base*1.22))
        BanTotMonTot.appendChild(text_node)
        Bandeja.appendChild(BanTotMonTot)
# <!-- Cantidad de Líneas [Integer] calcular-->
        BanCanLin = doc.createElement("BanCanLin")
        text_node = doc.createTextNode(str(line_cont - 1))
        BanCanLin.appendChild(text_node)
        Bandeja.appendChild(BanCanLin)        
# <!-- Adenda [Text] -->
        # reference = self.ref.replace(" ","")
        # reference = reference[len(self.Our_reference):len(reference)]
        # if reference != "N/A":
        #         reference = reference.replace("/","", 1)
        # o_ref = "O/Ref.:                                                                                                  "
        # for leter in self.Our_reference:
        #         o_ref = o_ref.replace(" ", leter,1)        
        # y_ref = "Y/Ref.:                                                                                                       {}".format(reference)
        # for leter in self.Y_reference:
        #         y_ref = y_ref.replace(" ", leter,1)
        # adenda = o_ref + y_ref 
        # BanAdenda = doc.createElement("BanAdenda")
        # text_node = doc.createTextNode(adenda)
        # BanAdenda.appendChild(text_node)
        # Bandeja.appendChild(BanAdenda)
# <!-- Monto Total a Pagar [Currency(15,2)] -->
        BanMonTotPag = doc.createElement("BanMonTotPag")
        text_node = doc.createTextNode(str(monto_no_grabado + monto_iva_min*1.10 + monto_iva_base*1.22))
        BanMonTotPag.appendChild(text_node)
        Bandeja.appendChild(BanMonTotPag)

        Bandeja.appendChild(BanLin)

#  <!-- Informacion de referencia-->
        if cfe_type in ["122","112","123","113"]:
                BanInfRef = doc.createElement("BanInfRef")
                Bandeja.appendChild(BanInfRef)

                BanInfRefItem = doc.createElement("BanInfRefItem")
                BanInfRef.appendChild(BanInfRefItem)
                if self.origin:
                        invoices = self.env['account.invoice'].search([('display_name','=',self.origin)])
                        ref_count = 1
                        for invoice in invoices:
                                InfRefNum = doc.createElement("InfRefNum")
                                text_node = doc.createTextNode(str(ref_count))
                                InfRefNum.appendChild(text_node)
                                BanInfRefItem.appendChild(InfRefNum)
                                if invoice.comprobantecfe:
                        #    <!-- Tipo CFE de referencia [String(20)] -->
                                        InfRefCFERef = doc.createElement("InfRefCFERef")
                                        text_node = doc.createTextNode(str(invoice.tpo_cfe))
                                        InfRefCFERef.appendChild(text_node)
                                        BanInfRefItem.appendChild(InfRefCFERef)
                        #    <!-- Serie del CFE de referencia [String(2)] -->
                                        InfRefCFESerRef = doc.createElement("InfRefCFESerRef")
                                        text_node = doc.createTextNode(str(invoice.serie_cfe))
                                        InfRefCFESerRef.appendChild(text_node)
                                        BanInfRefItem.appendChild(InfRefCFESerRef)
                        #    <!-- Número del CFE de referencia [Integer] -->
                                        InfRefCFENumRef = doc.createElement("InfRefCFENumRef")
                                        text_node = doc.createTextNode(str(invoice.comprobantecfe))
                                        InfRefCFENumRef.appendChild(text_node)
                                        BanInfRefItem.appendChild(InfRefCFENumRef)
                        #    <!-- Razón referencia [String(90)] -->
                                        InfRefRazRef = doc.createElement("InfRefRazRef")
                                        BanInfRefItem.appendChild(InfRefRazRef)
                        #    <!-- Fecha CFE de referencia [Date] -->
                                        InfRefFchRef = doc.createElement("InfRefFchRef")
                                        BanInfRefItem.appendChild(InfRefFchRef)               
                                else:
                                        InfRefInd = doc.createElement("InfRefInd")
                                        text_node = doc.createTextNode("1")
                                        InfRefInd.appendChild(text_node)
                                        BanInfRefItem.appendChild(InfRefInd)
                        #    <!-- Razón referencia [String(90)] -->
                                        InfRefRazRef = doc.createElement("InfRefRazRef")
                                        text_node = doc.createTextNode(str(self.origin_ref))
                                        InfRefRazRef.appendChild(text_node)
                                        BanInfRefItem.appendChild(InfRefRazRef)
                        #    <!-- Fecha CFE de referencia [Date] -->
                                        InfRefFchRef = doc.createElement("InfRefFchRef")
                                        text_node = doc.createTextNode(str(self.origin_date))
                                        InfRefFchRef.appendChild(text_node)
                                        BanInfRefItem.appendChild(InfRefFchRef)
                                ref_count += 1
                else:
                        InfRefNum = doc.createElement("InfRefNum")
                        text_node = doc.createTextNode("1")
                        InfRefNum.appendChild(text_node)
                        BanInfRefItem.appendChild(InfRefNum)

                        InfRefInd = doc.createElement("InfRefInd")
                        text_node = doc.createTextNode("1")
                        InfRefInd.appendChild(text_node)
                        BanInfRefItem.appendChild(InfRefInd)
        #    <!-- Razón referencia [String(90)] -->
                        InfRefRazRef = doc.createElement("InfRefRazRef")
                        text_node = doc.createTextNode(str(self.origin_ref))
                        InfRefRazRef.appendChild(text_node)
                        BanInfRefItem.appendChild(InfRefRazRef)
        #    <!-- Fecha CFE de referencia [Date] -->
                        InfRefFchRef = doc.createElement("InfRefFchRef")
                        text_node = doc.createTextNode(str(self.origin_date))
                        InfRefFchRef.appendChild(text_node)
                        BanInfRefItem.appendChild(InfRefFchRef)                        
        # if with_invoice:
        # # <!-- Envia documento por mail a cliente S o N [String(1)] -->
        #         BanEnvFactMail = doc.createElement("BanEnvFactMail")
        #         text_node = doc.createTextNode("S")
        #         BanEnvFactMail.appendChild(text_node)
        #         Bandeja.appendChild(BanEnvFactMail) 
        # # <!-- Lista de mails a los que se le envia el documento (separados por ;) [String(400)] -->
        #         BanMailsFact = doc.createElement("BanMailsFact")
        #         text_node = doc.createTextNode(str(self.partner_id.email))
        #         BanMailsFact.appendChild(text_node)
        #         Bandeja.appendChild(BanMailsFact) 

        xmldata = Bandeja.toprettyxml("   ")
        Data = doc.createCDATASection(xmldata)
        Valor.appendChild(Data)
        xmlescape = Xmlentrada.toprettyxml("   ")
        xmlescapedoc = doc.createTextNode(xmlescape)
        entrada.appendChild(xmlescapedoc)
        documentoXML = Envelope.toprettyxml("   ")
        url = self.company_id.url_key
        r = requests.post(
            url=url,
            data=self.scape_value(documentoXML),
            headers={"Content-Type": "text/xml"},
            verify=False,
        )
        self.txt_send = self.scape_value(documentoXML)
        self.txt_rquest = r.text
        if len(r.text.split("Resultado")) != 1:
                error = r.text.split("Resultado")[1].split(";")[1].split("&")[0]
                details = r.text.split("Descripcion")[1].split(";")[1].split("&")[0]
                if error == "1":
                        tpo_cfe = r.text.split("TipoCFE")[1].split(";")[1].split("&")[0]
                        serie_cfe = r.text.split("Serie")[1].split(";")[1].split("&")[0]
                        hashcfe = r.text.split("hashcfe")[1].split(";")[1].split("&")[0]
                        FchVenc = r.text.split("FchVenc")[1].split(";")[1].split("&")[0]
                        nrocae = r.text.split("nrocae")[1].split(";")[1].split("&")[0]
                        comprobantecfe = r.text.split("comprobantecfe")[1].split(";")[1].split("&")[0]
                        
                        self.serie_cfe = serie_cfe
                        self.tpo_cfe = tpo_cfe
                        self.error_dgi = error
                        self.description_dgi = details
                        self.hashcfe = hashcfe
                        self.FchVenc = FchVenc
                        self.nrocae = nrocae
                        self.comprobantecfe = comprobantecfe
                        self.action_invoice_open()
                else:
                        self.error_dgi = error
                        self.description_dgi = details
        else:
                self.error_dgi = "19"
                self.description_dgi = "Error de conexión con web service"
 