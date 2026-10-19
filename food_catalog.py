"""Small, auditable USDA FoodData Central SR Legacy reference snapshot.

Values are per 100 g edible food. A match is a reference for a plain ingredient,
never proof of a restaurant recipe, its cooking oil, or the eaten portion.
Retrieved from the official FoodData Central API on 2026-09-24.
"""
import math

_ROWS = (
    (168930, 'Rice, white, medium-grain, cooked, unenriched',
     ('米饭', '白米饭', '熟米饭', '白米饭熟重'), (130, 2.38, 28.6, 0.21)),
    (169228, 'Eggplant, raw',
     ('生茄子', '茄子生重'), (25, 0.98, 5.88, 0.18)),
    (171411, 'Oil, soybean, salad or cooking',
     ('食用油', '烹调油', '植物油', '大豆油'), (884, 0, 0, 100)),
    (171450, 'Chicken, broilers or fryers, meat and skin, cooked, roasted',
     ('鸡肉熟重带皮', '熟鸡肉带皮'), (239, 27.3, 0, 13.6)),
    (169434, 'Beef, flank, steak, separable lean and fat, cooked, braised',
     ('炖牛肉熟重', '牛肉炖熟瘦肥相间'), (263, 27, 0, 16.4)),
)


def _normalized(name):
    return ''.join(char for char in str(name or '') if char not in ' （）()\t\r\n')


def match(name):
    normalized = _normalized(name)
    for identifier, description, aliases, values in _ROWS:
        if normalized in {_normalized(alias) for alias in aliases}:
            basis = ('熟重' if identifier in (168930, 171450, 169434) else
                     '生重' if identifier == 169228 else '食用油重量')
            return {'id': str(identifier), 'description': description,
                    'per_100g': dict(zip(('kcal', 'protein_g', 'carbs_g', 'fat_g'), values)),
                    'version': 'USDA SR Legacy 2018',
                    'weight_basis': basis,
                    'url': f'https://fdc.nal.usda.gov/food-search/?query={identifier}'}
    return None


def verified(name, identifier, density):
    row = match(name)
    if not row or str(identifier) != row['id'] or not isinstance(density, dict):
        return None
    for key, value in row['per_100g'].items():
        pair = density.get(key)
        if not isinstance(pair, list) or len(pair) != 2 or any(
                isinstance(x, bool) or not isinstance(x, (int, float)) or
                not math.isfinite(x) or abs(x-value) > .01
                for x in pair):
            return None
    return row
