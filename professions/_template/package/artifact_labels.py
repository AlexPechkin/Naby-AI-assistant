"""Подписи полей на ru/en/zh — единственное, что пакет добавляет к оформлению."""
LABELS = {'results': ('Результаты', 'Results', '结果'), 'input_sha256': ('SHA-256 входа', 'Input SHA-256', '输入 SHA-256')}
TITLES = {'example_calc': {'ru': 'Пример расчёта', 'en': 'Example calculation', 'zh': '示例计算'}}


def field_label(key, language):
    t = LABELS.get(key)
    return t[('ru', 'en', 'zh').index(language)] if t else key.replace('_', ' ')
