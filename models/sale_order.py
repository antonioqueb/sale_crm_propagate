# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # CAMPOS (CRM -> SALE)
    # -------------------------------------------------------------------------
    service_frequency = fields.Char(string='Frecuencia del Servicio')
    residue_new = fields.Boolean(string='¿Residuo Nuevo?')
    requiere_visita = fields.Boolean(string='Requiere visita presencial')

    # CAMBIO: de Char a Many2one (selección real como CRM)
    pickup_location_id = fields.Many2one(
        'res.partner',
        string='Ubicación de recolección',
        ondelete='set null',
        help='Contacto/dirección seleccionada para la recolección.'
    )
    pickup_location_manual = fields.Boolean(
        string='Ubicación de recolección (manual)',
        default=False,
        copy=False,
        help='Si está activo, no se sobrescribe automáticamente con la dirección del cliente.'
    )

    # CAMBIO: Destino final ahora solo selección (Many2one), ya no texto
    final_destination_id = fields.Many2one(
        'res.partner',
        string='Destino final',
        ondelete='set null',
        help='Contacto/dirección seleccionada como destino final.'
    )
    final_destination_manual = fields.Boolean(
        string='Destino final (manual)',
        default=False,
        copy=False,
        help='Si está activo, no se sobrescribe automáticamente con el valor del CRM.'
    )

    expiration_date = fields.Date(
        string='Fecha de Expiración',
        default=lambda self: date(date.today().year, 12, 31)
    )

    no_delivery = fields.Boolean(
        string='No generar entrega',
        default=False,
        help='Si está marcado, al confirmar la orden NO se crearán ni procesarán albaranes de entrega.'
    )

    always_service = fields.Boolean(
        string='Siempre Servicios de Residuos',
        default=True,
        help='Cuando está marcado, las líneas se configuran por defecto para servicios de residuos'
    )

    related_quotation_id = fields.Many2one(
        'sale.order',
        string='Cotización Relacionada',
        help='Referencia a una cotización anterior para el mismo cliente. Útil cuando se agregan nuevos tipos de residuos.',
        domain="[('partner_id', '=', partner_id), ('id', '!=', id)]"
    )

    child_quotations_ids = fields.One2many(
        'sale.order',
        'related_quotation_id',
        string='Cotizaciones Derivadas',
        help='Cotizaciones posteriores que referencian a esta cotización'
    )

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

    # -------------------------------------------------------------------------
    # HELPERS: FORMATO DIRECCIÓN EN UNA LÍNEA (solo para display / reportes)
    # -------------------------------------------------------------------------
    def _format_partner_address_one_line(self, partner):
        """
        Devuelve la dirección del partner en una sola línea.
        Usa _display_address() (estándar) y colapsa saltos de línea.
        """
        if not partner:
            return False
        addr = (partner._display_address() or '').strip()
        parts = [p.strip().strip(',') for p in addr.splitlines() if p.strip()]
        return ', '.join(parts) if parts else (partner.name or False)

    # -------------------------------------------------------------------------
    # HELPERS: AUTOFILL pickup_location_id desde partner_shipping_id/partner_id
    # -------------------------------------------------------------------------
    def _autofill_pickup_location(self, force=False):
        """
        Si pickup_location_id está vacío (o force=True) y no es manual,
        rellena con partner_shipping_id si existe, si no partner_id.
        """
        if self.env.context.get('skip_pickup_autofill'):
            return

        for order in self:
            if order.pickup_location_manual:
                continue
            if (not force) and order.pickup_location_id:
                continue

            partner = order.partner_shipping_id or order.partner_id
            if partner and partner.id != (order.pickup_location_id.id if order.pickup_location_id else False):
                order.with_context(skip_pickup_autofill=True).write({
                    'pickup_location_id': partner.id,
                    'pickup_location_manual': False,
                })

    @api.onchange('partner_id', 'partner_shipping_id')
    def _onchange_partner_autofill_pickup_location(self):
        """
        En pantalla: si NO es manual, sincroniza pickup_location_id con partner_shipping/partner.
        """
        for order in self:
            if not order.pickup_location_manual:
                order.pickup_location_id = order.partner_shipping_id or order.partner_id

    # -------------------------------------------------------------------------
    # COMPUTES / ACTIONS
    # -------------------------------------------------------------------------
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

                # CAMBIO: defaults como Many2one (selección real)
                'default_pickup_location_id': self.pickup_location_id.id if self.pickup_location_id else False,
                'default_final_destination_id': self.final_destination_id.id if self.final_destination_id else False,

                'default_company_size': self.company_size,
                'default_industrial_sector': self.industrial_sector,
                'default_prospect_priority': self.prospect_priority,
                'default_always_service': True,
            }
        }

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrescritura de create para manejar la propagación de datos desde CRM.
        Utiliza api.model_create_multi para soportar la creación por lotes (estándar Odoo 19).
        """
        orders = super().create(vals_list)

        for order, vals in zip(orders, vals_list):
            opportunity_id = vals.get('opportunity_id') or self.env.context.get('default_opportunity_id')
            if not opportunity_id:
                continue

            lead = self.env['crm.lead'].browse(opportunity_id)

            # -----------------------------
            # Pickup desde CRM (Many2one)
            # -----------------------------
            lead_pickup = getattr(lead, 'pickup_location_id', False)
            pickup_partner_id = lead_pickup.id if lead_pickup else False

            # -----------------------------
            # Destino final desde CRM (Many2one)
            # -----------------------------
            lead_final_dest = getattr(lead, 'final_destination_id', False)
            final_dest_partner_id = lead_final_dest.id if lead_final_dest else False

            update_vals = {
                'service_frequency': getattr(lead, 'service_frequency', False),
                'residue_new': getattr(lead, 'residue_new', False),
                'requiere_visita': getattr(lead, 'requiere_visita', False),

                # CAMBIO: guardar selección real
                'pickup_location_id': pickup_partner_id,
                'pickup_location_manual': bool(pickup_partner_id),

                'final_destination_id': final_dest_partner_id,
                'final_destination_manual': bool(final_dest_partner_id),

                'always_service': True,

                # INFORMACIÓN BÁSICA DEL PROSPECTO
                'company_size': getattr(lead, 'company_size', False),
                'industrial_sector': getattr(lead, 'industrial_sector', False),
                'prospect_priority': getattr(lead, 'prospect_priority', False),
                'estimated_business_potential': getattr(lead, 'estimated_business_potential', 0.0),

                # INFORMACIÓN OPERATIVA
                'access_restrictions': getattr(lead, 'access_restrictions', False),
                'allowed_collection_schedules': getattr(lead, 'allowed_collection_schedules', False),
                'current_container_types': getattr(lead, 'current_container_types', False),
                'special_handling_conditions': getattr(lead, 'special_handling_conditions', False),
                'seasonality': getattr(lead, 'seasonality', False),

                # INFORMACIÓN REGULATORIA
                'waste_generator_registration': getattr(lead, 'waste_generator_registration', False),
                'environmental_authorizations': getattr(lead, 'environmental_authorizations', False),
                'quality_certifications': getattr(lead, 'quality_certifications', False),
                'other_relevant_permits': getattr(lead, 'other_relevant_permits', False),

                # COMPETENCIA Y MERCADO
                'current_service_provider': getattr(lead, 'current_service_provider', False),
                'current_costs': getattr(lead, 'current_costs', 0.0),
                'current_provider_satisfaction': getattr(lead, 'current_provider_satisfaction', False),
                'reason_for_new_provider': getattr(lead, 'reason_for_new_provider', False),

                # REQUERIMIENTOS ESPECIALES
                'specific_certificates_needed': getattr(lead, 'specific_certificates_needed', False),
                'reporting_requirements': getattr(lead, 'reporting_requirements', False),
                'service_urgency': getattr(lead, 'service_urgency', False),
                'estimated_budget': getattr(lead, 'estimated_budget', 0.0),

                # CAMPOS DE SEGUIMIENTO
                'next_contact_date': getattr(lead, 'next_contact_date', False),
                'pending_actions': getattr(lead, 'pending_actions', False),
                'conversation_notes': getattr(lead, 'conversation_notes', False),
            }

            # Preparar líneas si hay residuos en el lead
            lines = []
            for res in getattr(lead, 'residue_line_ids', self.env['crm.lead.residue']):
                product_id = res.product_id.id if res.product_id else False
                product_name = res.product_id.name if res.product_id else res.name

                # Protección contra duplicados (servicio)
                is_new_service = res.create_new_service
                existing_srv_id = res.existing_service_id.id if res.existing_service_id else False
                if product_id:
                    is_new_service = False
                    existing_srv_id = product_id

                # Protección contra duplicados (embalaje)
                packaging_id = res.packaging_id.id if res.packaging_id else False
                is_new_packaging = res.create_new_packaging
                packaging_name_val = res.packaging_name
                if packaging_id:
                    is_new_packaging = False
                    packaging_name_val = False

                line_data = {
                    'product_id': product_id,
                    'name': product_name or 'Nuevo Servicio',
                    'product_uom_qty': res.volume,

                    # Lógica servicio
                    'create_new_service': is_new_service,
                    'existing_service_id': existing_srv_id,

                    'residue_name': res.name,
                    'residue_type': res.residue_type,
                    'plan_manejo': res.plan_manejo,

                    # Lógica embalaje
                    'create_new_packaging': is_new_packaging,
                    'packaging_name': packaging_name_val,
                    'residue_packaging_id': packaging_id,

                    # Medidas
                    'residue_capacity': res.capacity,
                    'residue_weight_kg': res.weight_kg,
                    'residue_volume': res.volume,
                    'weight_per_unit': res.weight_per_unit,
                    'residue_uom_id': res.uom_id.id if res.uom_id else False,
                }

                # UoM de la línea de venta
                if res.uom_id:
                    line_data['product_uom_id'] = res.uom_id.id
                elif res.product_id and res.product_id.uom_id:
                    line_data['product_uom_id'] = res.product_id.uom_id.id

                lines.append((0, 0, line_data))

            if lines:
                update_vals['order_line'] = lines

            order.write(update_vals)

        # Asegurar autofill cuando NO venga del lead o venga vacío (si pickup_location_manual=True no se toca)
        orders._autofill_pickup_location(force=False)

        return orders

    def write(self, vals):
        """
        - Si el usuario edita pickup_location_id, lo marcamos como manual.
        - Si el usuario edita final_destination_id, lo marcamos como manual.
        - Si cambian partner_id/partner_shipping_id y NO es manual, re-llenamos pickup_location_id.
        """
        if self.env.context.get('skip_pickup_autofill'):
            return super().write(vals)

        # Marcar manual si se editan explícitamente (Many2one)
        if 'pickup_location_id' in vals:
            vals['pickup_location_manual'] = bool(vals.get('pickup_location_id'))

        if 'final_destination_id' in vals:
            vals['final_destination_manual'] = bool(vals.get('final_destination_id'))

        res = super().write(vals)

        # Re-llenar pickup_location_id si cambió partner/shipping y no es manual
        if 'pickup_location_id' not in vals and any(k in vals for k in ('partner_id', 'partner_shipping_id')):
            self._autofill_pickup_location(force=True)
        else:
            self._autofill_pickup_location(force=False)

        return res

    def action_confirm(self):
        """Si no_delivery=True, cancela todos los albaranes tras confirmar."""
        res = super().action_confirm()
        for order in self:
            if order.no_delivery:
                for picking in order.picking_ids:
                    picking.action_cancel()
        return res
