"""Exact source-rebound private actuarial drafts; no approval or submission."""
import json
from .artifact_labels import UI,TITLES,LANGUAGES,tr
from .artifact_formatting import snapshot,flat,extra_sections,docx_bytes,pdf_bytes,xlsx_bytes

SECTIONS={
'data_assumptions':{
'data_review':[
 (('Источники','Sources','来源'),('dataset_reviews.id','dataset_reviews.source_reference','dataset_reviews.currency','dataset_reviews.perimeter','dataset_reviews.period_start','dataset_reviews.period_end','dataset_reviews.cutoff_date','selected_requirements')),
 (('Полнота и согласованность','Completeness and consistency','完整性及一致性'),('dataset_reviews',)),
 (('Исправления','Proposed corrections','拟议修正'),('proposed_corrections',)),
 (('Ограничения','Limitations','限制'),('limitations','notices'))],
'assumptions_memo':[
 (('Предположение','Assumption','假设'),('assumption_reviews.id','assumption_reviews.kind','assumption_reviews.proposed_value','assumption_reviews.status')),
 (('Источник и год','Source and year','来源及年份'),('assumption_reviews.source_reference','assumption_reviews.excerpt','assumption_reviews.source_edition','assumption_reviews.source_publication_date','assumption_reviews.experience_start','assumption_reviews.experience_end','assumption_reviews.population_scope','selected_requirements')),
 (('Обоснование','Rationale','理由'),('assumption_reviews.rationale','assumption_reviews.evidence_gaps','limitations')),
 (('Чувствительность','Sensitivity','敏感性'),('assumption_reviews.sensitivity','notices'))]},
'actuarial_task':{'task':[
 (('Заказчик и исполнитель','Customer and practitioner','委托方及执行方'),('draft_task.client','draft_task.executor','selected_contract','source_reference','clause_reviews@client','clause_reviews@executor')),
 (('Цель и объект','Purpose and object','目的及对象'),('draft_task.purpose','draft_task.object','clause_reviews@purpose','clause_reviews@object')),
 (('Дата оценивания','Valuation date','评估日'),('valuation_date','draft_task.delivery_date','clause_reviews@valuation_date')),
 (('Данные и ответственность','Data and responsibility','数据及责任'),('data_scope','draft_task.data_responsibility','clause_reviews@data_scope','clause_reviews@data_responsibility')),
 (('Ограничения','Limitations','限制'),('draft_task.limitations','clause_reviews@limitations','selected_requirements','missing_clause_topics','contradictions','evidence_gaps','notices')),
 (('Использование результатов','Use of results','结果用途'),('draft_task.result_usage','clause_reviews@result_usage','engagement_status'))]},
'tariff':{'tariff_note':[
 (('Данные и экспозиция','Data and exposure','数据及风险暴露'),('insurance_class','experience_rows','loss_basis','trend_convention','target_cost_date','earned_exposure','claims_count','claims_total','trended_claims_total','reliability','osago_review.category','osago_review.selected_rule','osago_review.corridor')),
 (('Частота и средний убыток','Frequency and average claim','频率及平均赔款'),('frequency','frequency_unit','average_claim','trended_average_claim','average_claim_status','claim_development_not_estimated')),
 (('Нетто ставка','Net loss cost','净风险成本'),('experience_loss_cost','credibility','net_loss_cost')),
 (('Рисковая надбавка','Risk loading','风险附加'),('risk_loading',)),
 (('Нагрузка','Premium loads','保费加载'),('loads',)),
 (('Брутто ставка','Gross premium','毛保费'),('gross_premium_per_policy_year','premium_unit','insured_sum_rate','insured_sum_rate_unit','osago_review','proposal_insurer_decision_only')),
 (('Чувствительность','Sensitivity','敏感性'),('sensitivity','evidence_gaps'))]},
'reserves':{'reserve_report':[
 (('Треугольники','Triangles','赔款三角形'),('claims.basis','claims.triangle_age_date_convention','claims.triangle_rows')),
 (('Коэффициенты развития','Development factors','发展因子'),('claims.development_factors','claims.cumulative_factors')),
 (('Методы и выбор','Methods and selection','方法及选择'),('claims.method_comparison','unearned_premium.earning_pattern','unearned_premium.valuation_boundary','unearned_premium.premium_basis','regulatory_reserve_compliance_not_established','reserve_selection_requires_insurer_and_actuary_review')),
 (('Run off проверка','Run off review','径流核查'),('claims.runoff',)),
 (('Резерв по видам','Reserves by basis','按基础分类准备金'),('claims.selected_reserves','claims.selected_unpaid','claims.settlement_expenses','claims.total_with_settlement_expenses','claims.reinsurance_review','unearned_premium.rows','unearned_premium.total','unearned_premium.regulatory_reserve_equivalence_not_established')),
 (('Неопределённость','Uncertainty','不确定性'),('claims.uncertainty','claims.evidence_gaps'))]},
'life_pension':{
'reserve_report':[
 (('Треугольники','Triangles','赔款三角形'),()),
 (('Коэффициенты развития','Development factors','发展因子'),()),
 (('Методы и выбор','Methods and selection','方法及选择'),('mode','model_scope','horizon_years','payment_timing','present_value_basis')),
 (('Run off проверка','Run off review','径流核查'),()),
 (('Резерв по видам','Reserves by basis','按基础分类准备金'),('participant_results','present_value')),
 (('Неопределённость','Uncertainty','不确定性'),('sensitivity','evidence_gaps','IAS19_or_NPF_or_insurance_compliance_not_established'))],
'actuarial_report':[
 (('Задание','Engagement','任务'),('model_scope','mode')),
 (('Данные','Data','数据'),('horizon_years','payment_timing','participant_results.id','participant_results.sex','participant_results.age','participant_results.table_id','participant_results.number_of_lives','participant_results.source_reference')),
 (('Предположения','Assumptions','假设'),('assumption_metadata','mortality_tables','discount_curve','participant_results.lapse_model')),
 (('Методы','Methods','方法'),('present_value_basis','participant_results.employer_benefit_attribution')),
 (('Результаты','Results','结果'),('participant_results','present_value','sensitivity')),
 (('Ограничения','Limitations','限制'),('personal_data_local_only','IAS19_or_NPF_or_insurance_compliance_not_established','evidence_gaps'))]},
'mandatory_assessment':{
'actuarial_conclusion':[
 (('Сведения об организации и актуарии','Organisation and actuary details','机构及精算师资料'),('organization','organization_type','actuary')),
 (('Данные и проверка','Data and review','数据及核查'),('assessment_sections.data_review','balance_sheet.liability_basis','balance_sheet.currency')),
 (('Предположения и методы','Assumptions and methods','假设及方法'),('assessment_sections.assumptions','assessment_sections.methods')),
 (('Обязательства и резервы','Liabilities and reserves','负债及准备金'),('balance_sheet.liabilities','balance_sheet.liabilities_total','balance_sheet.reserves_subset','reported_reserves','reserve_reconciliation_difference')),
 (('Активы и достаточность','Assets and adequacy','资产及充足性'),('balance_sheet.assets','balance_sheet.assets_total','balance_sheet.capital','selected_requirements','required_capital','conditional_capital_ratio')),
 (('Изменения к прошлому году','Changes from the prior year','较上年变化'),('prior_period',)),
 (('Выводы и рекомендации','Conclusions and recommendations','结论及建议'),('assessment_sections.recommendations','assessment_sections.limitations','reporting_deadline','evidence_gaps','notices'))],
'actuarial_report':[
 (('Задание','Engagement','任务'),('organization','organization_type','actuary','selected_requirements')),
 (('Данные','Data','数据'),('assessment_sections.data_review','balance_sheet.liability_basis','balance_sheet.currency')),
 (('Предположения','Assumptions','假设'),('assessment_sections.assumptions',)),
 (('Методы','Methods','方法'),('assessment_sections.methods',)),
 (('Результаты','Results','结果'),('balance_sheet','required_capital','conditional_capital_ratio','reported_reserves','reserve_reconciliation_difference','prior_period','assessment_sections.recommendations')),
 (('Ограничения','Limitations','限制'),('assessment_sections.limitations','reporting_deadline','evidence_gaps','notices'))]},
'ifrs17':{'ifrs17_memo':[
 (('Группировка','Grouping','分组'),('group_reviews.id','group_reviews.portfolio','group_reviews.cohort','group_reviews.profitability','group_reviews.currency')),
 (('Модель','Model','模型'),('group_reviews.model','group_reviews.selected_rule','group_reviews.paa','group_reviews.vfa_review')),
 (('Денежные потоки','Cash flows','现金流'),('group_reviews.gmm_initial','group_reviews.vfa_review.nonvarying_fcf')),
 (('Ставки','Discounting basis','折现依据'),('group_reviews.gmm_initial.cashflow_review.date','group_reviews.gmm_initial.cashflow_review.discount_factor','group_reviews.csm_rollforward.interest_accretion','group_reviews.paa.movements@financing')),
 (('Рисковая поправка','Risk adjustment','风险调整'),('group_reviews.gmm_initial.risk_adjustment','group_reviews.gmm_initial.risk_basis','group_reviews.paa.loss_test','group_reviews.vfa_review.nonvarying_fcf')),
 (('CSM','Contractual service margin','合同服务边际'),('group_reviews.gmm_initial.initial_csm','group_reviews.gmm_initial.initial_onerous_loss','group_reviews.csm_rollforward','group_reviews.vfa_review.csm')),
 (('Переход','Transition','过渡'),('transition_note','regulatory_reconciliation','group_reviews.evidence_gaps','notices'))]},
'solvency_stress':{'stress_memo':[
 (('Сценарии','Scenarios','情景'),('scenario_reviews.id','scenario_reviews.description','scenario_reviews.changes','base_balance_sheet','selected_rule','base_required_capital')),
 (('Влияние на резервы','Reserve impact','准备金影响'),('base_balance_sheet.reserves_subset','scenario_reviews.stressed_reserves_subset','scenario_reviews.stressed_all_liabilities')),
 (('Влияние на капитал','Capital impact','资本影响'),('base_conditional_ratio','scenario_reviews.stressed_assets_before_direct_cost','scenario_reviews.direct_cost','scenario_reviews.conditional_capital','scenario_reviews.capital_change','scenario_reviews.stressed_required_capital','scenario_reviews.conditional_ratio')),
 (('Перестрахование','Reinsurance','再保险'),('scenario_reviews.stressed_reinsurance_assets',)),
 (('Ограничения','Limitations','限制'),('scenario_reviews.source_reference','scenario_reviews.solvency_conclusion','evidence_gaps','notices'))]},
'actuary_status':{'status_checklist':[
 (('СРО','SRO membership','自律组织会员'),('subject_id','purpose','requirement_reviews@sro')),
 (('Аттестация','Attestation','资格考试'),('requirement_reviews@attestation','requirement_reviews@education')),
 (('Опыт','Experience','经验'),('requirement_reviews@experience','requirement_reviews@cpd')),
 (('Реестр Банка России','Bank of Russia register','俄罗斯央行登记册'),('requirement_reviews@registry',)),
 (('Независимость','Independence','独立性'),('requirement_reviews@independence','requirement_reviews@restrictions','unaddressed_topics','notices'))]},
}
XLSX={'reserve_report'}
BOUNDS=('as_of','jurisdiction','valuation_date','data_scope','currency','input_sha256','assisted_draft','analysis_only','private','external_network_used','external_actions','tariffs_applied','reserves_approved','accounting_policy_approved','signature_applied','report_submitted','professional_status_granted','source_semantics_verified','current_legal_applicability_verified','arithmetic_precision_digits','human_review_required','records_changed','approval_granted','submission_performed','qualified_status_granted','accounting_policy_adopted','external_code_executed')

def _path(value,path):
    if not path:return value,True
    key,*rest=path.split('.')
    if isinstance(value,list):
        rows=[]
        for index,item in enumerate(value,1):
            selected,present=_path(item,path)
            if present:rows.append({'record_index':index,path.split('.')[-1]:selected})
        return rows,bool(rows)
    if not isinstance(value,dict):return None,False
    if '@' in key:
        key,identity=key.split('@',1)
        if key not in value:return None,False
        selected=[row for row in value[key] if any(row.get(selector)==identity for selector in ('topic','id','type'))]
        return _path(selected,'.'.join(rest)) if rest else (selected,True)
    if key not in value:return None,False
    return _path(value[key],'.'.join(rest))

def _content(function,artifact,result,language,*,config=None):
    u=UI[language]
    sections=[dict(title=u['summary'],paragraphs=[u['advice']],rows=flat({key:result[key] for key in ('mode','valuation_date','data_scope','currency','evidence_gaps','notices') if key in result},language))]
    if function=='life_pension' and artifact=='reserve_report':
        sections.append(dict(title=tr(('Предположения и исходные таблицы','Assumptions and source tables','假设及来源表'),language),paragraphs=[],rows=flat({key:result[key] for key in ('assumption_metadata','mortality_tables','discount_curve','personal_data_local_only') if key in result},language)))
    for title,paths in SECTIONS[function][artifact]:
        selected={}
        for path in paths:
            value,present=_path(result,path)
            if present:selected[path]=value
        source_config_fields=[]
        if function=='tariff' and 'insured_sum_rate' in paths and config is not None:
            data=config['data']
            if 'reference_sum_insured_per_policy' in data:
                selected['reference_sum_insured_per_policy']={'value':data['reference_sum_insured_per_policy'],'unit':'RUB/policy'}
                source_config_fields.append('reference_sum_insured_per_policy')
        na=(not paths) or (function=='reserves' and result.get('claims') is None and paths and all(path.startswith('claims.') for path in paths)) or (function=='tariff' and result.get('mode')=='osago_review' and not selected)
        paragraphs=[] if selected else [tr(('Раздел не применяется к выбранному режиму оценивания.','This section is not applicable to the selected valuation mode.','本章节不适用于所选评估模式。'),language) if na else u['missing']]
        sections.append(dict(title=tr(title,language),paragraphs=paragraphs,rows=flat(selected,language) if selected else [],source_paths=list(paths),selected_paths=list(selected),not_applicable=na,source_config_fields=source_config_fields))
    used={path.split('.')[0].split('@')[0] for specs in SECTIONS[function].values() for title,paths in specs for path in paths}
    remaining={key:value for key,value in result.items() if key not in used and key not in BOUNDS and key not in ('function','mode','evidence_gaps','notices')}
    if remaining:sections.append(dict(title=tr(('Дополнительные сведения','Additional information','补充资料'),language),paragraphs=[],rows=flat(remaining,language),additional_subject_fields=sorted(remaining)))
    sections.append(dict(title=u['bounds'],paragraphs=[u['disclaimer_note']],rows=flat({key:result[key] for key in BOUNDS if key in result},language)))
    return sections

def _validate_result(function,result):
    if function not in SECTIONS or type(result) is not dict:raise ValueError('actuary_function_result_required')
    authority={'external_actions','tariffs_applied','reserves_approved','accounting_policy_approved','signature_applied','report_submitted','professional_status_granted','source_semantics_verified','current_legal_applicability_verified','approval_granted','submission_performed','qualified_status_granted','accounting_policy_adopted','records_changed','contract_signature_established','source_authenticity_established','legal_authority_established'}
    def visit(value,depth=0):
        if depth>24:raise ValueError('artifact_nesting_limit')
        if isinstance(value,dict):
            for key,item in value.items():
                if (key in authority or key.endswith(('_approved','_signed'))) and item is True:raise ValueError('unsupported_final_or_verified_claim:'+key)
                visit(item,depth+1)
        elif isinstance(value,list):
            for item in value:visit(item,depth+1)
    visit(result)

def render(function,result,language,*,config=None,review_evidence=None):
    if language not in LANGUAGES:raise ValueError('language_invalid')
    result=snapshot(result);review_evidence=snapshot(review_evidence) if review_evidence is not None else None
    _validate_result(function,result)
    if config is None:raise ValueError('artifact_source_config_required')
    config=snapshot(config)
    from .core import execute
    if snapshot(execute(function,config))!=result:raise ValueError('artifact_result_input_mismatch')
    if review_evidence is not None:
        if type(review_evidence) is not dict:raise ValueError('review_evidence_object_required')
        _validate_result(function,review_evidence)
        for key in ('bindings','assumptions'):
            if type(review_evidence.get(key,[])) is not list or any(type(row) is not dict for row in review_evidence.get(key,[])):raise ValueError('review_evidence_rows_required')
    source_inputs={}
    if function=='tariff' and 'reference_sum_insured_per_policy' in config['data']:
        source_inputs['reference_sum_insured_per_policy']={'value':config['data']['reference_sum_insured_per_policy'],'unit':'RUB/policy'}
    files={'result.json':(json.dumps(dict(function=function,result=result,review_evidence=review_evidence,result_rebound_to_config=True,document_source_inputs=source_inputs),ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')}
    for artifact in SECTIONS[function]:
        content=_content(function,artifact,result,language,config=config)+extra_sections(review_evidence,language);title=tr(TITLES[artifact],language)
        writer=xlsx_bytes if artifact in XLSX else docx_bytes
        files[artifact+('.xlsx' if artifact in XLSX else '.docx')]=writer(title,content,language,review_evidence)
        files[artifact+'.pdf']=pdf_bytes(title,content,language,review_evidence)
    return files
