"""Async client for the SIMon mobile API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import secrets
import string
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import CLIENT_ID, CLIENT_SECRET, GRAPHQL_URL, TOKEN_URL

CONSUMPTIONS_QUERY = """
query consumptions {
  consumptions {
    detailedConsumptions {
      consumptions {
        consumed
        expirationDate
        left
        max
        type
        unit
        expiresWithinCurrentPeriod
        displaySeparately
      }
      id
      name
      type
    }
  }
}
"""

MFA_INFO_QUERY = """
query mfaInfo {
  mfaInfo {
    msisdn
    active
    mfaMethods
    alternativeNumber
    hasAlternativeTanMethod
    activeMfas {
      token
      method
      criticalEventType
      validUntil
      remainingAttempts
      nextTanAt
      locked
      lockedUntil
      cdReason
      authenticated
    }
    locked
    loginPossible
  }
}
"""


class SimonMobileError(Exception):
    """Base exception for SIMon mobile."""


class SimonMobileAuthError(SimonMobileError):
    """Authentication failed."""


class SimonMobileMfaRequired(SimonMobileAuthError):
    """Multifactor authentication is required but not supported yet."""


class SimonMobileAccountLocked(SimonMobileAuthError):
    """The SIMon mobile account is locked."""


class SimonMobileConnectionError(SimonMobileError):
    """Communication with SIMon mobile failed."""


class SimonMobileApiError(SimonMobileError):
    """The SIMon mobile API returned an error."""


@dataclass(slots=True)
class Consumption:
    """A single allowance consumption."""

    consumed: float
    expiration_date: datetime | None
    left: float
    maximum: float
    type: str
    unit: str
    expires_within_current_period: bool
    display_separately: bool


@dataclass(slots=True)
class ConsumptionPackage:
    """A tariff or option containing consumptions."""

    id: str
    name: str
    package_type: str
    consumptions: list[Consumption]


@dataclass(slots=True)
class SimonMobileData:
    """Normalized data consumed by Home Assistant entities."""

    msisdn: str
    packages: list[ConsumptionPackage]

    def by_type(self, consumption_type: str) -> list[tuple[ConsumptionPackage, Consumption]]:
        """Return consumptions of a given type."""
        return [
            (package, consumption)
            for package in self.packages
            for consumption in package.consumptions
            if consumption.type == consumption_type
        ]


class SimonMobileApi:
    """Async API client with in-memory OAuth token handling."""

    def __init__(self, session: ClientSession, username: str, password: str) -> None:
        """Initialize the client."""
        self._session = session
        self._username = username
        self._password = password
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._access_token_valid_until = 0.0
        self._auth_lock = asyncio.Lock()

    async def async_validate_login(self) -> str:
        """Validate credentials and return the account MSISDN."""
        await self._async_login()
        mfa_info = await self._async_graphql("mfaInfo", MFA_INFO_QUERY)
        self._validate_mfa_info(mfa_info)
        msisdn = mfa_info.get("mfaInfo", {}).get("msisdn")
        if not msisdn:
            raise SimonMobileApiError("SIMon mobile returned no account number")
        return str(msisdn)

    async def async_get_data(self) -> SimonMobileData:
        """Fetch and normalize account and consumption data."""
        mfa_info, consumptions = await asyncio.gather(
            self._async_graphql("mfaInfo", MFA_INFO_QUERY),
            self._async_graphql("consumptions", CONSUMPTIONS_QUERY),
        )
        self._validate_mfa_info(mfa_info)

        msisdn = str(mfa_info.get("mfaInfo", {}).get("msisdn", self._username))
        details = consumptions.get("consumptions", {}).get(
            "detailedConsumptions", []
        )
        return SimonMobileData(
            msisdn=msisdn,
            packages=[self._parse_package(item) for item in details],
        )

    async def _async_graphql(
        self, operation_name: str, query: str
    ) -> dict[str, Any]:
        """Run an authenticated GraphQL query."""
        await self._async_ensure_token()
        response = await self._async_request(
            GRAPHQL_URL,
            {
                "operationName": operation_name,
                "variables": {},
                "query": query,
            },
            bearer_token=self._access_token,
        )

        if response.status == 401:
            async with self._auth_lock:
                self._access_token_valid_until = 0
                await self._async_authenticate()
            response = await self._async_request(
                GRAPHQL_URL,
                {
                    "operationName": operation_name,
                    "variables": {},
                    "query": query,
                },
                bearer_token=self._access_token,
            )

        payload = await self._async_decode_response(response)
        if response.status in (401, 403):
            raise SimonMobileAuthError("SIMon mobile rejected the access token")
        if response.status >= 400:
            raise SimonMobileApiError(
                f"GraphQL request failed with HTTP {response.status}"
            )
        if errors := payload.get("errors"):
            raise SimonMobileApiError(f"GraphQL returned errors: {errors!r}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise SimonMobileApiError("GraphQL response contains no data")
        return data

    async def _async_ensure_token(self) -> None:
        """Ensure a usable access token exists."""
        if self._access_token and monotonic() < self._access_token_valid_until:
            return
        async with self._auth_lock:
            if self._access_token and monotonic() < self._access_token_valid_until:
                return
            await self._async_authenticate()

    async def _async_authenticate(self) -> None:
        """Refresh the token, falling back to a password login."""
        if self._refresh_token:
            try:
                await self._async_refresh()
                return
            except SimonMobileAuthError:
                self._access_token = None
                self._refresh_token = None
        await self._async_login()

    async def _async_login(self) -> None:
        """Authenticate with username and password."""
        response = await self._async_request(
            TOKEN_URL,
            {
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": self._username,
                "password": self._password,
            },
        )
        await self._async_process_token_response(response)

    async def _async_refresh(self) -> None:
        """Refresh the OAuth access token."""
        response = await self._async_request(
            TOKEN_URL,
            {
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": self._refresh_token,
            },
        )
        await self._async_process_token_response(response)

    async def _async_process_token_response(self, response: ClientResponse) -> None:
        """Validate and store an OAuth token response in memory."""
        payload = await self._async_decode_response(response)
        if payload.get("needs_multifactor_authentication"):
            raise SimonMobileMfaRequired("Multifactor authentication is required")
        if response.status in (400, 401, 403):
            raise SimonMobileAuthError("Invalid SIMon mobile credentials or token")
        if response.status >= 400:
            raise SimonMobileApiError(
                f"Token request failed with HTTP {response.status}"
            )
        access_token = payload.get("access_token")
        if not access_token:
            raise SimonMobileAuthError("Token response contains no access token")

        self._access_token = str(access_token)
        if refresh_token := payload.get("refresh_token"):
            self._refresh_token = str(refresh_token)
        expires_in = max(60, int(payload.get("expires_in", 3600)))
        self._access_token_valid_until = monotonic() + expires_in - 60

    async def _async_request(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        bearer_token: str | None = None,
    ) -> ClientResponse:
        """POST JSON to the API."""
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-Transaction": self._transaction_id(),
        }
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        try:
            async with asyncio.timeout(30):
                return await self._session.post(url, json=payload, headers=headers)
        except (TimeoutError, ClientError) as err:
            raise SimonMobileConnectionError(
                "Unable to communicate with SIMon mobile"
            ) from err

    @staticmethod
    async def _async_decode_response(response: ClientResponse) -> dict[str, Any]:
        """Decode a JSON response and map malformed responses."""
        try:
            payload = await response.json(content_type=None)
        except (ValueError, ClientError) as err:
            raise SimonMobileApiError("SIMon mobile returned invalid JSON") from err
        if not isinstance(payload, dict):
            raise SimonMobileApiError("SIMon mobile returned an unexpected response")
        return payload

    @staticmethod
    def _validate_mfa_info(data: dict[str, Any]) -> None:
        """Validate account and MFA state."""
        info = data.get("mfaInfo") or {}
        if info.get("locked") or info.get("loginPossible") is False:
            raise SimonMobileAccountLocked("The SIMon mobile account is locked")
        if info.get("active"):
            active_mfas = info.get("activeMfas") or []
            if not any(item.get("authenticated") for item in active_mfas):
                raise SimonMobileMfaRequired(
                    "Multifactor authentication is active and not completed"
                )

    @staticmethod
    def _parse_package(item: dict[str, Any]) -> ConsumptionPackage:
        """Normalize a detailed consumption package."""
        consumptions: list[Consumption] = []
        for raw in item.get("consumptions", []):
            expiration_date = None
            if value := raw.get("expirationDate"):
                try:
                    expiration_date = datetime.fromisoformat(str(value))
                except ValueError:
                    expiration_date = None
            consumptions.append(
                Consumption(
                    consumed=float(raw.get("consumed", 0)),
                    expiration_date=expiration_date,
                    left=float(raw.get("left", 0)),
                    maximum=float(raw.get("max", 0)),
                    type=str(raw.get("type", "UNKNOWN")),
                    unit=str(raw.get("unit", "")),
                    expires_within_current_period=bool(
                        raw.get("expiresWithinCurrentPeriod", False)
                    ),
                    display_separately=bool(raw.get("displaySeparately", False)),
                )
            )
        return ConsumptionPackage(
            id=str(item.get("id", "unknown")),
            name=str(item.get("name", "SIMon mobile")),
            package_type=str(item.get("type", "Unknown")),
            consumptions=consumptions,
        )

    @staticmethod
    def _transaction_id() -> str:
        """Generate a fresh client transaction identifier."""
        alphabet = string.ascii_lowercase + string.digits
        random_part = "".join(secrets.choice(alphabet) for _ in range(19))
        return f"ms{random_part[:8]}-{random_part[8:]}"
