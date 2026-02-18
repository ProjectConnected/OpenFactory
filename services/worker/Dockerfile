FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends     git make     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/common/openfactory_common /app/openfactory_common
COPY services/worker/openfactory_worker /app/openfactory_worker
COPY templates /templates

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["python","-m","openfactory_worker.worker"]
