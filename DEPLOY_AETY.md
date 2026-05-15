# Размещение проекта AETY на Ubuntu 22.04

## 1. DNS домена

В панели домена должны быть записи:

```text
A     @      IP_СЕРВЕРА
A     www    IP_СЕРВЕРА
```

Проверка:

```bash
nslookup aety.ru 8.8.8.8
nslookup www.aety.ru 8.8.8.8
```

## 2. Пакеты сервера

```bash
apt update && apt upgrade -y
apt install -y nginx postgresql postgresql-contrib git build-essential libpq-dev curl software-properties-common
add-apt-repository ppa:deadsnakes/ppa -y
apt update
apt install -y python3.12 python3.12-venv python3.12-dev
```

## 3. База данных

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE dbae;
CREATE USER aety_user WITH PASSWORD 'ЗАМЕНИ_ПАРОЛЬ';
GRANT ALL PRIVILEGES ON DATABASE dbae TO aety_user;
\c dbae
GRANT ALL ON SCHEMA public TO aety_user;
\q
```

## 4. Проект

```bash
mkdir -p /var/www/aety
cd /var/www/aety
```

Загрузи сюда проект через Git или WinSCP.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

После загрузки проекта выдай права пользователю, от которого будет работать сервис:

```bash
chown -R www-data:www-data /var/www/aety
```

## 5. Переменные окружения

```bash
cp .env.example .env
nano .env
```

Обязательно поменять:

```text
SECRET_KEY
DB_PASSWORD
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
DEFAULT_FROM_EMAIL
```

## 6. Миграции, статика и администратор

```bash
source /var/www/aety/.venv/bin/activate
python manage.py migrate
python manage.py collectstatic
python manage.py createsuperuser
```

## 7. Gunicorn через systemd

```bash
cp deploy/aety.service /etc/systemd/system/aety.service
systemctl daemon-reload
systemctl start aety
systemctl enable aety
systemctl status aety
```

## 8. Nginx

```bash
cp deploy/nginx-aety.conf /etc/nginx/sites-available/aety
ln -s /etc/nginx/sites-available/aety /etc/nginx/sites-enabled/aety
nginx -t
systemctl restart nginx
```

## 9. HTTPS

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d aety.ru -d www.aety.ru
```

После выпуска сертификата сайт должен открываться по адресу:

```text
https://aety.ru/
```

## 10. Проверка ошибок

```bash
systemctl status aety
journalctl -u aety -f
systemctl status nginx
tail -f /var/log/nginx/error.log
```
