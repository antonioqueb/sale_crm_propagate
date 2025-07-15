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
        
        service_name = f"Servicio Recolección de {self.residue_name}"
        
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