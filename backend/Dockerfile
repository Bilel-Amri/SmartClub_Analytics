FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

ARG INSTALL_ML_DEPS=0

WORKDIR /app

COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -q -r requirements.txt && \
    if [ "$INSTALL_ML_DEPS" = "1" ]; then pip install --no-cache-dir -q -r requirements-ml.txt; fi

COPY . .

EXPOSE 8000
