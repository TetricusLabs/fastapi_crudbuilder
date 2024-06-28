from unittest.mock import Mock

import pytest
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session, declarative_base

from fastapi_crudbuilder import CRUDBuilder

Base = declarative_base()


class TestModel(Base):
    __tablename__ = "test"

    id = Column(Integer, primary_key=True)
    name = Column(String)


class TestSchema(BaseModel):
    id: int
    name: str


def dummy_get_db():
    pass

@pytest.fixture
def mock_db_session():
    return Mock(spec=Session)
@pytest.fixture
def mock_get_db(mock_db_session):
    def _mock_get_db():
        return mock_db_session
    return _mock_get_db




@pytest.fixture
def crud_builder(mock_get_db):
    return CRUDBuilder(
        db_func=mock_get_db,
        db_model=TestModel,
        prefix="/test",
        create_schema=TestSchema,
        update_schema=TestSchema,
        allow_delete=True,
    )


def test_crud_builder_init(crud_builder, mock_get_db):
    assert crud_builder.db_func == mock_get_db
    assert crud_builder.db_model == TestModel
    assert crud_builder.prefix == "/test"
    assert crud_builder.create_schema == TestSchema
    assert crud_builder.update_schema == TestSchema
    assert crud_builder.allow_delete


def test_crud_builder_init_with_invalid_parameters(mock_get_db):
    with pytest.raises(AttributeError):
        CRUDBuilder(
            db_func=mock_get_db,
            db_model="InvalidModel",
            prefix="/test",
            create_schema=TestSchema,
            update_schema=TestSchema,
            allow_delete=True,
        )


def test_crud_builder_read_one(crud_builder, mock_db_session):
    # Arrange
    mock_db_session.get.return_value = TestModel(id=1, name="Test")

    # Act
    result = crud_builder._read_one()(
        item_id=1,
        db=mock_db_session,
    )

    # Assert
    assert result["id"] == 1
    assert result["name"] == "Test"
    mock_db_session.get.assert_called_once_with(TestModel, 1, options=None)


@pytest.mark.parametrize("allow_delete", [True, False])
def test_crud_builder_build_with_different_allow_delete(mock_get_db, allow_delete):
    # Arrange
    crud_builder = CRUDBuilder(
        db_func=mock_get_db,
        db_model=TestModel,
        prefix="/test",
        create_schema=TestSchema,
        update_schema=TestSchema,
        allow_delete=allow_delete,
    )

    # Act
    router = crud_builder.build()

    # Assert
    assert router is not None
    assert len(router.routes) == (6 if allow_delete else 4)
