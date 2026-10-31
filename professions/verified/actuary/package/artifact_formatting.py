"""Bounded local actuarial document writers; never opens source URLs."""
from decimal import Decimal
from pathlib import Path
import io,json,html,re,hashlib
from .artifact_labels import UI,field_label,token

FONT_SHA256='842af9dfc97ca922a4ee589f41dcb12a0405d8314295a8be811cd90d8c5acdf3'


def snapshot(value):
    raw=json.dumps(value,ensure_ascii=False,allow_nan=False,default=lambda x:str(x) if isinstance(x,Decimal) else (_ for _ in ()).throw(ValueError('non_json_artifact_input')))
    if len(raw.encode('utf-8'))>8_000_000:raise ValueError('artifact_input_limit')
    parsed=json.loads(raw)
    def visit(x,depth=0):
        if depth>24:raise ValueError('artifact_nesting_limit')
        if isinstance(x,str):
            if len(x)>200000:raise ValueError('artifact_text_invalid')
            if any(0xD800<=ord(c)<=0xDFFF or ord(c) in (0xFFFE,0xFFFF) for c in x):raise ValueError('artifact_unicode_invalid')
        elif isinstance(x,dict):
            if len(x)>10000:raise ValueError('artifact_mapping_limit')
            for k,v in x.items():visit(k,depth+1);visit(v,depth+1)
        elif isinstance(x,list):
            if len(x)>2000:raise ValueError('artifact_array_limit')
            for v in x:visit(v,depth+1)
    visit(parsed);return parsed


def display_text(value):
    """Escape XML-illegal controls for display while raw values remain in JSON."""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',lambda m:'\\x%02X'%ord(m.group()),str(value))


def scalar(value,language):
    u=UI[language]
    if value is None:return u['missing']
    if type(value) is bool:return u['yes'] if value else u['no']
    return display_text(token(str(value),language))


LITERAL_FIELDS={'quote','excerpt','name','id','source_id','fact_id','source_reference','reference','source_sha256','segment_id','pointer','scope','edition','period','description','rationale','selection_rationale','statement','title','formula','unit','procedure','purpose','version','data_version','software','code','code_version','symbol','notes','comment','text','limitation','limitations','customer','client','executor','owner','responsible','objective','object','data_scope','currency','valuation_date','as_of','date','publication_date','effective_date','effective_from','effective_to','start_date','end_date','due_date','document_identity'}

def flat(value,language,prefix='',literal=False):
    """Expand data into labelled rows; never a JSON dump in a document section."""
    u=UI[language];rows=[]
    if isinstance(value,dict):
        if not value:return [[prefix or u['details'],u['missing']]]
        for key,item in value.items():
            label=field_label(key,language)
            if item is None:
                leaf=key.split('.')[-1]
                if leaf in ('effective_to','not_after'):item=token('not_established',language)
                elif leaf in ('average_claim','trended_average_claim') and value.get('average_claim_status')=='undefined_zero_claim_count':item=token('not_defined',language)
                elif leaf in ('statistical_standard_error','confidence_interval'):item=token('not_calculated',language)
                elif leaf in ('insured_sum_rate','insured_sum_rate_unit','employer_benefit_attribution'):item=token('branch_not_requested',language)
                elif leaf in ('gmm_initial','csm_rollforward','paa','vfa_review','claims','unearned_premium'):item=token('branch_not_requested',language)
                elif leaf=='numeric_comparison' and value.get('topic') not in ('experience','cpd'):item=token('branch_not_requested',language)
                elif leaf=='provided_date' and value.get('calculation') is not None and 'candidate_deadline' in value:item=token('branch_not_requested',language)
                elif leaf=='calculation' and value.get('provided_date') is not None and 'candidate_deadline' in value:item=token('branch_not_requested',language)
                elif leaf=='weight' and value.get('mode')=='not_estimated':item=token('not_estimated',language)
                elif leaf in ('ultimate','IBNR','unpaid') and value.get('status')=='BF_nonnegative_unemerged_fraction_not_satisfied':item=token('not_defined',language)
                elif leaf in ('ultimate','IBNR','unpaid') and value.get('status')=='BF_prior_not_supplied':item=token('not_calculated',language)
                elif leaf in ('observed_factor','conditional_ratio','conditional_capital_ratio','base_conditional_ratio'):item=token('not_defined',language)
                elif leaf in ('selected_amount','selected_exposure','identical_dedup_candidate_amount') and 'conflicting_duplicate_keys' in value.get('evidence_gaps',[]):item=token('not_computed_conflicting_duplicates',language)
                elif leaf=='difference' and ('control_amount' in value or 'control_value' in value):item=token('not_calculated',language)
                elif leaf=='reserve_reconciliation_difference':item=token('not_calculated',language)
            if item=={} and key.split('.')[-1]=='missing_field_counts':item=token('no_missing_required_fields_detected',language)
            if key=='days' and isinstance(item,dict) and item and all(re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(k)) and type(v) is bool for k,v in item.items()):
                item={'calendar_days_count':len(item),'working_days_count':sum(item.values()),'nonworking_days_count':len(item)-sum(item.values())}
            is_literal=literal or key in LITERAL_FIELDS or key.split('.')[-1].endswith(('_unit','_units'))
            if key=='scope' and item in ('issued_no_prior_recognised_assets_or_initial_settlements','selected_movements_no_new_contracts_or_full_fcf_reconciliation','selected_B104_fee_arithmetic_only_no_options_guarantees_or_full_VFA_measurement'):is_literal=False
            rows.extend(flat(item,language,(prefix+' / ' if prefix else '')+label,is_literal))
    elif isinstance(value,list):
        if not value:return [[prefix or u['items'],u['none']]]
        for index,item in enumerate(value,1):rows.extend(flat(item,language,(prefix+' / ' if prefix else '')+str(index),literal))
    else:rows.append([prefix or u['value'],display_text(value) if literal and isinstance(value,str) else scalar(value,language)])
    if len(rows)>15000:raise ValueError('artifact_rows_limit')
    return rows


def extra_sections(review_evidence,language):
    u=UI[language];review=review_evidence or {};out=[]
    confirmation=review.get('engagement_confirmation')
    if confirmation is not None:
        from .artifact_labels import tr
        if type(confirmation) is not dict:raise ValueError('engagement_confirmation_object_required')
        scope=confirmation.get('scope',{})
        selected={key:confirmation[key] for key in ('required','received','source','contract_signature_established','source_authenticity_established','legal_authority_established') if key in confirmation}
        selected['valuation_date']=scope.get('valuation_date');selected['data_scope']=scope.get('data_scope')
        selected['selected_document_count']=len(scope.get('source_sha256s',[]))
        note=tr(('Подтверждение даты, состава данных и выбранных документов передано вызывающим приложением. Это не подтверждение юридического согласования договора, подлинности источников или полномочий.','Valuation date, data scope and selected-document confirmation come from the calling application. This does not establish legal agreement of a contract, source authenticity or authority.','评估日、数据范围及所选文件确认来自调用应用，不证明合同法律同意、来源真实性或权限。'),language)
        if not confirmation.get('required'):note=tr(('Для этого предварительного анализа подтверждение контекста задания не обязательно. Отсутствие подтверждения не является отказом или запретом проверки.','Engagement-context confirmation is optional for this preliminary review. Its absence is not a refusal or prohibition of review.','此初步核查不强制确认任务上下文。缺少确认不表示拒绝或禁止核查。'),language)+' '+note
        out.append({'title':tr(('Контекст задания приложения','Application engagement context','应用任务上下文'),language),'paragraphs':[note],'rows':flat(selected,language),'evidence_section':True})
    assumptions=review.get('assumptions',[])
    if assumptions:
        rows=[[str(a.get('pointer','')),str(a.get('value',''))+' '+str(a.get('unit','')),str(a.get('rationale',''))] for a in assumptions]
        out.append({'title':u['assumptions'],'paragraphs':[u['assumption_banner']],'columns':[field_label('pointer',language),u['value'],field_label('rationale',language)],'rows':rows,'evidence_section':True})
    bindings=review.get('bindings',[])
    if bindings:
        sources={}
        for binding in bindings:
            digest=str(binding.get('source_sha256',''))
            if digest not in sources:sources[digest]=len(sources)+1
        index_rows=[[str(index),digest] for digest,index in sources.items()]
        out.append({'title':u['evidence'],'paragraphs':[u['unverified']],'columns':[field_label('reference',language),field_label('source_sha256',language)],'rows':index_rows,'evidence_section':True})
        rows=[]
        for binding in bindings:
            identity=str(binding.get('fact_id',''))+'\n'+str(binding.get('pointer',''))+'\n'+str(binding.get('unit',''))
            source=str(sources[str(binding.get('source_sha256',''))])+' / '+str(binding.get('segment_id',''))
            rows.append([identity,source,str(binding.get('quote',''))])
        out.append({'title':field_label('quote',language),'paragraphs':[],'columns':[field_label('fact_id',language),field_label('reference',language),field_label('quote',language)],'rows':rows,'evidence_section':True})
        conversions=[]
        operations={
          'percent_to_ratio':('Проценты в долю','Percent to ratio','百分数转比例'),
        }
        units={'percent':('%','%','%'),'ratio':('доля','ratio','比例')}
        from .artifact_labels import tr
        for binding in bindings:
            conversion=binding.get('conversion')
            if conversion is None:continue
            if type(conversion) is not dict or conversion.get('operation') not in operations:raise ValueError('artifact_conversion_operation_invalid')
            source_unit=str(conversion.get('source_unit',''));derived_unit=str(conversion.get('derived_unit',''))
            source=str(conversion.get('source_value',''))+' '+tr(units[source_unit],language) if source_unit in units else str(conversion.get('source_value',''))+' '+source_unit
            derived=str(conversion.get('derived_value',''))+' '+tr(units[derived_unit],language) if derived_unit in units else str(conversion.get('derived_value',''))+' '+derived_unit
            conversions.append([str(binding.get('pointer','')),source,tr(operations[conversion['operation']],language)+'\n'+derived])
        if conversions:
            out.append({'title':tr(('Явные преобразования единиц','Explicit unit conversions','明确单位换算'),language),'paragraphs':[tr(('Исходный факт и цитата сохранены без изменений. Преобразование единиц является отдельным явным шагом и не доказывает применимость нормы.','The source fact and quotation remain unchanged. Unit conversion is a separate explicit step and does not establish rule applicability.','来源事实和引文保持不变。单位换算是单独明确步骤，不证明规则适用性。'),language)],'columns':[field_label('pointer',language),tr(('Исходное значение','Source value','来源值'),language),tr(('Операция и полученное значение','Operation and derived value','操作及得到值'),language)],'rows':conversions,'evidence_section':True})
    else:out.append({'title':u['evidence'],'paragraphs':[u['sources_unconfirmed'],u['unverified']],'rows':[],'evidence_section':True})
    return out


def intro(language,review_evidence):
    u=UI[language];review=review_evidence or {}
    paragraphs=[u['draft'],u['source_note'],u['unverified'],u['control_notice'],u['verification_scope']]
    if review.get('assumptions') or review.get('hypothetical_inputs_present'):
        paragraphs.insert(0,u['assumption_banner'])
    if review.get('as_of'):paragraphs.append(u['as_of']+': '+str(review['as_of']))
    return paragraphs


def docx_bytes(title,sections,language,review_evidence):
    from docx import Document
    from docx.shared import Inches,Pt,RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc=Document();section=doc.sections[0]
    section.page_width=Inches(8.5);section.page_height=Inches(11)
    section.top_margin=section.bottom_margin=Inches(.65);section.left_margin=section.right_margin=Inches(.7)
    normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(11)
    normal.paragraph_format.space_after=Pt(6)
    normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'Microsoft YaHei')
    for style in ('Title','Heading 1','Heading 2'):
        doc.styles[style].font.color.rgb=RGBColor(0,0,0)
        doc.styles[style].font.name='Arial'
        properties=doc.styles[style].element.find(qn('w:pPr'))
        if properties is not None:
            for border in list(properties.findall(qn('w:pBdr'))):properties.remove(border)
    doc.core_properties.author='NABY';doc.core_properties.title=title
    doc.add_paragraph(title,'Title')
    for paragraph in intro(language,review_evidence):doc.add_paragraph(display_text(paragraph))
    for content in sections:
        doc.add_heading(content['title'],1)
        for paragraph in content.get('paragraphs',[]):doc.add_paragraph(display_text(paragraph))
        if content.get('rows'):
            columns=content.get('columns',[UI[language]['field'],UI[language]['value']])
            table=doc.add_table(rows=0,cols=len(columns));table.style='Light Shading Accent 1';table.autofit=False
            widths=content.get('widths',[2.3,4.8] if len(columns)==2 else [7.1/len(columns)]*len(columns))
            for column,width in zip(table.columns,widths):column.width=Inches(width)
            header=table.add_row().cells
            for cell,label in zip(header,columns):cell.text=display_text(label)
            repeat=OxmlElement('w:tblHeader');table.rows[0]._tr.get_or_add_trPr().append(repeat)
            for row in content['rows']:
                cells=table.add_row().cells
                for cell,value in zip(cells,row):cell.text=display_text(value)
            for row in table.rows:
                for cell in row.cells:
                    margins=OxmlElement('w:tcMar')
                    for edge in ('top','left','bottom','right'):
                        item=OxmlElement('w:'+edge);item.set(qn('w:w'),'100');item.set(qn('w:type'),'dxa');margins.append(item)
                    cell._tc.get_or_add_tcPr().append(margins)
                    borders=OxmlElement('w:tcBorders')
                    for edge in ('top','left','bottom','right'):
                        border=OxmlElement('w:'+edge);border.set(qn('w:val'),'single');border.set(qn('w:sz'),'4');border.set(qn('w:color'),'D9D9D9');borders.append(border)
                    cell._tc.get_or_add_tcPr().append(borders)
                    for paragraph in cell.paragraphs:
                        paragraph.paragraph_format.space_after=Pt(3)
                        for run in paragraph.runs:run.font.size=Pt(9)
            doc.add_paragraph('')
    stream=io.BytesIO();doc.save(stream);return stream.getvalue()


def _font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    name='NabyActuaryDocumentSans'
    path=Path(__file__).resolve().parent/'fonts'/'NabyActuaryDocumentSans.ttf'
    if not path.exists():path=Path(__file__).resolve().parent.parent/'_shared'/'fonts'/'NabyActuaryDocumentSans.ttf'  # NABY build 39: one shared copy
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=FONT_SHA256:raise ValueError('document_font_hash_mismatch')
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name,io.BytesIO(raw)))
    return name


def pdf_bytes(title,sections,language,review_evidence):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph,SimpleDocTemplate,Spacer,LongTable,TableStyle,CondPageBreak
    from reportlab.pdfbase import pdfmetrics
    font=_font();face=pdfmetrics.getFont(font).face
    def safe(value):
        value=display_text(value)
        if any(ord(c)>32 and ord(c) not in face.charToGlyph for c in value):raise ValueError('document_font_missing_glyph')
        return html.escape(value,quote=False).replace('\n','<br/>')
    stream=io.BytesIO();document=SimpleDocTemplate(stream,pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=16*mm,bottomMargin=16*mm,title=title,author='NABY',invariant=1)
    normal=ParagraphStyle('body',fontName=font,fontSize=9.3,leading=13.5,spaceAfter=5,wordWrap='CJK' if language=='zh' else None,splitLongWords=1)
    title_style=ParagraphStyle('title',parent=normal,fontSize=17,leading=22,spaceAfter=12)
    heading=ParagraphStyle('heading',parent=normal,fontSize=12,leading=17,spaceBefore=11,spaceAfter=7,keepWithNext=False)
    label=ParagraphStyle('label',parent=normal,fontSize=8.5,leading=12,textColor='#404040',spaceBefore=3,spaceAfter=1,keepWithNext=True)
    story=[Paragraph(safe(title),title_style)]
    for paragraph in intro(language,review_evidence):story.append(Paragraph(safe(paragraph),normal))
    for section in sections:
        story.append(CondPageBreak(60))
        story.append(Paragraph(safe(section['title']),heading))
        for paragraph in section.get('paragraphs',[]):story.append(Paragraph(safe(paragraph),normal))
        rows=section.get('rows',[])
        if rows:
            columns=section.get('columns')
            values=([columns]+rows) if columns else rows
            widths=([64*mm,110*mm] if len(values[0])==2 else [174*mm/len(values[0])]*len(values[0]))
            table=LongTable([[Paragraph(safe(value) or ' ',normal) for value in row] for row in values],colWidths=widths,hAlign='LEFT',splitByRow=1,splitInRow=1,repeatRows=1 if columns else 0)
            table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.3,'#D9D9D9'),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('ROWBACKGROUNDS',(0,0),(-1,-1),['#f2f5f7','#ffffff'])]))
            story.append(table)
        story.append(Spacer(1,3))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(font,8);canvas.drawRightString(A4[0]-18*mm,9*mm,UI[language]['page']+' '+str(doc.page));canvas.restoreState()
    document.build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()


def xlsx_bytes(title,sections,language,review_evidence):
    from openpyxl import Workbook
    from openpyxl.styles import Font,Alignment,PatternFill
    from openpyxl.utils import get_column_letter
    book=Workbook();book.remove(book.active)
    evidence_titles={UI[language]['evidence'],UI[language]['assumptions']}
    main=[s for s in sections if not s.get('columns') and s['title'] not in evidence_titles and not s.get('evidence_section')]
    proofs=[s for s in sections if s['title'] in evidence_titles or s.get('evidence_section')]
    groups=([(UI[language]['calculation'],main)] if main else [])+[(s['title'],[s]) for s in sections if s.get('columns') and s not in proofs]
    if proofs:groups.append((UI[language]['evidence'],proofs))
    for index,(group_title,group) in enumerate(groups):
        base=re.sub(r'[\\/*?:\[\]]',' ',group_title).strip() or UI[language]['calculation']
        sheet=book.create_sheet((str(index+1)+' '+base)[:31])
        rows=[[title]];header_rows=[];max_columns=2
        if index==0:
            rows.extend([[paragraph] for paragraph in intro(language,review_evidence)])
            rows.append([{'ru':'Книга содержит сохранённые результаты локального расчёта. После изменения исходных данных запустите инструмент NABY повторно; автоматического пересчёта формул в Excel здесь нет.','en':'This workbook stores local calculation results. After changing inputs, rerun the NABY tool; this file does not automatically recalculate Excel formulas.','zh':'本工作簿保存本地计算结果。输入改变后请重新运行NABY工具；此文件不自动重新计算Excel公式。'}[language]])
        for section in group:
            rows.append([section['title']]);rows.extend([[paragraph] for paragraph in section.get('paragraphs',[])])
            columns=section.get('columns',[UI[language]['field'],UI[language]['value']]);max_columns=max(max_columns,len(columns))
            if section.get('rows'):
                header_rows.append(len(rows)+1);rows.append(columns);rows.extend(section['rows'])
            rows.append([])
        # Split very long source text into continuation rows so Excel's maximum
        # row height cannot hide a quote. Concatenating chunks preserves text.
        import unicodedata
        def chunks(value,width):
            result=[];part='';used=0;limit=max(8,int(width)-3)*20
            for character in str(value):
                cost=int(width) if character=='\n' else 2 if unicodedata.east_asian_width(character) in ('W','F') else 1
                if part and used+cost>limit:result.append(part);part='';used=0
                part+=character;used+=cost
            return result+[part]
        expanded=[];expanded_headers=[]
        for number,row in enumerate(rows,1):
            if number in header_rows:expanded_headers.append(len(expanded)+1)
            widths=([134] if len(row)==1 else [52,82] if max_columns==2 else [24]*max_columns)
            groups=[chunks(value,widths[col]) for col,value in enumerate(row)]
            for i in range(max([len(group) for group in groups] or [1])):
                expanded.append([group[i] if i<len(group) else '' for group in groups])
        rows=expanded;header_rows=expanded_headers
        for row in rows:
            values=[display_text(value) if value is not None else UI[language]['missing'] for value in row]
            if any(len(value)>32767 for value in values):raise ValueError('xlsx_cell_text_limit')
            sheet.append(values)
            for cell in sheet[sheet.max_row]:
                cell.data_type='s';cell.alignment=Alignment(vertical='top',wrap_text=True);cell.font=Font(name='Arial',size=10)
        sheet['A1'].font=Font(name='Arial',size=15,bold=True)
        for header_row in header_rows:
            for cell in sheet[header_row]:cell.fill=PatternFill('solid',fgColor='E8EEF3');cell.font=Font(name='Arial',size=10,bold=True)
        for number in range(1,max_columns+1):sheet.column_dimensions[get_column_letter(number)].width=52 if max_columns==2 else 24
        if max_columns==2:sheet.column_dimensions['B'].width=82
        # Native Excel does not reliably auto-size wrapped rows on file open.
        # Merge prose rows across the page and persist a safe initial height.
        import math,unicodedata
        def visual_width(value):return sum(2 if unicodedata.east_asian_width(c) in ('W','F') else 1 for c in value)
        for number,row in enumerate(rows,1):
            nonempty=[value for value in row if value is not None and str(value)]
            if len(row)==1 and nonempty and max_columns>1:sheet.merge_cells(start_row=number,start_column=1,end_row=number,end_column=max_columns)
            lines=1
            for col,value in enumerate(row,1):
                width=sum(sheet.column_dimensions[get_column_letter(c)].width for c in range(1,max_columns+1)) if len(row)==1 else sheet.column_dimensions[get_column_letter(col)].width
                estimate=sum(max(1,math.ceil(visual_width(part)/max(8,width-3))) for part in str(value).split('\n'))
                lines=max(lines,estimate)
            sheet.row_dimensions[number].height=min(409,lines*15+6)
        sheet.row_dimensions[1].height=max(28,sheet.row_dimensions[1].height)
        sheet.freeze_panes='A'+str(header_rows[0]+1) if header_rows else 'A2'
        if header_rows and len(group)==1 and group[0].get('columns') and group[0].get('rows'):sheet.auto_filter.ref=f'A{header_rows[0]}:{get_column_letter(max_columns)}{sheet.max_row-1}'
        sheet.sheet_properties.pageSetUpPr.fitToPage=True
        sheet.page_setup.orientation='landscape';sheet.page_setup.paperSize=sheet.PAPERSIZE_A4;sheet.page_setup.fitToWidth=1;sheet.page_setup.fitToHeight=0
    stream=io.BytesIO();book.save(stream);return stream.getvalue()

