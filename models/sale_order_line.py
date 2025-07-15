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

    # NUEVO: Campo para controlar el modo de selección
    create_new_service = fields.Boolean(
        string="Crear Nuevo Servicio",
        default=True,
        help="Marca para crear un nuevo servicio, desmarca para seleccionar uno existente"
    )

    # NUEVO: Campos para crear servicios directamente en las líneas
    residue_name = fields.Char(string="Nombre del Residuo")
    residue_volume = fields.Float(string="Volumen")
    residue_uom_id = fields.Many2one('uom.uom', string="Unidad de Medida")

    @api.onchange('create_new_service')
    def _onchange_create_new_service_line(self):
        """Limpiar campos según la opción seleccionada"""
        if self.create_new_service:
            # Limpiar producto seleccionado para crear nuevo
            self.product_id = False
        else:
            # Limpiar campos de nuevo servicio
            self.residue_name = False
            self.plan_manejo = False
            self.residue_type = False
            self.residue_volume = 0
            self.residue_uom_id = False

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
        
        service_name = f"Servicio de Recolección de {self.residue_name} - {plan_manejo_label}"
        
        service = self.env['product.product'].create({
            'name': service_name,
            'type': 'service',
            'categ_id': category.id,
            'sale_ok': True,
            'purchase_ok': False,
            'description_sale': f"""Servicio de manejo de residuo: {self.residue_name}
Plan de manejo: {plan_manejo_label}
Tipo de residuo: {residue_type_label}
Volumen: {self.residue_volume} {self.residue_uom_id.name if self.residue_uom_id else ''}""",
            'default_code': f"SRV-{self.residue_type.upper()}-{self.id or 'NEW'}",
        })

        # Asignar el servicio creado
        self.product_id = service.id
        self.name = service.name
        if self.residue_volume:
            self.product_uom_qty = self.residue_volume
        if self.residue_uom_id:
            self.product_uom = self.residue_uom_id.id