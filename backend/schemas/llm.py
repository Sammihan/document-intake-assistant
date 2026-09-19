from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtractedExecutor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str | None = None
    relationship: str | None = None


class ExtractedFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    full_name: str | None = None
    home_address: str | None = None
    covers_worldwide_assets: bool | None = None
    has_children: bool | None = None
    children: list[str] | None = None
    executor: ExtractedExecutor | None = None
    specific_gifts: list[str] | None = None
    additional_wishes: str | None = None

    @model_validator(mode="after")
    def children_must_be_empty_when_no_children(self) -> "ExtractedFields":
        if self.has_children is False and self.children:
            raise ValueError("children must be empty when has_children is false")
        return self

    def has_updates(self) -> bool:
        return bool(self.model_dump(exclude_none=True))


class LLMExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    extracted_fields: ExtractedFields = Field(default_factory=ExtractedFields)
    assistant_message: str = ""
    needs_clarification: bool
    clarification_reason: str | None = None

    @model_validator(mode="after")
    def clarification_reason_required_when_needed(self) -> "LLMExtractionResponse":
        if self.needs_clarification and not self.clarification_reason:
            raise ValueError("clarification_reason is required when needs_clarification is true")
        return self
