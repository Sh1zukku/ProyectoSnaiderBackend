FROM python:3.13-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY snaiderbackend/requirements.txt .

RUN uv pip install --no-cache -r requirements.txt --system

COPY snaiderbackend/ .

EXPOSE 8000

CMD ["bash", "-lc", "python manage.py migrate && DJANGO_SUPERUSER_USERNAME=admin DJANGO_SUPERUSER_EMAIL=admin@example.com DJANGO_SUPERUSER_PASSWORD=Admin123! python create_superuser.py && python manage.py runserver 0.0.0.0:8000"]
