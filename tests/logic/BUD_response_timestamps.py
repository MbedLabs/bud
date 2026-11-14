"""
* @file     ${tests/logic/BUD_response_timestamps.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Every timestamp an API response carries is marked as UTC.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module scans the response models of app.schemas and app.api.
"""

import datetime
import importlib
import inspect
import pkgutil
import typing

from pydantic import BaseModel

from tests.logic.response_timestamps import ResponseTimestampsBase


def is_datetime(annotation):
    """True when the annotation is a datetime or holds one."""
    if annotation is datetime.datetime:
        return True
    return any(is_datetime(argument) for argument in typing.get_args(annotation))


def response_models(packages, suffixes):
    """The pydantic models declared in the packages' modules whose names end in a suffix."""
    found = {}
    for package_name in packages:
        package = importlib.import_module(package_name)
        for module_info in pkgutil.iter_modules(package.__path__):
            module = importlib.import_module(f"{package_name}.{module_info.name}")
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(cls, BaseModel)
                    and cls.__module__ == module.__name__
                    and name.endswith(suffixes)
                ):
                    found[f"{cls.__module__}.{name}"] = cls
    return found


def unmarked_timestamps(models):
    """The datetime fields of the models that have no field serializer."""
    unmarked = []
    for qualified, cls in models.items():
        serialized = set()
        for decorator in cls.__pydantic_decorators__.field_serializers.values():
            serialized |= set(decorator.info.fields)
        for field, info in cls.model_fields.items():
            if is_datetime(info.annotation) and field not in serialized:
                unmarked.append(f"{qualified}.{field}")
    return unmarked


class ResponseTimestampsTest(ResponseTimestampsBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_models = response_models(
            self.parameters.RESPONSE_MODEL_PACKAGES, self.parameters.RESPONSE_MODEL_SUFFIXES
        )
        self.tc_unmarked = unmarked_timestamps(self.tc_models)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ResponseTimestampsTest().run()
