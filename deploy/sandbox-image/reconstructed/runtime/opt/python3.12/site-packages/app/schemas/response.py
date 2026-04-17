from typing import Optional, Any, Generic, TypeVar, List, Union
from pydantic import BaseModel, Field

T = TypeVar('T')


# Validation error detail model
class ValidationErrorDetail(BaseModel):
    """Model for individual validation error details"""

    location: List[Union[str, int]] = Field(
        description='Location of the error in the request (e.g., ["body", "field_name"])'
    )
    message: str = Field(description='Error message describing the validation issue')
    type: str = Field(description='Error type (e.g., "value_error.missing")')


# Validation error response model
class ValidationErrorResponse(BaseModel):
    """Response model for validation errors"""

    success: bool = Field(False, description='Always false for validation errors')
    message: str = Field(
        'Request data validation failed',
        description='General validation error message'
    )
    data: None = Field(None, description='Data is null for validation errors')
    errors: List[ValidationErrorDetail] = Field(
        description='List of validation error details'
    )


# Unified response model
class Response(BaseModel, Generic[T]):
    """Generic response model for API interface return results"""

    success: bool = Field(True, description='Whether the operation was successful')
    message: Optional[str] = Field(
        'Operation successful', description='Operation result message'
    )
    data: Optional[T] = Field(None, description='Data returned from the operation')

    # Shortcut method to create error response
    @classmethod
    def error(cls, message: str, data: Any = None) -> 'Response[Any]':
        """Create an error response instance"""
        return cls(success=False, message=message, data=data)
