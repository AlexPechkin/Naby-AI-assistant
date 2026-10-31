"""Narrow engineering input guard, not a complete DLP or network policy engine."""
import re

_SECRET = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----|\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16})\b|(?:api[_-]?key|access[_-]?token|password|client[_-]?secret)[\"\x27]?\s*[=:]\s*[\"\x27][^\"\x27\r\n]{8,}[\"\x27]',re.I)
_SECRET_FIELDS=frozenset(('api_key','apikey','access_token','password','client_secret','private_key','secret_key'))

def reject_known_secret_material(value,depth=0):
    """Reject known markers/credential assignments without echo or redaction.

    This deliberately also rejects bare private-key PEM markers. Raw JSON callers
    should check the parsed object too, so escaped credential keys are covered.
    No source is edited, and no signing, key validation or external call occurs.
    """
    if depth>32:raise ValueError('engineering_privacy_nesting_limit')
    if type(value) is str:
        if _SECRET.search(value):raise ValueError('secret_material_not_accepted')
    elif type(value) is dict:
        for key,item in value.items():
            if type(key) is not str:raise ValueError('engineering_string_keys_required')
            if key.lower().replace('-','_') in _SECRET_FIELDS and item not in (None,''):
                raise ValueError('secret_material_not_accepted')
            reject_known_secret_material(item,depth+1)
    elif type(value) is list:
        for item in value:reject_known_secret_material(item,depth+1)
