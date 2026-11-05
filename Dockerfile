FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Si no se incluyó modelos/modelo_anemia_rf.pkl real, se genera el modelo de RESPALDO sintético
# (no es el modelo de la tesis; ver README).
RUN python scripts/generar_modelo_respaldo.py
# Render inyecta $PORT; en local cae a 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
