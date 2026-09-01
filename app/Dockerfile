FROM python:3.11-slim
WORKDIR /app

# Copy the shared module first (config.py depends on shared/constants.py)
COPY shared /shared

# Install dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code itself
COPY app/ .

CMD ["python", "main.py"]