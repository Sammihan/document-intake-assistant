from pydantic import BaseModel, ConfigDict, Field, model_validator


class Executor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    name: str | None = None
    relationship: str | None = None


class PersonalWishesState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

    full_name: str | None = None
    home_address: str | None = None
    covers_worldwide_assets: bool | None = None
    has_children: bool | None = None
    children: list[str] = Field(default_factory=list)
    executor: Executor = Field(default_factory=Executor)
    specific_gifts: list[str] = Field(default_factory=list)
    additional_wishes: str | None = None

    @model_validator(mode="after")
    def children_must_be_empty_when_no_children(self) -> "PersonalWishesState":
        if self.has_children is False and self.children:
            raise ValueError("children must be empty when has_children is false")
        return self
