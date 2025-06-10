FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi
COPY . .
CMD ["python", "course-management/manage.py", "runserver", "0.0.0.0:8000"]
