from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for all knowledge DB tables. All tables — in `public` schema."""
