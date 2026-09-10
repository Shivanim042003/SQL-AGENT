class RequestValidationError(ValueError):
    """Raised when a user request fails validation."""


MAX_QUESTION_LENGTH = 2000


def validate_question(question: str) -> str:
    """
    Validate and normalize a user question.

    Returns:
        Cleaned question.

    Raises:
        RequestValidationError:
            If the question is invalid.
    """

    if not isinstance(question, str):
        raise RequestValidationError(
            "Question must be a string."
        )

    question = question.strip()

    if not question:
        raise RequestValidationError(
            "Question cannot be empty."
        )

    if len(question) > MAX_QUESTION_LENGTH:
        raise RequestValidationError(
            f"Question exceeds the maximum length of "
            f"{MAX_QUESTION_LENGTH} characters."
        )

    return question