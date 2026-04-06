"""Custom exception hierarchy for the HVAC CRM platform.

Все доменные исключения наследуются от HVACBaseError и перехватываются
единым обработчиком на уровне FastAPI middleware.
"""


class HVACBaseError(Exception):
    """Root exception for all application-level errors.

    Атрибуты:
        message: Человекочитаемое описание ошибки.
        code: Машиночитаемый код ошибки.
        status_code: HTTP статус-код для ответа.
        details: Дополнительные данные об ошибке.
    """

    def __init__(
        self,
        message: str = "Internal error",
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: dict | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(HVACBaseError):
    """Raised when a requested entity does not exist.

    Атрибуты:
        entity: Тип сущности (например, "Task", "Client").
        entity_id: Идентификатор запрошенной сущности.
    """

    def __init__(self, entity: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity} with id '{entity_id}' not found",
            code="NOT_FOUND",
            status_code=404,
            details={"entity": entity, "entity_id": entity_id},
        )


class ValidationError(HVACBaseError):
    """Raised when input data fails domain validation.

    Атрибуты:
        field: Поле, не прошедшее валидацию.
        reason: Причина отклонения.
    """

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(
            message=f"Validation failed for '{field}': {reason}",
            code="VALIDATION_ERROR",
            status_code=422,
            details={"field": field, "reason": reason},
        )


class WorkflowTransitionError(HVACBaseError):
    """Raised when a task status transition is not allowed.

    Атрибуты:
        task_id: ID задачи.
        from_status: Текущий статус.
        to_status: Запрошенный статус.
        reason: Причина отклонения перехода.
    """

    def __init__(self, task_id: str, from_status: str, to_status: str, reason: str) -> None:
        super().__init__(
            message=f"Transition '{from_status}' -> '{to_status}' denied for task '{task_id}': {reason}",
            code="WORKFLOW_TRANSITION_DENIED",
            status_code=409,
            details={
                "task_id": task_id,
                "from_status": from_status,
                "to_status": to_status,
                "reason": reason,
            },
        )


class AuthorizationError(HVACBaseError):
    """Raised when the current user lacks required permissions.

    Атрибуты:
        required_role: Требуемая роль.
        action: Действие, для которого не хватает прав.
    """

    def __init__(self, required_role: str, action: str) -> None:
        super().__init__(
            message=f"Role '{required_role}' required for action '{action}'",
            code="AUTHORIZATION_ERROR",
            status_code=403,
            details={"required_role": required_role, "action": action},
        )


class WarehouseInsufficientStockError(HVACBaseError):
    """Raised when warehouse stock is insufficient for the operation.

    Атрибуты:
        item_id: ID складского товара.
        requested: Запрошенное количество.
        available: Доступное количество.
    """

    def __init__(self, item_id: str, requested: float, available: float) -> None:
        super().__init__(
            message=f"Insufficient stock for item '{item_id}': requested {requested}, available {available}",
            code="INSUFFICIENT_STOCK",
            status_code=409,
            details={"item_id": item_id, "requested": requested, "available": available},
        )


class DuplicateError(HVACBaseError):
    """Raised when attempting to create a duplicate entity.

    Атрибуты:
        entity: Тип сущности.
        field: Поле с дубликатом.
        value: Дублирующееся значение.
    """

    def __init__(self, entity: str, field: str, value: str) -> None:
        super().__init__(
            message=f"{entity} with {field}='{value}' already exists",
            code="DUPLICATE_ENTITY",
            status_code=409,
            details={"entity": entity, "field": field, "value": value},
        )


class ExternalServiceError(HVACBaseError):
    """Raised when an external service call fails.

    Атрибуты:
        service: Имя внешнего сервиса.
        operation: Выполняемая операция.
    """

    def __init__(self, service: str, operation: str, detail: str = "") -> None:
        super().__init__(
            message=f"External service '{service}' failed on '{operation}': {detail}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details={"service": service, "operation": operation},
        )
