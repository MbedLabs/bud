"""Every timestamp an API response carries is marked as UTC."""

import datetime
import importlib
import inspect
import pkgutil
import typing

from pydantic import BaseModel

import app.schemas

SUFFIXES = ("Response", "Summary", "Item", "Entry")


def _is_datetime(annotation) -> bool:
    if annotation is datetime.datetime:
        return True
    return any(_is_datetime(arg) for arg in typing.get_args(annotation))


def _response_models():
    seen = {}
    for module_info in pkgutil.iter_modules(app.schemas.__path__):
        module = importlib.import_module(f"app.schemas.{module_info.name}")
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, BaseModel) and name.endswith(SUFFIXES):
                seen[f"{cls.__module__}.{name}"] = cls
    return seen


def test_the_scan_finds_the_response_models():
    assert len(_response_models()) > 20


def test_every_response_timestamp_has_the_utc_serializer():
    unmarked = []
    for qualified, cls in _response_models().items():
        serialized = set()
        for decorator in cls.__pydantic_decorators__.field_serializers.values():
            serialized |= set(decorator.info.fields)
        for field, info in cls.model_fields.items():
            if _is_datetime(info.annotation) and field not in serialized:
                unmarked.append(f"{qualified}.{field}")
    assert unmarked == []
