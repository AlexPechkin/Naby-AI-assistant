"""Embedded document UI. Exact numbers and source literals are never translated."""
import json,re
from pathlib import Path
LANGUAGES=('ru','en','zh')
def tr(values,language):
    if language not in LANGUAGES:raise ValueError('artifact_language_required')
    return values[LANGUAGES.index(language)]
ROOT=Path(__file__).parent
_UI=json.loads((ROOT/'artifact_ui.json').read_text(encoding='utf8'))
UI={language:{key:tr(values,language) for key,values in _UI.items()} for language in LANGUAGES}
FIELDS={}
TOKENS={
'not_established':('Инструмент не устанавливает','Not established by the tool','工具未确定'),
'not_calculated':('Не вычислялось для выбранных данных','Not calculated for selected data','未针对所选数据计算'),
'not_requested':('Ветвь не выбрана','Branch not selected','未选择该分支'),
'not_defined':('Не определено для выбранных данных','Undefined for selected data','对所选数据未定义'),
'not_applicable':('Указана неприменимость; основание требует проверки','Nonapplicability supplied; basis needs review','已提供不适用说明，依据须复核'),
}
for resource in ('architecture_code_ui_translations.json','debug_testing_ui_translations.json','lifecycle_ui_translations.json'):
    if (ROOT/resource).exists():
        data=json.loads((ROOT/resource).read_text(encoding='utf8'))
        TOKENS.update(data['tokens'] if type(data.get('tokens'))is dict else data)
if (ROOT/'artifact_subject_labels.json').exists():
    data=json.loads((ROOT/'artifact_subject_labels.json').read_text(encoding='utf8'))
    FIELDS.update(data.get('fields',{}));TOKENS.update(data.get('tokens',{}))
TEMPLATES=json.loads((ROOT/'artifact_templates.json').read_text(encoding='utf8'))
TITLES={key:value['title'] for key,value in TEMPLATES.items()}
def field_label(key,language):
    key=str(key)
    if key in FIELDS:return tr(FIELDS[key],language)
    if key in TOKENS:return tr(TOKENS[key],language)
    if key.isdigit():return key
    return UI[language]['field']+' ['+key+']'
def token(value,language):
    if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',value):return value
    if re.fullmatch(r'\d+(?:[.\-/:]\d+)+',value):return value
    if value in TOKENS:return tr(TOKENS[value],language)
    if ':' in value:
        base,detail=value.split(':',1)
        if base in TOKENS:return tr(TOKENS[base],language)+' / '+detail
    return value

