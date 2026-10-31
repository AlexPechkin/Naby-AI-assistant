# -*- coding: utf-8 -*-
"""Формат профессии Наби «naby-profession/1» и его проверка (сборка 50). Один и тот же модуль проверяет:
  • профессии, которые человек ставит сам по ссылке GitHub (profession_import.py);
  • присланные на сайт профессии — перед тем как автор возьмёт их в релиз (profession_review.py);
  • изменения в публичном репозитории Наби (GitHub Actions запускает этот же файл как tools/validate.py).
Зависит только от стандартной библиотеки — копируется в репозиторий без правок.

Папка профессии:
    <id>/
      profession.json   — описание и профиль (обязательно)
      README.md         — что умеет, для кого, автор (желательно)
      package/          — необязательный пакет-код на шаблоне profbase (только для проверенных автором; см. docs)
      examples/         — необязательные примеры задач и ожидаемых результатов
"""
import json
import os
import re
import sys

SCHEMA = 'naby-profession/1'
LANGS = ('ru', 'en', 'zh')
ID_RE = re.compile(r'^[a-z0-9][a-z0-9_]{2,47}$')
MAX_JSON = 600_000
MAX_TEXT = 6000
STATUSES = ('verified', 'in-progress', 'community')
PROFILE_KEYS = {
    'system': str, 'kinds': dict, 'default_kind': str, 'kinds_ru': dict, 'routing': dict, 'local': dict,
    'playbooks': list, 'quick_starts': list, 'safety': list, 'sources': list, 'focus': list, 'varieties': list,
    'laws': dict, 'programs': dict, 'group': str, 'icon': str, 'tagline': str, 'name': str, 'version': str,
    'private': (dict, list), 'local_kinds': list, 'passport': dict, 'new_tools': (list, dict), 'nonllm_models': (list, dict),
    'directions': (list, dict), 'direction_info': dict, 'patient_mode': (bool, dict, str),
}
REQUIRED_PROFILE = ('system', 'kinds', 'default_kind', 'kinds_ru')
FORBIDDEN_FILES = re.compile(r'\.(exe|dll|so|dylib|bat|cmd|ps1|vbs|scr|msi|jar|com|sh|command|app|pyc)$', re.I)
DANGER = [(re.compile(p, re.I), why) for p, why in [
    (r'\b(ignore|disregard|forget)\b.{0,40}\b(previous|all|above|prior)\b.{0,20}\b(instructions|rules)', 'попытка отменить правила'),
    (r'(забудь|игнорируй|отмени).{0,30}(правила|инструкции|законы)', 'попытка отменить правила'),
    (r'(api[_ -]?key|token|парол|password|seed|сид-фраз).{0,60}(отправ|send|post|upload|curl|http)', 'вынос секретов'),
    (r'\b(curl|wget|Invoke-WebRequest|iwr)\b[^\n]{0,80}\|\s*(sh|bash|iex|powershell)', 'скачай и выполни'),
    (r'\b(rm\s+-rf|format\s+c:|del\s+/s|Remove-Item\s+-Recurse)\b', 'удаление файлов'),
    (r'(always|всегда)\s.{0,30}(allow|разреш|без (вопроса|подтверждения))', 'обход подтверждений'),
]]


def _i18n(v, field, errors, required=True):
    if isinstance(v, str):
        if required: errors.append(f'{field}: нужен объект {{"ru": …, "en": …, "zh": …}} — сайт и Наби на трёх языках')
        return
    if not isinstance(v, dict):
        errors.append(f'{field}: нужен объект с ключами ru, en, zh'); return
    miss = [l for l in LANGS if not str(v.get(l) or '').strip()]
    if miss and required: errors.append(f'{field}: нет перевода — {", ".join(miss)}')


def _strings(obj, path=''):
    if isinstance(obj, str): yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items(): yield from _strings(v, f'{path}.{k}' if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj): yield from _strings(v, f'{path}[{i}]')


def scan_text(manifest):
    """Подброшенные указания в текстах профессии. -> [(где, что)]."""
    out = []
    for where, s in _strings(manifest):
        for rx, why in DANGER:
            if why == 'удаление файлов' and where.startswith('profile.safety'): continue   # «никогда не делай rm -rf» — это правило
            if rx.search(s): out.append((where, why)); break
        if re.search('[\u200b\u200e\u200f\u202a-\u202e\u2060-\u2064\U000e0000-\U000e007f]', s):   # ZWJ/ZWNJ — части эмодзи
            out.append((where, 'невидимые символы'))
    return out


def validate(m, folder_name=None):
    """-> (ошибки, предупреждения). Пустые ошибки — профессию можно ставить."""
    errors, warns = [], []
    if not isinstance(m, dict): return ['profession.json: нужен объект'], []
    if m.get('schema') != SCHEMA: errors.append(f'schema: должно быть "{SCHEMA}"')
    pid = str(m.get('id') or '')
    if not ID_RE.match(pid): errors.append('id: латиница в нижнем регистре, цифры и _, от 3 до 48 знаков')
    if folder_name and pid and folder_name != pid: errors.append(f'id «{pid}» не совпадает с именем папки «{folder_name}»')
    if not re.match(r'^\d+\.\d+(\.\d+)?$', str(m.get('version') or '')): errors.append('version: например "1.0" или "1.2.3"')
    _i18n(m.get('name'), 'name', errors)
    _i18n(m.get('tagline'), 'tagline', warns)
    if not isinstance(m.get('authors'), list) or not m['authors']: errors.append('authors: список авторов (имя и, по желанию, GitHub)')
    if m.get('license') not in ('Naby Professions License 1.0', 'NPL-1.0'):
        errors.append('license: "Naby Professions License 1.0" — профессии Наби распространяются по ней')
    if m.get('status', 'community') not in STATUSES: errors.append(f'status: одно из {", ".join(STATUSES)}')
    p = m.get('profile')
    if not isinstance(p, dict):
        errors.append('profile: нужен объект с описанием профессии (system, kinds, …)')
    else:
        for k in REQUIRED_PROFILE:
            if k not in p: errors.append(f'profile.{k}: обязательно')
        for k, v in p.items():
            t = PROFILE_KEYS.get(k)
            if t is None: warns.append(f'profile.{k}: неизвестное поле — Наби его не использует')
            elif not isinstance(v, t): errors.append(f'profile.{k}: должно быть ' + ' или '.join(x.__name__ for x in (t if isinstance(t, tuple) else (t,))))
        for kind, rx in (p.get('kinds') or {}).items() if isinstance(p.get('kinds'), dict) else []:
            try: re.compile(str(rx))
            except re.error as e: errors.append(f'profile.kinds.{kind}: неверное регулярное выражение ({e})')
            if len(str(rx)) > 600: errors.append(f'profile.kinds.{kind}: слишком длинное выражение (до 600 знаков)')
        if isinstance(p.get('kinds'), dict) and p.get('default_kind') not in p['kinds'] and p.get('default_kind') not in ('agent', 'general'):
            warns.append('profile.default_kind: обычно один из kinds, "general" или "agent"')
        if isinstance(p.get('system'), str) and len(p['system']) > MAX_TEXT: errors.append(f'profile.system: не длиннее {MAX_TEXT} знаков')
        if isinstance(p.get('routing'), dict):
            for kind, rows in p['routing'].items():
                if not isinstance(rows, list) or not all(isinstance(r, dict) and r.get('match') for r in rows):
                    errors.append(f'profile.routing.{kind}: список [{{"match": "часть имени модели", "label": "…"}}]')
    for where, why in scan_text(m):
        errors.append(f'{where}: {why} — такие тексты в профессию не принимаются')
    return errors, warns


def check_folder(path):
    """Проверить папку профессии. -> {'id', 'ok', 'errors', 'warnings', 'manifest', 'has_package'}."""
    errors, warns, m = [], [], None
    mp = os.path.join(path, 'profession.json')
    if not os.path.isfile(mp):
        return {'id': None, 'ok': False, 'errors': ['нет profession.json'], 'warnings': [], 'manifest': None, 'has_package': False}
    if os.path.getsize(mp) > MAX_JSON: errors.append('profession.json больше 600 КБ')
    else:
        try:
            with open(mp, encoding='utf-8') as f: m = json.load(f)
        except ValueError as e:
            errors.append(f'profession.json: не JSON ({e})')
    if m is not None:
        e2, w2 = validate(m, os.path.basename(os.path.normpath(path)))
        errors += e2; warns += w2
    for dp, _dirs, fs in os.walk(path):
        for fn in fs:
            rel = os.path.relpath(os.path.join(dp, fn), path)
            if FORBIDDEN_FILES.search(fn): errors.append(f'{rel}: исполняемые файлы в профессии запрещены')
            if os.path.islink(os.path.join(dp, fn)): errors.append(f'{rel}: ссылки на файлы запрещены')
    if not os.path.isfile(os.path.join(path, 'README.md')): warns.append('README.md: опишите, что умеет профессия и для кого')
    has_pkg = os.path.isdir(os.path.join(path, 'package'))
    if has_pkg and not os.path.isfile(os.path.join(path, 'package', 'NABY_PACKAGE.json')):
        errors.append('package/: нужен NABY_PACKAGE.json (см. шаблон в docs/profession-package)')
    return {'id': (m or {}).get('id'), 'ok': not errors, 'errors': errors, 'warnings': warns, 'manifest': m, 'has_package': has_pkg}


def to_runtime(m):
    """Профиль для Наби (тот же вид, что у встроенных 140 профессий) из profession.json."""
    p = dict(m.get('profile') or {})
    name = m.get('name') or {}
    p.setdefault('name', name.get('ru') or name.get('en') or m.get('id'))
    tag = m.get('tagline') or {}
    p.setdefault('tagline', tag.get('ru') or tag.get('en') or '')
    p.setdefault('icon', m.get('icon') or '🧩')
    p.setdefault('version', str(m.get('version')))
    p['source'] = m.get('_source') or 'community'
    p['authors'] = m.get('authors') or []
    return p


def main(argv):
    """python validate.py <папка-профессии | папка со многими профессиями> …  — для GitHub Actions и авторов."""
    paths = argv[1:] or ['professions']
    bad = 0; seen = 0
    for root in paths:
        cands = [root] if os.path.isfile(os.path.join(root, 'profession.json')) else \
            [os.path.join(dp, d) for dp, ds, _f in os.walk(root) for d in ds if os.path.isfile(os.path.join(dp, d, 'profession.json'))]
        for c in sorted(cands):
            seen += 1
            r = check_folder(c)
            mark = 'OK ' if r['ok'] else 'ERR'
            print(f'{mark} {c}')
            for e in r['errors']: print(f'   ✗ {e}')
            for w in r['warnings']: print(f'   ! {w}')
            bad += 0 if r['ok'] else 1
    print(f'\nПроверено профессий: {seen}, с ошибками: {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
