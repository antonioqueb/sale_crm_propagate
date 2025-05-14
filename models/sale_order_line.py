from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    residue_type = fields.Selection(
        [('rsu', 'RSU'), ('rme', 'RME'), ('rp', 'RP')],
        string='Tipo de manejo'
    )
        # NUEVAS COLUMNAS CRETIBM
    c = fields.Boolean(string="C")
    r = fields.Boolean(string="R")
    e = fields.Boolean(string="E")
    t = fields.Boolean(string="T")
    i = fields.Boolean(string="I")
    b = fields.Boolean(string="B")
    m = fields.Boolean(string="M")
