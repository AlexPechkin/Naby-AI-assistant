"""Source-rebound local scientific drafts. No numerical display rounding."""
import json
from .artifact_labels import UI,TITLES,LANGUAGES,tr
from .artifact_formatting import snapshot,flat,extra_sections,docx_bytes,pdf_bytes,xlsx_bytes

SECTIONS={
'physical_model':{'model_note':[
 (('Постановка','Problem statement','问题陈述'),('system','target','quantity_inventory','constant_inventory','declared_outputs')),
 (('Допущения','Assumptions','假设'),('assumptions',)),
 (('Уравнения и размерности','Equations and dimensions','方程及量纲'),('equations','dimensions_consistent','supported_expression_language')),
 (('Предельные случаи','Limiting cases','极限情况'),('limiting_cases','no_symbolic_limit_proof')),
 (('Оценки','Scale estimates','尺度估计'),('dimensionless_parameters','scale_checks')),
 (('Границы применимости','Applicability limits','适用限制'),('applicability_limits','mechanism_not_proven_by_single_fit'))]},
'numerical_sim':{'sim_protocol':[
 (('Задача и уравнения','Problem and equations','问题及方程'),('problem.equations','problem.geometry','problem.boundary_conditions','problem.initial_conditions','problem.materials','quantity_unit','mode')),
 (('Код и версия','Code and version','代码及版本'),('problem.code','problem.version','problem.method','problem.stop_criterion','problem.source_reference','monte_carlo.seed','monte_carlo.engine','monte_carlo.engine_version','monte_carlo.physics_model_version','no_solver_execution','no_cluster_execution')),
 (('Сетка и шаг','Grid and step','网格及步长'),('grid_levels','refinement','monte_carlo.events')),
 (('Сходимость','Convergence review','收敛核查'),('refinement_pairs','richardson_triplets','convergence_proven','reproducibility_scope')),
 (('Верификация','Benchmark comparison','基准比较'),('benchmark',)),
 (('Результаты с ошибками','Results and uncertainty','结果及不确定度'),('monte_carlo','evidence_gaps'))]},
'experiment_setup':{
'measurement_method':[
 (('Назначение','Purpose','目的'),('draft_method.objective','draft_method.measurand','draft_method.scope')),
 (('Средства измерений','Measuring instruments','测量仪器'),('instruments',)),
 (('Метод','Method draft','方法草稿'),('draft_method.proposed_method',)),
 (('Условия','Conditions','条件'),('measurement_plan.conditions','measurement_plan.background','measurement_plan.range')),
 (('Порядок измерений','Measurement plan','测量计划'),('measurement_plan.repeats','measurement_plan.control_points','journal_template')),
 (('Обработка','Processing','处理'),('processing','method_comparison','heat_balance')),
 (('Показатели точности','Accuracy basis','准确度依据'),('accuracy_basis','evidence_gaps','notices'))],
'exp_log':[
 (('Дата и время','Date and time','日期与时间'),('journal_rows.date','journal_rows.time','journal_rows.utc_offset')),
 (('Параметры установки','Setup parameters','装置参数'),('journal_rows.settings',)),
 (('Образец','Sample','样品'),('journal_rows.sample',)),
 (('Измерение','Measurement','测量'),('journal_rows.measurement','journal_rows.source_reference')),
 (('Оператор','Operator','操作人'),('journal_rows.operator',)),
 (('Замечания','Remarks','备注'),('journal_rows.notes','journal_template','evidence_gaps','notices'))]},
'uncertainty':{'uncertainty_budget':[
 (('Входная величина','Input quantity','输入量'),('measurement_model','output_unit','budget.output_unit','budget.components.id','budget.components.unit')),
 (('Оценка','Estimate','估计'),('budget.estimate','budget.components.estimate','budget.reported_result')),
 (('Тип A и B','Type A and B','A类及B类'),('budget.components.type','budget.components.distribution','budget.components.repeat_count','budget.components.source_reference')),
 (('Стандартная неопределённость','Standard uncertainty','标准不确定度'),('budget.components.standard_uncertainty','budget.components.sample_standard_deviation','budget.combined_standard_uncertainty')),
 (('Коэффициент чувствительности','Sensitivity coefficient','灵敏度系数'),('budget.components.sensitivity','budget.components.sensitivity_unit','budget.components.sensitivity_reference','budget.components.output_unit','budget.sensitivities_symbolically_verified')),
 (('Вклад','Contributions and covariance','贡献及协方差'),('budget.components.signed_contribution','budget.components.variance_contribution','budget.correlation_matrix','budget.correlation_source_reference','budget.input_covariance_matrix','budget.input_covariance_units','budget.signed_output_covariance_matrix','budget.combined_variance')),
 (('Расширенная неопределённость','Expanded uncertainty','扩展不确定度'),('budget.coverage_factor','budget.expanded_uncertainty','budget.coverage_statement','budget.coverage_probability_not_inferred','budget.propagation','budget.type_A_counted_only_once_per_component','budget.psd_method','budget.reporting_gaps','budget.source_reference','no_unjustified_outlier_removal','no_automatic_systematic_correction'))]},
'radiation_safety':{'rad_instruction':[
 (('Источники и помещения','Sources and rooms','源及场所'),('scope','event_date','source','selected_rule_metadata')),
 (('Допуск персонала','Personnel access evidence','人员准入证据'),('document_inventory@personnel_training','document_inventory@organization_permissions')),
 (('Дозиметрический контроль','Dosimetric monitoring','剂量监测'),('document_inventory@dosimetry','document_inventory@radiation_control','dose_estimate')),
 (('Учёт и хранение','Accounting and storage','登记及储存'),('document_inventory@source_inventory','document_inventory@storage')),
 (('Порядок работ','Proposed work','拟议工作'),('proposed_work',)),
 (('Действия при аварии','Selected emergency records','所选应急记录'),('document_inventory@emergency_plan','evidence_gaps','notices'))]},
'lab_hazards':{'hazard_review':[
 (('Опасность','Hazard','危险'),('scope','hazard_reviews.id','hazard_reviews.type','hazard_reviews.parameters')),
 (('Источник','Sources and selected risk model','来源及所选风险模型'),('hazard_reviews.evidence_gaps','selected_risk_matrix')),
 (('Меры','Observed and proposed controls','已观察及拟议控制'),('hazard_reviews.observed_controls','hazard_reviews.proposed_controls')),
 (('Блокировки','Interlock evidence and limits','联锁证据及限制'),('hazard_reviews.observed_controls','hazard_reviews.risk_score','notices')),
 (('Средства индивидуальной защиты','Protective equipment evidence','防护用品证据'),('hazard_reviews.parameters.eye_protection_basis','hazard_reviews.evidence_gaps')),
 (('Ответственный','Responsible person','责任人'),('hazard_reviews.responsible',))]},
'facility_time':{'facility_proposal':[
 (('Научное обоснование','Scientific case','科学理由'),('task','scope','proposal.scientific_case','proposal.facility_id','proposal.call_id')),
 (('Предварительные результаты','Preliminary results','初步结果'),('proposal.preliminary_results',)),
 (('Образцы и безопасность','Samples and safety questions','样品及安全问题'),('proposal.sample_safety',)),
 (('План смен','Shift and resource plan','班次及资源计划'),('requirements','candidate_reviews','shift_budget')),
 (('Ожидаемые результаты','Expected outcomes','预期结果'),('proposal.expected_outcomes','evidence_gaps','notices'))]},
'publication':{'paper':[
 (('Аннотация','Abstract','摘要'),('title','version','journal','draft_sections.abstract')),
 (('Введение','Introduction','引言'),('draft_sections.introduction',)),
 (('Метод и установка','Method and setup','方法及装置'),('draft_sections.method',)),
 (('Результаты','Results','结果'),('results',)),
 (('Систематика','Systematics','系统误差'),('systematics',)),
 (('Выводы','Conclusions','结论'),('draft_sections.conclusions','draft_sections.reviewer_response')),
 (('Данные и код','Data and code','数据及代码'),('data_code','reference_review','contributor_review','license_record','review_records','evidence_gaps','notices'))]},
'rd_reports':{'nir_report_phys':[
 (('Реферат','Abstract','摘要'),('project_id','scope','draft_sections.abstract')),
 (('Введение','Introduction','引言'),('draft_sections.introduction','agreement_review','milestone_review')),
 (('Методы','Methods','方法'),('draft_sections.methods',)),
 (('Результаты с неопределённостями','Results with uncertainty','含不确定度结果'),('results','budget_review')),
 (('Заключение','Conclusion','结论'),('draft_sections.conclusion','export_review','reporting_obligations')),
 (('Источники','Sources','来源'),('agreement_review','evidence_gaps','notices'))]},
}
XLSX={'exp_log','uncertainty_budget','hazard_review'}
BOUNDS=('as_of','jurisdiction','input_sha256','assisted_draft','analysis_only','private','external_network_used','external_actions','equipment_controlled','equipment_control_performed','startup_authorized','signature_applied','submission_performed','publication_cleared','export_classification_made','export_classification_performed','source_semantics_verified','current_legal_applicability_verified','arithmetic_precision_digits','external_code_executed','human_review_required')

def _path(value,path):
    if not path:return value,True
    key,*rest=path.split('.')
    if isinstance(value,list):
        rows=[]
        for index,item in enumerate(value,1):
            selected,present=_path(item,path)
            if present:rows.append({'record_index':index,path.split('.')[-1].split('@')[0]:selected})
        return rows,bool(rows)
    if not isinstance(value,dict):return None,False
    if '@' in key:
        key,identity=key.split('@',1)
        if key not in value:return None,False
        return [row for row in value[key] if row.get('id')==identity],True
    if key not in value:return None,False
    return _path(value[key],'.'.join(rest))

def _content(function,artifact,result,language):
    u=UI[language];sections=[dict(title=u['summary'],paragraphs=[u['advice']],rows=flat({key:result[key] for key in ('mode','dimensions_consistent','evidence_gaps','notices') if key in result},language))]
    if function=='radiation_safety':sections.append(dict(title=tr(('Перечень выбранных документов','Selected document inventory','所选文件清单'),language),paragraphs=[],rows=flat({'document_inventory':result['document_inventory']},language)))
    if function=='uncertainty':
        for key,title in [('fit',('Взвешенная линейная аппроксимация','Weighted linear fit','加权线性拟合')),('qc',('Контроль серии','Series control','序列控制'))]:
            if result.get(key) is not None:sections.append(dict(title=tr(title,language),paragraphs=[],rows=flat({key:result[key]},language)))
    for title,paths in SECTIONS[function][artifact]:
        selected={}
        for path in paths:
            value,present=_path(result,path)
            if present:selected[path]=value
        inapplicable=function=='uncertainty' and result.get('budget') is None and any(p.startswith('budget.') for p in paths) and not any(p in ('measurement_model','output_unit') for p in paths)
        if inapplicable:
            paragraph=tr(('Бюджет GUM не запрошен в выбранном режиме. Результаты статистической обработки приведены в отдельном разделе.','A GUM budget was not requested in the selected mode. Statistical processing results appear in a separate section.','所选模式未请求GUM预算，统计处理结果见单独章节。'),language)
            other={key:value for key,value in selected.items() if not key.startswith('budget.')}
            sections.append(dict(title=tr(title,language),paragraphs=[paragraph],rows=flat(other,language) if other else [],source_paths=list(paths),selected_paths=list(other),not_applicable=True))
        else:sections.append(dict(title=tr(title,language),paragraphs=[] if selected else [u['missing']],rows=flat(selected,language) if selected else [],source_paths=list(paths),selected_paths=list(selected)))
    used={path.split('.')[0].split('@')[0] for specs in SECTIONS[function].values() for title,paths in specs for path in paths}
    if function=='uncertainty':used.update(('budget','fit','qc','mode'))
    remaining={k:v for k,v in result.items() if k not in used and k not in BOUNDS and k not in ('function','evidence_gaps','notices')}
    if remaining:sections.append(dict(title=tr(('Дополнительные сведения','Additional information','补充资料'),language),paragraphs=[],rows=flat(remaining,language),additional_subject_fields=sorted(remaining)))
    sections.append(dict(title=u['bounds'],paragraphs=[u['disclaimer_note']],rows=flat({key:result[key] for key in BOUNDS if key in result},language)))
    return sections

def _validate_result(function,result):
    if function not in SECTIONS or type(result) is not dict:raise ValueError('physicist_function_result_required')
    authority={'external_actions','equipment_controlled','equipment_control_performed','startup_authorized','signature_applied','submission_performed','publication_cleared','export_classification_made','export_classification_performed'}
    def visit(value,depth=0):
        if depth>24:raise ValueError('artifact_nesting_limit')
        if isinstance(value,dict):
            for key,item in value.items():
                if (key in authority or key.endswith(('_approved','_confirmed','_signed')) or key in ('source_semantics_verified','current_legal_applicability_verified')) and item is True:raise ValueError('unsupported_final_or_verified_claim:'+key)
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
    files={'result.json':(json.dumps(dict(function=function,result=result,review_evidence=review_evidence,result_rebound_to_config=True),ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')}
    for artifact in SECTIONS[function]:
        title=tr(TITLES[artifact],language);content=_content(function,artifact,result,language)+extra_sections(review_evidence,language)
        writer=xlsx_bytes if artifact in XLSX else docx_bytes
        files[artifact+('.xlsx' if artifact in XLSX else '.docx')]=writer(title,content,language,review_evidence)
        files[artifact+'.pdf']=pdf_bytes(title,content,language,review_evidence)
    return files
