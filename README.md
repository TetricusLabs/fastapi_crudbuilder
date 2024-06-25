# CRUDBuilder
CRUDBuilder helps you to create CRUD endpoints for your FastAPI/ SqlAlchemy database models.

---

**Documentation**: <a href="https://github.com/TetricusLabs/crudbuilder" target="_blank">https://github.com/TetricusLabs/crudbuilder</a>

**Source Code**: <a href="https://github.com/TetricusLabs/crudbuilder" target="_blank">https://github.com/TetricusLabs/crudbuilder</a>

---

## Description


## Installation
```bash
poetry add CRUDBuilder
```
## Usage
```python
from fastapi import APIRouter, Security

from crudbuilder import CRUDBuilder
from src.postprocessors import YOUR_POSTPROCESSOR_1, YOUR_POSTPROCESSOR_2
from src.database import YOUR_DB_SESSION
from src.database.models import YOUR_MODEL
from src.security import YOUR_SECURITY


example = APIRouter(prefix="/example", tags=["Example CRUD"]) # set up a FastAPI router

@example.get("custom_non_crud_route")
def custom_route():
    return {"message": "Hello World"}

example = CRUDBuilder(
    db_model=YOUR_MODEL,
    db_func=YOUR_DB_SESSION,
    infer_create=True, # Optionally infer the create model
    infer_update=True, # Optionally infer the update model
    read_security=Security(YOUR_SECURITY.verify, scopes=["YOUR_MODEL:all:read"]), # Optionally add custom security function and scope to the endpoint
    create_security=Security(YOUR_SECURITY.verify, scopes=["YOUR_MODEL:all:create"]),
    update_security=Security(YOUR_SECURITY.verify, scopes=["YOUR_MODEL:all:update"]),
    delete_security=Security(YOUR_SECURITY.verify, scopes=["YOUR_MODEL:all:delete"]),
    response_postprocessors=[YOUR_POSTPROCESSOR_1(YOUR_MODEL), YOUR_POSTPROCESSOR_2(YOUR_MODEL)],
).build(example) # Attach the CRUD endpoints to the router

```

## Supported ORMS/ Caches
(Only SqlAlchemy and Memcached are supported for now)
- SqlAlchemy
- Memcached