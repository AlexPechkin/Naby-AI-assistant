"""Localised investment document labels. Source text is preserved verbatim."""
LANGUAGES=('ru','en','zh')
def tr(values,language):return values[LANGUAGES.index(language)]

_UI={
 'draft':('Черновик инвестиционного анализа для проверки специалистом','Investment analysis draft for specialist review','供专业人员核查的投资分析草稿'),
 'source_note':('Цитаты, названия документов и введённые пользователем данные сохранены на языке источника. Подписи и пояснения документа используют выбранный язык.','Quotations, document names and user supplied data retain their source language. Document labels and explanations use the selected language.','引文、文件名称和用户提供的数据保留来源语言。文档标签及说明使用所选语言。'),
 'unverified':('Проверка присутствия цитаты и арифметики не подтверждает подлинность источника, полноту раскрытия или актуальность правовой нормы.','Quotation occurrence and arithmetic checks do not establish source authenticity, complete disclosure or current legal applicability.','引文出现及算术核查不证明来源真实性、披露完整性或法律规范的现行适用性。'),
 'assumption_banner':('Результат содержит явные допущения. Их нужно сверить до использования анализа.','The result includes explicit assumptions. Review them before using the analysis.','结果包含明确假设，使用分析前须核查。'),
 'sources_unconfirmed':('В этом представлении нет привязанных числовых фактов. Откройте выбранные источники и журнал проверки.','No bound numerical facts are supplied in this view. Review the selected sources and evidence record.','此视图未提供已绑定数值事实，请核查所选来源及证据记录。'),
 'assumptions':('Допущения','Assumptions','假设'),
 'evidence':('Источники и проверка ввода','Sources and input checks','来源及输入核查'),
 'field':('Показатель','Field','字段'),'value':('Значение','Value','数值'),
 'missing':('Не предоставлено','Not supplied','未提供'),'none':('Нет записей','No entries','无记录'),
 'details':('Сведения','Details','详细信息'),'items':('Записи','Records','记录'),
 'yes':('Да','Yes','是'),'no':('Нет','No','否'),'page':('Страница','Page','页'),
 'as_of':('Дата анализа','Analysis date','分析日期'),'calculation':('Результат','Result','结果'),
 'summary':('Основной результат','Main result','主要结果'),
 'bounds':('Границы использования','Use limitations','使用边界'),
 'advice':('Материал представляет сценарный анализ и подготовку документов. Он не создаёт поручение брокеру, не совершает сделки и не устанавливает статус инвестора. Индивидуальное соответствие инструмента клиенту здесь не определяется.','This material provides scenario analysis and document preparation. It does not create broker instructions, execute trades or establish investor status. It does not determine whether an instrument is suitable for an individual client.','本资料用于情景分析及文件准备，不生成经纪商指令、不执行交易，也不认定投资者资格，不判断工具是否适合特定客户。'),
 'disclaimer_note':('Оговорка сама по себе не меняет содержание сообщения и не подтверждает соблюдение требований к инвестиционному консультированию, рекламе или публикации.','A disclaimer alone does not change the substance of a communication or establish compliance with investment advice, advertising or publication rules.','仅有免责声明不能改变信息的实质，也不能证明符合投资咨询、广告或发布规则。'),
 'withheld':('Содержимое не включено в публичный черновик. Передайте вопрос уполномоченному комплаенсу по внутреннему защищённому каналу.','The content is withheld from the public draft. Refer the matter to authorised compliance using an internal protected channel.','内容未纳入公开草稿。请通过内部受保护渠道提交授权合规人员处理。'),
 'gaps':('Недостающие данные и следующие действия','Missing data and next steps','缺失资料及后续步骤'),
 'static':('Здесь сохранены результаты расчёта. После изменения входных данных повторно запустите инструмент NABY; автоматического пересчёта в этой книге нет.','This workbook stores calculation results. After changing inputs, rerun the NABY tool; this file does not recalculate automatically.','本工作簿保存计算结果。输入改变后请重新运行NABY工具，本文件不会自动重新计算。'),
}
UI={lang:{key:tr(value,lang) for key,value in _UI.items()} for lang in LANGUAGES}
TITLES={
 'issuer_card':('Карточка эмитента и раскрытия','Issuer and disclosure record','发行人及披露信息卡'),
 'model_workbook':('Финансовая модель и оценка компании','Financial model and company valuation','财务模型及公司估值'),
 'peer_table':('Сравнение эмитентов и мультипликаторов','Issuer and multiple comparison','发行人及估值倍数比较'),
 'bond_card':('Анализ облигации','Bond analysis','债券分析'),
 'research_note':('Аналитический обзор и инвестиционная идея','Research note and investment thesis','研究报告及投资逻辑'),
 'disclaimer':('Оговорки к аналитическому материалу','Analytical material disclosures','分析资料声明'),
 'qual_checklist':('Проверка требований к статусу инвестора','Investor status requirements review','投资者资格要求核查'),
 'compliance_checklist':('Проверка источников и конфликтов интересов','Source and conflict of interest review','来源及利益冲突核查'),
 'portfolio_memo':('Сценарный анализ модельного портфеля','Model portfolio scenario analysis','模型投资组合情景分析'),
 'tax_note':('Налоги инвестора и индивидуальные счета','Investor taxes and individual accounts','投资者税务及个人账户'),
}
FIELDS={
 'function':('Функция','Function','功能'),'as_of':('Дата анализа','Analysis date','分析日期'),
 'status':('Состояние','Status','状态'),'id':('Идентификатор','Identifier','标识符'),
 'name':('Наименование','Name','名称'),'kind':('Вид','Kind','类型'),'type':('Тип','Type','类型'),
 'issuer':('Эмитент','Issuer','发行人'),'inn':('ИНН','Tax identifier','税务识别号'),'ticker':('Тикер','Ticker','证券代码'),
 'period':('Период','Period','期间'),'data_date':('Дата данных','Data date','数据日期'),'date':('Дата','Date','日期'),
 'currency':('Валюта','Currency','币种'),'unit':('Единица','Unit','单位'),'value':('Значение','Value','数值'),
 'source_reference':('Ссылка на выбранный источник','Selected source reference','所选来源引用'),
 'reference':('Ссылка на источник','Source reference','来源引用'),'evidence_refs':('Выбранные источники','Selected sources','所选来源'),
 'source_references':('Выбранные источники','Selected sources','所选来源'),'source_sha256':('Контрольная сумма источника SHA256','Source SHA256 digest','来源SHA256摘要'),
 'segment_id':('Фрагмент источника','Source segment','来源片段'),'quote':('Цитата источника','Source quotation','来源引文'),'excerpt':('Выдержка источника','Source excerpt','来源摘录'),
 'pointer':('Путь входного показателя','Input field path','输入字段路径'),'fact_id':('Идентификатор факта','Fact identifier','事实标识'),
 'rationale':('Основание','Rationale','依据'),'verified':('Подтверждено проверкой','Verified by check','经核查确认'),
 'quote_verified':('Цитата найдена в выбранном фрагменте','Quotation found in selected segment','在所选片段中找到引文'),
 'semantic_mapping_verified':('Смысловое соответствие проверено','Semantic mapping verified','已验证语义对应'),
 'documents':('Первичные документы','Primary documents','原始文件'),'standard':('Стандарт отчётности','Reporting standard','报告准则'),
 'metrics':('Показатели','Metrics','指标'),'material_facts':('Существенные факты','Material facts','重大事实'),
 'ratings':('Рейтинги','Ratings','评级'),'agency':('Рейтинговое агентство','Rating agency','评级机构'),
 'disclosure_limitations':('Ограничения раскрытия','Disclosure limitations','披露限制'),
 'missing_primary_documents':('Недостающие первичные документы','Missing primary documents','缺失原始文件'),
 'gaps':('Пробелы','Gaps','缺失项'),'next_steps':('Следующие действия','Next steps','后续步骤'),
 'source_declarations_are_not_verification':('Заявления об источниках не являются подтверждением','Source declarations are not verification','来源声明不构成核实'),
 'input_sha256':('Контрольная сумма ввода SHA256','Input SHA256 digest','输入SHA256摘要'),
 'source_semantics_verified':('Смысловая достоверность источников установлена','Source semantics established','已确定来源语义可靠性'),
 'current_legal_applicability_verified':('Текущая правовая применимость установлена','Current legal applicability established','已确定现行法律适用性'),
 'external_actions':('Внешние действия выполнены','External actions performed','已执行外部操作'),
 'audience':('Аудитория','Audience','受众'),'publication_draft_allowed':('Публичный черновик разрешён','Public draft allowed','允许公开草稿'),
 'content_withheld':('Содержимое удержано','Content withheld','内容已保留不公开'),'narrative':('Текст анализа','Analysis narrative','分析文本'),
 'public_facts':('Публичные факты','Public facts','公开事实'),'thesis':('Тезис','Thesis','投资逻辑'),
 'valuation':('Оценка','Valuation','估值'),'risks':('Риски','Risks','风险'),'catalysts':('Катализаторы','Catalysts','催化剂'),
 'falsifiers':('Условия опровержения идеи','Thesis falsifiers','逻辑证伪条件'),
 'conflict_disclosure':('Раскрытие конфликта интересов','Conflict disclosure','利益冲突披露'),
 'sources':('Источники сведений','Information sources','信息来源'),'flags':('Выявленные признаки риска','Detected risk indicators','发现的风险迹象'),
 'publication_blocked':('Публикация заблокирована','Publication blocked','发布已阻止'),
 'sensitive_content_withheld':('Чувствительное содержимое удержано','Sensitive content withheld','敏感内容未公开'),
 'entity_type':('Вид лица','Entity type','主体类型'),'instrument':('Инструмент','Instrument','金融工具'),
 'instrument_review':('Проверка требований инструмента','Instrument requirements review','工具要求核查'),
 'criteria_groups':('Группы критериев','Criteria groups','条件组'),'criteria':('Критерии','Criteria','条件'),
 'testing':('Тестирование','Testing','测试'),'evidence_gaps':('Недостающие доказательства','Evidence gaps','缺失证据'),
 'qualification_decision':('Решение о статусе','Qualification decision','资格决定'),
 'income_type':('Вид дохода','Income type','收入类型'),'residency':('Налоговое резидентство','Tax residency','税务居民身份'),
 'tax_period':('Налоговый период','Tax period','纳税期间'),'account':('Счёт','Account','账户'),
 'mode':('Режим','Mode','模式'),'conditions':('Условия','Conditions','条件'),'calculation':('Расчёт','Calculation','计算'),
 'base_before_relief':('База до льгот','Base before relief','优惠前税基'),'base_after_relief':('База после льгот','Base after relief','优惠后税基'),
 'marginal_tax_before':('Налог до льгот','Tax before relief','优惠前税额'),'marginal_tax_after':('Налог после льгот','Tax after relief','优惠后税额'),
 'withheld_tax':('Удержанный налог','Tax withheld','已扣缴税额'),'balance_to_review':('Сумма для сверки','Balance for review','待核对余额'),
 'method':('Метод','Method','方法'),'amount':('Сумма','Amount','金额'),'rate':('Ставка','Rate','比率'),
 'effective_date':('Дата действия','Effective date','生效日期'),'published_at':('Дата публикации','Publication date','发布日期'),
 'result':('Результат','Result','结果'),'notes':('Примечания','Notes','说明'),'note':('Примечание','Note','说明'),
 'reason':('Причина','Reason','原因'),'included':('Включено в расчёт','Included in calculation','已纳入计算'),
 'excluded':('Исключено','Excluded','已剔除'),'exclusion_reasons':('Причины исключения','Exclusion reasons','剔除原因'),
 'count':('Количество','Count','数量'),'total':('Итого','Total','合计'),'label':('Обозначение','Label','标签'),
}
TOKENS={
 'issuer_disclosure':('Раскрытие эмитента','Issuer disclosure','发行人披露'),
 'valuation_model':('Модель оценки компании','Company valuation model','公司估值模型'),
 'peer_comparison':('Сравнение эмитентов','Peer comparison','同业比较'),
 'bond_analysis':('Анализ облигации','Bond analysis','债券分析'),
 'research_report':('Аналитический обзор','Research note','研究报告'),
 'investor_status':('Статус инвестора','Investor status','投资者资格'),
 'insider_compliance':('Проверка инсайда и конфликтов','Insider and conflict review','内幕及利益冲突核查'),
 'portfolio_scenarios':('Портфельные сценарии','Portfolio scenarios','投资组合情景'),
 'investor_tax':('Налоги инвестора','Investor taxes','投资者税务'),
 'unknown':('Не установлено','Unknown','未知'),'provided':('Предоставлено','Provided','已提供'),
 'missing':('Отсутствует','Missing','缺失'),'not_applicable':('Не применяется','Not applicable','不适用'),
 'public':('Публичный источник по заявлению','Declared public source','声明为公开来源'),
 'nonpublic':('Непубличный источник','Nonpublic source','非公开来源'),
 'internal':('Внутренний материал','Internal material','内部资料'),'public_channel':('Публичный канал','Public channel','公开渠道'),
 'resident':('Резидент','Resident','居民'),'nonresident':('Нерезидент','Nonresident','非居民'),
 'individual':('Физическое лицо','Individual','个人'),'legal_entity':('Юридическое лицо','Legal entity','法人'),
 'dividends':('Дивиденды','Dividends','股息'),'coupons':('Купоны','Coupons','票息'),
 'sale':('Продажа ценных бумаг','Securities sale','证券出售'),'brokerage':('Брокерский счёт','Brokerage account','经纪账户'),
 'iis3':('ИИС третьего типа','Type three individual investment account','第三类个人投资账户'),
 'fixed':('Фиксированный купон','Fixed coupon','固定票息'),'floating':('Плавающий купон','Floating coupon','浮动票息'),
 'maturity':('Погашение','Maturity','到期'),'offer':('Оферта','Offer','要约'),
 'base':('Базовый','Base','基础'),'optimistic':('Оптимистичный','Optimistic','乐观'),
 'pessimistic':('Пессимистичный','Pessimistic','悲观'),'RUB':('RUB','RUB','RUB'),
 'IFRS':('МСФО','IFRS','国际财务报告准则'),'RAS':('РСБУ','RAS','俄罗斯会计准则'),
 'not_meaningful':('Не имеет экономического смысла','Not meaningful','无经济意义'),
}
def field_label(key,language):
    if key in FIELDS:return tr(FIELDS[key],language)
    if str(key).replace('.','',1).replace('-','',1).isdigit():return str(key)
    # Technical identifiers are preserved so every input/output remains auditable.
    return UI[language]['field']+' ['+str(key)+']'
def token(value,language):
    if value in TOKENS:return tr(TOKENS[value],language)
    if value in FIELDS:return tr(FIELDS[value],language)
    for suffix,labels in DYNAMIC_SUFFIXES.items():
        if value.endswith(suffix):return value[:-len(suffix)]+' '+tr(labels,language)
    return value

from .artifact_labels_extra import FIELDS_EXTRA,TOKENS_EXTRA
FIELDS.update(FIELDS_EXTRA)
TOKENS.update(TOKENS_EXTRA)
from pathlib import Path
import json
TOKENS.update(json.loads((Path(__file__).parent/'scenarios_ui_translations.json').read_text(encoding='utf8')))
DYNAMIC_SUFFIXES={
 '_primary_document_not_provided':('Первичный документ не предоставлен','Primary document not supplied','未提供原始文件'),
 '_documentation_missing':('Документы отсутствуют','Documentation missing','缺失文件'),
 '_documentation_unknown':('Документы не установлены','Documentation unknown','文件未知'),
 '_restricted':('Раскрытие ограничено','Disclosure restricted','披露受限'),
 '_missing':('Отсутствует','Missing','缺失'),
}
