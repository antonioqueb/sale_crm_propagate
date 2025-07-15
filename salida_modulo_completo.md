-e ### ./models/sale_order_line.py
```
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    residue_type = fields.Selection(
        [('rsu', 'RSU'), ('rme', 'RME'), ('rp', 'RP')],
        string='Tipo de manejo'
    )
    
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

    # Campo para controlar el modo de selección
    create_new_service = fields.Boolean(
        string="Crear Nuevo Servicio",
        default=False,  # Por defecto permitir seleccionar servicios existentes
        help="Marca para crear un nuevo servicio, desmarca para seleccionar uno existente"
    )

    # Campo para seleccionar servicio existente (similar al CRM)
    existing_service_id = fields.Many2one(
        'product.product',
        string="Seleccionar Servicio Existente",
        domain="[('type', '=', 'service'), ('categ_id.name', 'ilike', 'servicios de residuos')]",
        help="Selecciona un servicio existente en lugar de crear uno nuevo"
    )

    # Campos para crear servicios directamente en las líneas
    residue_name = fields.Char(string="Nombre del Residuo")
    residue_volume = fields.Float(string="Unidades", default=1.0)  # MODIFICADO: ahora es "Unidades"
    
    # NUEVO CAMPO PARA PESO
    residue_weight_kg = fields.Float(
        string="Peso Total (kg)",
        help="Peso total del residuo en kilogramos para sistema de acopio."
    )
    
    # CAMPO COMPUTADO PARA MOSTRAR CONVERSIÓN
    weight_per_unit = fields.Float(
        string="Kg por Unidad",
        compute="_compute_weight_per_unit",
        store=True,
        help="Peso promedio por unidad (kg/unidad)"
    )
    
    residue_uom_id = fields.Many2one('uom.uom', string="Unidad de Medida")

    @api.depends('residue_volume', 'residue_weight_kg')
    def _compute_weight_per_unit(self):
        """Calcular peso promedio por unidad"""
        for record in self:
            if record.residue_volume and record.residue_volume > 0:
                record.weight_per_unit = record.residue_weight_kg / record.residue_volume
            else:
                record.weight_per_unit = 0.0

    @api.onchange('create_new_service')
    def _onchange_create_new_service_line(self):
        """Limpiar campos según la opción seleccionada"""
        if self.create_new_service:
            # Si cambia a crear nuevo servicio, limpiar servicio existente
            self.existing_service_id = False
            self.product_id = False
            self.product_template_id = False
            # Mantener otros campos para que el usuario pueda editarlos
        else:
            # Si cambia a usar servicio existente, NO limpiar campos inmediatamente
            # Los campos se actualizarán cuando seleccione un servicio
            pass

    @api.onchange('existing_service_id')
    def _onchange_existing_service_id(self):
        """Asignar servicio existente seleccionado"""
        if self.existing_service_id and not self.create_new_service:
            service = self.existing_service_id
            self.product_id = service.id
            self.product_template_id = service.product_tmpl_id.id
            self.name = service.name
            
            # Intentar extraer información del código del producto o descripción
            if service.default_code:
                # Ejemplo: SRV-RSU-123 -> extraer RSU
                parts = service.default_code.split('-')
                if len(parts) >= 2:
                    residue_type_map = {'RSU': 'rsu', 'RME': 'rme', 'RP': 'rp'}
                    if parts[1] in residue_type_map:
                        self.residue_type = residue_type_map[parts[1]]
            
            # Intentar extraer plan de manejo de la descripción o nombre
            description = (service.description_sale or service.name or '').lower()
            plan_map = {
                'reciclaje': 'reciclaje',
                'co-procesamiento': 'coprocesamiento', 
                'coprocesamiento': 'coprocesamiento',
                'físico-químico': 'tratamiento_fisicoquimico',
                'fisicoquimico': 'tratamiento_fisicoquimico',
                'biológico': 'tratamiento_biologico',
                'biologico': 'tratamiento_biologico',
                'térmico': 'tratamiento_termico',
                'termico': 'tratamiento_termico',
                'incineración': 'tratamiento_termico',
                'incineracion': 'tratamiento_termico',
                'confinamiento': 'confinamiento_controlado',
                'reutilización': 'reutilizacion',
                'reutilizacion': 'reutilizacion',
                'destrucción': 'destruccion_fiscal',
                'destruccion': 'destruccion_fiscal',
            }
            
            for key, value in plan_map.items():
                if key in description:
                    self.plan_manejo = value
                    break
            
            # Extraer nombre del residuo del nombre del servicio
            if 'Servicio Recolección de' in service.name.lower():
                # Extraer el nombre del residuo del nombre del servicio
                parts = service.name.split(' - ')
                if len(parts) > 0:
                    residue_part = parts[0].replace('Servicio Recolección de ', '')
                    self.residue_name = residue_part

    @api.onchange('residue_name', 'plan_manejo', 'residue_type')
    def _onchange_residue_fields(self):
        """Crear automáticamente el servicio cuando se completan los campos"""
        if (self.create_new_service and self.residue_name and 
            self.plan_manejo and self.residue_type and not self.product_id):
            self._create_service_from_line_data()

    def _create_service_from_line_data(self):
        """Crear un servicio basado en los datos de la línea"""
        if not (self.residue_name and self.plan_manejo and self.residue_type):
            return

        # Obtener categoría para servicios de residuos
        category = self.env['product.category'].search([
            ('name', 'ilike', 'servicios de residuos')
        ], limit=1)
        
        if not category:
            category = self.env['product.category'].create({
                'name': 'Servicios de Residuos',
            })

        # Crear el producto/servicio
        plan_manejo_label = dict(self._fields['plan_manejo'].selection).get(self.plan_manejo, '')
        residue_type_label = dict(self._fields['residue_type'].selection).get(self.residue_type, '')
        
        service_name = f"Servicio Recolección de {self.residue_name} - {plan_manejo_label}"
        
        service = self.env['product.product'].create({
            'name': service_name,
            'type': 'service',
            'categ_id': category.id,
            'sale_ok': True,
            'purchase_ok': False,
            'description_sale': f"""Servicio de manejo de residuo: {self.residue_name}
Plan de manejo: {plan_manejo_label}
Tipo de residuo: {residue_type_label}
Peso estimado: {self.residue_weight_kg} kg
Unidades: {self.residue_volume} {self.residue_uom_id.name if self.residue_uom_id else ''}""",
            'default_code': f"SRV-{self.residue_type.upper()}-{self.id or 'NEW'}",
        })

        # Asignar el servicio creado
        self.product_id = service.id
        self.product_template_id = service.product_tmpl_id.id
        self.name = service.name
        if self.residue_volume:
            self.product_uom_qty = self.residue_volume
        if self.residue_uom_id:
            self.product_uom = self.residue_uom_id.id

    @api.onchange('order_id.always_service')
    def _onchange_order_always_service(self):
        """Cuando cambia el campo always_service de la orden, ajustar el comportamiento"""
        if hasattr(self.order_id, 'always_service') and self.order_id.always_service:
            # Si la orden siempre es de servicios, permitir ambas opciones
            pass
        else:
            # Si no es específicamente de servicios, permitir selección normal
            self.create_new_service = False
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

    # CAMPO QUE FALTABA - AÑADIDO
    expiration_date = fields.Date(
        string='Fecha de Expiración',
        default=lambda self: date(date.today().year, 12, 31)
    )

    no_delivery = fields.Boolean(
        string='No generar entrega',
        default=False,
        help='Si está marcado, al confirmar la orden NO se crearán ni procesarán albaranes de entrega.'
    )

    # Campo booleano para controlar si siempre es servicio
    always_service = fields.Boolean(
        string='Siempre Servicios de Residuos',
        default=True,
        help='Cuando está marcado, las líneas se configuran por defecto para servicios de residuos'
    )

    # Referencia a cotización anterior
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
            
            # Crear líneas solo con servicios creados - INCLUYENDO DATOS DE PESO
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
                        'residue_weight_kg': res.weight_kg,  # NUEVO CAMPO
                        'weight_per_unit': res.weight_per_unit,  # NUEVO CAMPO
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
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    residue_type = fields.Selection(
        [('rsu', 'RSU'), ('rme', 'RME'), ('rp', 'RP')],
        string='Tipo de manejo'
    )
    
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

    # Campo para controlar el modo de selección
    create_new_service = fields.Boolean(
        string="Crear Nuevo Servicio",
        default=False,  # Por defecto permitir seleccionar servicios existentes
        help="Marca para crear un nuevo servicio, desmarca para seleccionar uno existente"
    )

    # Campo para seleccionar servicio existente (similar al CRM)
    existing_service_id = fields.Many2one(
        'product.product',
        string="Seleccionar Servicio Existente",
        domain="[('type', '=', 'service'), ('categ_id.name', 'ilike', 'servicios de residuos')]",
        help="Selecciona un servicio existente en lugar de crear uno nuevo"
    )

    # Campos para crear servicios directamente en las líneas
    residue_name = fields.Char(string="Nombre del Residuo")
    residue_volume = fields.Float(string="Unidades", default=1.0)  # MODIFICADO: ahora es "Unidades"
    
    # NUEVO CAMPO PARA PESO
    residue_weight_kg = fields.Float(
        string="Peso Total (kg)",
        help="Peso total del residuo en kilogramos para sistema de acopio."
    )
    
    # CAMPO COMPUTADO PARA MOSTRAR CONVERSIÓN
    weight_per_unit = fields.Float(
        string="Kg por Unidad",
        compute="_compute_weight_per_unit",
        store=True,
        help="Peso promedio por unidad (kg/unidad)"
    )
    
    residue_uom_id = fields.Many2one('uom.uom', string="Unidad de Medida")

    @api.depends('residue_volume', 'residue_weight_kg')
    def _compute_weight_per_unit(self):
        """Calcular peso promedio por unidad"""
        for record in self:
            if record.residue_volume and record.residue_volume > 0:
                record.weight_per_unit = record.residue_weight_kg / record.residue_volume
            else:
                record.weight_per_unit = 0.0

    @api.onchange('create_new_service')
    def _onchange_create_new_service_line(self):
        """Limpiar campos según la opción seleccionada"""
        if self.create_new_service:
            # Si cambia a crear nuevo servicio, limpiar servicio existente
            self.existing_service_id = False
            self.product_id = False
            self.product_template_id = False
            # Mantener otros campos para que el usuario pueda editarlos
        else:
            # Si cambia a usar servicio existente, NO limpiar campos inmediatamente
            # Los campos se actualizarán cuando seleccione un servicio
            pass

    @api.onchange('existing_service_id')
    def _onchange_existing_service_id(self):
        """Asignar servicio existente seleccionado"""
        if self.existing_service_id and not self.create_new_service:
            service = self.existing_service_id
            self.product_id = service.id
            self.product_template_id = service.product_tmpl_id.id
            self.name = service.name
            
            # Intentar extraer información del código del producto o descripción
            if service.default_code:
                # Ejemplo: SRV-RSU-123 -> extraer RSU
                parts = service.default_code.split('-')
                if len(parts) >= 2:
                    residue_type_map = {'RSU': 'rsu', 'RME': 'rme', 'RP': 'rp'}
                    if parts[1] in residue_type_map:
                        self.residue_type = residue_type_map[parts[1]]
            
            # Intentar extraer plan de manejo de la descripción o nombre
            description = (service.description_sale or service.name or '').lower()
            plan_map = {
                'reciclaje': 'reciclaje',
                'co-procesamiento': 'coprocesamiento', 
                'coprocesamiento': 'coprocesamiento',
                'físico-químico': 'tratamiento_fisicoquimico',
                'fisicoquimico': 'tratamiento_fisicoquimico',
                'biológico': 'tratamiento_biologico',
                'biologico': 'tratamiento_biologico',
                'térmico': 'tratamiento_termico',
                'termico': 'tratamiento_termico',
                'incineración': 'tratamiento_termico',
                'incineracion': 'tratamiento_termico',
                'confinamiento': 'confinamiento_controlado',
                'reutilización': 'reutilizacion',
                'reutilizacion': 'reutilizacion',
                'destrucción': 'destruccion_fiscal',
                'destruccion': 'destruccion_fiscal',
            }
            
            for key, value in plan_map.items():
                if key in description:
                    self.plan_manejo = value
                    break
            
            # Extraer nombre del residuo del nombre del servicio
            if 'Servicio Recolección de' in service.name.lower():
                # Extraer el nombre del residuo del nombre del servicio
                parts = service.name.split(' - ')
                if len(parts) > 0:
                    residue_part = parts[0].replace('Servicio Recolección de ', '')
                    self.residue_name = residue_part

    @api.onchange('residue_name', 'plan_manejo', 'residue_type')
    def _onchange_residue_fields(self):
        """Crear automáticamente el servicio cuando se completan los campos"""
        if (self.create_new_service and self.residue_name and 
            self.plan_manejo and self.residue_type and not self.product_id):
            self._create_service_from_line_data()

    def _create_service_from_line_data(self):
        """Crear un servicio basado en los datos de la línea"""
        if not (self.residue_name and self.plan_manejo and self.residue_type):
            return

        # Obtener categoría para servicios de residuos
        category = self.env['product.category'].search([
            ('name', 'ilike', 'servicios de residuos')
        ], limit=1)
        
        if not category:
            category = self.env['product.category'].create({
                'name': 'Servicios de Residuos',
            })

        # Crear el producto/servicio
        plan_manejo_label = dict(self._fields['plan_manejo'].selection).get(self.plan_manejo, '')
        residue_type_label = dict(self._fields['residue_type'].selection).get(self.residue_type, '')
        
        service_name = f"Servicio Recolección de {self.residue_name} - {plan_manejo_label}"
        
        service = self.env['product.product'].create({
            'name': service_name,
            'type': 'service',
            'categ_id': category.id,
            'sale_ok': True,
            'purchase_ok': False,
            'description_sale': f"""Servicio de manejo de residuo: {self.residue_name}
Plan de manejo: {plan_manejo_label}
Tipo de residuo: {residue_type_label}
Peso estimado: {self.residue_weight_kg} kg
Unidades: {self.residue_volume} {self.residue_uom_id.name if self.residue_uom_id else ''}""",
            'default_code': f"SRV-{self.residue_type.upper()}-{self.id or 'NEW'}",
        })

        # Asignar el servicio creado
        self.product_id = service.id
        self.product_template_id = service.product_tmpl_id.id
        self.name = service.name
        if self.residue_volume:
            self.product_uom_qty = self.residue_volume
        if self.residue_uom_id:
            self.product_uom = self.residue_uom_id.id

    @api.onchange('order_id.always_service')
    def _onchange_order_always_service(self):
        """Cuando cambia el campo always_service de la orden, ajustar el comportamiento"""
        if hasattr(self.order_id, 'always_service') and self.order_id.always_service:
            # Si la orden siempre es de servicios, permitir ambas opciones
            pass
        else:
            # Si no es específicamente de servicios, permitir selección normal
            self.create_new_service = False
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

    # CAMPO QUE FALTABA - AÑADIDO
    expiration_date = fields.Date(
        string='Fecha de Expiración',
        default=lambda self: date(date.today().year, 12, 31)
    )

    no_delivery = fields.Boolean(
        string='No generar entrega',
        default=False,
        help='Si está marcado, al confirmar la orden NO se crearán ni procesarán albaranes de entrega.'
    )

    # Campo booleano para controlar si siempre es servicio
    always_service = fields.Boolean(
        string='Siempre Servicios de Residuos',
        default=True,
        help='Cuando está marcado, las líneas se configuran por defecto para servicios de residuos'
    )

    # Referencia a cotización anterior
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
            
            # Crear líneas solo con servicios creados - INCLUYENDO DATOS DE PESO
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
                        'residue_weight_kg': res.weight_kg,  # NUEVO CAMPO
                        'weight_per_unit': res.weight_per_unit,  # NUEVO CAMPO
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
        
        <!-- Nueva página: Gestión de Servicios -->
        <page string="Gestión de Servicios" name="service_management">
          
          <!-- Control global de servicios -->
          <group string="Configuración de Servicios">
            <field name="always_service"/>
          </group>

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

        </page>

        <page string="Informe General" name="general_report">

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

      <!-- 4) Tree: modificar columnas en las líneas -->
      <xpath expr="//page[@name='order_lines']//list/field[@name='product_template_id']" position="replace">
        
        <!-- Campo de control para decidir crear o seleccionar -->
        <field name="create_new_service" string="Crear Nuevo"/>
        
        <!-- Campo para seleccionar servicio existente -->
        <field name="existing_service_id" 
               string="Servicio Existente"
               options="{'no_create': True}"/>
        
        <!-- Campos siempre editables para información del residuo -->
        <field name="residue_name" string="Nombre Residuo"/>
        <field name="residue_type" string="Tipo"/>
        <field name="plan_manejo" string="Plan de Manejo"/>
        
        <!-- NUEVOS CAMPOS DE PESO Y UNIDADES -->
        <field name="residue_weight_kg" string="Peso Total (kg)"/>
        <field name="residue_volume" string="Unidades"/>
        <field name="weight_per_unit" string="Kg/Unidad" readonly="1"/>
        
      </xpath>

      <!-- 5) Agregar campos en el final de la lista -->
      <xpath expr="//page[@name='order_lines']//list/field[@name='price_subtotal']" position="after">
        <field name="product_id" invisible="1"/>
      </xpath>

      <!-- Agregar los nuevos campos después del product_id en la vista de formulario -->
      <xpath expr="//page[@name='order_lines']//form//field[@name='product_id']" position="after">
        
        <!-- Control de creación (siempre visible) -->
        <group string="Configuración del Servicio">
          <field name="create_new_service"/>
        </group>
        
        <!-- Selección de servicio existente -->
        <group string="Servicio Existente" invisible="create_new_service">
          <field name="existing_service_id" 
                 string="Servicio Existente"
                 options="{'no_create': True}"
                 placeholder="Buscar servicio existente..."/>
          <separator string="Información extraída del servicio" colspan="2" invisible="not existing_service_id"/>
          <field name="residue_name" string="Nombre" readonly="not create_new_service" invisible="not existing_service_id"/>
          <field name="residue_type" string="Tipo de Residuo" readonly="not create_new_service" invisible="not existing_service_id"/>
          <field name="plan_manejo" string="Plan de Manejo" readonly="not create_new_service" invisible="not existing_service_id"/>
        </group>
        
        <!-- Campos para crear nuevo servicio -->
        <group string="Crear Nuevo Servicio" invisible="not create_new_service">
          <field name="residue_name"/>
          <field name="residue_type"/>
          <field name="plan_manejo"/>
        </group>
        
        <!-- Información de cantidades y peso - SIEMPRE EDITABLE -->
        <group string="Cantidades y Peso">
          <field name="residue_weight_kg" string="Peso Total (kg)" placeholder="Ejemplo: 200"/>
          <field name="residue_volume" string="Número de Unidades" placeholder="Ejemplo: 1"/>
          <field name="weight_per_unit" string="Kg por Unidad" readonly="1"/>
          <field name="residue_uom_id"/>
        </group>
        
      </xpath>

      <!-- 7) Agregar botón en el header (arriba a la derecha) -->
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

