from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    service_frequency = fields.Char(string='Frecuencia del Servicio')
    residue_new = fields.Boolean(string='¿Residuo Nuevo?')
    requiere_visita = fields.Boolean(string='Requiere visita presencial')
    pickup_location = fields.Char(string='Ubicación de recolección')

    @api.model
    def create(self, vals):
        # Detecta si proviene de una oportunidad (lead)
        opportunity_id = vals.get('opportunity_id') or self.env.context.get('default_opportunity_id')
        order = super().create(vals)
        if opportunity_id:
            lead = self.env['crm.lead'].browse(opportunity_id)
            # Copia campos simples
            order.write({
                'service_frequency': lead.service_frequency,
                'residue_new': lead.residue_new,
                'requiere_visita': lead.requiere_visita,
                'pickup_location': lead.pickup_location,
            })
            # Genera líneas de pedido desde crm.lead.residue
            lines = []
            for res in lead.residue_line_ids:
                lines.append((0, 0, {
                    'name': res.name,
                    'product_uom_qty': res.volume,
                    'product_uom': res.uom_id.id,
                    'residue_type': res.residue_type,
                }))
            if lines:
                order.write({'order_line': lines})
        return order
