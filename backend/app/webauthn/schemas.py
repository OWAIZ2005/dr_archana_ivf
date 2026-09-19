import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PasskeyOut(BaseModel):
    """Never the credential_id or public_key — those are verification
    material, not something the settings screen that lists a person's
    passkeys has any reason to display or that should ever leave this
    table once written."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    device_label: str | None
    created_at: datetime
    last_used_at: datetime | None


class RegistrationOptionsOut(BaseModel):
    options: dict[str, Any]  # the raw PublicKeyCredentialCreationOptionsJSON — passed to navigator.credentials.create() client-side, opaque to this backend beyond that


class RegistrationVerifyRequest(BaseModel):
    credential: dict[str, Any]  # RegistrationResponseJSON from navigator.credentials.create()
    challenge: str  # echoed back from RegistrationOptionsOut.options.challenge
    device_label: str | None = None


class AuthenticationOptionsOut(BaseModel):
    options: dict[str, Any]


class AuthenticationVerifyRequest(BaseModel):
    credential: dict[str, Any]  # AuthenticationResponseJSON from navigator.credentials.get()
    challenge: str
