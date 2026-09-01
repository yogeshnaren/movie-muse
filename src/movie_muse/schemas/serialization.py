"""Generic dataclass <-> JSON-compatible dict conversion helpers.

Every domain type in this package is a frozen dataclass. These helpers keep
``to_dict``/``from_dict`` implementations short and consistent instead of
hand-rolling ad-hoc JSON mapping for each of the sixteen-plus domain schemas.
"""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, TypeVar

T = TypeVar("T")


def freeze_instance_fields(obj: Any) -> None:
    """Freeze JSON-like field values on a frozen dataclass instance."""

    for field in dataclasses.fields(obj):
        value = getattr(obj, field.name)
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            continue
        if isinstance(value, tuple):
            frozen_items = tuple(
                item
                if dataclasses.is_dataclass(item) and not isinstance(item, type)
                else freeze_json(item)
                for item in value
            )
            object.__setattr__(obj, field.name, frozen_items)
            continue
        frozen = freeze_json(value)
        if frozen is not value:
            object.__setattr__(obj, field.name, frozen)


def sealed(cls: type[T]) -> type[T]:
    """Wrap a frozen dataclass so nested mappings/lists cannot mutate after construction.

    ``@dataclass`` only emits a ``__post_init__`` call when the class already
    defined one. Wrapping ``__init__`` instead keeps freeze-on-construct
    behavior for every sealed type, including those with no ``__post_init__``.
    """

    existing_init = cls.__init__

    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        existing_init(self, *args, **kwargs)
        freeze_instance_fields(self)

    cls.__init__ = __init__  # type: ignore[method-assign]
    return cls


def freeze_json(value: Any) -> Any:
    """Recursively freeze JSON-like mappings and lists so nested payloads cannot mutate."""

    if isinstance(value, MappingProxyType):
        return MappingProxyType({str(key): freeze_json(item) for key, item in value.items()})
    if isinstance(value, dict):
        return MappingProxyType({str(key): freeze_json(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(freeze_json(item) for item in value)
    return value


def to_json_dict(value: Any) -> Any:
    """Recursively convert dataclasses/enums/tuples into plain JSON values."""

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_json_dict(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, list | tuple):
        return [to_json_dict(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): to_json_dict(item) for key, item in value.items()}
    return value


def dataclass_to_dict(value: Any) -> dict[str, Any]:
    """Type-narrowing wrapper for ``to_json_dict`` when ``value`` is a dataclass instance."""

    result = to_json_dict(value)
    if not isinstance(result, dict):
        raise TypeError(f"expected a dataclass instance, got {type(value).__name__}")
    return result


def dataclass_from_dict(
    cls: type[T],
    data: Mapping[str, Any],
    *,
    converters: Mapping[str, Callable[[Any], Any]] | None = None,
) -> T:
    """Build ``cls`` from ``data``, applying ``converters`` per field name.

    Fields absent from ``data`` are omitted so dataclass defaults apply.
    """

    converters = converters or {}
    field_names = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
    kwargs: dict[str, Any] = {}
    for name, value in data.items():
        if name not in field_names:
            continue
        converter = converters.get(name)
        kwargs[name] = converter(value) if converter is not None else value
    return cls(**kwargs)


def tuple_of(converter: Callable[[Any], Any]) -> Callable[[Any], tuple[Any, ...]]:
    """Return a converter that maps ``converter`` over an iterable into a tuple."""

    def _convert(values: Any) -> tuple[Any, ...]:
        return tuple(converter(item) for item in (values or ()))

    return _convert
