"""Bounded local embedded-document writers; never opens source paths or URLs."""
from decimal import Decimal
from pathlib import Path
import io,json,html,re,hashlib
from .artifact_labels import UI,field_label,token

FONT_SHA256='fdd4cac2c56b9f69396ceb51021d373f484108566fc6fae254edc9cbc1e890f1'


def snapshot(value):
    raw=json.dumps(value,ensure_ascii=False,allow_nan=False,default=lambda x:str(x) if isinstance(x,Decimal) else (_ for _ in ()).throw(ValueError('non_json_artifact_input')))
    if len(raw.encode('utf-8'))>8_000_000:raise ValueError('artifact_input_limit')
    parsed=json.loads(raw)
    def visit(x,depth=0):
        if depth>24:raise ValueError('artifact_nesting_limit')
        if isinstance(x,str):
            if len(x)>600000:raise ValueError('artifact_text_invalid')
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


LITERAL_FIELDS={'id','name','source_reference','source_references','reference','fact_id','source_id','source_sha256','segment_id','pointer','quote','excerpt','text','citation','url','edition','document_identity','clause','unit','value','description','rationale','title','purpose','action','responsibility','procedure','publication_date','effective_from','effective_to','observed_date','as_of','version','label','priority_label','likelihood_id','impact_id','owner','run_date','selection_date','date','path','path_label','configuration_sha256','data_sha256','input_sha256','logical_utf8_sha256','provided_utf8_content_sha256','original_bytes_sha256','image_sha256','sha256','content','query_json','response_json','record_json','compiler','tool','tool_version','toolchain','toolchain_version','firmware_version','software_version','board_revision','build_id','case_id','test_id','test_revision','case_revision','commit','branch','tag','hex','payload','payload_hex','computed_crc_hex','register_value','raw_status','raw_suite_status','run_id','dut','clock_id','expected_behavior','symptoms','connection','explanation','expected_observation','preconditions','inputs','steps','expected','analysis','proposal','notes','note','abstract','right_holder','authors','license_expression','ecosystem','purl'}


def flat(value,language,prefix='',literal=False):
    """Neutral recursive display; domain None states are resolved by artifacts."""
    u=UI[language];out=[]
    if isinstance(value,dict):
        if not value:return [[prefix or u['details'],u['missing']]]
        for key,item in value.items():
            label=field_label(key,language)
            child_literal=literal or key in LITERAL_FIELDS or key.endswith(('_unit','_units','_version','_reference','_id','_ids'))
            out.extend(flat(item,language,(prefix+' / ' if prefix else '')+label,child_literal))
    elif isinstance(value,list):
        if not value:return [[prefix or u['items'],u['none']]]
        for index,item in enumerate(value,1):out.extend(flat(item,language,(prefix+' / ' if prefix else '')+str(index),literal))
    else:out.append([prefix or u['value'],display_text(value) if literal and isinstance(value,str) else scalar(value,language)])
    if len(out)>15000:raise ValueError('artifact_rows_limit')
    return out


def extra_sections(review_evidence,language):
    u=UI[language];review=review_evidence or {};out=[]
    assumptions=review.get('assumptions',[])
    if assumptions:
        rows=[[str(a.get('pointer','')),str(a.get('value',''))+' '+str(a.get('unit','')),str(a.get('rationale',''))] for a in assumptions]
        out.append({'title':u['assumptions'],'paragraphs':[u['assumption_banner']],'columns':[field_label('pointer',language),u['value'],field_label('rationale',language)],'rows':rows,'evidence_section':True})
    bindings=review.get('bindings',[]);text_bindings=review.get('text_bindings',[])
    if bindings or text_bindings:
        sources={}
        for binding in bindings:
            digest=str(binding.get('source_sha256',''))
            if digest not in sources:sources[digest]=len(sources)+1
        for binding in text_bindings:
            for digest in binding.get('source_sha256',[]):
                if digest not in sources:sources[digest]=len(sources)+1
        index_rows=[[str(index),digest] for digest,index in sources.items()]
        out.append({'title':u['evidence'],'paragraphs':[u['unverified']],'columns':[field_label('reference',language),field_label('source_sha256',language)],'rows':index_rows,'evidence_section':True})
        rows=[]
        for binding in bindings:
            identity=str(binding.get('fact_id',''))+'\n'+str(binding.get('pointer',''))+'\n'+str(binding.get('unit',''))
            source=str(sources[str(binding.get('source_sha256',''))])+' / '+str(binding.get('segment_id',''))
            rows.append([identity,source,str(binding.get('quote',''))])
        if rows:out.append({'title':field_label('quote',language),'paragraphs':[],'columns':[field_label('fact_id',language),field_label('reference',language),field_label('quote',language)],'rows':rows,'evidence_section':True})
        if text_bindings:
            rows=[]
            for binding in text_bindings:
                refs='\n'.join(str(sources[digest])for digest in binding.get('source_sha256',[]))
                state=UI[language]['empty_source_binding'] if binding.get('empty_selected_file') else UI[language]['blank_source_binding'] if binding.get('blank_selected_file') else UI[language]['literal_source_binding'] if binding.get('text_occurrence_verified')is True else UI[language]['literal_binding_not_established']
                rows.append([str(binding.get('pointer','')),refs+'\n'+'\n'.join(binding.get('references',[])),state])
            out.append({'title':UI[language]['source_text_bindings'],'paragraphs':[UI[language]['unverified']],'columns':[field_label('pointer',language),field_label('reference',language),field_label('review_status',language)],'rows':rows,'evidence_section':True})
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
    paragraphs.append(u['precision_note'])
    if review.get('synthetic_format_example'):paragraphs.insert(0,u['synthetic_banner'])
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
    normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(11);normal.font.color.rgb=RGBColor(0,0,0)
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
        for block in content.get('code_blocks',[]):
            doc.add_paragraph(display_text(block['label']))
            p=doc.add_paragraph();p.paragraph_format.space_after=Pt(8)
            run=p.add_run(display_text(block['text']));run.font.name='Courier New';run.font.size=Pt(9);run.font.color.rgb=RGBColor(0,0,0)
        if content.get('rows'):
            columns=content.get('columns',[UI[language]['field'],UI[language]['value']])
            table=doc.add_table(rows=0,cols=len(columns));table.style='Table Grid';table.autofit=False
            widths=content.get('widths',[2.3,4.8] if len(columns)==2 else [7.1/len(columns)]*len(columns))
            for column,width in zip(table.columns,widths):column.width=Inches(width)
            header=table.add_row().cells
            for cell,label in zip(header,columns):
                cell.text=display_text(label)
                shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E8E8E8');cell._tc.get_or_add_tcPr().append(shade)
                for run in cell.paragraphs[0].runs:run.bold=True;run.font.color.rgb=RGBColor(0,0,0)
            repeat=OxmlElement('w:tblHeader');table.rows[0]._tr.get_or_add_trPr().append(repeat)
            for row in content['rows']:
                cells=table.add_row().cells
                for cell,value in zip(cells,row):cell.text=display_text(value)
            import math,unicodedata
            for row in table.rows:
                # Keep ordinary records whole, but permit a quote taller than
                # one printable page to continue instead of clipping in Word.
                lines=1
                for cell,width in zip(row.cells,widths):
                    capacity=max(8,(width*72-14)/4.5)
                    count=sum(max(1,math.ceil(sum(2 if unicodedata.east_asian_width(ch)in('W','F')else 4 if ch=='\t'else 1 for ch in line)/capacity))for line in cell.text.split('\n'))
                    lines=max(lines,count)
                if lines*12+16<600:
                    no_split=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(no_split)
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
                        for run in paragraph.runs:run.font.size=Pt(9);run.font.color.rgb=RGBColor(0,0,0)
            doc.add_paragraph('')
    stream=io.BytesIO();doc.save(stream);return stream.getvalue()


def _font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    name='NabyPhysicsDocumentSans'
    path=Path(__file__).resolve().parent/'fonts'/'NabyPhysicsDocumentSans.ttf'
    if not path.exists():path=Path(__file__).resolve().parent.parent/'_shared'/'fonts'/'NabyPhysicsDocumentSans.ttf'  # NABY build 39: one shared copy
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=FONT_SHA256:raise ValueError('document_font_hash_mismatch')
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name,io.BytesIO(raw)))
    return name


def pdf_bytes(title,sections,language,review_evidence):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph,SimpleDocTemplate,Spacer,LongTable,TableStyle,CondPageBreak
    from reportlab.pdfbase import pdfmetrics
    font=_font();face=pdfmetrics.getFont(font).face
    def safe(value):
        value=display_text(value)
        if any(ord(c)>32 and ord(c) not in face.charToGlyph for c in value):raise ValueError('document_font_missing_glyph')
        return html.escape(value,quote=False).replace('\n','<br/>')
    stream=io.BytesIO();document=SimpleDocTemplate(stream,pagesize=letter,leftMargin=18*mm,rightMargin=18*mm,topMargin=16*mm,bottomMargin=16*mm,title=title,author='NABY',invariant=1)
    class ReadableLongTable(LongTable):
        """Keep an ordinary record together; allow oversized source cells to flow."""
        def __init__(self,*args,**kwargs):
            kwargs['splitInRow']=0
            super().__init__(*args,**kwargs)
        def split(self,availWidth,availHeight):
            pieces=super().split(availWidth,availHeight)
            if pieces:return pieces
            repeat=self.repeatRows if type(self.repeatRows) is int else max(self.repeatRows,default=-1)+1
            index=repeat if len(self._rowHeights)>repeat else 0
            height=self._rowHeights[index]
            header=sum(h or 0 for h in self._rowHeights[:repeat])
            if height is not None and height>document.height-16-header:
                self.splitInRow=1
                try:return super().split(availWidth,availHeight)
                finally:self.splitInRow=0
            return []
    normal=ParagraphStyle('body',fontName=font,fontSize=9.3,leading=13.5,spaceAfter=5,wordWrap='CJK' if language=='zh' else None,splitLongWords=1)
    title_style=ParagraphStyle('title',parent=normal,fontSize=17,leading=22,spaceAfter=12)
    heading=ParagraphStyle('heading',parent=normal,fontSize=12,leading=17,spaceBefore=11,spaceAfter=7,keepWithNext=False)
    label=ParagraphStyle('label',parent=normal,fontSize=8.5,leading=12,textColor='#404040',spaceBefore=3,spaceAfter=1,keepWithNext=True)
    code_style=ParagraphStyle('code',parent=normal,fontSize=8.5,leading=11.5,wordWrap='CJK',spaceAfter=6)
    story=[Paragraph(safe(title),title_style)]
    for paragraph in intro(language,review_evidence):story.append(Paragraph(safe(paragraph),normal))
    for section in sections:
        story.append(CondPageBreak(60))
        story.append(Paragraph(safe(section['title']),heading))
        for paragraph in section.get('paragraphs',[]):story.append(Paragraph(safe(paragraph),normal))
        for block in section.get('code_blocks',[]):
            story.append(Paragraph(safe(block['label']),label))
            # Source line endings remain exact in JSON/TXT. Display wraps only;
            # visible BOM/tab escapes are explicitly described by the caller.
            for line in block['text'].replace('\r\n','\n').replace('\r','\n').split('\n'):
                escaped=safe(line).replace(' ','&#160;').replace('\t','&#160;'*4)
                story.append(Paragraph(escaped or '&#160;',code_style))
        rows=section.get('rows',[])
        if rows:
            columns=section.get('columns',[UI[language]['field'],UI[language]['value']])
            values=([columns]+rows) if columns else rows
            widths=([64*mm,110*mm] if len(values[0])==2 else [174*mm/len(values[0])]*len(values[0]))
            table=ReadableLongTable([[Paragraph(safe(value) or ' ',normal) for value in row] for row in values],colWidths=widths,hAlign='LEFT',splitByRow=1,repeatRows=1 if columns else 0)
            table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.3,'#D9D9D9'),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('ROWBACKGROUNDS',(0,0),(-1,-1),['#f2f2f2','#ffffff'])]))
            if columns:table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),'#E8E8E8'),('TEXTCOLOR',(0,0),(-1,0),'#000000')]))
            story.append(table)
        story.append(Spacer(1,3))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(font,8);canvas.drawRightString(letter[0]-18*mm,9*mm,UI[language]['page']+' '+str(doc.page));canvas.restoreState()
    document.build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()


