FROM python:3.13.11-slim AS runner

WORKDIR /app

COPY ./backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./backend/manage.py /app/manage.py
COPY ./backend/gunicorn_config.py /app/gunicorn_config.py
COPY ./backend/core /app/core
COPY ./backend/users /app/users
COPY ./backend/magicdocu /app/magicdocu

COPY ./docker/django/entrypoint.sh .
RUN chmod +x ./entrypoint.sh

EXPOSE 8000/tcp

COPY .env_prod /build/.env_prod
ENV ENV_FILE=/config/.env

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 
ENV DJANGO_DEBUG=False

VOLUME ["/uploads"]
VOLUME ["/config"]

RUN ln -s /uploads /app/uploads
EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh", "gunicorn"]
CMD ["--config", "gunicorn_config.py", "magicdocu.wsgi:application"]