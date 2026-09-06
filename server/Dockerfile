FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt
COPY server /app/server
COPY cados/core /app/cados/core
COPY cados/models /app/cados/models
COPY cados/assets /app/cados/assets
RUN python -c "from server.app.main import create_app"
RUN useradd --uid 10001 --create-home cados
USER cados
CMD ["uvicorn", "server.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
