# Original passport titles and sections; retained exactly for contract compatibility.

TITLES = {
    "tnved_classification": {"ru": "Обоснование классификации по ТН ВЭД", "en": "TN VED classification rationale", "zh": "商品编码分类依据"},
    "customs_value": {"ru": "Декларация таможенной стоимости (ДТС-1) и расчёт", "en": "Customs value declaration (DTS-1) and calculation", "zh": "海关完税价格申报及计算"},
    "customs_payments": {"ru": "Расчёт таможенных платежей", "en": "Customs payments calculation", "zh": "海关税费计算"},
    "declaration": {"ru": "Декларация на товары (проверка)", "en": "Goods declaration review", "zh": "货物报关单核查"},
    "non_tariff": {"ru": "Чек-лист запретов, ограничений и техрегулирования", "en": "Restrictions and technical regulation checklist", "zh": "禁令、限制及技术法规检查表"},
    "origin": {"ru": "Документы о происхождении", "en": "Origin documents", "zh": "原产地文件"},
    "trade_contract": {"ru": "Разбор внешнеторгового контракта", "en": "Foreign trade contract review", "zh": "外贸合同审查"},
    "post_clearance": {"ru": "Ответ на запрос таможни / жалоба", "en": "Response to customs inquiry / appeal", "zh": "海关问询答复/申诉"},
    "shipping_docs": {"ru": "Комплект товаросопроводительных документов", "en": "Shipping document set", "zh": "货运单证清单"},
    "currency_docs": {"ru": "Документы валютного контроля", "en": "Currency control documents", "zh": "外汇管制文件"},
}

SECTION_TRANSLATIONS = {
    "Описание товара": ("Product description", "商品描述"), "Кандидаты кодов": ("Code candidates", "编码候选"), "Применение ОПИ": ("Application of GIR", "一般解释规则的适用"), "Решения и пояснения": ("Decisions and explanatory notes", "决定及解释说明"), "Вывод и риски": ("Conclusion and risks", "结论与风险"),
    "Сделка и стороны": ("Transaction and parties", "交易及当事方"), "Связанность": ("Related parties", "关联关系"), "Цена по инвойсу": ("Invoice price", "发票价格"), "Дополнительные начисления": ("Additions", "计入项目"), "Вычеты": ("Deductions", "扣除项目"), "Подтверждающие документы": ("Supporting documents", "证明文件"),
    "Инвойс": ("Invoice", "发票"), "Упаковочный лист": ("Packing list", "装箱单"), "Транспортный документ (CMR, коносамент, AWB, СМГС)": ("Transport document (CMR, bill of lading, AWB, rail waybill)", "运输单据"), "Спецификация": ("Specification", "规格单"), "Страховой полис": ("Insurance policy", "保险单"),
    "База": ("Base", "计税基础"), "Пошлина": ("Duty", "关税"), "Акциз": ("Excise", "消费税"), "НДС при ввозе": ("Import VAT", "进口增值税"), "Таможенный сбор": ("Customs fee", "海关规费"), "Итог и аванс на ЕЛС": ("Total and ELS advance", "合计及统一账户预付款"),
    "Процедура и стороны": ("Procedure and parties", "程序及当事方"), "Товар: код, описание, вес": ("Goods: code, description, weight", "货物：编码、描述、重量"), "Происхождение": ("Origin", "原产地"), "Стоимость и платежи": ("Value and payments", "价格及税费"), "Графа 44: документы": ("Box 44: documents", "第44栏：单证"),
    "Нетарифные меры": ("Non-tariff measures", "非关税措施"), "Технические регламенты ЕАЭС": ("EAEU technical regulations", "欧亚经济联盟技术法规"), "Санитарный, ветеринарный, фитоконтроль": ("Sanitary, veterinary and phytosanitary control", "卫生、兽医及植物检疫"), "Маркировка": ("Marking", "标识"), "Санкции и национальные запреты": ("Sanctions and national restrictions", "制裁及国家禁令"),
    "Сертификат/декларация происхождения": ("Origin certificate/declaration", "原产地证书/声明"), "Критерий происхождения": ("Origin criterion", "原产地标准"), "Прямая отправка": ("Direct shipment", "直接运输"), "Право на преференцию": ("Preference eligibility", "优惠资格"),
    "Стороны и право": ("Parties and governing law", "当事方及适用法律"), "Предмет и спецификации": ("Subject and specifications", "标的及规格"), "Incoterms 2020": ("Incoterms 2020", "国际贸易术语2020"), "Цена, валюта, оплата": ("Price, currency and payment", "价格、货币及付款"), "Документы и сроки": ("Documents and deadlines", "单证及期限"), "Форс-мажор и санкционные оговорки": ("Force majeure and sanctions clauses", "不可抗力及制裁条款"),
    "Постановка контракта на учёт (УНК)": ("Contract registration (UNC)", "合同登记"), "Сведения о валютных операциях": ("Currency operation details", "外汇业务信息"), "Справка о подтверждающих документах": ("Supporting documents statement", "证明文件清单"), "Сроки репатриации": ("Repatriation deadlines", "汇回期限"),
    "Реквизиты запроса или решения": ("Inquiry or decision details", "问询或决定信息"), "Перечень документов": ("Document list", "文件清单"), "Пояснения по пунктам": ("Explanations by item", "逐项说明"), "Правовое обоснование": ("Legal grounds", "法律依据"), "Приложения": ("Appendices", "附件"),
}

SECTIONS = {
    "tnved_classification": {"classification_note": ["Описание товара", "Кандидаты кодов", "Применение ОПИ", "Решения и пояснения", "Вывод и риски"]},
    "customs_value": {"dts": ["Сделка и стороны", "Связанность", "Цена по инвойсу", "Дополнительные начисления", "Вычеты", "Подтверждающие документы"], "shipping_docs": ["Инвойс", "Упаковочный лист", "Транспортный документ (CMR, коносамент, AWB, СМГС)", "Спецификация", "Страховой полис"]},
    "customs_payments": {"payments_calc": ["База", "Пошлина", "Акциз", "НДС при ввозе", "Таможенный сбор", "Итог и аванс на ЕЛС"]},
    "declaration": {"dt": ["Процедура и стороны", "Товар: код, описание, вес", "Происхождение", "Стоимость и платежи", "Графа 44: документы"], "shipping_docs": ["Инвойс", "Упаковочный лист", "Транспортный документ (CMR, коносамент, AWB, СМГС)", "Спецификация", "Страховой полис"]},
    "non_tariff": {"permits_checklist": ["Нетарифные меры", "Технические регламенты ЕАЭС", "Санитарный, ветеринарный, фитоконтроль", "Маркировка", "Санкции и национальные запреты"]},
    "origin": {"origin_pack": ["Сертификат/декларация происхождения", "Критерий происхождения", "Прямая отправка", "Право на преференцию"]},
    "trade_contract": {"contract_review": ["Стороны и право", "Предмет и спецификации", "Incoterms 2020", "Цена, валюта, оплата", "Документы и сроки", "Форс-мажор и санкционные оговорки"], "currency_docs": ["Постановка контракта на учёт (УНК)", "Сведения о валютных операциях", "Справка о подтверждающих документах", "Сроки репатриации"]},
    "post_clearance": {"response_to_customs": ["Реквизиты запроса или решения", "Перечень документов", "Пояснения по пунктам", "Правовое обоснование", "Приложения"]},
}

UI = {
 'ru': {'draft':'Проект для проверки человеком. Не подан, не подписан и не является официальной электронной формой ФТС.','missing':'Данные не предоставлены; требуется выбранный документ или уточнение.','none':'Отдельные строки не предоставлены. Отсутствие сведений не означает отсутствие обязанности или риска.','source_note':'Названия, ссылки и выдержки из выбранных материалов сохраняются на языке оригинала. Служебный текст документа приведён на выбранном языке.','unverified':'Подлинность документов, применимость норм и актуальность редакций этим документом не подтверждаются.','assumption_banner':'Сценарный расчёт: есть неподтверждённые допущения.','assumptions':'Неподтверждённые допущения','evidence':'Связь с выбранными источниками','field':'Показатель','value':'Значение','source':'Источник','rationale':'Обоснование','unit':'Единица','quote':'Выдержка из источника','sources_unconfirmed':'Связь значений с исходными файлами не подтверждена переданными данными.','as_of':'Дата среза','calculation':'Расчёт и ограничения','details':'Подробности','warnings':'Замечания и недостающие данные','yes':'Да','no':'Нет','unknown':'Не установлено','original':'Исходный текст','check_required':'Требуется проверка','status':'Статус','shipping_untyped':'Документы без установленного типа','xml_note':'XML представляет внутренний проект NABY. Формат ФТС не подтверждён; файл нельзя считать готовым к подаче.','amount_rub':'Сумма в рублях','conditional_value':'Условная арифметическая оценка, не установленная таможенная стоимость','total_value':'Таможенная стоимость по представленным условиям','fx_scenarios':'Сценарии изменения курса','rounding':'Округление','methods':'Проверка метода и ставок','page':'Страница','items':'Строки','appendices':'Приложения','deadline_notice':'Срок рассчитан по переданным условиям; действующая норма и календарь требуют отдельной проверки.'},
 'en': {'draft':'Draft for human review. Not submitted, not signed and not an official FCS electronic form.','missing':'Data not supplied; a selected document or clarification is required.','none':'No separate entries supplied. Missing information does not establish absence of an obligation or risk.','source_note':'Names, references and excerpts from selected materials retain their original language. Document service text uses the selected language.','unverified':'This document does not verify document authenticity, applicability of rules or current legal editions.','assumption_banner':'Scenario calculation: unverified assumptions are present.','assumptions':'Unverified assumptions','evidence':'Links to selected sources','field':'Item','value':'Value','source':'Source','rationale':'Rationale','unit':'Unit','quote':'Source excerpt','sources_unconfirmed':'The supplied data does not confirm value-to-source bindings.','as_of':'Cutoff date','calculation':'Calculation and limitations','details':'Details','warnings':'Review notes and missing data','yes':'Yes','no':'No','unknown':'Not established','original':'Original text','check_required':'Verification required','status':'Status','shipping_untyped':'Documents without an established type','xml_note':'This XML is an internal NABY draft. The FCS schema is not verified; this file is not ready for submission.','amount_rub':'Amount in RUB','conditional_value':'Conditional arithmetic estimate, not an established customs value','total_value':'Customs value under the supplied conditions','fx_scenarios':'Exchange-rate scenarios','rounding':'Rounding','methods':'Method and rate checks','page':'Page','items':'Entries','appendices':'Appendices','deadline_notice':'The deadline uses supplied conditions; the applicable rule and calendar require separate verification.'},
 'zh': {'draft':'供人工审核的草案。尚未提交、未签署，也并非俄罗斯海关正式电子表格。','missing':'未提供数据；需要选择相关文件或补充说明。','none':'未提供单独条目。资料缺失不代表不存在义务或风险。','source_note':'所选资料中的名称、引用和摘录保留原文语言。文档提示文字使用所选语言。','unverified':'本文档不证明文件真实性、规则适用性或法规版本的现行效力。','assumption_banner':'情景计算：存在未经核实的假设。','assumptions':'未经核实的假设','evidence':'所选来源关联','field':'项目','value':'数值','source':'来源','rationale':'依据','unit':'单位','quote':'原文摘录','sources_unconfirmed':'所提供数据尚未确认数值与原始文件的关联。','as_of':'资料截止日期','calculation':'计算与限制','details':'详细信息','warnings':'待核查事项与缺失资料','yes':'是','no':'否','unknown':'尚未确定','original':'原始文本','check_required':'需要核实','status':'状态','shipping_untyped':'类型未确定的文件','xml_note':'此 XML 仅为 NABY 内部草案，未核实俄罗斯海关格式，不可视为可直接申报的文件。','amount_rub':'金额（卢布）','conditional_value':'条件性算术估计，并非已确定的海关完税价格','total_value':'按所提供条件计算的海关完税价格','fx_scenarios':'汇率情景','rounding':'舍入规则','methods':'方法与税率核查','page':'页','items':'条目','appendices':'附件','deadline_notice':'期限按所提供条件计算；适用规则及日历仍需独立核实。'}
}

# Tuples are RU, EN, ZH. Technical identifiers and exact source quotations are not translated.
FIELDS = {
 'name':('Наименование','Name','名称'),'composition':('Состав и материалы','Composition and materials','组成与材料'),'purpose':('Назначение','Purpose','用途'),'principle':('Принцип работы','Operating principle','工作原理'),'completeness':('Комплектность','Completeness','完整性'),
 'code':('Код','Code','编码'),'tnved_code':('Код ТН ВЭД','TN VED code','商品编码'),'arguments':('Аргументы','Arguments','论据'),'impact':('Влияние выбора кода','Impact of code selection','编码选择影响'),'opi':('ОПИ','GIR','一般解释规则'),'rule':('Правило','Rule','规则'),'rule_checks':('Проверки ОПИ','GIR checks','解释规则核查'),'rationale':('Обоснование','Rationale','依据'),'evidence_refs':('Ссылки на факты','Evidence references','证据引用'),'source_reference':('Источник','Source reference','来源引用'),'status':('Статус','Status','状态'),
 'parties':('Стороны','Parties','当事方'),'incoterms':('Базис Incoterms','Incoterms basis','贸易术语'),'related_parties':('Заявлена связанность сторон','Related parties declared','声明存在关联关系'),'price_original':('Цена по инвойсу','Invoice price','发票价格'),'currency':('Валюта','Currency','币种'),'fx_rate':('Курс пересчёта','Conversion rate','换算汇率'),'declaration_date':('Дата регистрации ДТ','Declaration registration date','报关单登记日期'),'original':('Исходная сумма','Original amount','原币金额'),'rub':('Сумма в рублях','Amount in RUB','卢布金额'),'kind':('Вид','Type','类型'),'tracks_base_fx':('Курс следует сценарию инвойса','Rate follows invoice scenario','汇率随发票情景变化'),
 'method':('Метод','Method','方法'),'method1_supported':('Условия метода 1 подтверждены представленными данными','Method 1 supported by supplied data','所提供数据支持方法一'),'method1_conditions':('Условия метода 1','Method 1 conditions','方法一条件'),'method1_issues':('Проблемы применения метода 1','Method 1 issues','方法一待解决问题'),'value_rub':('Таможенная стоимость в рублях','Customs value in RUB','卢布完税价格'),'candidate_value_rub':('Условный результат в рублях','Conditional result in RUB','条件性卢布结果'),'value_rub_unrounded':('До округления','Before rounding','舍入前'),'assumption':('Допущение','Assumption','假设'),'value':('Значение','Value','数值'),
 'customs_value_rub':('Таможенная стоимость в рублях','Customs value in RUB','卢布完税价格'),'duty':('Пошлина','Duty','关税'),'duty_formula':('Формула пошлины','Duty formula','关税公式'),'excise':('Акциз','Excise','消费税'),'excise_formula':('Формула акциза','Excise formula','消费税公式'),'vat_base':('База НДС','VAT base','增值税计税基础'),'vat_rate_percent':('Ставка НДС, %','VAT rate, %','增值税税率（%）'),'vat':('НДС','VAT','增值税'),'customs_fee':('Таможенный сбор','Customs fee','海关规费'),'special_duties':('Особые пошлины','Special duties','特别关税'),'total_advance_els':('Итог к авансу на ЕЛС','Total ELS advance','统一账户预付款合计'),'quantity':('Количество','Quantity','数量'),'rate_checks':('Проверки ставок','Rate checks','税率核查'),'rounding':('Округление','Rounding','舍入'),'breakdown':('Разбивка расчёта','Calculation breakdown','计算明细'),'amount':('Сумма','Amount','金额'),'amount_per_unit':('Ставка за единицу','Amount per unit','每单位金额'),'rate_percent':('Ставка, %','Rate, %','税率（%）'),'unit_currency_rate':('Курс валюты ставки','Rate currency conversion','税率币种换算'),'mode':('Способ расчёта','Calculation mode','计算方式'),
 'procedure':('Таможенная процедура','Customs procedure','海关程序'),'description':('Описание','Description','描述'),'net_weight_kg':('Вес нетто, кг','Net weight, kg','净重（公斤）'),'gross_weight_kg':('Вес брутто, кг','Gross weight, kg','毛重（公斤）'),'origin_country':('Страна происхождения','Country of origin','原产国'),'payments':('Платежи','Payments','税费'),'field':('Поле','Field','字段'),'declaration':('В ДТ','In declaration','报关单数值'),'source':('В источнике','In source','来源数值'),'release_deadline':('Расчётный срок выпуска','Calculated release deadline','计算的放行期限'),'registration_timestamp_required':('Нужно время регистрации с часовым поясом','Registration timestamp with timezone required','需要含时区的登记时间'),'adjustment_stage':('Этап корректировки','Adjustment stage','修改阶段'),'documents':('Документы','Documents','文件'),'g44_documents':('Документы графы 44','Box 44 documents','第44栏文件'),
 'number':('Номер','Number','编号'),'date':('Дата','Date','日期'),'issuer':('Выдавшая сторона','Issuer','签发方'),'exporter':('Экспортёр','Exporter','出口方'),'importer':('Импортёр','Importer','进口方'),'policy_number':('Номер полиса','Policy number','保险单号'),'carrier':('Перевозчик','Carrier','承运人'),'route':('Маршрут','Route','路线'),'places':('Количество мест','Packages','件数'),'insured_amount':('Страховая сумма','Insured amount','保险金额'),
 'topic':('Проверяемый вопрос','Review topic','核查事项'),'requirement':('Требование','Requirement','要求'),'required':('Необходимость','Required','是否需要'),'checked_at':('Заявленная дата проверки','Declared check date','声明的核查日期'),'end_recipient':('Конечный получатель','End recipient','最终收货方'),'direction':('Направление','Direction','方向'),'manufacture_country':('Страна производства','Manufacturing country','生产国'),'criterion':('Критерий','Criterion','标准'),'heading_changed':('Смена товарной позиции','Tariff heading change','税目变化'),'sufficient_processing':('Достаточная переработка по представленным условиям','Sufficient processing under supplied conditions','所提供条件下的充分加工'),'direct_shipment':('Прямая отправка','Direct shipment','直接运输'),'preference_eligible_preliminary':('Предварительное право на преференцию','Preliminary preference eligibility','初步优惠资格'),'criteria_results':('Проверки критериев','Criteria checks','标准核查'),'agreement':('Соглашение','Agreement','协定'),'value_content':('Стоимостный критерий','Value-content criterion','价值含量标准'),'non_origin_value':('Стоимость неоригинарных материалов','Non-originating material value','非原产材料价值'),'total_material_value':('Общая стоимость материалов','Total material value','材料总价值'),
 'clause_checks':('Проверки условий контракта','Contract clause checks','合同条款核查'),'quote':('Выдержка из источника','Source excerpt','原文摘录'),'analysis':('Анализ','Analysis','分析'),'amount_original':('Сумма в валюте контракта','Amount in contract currency','合同币种金额'),'amount_rub':('Рублёвый эквивалент','RUB equivalent','卢布等值'),'bank_registration_required_preliminary':('Предварительная необходимость учёта в банке','Preliminary bank registration requirement','初步银行登记要求'),'bank_registration_threshold_rub':('Переданный порог учёта, руб.','Supplied registration threshold, RUB','所提供登记门槛（卢布）'),'bank_rule':('Переданное правило банка','Supplied bank rule','所提供银行规则'),'repatriation_dates':('Условия и даты репатриации','Repatriation conditions and dates','汇回条件及日期'),'missing_or_unclear_sections':('Неясные или отсутствующие условия','Missing or unclear clauses','缺失或不明条款'),
 'request':('Текст запроса или решения','Inquiry or decision text','问询或决定文本'),'received_date':('Дата получения','Receipt date','收到日期'),'response_deadline':('Расчётный срок ответа','Calculated response deadline','计算的答复期限'),'deadline_rule':('Переданное правило срока','Supplied deadline rule','所提供期限规则'),'calendar':('Календарь расчёта','Calculation calendar','计算日历'),'requested':('Что запрошено','Requested item','所要求项目'),'available_reference':('Имеющийся документ','Available document','现有文件'),'explanation':('Пояснение','Explanation','说明'),'legal_arguments':('Правовые аргументы для проверки','Legal arguments for review','待核实法律论据'),'penalty':('Сценарный расчёт пеней','Scenario penalty calculation','滞纳金情景计算'),'principal':('Недоимка','Principal arrears','欠款本金'),'annual_rate_percent':('Годовая ставка, %','Annual rate, %','年利率（%）'),'days':('Дни','Days','天数'),'formula':('Формула','Formula','公式'),'periods':('Периоды','Periods','期间'),'start':('Начало','Start','开始'),'end':('Конец','End','结束'),'fraction_numerator':('Числитель доли','Fraction numerator','分数分子'),'fraction_denominator':('Знаменатель доли','Fraction denominator','分数分母'),
 'effective_from':('Действует с (заявлено)','Effective from (declared)','声明的生效日'),'effective_to':('Действует до (заявлено)','Effective until (declared)','声明的失效日'),'edition':('Редакция','Edition','版本'),'unit':('Единица','Unit','单位'),'pointer':('Путь показателя','Value path','数值路径'),'verified':('Подтверждено','Verified','已核实'),'source_sha256':('SHA256 источника','Source SHA256','来源SHA256'),'segment_id':('Сегмент источника','Source segment','来源片段'),'fact_id':('Идентификатор факта','Fact identifier','事实标识'),'fact':('Факт','Fact','事实'),'currency_documents':('Документы валютного контроля','Currency-control documents','外汇管制文件')
}

TOKENS = {
 'unknown':('Не установлено','Not established','尚未确定'),'not_applicable':('Заявлена неприменимость','Declared not applicable','声明不适用'),'review_required':('Требуется проверка','Review required','需要核查'),'verified':('Заявлено как проверенное; требуется проверка источника','Declared verified; source review required','声明已核实，仍需审查来源'),'confirmed':('Подтверждение заявлено, но не удостоверено документом','Confirmation declared, not authenticated here','声明已确认，但本文档不予认证'),'missing':('Нет данных','Missing data','资料缺失'),'provided':('Предоставлено','Supplied','已提供'),'not_checked':('Не проверено','Not checked','未核查'),'pass':('Условие выполнено по входным данным','Condition met using supplied inputs','按输入条件满足'),'fail':('Условие не выполнено','Condition not met','条件不满足'),'met':('Выполнено по входным данным','Met using supplied inputs','按输入满足'),'not_met':('Не выполнено','Not met','未满足'),'true':('Да','Yes','是'),'false':('Нет','No','否'),
 'proposal_pending_current_nomenclature_check':('Предложение; нужна сверка действующей ТН ВЭД','Proposal pending current nomenclature verification','建议编码，待核对现行商品目录'),'full_production':('Полностью произведённый товар','Wholly obtained goods','完全获得货物'),'sufficient_processing':('Достаточная переработка','Sufficient processing','充分加工'),'import':('Ввоз','Import','进口'),'export':('Вывоз','Export','出口'),'before_release':('До выпуска','Before release','放行前'),'after_release':('После выпуска','After release','放行后'),'human_only':('Только человек','Human only','仅由人工执行'),'ad_valorem':('Адвалорная','Ad valorem','从价'),'specific':('Специфическая','Specific','从量'),'combined_max':('Комбинированная, наибольшая из сумм','Combined, maximum component','复合税率，取较大额'),'combined_sum':('Комбинированная, сумма компонентов','Combined, sum of components','复合税率，各项相加'),'ROUND_HALF_UP':('До ближайшего с округлением половины вверх','Round half up','四舍五入'),'caller_declared':('Заявлено составителем','Caller-declared','编制者声明'),'pending_verification':('Ожидает проверки','Pending verification','待核实'),
 'license_or_permit_review':('Проверить лицензии и разрешения','Check licences and permits','核查许可文件'),'encryption_notification':('Проверить нотификацию шифровальных средств','Check encryption notification','核查加密通知'),'no_encryption_declared':('Шифрование не заявлено; это не заключение','Encryption not declared; not a conclusion','未声明加密，不构成结论'),'registry_check_required':('Нужна проверка в реестре','Registry verification required','需要登记库核查'),'veterinary_review':('Нужна ветеринарная проверка','Veterinary review required','需要兽医核查'),'not_declared_animal':('Животное происхождение не заявлено','Animal origin not declared','未声明动物来源'),'phytosanitary_review':('Нужна фитосанитарная проверка','Phytosanitary review required','需要植物检疫核查'),'not_declared_plant':('Растительное происхождение не заявлено','Plant origin not declared','未声明植物来源'),'chestny_znak_before_import':('Проверить маркировку до ввоза','Check marking before import','核查进口前标识'),'marked_goods_not_declared':('Принадлежность к маркируемым товарам не установлена','Marking applicability not established','尚未确定标识适用性'),'destination_origin_end_user_review':('Проверить страны и конечного получателя','Review countries and end user','核查国家和最终用户'),'no_legality_conclusion':('Заключение о законности не выдаётся','No legality conclusion','不作合法性结论')
}

def localized_section(name,language):
    if language=='ru':return name
    return SECTION_TRANSLATIONS[name][0 if language=='en' else 1]

TOKENS.update({
 'administrative':('Административное обжалование','Administrative appeal','行政申诉'),
 'judicial':('Судебное обжалование','Judicial appeal','司法申诉'),
 'documents_deadlines':('Документы и сроки','Documents and deadlines','单证及期限'),
 'force_majeure_sanctions':('Форс-мажор и санкционные условия','Force majeure and sanctions clauses','不可抗力及制裁条款'),
 'national_restrictions':('Национальные ограничения','National restrictions','国家限制措施'),
 'parties_law':('Стороны и применимое право','Parties and governing law','当事方及适用法律'),
 'photo_reference':('Фотография товара','Product photograph','商品照片'),
 'price_currency_payment':('Цена, валюта и оплата','Price, currency and payment','价格、货币及付款'),
 'subject_specifications':('Предмет и спецификации','Subject and specifications','标的及规格'),
 'caller_declared_not_authenticated':('Заявлено во входных данных, подлинность не проверена','Declared in the inputs; authenticity not verified','由输入数据声明，真实性未经核实'),
 'fee_once_per_declaration_not_per_item':('Сбор учитывается один раз на декларацию, а не на каждую товарную позицию','The fee applies once per declaration, not once per item','规费按每份报关单计一次，不按每个商品项目重复计收'),
 'insurance_before_arrival':('Страхование до места прибытия','Insurance before arrival','到达前的保险费用'),
 'transport_before_arrival':('Перевозка до места прибытия','Transport before arrival','到达前的运输费用'),
 'transport_after_arrival':('Перевозка после места прибытия','Transport after arrival','到达后的运输费用'),
 'invoice_currency_only_sensitivity_not_forecast_or_official_fx':('Чувствительность к курсу валюты инвойса; это не прогноз и не официальный курс','Sensitivity to the invoice currency rate; not a forecast or official exchange rate','仅分析发票币种汇率敏感性；不是预测或官方汇率'),
 'not_a_payment_order_or_final_declaration':('Это не платёжное поручение и не окончательная декларация','Not a payment order or a final declaration','不是付款指令或最终报关单'),
 'preferences_exemptions_require_source_review':('Преференции и освобождения требуют проверки источников','Preferences and exemptions require a source review','优惠和豁免需要核查依据'),
 'recycling_fee_penalties_storage_and_broker_fees_excluded':('Утильсбор, пени, хранение и услуги представителя не включены','Recycling fees, penalties, storage and broker fees are excluded','不包括回收费、滞纳金、仓储费和报关代理费'),
 'round_value_then_duty_then_excise_then_vat_sum_rounded_components':('Последовательно округляются стоимость, пошлина, акциз и НДС; итог складывается из округлённых сумм','Round value, duty, excise and VAT in order, then sum the rounded components','依次舍入完税价格、关税、消费税和增值税，然后汇总已舍入金额'),
 'special_duties_and_fee_excluded_from_vat_base':('Специальные пошлины и таможенный сбор не включены в указанную базу НДС','Special duties and the customs fee are excluded from the stated VAT base','列示的增值税计税基础不包括特别关税和海关规费'),
 'special_duties_supplied_amount_not_tariff_resolution':('Специальные пошлины заданы суммой; применимость тарифа не устанавливалась','Special duties are supplied as an amount; tariff applicability was not determined','特别关税按提供的金额计入；未确定其税率适用性'),
 'regional_content':('Доля региональной стоимости','Regional value content','区域价值成分'),
 'tariff_shift':('Изменение тарифной классификации','Change in tariff classification','税则归类改变'),
 'value_content':('Стоимостный критерий происхождения','Origin value-content criterion','原产地价值成分标准')
})

_EXTRA_FIELDS='''ad_valorem_unrounded|Адвалорная часть до округления|Ad-valorem component before rounding|从价部分未舍入金额
additions_complete|Полнота дополнительных начислений|Completeness of additions|计入项目的完整性
amount_unrounded|Сумма до округления|Amount before rounding|未舍入金额
animal_origin|Продукция животного происхождения|Animal-origin product|动物源产品
applied|Учтено в расчёте|Included in calculation|已计入计算
argument|Довод|Argument|理由
combination|Сочетание критериев|Combination of criteria|标准组合方式
comparator|Условие сравнения|Comparison operator|比较条件
compared_fields|Сопоставленные поля|Compared fields|已核对字段
country|Страна|Country|国家
country_eligible|Страна отвечает условиям|Country eligibility|国家资格条件
criteria|Критерии|Criteria|标准
current_edition_verified|Текущая редакция подтверждена|Current edition verified|现行版本已确认
customs_value|Таможенная стоимость|Customs value|海关完税价格
customs_value_rub_input|Исходная стоимость в рублях|Input customs value in RUB|输入的卢布完税价格
day_kind|Тип дней|Day type|日期类型
deadline_method|Метод расчёта срока|Deadline calculation method|期限计算方法
declared_features|Заявленные признаки|Declared features|声明的特征
denominator_basis|База знаменателя|Denominator basis|分母基础
denominator_value|Значение знаменателя|Denominator value|分母值
details|Подробности|Details|详细信息
digits|Уровень сравнения кода|Code comparison level|编码比较层级
direct_shipment_required|Прямая отправка обязательна|Direct shipment required|要求直接运输
document|Документ|Document|文件
document_required|Документ обязателен|Document required|要求文件
documented_separately|Подтверждено отдельно|Separately documented|单独提供证明
documents_sufficient|Достаточность документов|Document sufficiency|文件充分性
due_date|Срок исполнения|Due date|履行期限
duty_breakdown|Расшифровка пошлины|Duty breakdown|关税明细
encryption|Шифрование|Encryption|加密功能
excise_breakdown|Расшифровка акциза|Excise breakdown|消费税明细
final_classification|Окончательная классификация|Final classification|最终归类
final_origin_determination|Окончательное определение происхождения|Final origin determination|最终原产地认定
fx_date|Дата курса|Exchange-rate date|汇率日期
fx_details|Основание пересчёта валюты|Currency conversion details|货币换算依据
fx_nominal|Номинал котировки|Quote nominal|报价基数
fx_scenarios|Сценарии курса|Exchange-rate scenarios|汇率情景
fx_source_reference|Источник курса|Exchange-rate source|汇率来源
goods_eligible|Товар отвечает условиям|Goods eligibility|商品资格条件
id|Идентификатор|Identifier|标识符
include_received_day|Включать день получения|Include receipt day|计入收到当日
included_in_price|Уже включено в цену|Already included in price|已计入价格
incoterms_place|Место поставки по Incoterms|Incoterms named place|贸易术语指定地点
legality_conclusion|Заключение о законности|Legal-clearance conclusion|合法性结论
limitations|Границы расчёта|Calculation limits|计算范围限制
marked_goods|Товар подлежит маркировке|Goods subject to marking|需标识商品
materials|Материалы|Materials|材料
met|Условие выполнено по входным данным|Condition met under supplied data|按输入数据满足条件
metadata_status|Статус сведений об источнике|Source metadata status|来源元数据状态
method_source|Источник метода|Method source|方法依据
mismatches|Расхождения|Discrepancies|差异
missing_product_documents|Недостающие документы товара|Missing product documents|缺失的商品文件
multiplier|Множитель сценария|Scenario multiplier|情景乘数
nomenclature|Номенклатура|Nomenclature|商品目录
nonorigin_value|Стоимость непроисходящих материалов|Non-originating material value|非原产材料价值
official_checks|Источники для проверки|Sources to check|待核查来源
official_lists_verification_required|Нужна сверка официальных перечней|Official lists require verification|需要核查官方清单
originating|Материал имеет происхождение по выбранному правилу|Material originates under selected rule|材料符合选定原产地规则
other_conditions_met|Прочие условия выполнены|Other conditions met|其他条件已满足
per_units|База количества для ставки|Quantity basis of rate|税率数量基数
percent|Процент|Percent|百分比
permitted_restrictions_only|Только допустимые ограничения|Only permitted restrictions|仅存在允许的限制
photo_reference|Фотография товара|Product photograph|商品照片
plant_origin|Продукция растительного происхождения|Plant-origin product|植物源产品
preference_conditions|Условия преференции|Preference conditions|优惠条件
preliminary_decision_recommended|Рекомендуется предварительное решение|Advance decision recommended|建议申请预裁定
price_source_reference|Источник цены|Price source|价格来源
quantifiable|Сумма определима|Quantifiable amount|金额可量化
quantifiable_conditions|Условия поддаются оценке|Conditions can be valued|条件可估值
quantity_unit|Единица количества|Quantity unit|数量单位
quantum|Шаг округления|Rounding increment|舍入单位
rate_and_days_verification_required|Нужна проверка ставок и дней|Rates and days require verification|需核查费率和天数
rate_unit|Единица ставки|Rate unit|税率单位
reference|Источник|Source|依据
refresh_due|Пора повторно проверить источник|Source recheck due|应重新核查来源
regime|Режим происхождения|Origin regime|原产地制度
related_price_acceptable|Влияние связи сторон исключено по данным|Related-party price acceptable under supplied data|按输入数据关联交易价格可接受
release_rule|Правило срока выпуска|Release deadline rule|放行期限规则
replacement_plan|Как получить недостающее|Plan to obtain missing evidence|获取缺失证据的计划
response_days|Количество дней для ответа|Response day count|答复天数
roll_forward|Перенос окончания срока|Deadline roll-forward|期限顺延
rounded|Округлённая сумма|Rounded amount|已舍入金额
rub_per_unit|Рублей за единицу валюты|RUB per currency unit|每单位外币的卢布金额
rule_applicability_verified|Применимость правила подтверждена|Rule applicability verified|规则适用性已确认
sale_for_export|Продажа для вывоза в ЕАЭС|Sale for export to EAEU|为出口到欧亚经济联盟而销售
scenario_valid|Сценарий допустим|Scenario valid|情景有效
seller_proceeds_accounted|Учтены поступления продавцу|Seller proceeds accounted for|已计入卖方所得
semantic_applicability_verified|Смысловая применимость подтверждена|Semantic applicability verified|语义适用性已确认
source_authenticity_verified|Подлинность источника подтверждена|Source authenticity verified|来源真实性已确认
special_duties_basis|Основание особых пошлин|Special-duty basis|特别关税依据
stage|Этап|Stage|阶段
technical_description_reference|Техническое описание|Technical description|技术说明
threshold_percent|Порог в процентах|Percentage threshold|百分比门槛
threshold_rub|Порог в рублях|Threshold in RUB|卢布门槛
unchanged_nonorigin_codes|Коды материалов без требуемого изменения|Material codes without required change|未发生要求改变的材料编码
unresolved|Неустановленные требования|Unresolved requirements|未确定要求
unrounded|До округления|Before rounding|舍入前
unverified_fields|Не сопоставленные поля|Fields not reconciled|未核对字段
valuation_date|Дата оценки|Valuation date|估值日期
vat_exemption_basis|Основание освобождения от НДС|VAT exemption basis|增值税豁免依据
vat_treatment|Режим НДС|VAT treatment|增值税处理
calendar_days_count|Дней в календаре|Days in calendar|日历天数
working_days_count|Рабочих дней|Working-day count|工作日数
nonworking_days_count|Нерабочих дней|Non-working-day count|非工作日数'''
FIELDS.update({parts[0]:tuple(parts[1:]) for parts in (line.split('|') for line in _EXTRA_FIELDS.splitlines())})
_BRANCH_FIELDS='''deadline_restoration_not_assumed|Восстановление срока не предполагается|Deadline restoration is not assumed|不假定期限可恢复
appeal_deadline|Срок обжалования|Appeal deadline|申诉期限
route|Порядок обжалования|Appeal route|申诉途径
declaration_number|Номер декларации|Declaration number|报关单号
requested_on|Дата запроса корректировки|Amendment request date|更正请求日期
changes|Изменения|Changes|更改
field|Поле|Field|字段
old_value|Исходное значение|Original value|原值
new_value|Предлагаемое значение|Proposed value|建议值
reason|Причина|Reason|原因
numeric|Числовое поле|Numeric field|数值字段
delta|Разница|Difference|差额
document_refs|Подтверждающие документы|Supporting documents|证明文件
preparatory_status|Статус подготовки|Preparation status|准备状态
submission_performed|Подача выполнена|Submission performed|已提交
proposed_fields|Предлагаемые поля|Proposed fields|建议字段
official_kdt|Официальная корректировка ДТ|Official amendment form|正式更正表
original_declaration_changed|Исходная декларация изменена|Original declaration changed|原报关单已修改
dependent_rechecks_required|Требуемые повторные проверки|Required related checks|必须重新核查的相关事项
related_calculations_recomputed|Зависимые расчёты пересчитаны|Related calculations recomputed|相关计算已重算
challenged_decision|Оспариваемое решение|Challenged decision|被质疑的决定
applicant|Заявитель|Applicant|申请人
addressee|Адресат|Addressee|收件机关
demands|Требования|Requested remedies|诉求
grounds|Основания жалобы|Appeal grounds|申诉理由
deadline|Срок обжалования|Appeal deadline|申诉期限
event_date|Дата начала отсчёта|Start-event date|起算事件日期
event_description|Событие начала отсчёта|Start event|起算事件
event_reference|Источник даты события|Start-event source|起算事件依据
period_count|Продолжительность|Period count|期限长度
period_unit|Единица срока|Period unit|期限单位
include_event_day|Включать день события|Include event day|计入事件当日
month_end_policy|Правило конца месяца|Month-end policy|月底规则
calculated_deadline|Расчётная дата окончания|Calculated deadline|计算的截止日期
deadline_expired_as_of|Срок истёк на дату анализа|Deadline expired as of analysis date|截至分析日期期限已届满
outcome_not_promised|Исход не гарантируется|Outcome not promised|不保证结果'''
FIELDS.update({parts[0]:tuple(parts[1:]) for parts in (line.split('|') for line in _BRANCH_FIELDS.splitlines())})
FIELDS['method1_supported']=('Условия метода 1 выполнены по введённым признакам','Supplied flags satisfy method-one conditions','按输入的条件标记满足第一估价方法')
TOKENS.update({
 'draft_requires_review':('Проект требует проверки','Draft requires review','草案需要核查'),
 'calendar_days':('Календарные дни','Calendar days','自然日'),
 'working_days':('Рабочие дни','Working days','工作日'),
 'calendar_months':('Календарные месяцы','Calendar months','日历月'),
 'clamp_to_month_end':('Последний день месяца при отсутствии соответствующего числа','Use month end if the corresponding date is absent','无对应日期时采用月末日'),
 'reject_missing_day':('Остановиться, если соответствующего числа нет','Reject when corresponding day is absent','无对应日期时停止'),
 'payment_reconciliation':('Повторная сверка платежей','Reconcile payments again','重新核对税费'),
 'classification_and_specification':('Перепроверить классификацию и спецификацию','Recheck classification and specifications','重新核查归类和规格'),
 'tariff_and_non_tariff_measures':('Перепроверить тарифные и нетарифные меры','Recheck tariff and non-tariff measures','重新核查关税和非关税措施'),
 'customs_payments':('Пересчитать таможенные платежи','Recalculate customs payments','重新计算海关税费'),
 'origin_and_preferences':('Перепроверить происхождение и преференции','Recheck origin and preferences','重新核查原产地和优惠'),
 'customs_value_documents':('Перепроверить документы таможенной стоимости','Recheck customs valuation documents','重新核查完税价格文件'),
 'specific_duty_quantities':('Перепроверить количества для специфических ставок','Recheck quantities for specific duties','重新核查从量税数量'),
 'shipping_documents':('Перепроверить товаросопроводительные документы','Recheck shipping documents','重新核查货运单证'),
 'party_and_contract_documents':('Перепроверить стороны и договорные документы','Recheck parties and contract documents','重新核查当事方和合同文件'),
 'procedure_eligibility_and_payments':('Перепроверить процедуру и платежи','Recheck procedure eligibility and payments','重新核查程序资格和税费')
})

def field_label(key,language):
    if key in FIELDS:return FIELDS[key][('ru','en','zh').index(language)]
    if key in SECTION_TRANSLATIONS:return localized_section(key,language)
    if key in UI[language].values() or (len(str(key))==10 and str(key)[4:5]=='-' and str(key)[7:8]=='-'):return str(key)
    # Unknown keys remain explicit technical identifiers, never implied translated prose.
    return UI[language]['field']+' ['+str(key)+']'

def token(value,language):
    if value in TOKENS:return TOKENS[value][('ru','en','zh').index(language)]
    if value in FIELDS:return field_label(value,language)
    return value
