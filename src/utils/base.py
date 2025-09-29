import pydantic
from typing import Generic, Iterator, TypeVar, List, Optional, get_type_hints, Type

T = TypeVar('T', bound="BaseModel")


class BaseModel(pydantic.BaseModel):
    @classmethod
    def doc_schema(cls):
        return {'application/json': cls.model_json_schema(ref_template="#/components/schemas/{model}")}


def optional_model(name: str, base: type[BaseModel]) -> type[BaseModel]:
    annotations = get_type_hints(base)
    optional_fields = {
        k: (Optional[v], None)
        for k, v in annotations.items()
    }
    return pydantic.create_model(name, **optional_fields, __base__=BaseModel)


class BaseList(pydantic.RootModel[List[T]], Generic[T]):
    root: List[T]

    def __iter__(self) -> Iterator[T]:
        return iter(self.root)

    def __getitem__(self, item) -> T:
        return self.root[item]

    @classmethod
    def doc_schema(cls):
        return {'application/json': cls.model_json_schema(ref_template="#/components/schemas/{model}")}
