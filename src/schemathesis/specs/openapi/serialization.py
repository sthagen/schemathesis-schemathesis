from __future__ import annotations

import json
from typing import Any, Callable, Dict, Generator, List

from schemathesis.schemas import APIOperation
from schemathesis.specs.openapi.constants import LOCATION_TO_CONTAINER

Generated = Dict[str, Any]
Definition = Dict[str, Any]
DefinitionList = List[Definition]
MapFunction = Callable[[Generated], Generated]


def get_serializers_for_operation(operation: APIOperation) -> dict[str, Callable]:
    serializers = {}
    for location, container in LOCATION_TO_CONTAINER.items():
        serializer = operation.get_parameter_serializer(location)
        if serializer is not None:
            serializers[container] = serializer
    return serializers


def make_serializer(
    func: Callable[[DefinitionList], Generator[Callable | None, None, None]],
) -> Callable[[DefinitionList], Callable | None]:
    """A maker function to avoid code duplication."""

    def _wrapper(definitions: DefinitionList) -> Callable | None:
        functions = list(func(definitions))
        if not functions:
            return None

        def composed(x: Any) -> Any:
            result = x
            for func in reversed(functions):
                if func is not None:
                    result = func(result)
            return result

        return composed

    return _wrapper


def _serialize_openapi3(definitions: DefinitionList) -> Generator[Callable | None, None, None]:
    """Different collection styles for Open API 3.0."""
    for definition in definitions:
        name = definition["name"]
        if "content" in definition:
            # https://swagger.io/docs/specification/describing-parameters/#schema-vs-content
            options = iter(definition["content"].keys())
            media_type = next(options, None)
            if media_type == "application/json":
                yield to_json(name)
        else:
            # Simple serialization
            style = definition.get("style")
            explode = definition.get("explode")
            type_ = definition.get("schema", {}).get("type")
            if definition["in"] == "path":
                yield from _serialize_path_openapi3(name, type_, style, explode)
            elif definition["in"] == "query":
                yield from _serialize_query_openapi3(name, type_, style, explode)
            elif definition["in"] == "header":
                yield from _serialize_header_openapi3(name, type_, explode)
            elif definition["in"] == "cookie":
                yield from _serialize_cookie_openapi3(name, type_, explode)


def _serialize_path_openapi3(
    name: str, type_: str, style: str | None, explode: bool | None
) -> Generator[Callable | None, None, None]:
    if style == "simple":
        if type_ == "object":
            if explode is False:
                yield comma_delimited_object(name)
            if explode is True:
                yield delimited_object(name)
        if type_ == "array":
            yield delimited(name, delimiter=",")
    if style == "label":
        if type_ == "object":
            yield label_object(name, explode=explode)
        elif type_ == "array":
            yield label_array(name, explode=explode)
        else:
            yield label_primitive(name)
    if style == "matrix":
        if type_ == "object":
            yield matrix_object(name, explode=explode)
        elif type_ == "array":
            yield matrix_array(name, explode=explode)
        else:
            yield matrix_primitive(name)


def _serialize_query_openapi3(
    name: str, type_: str, style: str | None, explode: bool | None
) -> Generator[Callable | None, None, None]:
    if type_ == "object":
        if style == "deepObject":
            yield deep_object(name)
        if style is None or style == "form":
            if explode is False:
                yield comma_delimited_object(name)
            if explode is True:
                yield extracted_object(name)
    elif type_ == "array" and explode is False:
        if style == "pipeDelimited":
            yield delimited(name, delimiter="|")
        if style == "spaceDelimited":
            yield delimited(name, delimiter=" ")
        if style is None or style == "form":  # "form" is the default style
            yield delimited(name, delimiter=",")


def _serialize_header_openapi3(name: str, type_: str, explode: bool | None) -> Generator[Callable | None, None, None]:
    # Headers should be coerced to a string so we can check it for validity later
    yield to_string(name)
    # Header parameters always use the "simple" style, that is, comma-separated values
    if type_ == "array":
        yield delimited(name, delimiter=",")
    if type_ == "object":
        if explode is False:
            yield comma_delimited_object(name)
        if explode is True:
            yield delimited_object(name)


def _serialize_cookie_openapi3(name: str, type_: str, explode: bool | None) -> Generator[Callable | None, None, None]:
    # Cookies should be coerced to a string so we can check it for validity later
    yield to_string(name)
    # Cookie parameters always use the "form" style
    if explode and type_ in ("array", "object"):
        # `explode=true` doesn't make sense
        # I.e. we can't create multiple values for the same cookie
        # We use the same behavior as in the examples - https://swagger.io/docs/specification/serialization/
        # The item is removed
        yield nothing(name)
    if explode is False:
        if type_ == "array":
            yield delimited(name, delimiter=",")
        if type_ == "object":
            yield comma_delimited_object(name)


def _serialize_swagger2(definitions: DefinitionList) -> Generator[Callable | None, None, None]:
    """Different collection formats for Open API 2.0."""
    for definition in definitions:
        name = definition["name"]
        collection_format = definition.get("collectionFormat", "csv")
        type_ = definition.get("type")
        if definition["in"] == "header":
            # Headers should be coerced to a string so we can check it for validity later
            yield to_string(name)
        if type_ in ("array", "object"):
            if collection_format == "csv":
                yield delimited(name, delimiter=",")
            if collection_format == "ssv":
                yield delimited(name, delimiter=" ")
            if collection_format == "tsv":
                yield delimited(name, delimiter="\t")
            if collection_format == "pipes":
                yield delimited(name, delimiter="|")


serialize_openapi3_parameters = make_serializer(_serialize_openapi3)
serialize_swagger2_parameters = make_serializer(_serialize_swagger2)


def conversion(func: Callable[..., None]) -> Callable:
    def _wrapper(name: str, **kwargs: Any) -> MapFunction:
        def _map(item: Generated) -> Generated:
            if name in (item or {}):
                func(item, name, **kwargs)
            return item

        return _map

    return _wrapper


def make_delimited(data: dict[str, Any] | None, delimiter: str = ",") -> str:
    return delimiter.join(f"{key}={value}" for key, value in force_dict(data or {}).items())


def force_iterable(value: Any) -> list | tuple:
    """Converts the value to a list or a tuple.

    Only relevant for negative test scenarios where the original types might be changed.
    """
    if isinstance(value, (tuple, list)):
        return value
    return [value]


def force_dict(value: Any) -> dict:
    """Converts the value to a dictionary.

    Only relevant for negative test scenarios where the original types might be changed.
    """
    if isinstance(value, dict):
        return value
    return {"": value}


@conversion
def to_json(item: Generated, name: str) -> None:
    """Serialize an item to JSON."""
    item[name] = json.dumps(item[name])


@conversion
def delimited(item: Generated, name: str, delimiter: str) -> None:
    item[name] = delimiter.join(map(str, force_iterable(item[name] or ())))


@conversion
def deep_object(item: Generated, name: str) -> None:
    """Serialize an object with `deepObject` style.

    id={"role": "admin", "firstName": "Alex"} => id[role]=admin&id[firstName]=Alex
    """
    generated = item.pop(name)
    if generated:
        item.update({f"{name}[{key}]": value for key, value in force_dict(generated).items()})
    else:
        item[name] = ""


@conversion
def comma_delimited_object(item: Generated, name: str) -> None:
    item[name] = ",".join(map(str, sum((force_dict(item[name] or {})).items(), ())))


@conversion
def delimited_object(item: Generated, name: str) -> None:
    item[name] = make_delimited(item[name])


@conversion
def extracted_object(item: Generated, name: str) -> None:
    """Merge a child node to the parent one."""
    generated = item.pop(name)
    if generated and isinstance(generated, dict):
        item.update(generated)
    else:
        item[name] = ""


@conversion
def label_primitive(item: Generated, name: str) -> None:
    """Serialize a primitive value with the `label` style.

    5 => ".5"
    """
    new = item[name]
    if new:
        item[name] = f".{new}"
    else:
        item[name] = ""


@conversion
def label_array(item: Generated, name: str, explode: bool | None) -> None:
    """Serialize an array with the `label` style.

    Explode=True

        id=[3, 4, 5] => ".3.4.5"

    Explode=False

        id=[3, 4, 5] => ".3,4,5"
    """
    if explode:
        delimiter = "."
    else:
        delimiter = ","
    new = delimiter.join(map(str, force_iterable(item[name] or ())))
    if new:
        item[name] = f".{new}"
    else:
        item[name] = ""


@conversion
def label_object(item: Generated, name: str, explode: bool | None) -> None:
    """Serialize an object with the `label` style.

    Explode=True

        id={"role": "admin", "firstName": "Alex"} => ".role=admin.firstName=Alex"

    Explode=False

        id={"role": "admin", "firstName": "Alex"} => ".role=admin,firstName,Alex"
    """
    if explode:
        new = make_delimited(item[name], ".")
    else:
        object_items = map(str, sum(force_dict(item[name] or {}).items(), ()))
        new = ",".join(object_items)
    if new:
        item[name] = f".{new}"
    else:
        item[name] = new


@conversion
def matrix_primitive(item: Generated, name: str) -> None:
    """Serialize a primitive value with the `matrix` style.

    5 => ";id=5"
    """
    new = item[name]
    if new is not None:
        item[name] = f";{name}={new}"
    else:
        item[name] = ""


@conversion
def matrix_array(item: Generated, name: str, explode: bool | None) -> None:
    """Serialize an array with the `matrix` style.

    Explode=True

        id=[3, 4, 5] => ";id=3;id=4;id=5"

    Explode=False

        id=[3, 4, 5] => ";id=3,4,5"
    """
    if explode:
        new = ";".join(f"{name}={value}" for value in force_iterable(item[name] or ()))
    else:
        new = ",".join(map(str, force_iterable(item[name] or ())))
    if new:
        item[name] = f";{new}"
    else:
        item[name] = new


@conversion
def matrix_object(item: Generated, name: str, explode: bool | None) -> None:
    """Serialize an object with the `matrix` style.

    Explode=True

        id={"role": "admin", "firstName": "Alex"} => ";role=admin;firstName=Alex"

    Explode=False

        id={"role": "admin", "firstName": "Alex"} => ";role=admin,firstName,Alex"
    """
    if explode:
        new = make_delimited(item[name], ";")
    else:
        object_items = map(str, sum(force_dict(item[name] or {}).items(), ()))
        new = ",".join(object_items)
    if new:
        item[name] = f";{new}"
    else:
        item[name] = ""


@conversion
def nothing(item: Generated, name: str) -> None:
    """Remove a key from an item."""
    item.pop(name, None)


@conversion
def to_string(item: Generated, name: str) -> None:
    """Convert the value to a string."""
    item[name] = str(item[name])
