import uuid
from datetime import date as date_type
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CreateDailyRequest(BaseModel):
    date: Optional[date_type] = None


class FinalizeDateRequest(BaseModel):
    date: Optional[date_type] = None


class SuggestRecipeRequest(BaseModel):
    recipe_id: uuid.UUID


class VoteRequest(BaseModel):
    recipe_id: uuid.UUID


class MenuRecipeResponse(BaseModel):
    id: uuid.UUID
    recipe_id: uuid.UUID
    title: str
    source: str
    added_by: Optional[uuid.UUID] = None
    votes_count: int = 0

    model_config = {"from_attributes": True}


class MenuResponse(BaseModel):
    id: uuid.UUID
    date: date_type
    status: str
    winner_recipe_id: Optional[uuid.UUID] = None
    recipes: list[MenuRecipeResponse]
    created_at: datetime
    user_voted_recipe_id: Optional[uuid.UUID] = None
    total_votes: int = 0

    model_config = {"from_attributes": True}
