import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class IngredientRequest(BaseModel):
    name: str
    amount: str
    unit: str | None = None


class RecipeCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    servings: int = 4
    ingredients: list[IngredientRequest] = []
    glyph_kind: str | None = Field(default=None, max_length=20)
    glyph_color: str | None = Field(default=None, max_length=20)


class RecipeUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    servings: int | None = None
    ingredients: list[IngredientRequest] | None = None
    glyph_kind: str | None = Field(default=None, max_length=20)
    glyph_color: str | None = Field(default=None, max_length=20)


class IngredientResponse(BaseModel):
    id: uuid.UUID
    name: str
    amount: str
    unit: str | None

    model_config = {"from_attributes": True}


class RecipeResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    servings: int
    author_id: uuid.UUID
    ingredients: list[IngredientResponse]
    glyph_kind: str | None = None
    glyph_color: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
