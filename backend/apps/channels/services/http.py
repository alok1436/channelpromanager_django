import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rest_framework.exceptions import APIException


class ProviderRequestError(APIException):
    status_code = 502
    default_detail = "The external provider request failed."


def post_form(url, data, headers=None, timeout=20):
    request = Request(
        url,
        data=urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", **(headers or {})},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        # Do not include response bodies: providers may echo sensitive values.
        raise ProviderRequestError() from exc

