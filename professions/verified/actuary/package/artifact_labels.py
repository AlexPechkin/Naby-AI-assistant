"""Actuarial draft UI; original source language, numbers and units stay literal."""
import json,re
from pathlib import Path
LANGUAGES=('ru','en','zh')
def tr(values,language):return values[LANGUAGES.index(language)]
_UI={
'draft':('Актуарный черновик для профессиональной проверки','Actuarial draft for professional review','供专业核查的精算草稿'),
'source_note':('Наименования, исходные записи, цитаты и авторские тексты сохранены на языке источника. Подписи и служебные пояснения используют выбранный язык.','Names, original records, quotations and authored text retain their source language. Labels and service explanations use the selected language.','名称、原始记录、引文及作者文本保留原语言。标签及服务说明使用所选语言。'),
'unverified':('Совпадение цитаты и вычисленная арифметика не доказывают подлинность источника, пригодность предположения, актуальность нормы, полноту данных или полномочия актуария.','Quotation occurrence and computed arithmetic do not establish source authenticity, assumption suitability, current legal applicability, data completeness or an actuary’s authority.','引文出现及算术计算不证明来源真实性、假设适用性、现行法律适用性、数据完整性或精算师权限。'),
'verification_scope':('Отсутствие подтверждения в этой модели не означает, что человек не выполнил отдельную проверку.','Lack of confirmation in this model does not assert that a human performed no separate review.','本模型缺少确认，不代表人员未进行单独核查。'),
'control_notice':('Управляющие символы исходного текста показаны видимыми escape последовательностями. Исходные значения сохраняются в JSON и закрытом журнале выбранных источников.','Source control characters display as visible escape sequences. Original values remain in JSON and the private selected-source record.','来源控制字符以可见转义序列显示。原值保留在JSON及所选来源私密记录中。'),
'assumption_banner':('Ввод содержит явные допущения. Их нужно проверить до использования результата.','Inputs contain explicit assumptions. Review them before using the result.','输入含明确假设，使用结果前须核查。'),
'sources_unconfirmed':('В этом представлении нет привязанных фактов. Проверьте выбранные первичные материалы и журнал источников.','No bound facts are supplied in this view. Review selected primary material and the source record.','此视图未提供绑定事实，请核查所选原始资料及来源记录。'),
'assumptions':('Допущения','Assumptions','假设'),'evidence':('Выбранные источники и проверка ввода','Selected sources and input checks','所选来源及输入核查'),
'field':('Показатель','Field','字段'),'value':('Значение','Value','数值'),'missing':('Не предоставлено','Not supplied','未提供'),
'none':('Нет записей','No entries','无记录'),'details':('Сведения','Details','详细资料'),'items':('Записи','Records','记录'),
'yes':('Да','Yes','是'),'no':('Нет','No','否'),'page':('Страница','Page','页'),'as_of':('Дата анализа','Analysis date','分析日期'),
'calculation':('Результат','Result','结果'),'summary':('Основание и область оценивания','Valuation basis and scope','评估依据及范围'),
'bounds':('Границы использования','Use limitations','使用边界'),'gaps':('Недостающие сведения и следующие действия','Gaps and next steps','缺失资料及后续步骤'),
'advice':('Материал содержит вспомогательный анализ и проекты документов. Он не утверждает тарифы, резервы или учётную политику, не подтверждает платёжеспособность и право практики, не подписывает и не отправляет документы.','This material contains assisted analysis and draft documents. It does not approve tariffs, reserves or accounting policy, establish solvency or practice rights, sign or submit documents.','本资料包含辅助分析及文件草稿，不批准费率、准备金或会计政策，不认定偿付能力或执业权，不签署或提交文件。'),
'disclaimer_note':('Выбор предположений, метода и итоговой оценки требует профессионального суждения и отдельного решения уполномоченных лиц. Арифметический результат не является актуарным заключением или утверждённой величиной.','Assumption, method and final valuation selection require professional judgement and a separate decision by authorised persons. Arithmetic output is not an actuarial conclusion or an approved amount.','假设、方法及最终评估的选择需要专业判断及获授权人员单独决定。算术结果不是精算结论或获批金额。'),
}
UI={language:{key:tr(values,language) for key,values in _UI.items()} for language in LANGUAGES}
TITLES={
'data_review':('Отчёт о проверке данных','Data review report','数据核查报告'),
'assumptions_memo':('Обоснование актуарных предположений','Actuarial assumptions memorandum','精算假设备忘录'),
'task':('Проект актуарного задания','Actuarial engagement draft','精算任务草稿'),
'tariff_note':('Актуарное обоснование тарифа','Actuarial tariff basis','精算费率依据'),
'reserve_report':('Расчёт страховых резервов','Insurance reserve calculation','保险准备金计算'),
'actuarial_report':('Проект актуарного отчёта','Actuarial report draft','精算报告草稿'),
'actuarial_conclusion':('Проект актуарного заключения по обязательному оцениванию','Mandatory valuation actuarial conclusion draft','法定评估精算结论草稿'),
'ifrs17_memo':('Записка по оценке МСФО 17','IFRS 17 measurement memorandum','IFRS 17计量备忘录'),
'stress_memo':('Стресс тест страховщика','Insurer stress review','保险公司压力核查'),
'status_checklist':('Чек лист требований к ответственному актуарию','Responsible actuary requirements checklist','责任精算师要求核查表'),
}
FIELDS={}
TOKENS={
'not_established':('Не установлено','Not established','未确定'),
'not_applicable':('Не применяется','Not applicable','不适用'),
'not_defined':('Не определено для выбранных данных','Undefined for selected data','对所选数据未定义'),
'not_calculated':('Не вычислялось','Not calculated','未计算'),
'unknown':('Не установлено','Unknown','未知'),
'analysis_only':('Только вспомогательный анализ','Assisted analysis only','仅辅助分析'),
}
_path=Path(__file__).parent
if (_path/'scenarios_ui_translations.json').exists():TOKENS.update(json.loads((_path/'scenarios_ui_translations.json').read_text(encoding='utf8')))
if (_path/'artifact_subject_labels.json').exists():
    data=json.loads((_path/'artifact_subject_labels.json').read_text(encoding='utf8'));FIELDS.update(data.get('fields',{}));TOKENS.update(data.get('tokens',{}))
def field_label(key,language):
    if '.' in str(key) or '@' in str(key):return ' / '.join(field_label(part,language) for part in str(key).replace('@','.').split('.'))
    if key in FIELDS:return tr(FIELDS[key],language)
    if key in TOKENS:return tr(TOKENS[key],language)
    if str(key).isdigit():return str(key)
    return UI[language]['field']+' ['+str(key)+']'
def token(value,language):
    # Numeric values, scientific notation, dates and dotted versions are data.
    if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',value):return value
    if re.fullmatch(r'\d+(?:[.\-/:]\d+)+',value):return value
    if value in TOKENS:return tr(TOKENS[value],language)
    if value.startswith('missing.'):
        return tr(('Отсутствует поле','Missing field','缺失字段'),language)+' / '+field_label(value.split('.',1)[1],language)
    if value.startswith('after_cutoff.'):
        return tr(('Дата после выбранного среза','Date after selected cutoff','日期晚于所选截止日'),language)+' / '+field_label(value.split('.',1)[1],language)
    if '.' in value and all(part in FIELDS or part.isdigit() for part in value.split('.')):return field_label(value,language)
    return value
