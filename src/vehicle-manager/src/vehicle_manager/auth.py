from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel

from vehicle_manager.errors import (
    TokenExpiredError,
    TokenVerificationFailedError,
    WrongTenantError,
    eh,
)
from vehicle_manager.settings import GetSettings


@lru_cache
def _get_jwks_client_cached(url: str):
    return PyJWKClient(url)


def _get_jwks_client(settings: GetSettings):
    return _get_jwks_client_cached(settings.oauth_jwks_url)


def _get_token_payload(
    settings: GetSettings,
    jwks_client: Annotated[PyJWKClient, Depends(_get_jwks_client)],
    creds: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
) -> dict:
    token = creds.credentials

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.oauth_issuer_url,
            audience=settings.oauth_client_id,
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise TokenExpiredError(headers={"WWW-Authenticate": "Bearer"})  # type: ignore
    except jwt.PyJWTError as e:
        raise TokenVerificationFailedError(
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},  # type: ignore
        )


class UserInfo(BaseModel):
    sub: str
    tenant_id: str


def get_user_info(
    settings: GetSettings,
    token_payload: Annotated[dict[str, Any], Depends(_get_token_payload)],
):
    ret = UserInfo.model_validate(token_payload)
    if ret.tenant_id != settings.tenant_id:
        raise WrongTenantError(headers={"WWW-Authenticate": "Bearer"})  # type: ignore
    return ret


GetUserInfo = Annotated[UserInfo, Depends(get_user_info)]


def get_user_id(user_info: GetUserInfo) -> str:
    return user_info.sub


GetUserId = Annotated[str, Depends(get_user_id)]


AUTH_RESPONSES_DICT: dict[int | str, Any] = {
    401: eh.generate_swagger_response(
        TokenExpiredError, TokenVerificationFailedError, WrongTenantError
    )
}
