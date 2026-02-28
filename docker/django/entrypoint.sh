#!/bin/sh

if [ ! -f "/config/.env" ]; then
    cp /build/.env_prod /config/.env
fi

grep -wq "DJANGO_SECRET_KEY" /config/.env
if [ $? -ne 0 ]; then 
    NEWKEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
    printf "DJANGO_SECRET_KEY=%s\n" $NEWKEY >> /config/.env
fi

python manage.py migrate
if [ $? -ne 0 ]; then
    echo "Failed to run database migrations!"
    exit 1
fi

celery -A magicdocu worker --loglevel=info &

exec "$@"