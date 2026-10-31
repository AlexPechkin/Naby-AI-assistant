"""Bound local investment documents, with no publishing or broker actions."""
import json
from .artifact_labels import UI,TITLES,LANGUAGES,tr,field_label,token
from .artifact_formatting import snapshot,flat,extra_sections,docx_bytes,pdf_bytes,xlsx_bytes,LITERAL_FIELDS

SECTIONS={
 'issuer_disclosure':{'issuer_card':[
  (('Реквизиты и бумаги','Issuer and securities','发行人及证券'),('issuer','inn','ticker','period')),
  (('Отчётность и даты','Statements and dates','财务报告及日期'),('documents',)),
  (('Существенные факты','Material facts','重大事实'),('material_facts',)),
  (('Долг и рейтинги','Debt and ratings','债务及评级'),('debt','ratings')),
  (('Ограничения раскрытия','Disclosure limitations','披露限制'),('disclosure_limitations','missing_primary_documents'))]},
 'valuation_model':{'model_workbook':[
  (('Допущения с источниками','Assumptions and sources','假设及来源'),('issuer','valuation_date','currency','enterprise_to_equity_bridge','selected_balance_projection')),
  (('Прогноз прибыли денежных потоков и баланса','Profit cash flow and balance forecast','利润现金流及资产负债预测'),('scenario_forecasts',)),
  (('Ставка дисконтирования','Discount rate','折现率'),('scenario_discounting',)),
  (('Дисконтированная стоимость','Discounted value','折现价值'),('range_per_share','opening_balance_residual','opening_balance_identity_holds','any_balance_gaps','multiple_crosscheck')),
  (('Сценарии','Scenarios','情景'),('scenarios',)),
  (('Чувствительность','Sensitivity','敏感性'),('sensitivity',))],
 'research_note':[(('Результат сценарного анализа','Scenario analysis result','情景分析结果'),('scenarios','range_per_share','multiple_crosscheck','sensitivity'))]},
 'peer_comparison':{'peer_table':[
  (('Эмитенты и показатели сравнения','Issuers and comparison metrics','发行人及比较指标'),('peers','included_peers','excluded_peers','comparison_date','currency','period','standard')),
  (('Сводные мультипликаторы','Multiple summaries','倍数汇总'),('median_ev_ebitda','summary','medians','outlier_analysis','comparison_policy','mixed_standards','mixed_periods'))]},
 'bond_analysis':{'bond_card':[
  (('Параметры выпуска','Issue parameters','发行参数'),('isin','issue','price','price_date','settlement_date','price_percent','clean_price','dirty_price','accrued_interest','face_value','currency','coupon_type','target','target_date')),
  (('Купон оферты и амортизация','Coupon offers and amortisation','票息要约及摊还'),('cashflows','cash_flows','coupon','floating_assumptions','offer','amortisation','assumptions','yield_convention','day_count')),
  (('Доходность и дюрация','Yield and duration','收益率及久期'),('ytm','yield','yield_to_target','ytm_annual_effective','macaulay_duration_years','modified_duration_years','modified_duration','convexity','solver','reprice_error')),
  (('Спред к ОФЗ','Spread to OFZ','相对俄罗斯国债利差'),('simple_yield_spread','spread_basis','benchmark')),
  (('Рейтинги и дата','Ratings and date','评级及日期'),('ratings',)),
  (('Ковенанты и риски','Covenants and risks','契约及风险'),('covenants','risks','subordination','currency_risk','warnings'))]},
 'research_report':{'research_note':[
  (('Тезис и аудитория','Thesis and audience','投资逻辑及受众'),('audience','issuer','data_date','thesis')),
  (('Публичные факты и источники','Public facts and sources','公开事实及来源'),('public_facts',)),
  (('Оценка','Valuation','估值'),('valuation',)),
  (('Риски и катализаторы','Risks and catalysts','风险及催化剂'),('risks','catalysts')),
  (('Что опровергнет идею','What would falsify the thesis','投资逻辑证伪条件'),('falsifiers',)),
  (('Оговорки','Disclosures','声明'),('conflict_disclosure','publication_draft_allowed','content_withheld'))],
 'disclaimer':[
  (('Не является индивидуальной инвестиционной рекомендацией','Not individual investment advice','不是个性化投资建议'),('not_individual_investment_advice','personalization','individual_recommendation_classification')),
  (('Риски','Risks','风险'),('risks',)),
  (('Конфликт интересов','Conflict of interest','利益冲突'),('conflict_disclosure',)),
  (('Даты и источники данных','Data dates and sources','数据日期及来源'),('audience','issuer','data_date','source_inventory','publication_draft_allowed','content_withheld'))]},
 'investor_status':{'qual_checklist':[
  (('Инструмент и вид инвестора','Instrument and investor type','工具及投资者类别'),('entity_type','instrument','instrument_review')),
  (('Критерии и документы','Criteria and documents','条件及文件'),('criteria_groups','criteria','evidence_gaps','qualification_decision')),
  (('Тестирование неквалифицированного инвестора','Nonqualified investor testing','非合格投资者测试'),('testing',))]},
 'insider_compliance':{'compliance_checklist':[
  (('Источники сведений','Information sources','信息来源'),('sources',)),
  (('Инсайд и признаки манипулирования','Inside information and manipulation indicators','内幕信息及操纵迹象'),('flags','publication_blocked','sensitive_content_withheld','insider_review')),
  (('Конфликт интересов и согласование','Conflicts and review','利益冲突及审核'),('conflict_disclosure','compliance_route','compliance_checklist','checklist_documents_do_not_establish_clearance','next_steps'))]},
 'portfolio_scenarios':{'portfolio_memo':[
  (('Состав и веса на дату','Composition and weights on date','指定日期构成及权重'),('positions','total_base_value','price_date','currency','as_of')),
  (('Концентрации','Concentrations','集中度'),('issuer_concentration','sector_concentration','currency_concentration','concentrations')),
  (('Стресс сценарии и допущения','Stress scenarios and assumptions','压力情景及假设'),('scenarios','portfolio_modified_duration','bond_sleeve_modified_duration','weights_computed_from_values')),
  (('Ограничения модели','Model limitations','模型限制'),('warnings','limitations','not_personal_recommendation','historical_results_not_guaranteed'))]},
 'investor_tax':{'tax_note':[
  (('Вид дохода счёт и период','Income type account and period','收入类型账户及期间'),('income_type','residency','tax_period','account','mode')),
  (('Налоговая база и расчёт','Tax base and calculation','税基及计算'),('calculation',)),
  (('Налоговый агент','Tax agent','税务代理人'),('tax_agent_assessment',)),
  (('Льготы вычеты и условия','Reliefs deductions and conditions','优惠扣除及条件'),('conditions','relief','iis','long_term_ownership')),
  (('Источники норм','Legal sources','法律来源'),('rules',))]},
}
XLSX={'model_workbook','peer_table'}

def _take(result,keys):return {key:result[key] for key in keys if key in result}

def _section(title,value,language):
    if value is None or value=={} or value==[]:
        return dict(title=tr(title,language),paragraphs=[UI[language]['missing']],rows=[])
    return dict(title=tr(title,language),paragraphs=[],rows=flat(value,language))

def _grid(title,records,keys,language):
    def cell(value,key):
        if isinstance(value,(dict,list)):return '\n'.join(' / '.join(row) for row in flat(value,language))
        if value is None:
            if key in ('pe','ev_ebitda','net_debt_ebitda','dividend_yield'):return tr(('Неприменимо','N/M','不适用'),language)
            if key=='outlier':return tr(('Не оценивался','Not assessed','未评估'),language)
            return UI[language]['missing']
        if type(value) is bool:return UI[language]['yes'] if value else UI[language]['no']
        if key in ('pe','ev_ebitda','net_debt_ebitda','dividend_yield'):
            from decimal import Decimal,localcontext,Context
            with localcontext(Context(prec=128)):
                number=Decimal(value).quantize(Decimal('.000001'))
                return format(number,'f').rstrip('0').rstrip('.') or '0'
        return str(value) if key in LITERAL_FIELDS else token(str(value),language)
    return dict(title=title,paragraphs=[],columns=[field_label(key,language) for key in keys],rows=[[cell(row.get(key),key) for key in keys] for row in records])

def _scenarios(result,language):
    sections=[]
    for key,scenario in result.get('scenarios',{}).items():
        title=token(str(key),language)
        if not isinstance(scenario,dict):continue
        flow=scenario.get('flows')
        if isinstance(flow,list) and flow and all(isinstance(row,dict) for row in flow):
            keys=list(dict.fromkeys(k for row in flow for k in row))
            # A transposed model keeps years in columns and operating metrics in rows.
            for offset in range(0,len(flow),6):
                group=flow[offset:offset+6]
                columns=[field_label('year',language)]+[str(row.get('year',offset+i+1)) for i,row in enumerate(group)]
                def scalar(value):
                    if value is None:return UI[language]['missing']
                    if type(value) is bool:return UI[language]['yes'] if value else UI[language]['no']
                    return token(str(value),language)
                rows=[[field_label(k,language)]+[scalar(row.get(k)) for row in group] for k in keys if k!='year']
                sections.append(dict(title=title,paragraphs=[],columns=columns,rows=rows))
        details={k:v for k,v in scenario.items() if k!='flows'}
        sections.append(dict(title=title+' '+field_label('valuation',language),paragraphs=[],rows=flat(details,language)))
    return sections

def _content(function,artifact,result,language):
    u=UI[language]
    if function=='research_report':
        result=dict(result)
        narrative=result.get('narrative')
        if isinstance(narrative,dict):
            for key in ('thesis','valuation','risks','catalysts','falsifiers','conflict_disclosure'):
                if key in narrative:result[key]=narrative[key]
    summary_keys=('status','publication_blocked','content_withheld','qualification_decision','calculation','range_per_share','value_range','median_ev_ebitda','ytm','macaulay_duration_years','modified_duration_years','simple_yield_spread','total_base_value','missing_primary_documents','any_balance_gaps')
    # Put the result and unresolved issues before the technical input digest.
    summary=_take(result,summary_keys)
    if 'calculation' in summary and isinstance(summary['calculation'],dict):
        summary['calculation']=_take(summary['calculation'],('base_before_relief_rub','base_after_relief_rub','marginal_tax_before_relief_rub','marginal_tax_after_relief_rub','balance_to_review_rub'))
    sections=[dict(title=u['summary'],paragraphs=[u['advice']],rows=flat(summary,language) if summary else [])]
    if result.get('content_withheld') or result.get('sensitive_content_withheld'):
        sections[0]['paragraphs'].insert(0,u['withheld'])
    used=set(summary_keys)
    if function=='research_report':used.add('narrative')
    for title,keys in SECTIONS[function][artifact]:
        if function=='valuation_model' and keys==('scenario_forecasts',):
            sections.extend(_scenarios(result,language))
        elif function=='valuation_model' and keys==('scenario_discounting',):
            sections.append(_section(title,{key:scenario.get('discounting') for key,scenario in result.get('scenarios',{}).items()},language))
        elif function=='valuation_model' and keys==('scenarios',):
            sections.append(_section(title,{key:{k:v for k,v in scenario.items() if k not in ('flows','discounting')} for key,scenario in result.get('scenarios',{}).items()},language))
        elif function=='peer_comparison' and 'peers' in keys and isinstance(result.get('peers'),list):
            peers=result['peers']
            other=_take(result,[key for key in keys if key!='peers'])
            if other:sections.append(_section(('Параметры сопоставления','Comparison parameters','比较参数'),other,language))
            sections.append(_grid(tr(title,language),peers,('id','issuer','included','currency','price_date','period','standard'),language))
            sections.append(_grid(tr(('Капитализация и стоимость','Capitalisation and value','市值及企业价值'),language),peers,('id','market_cap','ev','ebitda','net_income','ev_ebitda'),language))
            sections.append(_grid(tr(('Доходность долг и ограничения','Returns debt and limitations','回报债务及限制'),language),peers,('id','pe','net_debt_ebitda','dividend_yield','outlier','mismatches'),language))
            sections[-1]['paragraphs'].append(tr(('В таблицах коэффициенты округлены до шести знаков после запятой. Полные значения сохранены в JSON результата.','Ratios in these tables are displayed to six decimal places. Full values remain in the result JSON.','表中比率显示至小数点后六位，完整数值保留在结果JSON中。'),language))
            known={'id','issuer','included','currency','price_date','period','standard','market_cap','ev','ebitda','net_income','ev_ebitda','pe','net_debt_ebitda','dividend_yield','outlier','mismatches'}
            selection={}
            for i,row in enumerate(peers):
                details={k:v for k,v in row.items() if k not in known}
                details['unrounded_ratios']={k:(row[k] if row.get(k) is not None else tr(('Неприменимо','N/M','不适用'),language)) for k in ('pe','ev_ebitda','net_debt_ebitda','dividend_yield')}
                selection[str(row.get('id',i))]=details
            sections.append(_section(('Отбор и основания','Selection and basis','筛选及依据'),selection,language))
        else:sections.append(_section(title,_take(result,keys),language))
        used.update(keys)
    sections.append(dict(title=u['gaps'],paragraphs=[],rows=flat(_take(result,('gaps','next_steps','evidence_gaps')),language)))
    used.update(('gaps','next_steps','evidence_gaps'))
    # Preserve every returned field in a named appendix, including new branches.
    extra={key:value for key,value in result.items() if key not in used and key not in ('function','input_sha256','source_semantics_verified','current_legal_applicability_verified','external_actions','source_declarations_are_not_verification')}
    if extra:sections.append(_section(('Дополнительные параметры и ограничения','Additional parameters and limitations','补充参数及限制'),extra,language))
    sections.append(dict(title=u['bounds'],paragraphs=[u['disclaimer_note']],rows=flat(_take(result,('as_of','input_sha256','source_semantics_verified','current_legal_applicability_verified','external_actions','source_declarations_are_not_verification')),language)))
    return sections

def _validate_result(function,result):
    if function not in SECTIONS or type(result) is not dict:raise ValueError('investment_function_result_required')
    authority={'external_actions','signature_applied','submission_performed','qualification_granted','broker_order_created','trade_executed','publication_performed','official_legal_opinion','publication_draft_allowed'}
    def visit(value,depth=0):
        if depth>24:raise ValueError('artifact_nesting_limit')
        if isinstance(value,dict):
            for key,item in value.items():
                if (key in authority or key.endswith(('_verified','_approved','_confirmed','_signed'))) and item is True:
                    raise ValueError('unsupported_final_or_verified_claim:'+key)
                visit(item,depth+1)
        elif isinstance(value,list):
            for item in value:visit(item,depth+1)
    visit(result)

def render(function,result,language,*,config=None,review_evidence=None):
    if language not in LANGUAGES:raise ValueError('language_invalid')
    result=snapshot(result);review_evidence=snapshot(review_evidence) if review_evidence is not None else None
    _validate_result(function,result)
    if config is None:raise ValueError('artifact_source_config_required')
    from .core import execute
    if snapshot(execute(function,snapshot(config)))!=result:raise ValueError('artifact_result_input_mismatch')
    if review_evidence is not None:
        if type(review_evidence) is not dict:raise ValueError('review_evidence_object_required')
        for key in ('bindings','assumptions'):
            if type(review_evidence.get(key,[])) is not list or any(type(row) is not dict for row in review_evidence.get(key,[])):raise ValueError('review_evidence_rows_required')
    if result.get('content_withheld') or result.get('sensitive_content_withheld'):
        # A citation appendix must not undo the subject engine's withholding.
        # Full selected evidence remains in the separate private host audit.
        review_evidence={key:value for key,value in (review_evidence or {}).items() if key in ('as_of','hypothetical_inputs_present')}
        review_evidence['sensitive_quotes_withheld']=True
    files={'result.json':(json.dumps(dict(function=function,result=result,review_evidence=review_evidence,result_rebound_to_config=True),ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')}
    for artifact in SECTIONS[function]:
        title=tr(TITLES[artifact],language)
        content=_content(function,artifact,result,language)+extra_sections(review_evidence,language)
        if artifact in XLSX:files[artifact+'.xlsx']=xlsx_bytes(title,content,language,review_evidence)
        else:files[artifact+'.docx']=docx_bytes(title,content,language,review_evidence)
        files[artifact+'.pdf']=pdf_bytes(title,content,language,review_evidence)
    return files
