import logging
from typing import Annotated, Any, Callable, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, RootModel

try:
    from sqlalchemy import delete, select
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.declarative import DeclarativeMeta
    from sqlalchemy.orm import Session
except ImportError:
    sqlalchemy_installed = False
else:
    sqlalchemy_installed = True

from fastapi_crudbuilder.transform import (
    build_joins,
    get_create_schema,
    get_pk,
    get_response_model,
    get_update_schema,
    run_postprocessors,
)

from fastapi_crudbuilder.generators import generate_cache_key

_LOGGER = logging.getLogger(__name__)


class CRUDBuilder:
    """Build router for performing CRUD (Create, Read, Update, Delete) operations

    Designed for use with FastAPI to build a router for CRUD operations on a SQLAlchemy
    model. It automates the creation of API endpoints for these operations, making it
    easier to set up a RESTful API.

    IMPORTANT: FastAPI matches URL paths in the order they're defined. That means you
    should define your routers from most specific to most general. For example:
    @router.get("/specific")
    def specific_endpoint():
        pass

    @router.get("/{general})
    def general_endpoint(general: str)
        pass

    Dependencies:
        FastAPI: Web framework for building APIs.
        SQLAlchemy: ORM for interacting with databases.
        Pydantic: Data validation and settings management using Python type annotations.

    Standard Usage - You pass in the create and update schemas:
        from your_model_file import YourModel
        from your_schemas import CreateSchema, UpdateSchema

        crud_router = CRUDBuilder(
            db_func=get_db,  # Function to get the database session
            db_model=YourModel,
            prefix="/yourmodel",
            create_schema=CreateSchema,
            update_schema=UpdateSchema,
            allow_delete=True
        ).build()

        app = FastAPI()
        app.include_router(crud_router)

    Inference Usage - Infers create and update schemas from your model:
        from your_model_file import YourModel

        crud_router = CRUDBuilder(
            db_func=get_db,  # Function to get the database session
            db_model=YourModel,
            prefix="/yourmodel",
            infer_create=True,
            infer_update=True,
            allow_delete=True
        ).build()

        app = FastAPI()
        app.include_router(crud_router)

    Calling endpoints:
        GET /yourmodel
        Get all items for your model
        Query params:
            limit: Number of items to return
            skip: Number of items to skip
            sort_field: Name of field to sort by, defaults to the primary key
            sort_desc: True to sort descending, False for ascending
            equals_field: Name of field to filter to a value, paired with equals_value
            equals_value: Value of equals_field to filter by
            relationships: Comma-separated names of fields that are relationships in the
                SQLAlchemy model

        GET /yourmodel/{item_id}
        Get one item for your model by primary key (item_id)
        Query params:
            relationships: Comma-separated names of fields that are relationships in the
                SQLAlchemy model

        POST /yourmodel
        Create one new item for your model
        Request body:
            JSON must match the given create_schema

        PUT /yourmodel/{item_id}
        Update fields for one item for your model by primary key (item_id)
        Request body:
            JSON must match the given update_schema

        DELETE /yourmodel
        Delete all contents in your model

        DELETE /yourmodel/{item_id}
        Delete one item for your model by primary key (item_id)

    Notes:
        * Ensure that the provided SQLAlchemy model and Pydantic schemas are compatible.
        * The db_func should return a SQLAlchemy Session object. This will be injected
            using FastAPI's Depends.
        * The CRUD endpoints will reflect the attributes and relationships defined in
            the SQLAlchemy model.
    """

    def __init__(
            self,
            db_func: Callable,
            db_model: DeclarativeMeta,
            cache_func: Optional[Callable] = None,
            cache_expiry_seconds: int = 60,
            prefix: str = None,
            create_schema: Optional[BaseModel] = None,
            update_schema: Optional[BaseModel] = None,
            infer_create: bool = False,
            infer_update: bool = False,
            allow_delete: bool = False,
            read_security: Optional[Security] = None,
            create_security: Optional[Security] = None,
            update_security: Optional[Security] = None,
            delete_security: Optional[Security] = None,
            router_dependencies: Optional[Sequence[Depends]] = None,
            read_dependencies: Optional[Sequence[Depends]] = None,
            create_dependencies: Optional[Sequence[Depends]] = None,
            update_dependencies: Optional[Sequence[Depends]] = None,
            delete_dependencies: Optional[Sequence[Depends]] = None,
            exclude_fields: Optional[set] = None,
            response_postprocessors: Optional[Sequence[Callable]] = None,
    ):
        assert (
            sqlalchemy_installed
        ), "SQLAlchemy must be installed."

        """Initializes CRUDBuilder object

        :param prefix: URL prefix for the generated routes.
        :param db_func: A callable that returns a SQLAlchemy Session.
        :param db_model: SQLAlchemy declarative model class.
        :param cache_func: A callable that returns a cache session.
        :param cache_expiry_seconds: Number of seconds to cache data.
        :param create_schema: Pydantic model to validate data on create operations.
        :param update_schema: Pydantic model to validate data on update operations.
        :param infer_create: Infer create_schema from db_model. Skipped if schema given
        :param infer_update: Infer update_schema from db_model. Skipped if schema given
        :param allow_delete: Enable or disable delete operations.
        :param read_security: Security dependency to protect read endpoints
        :param create_security: Security dependency to protect create endpoints
        :param update_security: Security dependency to protect update endpoints
        :param delete_security: Security dependency to protect delete endpoints
        :param router_dependencies: Dependencies to add to router
        :param read_dependencies: Dependencies to add to read endpoints
        :param create_dependencies: Dependencies to add to create endpoints
        :param update_dependencies: Dependencies to add to update endpoints
        :param delete_dependencies: Dependencies to add to delete endpoints
        :param exclude_fields: Fields to exclude when building model schemas
        """
        self.prefix = prefix
        self.db_func = db_func
        self.db_model = db_model
        self.cache_func = cache_func if cache_func else lambda: None
        self.cache_expiry_seconds = cache_expiry_seconds
        self.create_schema = create_schema
        self.update_schema = update_schema
        self.infer_create = infer_create
        self.infer_update = infer_update
        self.allow_delete = allow_delete
        self.read_security = read_security
        self.create_security = create_security
        self.update_security = update_security
        self.delete_security = delete_security
        self.router_dependencies = router_dependencies
        self.read_dependencies = read_dependencies
        self.create_dependencies = create_dependencies
        self.update_dependencies = update_dependencies
        self.delete_dependencies = delete_dependencies
        self.exclude_fields = exclude_fields
        self.response_postprocessors = response_postprocessors

        if not create_schema and infer_create:
            self.create_schema = get_create_schema(self.db_model, self.exclude_fields)
        if not update_schema and infer_update:
            self.update_schema = get_update_schema(self.db_model, self.exclude_fields)

        self.pk = get_pk(self.db_model)
        self.pk_name = self.pk.description
        self.pk_type = self.pk.type.python_type
        self.pk_ref = getattr(self.db_model, self.pk.description)
        self.response_model = get_response_model(self.db_model, self.exclude_fields)

    def build(self, router: Optional[APIRouter] = None) -> APIRouter:
        """Build APIRouter instance with routes for CRUD operations based on the
        provided model and schemas.
        """
        if not router:
            router = APIRouter(
                prefix=self.prefix, dependencies=self.router_dependencies
            )

        router.add_api_route(
            "/{item_id}",
            self._read_one(),
            methods=["GET"],
            dependencies=self.read_dependencies,
            response_model=self.response_model,
            response_model_exclude_unset=True,
            summary=f"Read one {self.db_model.__name__} item",
            description=f"Read one {self.db_model.__name__} item by primary key",
        )
        router.add_api_route(
            "",
            self._read_all(),
            methods=["GET"],
            dependencies=self.read_dependencies,
            response_model=RootModel[list[self.response_model]],
            response_model_exclude_unset=True,
            summary=f"Read all {self.db_model.__name__} items",
            description=f"Read all {self.db_model.__name__} items",
        )
        if self.create_schema:
            router.add_api_route(
                "",
                self._create_one(),
                methods=["POST"],
                dependencies=self.create_dependencies,
                response_model=self.response_model,
                response_model_exclude_unset=True,
                summary=f"Create one {self.db_model.__name__} item",
                description=f"Create one {self.db_model.__name__} item",
            )
        if self.update_schema:
            router.add_api_route(
                "/{item_id}",
                self._update_one(),
                methods=["PUT"],
                dependencies=self.update_dependencies,
                response_model=self.response_model,
                response_model_exclude_unset=True,
                summary=f"Update one {self.db_model.__name__} item",
                description=f"Update one {self.db_model.__name__} item by primary key",
            )
        if self.allow_delete:
            router.add_api_route(
                "/{item_id}",
                self._delete_one(),
                methods=["DELETE"],
                dependencies=self.delete_dependencies,
                response_model=self.response_model,
                response_model_exclude_unset=True,
                summary=f"Delete one {self.db_model.__name__} item",
                description=f"Delete one {self.db_model.__name__} item by primary key",
            )
            router.add_api_route(
                "",
                self._delete_all(),
                methods=["DELETE"],
                dependencies=self.delete_dependencies,
                response_model=RootModel[list[self.response_model]],
                response_model_exclude_unset=True,
                summary=f"Delete all {self.db_model.__name__} items",
                description=f"Delete all {self.db_model.__name__} items",
            )
        return router

    def _read_one(self) -> Callable:
        """Build route to read a single item"""

        def route(
                item_id: self.pk_type,
                db: Annotated[Session, Depends(self.db_func)],
                cache: Annotated[Any | None, Depends(self.cache_func)] = None,
                _: Annotated[Any | None, self.read_security] = None,
                relationships: Optional[str] = None,
        ):
            _LOGGER.info(
                f"Reading {self.db_model.__name__} {item_id}; "
                f"relationships {relationships}"
            )
            cache_prefix = self.db_model.__name__.lower()
            cache_key = None

            joins = None
            if relationships:
                cache_prefix.join(f"_{relationships}")
                joins = build_joins(self.db_model, relationships.split(","))

            if cache:
                cache_key = generate_cache_key(cache_prefix, item_id)
                cached_value = cache.get(cache_key)
                if cached_value:
                    _LOGGER.info(f"Cache hit for {cache_key}, returning cached data")
                    return jsonable_encoder(cached_value)

            model = db.get(self.db_model, item_id, options=joins)
            if not model:
                raise HTTPException(404, "No resource found")

            model = run_postprocessors(self.response_postprocessors, model)

            if cache:
                cache.set(cache_key, model, expire=self.cache_expiry_seconds)
                _LOGGER.info(f"Cache miss for {cache_key}, setting cache")

            return jsonable_encoder(model)

        return route

    def _read_all(self) -> Callable:
        """Build route to read all items or a page of items"""

        def route(
                db: Annotated[Session, Depends(self.db_func)],
                cache: Annotated[Any | None, Depends(self.cache_func)] = None,
                _: Annotated[Any | None, self.read_security] = None,
                limit: Optional[int] = 100,  # Prevent accidentally hitting db w/o limit
                skip: Optional[int] = 0,
                sort_field: str = self.pk_name,
                sort_desc: Optional[bool] = False,
                equals_field: Optional[str] = None,
                equals_value: Optional[str] = None,
                relationships: Optional[str] = None,
        ):
            _LOGGER.info(
                f"Reading all {self.db_model.__name__}; "
                f"relationships {relationships}; "
                f"limit {limit}; "
                f"skip {skip}; "
                f"sort_field {sort_field}; "
                f"sort_desc {sort_desc}; "
                f"equals_field {equals_field}; "
                f"equals_value {equals_value}"
            )
            cache_prefix = self.db_model.__name__.lower()
            cache_key = None

            filter_criteria = []
            if equals_field and equals_value:
                cache_prefix.join(f"_{equals_field}_{equals_value}")
                filter_criteria = [getattr(self.db_model, equals_field) == equals_value]

            sort = getattr(self.db_model, sort_field)
            if sort_desc:
                cache_prefix.join(f"_{sort_field}_desc")
                sort = getattr(self.db_model, sort_field).desc()

            if relationships:
                cache_prefix.join(f"_{relationships}")
                joins = build_joins(self.db_model, relationships.split(","))

                if cache:
                    cache_key = generate_cache_key(cache_prefix, "all")
                    cached_value = cache.get(cache_key)
                    if cached_value:
                        _LOGGER.info(
                            f"Cache hit for {cache_key}, returning cached data"
                        )
                        return jsonable_encoder(cached_value)

                models = (
                    db.scalars(
                        select(self.db_model)
                        .options(*joins)
                        .where(*filter_criteria)
                        .order_by(sort)
                        .limit(limit)
                        .offset(skip)
                    )
                    .unique()
                    .all()
                )
                if not models:
                    return []

                models = run_postprocessors(self.response_postprocessors, models)
                if cache:
                    cache.set(cache_key, models, expire=self.cache_expiry_seconds)
                    _LOGGER.info(f"Cache miss for {cache_key}, setting cache")
                return jsonable_encoder(models)

            if cache:
                cache_key = generate_cache_key(cache_prefix, "all")
                cached_value = cache.get(cache_key)
                if cached_value:
                    _LOGGER.info(f"Cache hit for {cache_key}, returning cached data")
                    return jsonable_encoder(cached_value)

            models = db.scalars(
                select(self.db_model)
                .where(*filter_criteria)
                .order_by(sort)
                .limit(limit)
                .offset(skip)
            ).all()
            if not models:
                return []

            models = run_postprocessors(self.response_postprocessors, models)
            if cache:
                cache.set(cache_key, models, expire=self.cache_expiry_seconds)
                _LOGGER.info(f"Cache miss for {cache_key}, setting cache")
            return jsonable_encoder(models)

        return route

    def _create_one(self) -> Callable:
        """Build route to create one item"""

        def route(
                create_schema: self.create_schema,
                db: Annotated[Session, Depends(self.db_func)],
                _: Annotated[Any | None, self.create_security] = None,
        ):
            _LOGGER.info(
                f"Create {self.db_model.__name__}; "
                f"create_schema {create_schema.model_dump()}"
            )
            model = self.db_model(**create_schema.model_dump())
            db.add(model)
            db.commit()
            db.refresh(model)

            model = run_postprocessors(self.response_postprocessors, model)

            return jsonable_encoder(model)

        return route

    def _update_one(self) -> Callable:
        """Build route to update attributes for one item"""

        def route(
                item_id: self.pk_type,
                update_fields: dict[str, Any],
                db: Annotated[Session, Depends(self.db_func)],
                cache: Annotated[Any | None, Depends(self.cache_func)] = None,
                _: Annotated[Any | None, self.update_security] = None,
        ):
            # Validate type and transform raw payload into Pydantic model
            update_schema = self.update_schema(**update_fields)
            _LOGGER.info(
                f"Update one {self.db_model.__name__} {item_id}; "
                f"update_schema {update_schema.model_dump()}"
            )
            try:
                model = db.get(self.db_model, item_id)
                if not model:
                    raise HTTPException(404, "No resource found")

                # We iterate through the keys in the given payload instead of using a
                # Pydantic model in the function signature because we want to be able
                # to update only a subset of fields and not all.
                for key in update_fields.keys():
                    setattr(model, key, getattr(update_schema, key))

                db.add(model)
                db.commit()
                db.refresh(model)

                if cache:
                    cache_key = generate_cache_key(
                        f"{self.db_model.__name__.lower()}", item_id
                    )
                    _LOGGER.info(f"Deleting cache for {cache_key}")
                    cache.delete(cache_key)

            except IntegrityError as e:
                db.rollback()
                raise HTTPException(500, e)

            model = run_postprocessors(self.response_postprocessors, model)

            return jsonable_encoder(model)

        return route

    def _delete_one(self) -> Callable:
        """Build route to delete one item"""

        def route(
                item_id: self.pk_type,
                db: Annotated[Session, Depends(self.db_func)],
                cache: Annotated[Any | None, Depends(self.cache_func)] = None,
                _: Annotated[Any | None, self.delete_security] = None,
        ):
            _LOGGER.info(f"Delete one {self.db_model.__name__} {item_id}")
            try:
                model = db.scalar(select(self.db_model).where(self.pk_ref == item_id))
                if not model:
                    raise HTTPException(404, "Resource not found")

                db.delete(model)
                db.commit()

                if cache:
                    cache_key = generate_cache_key(
                        f"{self.db_model.__name__.lower()}", item_id
                    )
                    _LOGGER.info(f"Deleting cache for {cache_key}")
                    cache.delete(cache_key)
            except IntegrityError as e:
                db.rollback()
                raise HTTPException(500, e)

            model = run_postprocessors(self.response_postprocessors, model)
            return jsonable_encoder(model)

        return route

    def _delete_all(self) -> Callable:
        """Build route to delete all items"""

        def route(
                db: Annotated[Session, Depends(self.db_func)],
                cache: Annotated[Any | None, Depends(self.cache_func)] = None,
                _: Annotated[Any | None, self.delete_security] = None,
        ):
            _LOGGER.info(f"Delete all {self.db_model.__name__}")
            try:
                db.execute(delete(self.db_model))
                db.commit()
            except IntegrityError as e:
                db.rollback()
                raise HTTPException(500, e)

            result = self._read_all()(db=db)

            if cache:
                keys_to_delete = [
                    generate_cache_key(
                        f"{self.db_model.__name__.lower()}", item[self.pk_name]
                    )
                    for item in result
                ]

                _LOGGER.info(f"Deleting cache for {keys_to_delete}")
                cache.delete_many(keys_to_delete)

            result = run_postprocessors(self.response_postprocessors, result)

            return jsonable_encoder(result)

        return route
