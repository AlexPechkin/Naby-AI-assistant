"""Private structural engineering drafts rebound to their exact validated input."""
import json
from .artifact_labels import UI,TITLES,LANGUAGES,tr,field_label,TOKENS,token
from .artifact_formatting import snapshot,flat,extra_sections,docx_bytes,pdf_bytes,xlsx_bytes,LITERAL_FIELDS,display_text

# Every original passport section is retained. Paths route actual nested fields;
# unlisted descendants stay with the nearest mapped parent, never disappear.
REPORT=[
 (('Исходные данные','Initial data','基础资料'),('as_of','jurisdiction','model_review.context','object','site','context','member_id','material_class','selected_section','selected_material_properties','site_id','igi')),
 (('Нормы','Standards','规范'),('standards','selected_requirements','selected_rule','selected_parameters','model_basis','stability_basis','masonry_basis','option_reviews.model_basis','option_reviews.characteristic_basis','option_reviews.bearing.model_basis','option_reviews.settlement.model_basis','differential_settlement.model_basis')),
 (('Расчётная схема и модель','Structural scheme and model','计算模型与结构方案'),('mode','model_review.topology_review','model_review.stiffness_review','model_review.mesh_review','model_review.mesh_review_status','model_review_status','model_review','geometry','section','material','model','foundation','ground','contact','geology','model_scope','force_basis','section_properties','reinforcement','option_reviews.type','option_reviews.role','option_reviews.B','option_reviews.L','option_reviews.force_basis')),
 (('Нагрузки и сочетания','Loads and combinations','荷载与组合'),('loads','demand','demands','actions','combinations','input_actions','model_review.equilibrium_checks.applied_resultants','combination_reviews.provided_forces','option_reviews.load_reviews.provided')),
 (('Результаты и проверки','Results and checks','结果与校核'),('checks','results','verification','member_results','contact_review','settlement','resistance','pile','model_review.equilibrium_checks','model_review.support_compression_reviews','combination_reviews','serviceability','option_reviews','differential_settlement','independent_beam.total_applied_kN','independent_beam.reaction_left_kN','independent_beam.reaction_right_kN','independent_beam.midspan_sagging_moment_kNm','independent_beam.midspan_displacement_m')),
 (('Независимые проверки','Independent checks','独立校核'),('independent_beam','independent_beam_status','independent_checks','comparison')),
 (('Выводы','Conclusions','结论'),('evidence_gaps','questions','recommendations','notices','scope_limits','limitations','exclusions','option_reviews.exclusions','option_reviews.evidence_gaps')),
]
SECTIONS={
'loads':{'loads_table':[
 (('Нагрузка','Action','荷载'),('site','structure_class','purpose','load_table')),
 (('Нормативное значение','Characteristic value','标准值'),('load_table.normative_value','load_table.unit','load_table.scope_id','load_table.component','load_table.derivation')),
 (('Коэффициент надёжности','Reliability factor','可靠度系数'),('combinations.gamma_n','combinations.terms.gamma_f','combinations.terms.psi','combinations.selection_basis')),
 (('Расчётное значение','Design value','设计值'),('combinations','envelopes')),
 (('Источник пункт СП','Source code clause','来源规范条款'),('standards','load_table.source_reference','combinations.source_reference','unused_action_ids','evidence_gaps'))]},
'fe_model':{'calc_report':REPORT},
'member_design':{'calc_report':REPORT},
'foundations':{'calc_report':REPORT},
'kr_section':{
'kr_explanatory':[
 (('Исходные данные и изыскания','Initial data and surveys','基础资料与勘察'),('object','stage','structure_class','sections.surveys','content_items','selected_requirements','requirement_review')),
 (('Нагрузки','Loads','荷载'),('sections.loads',)),
 (('Принятые конструктивные схемы','Selected structural schemes','选定结构方案'),('sections.schemes',)),
 (('Материалы','Materials','材料'),('sections.materials',)),
 (('Обоснование надёжности и устойчивости','Reliability and stability justification','可靠性与稳定性论证'),('sections.reliability',)),
 (('Защита конструкций','Structural protection','结构防护'),('sections.protection',)),
 (('Графическая часть','Graphical part','图纸部分'),('sections.graphics','sheets','specifications','details','link_checks','revisions','checklist','evidence_gaps'))],
'kr_checklist':[
 (('Общие данные','General data','总说明'),('object','stage','structure_class','checklist@general_data','sections','content_items','evidence_gaps')),
 (('Ссылочные документы','Referenced documents','引用文件'),('selected_requirements','requirement_review','checklist@reference_documents','link_checks')),
 (('Спецификации','Specifications','材料与构件明细'),('specifications','checklist@specifications')),
 (('Узлы','Details','节点'),('details','checklist@details')),
 (('Штампы и подписи','Title blocks and signatures','图签与签署'),('sheets','checklist@stamps_signatures')),
 (('Изменения','Changes','变更'),('revisions','checklist@changes'))]},
'inspection':{'inspection_report':[
 (('Цель и программа','Purpose and program','目的与方案'),('object','goal','program','selected_requirements')),
 (('Описание конструкций','Structure description','结构说明'),('construction_year','archive_records','access','structures')),
 (('Ведомость дефектов','Defect register','缺陷记录'),('defects','photos','risk_register','immediate_escalation_required')),
 (('Результаты испытаний','Test results','试验结果'),('test_results',)),
 (('Поверочный расчёт','Verification calculation','复核计算'),('verification_calculation','verification_calculation_performed')),
 (('Категория технического состояния','Technical condition category','技术状态类别'),('category_review',)),
 (('Рекомендации','Recommendations','建议'),('recommendations','evidence_gaps'))]},
'expertise_review':{'expertise_answers':[
 (('Номер замечания','Comment number','意见编号'),('object','comments.id','comments.owner','comments.due')),
 (('Суть','Essence','要点'),('comments.excerpt','comments.source_reference','comments.requirement_ids','comments.disposition')),
 (('Ответ','Response','答复'),('comments.proposed_response','comments.response_authorship','comments.expert_comment_closed','decision_log','scientific_support')),
 (('Изменённые листы и расчёты','Changed sheets and calculations','变更图纸与计算'),('comments.proposed_changes','supplied_documents','second_run','second_run_status')),
 (('Ссылка на норму','Requirement reference','规范引用'),('selected_requirements','evidence_gaps'))]},
'site_support':{'designer_answer':[
 (('Запрос','Request','请求'),('request','issue_history')),
 (('Анализ','Analysis','分析'),('design_records','observations','substitution_review','substitution_status','selected_requirements','required_checks')),
 (('Решение','Decision','决策'),('draft_response','decision_log','evidence_gaps','immediate_escalation_required','escalation_instruction')),
 (('Изменения в РД','Working document changes','施工图文件变更'),('rd_changes',)),
 (('Подпись ответственного','Responsible signature','负责人签署'),('responsible_signature_status',))]},
}
XLSX={'loads_table','kr_checklist','expertise_answers'}
BOUNDS={'input_sha256','as_of','jurisdiction','draft_only','assisted_draft','analysis_only','source_semantics_verified','current_legal_applicability_verified','external_actions','design_approved','design_approval','model_certified','fitness_for_use_certified','technical_category_assigned','drawings_issued','signature_applied','submission_performed','physical_work_authorized','graphical_content_generated','design_compliance_established','solver_executed','snow_wind_regional_lookup_performed','special_action_generation_performed','combination_generation_performed','function','private','source_semantics_established','current_normative_chain_established','design_approval_granted','safety_conclusion_made','records_changed','external_network_used','external_solver_executed','foundation_type_selected','no_soil_parameters_invented'}


def _leaves(value,path=(),parents=()):
    if type(value) is dict and value:
        for key,item in value.items():yield from _leaves(item,path+(key,),parents+((path,value),))
    elif type(value) is list and value:
        for i,item in enumerate(value):yield from _leaves(item,path+(str(i),),parents+((path,value),))
    else:yield path,value,parents


def _score(pattern,path,parents):
    plain=tuple(v for v in path if not v.isdigit())
    if '@' not in pattern:
        parts=tuple(pattern.split('.'))
        return len(parts) if plain[:len(parts)]==parts else -1
    base,topic=pattern.split('@',1);parts=tuple(base.split('.'))
    if plain[:len(parts)]!=parts:return -1
    return len(parts)+1 if any(type(v) is dict and v.get('category')==topic for _,v in parents) else -1


def _content(function,artifact,result,language):
    specs=SECTIONS[function][artifact];u=UI[language]
    sections=[{'title':tr(title,language),'rows':[],'paragraphs':[],'source_paths':list(paths),'selected_paths':[],'rendered_leaf_values':[]} for title,paths in specs]
    fallback=4 if artifact=='calc_report' else len(sections)-1
    for path,value,parents in _leaves(result):
        if not path or path[0] in BOUNDS:continue
        choices=[(max((_score(p,path,parents) for p in paths),default=-1),i) for i,(_,paths) in enumerate(specs)]
        score,index=max(choices,key=lambda p:(p[0],-p[1]))
        if score<0:index=fallback
        section=sections[index]
        identifiers=[]
        for _,parent in parents:
            if type(parent) is dict and type(parent.get('id')) is str and parent['id'] not in identifiers:identifiers.append(parent['id'])
        tail=path[-3:]
        label=' / '.join(identifiers+[field_label(p,language) for p in tail])
        if path[-1] in ('Wx','Wy'):
            unit='m3' if 'contact' in path else 'mm3'
            label+=' ['+unit+']'
        # Preserve the parent predicate context for null rendering, while never
        # changing source values, exact numerals, dates, symbols or versions.
        key=path[-1]
        semantic_key=next(part for part in reversed(path) if not part.isdigit())
        shown=flat({key:value},language)[0][1] if not isinstance(value,(dict,list)) else flat(value,language)[0][1]
        if isinstance(value,str) and (semantic_key in LITERAL_FIELDS or semantic_key.endswith(('_id','_ids','_unit','_units','_version','_reference'))):
            shown=display_text(value)
        if (key=='formula' or key=='method' and path[0]=='program') and isinstance(value,str) and value in TOKENS:shown=token(value,language)
        if value is None and key in ('reinforcement','stability_basis','masonry_basis','normalized_slenderness'):
            context_token='not_used_for_selected_non_RC_model' if key=='reinforcement' else 'not_used_for_selected_timber_model' if key=='normalized_slenderness' else 'not_requested'
            shown=token(context_token,language)
        if value is None and key=='cracked_section':shown=token('not_used_for_selected_non_RC_model',language)
        if value is None and key in ('minimum_pressure','maximum_pressure','average_contact_pressure','contact_fraction','eccentricity_x','eccentricity_y','utilization','within_selected_limit'):
            shown=token('not_calculated',language)
        section['rows'].append([label,shown]);section['selected_paths'].append('.'.join(path));section['rendered_leaf_values'].append({'path':'.'.join(path),'value':value,'display':shown})
    for section in sections:
        if not section['rows']:section['paragraphs'].append(u['missing'])
    if artifact=='calc_report' and function in ('member_design','foundations'):
        if not sections[5]['rows']:
            sections[5]['paragraphs']=[tr(('Независимый решатель или второй расчёт этим инструментом не запускался. Отдельные числовые сравнения не заменяют независимую инженерную проверку.','No independent solver or second calculation was run by this tool. Individual numerical checks do not replace independent engineering review.','本工具未运行独立求解器或第二次计算。单项数值校核不能替代独立工程复核。'),language)]
    if function=='foundations' and result.get('status')=='survey_data_required':
        sections[1]['paragraphs']=[tr(('Выбран режим вопросов без отчёта ИГИ. Расчётные нормы и параметры здесь не выбирались.','Questions without a geological survey were selected. Calculation standards and parameters were not selected here.','所选为无勘察报告提问模式；此处未选择计算规范或参数。'),language)]
    if function=='loads':
        sections[0]['paragraphs'].append(tr((f"В наборе {len(result['load_table'])} нагрузок и {len(result['combinations'])} явно выбранных сочетаний. Таблица сохраняет их области, знаки и источники.",f"The set contains {len(result['load_table'])} actions and {len(result['combinations'])} explicitly selected combinations. Their scopes, signs and sources are retained.",f"集合含{len(result['load_table'])}项荷载及{len(result['combinations'])}个明确选定组合，保留范围、符号与来源。"),language))
    elif function=='member_design':
        sections[0]['paragraphs'].append(tr((f"Проверки относятся к элементу {result['member_id']} и {len(result['combination_reviews'])} предоставленным сочетаниям. Указанные ниже пределы действуют только в выбранной ограниченной модели.",f"Checks concern member {result['member_id']} and {len(result['combination_reviews'])} supplied combinations. The limits below apply only within the selected bounded model.",f"校核针对构件{result['member_id']}及{len(result['combination_reviews'])}个已提供组合；下列限值仅适用于所选有限范围模型。"),language))
    elif function=='foundations':
        sections[0]['paragraphs'].append(tr((f"Для участка {result['site_id']} рассмотрено записей вариантов {len(result['option_reviews'])}. Ответственный специалист должен установить достаточность изысканий и применимость каждого метода.",f"For site {result['site_id']}, {len(result['option_reviews'])} option records were reviewed. The responsible specialist must establish survey sufficiency and each method's applicability.",f"场地{result['site_id']}审查了{len(result['option_reviews'])}条方案记录；勘察充分性与方法适用性须由负责专业人员确定。"),language))
    elif function=='inspection':
        sections[0]['paragraphs'].append(tr((f"Предоставлено дефектов {len(result['defects'])}; явно срочных записей {len(result['risk_register'])}. Категория состояния этим документом не присваивается.",f"The supplied set contains {len(result['defects'])} defects and {len(result['risk_register'])} explicitly urgent records. This document assigns no condition category.",f"已提供{len(result['defects'])}条缺陷及{len(result['risk_register'])}条明确紧急记录；本文件不评定状态类别。"),language))
    if function=='loads':
        # Comparative human table keeps characteristic values separate from
        # combination-dependent design factors and contributions.
        actionrows=[]
        for row in result['load_table']:
            actionrows.append([row['id']+'\n'+row['name'],row['normative_value']+' '+row['unit'],row['scope_id']+' / '+row['component'],row['source_reference']])
        sections[0]['columns']=[tr(('Нагрузка','Action','荷载'),language),tr(('Нормативное значение и единица','Characteristic value and unit','标准值与单位'),language),tr(('Область и компонент','Scope and component','范围与分量'),language),tr(('Источник','Source','来源'),language)]
        sections[0]['rows']=actionrows+[[r[0],r[1],'',''] for r in sections[0]['rows']]
        sections[3]['paragraphs'].append(tr(('Расчётные значения относятся к указанным сочетаниям. Вклад учитывает выбранные gamma f, psi и gamma n; огибающая нагрузки не является огибающей усилий элемента.','Design values belong to the named combinations. Contributions include selected gamma f, psi and gamma n; a load envelope is not an internal-force envelope.','设计值属于指定组合。贡献值包含选定的gamma f、psi及gamma n；荷载包络并非构件内力包络。'),language))
    if function in ('inspection','site_support') and result.get('immediate_escalation_required'):
        sections[0]['paragraphs'].insert(0,token('escalate_to_responsible_person_now_do_not_wait_for_report',language))
    sections.append({'title':u['bounds'],'paragraphs':[u['advice'],u['disclaimer_note']],'rows':flat({k:v for k,v in result.items() if k in BOUNDS},language),'source_paths':sorted(BOUNDS),'selected_paths':[k for k in result if k in BOUNDS]})
    return sections


def render(function,result,language,*,config,review_evidence=None):
    if language not in LANGUAGES or function not in SECTIONS:raise ValueError('artifact_function_language')
    result=snapshot(result);config=snapshot(config);review_evidence=snapshot(review_evidence) if review_evidence is not None else None
    from .core import execute
    canonical=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    if canonical(execute(function,config))!=canonical(result):raise ValueError('artifact_result_input_mismatch')
    if review_evidence is not None:
        if type(review_evidence) is not dict:raise ValueError('artifact_evidence_object')
        for key in ('bindings','assumptions'):
            if type(review_evidence.get(key,[])) is not list or any(type(v) is not dict for v in review_evidence.get(key,[])):raise ValueError('artifact_evidence_rows')
    files={'result.json':(json.dumps({'function':function,'result':result,'review_evidence':review_evidence,'result_rebound_to_config':True},ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')}
    for artifact in SECTIONS[function]:
        sections=_content(function,artifact,result,language)+extra_sections(review_evidence,language)
        title=tr(TITLES[artifact],language);writer=xlsx_bytes if artifact in XLSX else docx_bytes
        files[artifact+('.xlsx' if artifact in XLSX else '.docx')]=writer(title,sections,language,review_evidence)
        files[artifact+'.pdf']=pdf_bytes(title,sections,language,review_evidence)
    return files
