# FastAPI CRUDBuilder
Designed for use with FastAPI to build a router for CRUD operations on a SQLAlchemy
model. It automates the creation of API endpoints for these operations, making it
easier to set up a RESTful API.

Endpoints are created for the following operations:
- Read all items
- Read one item by primary key
- Create one item
- Update one item by primary key
- Delete all items
- Delete one item by primary key

Endpoints created by CRUDBuilder are designed to support the OpenAPI documentation that FastAPI automatically generates.
Optionally, you can add security, caching and custom postprocessors to the generated endpoints. They're designed to attach to
an existing `APIRouter` object in FastAPI, or alternatively can be used to create a new router.

---

**Documentation**: (This file) <a href="https://github.com/TetricusLabs/fastapi_crudbuilder" target="_blank">https://github.com/TetricusLabs/crudbuilder</a>

**Source Code**: <a href="https://github.com/TetricusLabs/fastapi_crudbuilder" target="_blank">https://github.com/TetricusLabs/crudbuilder</a>

---

## Pre-requisites
- Python 3.10+
- FastAPI
- SQLAlchemy
- [optional] Memcached (pymemcached client)

## Features
- Automatically generate CRUD endpoints for a given SQLAlchemy model
- Automatically generate OpenAPI documentation for the generated endpoints
- Optionally add security to the generated endpoints
- Optionally add caching to the generated endpoints
- Optionally add postprocessors to the generated endpoints
- Optionally infer the create and update models from the SQLAlchemy model, or provide custom Pydantic models
- Designed to be used with FastAPI
- Extendable to support other ORMs and caches



## Installation
```bash
poetry add fastapi_crudbuilder
```
## Usage Example

```python
from fastapi import APIRouter, Security

from fastapi_crudbuilder import CRUDBuilder
from src.postprocessors import YOUR_POSTPROCESSOR_1, YOUR_POSTPROCESSOR_2
from src.database import YOUR_DB_SESSION
from src.database.models import YOUR_MODEL
from src.security import YOUR_SECURITY_FUNCTION

example = APIRouter(prefix="/example", tags=["Example CRUD"])  # set up a FastAPI router to attach the CRUD endpoints to


@example.get("custom_non_crudbldr_route")
def custom_route():
    return {"message": "Hello World"}


example = CRUDBuilder(
    db_model=YOUR_MODEL,
    db_func=YOUR_DB_SESSION,
    infer_create=True,  # Optionally infer the create model
    infer_update=True,  # Optionally infer the update model
    read_security=Security(YOUR_SECURITY_FUNCTION.verify, scopes=["YOUR_MODEL:all:read"]),
    # Optionally add custom security function and scope to the endpoint
    create_security=Security(YOUR_SECURITY_FUNCTION.verify, scopes=["YOUR_MODEL:all:create"]),
    update_security=Security(YOUR_SECURITY_FUNCTION.verify, scopes=["YOUR_MODEL:all:update"]),
    delete_security=Security(YOUR_SECURITY_FUNCTION.verify, scopes=["YOUR_MODEL:all:delete"]),
    response_postprocessors=[YOUR_POSTPROCESSOR_1(YOUR_MODEL), YOUR_POSTPROCESSOR_2(YOUR_MODEL)],
).build(example)  # Attach the CRUD endpoints to the router

```
The router **must** then be added to the FastAPI app (like any other router) in order to be used.
```python
from fastapi import FastAPI
from src.routes.example import example

app = FastAPI()
app.include_router(example)

```
## Required parameters
- db_model: The SqlAlchemy model you want to create CRUD endpoints for
- db_func: The function that returns the SqlAlchemy session you'd like to use

## Optional extensions

### Infer Create/Update
This will infer the model for the create and update endpoints from the SqlAlchemy model. Otherwise, you can pass in a 
custom Pydantic model for the data to be validated against. This will also be reflected in the automatically generated OpenAPI documentation.

### Security
You can pass in a FastAPI Security object to the CRUDBuilder class for each operation type (read, create, update, delete).

### Postprocessors
Post Processors are passed into the CRUDBuilder class as a list of functions that take the model as an argument and
return a function that takes the response as an argument and returns a modified version of the response. 

These are processed **in order** (e.g. in the example above `YOUR_POSTPROCESSOR_1` would be applied to 
the database result first, then `YOUR_POSTPROCESSOR_2` etc.) 

Post Processors are expected to receive a passed-in data model and return a callable that takes the response data and modifies it.

This allows you to adjust the response of the CRUD endpoints -- for example if you store dates in your Database as UTC
but want to render them to users in their local time or a different format. See example below:

```python
def transform_response_date(db_model: BaseModel) -> Callable:
    def transform_dates(data: db_model.__class__, db_model: DeclarativeMeta = db_model):
        columns = inspect(db_model).columns.items()
        for name, column in columns:
            if column.type.python_type.__name__ in (
                "datetime",
                "date",
                "datetime.datetime",
            ):
                _LOGGER.info(f"Transforming {name} to ISO 8601 date format.")
                if getattr(data, name):
                    setattr(
                        data, name, convert_iso_datetime_format(getattr(data, name))
                    )
        return data

    return transform_dates
```


### Caching
You can optionally pass a cache object to the CRUDBuilder class. Right now only Memcached is supported, and only the pymemcached client
has been tested. See https://pymemcache.readthedocs.io/en/latest/getting_started.html for more information on how to set up a pymemcached client.

In theory any client with the methods:
- get
- set
- delete
- delete_many 

should work, but this has not been tested.


## Supported ORMS/ Caches
(Only SqlAlchemy and Memcached are supported for now)
- SqlAlchemy
- Memcached (pymemcached client)


## Calling endpoints:
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

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## Testing
We use pytest for testing. To run the tests, simply run `pytest` in the root directory of the project. Tests are stored in the `tests` directory.

## License
[MIT](https://choosealicense.com/licenses/mit/)
