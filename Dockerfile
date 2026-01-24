# STAGE 1: Base Image
FROM python:3.11-slim

# STAGE 2: Set Working Directory
WORKDIR /app

# STAGE 3: Install System Dependencies
RUN apt-get update && apt-get install -y \
   gcc \
   postgresql-client \
   && rm -rf /var/lib/apt/lists/*

# STAGE 4: Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# STAGE 5: Copy Application Code
COPY . .

# STAGE 6: Create Necessary Directories
RUN mkdir -p data/backups exports

# STAGE 7: Set Environment Variables
ENV PYTHONUNBUFFERED=1

# STAGE 8: Expose Port
EXPOSE 8000

# STAGE 9: Initialize database AND run app
# Create a startup script that initializes DB then starts app
RUN echo '#!/bin/bash\npython init_db.py\npython app.py' > /app/start.sh && \
    chmod +x /app/start.sh

CMD ["/app/start.sh"]
