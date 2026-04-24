import uuid
from datetime import date as date_type
from datetime import datetime

from pydantic import BaseModel


class CreateDailyRequest(BaseModel):
    date: date_type | None = None


class FinalizeDateRequest(BaseModel):
    date: date_type | None = None


class SuggestRecipeRequest(BaseModel):
    recipe_id: uuid.UUID


class VoteRequest(BaseModel):
    recipe_id: uuid.UUID


class VoterResponse(BaseModel):
    id: uuid.UUID
    first_name: str | None = None
    username: str

    model_config = {"from_attributes": True}


class MenuRecipeResponse(BaseModel):
    id: uuid.UUID
    recipe_id: uuid.UUID
    title: str
    source: str
    added_by: uuid.UUID | None = None
    votes_count: int = 0
    voters: list[VoterResponse] = []

    model_config = {"from_attributes": True}


class MenuResponse(BaseModel):
    id: uuid.UUID
    date: date_type
    status: str
    winner_recipe_id: uuid.UUID | None = None
    recipes: list[MenuRecipeResponse]
    created_at: datetime
    user_voted_recipe_id: uuid.UUID | None = None
    total_votes: int = 0

    model_config = {"from_attributes": True}
