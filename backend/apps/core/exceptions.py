from rest_framework.views import exception_handler
def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None and response.status_code >= 400:
        response.data = {"success": False, "message": "Validation failed." if response.status_code == 400 else "Request failed.", "errors": response.data}
    return response
