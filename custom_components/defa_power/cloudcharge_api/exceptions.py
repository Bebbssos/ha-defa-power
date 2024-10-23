"""Exceptions for the CloudCharge API."""

from enum import Enum


class CloudChargeAPIError(Exception):
    """Base exception for CloudCharge API errors."""


class CloudChargeAuthError(CloudChargeAPIError):
    """Exception for authentication errors."""


class CloudChargeRequestError(CloudChargeAPIError):
    """Exception for general request errors."""


class CloudChargeNotLoggedInError(CloudChargeAPIError):
    """Exception for calling a method that requires login when not logged in."""


class CloudChargeBadRequestErrorType(Enum):
    """Enum for known CloudCharge error types."""

    INVALID_PHONE_NUMBER = "Invalid phone number"
    UNKNOWN = "unknown"


class CloudChargeBadRequestError(CloudChargeAPIError):
    """Exception for bad request errors."""

    def __init__(self, raw_message: str):
        """Initialize the exception."""
        self.raw_message = raw_message
        self.error_type = self.__map_error_type(raw_message)

    def __map_error_type(self, raw_message: str) -> CloudChargeBadRequestErrorType:
        """Map raw message to CloudChargeBadRequestErrorType."""
        try:
            return CloudChargeBadRequestErrorType(raw_message)
        except ValueError:
            return CloudChargeBadRequestErrorType.UNKNOWN


class CloudChargeForbiddenErrorType(Enum):
    """Enum for known CloudCharge error types."""

    INVALID_DEV_TOKEN = (
        'field "devToken" in request body did not match any existing developer key'
    )
    INVALID_LOGIN_CREDENTIALS = "Invalid login credentials."
    NO_LOGIN_ATTEMPTS_FOUND = "No loginAttempts found"
    UNKNOWN = "unknown"


class CloudChargeForbiddenError(CloudChargeAPIError):
    """Exception for bad request errors."""

    def __init__(self, raw_message: str):
        """Initialize the exception."""
        self.raw_message = raw_message
        self.error_type = self.__map_error_type(raw_message)

    def __map_error_type(self, raw_message: str) -> CloudChargeForbiddenErrorType:
        """Map raw message to CloudChargeForbiddenErrorType."""
        try:
            return CloudChargeForbiddenErrorType(raw_message)
        except ValueError:
            return CloudChargeForbiddenErrorType.UNKNOWN
