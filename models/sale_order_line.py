from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    residue_type = fields.Selection(
        [('rsu', 'RSU'), ('rme', 'RME'), ('rp', 'RP')],
        string='Tipo de manejo'
    )
    no_delivery = fields.Boolean(
        string='No generar entrega',
        help='Para líneas de residuos, cancelar movimientos de stock al confirmar.'
    )

    @api.onchange('residue_type')
    def _onchange_residue_type(self):
        # si es línea de residuo, marcar no_delivery
        for line in self:
            line.no_delivery = bool(line.residue_type)
