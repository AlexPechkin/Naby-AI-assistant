"""Readable local appraisal drafts and exact-value workbooks for RU EN ZH."""
from decimal import Decimal
import json
from .artifact_labels import TITLES,SECTIONS,UI,FIELDS,localized_section,field_label,token
from .artifact_formatting import snapshot,flat,extra_sections,docx_bytes,pdf_bytes,xlsx_bytes,scalar

XLSX=frozenset(('comparables_table','income_calc','cost_calc_doc'))
LANGUAGES=('ru','en','zh')

def _take(record,*keys):return {key:record[key] for key in keys if key in record}

def _select(record,*choices):
    for key in choices:
        if key in record:return record[key]
    return None

def _section(title,value,language,paragraphs=None):
    return dict(title=localized_section(title,language),paragraphs=paragraphs or [],rows=flat(value,language))

def _cell(value,language):
    if isinstance(value,(dict,list)):
        return '\n'.join(label+': '+str(item) for label,item in flat(value,language))
    return scalar(value,language)

def _summary(function,result,language):
    keys={
      'assignment':('missing_contract_terms','independence_issues','documentation_gaps'),
      'object_docs':('cadastral_number','discrepancies'),
      'market_analysis':('included_count','excluded_count','range','range_unit','arithmetic_mean'),
      'sales_comparison':('weighted_unit_price','quantity_unit','target_quantity','weighted_value','coefficient_of_variation','review_comparables_required','insufficient_comparables_under_supplied_policy','single_observation_is_not_market_representativeness'),
      'income_approach':('noi','direct_capitalization_value','dcf_value'),
      'cost_approach':('total_value','depreciated_replacement_cost'),
      'valuation_report':('final_value','range','documentation_gaps','unresolved'),
      'cadastral_dispute':('requirement','cadastral_value','market_value','deadline'),
      'mortgage_pledge':('market_value','liquidity','exposure_months','bank_requirements_to_verify'),
      'report_review':('arithmetic_difference','unreviewed_sections','conclusion'),
      'appraiser_status':('appraiser','issues','unresolved_independence','reminders','declared_registry_record_date','review_due_from_declared_record','registry_refresh_suggested','last_confirmed_registry_snapshot')
    }[function]
    selected={key:result[key] for key in keys+('task_scope','currency','valuation_date','report_date','as_of','tax_basis','unresolved_tax_basis') if key in result}
    if function=='cadastral_dispute' and result.get('mode')=='error_correction':selected.pop('market_value',None)
    if function=='assignment':selected.update(_take(result,'task_ready_for_review','unresolved_independence'))
    if function=='object_docs':selected.update(_take(result,'missing_evidence'))
    if function=='income_approach':
        selected.update(_take(result,'method','limitations'))
        for key in ('direct_capitalization_value','dcf_value'):
            if selected.get(key) is None:selected[key]={'ru':'Не рассчитано для выбранного метода или условий. См ограничения.','en':'Not calculated for the selected method or conditions. See limitations.','zh':'未按所选方法或条件计算，请查看限制。'}[language]
    if function=='mortgage_pledge' and result.get('mode')=='preparation':
        selected['market_value']={'ru':'В режиме подготовки стоимость не определяется','en':'Preparation mode does not determine value','zh':'准备模式不确定价值'}[language]
    if function in ('cadastral_dispute','mortgage_pledge') and isinstance(result.get('valuation_report'),dict):selected['documentation_gaps']=result['valuation_report'].get('documentation_gaps',[])
    if function=='appraiser_status' and result.get('roadmap'):
        selected=_take(result,'goal','mode','activity_direction','unresolved_steps','appraiser','as_of')
        dates=[item['due_date'] for item in result['roadmap'] if item.get('due_date')]
        if dates:selected['next_proposed_date']=min(dates)
    notices=[]
    if function=='cadastral_dispute' and result.get('mode')=='error_correction':
        notices.append({'ru':'Эта ветка готовит исправление реестровых данных; рыночная оценка здесь не выполняется.','en':'This branch prepares correction of registry data; it does not perform a market valuation.','zh':'此分支准备更正登记数据，不执行市场价值评估。'}[language])
    if result.get('conditional_arithmetic'):
        notices.append({'ru':'Условная арифметика. Налоговая база цен не установлена полностью; наблюдаемые суммы нельзя считать подтверждённо сопоставимыми по НДС.','en':'Conditional arithmetic. The price tax basis is not fully established; observed amounts are not certified as comparable for VAT.','zh':'条件性算术计算。价格税基尚未完全确定，不能证明观察金额在增值税口径上可比。'}[language])
    if function in ('market_analysis','sales_comparison','income_approach','cost_approach'):
        notices.append({'ru':'Результат отдельного подхода или исследования не заменяет итоговое суждение оценщика.','en':'An approach or research result does not replace the appraiser final judgement.','zh':'单项方法或研究结果不能替代估价师的最终判断。'}[language])
    if function=='income_approach':
        notices.append({'ru':'Загрузка здесь означает физическую занятость объекта. Отдельные потери неоплаты не определяются этим расчётом. Если они существенны, базовый результат нельзя считать полноценным ЧОД без обоснованной корректировки или явно подготовленного потока для ДДП. Не следует скрывать такие потери в загрузке или обычных операционных расходах.','en':'Occupancy here means physical use of the property. Separate non-payment losses are not determined by this calculation. If material, the base result is not a complete NOI without a substantiated correction or explicitly prepared DCF cash flow. Do not hide such losses in occupancy or ordinary operating expenses.','zh':'此处出租率指对象的实际使用率。本计算不确定单独的欠款损失。如该损失重大，未经有依据的调整或明确准备的折现现金流，基础结果不能视为完整净营业收入。不得把这类损失隐藏在出租率或普通运营费用中。'}[language])
    if function=='mortgage_pledge':notices.append({'ru':'Кредитное решение принимает банк. Автоматический дисконт к рыночной стоимости не устанавливает иной вид стоимости.','en':'The bank makes the credit decision. An automatic haircut does not establish a different type of value.','zh':'信贷决定由银行作出。自动折扣不能确定另一种价值类型。'}[language])
    return dict(title=UI[language]['summary'],paragraphs=notices,rows=flat(selected,language))

def _comparables(result,language):
    rows=[]
    for item in result.get('comparables',[]):
        rows.append([
          _cell(_take(item,'id','property_id','source_reference','source','included','excluded_reasons'),language),
          _cell(item.get('date'),language),
          _cell(_take(item,'price','price_type','price_basis','currency','unit_price','area','quantity_unit','tax_basis','tax_basis_gap'),language),
          _cell(_take(item,'characteristics','location','condition','segment','rights'),language),
          '\n'.join(token(str(a.get('kind')),language)+': '+token(str(a.get('mode')),language)+(' '+str(a['value']) if 'value' in a else '') for a in item.get('adjustments',[])) or UI[language]['none'],
          _cell(_take(item,'adjusted_price','adjusted_unit_price','indicative_net_unit_price','total_factor'),language),
          _cell(_take(item,'weight','weight_raw'),language) if 'weight' in item else {'ru':'Веса на этом этапе не рассчитывались','en':'Weights were not calculated at this stage','zh':'此阶段未计算权重'}[language]])
    return dict(title=localized_section('Аналог и источник',language),paragraphs=[],columns=[localized_section(x,language) for x in SECTIONS['sales_comparison']['comparables_table']],rows=rows)

def _adjustments(result,language):
    rows=[]
    for item in result.get('comparables',[]):
        for adjustment in item.get('adjustments',[]):
            rows.append([str(item.get('id','')),token(str(adjustment.get('kind')),language),token(str(adjustment.get('mode')),language),_cell(_take(adjustment,'value','before','after'),language),_cell(_take(adjustment,'source_reference','date','year'),language),str(adjustment.get('rationale',''))])
    return dict(title={'ru':'Основания корректировок','en':'Adjustment basis','zh':'修正依据'}[language],paragraphs=[],columns=[field_label(k,language) for k in ('id','kind','method','value','source_reference','rationale')],rows=rows)

def _report_sections(record,language):
    if record is None:record={}
    if not isinstance(record,dict):record={'report_reference':record}
    selected=record.get('sections')
    if isinstance(selected,dict):
        mapping={
          'Задание и стандарты':{k:selected.get(k) for k in ('assignment','standards')},
          'Допущения':selected.get('assumptions'),'Объект':selected.get('object'),'Анализ рынка':selected.get('market'),
          'Подходы и расчёты':selected.get('approaches'),'Согласование':selected.get('reconciliation'),
          'Итоговая стоимость':dict(selected_value=selected.get('value'),**_take(record,'market_value','currency','valuation_date','report_date')),
          'Сведения об оценщике и СРО':dict(selected_text=selected.get('appraiser'),**_take(record,'appraiser','appraiser_documentation','documentation_gaps')),'Приложения':selected.get('appendices')}
        return [_section(name,mapping[name],language) for name in SECTIONS['valuation_report']['valuation_report_doc']]
    mapping={
      'Задание и стандарты':_take(record,'assignment','standards','task_scope','report_date'),
      'Допущения':_take(record,'assumptions','limitations'),
      'Объект':_select(record,'object','object_card'),
      'Анализ рынка':_select(record,'market','market_analysis'),
      'Подходы и расчёты':_take(record,'approaches','refusals','calculations'),
      'Согласование':_select(record,'reconciliation','approaches'),
      'Итоговая стоимость':_take(record,'final_value','range','valuation_date','currency'),
      'Сведения об оценщике и СРО':_take(record,'appraiser','appraiser_documentation','documentation_gaps'),
      'Приложения':_select(record,'appendices','attachments')}
    if mapping['Итоговая стоимость'].get('currency') is None:
        mapping['Итоговая стоимость']['currency']=(record.get('task_scope') or {}).get('currency')
    return [_section(name,mapping[name],language) for name in SECTIONS['valuation_report']['valuation_report_doc']]

def _content(function,artifact,result,language):
    sections=[_summary(function,result,language)]
    if artifact=='comparables_table':
        sections.append(_comparables(result,language))
        if any(item.get('adjustments') for item in result.get('comparables',[])):sections.append(_adjustments(result,language))
        sections.append(dict(title={'ru':'Исключения и обоснования','en':'Exclusions and reasoning','zh':'剔除及依据'}[language],paragraphs=[],rows=flat(_take(result,'outlier_analysis','weighting','cv_policy','included_count','excluded_count'),language)))
        return sections
    if artifact=='valuation_report_doc':
        record=result if function=='valuation_report' else _select(result,'valuation_report','report','report_content')
        if record is None:
            note={'ru':'Выбранный полный отчёт не передан. Этот документ является перечнем подготовки, а не новым отчётом с определённой стоимостью.','en':'No selected complete report supplied. This document is a preparation checklist, not a new report determining value.','zh':'未提供选定的完整报告。本文档是准备清单，不是确定价值的新估价报告。'}[language]
            sections.append(dict(title={'ru':'Подготовка отчёта','en':'Report preparation','zh':'报告准备'}[language],paragraphs=[note],rows=flat(_take(result,'task_scope','bank','purpose','bank_policy','bank_requirements_to_verify','fso9_basis','liquidity','exposure_months'),language)))
            return sections
        sections.extend(_report_sections(record,language));return sections
    if artifact=='object_card':
        obj=result if function=='object_docs' else result.get('object_card',{})
        checklist=(obj.get('inspection') or {}).get('checklist') or {}
        technical=_take(obj,'property_type','land_use','technical')
        if obj.get('property_type')!='land':technical.pop('land_use',None)
        values={
          'Кадастровый номер и адрес':_take(obj,'cadastral_number','address'),
          'Права и обременения (ЕГРН)':_take(obj,'rights','encumbrances','egrn','egrn_area'),
          'Технические характеристики':technical,
          'Состояние':{k:checklist.get(k) for k in ('structure','finish','utilities','alterations')},
          'Окружение и локация':{k:checklist.get(k) for k in ('environment','access')},
          'Расхождения в документах':_take(obj,'discrepancies','identity_discrepancies','missing_evidence')}
    elif artifact=='contract_task':
        values={'Объект и права':_take(result,'client','object','rights','task_scope'),
          'Цель и вид стоимости':_take(result,'purpose','value_type'),
          'Дата оценки':_take(result,'valuation_date','report_date'),
          'Допущения и ограничения':_take(result,'assumptions','limitations','independence','independence_issues','missing_contract_terms'),
          'Сведения об оценщике, СРО, страховании':_take(result,'appraiser','appraiser_documentation','documentation_gaps'),
          'Цена и сроки':_take(result,'price_terms','delivery','clause_checks')}
    elif artifact=='inspection_act':
        obj=result.get('inspection') or {}
        checklist=obj.get('checklist') or {}
        values={'Дата и участники':_take(obj,'date','participants'),
          'Осмотренные помещения':obj.get('rooms'),'Состояние и отделка':{k:checklist.get(k) for k in ('structure','finish')},
          'Инженерные системы':checklist.get('utilities'),'Перепланировки':checklist.get('alterations'),'Фото':result.get('photos')}
    elif artifact=='market_review':
        values={'Макро- и региональные факторы':_take(result,'region','macro_factors'),
          'Сегмент':_take(result,'segment','target','task_scope'),
          'Ценообразующие факторы':result.get('pricing_factors'),'Диапазон цен':_take(result,'range','unit_price_range','arithmetic_mean','excluded','duplicates','outliers'),
          'Скидка на торг и источник':result.get('bargain_discount')}
    elif artifact=='income_calc':
        values={'Арендные ставки':_take(result,'market_rent_annual','rental_derivation','other_income_annual','rent_components','source_references'),
          'Загрузка':_take(result,'occupancy','vacancy','collection_loss'),
          'Операционные расходы':_take(result,'operating_expenses','expense_lines','property_tax','land_tax'),
          'ЧОД':_take(result,'pgi','egi','noi','noi_display_rounding_adjustment','unrounded','cashflows'),
          'Ставка капитализации':_take(result,'cap_rate','discount_rate','exit_cap_rate','rate_basis'),
          'Стоимость и чувствительность':_take(result,'method','direct_capitalization_value','dcf_value','reversion','discounted_reversion','selling_costs','sensitivity')}
    elif artifact=='cost_calc_doc':
        values={'Земельный участок':_take(result,'land_value','land_basis'),
          'Затраты на замещение и справочник':_take(result,'unit_cost','gross_replacement_cost','depreciated_replacement_cost','handbook','quantity','quantity_unit'),
          'Индексы':_take(result,'index','indices'),
          'Износ':_take(result,'depreciation','depreciation_fractions','total_depreciation'),
          'Прибыль предпринимателя':_take(result,'entrepreneurial_profit_percent','entrepreneurial_profit','entrepreneurial_profit_amount','calculated_profit_on_selected_base','profit_basis'),
          'Итог':_take(result,'total_value','improvements_value','rounding_adjustment','applicability_review','limited_applicability','limitations')}
    elif artifact=='cadastral_application':
        values={'Заявитель':_take(result,'applicant','addressee','route'),
          'Объект и кадастровый номер':_take(result,'cadastral_number','object','cadastral_value','cadastral_determined_on','application_date'),
          'Требование':_take(result,'requirement','route','registry_errors','challenged_decision','deadline','tax_effect'),
          'Отчёт об оценке':_take(result,'report_reference','market_value','report_date'),
          'Приложения':result.get('attachments')}
    elif artifact=='review_note':
        values={'Объект проверки':_take(result,'purpose','report_identifier','report_date','as_of','report_pages'),
          'Замечания со ссылкой на норму и страницу':_take(result,'issues','section_checks'),
          'Влияние на стоимость':_take(result,'recalculated_final_value','declared_final_value','arithmetic_difference','arithmetic'),
          'Вывод':_take(result,'conclusion','limitations','unresolved','missing_sections','unreviewed_sections')}
    elif artifact=='status_checklist':
        if result.get('roadmap'):
            steps={item['topic']:item for item in result['roadmap']}
            values={'СРО':steps.get('sro_admission'),'Квалификационный аттестат и срок':steps.get('qualification_exam'),'Страхование ответственности':steps.get('insurance'),'Независимость':steps.get('independence'),'Хранение отчётов':steps.get('report_archive')}
        else:
            values={'СРО':_take(result,'sro_member','membership','appraiser'),
              'Квалификационный аттестат и срок':_take(result,'certificate','qualification_rule'),
              'Страхование ответственности':_take(result,'insurance','insurance_requirement'),
              'Независимость':result.get('independence'),
              'Хранение отчётов':_take(result,'archive','reminders','issues','unresolved_independence','declared_registry_record_date','review_due_from_declared_record','registry_refresh_suggested','last_confirmed_registry_snapshot')}
    else:raise ValueError('unknown_appraisal_artifact')
    sections.extend(_section(name,values[name],language) for name in SECTIONS[function][artifact])
    if artifact=='inspection_act':
        sections.append(dict(title={'ru':'Границы фотоматериалов','en':'Photograph scope','zh':'照片资料范围'}[language],paragraphs=[{'ru':'Показан перечень выбранных фотоматериалов с подписями и контрольными суммами. Этот инструмент не открывал изображения и не подтверждает содержание пикселей или фактическое проведение осмотра.','en':'The selected photograph index shows captions and file digests. This tool did not open image pixels or certify their content or the actual inspection.','zh':'本清单列示所选照片的说明及文件摘要。工具未打开图像像素，也不证明图像内容或实际勘查。'}[language]],rows=[]))
    if function=='mortgage_pledge':sections.append(dict(title={'ru':'Требования банка и ликвидность','en':'Bank requirements and liquidity','zh':'银行要求及流动性'}[language],paragraphs=[],rows=flat(_take(result,'bank','purpose','fso9_basis','bank_requirements_to_verify','liquidity','exposure_months','pledge_value','credit_decision_not_made'),language)))
    return sections

def _validate_result(function,result):
    if function not in SECTIONS or type(result) is not dict:raise ValueError('appraisal_function_result_required')
    authority={'external_actions','official_report','official_expertise','official_sro_expertise','signature_applied','submission_performed','credit_decision_made','professional_report_signed'}
    def visit(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if (key in authority or key.endswith(('_verified','_approved','_confirmed','_signed'))) and item is True:
                    raise ValueError('unsupported_final_or_verified_claim:'+key)
                visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(result)

def render(function,result,language,*,config=None,review_evidence=None):
    if language not in LANGUAGES:raise ValueError('language_invalid')
    result=snapshot(result);review_evidence=snapshot(review_evidence) if review_evidence is not None else None
    _validate_result(function,result)
    if config is not None:
        from .core import execute
        if snapshot(execute(function,snapshot(config)))!=result:raise ValueError('artifact_result_input_mismatch')
    if review_evidence is not None:
        if type(review_evidence) is not dict:raise ValueError('review_evidence_object_required')
        for key in ('bindings','assumptions'):
            if type(review_evidence.get(key,[])) is not list or any(type(row) is not dict for row in review_evidence.get(key,[])):raise ValueError('review_evidence_rows_required')
    files={'result.json':(json.dumps(dict(function=function,result=result,review_evidence=review_evidence,result_rebound_to_config=config is not None),ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')}
    for artifact in SECTIONS[function]:
        if function=='cadastral_dispute' and result.get('mode')=='error_correction' and artifact=='valuation_report_doc':continue
        title=TITLES[artifact][LANGUAGES.index(language)]
        if artifact=='inspection_act':title={'ru':'Акт осмотра и перечень фотоматериалов','en':'Inspection record and photograph index','zh':'勘查记录及照片资料清单'}[language]
        if artifact=='status_checklist' and result.get('roadmap'):title={'ru':'План действий оценщика','en':'Appraiser action plan','zh':'估价师行动计划'}[language]
        if function=='mortgage_pledge' and artifact=='valuation_report_doc' and result.get('valuation_report') is None:
            title={'ru':'Подготовка отчёта для залога','en':'Report preparation for collateral','zh':'抵押估价报告准备'}[language]
        sections=_content(function,artifact,result,language)+extra_sections(review_evidence,language)
        if artifact in XLSX:files[artifact+'.xlsx']=xlsx_bytes(title,sections,language,review_evidence)
        else:
            files[artifact+'.docx']=docx_bytes(title,sections,language,review_evidence)
            files[artifact+'.pdf']=pdf_bytes(title,sections,language,review_evidence)
    return files
