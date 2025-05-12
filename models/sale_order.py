from odoo import models, fields, api
from datetime import date

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    service_frequency = fields.Char(string='Frecuencia del Servicio')
    residue_new = fields.Boolean(string='¿Residuo Nuevo?')
    requiere_visita = fields.Boolean(string='Requiere visita presencial')
    pickup_location = fields.Char(string='Ubicación de recolección')

    # Nuevo campo de expiración, por defecto 31-dic del año actual
    expiration_date = fields.Date(
        string='Fecha de Expiración',
        default=lambda self: date(date.today().year, 12, 31)
    )

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
                # Nota: expiration_date ya viene con default, no es necesario sobrescribir
            })
            # Genera líneas de pedido desde crm.lead.residue
            lines = []
            for res in lead.residue_line_ids:
                # 1) Línea de nota que preserva la descripción original
                lines.append((0, 0, {
                    'display_type': 'line_note',
                    'name': res.name,
                }))
                # 2) Línea de producto con descripción inicial
                lines.append((0, 0, {
                    'name': res.name,
                    'product_uom_qty': res.volume,
                    'product_uom': res.uom_id.id,
                    'residue_type': res.residue_type,
                }))
            if lines:
                order.write({'order_line': lines})
        return order
