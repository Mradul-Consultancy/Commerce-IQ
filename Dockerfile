FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DB_ENGINE=duckdb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python src/generate_data.py --scale small \
    && python src/init_db.py \
    && python src/load_data.py \
    && python src/create_views.py \
    && rm -f data/*.csv reports/*.csv

RUN chmod +x start.sh

EXPOSE 8000 8501

CMD ["./start.sh"]
