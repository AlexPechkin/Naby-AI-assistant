"""Фасад пакета: хост Наби (profession_packages.py) вызывает run(function, proposal_json, documents, language, review)."""
from .core import CORE
from .binding import verify
from .artifacts import render
import profbase


def run(function, proposal_json, documents, language='ru', review='preview'):
    return profbase.run(CORE, verify, render, function, proposal_json, documents, language, review)
