"""Диспетчер функций профессии — только список функций и флаги; всё остальное в profbase.Core."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / '_shared')) if str(Path(__file__).resolve().parent.parent / '_shared') not in sys.path else None
import profbase

FUNCTIONS = ('example_calc', 'example_report')          # <- функции профессии
CALCULATIONS = frozenset(('example_calc',))             # считаются в calculations.py, остальные — scenarios.py
RESERVED_EXTRA = ()                                     # <- поля-полномочия, которые модель не вправе предлагать (сверх общих)
RESULT_FLAGS = {}                                       # <- доп. флаги результата, например {'submission_performed': False}

CORE = profbase.Core(__package__, FUNCTIONS, CALCULATIONS, RESERVED_EXTRA, RESULT_FLAGS, error='unknown_example_function')
execute, input_units, selected_texts = CORE.execute, CORE.input_units, CORE.selected_texts
reject_proposed_authority = lambda value: profbase.reject_proposed_authority(value, CORE.RESERVED)
strict_snapshot = profbase.strict_snapshot
