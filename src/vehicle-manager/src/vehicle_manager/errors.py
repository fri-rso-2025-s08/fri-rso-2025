from fastapi_problem.error import StatusProblem
from fastapi_problem.handler import new_exception_handler


class TokenExpiredError(StatusProblem):
    status = 401
    title = "Token has expired."


class TokenVerificationFailedError(StatusProblem):
    status = 401
    title = "Token verification failed."


class WrongTenantError(StatusProblem):
    status = 401
    title = "User is not authorized to use this tenant."


class VehicleNotFoundError(StatusProblem):
    status = 404
    title = "Vehicle not found."


eh = new_exception_handler()
