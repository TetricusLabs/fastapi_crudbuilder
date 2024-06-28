import functools
from typing import Callable, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.strategy_options import _AbstractLoad
from sqlalchemy.schema import Column


def get_pk(db_model: DeclarativeMeta) -> Optional[Column]:
    """Get primary key of SQLAlchemy model"""
    for column in db_model.__mapper__.columns:
        if column.primary_key:
            return column
    return None


def get_response_model(
    db_model: DeclarativeMeta, exclude_fields: set[str] = None
) -> BaseModel:
    """Dynamically build response model from given database model

    :param db_model: A SQLALchemy declarative model class
    :param exclude_fields: Fields to exclude when building model schemas
    :return: Pydantic model that defines response for endpoints
    """
    if exclude_fields is None:
        exclude_fields = set()
        
    columns = inspect(db_model).columns.items()
    relationship_names = inspect(db_model).relationships.keys()
    base_columns = {
        name: (
            Optional[col.type.python_type] if col.nullable else col.type.python_type,
            None,
        )
        for name, col in columns
        if name not in exclude_fields
    }
    relationships = {
        name: (Optional[Union[list[dict], dict]], None)
        for name in relationship_names
        if name not in exclude_fields
    }
    types = {**base_columns, **relationships}
    return create_model(
        db_model.__name__,
        **types,
        __config__=ConfigDict(
            from_attributes=True,
            arbitrary_types_allowed=True,
            extra="allow",
            ignored_types=(DeclarativeMeta,),
        ),
    )


def get_create_schema(db_model: DeclarativeMeta, exclude_fields: set[str] = None) -> BaseModel:
    """Dynamically build create schema from given database model

    :param db_model: A SQLALchemy declarative model class
    :param exclude_fields: Fields to exclude when building model schemas
    :return: Pydantic request model for create endpoints
    """
    
    if exclude_fields is None:
        exclude_fields = set()
        
    columns = inspect(db_model).columns.items()
    base_columns = {
        name: (
            Optional[col.type.python_type] if col.nullable else col.type.python_type,
            None,
        )
        for name, col in columns
        if not col.default and col.name not in exclude_fields
    }
    return create_model(
        db_model.__name__,
        **base_columns,
        __config__=ConfigDict(from_attributes=True, extra="forbid"),
    )


def get_update_schema(db_model: DeclarativeMeta, exclude_fields: set[str] = None) -> BaseModel:
    """Dynamically build update schema from given database model

    :param db_model: A SQLALchemy declarative model class
    :param exclude_fields: Fields to exclude when building model schemas
    :return: Pydantic request model for update endpoints
    """
    if exclude_fields is None:
        exclude_fields = set()
        
    columns = inspect(db_model).columns.items()
    base_columns = {
        name: (
            Optional[col.type.python_type] if col.nullable else col.type.python_type,
            None,
        )
        for name, col in columns
        if not col.primary_key and col.name not in exclude_fields
    }
    return create_model(
        db_model.__name__,
        **base_columns,
        __config__=ConfigDict(from_attributes=True, extra="forbid"),
    )


def build_joins(
    db_model: DeclarativeMeta, relationships: list[str]
) -> list["_AbstractLoad"]:
    """Build joins from a set of requested relationships

    :param db_model: A SQLALchemy declarative model class
    :param relationships: Fields in db_model connected via a SQLAlchemy relationship()
    :return: Joinedloads to include relationships
    """
    db_model_relationships = dict(inspect(db_model).relationships.items())
    joins = [
        joinedload(getattr(db_model, relationship))
        for relationship in relationships
        if relationship in db_model_relationships
    ]
    return joins


def run_postprocessors(
    postprocessors: Sequence[Callable],
    models: DeclarativeMeta | Sequence[DeclarativeMeta],
) -> DeclarativeMeta | Sequence[DeclarativeMeta]:
    if postprocessors:
        if isinstance(models, Sequence):
            return [
                functools.reduce(
                    lambda model, postprocessor: postprocessor(model),
                    postprocessors,
                    model,
                )
                for model in models
            ]
        else:
            return functools.reduce(
                lambda model, postprocessor: postprocessor(model),
                postprocessors,
                models,
            )
    return models
