-e ### ./models/sale_order_line.py
```
from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    residue_type = fields.Selection(
        [('rsu', 'RSU'), ('rme', 'RME'), ('rp', 'RP')],
        string='Tipo de manejo'
    )
    # AGREGAR ESTE CAMPO
    plan_manejo = fields.Selection(
        selection=[
            ('reciclaje', 'Reciclaje'),
            ('coprocesamiento', 'Co-procesamiento'),
            ('tratamiento_fisicoquimico', 'Tratamiento Físico-Químico'),
            ('tratamiento_biologico', 'Tratamiento Biológico'),
            ('tratamiento_termico', 'Tratamiento Térmico (Incineración)'),
            ('confinamiento_controlado', 'Confinamiento Controlado'),
            ('reutilizacion', 'Reutilización'),
            ('destruccion_fiscal', 'Destrucción Fiscal'),
        ],
        string="Plan de Manejo",
        help="Método de tratamiento y/o disposición final para el residuo según normatividad ambiental."
    )
```

-e ### ./models/sale_order.py
```
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
```

-e ### ./reports/sale_order_report_template.xml
```
<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <!-- Heredar y extender el template del reporte de orden de venta -->
    <template id="report_saleorder_document_custom" inherit_id="sale.report_saleorder_document">
        
        <!-- Cambiar el título del documento -->
        <xpath expr="//t[@t-set='layout_document_title']" position="replace">
            <t t-set="layout_document_title">
                <span style="font-size: 23px; font-weight: 700;">PROPUESTA TECNICA Y ECONOMICA DE SERVICIOS N°  </span>
                <span t-field="doc.name" style="font-size: 23px; font-weight: 700;">SO0000</span>
            </t>
        </xpath>
        
        <!-- Agregar descripción personalizada antes de la tabla de líneas -->
        <xpath expr="//div[@class='oe_structure'][2]" position="after">
            <div class="row mt-4 mb-3" style="font-size: 13px; line-height: 1.2;">
                <div class="col-12">
                    <h4 style="font-size: 14px; line-height: 1.2; margin-bottom: 8px;">Servicio de transporte y disposición de residuos para: <span t-field="doc.partner_id.name" style="font-weight: 700;">DIFRENOSA</span></h4>
                    <p class="text-muted" style="font-size: 12px; line-height: 1.2; margin-bottom: 10px;">Según normatividad aplicable</p>
                    
                    <h5 class="mt-3" style="font-size: 13px; line-height: 1.2; margin-bottom: 8px;">Propuesta Técnica y Económica de Servicios</h5>
                    
                    <h6 class="mt-3" style="font-size: 12px; line-height: 1.2; margin-bottom: 8px;">1.0 ANTECEDENTES</h6>
                    <p style="font-size: 12px; line-height: 1.2; margin-bottom: 10px;">
                        Servicios Ambientales Internacionales, S. de R.L. (SAI) ofrece a <strong><span t-field="doc.partner_id.name">DIFRENOSA</span></strong> 
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
                    
                    <!-- Agregar imagen de flota de vehículos -->
                    <div class="row mt-3 mb-8" style="text-align: center;">
                        <div class="col-12">
                            <img src="/sale_crm_propagate/static/description/frontal.jpg" 
                                 alt="Flota de vehículos especializados" 
                                 style="max-width: 100%; height: auto; max-height: 470px; border: 1px solid #ddd; border-radius: 5px;"/>
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
                <div class="col-4" t-if="doc.pickup_location">
                    <strong>Ubicación de recolección:</strong> <span t-field="doc.pickup_location"/>
                </div>
                <!-- <div class="col-4" t-if="doc.expiration_date">
                    <strong class="text-primary">Fecha de Expiración:</strong><br/>
                    <span t-field="doc.expiration_date" t-options='{"widget": "date"}'/>
                </div> -->
            </div>
        </xpath>
        
        <!-- Modificar el encabezado de la columna Quantity para mostrar "Cantidad" -->
        <xpath expr="//th[@name='th_quantity']" position="replace">
            <th name="th_quantity" class="text-end text-nowrap">Cantidad</th>
        </xpath>
        
        <!-- Modificar el contenido de la celda de cantidad para mostrar cantidad + embalaje solamente -->
        <xpath expr="//td[@name='td_quantity']" position="replace">
            <td name="td_quantity" class="text-end text-nowrap">
                <span t-field="line.product_uom_qty">3</span>
                <span t-if="line.product_packaging_id" t-field="line.product_packaging_id">TOTE</span>
                <span t-else="" t-field="line.product_uom">units</span>
            </td>
        </xpath>
        
    </template>
</odoo>
```

-e ### ./salida_modulo_completo.md
```
-e ### ./models/sale_order_line.py
```
from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    residue_type = fields.Selection(
        [('rsu', 'RSU'), ('rme', 'RME'), ('rp', 'RP')],
        string='Tipo de manejo'
    )
    # AGREGAR ESTE CAMPO
    plan_manejo = fields.Selection(
        selection=[
            ('reciclaje', 'Reciclaje'),
            ('coprocesamiento', 'Co-procesamiento'),
            ('tratamiento_fisicoquimico', 'Tratamiento Físico-Químico'),
            ('tratamiento_biologico', 'Tratamiento Biológico'),
            ('tratamiento_termico', 'Tratamiento Térmico (Incineración)'),
            ('confinamiento_controlado', 'Confinamiento Controlado'),
            ('reutilizacion', 'Reutilización'),
            ('destruccion_fiscal', 'Destrucción Fiscal'),
        ],
        string="Plan de Manejo",
        help="Método de tratamiento y/o disposición final para el residuo según normatividad ambiental."
    )
```

-e ### ./models/sale_order.py
```
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
```

-e ### ./reports/sale_order_report_template.xml
```
<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <!-- Heredar y extender el template del reporte de orden de venta -->
    <template id="report_saleorder_document_custom" inherit_id="sale.report_saleorder_document">
        
        <!-- Cambiar el título del documento -->
        <xpath expr="//t[@t-set='layout_document_title']" position="replace">
            <t t-set="layout_document_title">
                <span style="font-size: 23px; font-weight: 700;">PROPUESTA TECNICA Y ECONOMICA DE SERVICIOS N°  </span>
                <span t-field="doc.name" style="font-size: 23px; font-weight: 700;">SO0000</span>
            </t>
        </xpath>
        
        <!-- Agregar descripción personalizada antes de la tabla de líneas -->
        <xpath expr="//div[@class='oe_structure'][2]" position="after">
            <div class="row mt-4 mb-3" style="font-size: 13px; line-height: 1.2;">
                <div class="col-12">
                    <h4 style="font-size: 14px; line-height: 1.2; margin-bottom: 8px;">Servicio de transporte y disposición de residuos para: <span t-field="doc.partner_id.name" style="font-weight: 700;">DIFRENOSA</span></h4>
                    <p class="text-muted" style="font-size: 12px; line-height: 1.2; margin-bottom: 10px;">Según normatividad aplicable</p>
                    
                    <h5 class="mt-3" style="font-size: 13px; line-height: 1.2; margin-bottom: 8px;">Propuesta Técnica y Económica de Servicios</h5>
                    
                    <h6 class="mt-3" style="font-size: 12px; line-height: 1.2; margin-bottom: 8px;">1.0 ANTECEDENTES</h6>
                    <p style="font-size: 12px; line-height: 1.2; margin-bottom: 10px;">
                        Servicios Ambientales Internacionales, S. de R.L. (SAI) ofrece a <strong><span t-field="doc.partner_id.name">DIFRENOSA</span></strong> 
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
                    
                    <!-- Agregar imagen de flota de vehículos -->
                    <div class="row mt-3 mb-8" style="text-align: center;">
                        <div class="col-12">
                            <img src="/sale_crm_propagate/static/description/frontal.jpg" 
                                 alt="Flota de vehículos especializados" 
                                 style="max-width: 100%; height: auto; max-height: 470px; border: 1px solid #ddd; border-radius: 5px;"/>
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
                <div class="col-4" t-if="doc.pickup_location">
                    <strong>Ubicación de recolección:</strong> <span t-field="doc.pickup_location"/>
                </div>
                <!-- <div class="col-4" t-if="doc.expiration_date">
                    <strong class="text-primary">Fecha de Expiración:</strong><br/>
                    <span t-field="doc.expiration_date" t-options='{"widget": "date"}'/>
                </div> -->
            </div>
        </xpath>
        
        <!-- Modificar el encabezado de la columna Quantity para mostrar "Cantidad" -->
        <xpath expr="//th[@name='th_quantity']" position="replace">
            <th name="th_quantity" class="text-end text-nowrap">Cantidad</th>
        </xpath>
        
        <!-- Modificar el contenido de la celda de cantidad para mostrar cantidad + embalaje solamente -->
        <xpath expr="//td[@name='td_quantity']" position="replace">
            <td name="td_quantity" class="text-end text-nowrap">
                <span t-field="line.product_uom_qty">3</span>
                <span t-if="line.product_packaging_id" t-field="line.product_packaging_id">TOTE</span>
                <span t-else="" t-field="line.product_uom">units</span>
            </td>
        </xpath>
        
    </template>
</odoo>
```
```

-e ### ./views/sale_order_view.xml
```
<?xml version="1.0" encoding="UTF-8"?>
<odoo>
  <record id="view_sale_order_form_crm_fields" model="ir.ui.view">
    <field name="name">sale.order.form.crm.fields</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">

      <!-- 1) Pestaña "Informe General" después de Líneas de la Orden -->
      <xpath expr="//notebook/page[@name='order_lines']" position="after">
        <page string="Informe General" name="general_report">
          
          <!-- Información del Servicio -->
          <group string="Información del Servicio">
            <group>
              <field name="service_frequency" readonly="1"/>
              <field name="pickup_location" readonly="1"/>
            </group>
            <group>
              <field name="residue_new" readonly="1"/>
              <field name="requiere_visita" readonly="1"/>
            </group>
          </group>

          <!-- Información Básica del Prospecto -->
          <group string="Información Básica del Prospecto">
            <group>
              <field name="company_size" readonly="1"/>
              <field name="industrial_sector" readonly="1"/>
            </group>
            <group>
              <field name="prospect_priority" readonly="1"/>
              <field name="estimated_business_potential" readonly="1"/>
            </group>
          </group>

          <!-- Información Operativa -->
          <group string="Información Operativa">
            <group>
              <field name="access_restrictions" widget="text" readonly="1"/>
              <field name="allowed_collection_schedules" widget="text" readonly="1"/>
              <field name="current_container_types" widget="text" readonly="1"/>
            </group>
            <group>
              <field name="special_handling_conditions" widget="text" readonly="1"/>
              <field name="seasonality" widget="text" readonly="1"/>
            </group>
          </group>

          <!-- Información Regulatoria -->
          <group string="Información Regulatoria">
            <group>
              <field name="waste_generator_registration" readonly="1"/>
              <field name="environmental_authorizations" widget="text" readonly="1"/>
            </group>
            <group>
              <field name="quality_certifications" widget="text" readonly="1"/>
              <field name="other_relevant_permits" widget="text" readonly="1"/>
            </group>
          </group>

          <!-- Competencia y Mercado -->
          <group string="Competencia y Mercado">
            <group>
              <field name="current_service_provider" readonly="1"/>
              <field name="current_costs" readonly="1"/>
              <field name="current_provider_satisfaction" readonly="1"/>
            </group>
            <group>
              <field name="reason_for_new_provider" widget="text" readonly="1"/>
            </group>
          </group>

          <!-- Requerimientos Especiales -->
          <group string="Requerimientos Especiales">
            <group>
              <field name="specific_certificates_needed" widget="text" readonly="1"/>
              <field name="reporting_requirements" widget="text" readonly="1"/>
            </group>
            <group>
              <field name="service_urgency" readonly="1"/>
              <field name="estimated_budget" readonly="1"/>
            </group>
          </group>

          <!-- Campos de Seguimiento -->
          <group string="Seguimiento">
            <group>
              <field name="next_contact_date" readonly="1"/>
              <field name="pending_actions" widget="text" readonly="1"/>
            </group>
            <group>
              <field name="conversation_notes" widget="text" readonly="1"/>
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
      <xpath expr="//field[@name='payment_term_id']" position="before">
        <group>
          <field name="expiration_date"/>
        </group>
      </xpath>

      <!-- 4) Tree: columnas después de product_template_id -->
      <xpath expr="//page[@name='order_lines']//list/field[@name='product_template_id']" position="after">
        <field name="plan_manejo"/>
        <field name="residue_type"/>
      </xpath>

      <!-- 5) Form embebido: columnas después de product_id -->
      <xpath expr="//page[@name='order_lines']//form//field[@name='product_id']" position="after">
        <field name="plan_manejo"/>
        <field name="residue_type"/>
      </xpath>

      <!-- 6) Agregar botón en el header (arriba a la derecha) -->
      <xpath expr="//header" position="inside">
        <button type="object" 
                name="action_create_related_quotation" 
                string="Nueva Cotización" 
                class="btn btn-secondary"
                invisible="state not in ['draft', 'sent']"
                help="Crear una nueva cotización para este cliente con nuevos residuos"/>
      </xpath>

    </field>
  </record>
</odoo>
```

### __init__.py
```python
from . import models
```

### __manifest__.py
```python
{
    'name': 'CRM to Sale Propagate',
    'version': '18.0.1.0.0',
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
}
```

