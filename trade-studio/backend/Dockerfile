FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir 'gunicorn>=23,<24' \
    && useradd -u 10001 -m appuser && mkdir /data && chown appuser:appuser /data
COPY server.py email_gateway.py market.py onboarding.py phone_verification.py sms_gateway.py index.html wsgi.py ./
USER appuser
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "wsgi:app"]
