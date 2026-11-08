from __future__ import annotations

COSTBOOK_VERSION = 'san-joaquin-sfr-2026-11-placeholder'
CALIBRATION_STATUS = 'uncalibrated_placeholder_assumptions_not_contractor_bids'
UNITS = ('per_living_sqft', 'per_unit', 'per_lump')
SEVERITIES = ('cosmetic', 'moderate', 'major')

CONCEALED_AREAS = frozenset({'foundation', 'structural', 'electrical', 'plumbing', 'sewer_lateral', 'mold', 'asbestos', 'hvac'})

SOURCE_CLASSES = ('photograph', 'listing_remarks', 'site_visit', 'inspection_report', 'contractor_bid')
PRICEABLE_FROM = {
    'photograph': frozenset({'roof', 'exterior_paint', 'landscaping', 'flooring', 'interior_paint', 'kitchen', 'bathroom', 'windows', 'doors', 'drywall', 'cabinetry', 'fixtures', 'debris_removal', 'fencing', 'driveway', 'garage_door'}),
    'listing_remarks': frozenset({'roof', 'exterior_paint', 'landscaping', 'flooring', 'interior_paint', 'kitchen', 'bathroom', 'windows', 'doors', 'drywall', 'cabinetry', 'fixtures', 'debris_removal', 'fencing', 'driveway', 'garage_door'}),
    'site_visit': frozenset({'roof', 'exterior_paint', 'landscaping', 'flooring', 'interior_paint', 'kitchen', 'bathroom', 'windows', 'doors', 'drywall', 'cabinetry', 'fixtures', 'debris_removal', 'fencing', 'driveway', 'garage_door', 'hvac'}),
    'inspection_report': None,
    'contractor_bid': None,
}

COSTBOOK = {
    'roof':            {'unit': 'per_living_sqft', 'cosmetic': (300, 500, 800),      'moderate': (900, 1300, 1900),     'major': (1600, 2200, 3200)},
    'exterior_paint':  {'unit': 'per_living_sqft', 'cosmetic': (150, 250, 400),      'moderate': (350, 500, 750),       'major': (600, 850, 1200)},
    'interior_paint':  {'unit': 'per_living_sqft', 'cosmetic': (120, 200, 320),      'moderate': (250, 380, 550),       'major': (400, 600, 900)},
    'flooring':        {'unit': 'per_living_sqft', 'cosmetic': (200, 350, 550),      'moderate': (450, 700, 1000),      'major': (800, 1200, 1700)},
    'drywall':         {'unit': 'per_living_sqft', 'cosmetic': (80, 150, 260),       'moderate': (220, 380, 600),       'major': (500, 800, 1200)},
    'kitchen':         {'unit': 'per_unit',        'cosmetic': (350000, 600000, 950000),   'moderate': (900000, 1500000, 2300000),  'major': (2000000, 3200000, 4800000)},
    'bathroom':        {'unit': 'per_unit',        'cosmetic': (150000, 280000, 450000),   'moderate': (400000, 700000, 1100000),   'major': (900000, 1400000, 2100000)},
    'windows':         {'unit': 'per_unit',        'cosmetic': (25000, 45000, 70000),      'moderate': (50000, 80000, 120000),      'major': (90000, 140000, 210000)},
    'doors':           {'unit': 'per_unit',        'cosmetic': (15000, 28000, 45000),      'moderate': (35000, 55000, 85000),       'major': (60000, 95000, 140000)},
    'cabinetry':       {'unit': 'per_unit',        'cosmetic': (120000, 220000, 360000),   'moderate': (300000, 500000, 780000),    'major': (650000, 1000000, 1500000)},
    'fixtures':        {'unit': 'per_unit',        'cosmetic': (8000, 15000, 26000),       'moderate': (20000, 35000, 55000),       'major': (45000, 70000, 110000)},
    'garage_door':     {'unit': 'per_unit',        'cosmetic': (40000, 70000, 110000),     'moderate': (90000, 140000, 210000),     'major': (160000, 240000, 350000)},
    'landscaping':     {'unit': 'per_lump',        'cosmetic': (80000, 160000, 280000),    'moderate': (250000, 450000, 700000),    'major': (600000, 1000000, 1600000)},
    'fencing':         {'unit': 'per_lump',        'cosmetic': (60000, 120000, 200000),    'moderate': (180000, 320000, 500000),    'major': (450000, 750000, 1150000)},
    'driveway':        {'unit': 'per_lump',        'cosmetic': (70000, 130000, 220000),    'moderate': (200000, 360000, 560000),    'major': (500000, 850000, 1300000)},
    'debris_removal':  {'unit': 'per_lump',        'cosmetic': (30000, 60000, 110000),     'moderate': (90000, 170000, 280000),     'major': (250000, 450000, 750000)},
    'hvac':            {'unit': 'per_unit',        'cosmetic': (80000, 150000, 260000),    'moderate': (350000, 600000, 950000),    'major': (800000, 1300000, 2000000)},
    'electrical':      {'unit': 'per_living_sqft', 'cosmetic': (150, 280, 480),      'moderate': (500, 850, 1300),      'major': (1100, 1800, 2700)},
    'plumbing':        {'unit': 'per_living_sqft', 'cosmetic': (150, 280, 480),      'moderate': (500, 850, 1300),      'major': (1100, 1800, 2700)},
    'sewer_lateral':   {'unit': 'per_lump',        'cosmetic': (200000, 400000, 700000),   'moderate': (600000, 1000000, 1600000),  'major': (1400000, 2200000, 3400000)},
    'foundation':      {'unit': 'per_lump',        'cosmetic': (300000, 600000, 1100000),  'moderate': (1200000, 2200000, 3600000), 'major': (3000000, 5500000, 9000000)},
    'structural':      {'unit': 'per_lump',        'cosmetic': (400000, 800000, 1400000),  'moderate': (1500000, 2800000, 4600000), 'major': (4000000, 7500000, 12000000)},
    'mold':            {'unit': 'per_lump',        'cosmetic': (120000, 250000, 450000),   'moderate': (400000, 750000, 1250000),   'major': (1000000, 1900000, 3200000)},
    'asbestos':        {'unit': 'per_lump',        'cosmetic': (200000, 400000, 700000),   'moderate': (600000, 1100000, 1800000),  'major': (1500000, 2700000, 4400000)},
}

PERMIT_TRIGGERING = frozenset({'roof', 'electrical', 'plumbing', 'structural', 'foundation', 'sewer_lateral', 'hvac', 'asbestos'})
TIMELINE_WEEKS = {'cosmetic': 1, 'moderate': 3, 'major': 7}
