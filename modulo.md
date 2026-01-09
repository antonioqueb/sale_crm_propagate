## ./__init__.py
```py
from . import models
```

## ./__manifest__.py
```py
{
    'name': 'CRM to Sale Propagate',
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Propaga campos y líneas de residuos de CRM a cotizaciones',
    'author': 'Alphaqueb Consulting',
    'depends': ['crm_custom_fields', 'sale'],
    'data': [
        'views/sale_order_view.xml',
        'reports/sale_order_report_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}```

## ./models/__init__.py
```py
from . import sale_order
from . import sale_order_line
```

## ./models/sale_order_line.py
```py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _get_or_create_service_uom(self):
        """Busca o crea la UoM 'Unidad de servicio'."""
        UoM = self.env['uom.uom'].sudo()
        unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)

        # 1) Buscar existente
        service_uom = UoM.search([('name', '=ilike', 'Unidad de servicio')], limit=1)
        if not service_uom:
            service_uom = UoM.search([('name', 'ilike', 'Unidad de servicio')], limit=1)
        if service_uom:
            return service_uom

        # 2) Crear por copia de "Unidades"
        if not unit:
            return False

        vals = {'name': 'Unidad de servicio'}
        candidates = [
            'category_id', 'uom_type', 'factor', 'factor_inv', 
            'ratio', 'ratio_inv', 'rounding', 'active', 'relative_uom_id'
        ]
        for f in candidates:
            if f in unit._fields:
                vals[f] = unit[f]

        if 'active' in UoM._fields:
            vals['active'] = True

        try:
            return UoM.create(vals)
        except Exception:
            return unit

    def _create_or_update_packaging_v19(self, record):
        """Crea una UdM para embalaje si es necesario."""
        if not record.create_new_packaging or not record.packaging_name:
            return

        UoM = self.env['uom.uom'].sudo()
        existing = UoM.search([('name', '=', record.packaging_name)], limit=1)
        if existing:
            record.residue_packaging_id = existing.id
            return

        unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        vals = {'name': record.packaging_name}

        if unit:
            for f in ['category_id', 'uom_type', 'rounding', 'active', 'relative_uom_id', 'factor', 'factor_inv', 'ratio', 'ratio_inv']:
                if f in unit._fields and f in UoM._fields:
                    vals[f] = unit[f]

        qty = record.residue_volume or 1.0
        if 'factor' in UoM._fields:
            vals['factor'] = (1.0 / qty) if qty else 1.0
        elif 'ratio' in UoM._fields:
            vals['ratio'] = (1.0 / qty) if qty else 1.0

        if 'active' in UoM._fields:
            vals['active'] = True

        try:
            new_uom = UoM.create(vals)
            record.residue_packaging_id = new_uom.id
        except Exception as e:
            _logger.exception("Error creando embalaje. vals=%s", vals)

    def _create_service_product(self):
        """
        Crea el producto real basado en los datos de la línea.
        Eliminado ensure_one() para soportar creación en onchange (NewId).
        """
        # Validación mínima
        if not (self.create_new_service and self.residue_name):
            return None

        # Evitar crear duplicados si ya tengo un product_id con el mismo nombre
        if self.product_id and self.product_id.name == self.residue_name:
            return self.product_id

        Category = self.env['product.category'].sudo()
        Product = self.env['product.product'].sudo()

        category = Category.search([('name', 'ilike', 'servicios de residuos')], limit=1)
        if not category:
            category = Category.create({'name': 'Servicios de Residuos'})

        service_uom = self._get_or_create_service_uom()
        
        # MODIFICACIÓN: Ya no generamos la descripción larga con Plan/Tipo/Capacidad.
        # desc = f"Residuo: {self.residue_name}\nPlan: {plan_label}\nTipo: {type_label}..."

        vals = {
            'name': self.residue_name,
            'type': 'service',
            'categ_id': category.id,
            'sale_ok': True,
            'purchase_ok': False,
            # 'description_sale': desc,  <-- Se omite para que no se guarde en el producto
            'uom_id': service_uom.id if service_uom else False,
        }
        
        # En Odoo 19 es posible que uom_po_id no exista o sea requerido, lo manejamos seguro
        if 'uom_po_id' in Product._fields and service_uom:
             vals['uom_po_id'] = service_uom.id

        safe_vals = {k: v for k, v in vals.items() if k in Product._fields}
        
        try:
            return Product.create(safe_vals)
        except Exception as e:
            _logger.error(f"Error creando producto servicio: {e}")
            return False

    # -------------------------------------------------------------------------
    # CAMPOS
    # -------------------------------------------------------------------------
    residue_type = fields.Selection([('rsu', 'RSU'), ('rme', 'RME'), ('rp', 'RP')], string='Tipo de manejo')
    
    plan_manejo = fields.Selection([
        ('reciclaje', 'Reciclaje'),
        ('aprovechamiento_energetico', 'Aprovechamiento Energético'),
        ('relleno_sanitario', 'Relleno Sanitario'),
        ('coprocesamiento', 'Co-procesamiento'),
        ('tratamiento_fisicoquimico', 'Tratamiento Físico-Químico'),
        ('tratamiento_biologico', 'Tratamiento Biológico'),
        ('tratamiento_termico', 'Tratamiento Térmico'),
        ('confinamiento_controlado', 'Confinamiento Controlado'),
        ('reutilizacion', 'Reutilización'),
        ('destruccion_fiscal', 'Destrucción Fiscal'),
    ], string="Plan de Manejo")

    create_new_service = fields.Boolean(string="¿Nuevo Servicio?", default=False)
    existing_service_id = fields.Many2one('product.product', string="Servicio Existente", domain="[('type', '=', 'service'), ('sale_ok', '=', True)]")
    residue_name = fields.Char(string="Nombre del Residuo")

    create_new_packaging = fields.Boolean(string="¿Nuevo Embalaje?", default=False)
    packaging_name = fields.Char(string="Nombre Nuevo Embalaje")
    residue_packaging_id = fields.Many2one('uom.uom', string="Embalaje Existente")

    residue_capacity = fields.Char(string='Capacidad')
    residue_weight_kg = fields.Float(string="Peso Total (kg)", default=0.0)
    residue_volume = fields.Float(string="Unidades", default=1.0)
    
    weight_per_unit = fields.Float(string="Kg por Unidad", compute="_compute_weight_per_unit", store=True)
    
    residue_uom_id = fields.Many2one('uom.uom', string="Unidad de Medida Base", default=lambda self: self._get_or_create_service_uom())

    # -------------------------------------------------------------------------
    # ONCHANGES & LOGIC
    # -------------------------------------------------------------------------
    @api.depends('residue_volume', 'residue_weight_kg')
    def _compute_weight_per_unit(self):
        for record in self:
            record.weight_per_unit = (record.residue_weight_kg / record.residue_volume) if record.residue_volume else 0.0

    @api.onchange('create_new_service')
    def _onchange_create_new_service(self):
        if self.create_new_service:
            self.existing_service_id = False
            self.product_id = False
            # Asegurar UoM base
            if not self.residue_uom_id:
                self.residue_uom_id = self._get_or_create_service_uom()
            # Sincronizar UoM del producto
            self.product_uom_id = self.residue_uom_id
        else:
            if not self.existing_service_id:
                self.product_id = False

    @api.onchange('create_new_packaging')
    def _onchange_create_new_packaging(self):
        if self.create_new_packaging:
            self.residue_packaging_id = False
        else:
            self.packaging_name = False

    @api.onchange('existing_service_id')
    def _onchange_existing_service_id(self):
        if self.existing_service_id and not self.create_new_service:
            service = self.existing_service_id
            self.product_id = service.id
            self.product_template_id = service.product_tmpl_id.id
            
            # MODIFICACIÓN: Usar SOLO el nombre del servicio, ignorando description_sale
            self.name = service.name
            
            self.residue_name = service.name
            
            uom = self._get_or_create_service_uom()
            self.residue_uom_id = uom
            # SIEMPRE usar la UoM del servicio, no del embalaje
            self.product_uom_id = uom

            self.create_new_packaging = False
            self.packaging_name = False
            self.residue_packaging_id = False

    @api.onchange('residue_packaging_id')
    def _onchange_residue_packaging(self):
        """
        CORRECCIÓN: Ya NO sobrescribimos product_uom_id con el embalaje.
        Solo almacenamos el embalaje en su campo.
        """
        pass
    
    @api.onchange('residue_uom_id')
    def _onchange_residue_uom(self):
        """
        Si cambia la UoM del residuo, actualizamos la del producto.
        """
        if self.residue_uom_id:
            self.product_uom_id = self.residue_uom_id

    @api.onchange('residue_name', 'plan_manejo', 'residue_type', 'residue_capacity')
    def _onchange_residue_fields(self):
        """
        Crea el producto 'al vuelo' cuando el usuario llena los datos mínimos.
        """
        if self.create_new_service and self.residue_name:
            # Crear el producto inmediatamente
            new_product = self._create_service_product()
            if new_product:
                self.product_id = new_product.id
                
                # MODIFICACIÓN: Usar SOLO el nombre, sin description_sale
                self.name = new_product.name
                
                # Usar la UoM del nuevo producto (que es 'Unidad de servicio')
                if new_product.uom_id:
                    self.product_uom_id = new_product.uom_id
                elif self.residue_uom_id:
                     self.product_uom_id = self.residue_uom_id

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        uom_service = self._get_or_create_service_uom()
        for vals in vals_list:
            if not vals.get('residue_uom_id') and uom_service:
                vals['residue_uom_id'] = uom_service.id
            
            # Asegurar que product_uom_id sea la del servicio, NO la del embalaje
            if not vals.get('product_uom_id') and uom_service:
                vals['product_uom_id'] = uom_service.id

        lines = super().create(vals_list)

        for line in lines:
            # 1. Crear Embalaje si hace falta
            if line.create_new_packaging and line.packaging_name:
                line._create_or_update_packaging_v19(line)
            
            # CORRECCIÓN: No sobrescribir product_uom_id con residue_packaging_id
            # El embalaje queda solo en line.residue_packaging_id

            # 2. El servicio generalmente ya se creó en onchange, 
            # pero por seguridad verificamos:
            if line.create_new_service and not line.product_id and line.residue_name:
                service = line._create_service_product()
                if service:
                    line.product_id = service.id
                    line.product_uom_qty = line.residue_volume
                    # MODIFICACIÓN: Asegurar que la descripción de la línea sea solo el nombre
                    line.name = service.name
                    # Aseguramos UoM correcta
                    if service.uom_id:
                        line.product_uom_id = service.uom_id

        return lines

    def write(self, vals):
        res = super().write(vals)
        for line in self:
            # Embalaje
            if 'create_new_packaging' in vals or 'packaging_name' in vals:
                line._create_or_update_packaging_v19(line)
                # CORRECCIÓN: No tocamos product_uom_id aquí

            # Servicio
            if line.create_new_service and line.residue_name and (not line.product_id or line.product_id.name != line.residue_name):
                if not line.product_id:
                     service = line._create_service_product()
                     if service:
                         line.product_id = service.id
                         # MODIFICACIÓN: Asegurar que la descripción sea solo el nombre
                         line.name = service.name
                         # Aseguramos UoM correcta
                         if service.uom_id:
                            line.product_uom_id = service.uom_id
        return res```

## ./models/sale_order.py
```py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    # CAMPOS (CRM -> SALE)
    # -------------------------------------------------------------------------
    

    def _get_service_frequency_selection(self):
        """
        Reutiliza exactamente el selection definido en crm.lead.service_frequency
        (campo definido en tu módulo crm_custom_fields).
        """
        Lead = self.env['crm.lead']
        lead_field = Lead._fields.get('service_frequency')
        if not lead_field or getattr(lead_field, 'type', None) != 'selection':
            return []

        sel = lead_field.selection
        # Puede venir como lista o como callable (método)
        if callable(sel):
            # Normalmente acepta un recordset (aunque esté vacío)
            try:
                return sel(Lead)
            except TypeError:
                # Fallbacks por si tu implementación de CRM usa otra firma
                try:
                    return sel(self.env)
                except Exception:
                    return []
        return sel or []

    service_frequency = fields.Selection(
        selection=lambda self: self._get_service_frequency_selection(),
        string='Frecuencia del Servicio'
    )



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
```

## ./reports/__init__.py
```py
from . import reports
from . import sale_order_report_template
```

## ./reports/sale_order_report_template.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <template id="report_saleorder_document_custom" inherit_id="sale.report_saleorder_document">

        <!-- OCULTAR el bloque superior de dirección -->
        <xpath expr="//t[@t-set='address']" position="replace">
            <t t-set="address" t-value="''"/>
        </xpath>

        <!-- OCULTAR bloque estándar de direcciones -->
        <xpath expr="//t[@t-set='information_block']" position="replace">
            <t/>
        </xpath>

        <!-- Cambiar el título del documento -->
        <xpath expr="//t[@t-set='layout_document_title']" position="replace">
            <t t-set="layout_document_title">
                <span style="font-size: 23px; font-weight: 700;">PROPUESTA TECNICA Y ECONOMICA DE SERVICIOS N°  </span>
                <span t-field="doc.name" style="font-size: 23px; font-weight: 700;">SO0000</span>
            </t>
        </xpath>

        <!-- Agregar descripción personalizada antes de la tabla de líneas -->
        <xpath expr="//div[@class='oe_structure'][2]" position="after">
            <!-- CSS para ocultar columna de impuestos (ahora 5ta) e importe (ahora 6ta) -->
            <style>
                .o_main_table th:nth-child(5),
                .o_main_table td:nth-child(5),
                .o_main_table th:nth-child(6),
                .o_main_table td:nth-child(6) {
                    display: none !important;
                }
            </style>
            <div class="row mt-4 mb-3" style="font-size: 13px; line-height: 1.2;">
                <div class="col-12">
                    <h4 style="font-size: 14px; line-height: 1.2; margin-bottom: 8px;">
                        Servicio de transporte y disposición de residuos para:
                        <span t-field="doc.partner_id.name" style="font-weight: 700;">DIFRENOSA</span>
                    </h4>
                    <p class="text-muted" style="font-size: 12px; line-height: 1.2; margin-bottom: 10px;">Según normatividad aplicable</p>

                    <h5 class="mt-3" style="font-size: 13px; line-height: 1.2; margin-bottom: 8px;">Propuesta Técnica y Económica de Servicios</h5>

                    <h6 class="mt-3" style="font-size: 12px; line-height: 1.2; margin-bottom: 8px;">1.0 ANTECEDENTES</h6>
                    <p style="font-size: 12px; line-height: 1.2; margin-bottom: 10px;">
                        Servicios Ambientales Internacionales, S. de R.L. (SAI) ofrece a
                        <strong><span t-field="doc.partner_id.name">DIFRENOSA</span></strong>
                        sus servicios autorizados de transporte y disposición de residuos. Asimismo, SAI tiene información clara de las
                        especificaciones del cliente necesarias para poder adjudicar y realizar el servicio en forma satisfactoria. SAI
                        tiene el entendimiento siguiente sobre este proyecto:
                    </p>

                    <div style="margin-left: 20px; font-size: 12px; line-height: 1.2;">
                        <p style="margin-bottom: 5px;"><strong>a)</strong> El traslado deberá realizarse en vehículos y operadores autorizados y con los plaques
                        correspondientes según normas aplicables.</p>

                        <p style="margin-bottom: 5px;"><strong>b)</strong> SAI deberá contar con el personal capacitado y el equipo de protección personal necesario para el
                        manejo del residuo.</p>

                        <p style="margin-bottom: 5px;"><strong>c)</strong> SAI podrá proporcionar la documentación para llevar a cabo el embarque.</p>

                        <p style="margin-bottom: 5px;"><strong>d)</strong> SAI declara que cuenta con autorizaciones necesarias de competencia federal y estatal para realizar los
                        servicios.</p>
                    </div>

                    <div class="row mb-5 mt-4 " style="text-align: center; margin-bottom: 20px;">
                        <div class="col-12 mb-5">
                            <img src="/sale_crm_propagate/static/description/frontal.png"
                                 alt="Flota de vehículos especializados"
                                 style="max-width: 100%; height: auto; margin-bottom: 60px; max-height: 420px;"/>
                        </div>
                    </div>
                </div>
            </div>
        </xpath>

        <!-- Agregar información del servicio después de la información de fechas -->
        <xpath expr="//div[@id='informations']" position="after">
            <div class="row mt-3">
                <div class="col-4" t-if="doc.service_frequency">
                    <strong>Frecuencia del Servicio:</strong> <span t-field="doc.service_frequency"/>
                </div>

                <!-- FIX: ya no existe doc.pickup_location (Char). Ahora es Many2one -->
                <div class="col-4" t-if="doc.pickup_location_id">
                    <strong>Ubicación de recolección:</strong>
                    <span t-esc="((doc.pickup_location_id._display_address() or doc.pickup_location_id.name or '').replace('\n', ', '))"/>
                </div>

                <!-- OPCIONAL: Destino final (Many2one). Si no lo quieres, elimina este bloque -->
                <div class="col-4" t-if="doc.final_destination_id">
                    <strong>Destino final:</strong>
                    <span t-esc="((doc.final_destination_id._display_address() or doc.final_destination_id.name or '').replace('\n', ', '))"/>
                </div>
            </div>
        </xpath>

        <!-- Modificar el encabezado de la columna Quantity -->
        <xpath expr="//th[@name='th_quantity']" position="replace">
            <th name="th_quantity" class="text-end text-nowrap">Cantidad</th>
        </xpath>

        <!-- NUEVO: Agregar columna "Capacidad" después de Cantidad -->
        <xpath expr="//th[@name='th_quantity']" position="after">
            <th name="th_capacity" class="text-nowrap">Capacidad</th>
        </xpath>

        <!-- Modificar el contenido de la celda de cantidad -->
        <xpath expr="//td[@name='td_product_quantity']" position="replace">
            <td name="td_product_quantity" class="o_td_quantity text-end text-nowrap">
                <span t-field="line.product_uom_qty">3</span>
                <span t-if="line.residue_packaging_id" t-field="line.residue_packaging_id.name">TOTE</span>
                <span t-else="" t-field="line.product_uom_id">units</span>
            </td>
        </xpath>

        <!-- NUEVO: Celda "Capacidad" después de la celda de cantidad -->
        <xpath expr="//td[@name='td_product_quantity']" position="after">
            <td name="td_capacity" class="text-nowrap">
                <span t-esc="line.residue_capacity or ''"/>
            </td>
        </xpath>

        <!-- OCULTAR campos sensibles en las líneas del reporte -->
        <xpath expr="//span[@t-field='line.name']" position="after">
            <t t-set="hide_internal_fields" t-value="True"/>
        </xpath>

        <!-- OCULTAR SUBTOTAL, IMPUESTOS Y TOTAL -->
        <xpath expr="//div[@id='total']" position="replace">
            <div id="total" style="display: none;"/>
        </xpath>

    </template>
</odoo>
```

## ./views/sale_order_view.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<odoo>
  <record id="view_sale_order_form_crm_fields" model="ir.ui.view">
    <field name="name">sale.order.form.crm.fields</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">

      <!-- =========================================================
           1) PESTAÑAS ADICIONALES
           ========================================================= -->
      
      <xpath expr="//notebook/page[@name='order_lines']" position="after">
        
        <!-- Nueva página: Gestión de Servicios -->
        <page string="Gestión de Servicios" name="service_management">
          
          <!-- Control global de servicios -->
          <group string="Configuración de Servicios">
            <field name="always_service"/>
          </group>

          <!-- Información del Servicio -->
          <group string="Información del Servicio">
            <group>
              <field name="service_frequency"/>

              <!-- CAMBIO: selector real como CRM -->
              <field name="pickup_location_id"
                     widget="res_partner_many2one"
                     context="{
                        'default_parent_id': partner_id,
                        'default_type': 'delivery',
                        'show_address': 1
                     }"
                     domain="['|', ('parent_id', '=', partner_id), ('id', '=', partner_id)]"
                     options="{'always_reload': True, 'no_quick_create': True}"
                     placeholder="Seleccionar ubicación de recolección..."
              />

              <!-- CAMBIO: selector real como CRM -->
              <field name="final_destination_id"
                    widget="res_partner_many2one"
                    context="{
                        'default_parent_id': partner_id,
                        'default_type': 'delivery',
                        'show_address': 1
                    }"
                    domain="[('category_id.name', '=', 'Destino Final')]"
                    options="{'always_reload': True, 'no_quick_create': True}"
                    placeholder="Seleccionar destino final..."
              />


            </group>
            <group>
              <field name="residue_new"/>
              <field name="requiere_visita"/>
            </group>
          </group>

          <!-- Información Básica del Prospecto -->
          <group string="Información Básica del Prospecto">
            <group>
              <field name="company_size"/>
              <field name="industrial_sector"/>
            </group>
            <group>
              <field name="prospect_priority"/>
              <field name="estimated_business_potential"/>
            </group>
          </group>

        </page>

        <page string="Informe General" name="general_report">

          <!-- Información Operativa -->
          <group string="Información Operativa">
            <group>
              <field name="access_restrictions" widget="text"/>
              <field name="allowed_collection_schedules" widget="text"/>
              <field name="current_container_types" widget="text"/>
            </group>
            <group>
              <field name="special_handling_conditions" widget="text"/>
              <field name="seasonality" widget="text"/>
            </group>
          </group>

          <!-- Información Regulatoria -->
          <group string="Información Regulatoria">
            <group>
              <field name="waste_generator_registration"/>
              <field name="environmental_authorizations" widget="text"/>
            </group>
            <group>
              <field name="quality_certifications" widget="text"/>
              <field name="other_relevant_permits" widget="text"/>
            </group>
          </group>

          <!-- Competencia y Mercado -->
          <group string="Competencia y Mercado">
            <group>
              <field name="current_service_provider"/>
              <field name="current_costs"/>
              <field name="current_provider_satisfaction"/>
            </group>
            <group>
              <field name="reason_for_new_provider" widget="text"/>
            </group>
          </group>

          <!-- Requerimientos Especiales -->
          <group string="Requerimientos Especiales">
            <group>
              <field name="specific_certificates_needed" widget="text"/>
              <field name="reporting_requirements" widget="text"/>
            </group>
            <group>
              <field name="service_urgency"/>
              <field name="estimated_budget"/>
            </group>
          </group>

          <!-- Campos de Seguimiento -->
          <group string="Seguimiento">
            <group>
              <field name="next_contact_date"/>
              <field name="pending_actions" widget="text"/>
            </group>
            <group>
              <field name="conversation_notes" widget="text"/>
            </group>
          </group>

        </page>
      </xpath>

      <!-- 2) Pestaña "Cotizaciones Relacionadas" -->
      <xpath expr="//notebook/page[@name='general_report']" position="after">
        <page string="Cotizaciones Relacionadas" name="related_quotations">
          
          <!-- Sección de referencia a cotización anterior -->
          <group string="Referencia">
            <field name="related_quotation_id" 
                   options="{'no_create': True}" 
                   placeholder="Seleccionar cotización anterior para este cliente..."/>
          </group>

          <!-- Botones de acción -->
          <div class="oe_button_box">
            <button type="object" 
                    name="action_view_child_quotations" 
                    class="oe_stat_button" 
                    icon="fa-list-alt"
                    invisible="child_quotations_count == 0">
              <field name="child_quotations_count" widget="statinfo" string="Cotizaciones Derivadas"/>
            </button>
          </div>

          <div class="row mt-3">
            <div class="col-12">
              <button type="object" 
                      name="action_create_related_quotation" 
                      string="Crear Nueva Cotización para este Cliente" 
                      class="btn btn-primary"
                      icon="fa-plus"/>
            </div>
          </div>

          <!-- Información de la cotización relacionada (solo lectura) -->
          <group string="Información de Cotización Relacionada" 
                 invisible="not related_quotation_id">
            <field name="related_quotation_id" invisible="1"/>
            <label for="related_quotation_id" string="Cotización Base:"/>
            <div class="o_row">
              <field name="related_quotation_id" readonly="1" nolabel="1"/>
            </div>
          </group>

          <!-- Lista de cotizaciones derivadas -->
          <group string="Cotizaciones Derivadas de esta Propuesta" 
                 invisible="child_quotations_count == 0">
            <field name="child_quotations_ids" nolabel="1" readonly="1">
              <list>
                <field name="name"/>
                <field name="partner_id"/>
                <field name="date_order"/>
                <field name="state"/>
                <field name="amount_total"/>
              </list>
            </field>
          </group>

        </page>
      </xpath>

      <!-- 3) Campos globales antes de Términos de pago -->
      <xpath expr="//field[@name='date_order']" position="before">
          <field name="expiration_date"/>
      </xpath>

      <!-- 4) Botón en el header -->
      <xpath expr="//header" position="inside">
        <button type="object" 
                name="action_create_related_quotation" 
                string="Nueva Cotización" 
                class="btn btn-secondary"
                invisible="state not in ['draft', 'sent']"
                help="Crear una nueva cotización para este cliente con nuevos residuos"/>
      </xpath>


      <!-- =========================================================
           5) MODIFICACIÓN LISTA DE LÍNEAS (ESTÉTICA CRM + FUNCIONALIDAD)
           ========================================================= -->
      
      <!-- Ocultamos las columnas originales para no borrarlas y perder referencias -->
      <xpath expr="//page[@name='order_lines']//list/field[@name='product_template_id']" position="attributes">
         <attribute name="column_invisible">True</attribute>
      </xpath>
      
      <!-- Ocultamos la descripción original para reinsertarla en nuestra posición deseada -->
      <xpath expr="//page[@name='order_lines']//list/field[@name='name']" position="attributes">
         <attribute name="column_invisible">True</attribute>
      </xpath>

      <!-- Insertamos nuestras columnas personalizadas al inicio -->
      <xpath expr="//page[@name='order_lines']//list/field[@name='product_template_id']" position="before">
        
        <!-- A. Lógica SERVICIO (Toggle y campos condicionales) -->
        <field name="create_new_service" 
               string="Nuevo" 
               widget="boolean_toggle" 
               width="60px"/>
        
        <!-- Opción A1: Escribir nombre (Visible si Nuevo=True) -->
        <field name="residue_name" 
               string="Nombre"
               invisible="not create_new_service"
               required="create_new_service"
               placeholder="Nombre del residuo..."
               width="150px"/>
        
        <!-- Opción A2: Seleccionar existente (Visible si Nuevo=False) -->
        <field name="existing_service_id"
               string="Existente"
               domain="[('sale_ok','=',True), ('type','=','service')]"
               options="{'no_create': True, 'no_open': True}"
               invisible="create_new_service"
               required="not create_new_service"
               placeholder="Buscar servicio..." 
               width="150px"/>
        <!-- D. DESCRIPCIÓN (Recuperada para permitir editar detalles de la partida) -->
        <field name="name" 
               string="Descripción" 
               widget="section_and_note_text" 
               optional="show"/>
        
        <!-- Informativos -->
        <field name="residue_type" string="Tipo" optional="show" width="80px"/>
        <field name="plan_manejo" string="Manejo" optional="show" width="100px"/>

        <!-- B. Lógica EMBALAJE (Toggle y campos condicionales) -->
        <field name="create_new_packaging" 
               string="Nuevo Emb." 
               widget="boolean_toggle"
               width="60px"/>
        
        <!-- Opción B1: Escribir nuevo embalaje (Visible si NuevoEmb=True) -->
        <field name="packaging_name" 
               string="Embalaje" 
               invisible="not create_new_packaging"
               required="create_new_packaging"
               placeholder="Ej: Tambor"
               width="100px"/>
        
        <!-- Opción B2: Seleccionar existente (Visible si NuevoEmb=False) -->
        <field name="residue_packaging_id" 
               string="Emb. Existente" 
               options="{'no_create': True}"
               invisible="create_new_packaging"
               required="not create_new_packaging"
               placeholder="Selec..."
               width="100px"/>

        <!-- C. Medidas y Totales -->
        <field name="residue_capacity" string="Capacidad" width="70px"/>
        <field name="residue_weight_kg" string="Peso(kg)" width="70px"/>
        <field name="residue_volume" string="Uds" width="70px" column_invisible="True"/>
        <field name="weight_per_unit" string="Kg/U" optional="hide" column_invisible="True"/>
        
        <!-- UoM (Informativo) -->
        <field name="residue_uom_id" string="UoM Base" optional="hide" column_invisible="True"/>
        
      </xpath>

      <!-- Agregar campos ocultos necesarios al final de la lista -->
      <xpath expr="//page[@name='order_lines']//list/field[@name='price_subtotal']" position="after">
        <field name="product_id" column_invisible="True"/>
        <field name="product_uom_id" column_invisible="True"/>
      </xpath>

      <!-- =========================================================
           6) FORMULARIO DE LÍNEA (DETALLE / POPUP)
           ========================================================= -->
      <xpath expr="//page[@name='order_lines']//form//field[@name='product_id']" position="after">
        
        <!-- Control de creación -->
        <group string="Configuración del Servicio">
          <group>
            <field name="create_new_service" widget="boolean_toggle"/>
            <field name="create_new_packaging" widget="boolean_toggle"/>
          </group>
        </group>
        
        <!-- Selección de servicio existente -->
        <group string="Servicio Existente" invisible="create_new_service">
          <field name="existing_service_id" 
                 options="{'no_create': True}"
                 placeholder="Buscar servicio existente..."/>
        </group>
        
        <!-- Campos para crear nuevo servicio -->
        <group string="Detalles del Residuo">
           <field name="residue_name" required="create_new_service"/>
           <field name="residue_type"/>
           <field name="plan_manejo"/>
        </group>

        <!-- Embalaje -->
        <group string="Embalaje">
           <field name="packaging_name" invisible="not create_new_packaging" required="create_new_packaging"/>
           <field name="residue_packaging_id" invisible="create_new_packaging"/>
        </group>
        
        <!-- Información de cantidades -->
        <group string="Medidas y Pesos">
          <group>
            <field name="residue_capacity" placeholder="Ej: 200 L"/>
            <field name="residue_volume" string="Número de Unidades"/>
          </group>
          <group>
            <field name="residue_weight_kg" string="Peso Total (kg)"/>
            <field name="weight_per_unit" readonly="1"/>
            <field name="residue_uom_id" readonly="1"/>
          </group>
        </group>
        
      </xpath>

    </field>
  </record>
</odoo>
```

