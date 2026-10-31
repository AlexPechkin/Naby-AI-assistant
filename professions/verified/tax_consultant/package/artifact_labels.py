"""Tax document labels. Original source strings never undergo path translation."""
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parent
LANGUAGES=('ru','en','zh')

def tr(values,language):
    if language not in LANGUAGES:raise ValueError('artifact_language_required')
    return values[LANGUAGES.index(language)]

def _read(name):
    value=json.loads((ROOT/name).read_text(encoding='utf-8'))
    if type(value)is not dict or any(type(k)is not str or type(v)is not list or len(v)!=3 or any(type(x)is not str or not x for x in v) for k,v in value.items()):raise ValueError('artifact_translation_resource_invalid')
    return value

FIELDS=_read('artifact_subject_labels.json')
UI_VALUES=_read('artifact_ui.json')
UI={language:{key:tr(value,language) for key,value in UI_VALUES.items()} for language in LANGUAGES}
TOKENS={}
TOKEN_CONFLICTS={}
for name in ('tax_models_ui_translations.json','tax_procedure_ui_translations.json','practice_ui_translations.json'):
    for key,value in _read(name).items():
        if key in TOKENS and TOKENS[key]!=value:TOKEN_CONFLICTS.setdefault(key,[]).append({'resource':name,'translation':value})
        TOKENS[key]=value
# Shared small enums are deliberately neutral across workflow contexts.
TOKENS.update({
    'unknown':['Не установлено по выбранным данным','Not established from selected data','根据所选资料未确定'],
    'provided':['Предоставлено в выбранной записи','Provided in the selected record','在所选记录中提供'],
    'not_selected':['Не выбрано','Not selected','未选择'],
    'none':['Не выбрано','Not selected','未选择'],
    'other':['Иная выбранная категория','Other selected category','其他所选类别'],
    'le':['Не больше','Less than or equal to','小于或等于'],
    'ge':['Не меньше','Greater than or equal to','大于或等于'],
    'scope':['Предоставленная область','Supplied scope','所提供范围']})
MISSING_FIELDS=set()
MISSING_TOKENS=set()
NUMBER=re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')

def field_label(key,language):
    if key not in FIELDS:
        MISSING_FIELDS.add(key)
        return key
    return tr(FIELDS[key],language)

def token(value,language,required=False):
    if type(value)is not str:return str(value)
    if NUMBER.fullmatch(value):return value
    if value in TOKENS:return tr(TOKENS[value],language)
    if required:
        MISSING_TOKENS.add(value)
        raise ValueError('artifact_control_token_missing')
    return value
