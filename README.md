# Description


## Links
- /admin/
- /api/v1/docs/swagger/

# Run
## At server
```shell
export DOMAIN=example.com

# Issue SSL cert for ${DOMAIN}
docker compose -f .docker/compose.certbot.yml up   # Press ctrl + C

# Create minio license
open https://www.min.io/download  # Get license 
cat > .docker/minio/license

# Run services
docker compose -f .docker/compose.services.yml up -d --build
docker compose -f .docker/compose.services.yml exec s3 sh -c '
  mc alias set local http://127.0.0.1:9000 user pass-pass &&
  mc mb --ignore-existing local/main &&
  mc anonymous set download local/main
'

# Run back-end
cp .docker/.env.dev_prod .env  # Edit .env
docker compose -f .docker/compose.yml up -d --build
docker compose -f .docker/compose.services.yml restart nginx
docker compose -f .docker/compose.yml exec back sh -c "./manage.py migrate"
docker compose -f .docker/compose.yml exec back sh -c "./manage.py create_super_user"
docker compose -f .docker/compose.yml exec back sh -c "./manage.py collectstatic --noinput"

open ${DOMAIN}/admin/  # Login as admin:admin and change password at /admin/users/user/
```

## At local
```shell
docker compose -f .docker/compose.services.yml up -d pg s3 redis rabbit

pyenv virtualenv 3.14.1 payment_back
pyenv activate payment_back

pip install uv
uv install

pre-commit install

cp .docker/.env.debug .env

./manage.py migrate
./manage.py create_super_user
./manage.py collectstatic --noinput

./manage.py runserver localhost:8000
open http://localhost:8000/admin/  # Login as admin:admin

celery -A project worker -l DEBUG -P threads --concurrency=1
```

# Develop
```shell
./manage.py makemigrations

./manage.py test

./manage.py makemessages  -l en
./manage.py compilemessages -l en

./manage.py makemessages  -l ru
./manage.py compilemessages -l ru

ruff format
```
