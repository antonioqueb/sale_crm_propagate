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
}