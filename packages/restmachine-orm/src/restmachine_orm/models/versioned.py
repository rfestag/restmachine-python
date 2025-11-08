"""
Versioned model support for RestMachine ORM.

Uses Pydantic's discriminated unions to automatically deserialize to the correct
version class, with automatic upgrades to the latest version.
"""

from typing import ClassVar, Optional, TYPE_CHECKING, Any
from pydantic import Field as PydanticField
import inflection
from restmachine_orm.models.base import Model

if TYPE_CHECKING:
    pass


class VersionedModel(Model):
    """
    Base class for versioned models.

    Enables schema evolution with automatic upgrades using Pydantic's discriminated
    union support. Each version self-registers and knows how to upgrade itself.

    Usage:
        @versioned_model("User")
        class UserV1(VersionedModel):
            id: str
            name: str

            def upgrade(self):
                return UserV2(id=self.id, name=self.name, age=0)

        @versioned_model("User", latest=True)
        class UserV2(VersionedModel):
            id: str
            name: str
            age: int = 0
            # No upgrade() - this is latest

        # Application uses latest
        User = get_latest_model("User")  # Returns UserV2
        user = User.get(id="123")  # Auto-upgrades V1 records to V2
    """

    # Discriminator field for Pydantic unions
    # Uses class name as the discriminator value
    # This is a regular field that gets saved to the database
    model_version: Optional[str] = PydanticField(default=None)

    # Set by @versioned_model decorator
    _model_name: ClassVar[Optional[str]] = None
    _is_latest: ClassVar[bool] = False

    def __init__(self, **data: Any):
        """Initialize versioned model, setting discriminator."""
        # Set discriminator before calling super().__init__
        if 'model_version' not in data or data.get('model_version') is None:
            data['model_version'] = self.__class__.__name__

        super().__init__(**data)

    def upgrade(self) -> Optional["VersionedModel"]:
        """
        Upgrade this instance to the next version.

        Each version implements this to return an instance of the next (or a later)
        version. The latest version should not override this (returns None).

        Returns:
            Instance of a newer version, or None if this is the latest version.

        Example:
            def upgrade(self):
                # V1 knows how to become V2
                return UserV2(
                    id=self.id,
                    name=self.name,
                    age=0  # New field with default
                )

        Note:
            - Only needs to know about the immediate next version
            - Can skip versions if desired (V1 → V3, skipping V2)
            - Latest version doesn't implement this (returns None)
            - Backend infrastructure handles recursive chaining
        """
        return None  # Default: no upgrade (latest version)

    @classmethod
    def _get_table_name(cls) -> str:
        """
        Get table name from model_name.

        All versions of a model share the same table, derived from the logical
        model name (e.g., "User" → "users").
        """
        if hasattr(cls, '_model_name') and cls._model_name:
            return inflection.pluralize(cls._model_name.lower())

        # Fallback for non-versioned models
        return super()._get_table_name()  # type: ignore[misc, no-any-return]
