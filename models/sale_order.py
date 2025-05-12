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

    # Flag global para controlar si debe generar entrega
    no_delivery = fields.Boolean(
        string='No generar entrega',
        default=False,
        help='Si está marcado, al confirmar la orden NO se crearán ni procesarán albaranes de entrega.'
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
                # 1) Línea de nota
                lines.append((0, 0, {
                    'display_type': 'line_note',
                    'name': res.name,
                }))
                # 2) Línea de producto (residuo)
                lines.append((0, 0, {
                    'name': res.name,
                    'product_uom_qty': res.volume,
                    'product_uom': res.uom_id.id,
                    'residue_type': res.residue_type,
                }))
            if lines:
                order.write({'order_line': lines})
        return order

    def action_confirm(self):
        """Si no_delivery=True, cancela todos los albaranes tras confirmar."""
        res = super().action_confirm()
        for order in self:
            if order.no_delivery:
                for picking in order.picking_ids:
                    # cancelar el picking y sus movimientos
                    picking.action_cancel()
        return res
