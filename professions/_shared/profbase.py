# -*- coding: utf-8 -*-
"""profbase — общая основа пакетов профессий Наби (сборка 45). Один раз для всех, вместо копии в каждом пакете.

Что здесь (одинаковое у всех 10 проверенных пакетов, собрано из их самых полных версий):
  • Core  — безопасный запуск функции пакета: запрет «полномочий» в предложении модели (RESERVED), снимок входа
            с sha256, Decimal prec=128, обязательные флаги в результате (analysis_only, external_actions=False…).
  • run() — фасад service.run: строгий JSON (дубликаты ключей, NaN), проверка привязок (binding.verify пакета),
            выполнение, рендер артефактов с проверкой имён/размеров, selected_evidence.json.
  • evidence — точные числа и даты из источников (exact_number, source_number, whole_token_present, day, text).
  • writers — Word/PDF/Excel из секций {title, paragraphs, columns, rows}; шрифт — один общий (NabyDocumentSans
            из profpkgs/_shared/fonts), проверяется по sha256; разделы «Допущения», «Источники», «Цитаты».

Пакет-наследник оставляет только своё: FUNCTIONS, CALCULATIONS, RESERVED_EXTRA, флаги результата, calculations.py,
scenarios.py, artifacts.py (какие секции показать), artifact_labels (подписи полей на ru/en/zh) и binding.py — пока
привязки не вынесены сюда (это следующий шаг развития основы).

Десять проверенных пакетов на эту основу пока НЕ переведены: их core.py и binding.py закреплены по байтам (хэши в
NABY_PACKAGE.json). Новые пакеты строятся сразу на profbase: см. professions/_template.
"""
import copy
import hashlib
import html
import io
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation, Context, DecimalException, localcontext
from importlib import import_module
from pathlib import Path

FONT_NAME = 'NabyDocumentSans'
FONT_FILE = 'NabyDocumentSans.ttf'
FONT_SHA256 = 'd4b79f59e2b6b3d791b3ed265edc5294ce9973a13c1c6f86a5ccd9e40d07fd9d'
MAX_JSON = 2_000_000
MAX_ARTIFACT = 24_000_000
MAX_ARTIFACTS = 30
ARTIFACT_NAME = re.compile(r'[A-Za-z0-9_-]+\.(?:json|docx|xlsx|pdf|xml|html|txt|csv|md)')

# Поля, которые модель не вправе «предложить»: это решения хозяина/человека, а не факты
RESERVED = frozenset((
    'verified', 'confirmed', 'approved', 'signed', 'trusted', 'is_trusted', 'user_approval', 'approved_by_user', 'authorized',
    'host_context', 'assignment_context', 'external_actions', 'official_report', 'signature_applied', 'calculation_allowed',
    'host_agreement_received', 'assignment_user_confirmation_received', 'freshness', 'current_law', 'practice_right',
    'current_rule_chain_complete', 'actual_weekly_update_performed', 'last_confirmed_database', 'last_verified_snapshot',
    'last_verified_at', 'actual_success_at', 'safety_established', 'authorization_established', 'approval_established',
    'classification_decision', 'final_classification', 'clinical_approval', 'practice_authorized',
))
RESERVED_SUFFIXES = ('_verified', '_confirmed', '_approved', '_signed', '_approval_established', '_authorization_established')
# Флаги, которые основа ставит в каждый результат (пакет может добавить свои через result_flags)
BASE_RESULT_FLAGS = {'source_semantics_verified': False, 'current_legal_applicability_verified': False,
                     'external_actions': False, 'analysis_only': True}


# ───────── безопасность предложения модели ─────────
def reject_proposed_authority(value, reserved=RESERVED, depth=0):
    if depth > 32: raise ValueError('proposal_nesting_limit')
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str: raise ValueError('proposal_string_keys_required')
            if key in reserved or key.endswith(RESERVED_SUFFIXES): raise ValueError('reserved_authority_field:' + key)
            reject_proposed_authority(item, reserved, depth + 1)
    elif type(value) is list:
        for item in value: reject_proposed_authority(item, reserved, depth + 1)


def strict_snapshot(value):
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))
    except (TypeError, OverflowError, RecursionError):
        raise ValueError('bounded_json_config_required') from None
    if len(raw.encode('utf8')) > MAX_JSON: raise ValueError('config_size_limit')
    return json.loads(raw), hashlib.sha256(raw.encode('utf8')).hexdigest()


class Core:
    """Диспетчер функций пакета. package — имя пакета (__package__ из его core.py)."""

    def __init__(self, package, functions, calculations=(), reserved_extra=(), result_flags=None,
                 calc_module='.calculations', scenario_module='.scenarios', error='unknown_function'):
        self.package = package
        self.FUNCTIONS = tuple(functions)
        self.CALCULATIONS = frozenset(calculations)
        self.RESERVED = RESERVED | frozenset(reserved_extra)
        self.result_flags = dict(BASE_RESULT_FLAGS, **(result_flags or {}))
        self.calc_module, self.scenario_module, self.error = calc_module, scenario_module, error

    def module_for(self, function):
        if type(function) is not str or function not in self.FUNCTIONS: raise ValueError(self.error)
        return import_module(self.calc_module if function in self.CALCULATIONS else self.scenario_module, self.package)

    def execute(self, function_id, config):
        module = self.module_for(function_id)
        if type(config) is not dict or set(config) != {'function', 'data'} or config['function'] != function_id \
                or type(config['data']) is not dict:
            raise ValueError('function_config_mismatch')
        reject_proposed_authority(config['data'], self.RESERVED)
        original, digest = strict_snapshot(config)
        with localcontext(Context(prec=128)):
            try:
                result = getattr(module, function_id)(copy.deepcopy(original['data']))
            except (KeyError, AttributeError, TypeError, IndexError):
                raise ValueError('invalid_subject_input_structure') from None
            except (DecimalException, OverflowError, ZeroDivisionError):
                raise ValueError('bounded_calculation_required') from None
        result = copy.deepcopy(result)
        result.update(input_sha256=digest, **self.result_flags)
        strict_snapshot(result)
        return result

    def input_units(self, function_id, data):
        try:
            return self.module_for(function_id).input_units(function_id, data)
        except (KeyError, AttributeError, TypeError, IndexError):
            raise ValueError('invalid_numeric_input_structure') from None

    def selected_texts(self, function_id, data):
        callback = getattr(self.module_for(function_id), 'selected_texts', None)
        try:
            return callback(function_id, data) if callback else {}
        except (KeyError, AttributeError, TypeError, IndexError):
            raise ValueError('invalid_selected_text_structure') from None


# ───────── фасад service.run ─────────
def _pairs(items):
    result = {}
    for key, value in items:
        if key in result: raise ValueError('duplicate_json_key')
        result[key] = value
    return result


def _constant(_):
    raise ValueError('nonfinite_json')


def parse_proposal(proposal_json):
    if type(proposal_json) is not str or len(proposal_json.encode('utf8')) > MAX_JSON: raise ValueError('bounded_json_required')
    try:
        config = json.loads(proposal_json, object_pairs_hook=_pairs, parse_constant=_constant)
    except RecursionError:
        raise ValueError('proposal_nesting_limit') from None
    json.dumps(config, allow_nan=False)
    return config


def validate_artifacts(files):
    if type(files) is not dict or not 1 <= len(files) <= MAX_ARTIFACTS: raise ValueError('bounded_artifacts_required')
    for name, raw in files.items():
        if type(name) is not str or len(name) > 200 or not ARTIFACT_NAME.fullmatch(name): raise ValueError('artifact_name')
        if type(raw) is not bytes or not 1 <= len(raw) <= MAX_ARTIFACT: raise ValueError('artifact_bytes')
    return files


def run(core, verify, render, function, proposal_json, documents, language='ru', review='preview'):
    """Общий service.run. verify(function, config, documents) -> (facts, evidence); render(function, result, language,
    config=, review_evidence=) -> {имя: bytes}."""
    if function not in core.FUNCTIONS or language not in ('ru', 'en', 'zh') or review not in ('preview', 'calculate'):
        raise ValueError('function_language_review_required')
    config = parse_proposal(proposal_json)
    facts, evidence = verify(function, config, documents)
    domain_config = {'function': function, 'data': config['data']}
    result = core.execute(function, domain_config)
    files = {}
    if review == 'calculate':
        files = validate_artifacts(render(function, result, language, config=domain_config, review_evidence=evidence))
        files['selected_evidence.json'] = (json.dumps({'facts': facts, 'review': evidence}, ensure_ascii=False, indent=2,
                                                      allow_nan=False) + '\n').encode('utf8')
    return {'function': function, 'result': result, 'files': files, 'evidence': evidence,
            'proposal_sha256': hashlib.sha256(proposal_json.encode('utf8')).hexdigest(),
            'review': review, 'private': True, 'external_network_used': False, 'records_changed': False,
            'host_integration_required': True, 'source_semantics_verified': False}


# ───────── точные числа и даты из источников ─────────
def day(value):
    if type(value) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value): raise ValueError('iso_date_required')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('invalid_date') from None


def text(value, maximum):
    if type(value) is not str or not value.strip() or len(value) > maximum: raise ValueError('bounded_source_text_required')
    return value


def exact_number(value):
    """Каноническое число: десятичная запись или e-нотация; без двоичных дробей и группировки."""
    if type(value) not in (str, int) or len(str(value)) > 160: raise ValueError('exact_numeric_value_required')
    value = str(value)
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,3})?', value): raise ValueError('exact_numeric_value_required')
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError('invalid_numeric_value') from None
    if not number.is_finite() or len(number.as_tuple().digits) > 40 or abs(number.as_tuple().exponent) > 140 \
            or (number and abs(number.adjusted()) > 100):
        raise ValueError('bounded_numeric_value_required')
    return number


_SUP = str.maketrans('⁺⁻⁰¹²³⁴⁵⁶⁷⁸⁹', '+-0123456789')


def source_number(token, separator):
    """Число как в источнике: явный разделитель, e или ×10^ запись, группировка пробелами; без многоточий."""
    if separator not in ('.', ','): raise ValueError('decimal_separator_required')
    token = text(token, 160)
    if any(c in token for c in ('…', '(', ')')) or '...' in token: raise ValueError('ambiguous_source_token')
    raw = token.replace('−', '-').replace(' ', ' ').replace(' ', ' ')
    sup = re.fullmatch(r'(.+?[x×]\s*10)([⁺⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+)', raw)
    if sup: raw = sup.group(1) + '^' + sup.group(2).translate(_SUP)
    sci = re.fullmatch(r'(.+?)(?:\s*[x×]\s*10\s*\^\s*([+-]?\d{1,3}))', raw)
    if sci:
        mantissa, exponent = sci.group(1), sci.group(2)
    else:
        parts = re.fullmatch(r'(.+?)(?: *[eE]([+-]?\d{1,3}))?', raw)
        if not parts: raise ValueError('source_token_required')
        mantissa, exponent = parts.group(1), parts.group(2)
    sep = re.escape(separator)
    integer = r'(?:\d+|\d{1,3}(?: \d{3})+)'
    fraction = r'(?:\d+|\d{3}(?: \d{3})*(?: \d{1,4})?)'
    if not re.fullmatch(r'[+-]?' + integer + r'(?:' + sep + fraction + r')?', mantissa): raise ValueError('source_token_required')
    canonical = mantissa.replace(' ', '').replace(separator, '.') + ('e' + exponent if exponent is not None else '')
    return exact_number(canonical)


def whole_token_present(quote, token):
    """Маркер стоит в цитате целиком (не кусок сгруппированной мантиссы и не оторванная степень)."""
    pattern = r'(?<![\w.,^+\-−])' + re.escape(token) + r'(?![\w.,^])'
    for match in re.finditer(pattern, quote):
        before, after = quote[:match.start()], quote[match.end():]
        if re.search(r'\d $', before) or re.match(r'^ \d', after): continue
        return True
    return False


# ───────── документы: Word / PDF / Excel ─────────
def snapshot(value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False,
                     default=lambda x: str(x) if isinstance(x, Decimal) else (_ for _ in ()).throw(ValueError('non_json_artifact_input')))
    if len(raw.encode('utf-8')) > 8_000_000: raise ValueError('artifact_input_limit')
    parsed = json.loads(raw)

    def visit(x, depth=0):
        if depth > 24: raise ValueError('artifact_nesting_limit')
        if isinstance(x, str):
            if len(x) > 200000: raise ValueError('artifact_text_invalid')
            if any(0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in x): raise ValueError('artifact_unicode_invalid')
        elif isinstance(x, dict):
            if len(x) > 10000: raise ValueError('artifact_mapping_limit')
            for k, v in x.items(): visit(k, depth + 1); visit(v, depth + 1)
        elif isinstance(x, list):
            if len(x) > 2000: raise ValueError('artifact_array_limit')
            for v in x: visit(v, depth + 1)
    visit(parsed)
    return parsed


def display_text(value):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', lambda m: '\\x%02X' % ord(m.group()), str(value))


UI = {
    'ru': {'field': 'Поле', 'value': 'Значение', 'missing': '—', 'yes': 'да', 'no': 'нет', 'assumptions': 'Допущения',
           'evidence': 'Источники', 'quote': 'Цитата', 'reference': 'Ссылка', 'pointer': 'Поле данных', 'rationale': 'Обоснование',
           'fact_id': 'Факт', 'source_sha256': 'SHA-256 файла',
           'draft': 'Черновик, подготовленный Наби на этом компьютере по выбранным вами файлам.',
           'source_note': 'Каждое число привязано к цитате из источника; смысл цитат и применимость норм проверяет человек.',
           'unverified': 'Автоматическая привязка подтверждает только наличие текста в файле, но не его смысл.',
           'control_notice': 'Документ не является официальным заключением и не подписан.',
           'verification_scope': 'Расчёт выполнен локально, без сети; записи не изменялись.',
           'assumption_banner': 'В расчёте есть допущения, не взятые из файлов, — они перечислены отдельно.',
           'sources_unconfirmed': 'Источники для этого расчёта не привязаны.', 'as_of': 'По состоянию на'},
    'en': {'field': 'Field', 'value': 'Value', 'missing': '—', 'yes': 'yes', 'no': 'no', 'assumptions': 'Assumptions',
           'evidence': 'Sources', 'quote': 'Quote', 'reference': 'Reference', 'pointer': 'Data field', 'rationale': 'Rationale',
           'fact_id': 'Fact', 'source_sha256': 'File SHA-256',
           'draft': 'A draft prepared by Naby on this computer from the files you selected.',
           'source_note': 'Every number is bound to a quotation from a source; meaning and applicability are checked by a person.',
           'unverified': 'Automatic binding confirms only that the text occurs in the file, not its meaning.',
           'control_notice': 'This document is not an official opinion and is not signed.',
           'verification_scope': 'Calculated locally, offline; no records were changed.',
           'assumption_banner': 'The calculation contains assumptions not taken from files — they are listed separately.',
           'sources_unconfirmed': 'No sources are bound to this calculation.', 'as_of': 'As of'},
    'zh': {'field': '字段', 'value': '值', 'missing': '—', 'yes': '是', 'no': '否', 'assumptions': '假设', 'evidence': '来源',
           'quote': '引文', 'reference': '参考', 'pointer': '数据字段', 'rationale': '理由', 'fact_id': '事实', 'source_sha256': '文件 SHA-256',
           'draft': 'Naby 在本机根据您选择的文件准备的草稿。', 'source_note': '每个数字都对应来源引文；含义和适用性由人核对。',
           'unverified': '自动绑定仅确认文本存在于文件中，不确认其含义。', 'control_notice': '本文件不是正式结论，未签署。',
           'verification_scope': '本机离线计算；未更改任何记录。', 'assumption_banner': '计算包含未取自文件的假设，另列。',
           'sources_unconfirmed': '此计算未绑定来源。', 'as_of': '截至'},
}


def tr(triple, language):
    return triple[('ru', 'en', 'zh').index(language)]


def intro(language, review_evidence):
    u = UI[language]; review = review_evidence or {}
    paragraphs = [u['draft'], u['source_note'], u['unverified'], u['control_notice'], u['verification_scope']]
    if review.get('assumptions') or review.get('hypothetical_inputs_present'): paragraphs.insert(0, u['assumption_banner'])
    if review.get('as_of'): paragraphs.append(u['as_of'] + ': ' + str(review['as_of']))
    return paragraphs


def evidence_sections(review_evidence, language, field_label=None):
    """Разделы «Допущения», «Источники», «Цитаты» — одинаковые для всех профессий."""
    u = UI[language]; review = review_evidence or {}; out = []
    lab = field_label or (lambda key, lang: u.get(key, key))
    if review.get('assumptions'):
        rows = [[str(a.get('pointer', '')), str(a.get('value', '')) + ' ' + str(a.get('unit', '')), str(a.get('rationale', ''))]
                for a in review['assumptions']]
        out.append({'title': u['assumptions'], 'paragraphs': [u['assumption_banner']],
                    'columns': [lab('pointer', language), u['value'], lab('rationale', language)], 'rows': rows, 'evidence_section': True})
    bindings = review.get('bindings', [])
    if not bindings:
        out.append({'title': u['evidence'], 'paragraphs': [u['sources_unconfirmed'], u['unverified']], 'rows': [], 'evidence_section': True})
        return out
    sources = {}
    for b in bindings:
        digest = str(b.get('source_sha256', ''))
        if digest not in sources: sources[digest] = len(sources) + 1
    out.append({'title': u['evidence'], 'paragraphs': [u['unverified']], 'columns': [lab('reference', language), lab('source_sha256', language)],
                'rows': [[str(i), d] for d, i in sources.items()], 'evidence_section': True})
    rows = [[str(b.get('fact_id', '')) + '\n' + str(b.get('pointer', '')) + '\n' + str(b.get('unit', '')),
             str(sources[str(b.get('source_sha256', ''))]) + ' / ' + str(b.get('segment_id', '')), str(b.get('quote', ''))] for b in bindings]
    out.append({'title': lab('quote', language), 'paragraphs': [], 'columns': [lab('fact_id', language), lab('reference', language), lab('quote', language)],
                'rows': rows, 'evidence_section': True})
    return out


def font_path():
    return Path(__file__).resolve().parent / 'fonts' / FONT_FILE


def _font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    raw = font_path().read_bytes()
    if hashlib.sha256(raw).hexdigest() != FONT_SHA256: raise ValueError('document_font_hash_mismatch')
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames(): pdfmetrics.registerFont(TTFont(FONT_NAME, io.BytesIO(raw)))
    return FONT_NAME


def docx_bytes(title, sections, language, review_evidence):
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc = Document(); section = doc.sections[0]
    section.page_width = Inches(8.5); section.page_height = Inches(11)
    section.top_margin = section.bottom_margin = Inches(.65); section.left_margin = section.right_margin = Inches(.7)
    normal = doc.styles['Normal']; normal.font.name = 'Arial'; normal.font.size = Pt(11); normal.paragraph_format.space_after = Pt(6)
    normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'), 'Microsoft YaHei')
    for style in ('Title', 'Heading 1', 'Heading 2'):
        doc.styles[style].font.color.rgb = RGBColor(0, 0, 0); doc.styles[style].font.name = 'Arial'
        props = doc.styles[style].element.find(qn('w:pPr'))
        if props is not None:
            for border in list(props.findall(qn('w:pBdr'))): props.remove(border)
    doc.core_properties.author = 'NABY'; doc.core_properties.title = title
    doc.add_paragraph(title, 'Title')
    for p in intro(language, review_evidence): doc.add_paragraph(display_text(p))
    for content in sections:
        doc.add_heading(content['title'], 1)
        for p in content.get('paragraphs', []): doc.add_paragraph(display_text(p))
        if content.get('rows'):
            columns = content.get('columns', [UI[language]['field'], UI[language]['value']])
            table = doc.add_table(rows=0, cols=len(columns)); table.style = 'Light Shading Accent 1'; table.autofit = False
            widths = content.get('widths', [2.3, 4.8] if len(columns) == 2 else [7.1 / len(columns)] * len(columns))
            for column, width in zip(table.columns, widths): column.width = Inches(width)
            header = table.add_row().cells
            for cell, label in zip(header, columns): cell.text = display_text(label)
            table.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
            for row in content['rows']:
                cells = table.add_row().cells
                for cell, value in zip(cells, row): cell.text = display_text(value)
            for row in table.rows:
                for cell in row.cells:
                    pr = cell._tc.get_or_add_tcPr()
                    margins = OxmlElement('w:tcMar')
                    for edge in ('top', 'left', 'bottom', 'right'):
                        item = OxmlElement('w:' + edge); item.set(qn('w:w'), '100'); item.set(qn('w:type'), 'dxa'); margins.append(item)
                    pr.append(margins)
                    borders = OxmlElement('w:tcBorders')
                    for edge in ('top', 'left', 'bottom', 'right'):
                        border = OxmlElement('w:' + edge); border.set(qn('w:val'), 'single'); border.set(qn('w:sz'), '4')
                        border.set(qn('w:color'), 'D9D9D9'); borders.append(border)
                    pr.append(borders)
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.space_after = Pt(3)
                        for run in paragraph.runs: run.font.size = Pt(9)
            doc.add_paragraph('')
    stream = io.BytesIO(); doc.save(stream); return stream.getvalue()


def pdf_bytes(title, sections, language, review_evidence):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, LongTable, TableStyle, CondPageBreak
    from reportlab.pdfbase import pdfmetrics
    font = _font(); face = pdfmetrics.getFont(font).face

    def safe(value):
        value = display_text(value)
        if any(ord(c) > 32 and ord(c) not in face.charToGlyph for c in value): raise ValueError('document_font_missing_glyph')
        return html.escape(value, quote=False).replace('\n', '<br/>')
    body = ParagraphStyle('b', fontName=font, fontSize=10, leading=13)
    head = ParagraphStyle('h', fontName=font, fontSize=13, leading=16, spaceBefore=6, spaceAfter=4)
    ttl = ParagraphStyle('t', fontName=font, fontSize=17, leading=21, spaceAfter=8)
    cell = ParagraphStyle('c', fontName=font, fontSize=8.5, leading=10.5)
    story = [Paragraph(safe(title), ttl)] + [Paragraph(safe(p), body) for p in intro(language, review_evidence)]
    for content in sections:
        story += [CondPageBreak(30 * mm), Paragraph(safe(content['title']), head)]
        story += [Paragraph(safe(p), body) for p in content.get('paragraphs', [])]
        if content.get('rows'):
            columns = content.get('columns', [UI[language]['field'], UI[language]['value']])
            data = [[Paragraph(safe(c), cell) for c in columns]] + [[Paragraph(safe(v), cell) for v in row] for row in content['rows']]
            widths = content.get('widths', [60, 120] if len(columns) == 2 else [180 / len(columns)] * len(columns))
            table = LongTable(data, colWidths=[w * mm for w in widths], repeatRows=1)
            table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, (0.85, 0.85, 0.85)), ('BACKGROUND', (0, 0), (-1, 0), (0.93, 0.93, 0.93)),
                                       ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            story += [table, Spacer(1, 4 * mm)]
    stream = io.BytesIO()
    SimpleDocTemplate(stream, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                      title=title, author='NABY').build(story)
    return stream.getvalue()


def xlsx_bytes(title, sections, language, review_evidence):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    wb = Workbook(); ws = wb.active; ws.title = 'Summary'
    ws.append([display_text(title)]); ws['A1'].font = Font(bold=True, size=13)
    for p in intro(language, review_evidence): ws.append([display_text(p)])
    ws.append([])
    used = {'Summary'}
    for content in sections:
        name = re.sub(r'[\[\]:*?/\\]', ' ', str(content['title']))[:28].strip() or 'Sheet'
        n = 1
        while name in used: n += 1; name = name[:25] + f' {n}'
        used.add(name)
        sh = wb.create_sheet(name)
        sh.append([display_text(content['title'])]); sh['A1'].font = Font(bold=True)
        for p in content.get('paragraphs', []): sh.append([display_text(p)])
        if content.get('rows'):
            columns = content.get('columns', [UI[language]['field'], UI[language]['value']])
            sh.append([display_text(c) for c in columns])
            for c in sh[sh.max_row]: c.font = Font(bold=True)
            for row in content['rows']: sh.append([display_text(v) for v in row])
            for col in sh.columns:
                width = max(len(str(c.value or '').split('\n')[0]) for c in col)
                sh.column_dimensions[col[0].column_letter].width = min(60, max(12, width + 2))
                for c in col: c.alignment = Alignment(wrap_text=True, vertical='top')
    stream = io.BytesIO(); wb.save(stream); return stream.getvalue()


def render(title, sections, language, review_evidence, formats=('docx', 'pdf', 'xlsx'), stem='draft', field_label=None):
    """Собрать файлы из секций пакета + общих разделов источников. -> {имя: bytes}."""
    sections = list(sections) + evidence_sections(review_evidence, language, field_label)
    writers = {'docx': docx_bytes, 'pdf': pdf_bytes, 'xlsx': xlsx_bytes}
    return {f'{stem}.{fmt}': writers[fmt](title, sections, language, review_evidence) for fmt in formats if fmt in writers}
