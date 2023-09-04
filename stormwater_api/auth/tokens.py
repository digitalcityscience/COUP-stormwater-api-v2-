import logging
from datetime import datetime
from typing import Optional

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from stormwater_api.config import settings
from stormwater_api.models.base import BaseModelStrict

logger = logging.getLogger(__name__)


class AuthError(Exception):
    def __init__(self):
        super().__init__()
        self.message = ""


class AuthErrorInvalidToken(AuthError):
    def __init__(self):
        super().__init__()
        self.message = "Invalid token"


class AuthErrorExpiredToken(AuthError):
    def __init__(self):
        super().__init__()
        self.message = "Token is expired"


class AuthErrorMissingToken(AuthError):
    def __init__(self):
        super().__init__()
        self.message = "Header missing bearer token"


class AuthErrorNotAnAccessToken(AuthError):
    def __init__(self):
        super().__init__()
        self.message = "Refresh tokens cannot be used to authenticate."


class ApiUser(BaseModelStrict):
    id: str
    email: str
    restricted: bool
    created_at: datetime


class VerifiedTokenPayload(BaseModelStrict):
    user: ApiUser
    iat: int  # Issued At
    exp: int  # Expiration
    type: str


class TokenManager:
    def __init__(
        self,
        signing_key: str,
    ):
        self.signing_algorithm = "HS256"
        self.signing_key = signing_key

    def _verify_token(self, token: str) -> VerifiedTokenPayload:
        try:
            return VerifiedTokenPayload(
                **jwt.decode(
                    token,
                    self.signing_key,
                    algorithms=[self.signing_algorithm],
                )
            )
        except jwt.ExpiredSignatureError as error:
            logger.error("Token verification failed: Token expired.")
            raise AuthErrorExpiredToken from error
        except Exception as error:
            logger.error("Token verification failed: Invalid token.")
            raise AuthErrorInvalidToken from error

    def verify_access_token(self, token: str) -> ApiUser:
        verified_token = self._verify_token(token)
        if verified_token.type != "access":
            logger.error("Token verification failed: Not an access token.")
            raise AuthErrorNotAnAccessToken
        return verified_token.user


def authorise_request(
    *,
    token: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    request: Request,
) -> ApiUser:
    # TODO remove this condition, use only during development
    # from datetime import datetime
    # if settings.environment == "LOCALDEV":
    #     return ApiUserInToken(
    #         id="local_dev_user",
    #         email="local_dev@user.de",
    #         restricted=False,
    #         created_at=datetime.now(),
    #     )

    if not token:
        raise AuthErrorMissingToken
    if user_in_token := TokenManager(
        settings.auth.token_signing_key
    ).verify_access_token(token.credentials):
        # register in DB that this user called the endpoint for access monitoring
        # USERS_DB.create_request_event(
        #     user_id=user_in_token.id, endpoint=request.url.path.replace("/", "")
        # )

        return user_in_token
