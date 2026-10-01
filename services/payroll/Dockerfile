FROM python:3.13-slim

WORKDIR /app

# Copy shared library first and install in editable mode
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Copy payroll service requirements and install
COPY services/payroll/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy payroll service app code
COPY services/payroll/app /app/services/payroll/app

EXPOSE 8004

CMD ["uvicorn", "services.payroll.app.main:app", "--host", "0.0.0.0", "--port", "8004"]
