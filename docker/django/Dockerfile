FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd && rm -rf /var/lib/apt/lists/*
COPY requirements /requirements
ARG REQUIREMENTS_FILE=development.txt
RUN pip install --no-cache-dir -r /requirements/${REQUIREMENTS_FILE}
COPY docker/django/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
COPY backend /app
RUN addgroup --system app && adduser --system --ingroup app --home /app app \
    && chown -R app:app /app
USER app
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
