"""Local climate document rendering with exact recomputation and typed leaf coverage."""
import json
from .artifact_labels import UI,TOKENS,TITLES,TEMPLATES,FIELDS,tr,field_label,token,LANGUAGES
from .artifact_formatting import snapshot,display_text,scalar,LITERAL_FIELDS,flat,extra_sections,docx_bytes,pdf_bytes,xlsx_bytes

# Each original logical section retains its own data routes. Deeper routes win;
# residual nested leaves remain in the nearest logical section, never a JSON dump.
ROUTES={
'data_provenance':{'data_card':[
('datasets.id','datasets.version','datasets.source_reference','datasets.reference_date','mode','questions'),
('datasets.variable','datasets.unit','datasets.calendar'),
('datasets.kind','datasets.location','datasets.station_changes'),
('datasets.start','datasets.end','datasets.frequency','datasets.expected_records','datasets.provided_records','datasets.usable_unique_records','datasets.coverage_ratio','datasets.missing_or_unusable_periods','datasets.outside_periods','datasets.quality_counts','datasets.duplicate_groups','datasets.range_flags'),
('datasets','evidence_gaps')]},
'normals_anomalies':{'climate_summary':[
('series','aggregation','questions'),
('targets.value','targets.year','targets.period','targets.months','targets.selected_coordinates'),
(),
(),
('baseline','coverage_rule','monthly_normals','targets'),
('evidence_gaps','source_record_count','unusable_record_count')]},
'trends_extremes':{'trend_note':[
('trend.series','trend.selected_years','trend.valid_count','trend.provided_count','trend.missing_or_unusable_years','daily_indices.series','daily_indices.start','daily_indices.end','daily_indices.coverage','return_levels.annual_block_years'),
('trend.dependence','trend.annual_spacing_regular','trend.rank_autocorrelations','trend.variance_multiplier','trend.critical_z','trend.p_method','trend.tau_definition','trend.test_rule_reference','daily_indices.thresholds','daily_indices.definition_reference','daily_indices.window_policy','daily_indices.run_boundary','return_levels.mode','return_levels.selected_parameters','return_levels.shape_convention','return_levels.critical_z','return_levels.uncertainty_rule_reference','return_levels.fit_provenance','external_results'),
('trend',),
('daily_indices','return_levels'),
('evidence_gaps',)]},
'scenarios_downscaling':{'scenario_note':[
('mode','method','unit','calendar','models.id','models.source_id','models.variant_label','models.grid_label','models.version','models.reference_date','models.source_reference','models.observation_reference','models.observation_dataset_reference_date','external_results.engine','external_results.version','external_results.configuration_sha256','external_results.data_sha256','external_results.source_reference','external_results.calendar','external_results.run_date'),
('models','external_results.method','external_results.baseline'),
('projections','ensemble.weighted_change','ensemble.horizon','ensemble.scenario_summaries','external_results.results'),
('ensemble','evidence_gaps'),
('panel_policy','weather_forecast','external_results.engine_executed_here')]},
'climate_risk_adaptation':{
'risk_assessment':[
('object','horizon','context','mode','questions','selected_documents'),
('hazards.id','hazards.hazard','hazards.asset','hazards.evidence','hazards.metrics','hazards.scenario_context'),
('hazards.exposure','hazards.vulnerability'),
('selected_matrix','hazards.evaluation_basis','hazards.likelihood_category','hazards.consequence_category','hazards.classification_status','risk_interpretation'),
('hazards','measures','evidence_gaps')],
'adaptation_plan':[
('object','horizon','context','hazards','selected_matrix','selected_documents','risk_interpretation','mode','questions'),
('measures.id','measures.hazard_ids','measures.action','measures.tradeoffs','measures.source_reference'),
('measures.responsible','measures.deadline'),
('measures.indicator',),
('measures.funding',),
('measures.monitoring','evidence_gaps','effectiveness_established')]},
'ghg_inventory':{'ghg_report':[
('organization','reporting_year','framework','boundary','consolidation','mode','questions','eligibility_review','deadline'),
('source_reviews.provided.id','source_reviews.provided.activity_id','source_reviews.provided.site_id','source_reviews.provided.category','source_reviews.reporting_bucket','source_reviews.provided.gas','source_reviews.provided.carbon_origin','source_reviews.provided.source_reference','source_reviews.provided.excerpt','exclusion_reviews'),
('source_reviews.provided.parameters.activity','source_reviews.provided.parameters.mass','source_reviews.provided.parameters.amount','source_reviews.provided.period_start','source_reviews.provided.period_end','source_reviews.provided.attribution','quality_reviews'),
('methods','gwp','source_reviews.provided.method_id','source_reviews.model','source_reviews.provided.parameters.factor','source_reviews.provided.parameters.net_calorific_value','source_reviews.provided.oxidation','source_reviews.provided.oxidation_mode','source_reviews.selected_GWP100','source_reviews.provided.co2e_basis','source_reviews.co2e_basis_metadata'),
('source_reviews','gas_totals_by_scope','scope_totals_tCO2e','separate_fluxes_tCO2e'),
('corporate_aggregate_tCO2e','corporate_aggregate_status','RU_direct_gross_candidate_tCO2e','scope_totals_status','scope_totals_by_basis','gas_disaggregation_status','evidence_gaps')]},
'climate_project':{'project_concept':[
('project','mode','questions','risk_reviews','additionality_reviews','double_counting_review'),
('project.baseline_description','quantification.baseline_procedure','quantification.period_reviews.provided.baseline_emissions','quantification.period_reviews.provided.baseline_removals','quantification.period_reviews.component_values.baseline_emissions','quantification.period_reviews.component_values.baseline_removals'),
('project.project_scenario','quantification.period_reviews.provided.project_emissions','quantification.period_reviews.provided.project_removals','quantification.period_reviews.component_values.project_emissions','quantification.period_reviews.component_values.project_removals'),
('quantification','carbon_units_quantity','carbon_units_status','creditable_units','creditable_status'),
('monitoring',),
('assurance_record_reviews','evidence_gaps'),
('economics',)]},
'design_climate':{'design_climate_note':[
('location','object_type','station','mode','questions'),
('parameters','supplementary_context'),
('selected_documents',),
('limitations','evidence_gaps','parameter_scope')]},
'climate_publication':{'climate_summary':[
('audience','purpose','mode','questions','authorship','draft_sections.main','statements@main'),
('draft_sections.temperature','statements@temperature'),
('draft_sections.precipitation','statements@precipitation'),
('draft_sections.extremes','statements@extremes'),
('draft_sections.comparison','statements@comparison'),
('draft_sections.confidence','statements@confidence','statements','references','limitations','evidence_gaps')]}
}
BOUND_SUFFIXES=('_approved','_certified','_established','_performed','_issued','_registered','_applied','_authorized','_verified','_executed')
BOUNDS={'input_sha256','as_of','jurisdiction','analysis_only','assisted_draft','external_actions','arithmetic_precision','interpretation'}
# These records belong with their scientific/ledger context, even if their name
# ends in a general authority suffix.
CONTEXT_FIELDS={'selected_by_critical_rule','coverage_established','nominal_coverage_established','official_standard_status_established','calibration_validation_disjoint','engine_executed_here','effectiveness_established'}
def _is_bound(key):return key in BOUNDS or key not in CONTEXT_FIELDS and key.endswith(BOUND_SUFFIXES)

def _leaves(value,path=(),parents=()):
    if type(value) is dict and value:
        for key,item in value.items():yield from _leaves(item,path+(key,),parents+((path,value),))
    elif type(value) is list and value:
        for i,item in enumerate(value):yield from _leaves(item,path+(str(i),),parents+((path,value),))
    else:yield path,value,parents

def _score(pattern,path,parents):
    plain=tuple(v for v in path if not v.isdigit())
    if '@' not in pattern:
        parts=tuple(pattern.split('.'));return len(parts) if plain[:len(parts)]==parts else -1
    base,topic=pattern.split('@',1);parts=tuple(base.split('.'))
    if plain[:len(parts)]!=parts:return -1
    return len(parts)+1 if any(type(v) is dict and v.get('topic')==topic for _,v in parents) else -1

def _semantic_key(path):
    return next((v for v in reversed(path) if not v.isdigit()),'value')

def _label_component(path,index,language):
    # Dynamic model identifiers and gas species are source keys, not UI fields.
    if path[index]=='baseline' and index and path[index-1]=='indicator':
        return tr(('Исходное значение индикатора','Indicator baseline value','指标基准值'),language)
    if index and path[index-1]=='normalized_model_weights':return display_text(path[index])
    if index>=2 and path[index-2]=='gas_totals_by_scope':return display_text(path[index])
    if path==('scope_totals_tCO2e',):return tr(('Сводные итоги по известному столетнему основанию','Summary totals on a known one hundred year basis','已知百年依据的汇总结果'),language)
    return field_label(path[index],language)

def _shown(function,path,value,parents,result,language):
    key=_semantic_key(path)
    if type(value)is str and path[0]=='draft_sections':return display_text(value)
    if type(value)is str and key in ('fields','comparability_gaps','topic') and value in FIELDS:return field_label(value,language)
    if type(value)is str and ((function=='data_provenance' and key=='frequency') or (function=='normals_anomalies' and key=='period' and path[0]=='targets')):return token(value,language)
    if type(value)is str and ((function=='scenarios_downscaling' and path==('method',)) or (function=='ghg_inventory' and key=='model')) and value in TOKENS:return token(value,language)
    if function=='climate_publication' and key=='draft_sections' and value=={}:return token('not_requested',language)
    if value is None:
        if function=='normals_anomalies' and key=='percent_anomaly':
            if result['aggregation']!='monthly_total_sum':return tr(('Не используется для выбранного анализа средних','Not used for selected mean analysis','所选均值分析不使用此项'),language)
            if any(type(parent)is dict and parent.get('normal')=='0' for _,parent in parents):return tr(('Отношение не определено при нулевой базе','Ratio undefined at zero baseline','基准为零时比值未定义'),language)
        if function=='scenarios_downscaling' and key=='percent_change' and result.get('method')=='additive_mean':return tr(('Не используется для аддитивного изменения','Not used for additive change','加性变化不使用此项'),language)
        if function=='climate_project' and key in ('irr','irr_interval'):
            return token('not_requested' if result.get('economics',{}).get('irr_status')=='not_requested' else 'not_defined',language)
        if function=='ghg_inventory' and key in ('gross_mass_t_gas','attributed_mass_t_gas','selected_GWP100'):
            aggregate=any(type(parent)is dict and parent.get('model') in ('activity_CO2e_factor','provided_CO2e') for _,parent in parents)
            if aggregate:return tr(('Не используется в ветви готового CO2 эквивалента','Not used in the preaggregated CO2 equivalent branch','已汇总二氧化碳当量分支不使用此项'),language)
        if function=='ghg_inventory' and key=='gwp':return tr(('Таблица GWP не выбрана для ветви готового CO2 эквивалента','No GWP table selected for preaggregated CO2 equivalent branch','已汇总二氧化碳当量分支未选择GWP表'),language)
        if function=='ghg_inventory' and key=='scope_totals_tCO2e':
            status=result.get('scope_totals_status')
            return token(status,language) if status in TOKENS else tr(('Сводный итог не вычислен см состояние сводки','Summary total not calculated see summary status','尚未计算汇总总量，请参阅汇总状态'),language)
        if function=='ghg_inventory' and key in ('set_id','horizon_years','horizon') and any(part in path for part in ('co2e_basis','co2e_basis_metadata','scope_totals_by_basis')):
            return tr(('Неизвестно по выбранным метаданным','Unknown in selected metadata','所选元数据中未知'),language)
        if function=='trends_extremes' and path[0]=='return_levels' and key in ('critical_z','uncertainty_rule_reference') and result.get('return_levels',{}).get('mode')=='selected_gev_parameters':
            return tr(('Не используется для диапазона предоставленных повторов','Not used for the supplied replicate range','所提供重复结果范围不使用此项'),language)
        if function=='data_provenance' and key=='selected_range_check':return token('not_requested',language)
        if function=='ghg_inventory' and key in ('deadline','eligibility_review'):return token('not_requested',language)
        if function=='trends_extremes' and key=='observed_segment_statistic':
            return token('not_requested' if result.get('daily_indices',{}).get('window_policy')=='require_complete' else 'not_calculated',language)
        if function=='trends_extremes' and key=='fit_provenance':return token('not_requested',language)
        if function=='climate_risk_adaptation' and key=='physical_expected_loss':return tr(('Не вычисляется порядковой матрицей','Not calculated by the ordinal matrix','有序矩阵不计算该值'),language)
        if function=='climate_risk_adaptation' and key in ('priority','priority_label'):return tr(('Не классифицировано см статус сопоставления','Not classified see matching status','未分类，请参阅匹配状态'),language)
        if key in ('effective_from','effective_to','selected_applicability_date'):return token('not_established',language)
        if function=='trends_extremes' and len(path)==1:return token('not_requested',language)
        if key in ('corporate_aggregate_tCO2e',):return tr(('Не суммируется во избежание смешения альтернативных границ отчётности','Not aggregated to avoid mixing alternative reporting boundaries','不合计，以免混合替代报告边界'),language)
        if key=='RU_direct_gross_candidate_tCO2e':return token('not_calculated' if result.get('framework')=='RU_direct_draft' else 'not_requested',language)
        if function=='climate_project' and key=='separate_reversal_adjustment':
            included=any(type(parent)is dict and type(parent.get('provided'))is dict and parent['provided'].get('reversal_mode')=='included_in_project_emissions' for _,parent in parents)
            if included:return tr(('Учтено в проектных выбросах без повторной отдельной поправки','Included in project emissions without a second separate adjustment','已计入项目排放，不再另行重复调整'),language)
            return token('not_requested',language)
        if function=='climate_project' and key in ('quantification','economics'):return token('not_requested',language)
        if key in ('carbon_units_quantity','creditable_units'):return token('not_established',language)
        if key=='value' and (path[0]=='targets' or 'indices' in path):return token('not_calculated',language)
        if key in ('normal','anomaly','rank_descending_competition','rank_population','rank_tie_count','percent_anomaly','percent_change','lower','upper','return_level','slope_interval','asymptotic_two_sided_p','z','selected_variance_s','variance_multiplier','internal_variance','total_descriptive_variance','extrapolation_ratio_to_record_length','at_or_above_selected_threshold','exceeds_selected_critical_value','irr','irr_interval'):
            return token('not_calculated',language)
    if type(value) is str and (key in LITERAL_FIELDS or key.endswith(('_id','_ids','_unit','_units','_version','_reference','_refs'))):return display_text(value)
    if type(value) in (dict,list):return UI[language]['missing'] if type(value) is dict else UI[language]['none']
    return scalar(value,language)

def _summary(function,result,language):
    if function=='data_provenance':
        count=len(result.get('datasets',[]))
        return tr((f'Рассмотрено наборов данных {count}. Полнота относится к выбранным координатам и исходным флагам качества; однородность и право повторного использования этим обзором не удостоверяются.',f'{count} dataset records were reviewed. Completeness concerns selected coordinates and source quality flags; this review does not certify homogeneity or reuse rights.',f'已审查{count}个数据集记录。完整性仅涉及所选坐标及来源质量标志；本审查不认证均一性或再利用权。'),language)
    if function=='normals_anomalies':
        total=len(result['targets']);computed=sum(v['anomaly'] is not None for v in result['targets']);b=result['baseline']
        return tr((f'Базовый период {b["start_year"]}–{b["end_year"]}. Аномалия вычислена для {computed} из {total} выбранных периодов. Место в ряду относится только к явно выбранным годам сравнения.',f'The selected baseline is {b["start_year"]}–{b["end_year"]}. Anomalies were computed for {computed} of {total} selected periods. Ranks concern only explicitly selected comparison years.',f'所选基准时段为{b["start_year"]}–{b["end_year"]}。已为{total}个所选时段中的{computed}个计算距平；排名仅涉及明确选定的比较年份。'),language)
    if function=='trends_extremes':
        count=sum(result.get(k) is not None for k in ('trend','daily_indices','return_levels','external_results'))
        return tr((f'Представлено независимых ветвей анализа {count}. Тренд индексы и уровни повторяемости имеют отдельные исходные условия и ограничения; причинная атрибуция не устанавливается.',f'{count} independent analysis branches are presented. Trend indices and return levels have separate input conditions and limits; causal attribution is not established.',f'列示{count}个独立分析分支。趋势、指数与重现水平各有输入条件及限制；未确定因果归因。'),language)
    if function=='scenarios_downscaling':
        if result.get('mode')=='external_results_review':return tr(('Рассматривается выбранный экспорт внешнего расчёта. Его значения сохраняются с версией и условиями запуска; внешний инструмент здесь не выполнялся.','A selected external calculation export is reviewed. Its values retain source version and run conditions; the external engine was not executed here.','本次审查所选外部计算导出；保留数值、来源版本与运行条件，未在此执行外部工具。'),language)
        count=len(result.get('models',[]));projections=len(result.get('projections',[]))
        return tr((f'Выбрано моделей {count} и записей проекций {projections}. Коррекция проверяется на отдельной выборке; описательные веса и разброс не являются вероятностями сценариев или прогнозом погоды.',f'{count} models and {projections} projection records were selected. Adjustment is assessed on a separate validation set; descriptive weights and spread are not scenario probabilities or weather forecasts.',f'已选择{count}个模型及{projections}条预估记录。订正在独立验证集上评估；描述性权重与离散程度并非情景概率或天气预报。'),language)
    if function=='climate_risk_adaptation':
        hazards=len(result['hazards']);matched=sum(v['classification_status']=='selected_ordinal_cell_matched' for v in result['hazards']);measures=len(result['measures'])
        return tr((f'Опасностей в выбранном наборе {hazards}; совпавших ячеек порядковой матрицы {matched}; предложенных мер {measures}. Пробелы исходных сведений и реквизитов мер перечислены ниже.',f'The selected set contains {hazards} hazards {matched} matched ordinal cells and {measures} proposed measures. Missing evidence and measure details are listed below.',f'所选集合包含{hazards}项危险、{matched}个已匹配有序单元及{measures}项建议措施。下文列出证据及措施资料缺项。'),language)
    if function=='ghg_inventory':
        if not result.get('source_reviews'):return tr(('Числовой расчёт инвентаризации не выполнялся. Вопросы ниже помогают выбрать фактические границы данные о деятельности методики и источники коэффициентов.','No numeric inventory was calculated. The questions below help select actual boundaries activity data methods and factor sources.','尚未计算数值排放清单。下列问题用于选定实际边界、活动数据、方法与因子来源。'),language)
        count=len(result['source_reviews'])
        return tr((f'Обработано исходных записей {count}. Итоги сохраняются отдельно по выбранным контурам и основаниям CO2 эквивалента; альтернативные варианты Scope 2 не складываются в единый корпоративный итог.',f'{count} source records were processed. Totals remain separate by selected scope and CO2 equivalent basis; alternative Scope 2 results are not added into one corporate aggregate.',f'已处理{count}条来源记录。按所选边界与二氧化碳当量依据分别保留汇总；替代范围二结果不相加为企业总量。'),language)
    if function=='climate_project':
        q=result.get('quantification')
        if q is None:return tr(('Подготовлена авторская концепция без выбранной арифметики потоков. Для обсуждения проекта не требуются выдуманные объёмы сокращений или поглощений.','An authored concept is prepared without selected flux arithmetic. Project discussion requires no invented reductions or removals.','已编制作者概念草稿，尚未选择通量算术；讨论项目无需虚构减排或清除数量。'),language)
        value=q['total_net_benefit_tCO2e']
        return tr((f'Чистое изменение выбранных потоков {value} tCO2e. Это условная арифметика исходных величин; количество допускаемых или выпущенных углеродных единиц не определяется.',f'The net change of selected fluxes is {value} tCO2e. This is conditional input arithmetic; no creditable or issued carbon unit quantity is determined.',f'所选通量净变化为{value} tCO2e。这是输入值的条件性算术；未确定可记入或已签发碳单位数量。'),language)
    if function=='design_climate':
        count=len(result['parameters'])
        return tr((f'Предоставлено выбранных табличных параметров {count}. Каждый параметр сохраняет единицу таблицу строку столбец и выбранную редакцию. Репрезентативность и правовая применимость требуют отдельной проверки.',f'{count} selected tabular parameters were supplied. Each retains its unit table row column and selected edition. Representativeness and legal applicability require separate review.',f'已提供{count}项所选表格参数；各项保留单位、表格、行、列及版本。代表性与法律适用性须单独审查。'),language)
    counts={k:sum(v['kind']==k for v in result.get('statements',[])) for k in ('fact','inference','projection')}
    return tr((f'В выбранном наборе фактов {counts["fact"]} выводов {counts["inference"]} проекций {counts["projection"]}. Авторский текст и выбранные свидетельства показаны отдельно; независимая проверка ссылок и разрешение публикации не заявляются.',f'The selected set contains {counts["fact"]} facts {counts["inference"]} inferences and {counts["projection"]} projections. Authored text and selected evidence are separate; independent reference verification and publication clearance are not claimed.',f'所选集合包含{counts["fact"]}项事实、{counts["inference"]}项推论及{counts["projection"]}项预估。作者文本与所选证据分开列示，不声称已独立核验引文或许可发布。'),language)

def _content(function,artifact,result,language):
    specs=ROUTES[function][artifact]
    definitions=TEMPLATES[artifact]['sections']
    if len(specs)!=len(definitions):raise ValueError('artifact_section_count_mismatch')
    sections=[dict(title=tr(title,language),rows=[],paragraphs=[],source_paths=list(paths),selected_paths=[],rendered_leaf_values=[]) for title,paths in zip(definitions,specs)]
    for path,value,parents in _leaves(result):
        if not path or _is_bound(path[0]):continue
        choices=[(max((_score(p,path,parents) for p in paths),default=-1),i) for i,paths in enumerate(specs)]
        score,index=max(choices,key=lambda p:(p[0],-p[1]))
        if score<0:index=len(sections)-1
        # Unit-based display placement only. No station or climate quantity is
        # substituted; every target retains its actual variable and source.
        if function=='normals_anomalies' and path[0]=='targets' and len(path)>2 and path[2] in ('value','year','period','months','selected_coordinates'):
            unit=result['series']['unit'];index=1 if unit in ('degC','K') else 2 if unit in ('mm','mm/day') else 0
        section=sections[index];identities=[]
        for _,parent in parents:
            if type(parent)is dict and type(parent.get('id'))is str and parent['id'] not in identities:identities.append(parent['id'])
        label=' / '.join(identities+[_label_component(path,i,language) for i in range(max(0,len(path)-3),len(path))])
        shown=_shown(function,path,value,parents,result,language)
        prose=(function=='climate_publication' and path[0]=='draft_sections' or function=='climate_project' and len(path)==2 and path[0]=='project' and path[1] in ('description','baseline_description','project_scenario','boundary_description'))
        if prose and type(value)is str:section['paragraphs'].append(display_text(value))
        else:section['rows'].append([label,shown])
        section['selected_paths'].append('.'.join(path))
        section['rendered_leaf_values'].append(dict(path='.'.join(path),value=value,display=shown))
    for section in sections:
        if not section['rows'] and not section['paragraphs']:
            section['paragraphs']=[tr(('Для этого раздела нет записей в выбранной ветви исходных данных','No records for this section in the selected input branch','所选输入分支中无本节记录'),language)]
    sections[0]['paragraphs'].insert(0,_summary(function,result,language))
    if function=='climate_risk_adaptation':
        sections[0]['paragraphs'].append(token('ordinal_lookup_not_probability_or_expected_loss',language))
    if function=='design_climate':
        sections[0]['paragraphs'].append(token('selected_normative_table_values_only_no_automatic_station_substitution',language))
    if function=='climate_publication':
        sections[0]['paragraphs'].append(tr(('Авторский текст отделён от тезисов с выбранными источниками. Факт вывод и проекция имеют разные основания.','Authored text is separate from statements with selected sources. Facts inferences and projections have different bases.','作者文本与关联所选来源的论述分开；事实、推论与预估各有不同依据。'),language))
    if function=='ghg_inventory' and result.get('source_reviews'):
        rows=[]
        for number,group in enumerate(result.get('scope_totals_by_basis',[]),1):
            set_name=group['set_id'] if group['set_id'] is not None else tr(('Набор неизвестен','Set unknown','集合未知'),language)
            horizon=str(group['horizon_years'])+' '+tr(('лет','years','年'),language) if group['horizon_years'] is not None else tr(('Горизонт неизвестен','Horizon unknown','时段未知'),language)
            for key,value in {**group['scope_totals_tCO2e'],**group['separate_fluxes_tCO2e']}.items():
                rows.append([token(key,language),str(number),set_name+'\n'+horizon,str(value)+' tCO2e'])
        if rows:
            summary=dict(title=tr(('Сводные итоги по выбранным основаниям','Summary by selected basis','按所选依据汇总'),language),paragraphs=[_summary(function,result,language),tr(('Группы сопоставлены только по предоставленным идентификаторам. Это не удостоверяет смысловую эквивалентность методик. Неизвестные или несовместимые основания не объединяются.','Groups are compared only by supplied identifiers. This does not certify semantic equivalence of methods. Unknown or incompatible bases are not combined.','分组仅按所提供标识比较，不认证方法的语义等价性；未知或不兼容依据不合并。'),language)],columns=[tr(('Контур или отдельный поток','Scope or separate flux','边界或独立通量'),language),tr(('Группа основания','Basis group','依据分组'),language),tr(('Набор и горизонт из выбранных метаданных','Set and horizon from selected metadata','所选元数据中的集合与时段'),language),tr(('CO2 эквивалент в тоннах','CO2 equivalent in tonnes','二氧化碳当量，吨'),language)],rows=rows,source_paths=[],selected_paths=[],rendered_leaf_values=[],additional_summary=True)
            sections.insert(0,summary)
    bounds={k:v for k,v in result.items() if _is_bound(k)}
    sections.append(dict(title=tr(('Область проверки инструментом','Scope of tool checks','工具校核范围'),language),paragraphs=[UI[language]['verification_scope']],rows=flat(bounds,language),source_paths=sorted(bounds),selected_paths=sorted(bounds),rendered_leaf_values=[dict(path=k,value=v,display=scalar(v,language)) for k,v in bounds.items()]))
    return sections

def render(function,result,language,*,config,review_evidence=None):
    if language not in LANGUAGES or function not in ROUTES:raise ValueError('artifact_function_language')
    # Reject non-JSON objects before helper normalization; comparison keeps
    # bool/int/string/null distinctions through canonical JSON.
    try:
        json.dumps(result,allow_nan=False);json.dumps(config,allow_nan=False)
    except (TypeError,ValueError):raise ValueError('artifact_json_values_required') from None
    result=snapshot(result);config=snapshot(config)
    review_evidence=snapshot(review_evidence) if review_evidence is not None else None
    from .core import execute
    canonical=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    if canonical(execute(function,config))!=canonical(result):raise ValueError('artifact_result_input_mismatch')
    files={'result.json':(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')}
    for artifact in ROUTES[function]:
        sections=_content(function,artifact,result,language)+extra_sections(review_evidence,language)
        title=tr(TITLES[artifact],language)
        files[artifact+'.'+TEMPLATES[artifact]['format']]=(xlsx_bytes if TEMPLATES[artifact]['format']=='xlsx' else docx_bytes)(title,sections,language,review_evidence)
        files[artifact+'.pdf']=pdf_bytes(title,sections,language,review_evidence)
    return files

