"""Structural engineering document UI. Source literals and exact values stay intact."""
import json
import re
from pathlib import Path

LANGUAGES=('ru','en','zh')
def tr(values,language):return values[LANGUAGES.index(language)]
_UI={
'draft':('Черновик инженерного анализа для проверки ответственным конструктором','Structural engineering draft for responsible engineer review','供责任结构工程师复核的工程分析草稿'),
'synthetic_banner':('Синтетический пример формата. Эти записи не являются фактическими данными объекта или разрешением работ.','Synthetic format example. These records are not actual project data or permission to work.','合成格式示例。这些记录不是实际项目资料或作业许可。'),
'source_note':('Исходные записи, названия, цитаты и авторские предложения сохранены на языке источника. Служебные подписи используют выбранный язык.','Original records, names, quotations and authored proposals retain their source language. Service labels use the selected language.','原始记录、名称、引文及作者建议保留来源语言。服务标签使用所选语言。'),
'unverified':('Совпадение цитаты и арифметическая проверка не устанавливают подлинность источника, применимость нормы, полноту модели или безопасность конструкции.','Quotation occurrence and arithmetic checks do not establish source authenticity, rule applicability, model completeness or structural safety.','引文出现及算术校核不确定来源真实性、规范适用性、模型完整性或结构安全性。'),
'verification_scope':('Отсутствие подтверждения в инструменте не означает, что человек не провёл отдельную проверку.','Lack of confirmation in the tool does not assert that a human performed no separate review.','工具未确认，不代表人员未进行单独复核。'),
'control_notice':('Управляющие символы источника показаны видимыми escape последовательностями; исходные значения сохранены в JSON и закрытом журнале источников.','Source control characters appear as visible escape sequences; original values remain in JSON and the private source record.','来源控制字符以可见转义序列显示；原值保留在JSON及私密来源记录中。'),
'precision_note':('Технические таблицы сохраняют точные арифметические записи. Количество показанных знаков не означает такую точность измерений или применимость модели.','Technical tables retain exact arithmetic records. Displayed digits do not imply that measurement precision or model applicability.','技术表保留精确算术记录；显示位数不代表测量具有该精度或模型适用。'),
'assumption_banner':('Ввод содержит явные допущения; их применимость требует отдельной инженерной проверки.','Inputs contain explicit assumptions; their applicability requires separate engineering review.','输入含明确假设；其适用性须单独进行工程复核。'),
'sources_unconfirmed':('В этом представлении нет привязанных фактов; проверьте выбранные исходные документы и журнал источников.','No bound facts are supplied in this view; review selected input documents and the source record.','本视图未提供绑定事实；请核查所选原始文件及来源记录。'),
'assumptions':('Допущения','Assumptions','假设'),'evidence':('Выбранные источники и проверка ввода','Selected sources and input checks','所选来源及输入校核'),
'field':('Показатель','Field','字段'),'value':('Значение','Value','数值'),'missing':('Не предоставлено','Not supplied','未提供'),
'none':('Нет записей в предоставленном наборе','No entries in the supplied set','所提供集合中无记录'),'details':('Сведения','Details','详细资料'),'items':('Записи','Records','记录'),
'yes':('Да','Yes','是'),'no':('Нет','No','否'),'page':('Страница','Page','页'),'as_of':('Дата информационного среза','Information cutoff date','信息截止日期'),
'calculation':('Результаты и проверки','Results and checks','结果与校核'),'summary':('Объект и область анализа','Object and analysis scope','对象与分析范围'),
'bounds':('Границы использования','Use limitations','使用边界'),'gaps':('Вопросы для ответственного специалиста','Questions for the responsible specialist','供负责专业人员处理的问题'),
'advice':('Материал не разрешает строительство, замену материалов или эксплуатацию, не присваивает категорию состояния, не выпускает чертежи и не подписывает документы.','This material does not authorise construction, material substitution or use, assign a condition category, issue drawings or sign documents.','本资料不授权施工、材料替代或使用，不评定状态类别，不签发图纸或签署文件。'),
'disclaimer_note':('Результаты относятся только к явно предоставленной схеме, данным и выбранным проверкам. Окончательные проектные решения и меры при опасных признаках определяет ответственный специалист.','Results apply only to the explicitly supplied scheme, data and selected checks. The responsible specialist determines final design decisions and measures for dangerous signs.','结果仅适用于明确提供的模型、数据及选定校核。最终设计决策及危险迹象的处置措施由负责专业人员确定。'),
}
UI={language:{key:tr(values,language) for key,values in _UI.items()} for language in LANGUAGES}
TITLES={
'loads_table':('Таблица сбора нагрузок и сочетаний','Load collection and combination table','荷载汇总与组合表'),
'calc_report':('Расчётное обоснование конструктивной схемы','Structural calculation justification','结构计算论证'),
'kr_explanatory':('Конструктивные решения текстовая часть','Structural solutions textual part','结构方案文字部分'),
'kr_checklist':('Проверка оформления конструктивных чертежей','Structural drawing documentation review','结构图纸编制核查'),
'inspection_report':('Черновик технического отчёта об обследовании','Technical inspection report draft','技术检查报告草稿'),
'expertise_answers':('Черновики ответов на замечания экспертизы','Expert review response drafts','审查意见答复草稿'),
'designer_answer':('Черновик ответа проектировщика стройке','Designer response to site draft','设计方现场答复草稿'),
}
FIELDS={}
TOKENS={
'not_established':('Не установлено','Not established','未确定'),
'not_calculated':('Не вычислялось для выбранных данных','Not calculated for selected data','未针对所选数据计算'),
'not_requested':('Ветвь не запрошена','Branch not requested','未请求该分支'),
'not_defined':('Не определено для выбранных данных','Undefined for selected data','对所选数据未定义'),
'not_applicable':('Указана неприменимость; основание требует проверки','Nonapplicability supplied; basis needs review','已提供不适用说明；依据须复核'),
}
ROOT=Path(__file__).parent
for resource in ('scenarios_ui_translations.json','calculation_ui_translations.json','member_ui_translations.json'):
    if (ROOT/resource).exists():TOKENS.update(json.loads((ROOT/resource).read_text(encoding='utf8')))
if (ROOT/'artifact_subject_labels.json').exists():
    data=json.loads((ROOT/'artifact_subject_labels.json').read_text(encoding='utf8'))
    FIELDS.update(data.get('fields',{}));TOKENS.update(data.get('tokens',{}))

def field_label(key,language):
    if '.' in str(key) or '@' in str(key):return ' / '.join(field_label(v,language) for v in str(key).replace('@','.').split('.'))
    if key in FIELDS:return tr(FIELDS[key],language)
    if key in TOKENS:return tr(TOKENS[key],language)
    if str(key).isdigit():return str(key)
    return UI[language]['field']+' ['+str(key)+']'

def token(value,language):
    if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',value):return value
    if re.fullmatch(r'\d+(?:[.\-/:]\d+)+',value):return value
    if value in TOKENS:return tr(TOKENS[value],language)
    for prefix,caption in (('context.',('Не установлен контекст','Context not established','背景未确定')),('properties.',('Не предоставлено свойство','Property not supplied','未提供属性'))):
        if value.startswith(prefix):return tr(caption,language)+' / '+field_label(value[len(prefix):],language)
    if ':' in value and value.split(':',1)[0] in TOKENS:
        base,detail=value.split(':',1);return tr(TOKENS[base],language)+' / '+field_label(detail,language)
    return value
