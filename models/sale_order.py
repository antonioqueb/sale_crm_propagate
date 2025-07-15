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

    no_delivery = fields.Boolean(
        string='No generar entrega',
        default=False,
        help='Si está marcado, al confirmar la orden NO se crearán ni procesarán albaranes de entrega.'
    )

    # NUEVO: Campo booleano para controlar si siempre es servicio
    always_service = fields.Boolean(
        string='Siempre Servicios de Residuos',
        default=True,
        help='Cuando está marcado, las líneas se configuran por defecto para servicios de residuos'
    )

    # NUEVO CAMPO: Referencia a cotización anterior
    related_quotation_id = fields.Many2one(
        'sale.order',
        string='Cotización Relacionada',
        help='Referencia a una cotización anterior para el mismo cliente. Útil cuando se agregan nuevos tipos de residuos.',
        domain="[('partner_id', '=', partner_id), ('id', '!=', id)]"
    )
    
    # Campo computado para mostrar cotizaciones relacionadas (hijas)
    child_quotations_ids = fields.One2many(
        'sale.order',
        'related_quotation_id',
        string='Cotizaciones Derivadas',
        help='Cotizaciones posteriores que referencian a esta cotización'
    )
    
    # Contador de cotizaciones relacionadas
    child_quotations_count = fields.Integer(
        string='Cotizaciones Derivadas',
        compute='_compute_child_quotations_count'
    )

    # INFORMACIÓN BÁSICA DEL PROSPECTO
    company_size = fields.Selection([
        ('micro', 'Micro'),
        ('pequena', 'Pequeña'),
        ('mediana', 'Mediana'),
        ('grande', 'Grande')
    ], string="Tamaño de Empresa")
    
    industrial_sector = fields.Char(string="Giro Industrial/Actividad Económica")
    
    # ORIGEN Y CLASIFICACIÓN COMERCIAL
    prospect_priority = fields.Selection([
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
        ('estrategico', 'Estratégico')
    ], string="Prioridad del Prospecto")
    
    estimated_business_potential = fields.Float(string="Potencial Estimado de Negocio")
    
    # INFORMACIÓN OPERATIVA
    access_restrictions = fields.Text(string="Restricciones de Acceso")
    allowed_collection_schedules = fields.Text(string="Horarios Permitidos para Recolección")
    current_container_types = fields.Text(string="Tipo de Contenedores Actuales")
    special_handling_conditions = fields.Text(string="Condiciones Especiales de Manejo")
    seasonality = fields.Text(string="Estacionalidad")
    
    # INFORMACIÓN REGULATORIA
    waste_generator_registration = fields.Char(string="Registro como Generador de Residuos")
    environmental_authorizations = fields.Text(string="Autorizaciones Ambientales Vigentes")
    quality_certifications = fields.Text(string="Certificaciones de Calidad")
    other_relevant_permits = fields.Text(string="Otros Permisos Relevantes")
    
    # COMPETENCIA Y MERCADO
    current_service_provider = fields.Char(string="Proveedor Actual de Servicios")
    current_costs = fields.Float(string="Costos Actuales")
    current_provider_satisfaction = fields.Selection([
        ('muy_bajo', 'Muy Bajo'),
        ('bajo', 'Bajo'),
        ('medio', 'Medio'),
        ('alto', 'Alto'),
        ('muy_alto', 'Muy Alto')
    ], string="Nivel de Satisfacción con Proveedor Actual")
    
    reason_for_new_provider = fields.Text(string="Motivo de Búsqueda de Nuevo Proveedor")
    
    # REQUERIMIENTOS ESPECIALES
    specific_certificates_needed = fields.Text(string="Necesidad de Certificados Específicos")
    reporting_requirements = fields.Text(string="Requerimientos de Reporteo")
    service_urgency = fields.Selection([
        ('inmediata', 'Inmediata'),
        ('1_semana', '1 Semana'),
        ('1_mes', '1 Mes'),
        ('3_meses', '3 Meses'),
        ('sin_prisa', 'Sin Prisa')
    ], string="Urgencia del Servicio")
    
    estimated_budget = fields.Float(string="Presupuesto Estimado")
    
    # CAMPOS DE SEGUIMIENTO
    next_contact_date = fields.Datetime(string="Fecha de Próximo Contacto")
    pending_actions = fields.Text(string="Acciones Pendientes")
    conversation_notes = fields.Text(string="Notas de Conversaciones")

    @api.depends('child_quotations_ids')
    def _compute_child_quotations_count(self):
        for record in self:
            record.child_quotations_count = len(record.child_quotations_ids)

    def action_view_child_quotations(self):
        """Acción para ver las cotizaciones derivadas"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Cotizaciones Derivadas de {self.name}',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('related_quotation_id', '=', self.id)],
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_related_quotation_id': self.id,
            }
        }

    def action_create_related_quotation(self):
        """Acción para crear una nueva cotización relacionada"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Nueva Cotización para {self.partner_id.name}',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_related_quotation_id': self.id,
                'default_service_frequency': self.service_frequency,
                'default_pickup_location': self.pickup_location,
                'default_company_size': self.company_size,
                'default_industrial_sector': self.industrial_sector,
                'default_prospect_priority': self.prospect_priority,
                'default_always_service': True,
            }
        }

    @api.model
    def create(self, vals):
        # Crea primero la orden
        order = super().create(vals)
        # Si viene de CRM, copiamos los datos
        opportunity_id = vals.get('opportunity_id') or self.env.context.get('default_opportunity_id')
        if opportunity_id:
            lead = self.env['crm.lead'].browse(opportunity_id)
            order.write({
                'service_frequency': lead.service_frequency,
                'residue_new': lead.residue_new,
                'requiere_visita': lead.requiere_visita,
                'pickup_location': lead.pickup_location,
                'always_service': True,  # Siempre true cuando viene de CRM
                # INFORMACIÓN BÁSICA DEL PROSPECTO
                'company_size': lead.company_size,
                'industrial_sector': lead.industrial_sector,
                'prospect_priority': lead.prospect_priority,
                'estimated_business_potential': lead.estimated_business_potential,
                # INFORMACIÓN OPERATIVA
                'access_restrictions': lead.access_restrictions,
                'allowed_collection_schedules': lead.allowed_collection_schedules,
                'current_container_types': lead.current_container_types,
                'special_handling_conditions': lead.special_handling_conditions,
                'seasonality': lead.seasonality,
                # INFORMACIÓN REGULATORIA
                'waste_generator_registration': lead.waste_generator_registration,
                'environmental_authorizations': lead.environmental_authorizations,
                'quality_certifications': lead.quality_certifications,
                'other_relevant_permits': lead.other_relevant_permits,
                # COMPETENCIA Y MERCADO
                'current_service_provider': lead.current_service_provider,
                'current_costs': lead.current_costs,
                'current_provider_satisfaction': lead.current_provider_satisfaction,
                'reason_for_new_provider': lead.reason_for_new_provider,
                # REQUERIMIENTOS ESPECIALES
                'specific_certificates_needed': lead.specific_certificates_needed,
                'reporting_requirements': lead.reporting_requirements,
                'service_urgency': lead.service_urgency,
                'estimated_budget': lead.estimated_budget,
                # CAMPOS DE SEGUIMIENTO
                'next_contact_date': lead.next_contact_date,
                'pending_actions': lead.pending_actions,
                'conversation_notes': lead.conversation_notes,
            })
            
            # Crear líneas solo con servicios creados
            lines = []
            for res in lead.residue_line_ids:
                if hasattr(res, 'product_id') and res.product_id:
                    lines.append((0, 0, {
                        'product_id': res.product_id.id,
                        'name': res.product_id.name,
                        'product_uom_qty': res.volume,
                        'product_uom': res.uom_id.id,
                        'residue_type': res.residue_type,
                        'plan_manejo': res.plan_manejo,
                        'create_new_service': res.create_new_service,
                        'residue_name': res.name,
                        'residue_volume': res.volume,
                        'residue_uom_id': res.uom_id.id,
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
                    picking.action_cancel()
        return res