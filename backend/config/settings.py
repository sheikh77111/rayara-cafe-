import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env file if present
for _env_candidate in [BASE_DIR.parent / '.env', BASE_DIR / '.env']:
    if _env_candidate.exists():
        with open(_env_candidate, 'r', encoding='utf-8') as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
        break
SECRET_KEY = os.getenv('SECRET_KEY', 'unsafe-local-development-key')
DEBUG = os.getenv('DEBUG', '1') == '1'
ALLOWED_HOSTS = ['*'] if DEBUG else [x.strip() for x in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if x.strip()]
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'core',
    'pos',
]
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','corsheaders.middleware.CorsMiddleware',
 'django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware',
 'django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware',
 'django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF='config.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
WSGI_APPLICATION='config.wsgi.application'

try:
    import dj_database_url
    DATABASES={'default': dj_database_url.config(default='sqlite:///'+str(BASE_DIR/'db.sqlite3'), conn_max_age=600)}
except ImportError:
    db_url = os.getenv('DATABASE_URL')
    if db_url and (db_url.startswith('postgres://') or db_url.startswith('postgresql://')):
        import urllib.parse
        url = urllib.parse.urlparse(db_url)
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': url.path[1:],
                'USER': url.username,
                'PASSWORD': url.password,
                'HOST': url.hostname,
                'PORT': url.port or 5432,
            }
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': str(BASE_DIR / 'db.sqlite3'),
            }
        }

AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='en-us'; TIME_ZONE='Asia/Kolkata'; USE_I18N=True; USE_TZ=True
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    x.strip() for x in os.getenv(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:3002,http://127.0.0.1:3003'
    ).split(',') if x.strip()
]

# CSRF Trusted Origins (Allows frontend Next.js on any port e.g. 3000, 3001, 3002, 3003 or local LAN IP)
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:3001',
    'http://localhost:3002',
    'http://localhost:3003',
    'http://localhost:3004',
    'http://localhost:3005',
    'http://localhost:8000',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:3001',
    'http://127.0.0.1:3002',
    'http://127.0.0.1:3003',
    'http://127.0.0.1:3004',
    'http://127.0.0.1:3005',
    'http://127.0.0.1:8000',
]
_env_csrf = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if _env_csrf:
    CSRF_TRUSTED_ORIGINS.extend([x.strip() for x in _env_csrf.split(',') if x.strip()])

# Dynamically trust local LAN IP for staff tablet and mobile dining QR scans
import socket
try:
    _host_ip = socket.gethostbyname(socket.gethostname())
    if _host_ip and _host_ip != '127.0.0.1':
        for _p in (3000, 3001, 3002, 3003, 3004, 3005, 8000):
            CSRF_TRUSTED_ORIGINS.append(f'http://{_host_ip}:{_p}')
except Exception:
    pass

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'config.authentication.CsrfExemptSessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '120/hour'}
}

# Resend Email Configuration
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '').strip()
RESEND_FROM_EMAIL = os.getenv('RESEND_FROM_EMAIL', 'Rayara Café <onboarding@resend.dev>').strip()

# Email Configuration (Fallback via SMTP / Console)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '').strip()
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '').strip()

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', '1') == '1'
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', f'Rayara Café <{EMAIL_HOST_USER}>')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'Rayara Café <noreply@rayaracafe.com>'

