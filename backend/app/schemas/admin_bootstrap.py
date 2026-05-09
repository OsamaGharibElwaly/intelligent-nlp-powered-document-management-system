from pydantic import BaseModel, EmailStr, Field


class AdminBootstrapPromoteRequest(BaseModel):
    secretCode: str = Field(min_length=1)
    confirmSecretCode: str = Field(min_length=1)
    targetEmail: EmailStr


class AdminBootstrapPromoteResponse(BaseModel):
    message: str
    email: str
    role: str
