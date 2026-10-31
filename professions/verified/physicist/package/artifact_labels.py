"""Scientific draft labels; selected source text retains its original language."""
import json,re
from pathlib import Path
LANGUAGES=('ru','en','zh')
def tr(values,language):return values[LANGUAGES.index(language)]
_UI={
'draft':('Исследовательский черновик для проверки уполномоченным специалистом','Research draft for authorised specialist review','供授权专业人员核查的研究草稿'),
'source_note':('Названия, формулы, цитаты, исходные записи и авторские тексты сохранены на языке источника. Подписи и служебные пояснения используют выбранный язык.','Names, formulas, quotations, original records and authored text retain their original language. Labels and service explanations use the selected language.','名称、公式、引文、原始记录及作者文本保留原语言。标签及服务说明使用所选语言。'),
'unverified':('Совпадение цитаты и вычисленная арифметика не доказывают подлинность источника, физическую истинность модели, действующую редакцию нормы или полномочия.','Quotation occurrence and computed arithmetic do not establish source authenticity, physical truth of a model, current legal applicability or authority.','引文出现及算术计算不证明来源真实性、模型物理真实性、现行法律适用性或权限。'),
'verification_scope':('Флаг отсутствия подтверждения в этой модели не является утверждением об отсутствии отдельной проверки человеком.','A verification flag absent in this model does not assert that a human has performed no separate review.','此模型未确认验证，并不声称人员未进行单独审核。'),
'control_notice':('Управляющие символы исходного текста отображаются видимыми escape последовательностями; исходные значения сохранены в JSON и закрытом журнале выбранных источников.','Source control characters display as visible escape sequences; original values remain in JSON and the private selected-source record.','来源控制字符以可见转义序列显示，原值保留在JSON及所选来源私密记录中。'),
'assumption_banner':('Ввод содержит явные допущения. Их нужно проверить до использования результата.','Inputs contain explicit assumptions. Review them before using the result.','输入含明确假设，使用结果前须核查。'),
'sources_unconfirmed':('В этом представлении нет привязанных фактов. Проверьте выбранные первичные материалы и журнал источников.','No bound facts are supplied in this view. Review selected primary material and the source record.','此视图未提供绑定事实，请核查所选原始资料及来源记录。'),
'assumptions':('Допущения','Assumptions','假设'),'evidence':('Выбранные источники и проверка ввода','Selected sources and input checks','所选来源及输入核查'),
'field':('Показатель','Field','字段'),'value':('Значение','Value','数值'),'missing':('Не предоставлено','Not supplied','未提供'),
'none':('Нет записей','No entries','无记录'),'details':('Сведения','Details','详细资料'),'items':('Записи','Records','记录'),
'yes':('Да','Yes','是'),'no':('Нет','No','否'),'page':('Страница','Page','页'),'as_of':('Дата анализа','Analysis date','分析日期'),
'calculation':('Результат','Result','结果'),'summary':('Основной результат и область проверки','Main result and review scope','主要结果及审核范围'),
'bounds':('Границы использования','Use limitations','使用边界'),'gaps':('Пробелы и следующие действия','Gaps and next steps','缺口及后续步骤'),
'advice':('Материал содержит анализ выбранных данных и проекты документов. Он не управляет оборудованием, не разрешает запуск, не подтверждает безопасность, не выполняет подачу или публикацию и не устанавливает экспортную классификацию.','This material analyses selected data and prepares draft documents. It does not control equipment, authorise startup, establish safety, submit or publish material, or determine export classification.','本资料分析所选数据并准备文件草稿，不控制设备、不授权启动、不确定安全性、不提交或发表，也不认定出口分类。'),
'disclaimer_note':('Физическая применимость, метрологическая прослеживаемость, безопасность и окончательные решения требуют отдельной проверки компетентными лицами. Согласие с одной кривой не доказывает механизм.','Physical applicability, metrological traceability, safety and final decisions require separate competent review. Agreement with one curve does not prove a mechanism.','物理适用性、计量溯源、安全性及最终决定须由有资质人员单独核查。与单条曲线一致不证明机制。'),
}
UI={lang:{key:tr(values,lang) for key,values in _UI.items()} for lang in LANGUAGES}
TITLES={
'model_note':('Записка о физической модели','Physical model note','物理模型说明'),
'sim_protocol':('Протокол численного моделирования','Numerical modelling protocol','数值建模记录'),
'measurement_method':('Проект методики измерений','Measurement procedure draft','测量程序草稿'),
'exp_log':('Журнал эксперимента','Experiment log','实验日志'),
'uncertainty_budget':('Бюджет неопределённости измерений','Measurement uncertainty budget','测量不确定度预算'),
'rad_instruction':('Проект инструкции по радиационной безопасности','Radiation safety instruction draft','辐射安全规程草稿'),
'hazard_review':('Анализ опасностей установки','Facility hazard review','装置危险分析'),
'facility_proposal':('Проект заявки на время установки','Facility time proposal draft','装置机时申请草稿'),
'paper':('Проект рукописи статьи','Manuscript draft','论文草稿'),
'nir_report_phys':('Проект отчёта о научно исследовательской работе','Research and development report draft','研发报告草稿'),
}
FIELDS={};TOKENS={
'not_established':('Не установлено','Not established','未确定'),
'not_applicable':('Не применяется','Not applicable','不适用'),
'not_defined':('Не определено для выбранных данных','Undefined for selected data','对所选数据未定义'),
'not_calculated':('Не вычислялось','Not calculated','未计算'),
'unknown':('Не установлено','Unknown','未知'),
'provided':('Предоставлено','Supplied','已提供'),'missing':('Не предоставлено','Not supplied','未提供'),
'analysis_only':('Только вспомогательный анализ','Assisted analysis only','仅辅助分析'),
}
_path=Path(__file__).parent
for filename in ('artifact_subject_labels.json','scenarios_ui_translations.json'):
    if (_path/filename).exists():
        data=json.loads((_path/filename).read_text(encoding='utf8'))
        if filename=='artifact_subject_labels.json':FIELDS.update(data.get('fields',{}));TOKENS.update(data.get('tokens',{}))
        else:TOKENS.update(data)
# This shared domain status covers both supplied and conditionally calculated
# dates. Keep the reviewed neutral display text over the scenario default.
TOKENS['provided_date_not_legally_validated']=json.loads((_path/'artifact_subject_labels.json').read_text(encoding='utf8'))['tokens']['provided_date_not_legally_validated']
def field_label(key,language):
    if '.' in str(key) or '@' in str(key):return ' / '.join(field_label(part,language) for part in str(key).replace('@','.').split('.'))
    if key in FIELDS:return tr(FIELDS[key],language)
    if key in TOKENS:return tr(TOKENS[key],language)
    if str(key).replace('-','',1).replace('.','',1).isdigit():return str(key)
    return UI[language]['field']+' ['+str(key)+']'
def token(value,language):
    if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',value):return value
    if re.fullmatch(r'\d+(?:\.\d+){2,}',value):return value
    match=re.fullmatch(r'journal\.(\d+)\.time_and_offset',value)
    if match:return tr(('В записи журнала '+str(int(match[1])+1)+' нет явной пары времени и смещения UTC','Journal entry '+str(int(match[1])+1)+' lacks an explicit time and UTC offset pair','日志记录'+str(int(match[1])+1)+'缺少明确时间及UTC偏移对'),language)
    if value.startswith('lhs_observation_not_supplied:'):
        symbol=value.split(':',1)[1]
        return tr(('Наблюдение левой части '+symbol+' не предоставлено','Left-hand observation '+symbol+' not supplied','未提供左侧'+symbol+'观察'),language)
    match=re.fullmatch(r'observed_controls\.(\d+)\.(\w+)',value)
    if match:return tr(('Наблюдаемое средство защиты '+str(int(match[1])+1)+' состояние ','Observed protective control '+str(int(match[1])+1)+' state ','观察防护措施'+str(int(match[1])+1)+'状态'),language)+token(match[2],language)
    match=re.fullmatch(r'data_code\.([^.]+)\.(access|license_record)',value)
    if match:return tr(('Вопрос по данным или коду ','Data or code review question for ','数据或代码审核问题 '),language)+match[1]+' / '+field_label('access_record' if match[2]=='access' else 'license_record',language)
    if value.startswith('contributor.'):return tr(('Не предоставлено подтверждение согласия участника ','Contributor consent evidence not supplied for ','未提供贡献者同意证据 '),language)+value.split('.',1)[1]
    if value.startswith('export.') and value.split('.',1)[1] in FIELDS:return tr(('Вопрос экспортного контроля ','Export review question ','出口审核问题 '),language)+field_label(value.split('.',1)[1],language)
    if value in TOKENS:return tr(TOKENS[value],language)
    if value in FIELDS:return tr(FIELDS[value],language)
    if '.' in value and all(part in FIELDS or part.isdigit() for part in value.split('.')):return ' / '.join(field_label(part,language) for part in value.split('.'))
    return value
