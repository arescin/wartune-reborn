# Dockerfile para o Portal Web Wartune Reborn (PHP 8.2 / Apache)
FROM php:8.2-apache

# Instalar dependências de sistema para extensões do banco de dados
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libsqlite3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar extensões PDO necessárias (PostgreSQL, MySQL, SQLite)
RUN docker-php-ext-install pdo pdo_pgsql pdo_mysql pdo_sqlite

# Ativar módulos do Apache
RUN a2enmod rewrite headers

# Configuração do Apache
COPY docker/portal/apache.conf /etc/apache2/sites-available/000-default.conf

# Copiar arquivos da aplicação
COPY "Wartune Reborn Portal v1/" /var/www/html/

# Ajustar permissões para o www-data
RUN chown -R www-data:www-data /var/www/html && \
    chmod -R 755 /var/www/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

CMD ["apache2-foreground"]
