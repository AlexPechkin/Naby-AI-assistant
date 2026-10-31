"""Explicit calendar-date evidence matching without rewriting a source.

For root binding's opt-in date field only; never a generic literal/ID matcher.
Accepts ASCII YYYY-MM-DD and D.M.YYYY (one/two digit day and month).
No locale, words, two-digit years, slash order, timezone or calendar inference.
"""
from datetime import date
import re
import unicodedata

MAX_SOURCE_CHARACTERS=32_000_000
MAX_MATCHES=10_000
_EXPECTED=re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}\Z')
_TOKENS=re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4}')

def _word_continuation(character):
    return character.isalnum() or character=='_' or unicodedata.category(character) in ('Mn','Mc','Me','Cf')

def _boundary(source,start,end):
    """Whole standalone token, including non-ASCII word/number neighbours.

    A terminal sentence dot is punctuation; dot/colon followed immediately by
    another word/number is an extended token. Hyphen/slash/sign attachment is
    rejected rather than treating a field/identifier fragment as a date.
    """
    if start:
        previous=source[start-1]
        if (_word_continuation(previous) and not (start==1 and previous=='\ufeff')) or previous in './\\+-\u2212':return False
        if previous==':' and start>1 and source[start-2].isdigit():return False
    if end<len(source):
        following=source[end]
        if _word_continuation(following) or following in '/\\+-\u2212':return False
        if following in '.:' and end+1<len(source):
            after=source[end+1]
            if _word_continuation(after) or after in '/\\+-\u2212':return False
    return True

def calendar_date_records(source):
    """Parse each selected source surface once into bounded calendar records.

    Records: original_token, normalized_iso, format ('iso'|'dmy_dot'), start,
    end. Offsets are Python str character offsets; end is exclusive. Source is
    never stripped, decoded, normalized or returned as a fabricated document.
    Invalid dates within a source are ignored, not repaired. Invalid source
    type/resource bounds raise controlled ValueError. At most10,000 valid date
    records in total, no cache or side effects. A match is not row/field/source semantics
    or normative applicability/authenticity proof.
    """
    if type(source) is not str:raise ValueError('calendar_source_text_required')
    if len(source)>MAX_SOURCE_CHARACTERS:raise ValueError('calendar_source_size_limit')
    result=[]
    for match in _TOKENS.finditer(source):
        start,end=match.span()
        if not _boundary(source,start,end):continue
        token=match.group()
        if '-' in token:
            year,month,day=token.split('-');kind='iso'
        else:
            day,month,year=token.split('.');kind='dmy_dot'
        try:actual=date(int(year),int(month),int(day))
        except ValueError:continue
        if len(result)==MAX_MATCHES:raise ValueError('calendar_date_match_limit')
        result.append({'original_token':token,'normalized_iso':actual.isoformat(),
                       'format':kind,'start':start,'end':end})
    return result

def match_calendar_date(expectedISO,source):
    """Filter a source parse for one canonical ISO date; no match returns[].

    Host binding can call calendar_date_records once and index records by
    normalized_iso for many explicitly marked fields, using its per-call scope.
    This helper deliberately has no process-global cache.
    """
    if type(expectedISO) is not str or not _EXPECTED.fullmatch(expectedISO):
        raise ValueError('expected_calendar_ISO_required')
    try:date.fromisoformat(expectedISO)
    except ValueError:raise ValueError('expected_calendar_ISO_required') from None
    return [record for record in calendar_date_records(source)
            if record['normalized_iso']==expectedISO]
