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
        return res