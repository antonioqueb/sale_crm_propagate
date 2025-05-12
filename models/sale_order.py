from odoo import models, fields, api
from datetime import date

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    service_frequency = fields.Char(string='Frecuencia del Servicio')
    residue_new = fields.Boolean(string='¿Residuo Nuevo?')
    requiere_visita = fields.Boolean(string='Requiere visita presencial')
    pickup_location = fields.Char(string='Ubicación de recolección')

    expiration_date = fields.Date(
        string='Fecha de Expiración',
        default=lambda self: date(date.today().year, 12, 31)
    )

    @api.model
    def create(self, vals):
        opportunity_id = vals.get('opportunity_id') or self.env.context.get('default_opportunity_id')
        order = super().create(vals)
        if opportunity_id:
            lead = self.env['crm.lead'].browse(opportunity_id)
            order.write({
                'service_frequency': lead.service_frequency,
                'residue_new': lead.residue_new,
                'requiere_visita': lead.requiere_visita,
                'pickup_location': lead.pickup_location,
            })
            lines = []
            for res in lead.residue_line_ids:
                # 1) nota
                lines.append((0, 0, {
                    'display_type': 'line_note',
                    'name': res.name,
                }))
                # 2) línea de producto (residuo)
                lines.append((0, 0, {
                    'name': res.name,
                    'product_uom_qty': res.volume,
                    'product_uom': res.uom_id.id,
                    'residue_type': res.residue_type,
                    'no_delivery': True,        # marcar para no entrega
                }))
            if lines:
                order.write({'order_line': lines})
        return order

    def action_confirm(self):
        """Al confirmar, cancela cualquier movimiento asociado a líneas no_delivery."""
        res = super().action_confirm()
        for order in self:
            for picking in order.picking_ids:
                # cancelar moves de líneas no_delivery
                moves_cancel = picking.move_lines.filtered(lambda m: m.sale_line_id.no_delivery)
                if moves_cancel:
                    moves_cancel._action_cancel()
                # si no quedan moves activos, cancelar el picking
                remain = picking.move_lines.filtered(lambda m: not m.sale_line_id.no_delivery)
                if not remain:
                    picking.button_cancel()
        return res
