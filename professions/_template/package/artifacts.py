"""Какие разделы показать в Word/PDF/Excel. Общие разделы источников/цитат/допущений добавляет profbase.render."""
import profbase
from .artifact_labels import field_label, TITLES


def _sections(function, result, language):
    rows = [[field_label(k, language), profbase.display_text(v)] for k, v in sorted(result.items()) if not k.endswith(('_sha256',)) and type(v) not in (dict, list)]
    return [{'title': field_label('results', language), 'paragraphs': [], 'rows': rows}]


def render(function, result, language, config=None, review_evidence=None):
    title = TITLES.get(function, {}).get(language, function)
    return profbase.render(title, _sections(function, profbase.snapshot(result), language), language, review_evidence,
                           stem=function, field_label=field_label)
