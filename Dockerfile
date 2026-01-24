 
# STAGE 1: Base Image 

# Start from official Python 3.11 image (lightweight version) 
FROM python:3.11-slim 
 

# What is "FROM"? 

# - Tells Docker what base image to use 
# - python:3.11-slim = Python 3.11 pre-installed on minimal Linux 
# - "slim" = smaller size (150MB vs 1GB), faster downloads 
# - Alternative: python:3.11-alpine (even smaller but harder to use) 
 


# STAGE 2: Set Working Directory 

WORKDIR /app 
 
# What is "WORKDIR"? 

# - Creates /app folder inside container 
# - All future commands run from /app 
# - Like doing: mkdir /app && cd /app 
# - Your code will live in /app inside the container 
 





# STAGE 3: Install System Dependencies 
 
# Some Python packages need C compilers to install 
RUN apt-get update && apt-get install -y \ 
   gcc \ 
   postgresql-client \ 
   && rm -rf /var/lib/apt/lists/* 
 
# What is "RUN"? 

# - Executes commands while building image 
# - apt-get = Linux package manager (like pip for system tools) 
# - gcc = C compiler (needed for psycopg2) 
# - postgresql-client = PostgreSQL command-line tools 
# - rm -rf /var/lib/apt/lists/* = delete package cache (saves space) 
 
# Why install these?
# - psycopg2 needs gcc to compile 
# - postgresql-client useful for debugging database issues 
# - Without these, pip install psycopg2 fails! 
 



# STAGE 4: Install Python Dependencies 

# Copy requirements.txt FIRST (Docker caching optimization) 
COPY requirements.txt . 
 
# What is "COPY"? 
# - Copies file from your computer into container 
# - requirements.txt = source file (on your computer) 
# - . = destination (current directory in container = /app) 

 
# Why copy requirements.txt separately? 
# DOCKER CACHING MAGIC: 
# - Docker caches each step 
# - If requirements.txt doesn't change, Docker reuses cached layer 
# - If only code changes, Docker skips reinstalling packages 
# - Saves 2-3 minutes per rebuild! 
 
# Install Python packages 
RUN pip install --no-cache-dir -r requirements.txt 
 
# What is "pip install --no-cache-dir"? 
# - pip install = install Python packages 
# - --no-cache-dir = don't save pip cache (saves 100-200MB) 
# - -r requirements.txt = read package list from file 
 
# This takes 1-2 minutes first time, then cached 
 



# STAGE 5: Copy Application Code 

COPY . . 
 
# What is "COPY . ."? 
# - First . = everything in current folder (your computer) 
# - Second . = copy to current folder in container (/app) 
# - Copies: inventory_app.py, cli.py, helper_functions.py, etc. 
 
# Why copy code AFTER installing dependencies? 
# - Code changes frequently (you're developing) 
# - Dependencies rarely change 
# - Docker reuses cached dependency layer 
# - Only rebuilds code layer (fast!) 
 
 



# STAGE 6: Create Necessary Directories 

RUN mkdir -p data/backups exports 
 
# What is "mkdir -p"? 
# - mkdir = make directory 
# - -p = create parent directories if needed (no error if exists) 
# - Creates: /app/data, /app/data/backups, /app/exports 
 
# Why create these? 
# - Your code expects these folders to exist 
# - Prevents "FileNotFoundError: directory not found" errors 
# - Good practice for fresh deployments 
 



# ============================================================ 
# STAGE 7: Set Environment Variables 
# ============================================================ 
ENV PYTHONUNBUFFERED=1 
 
# What is "ENV"? 
# - Sets environment variable inside container 
# - PYTHONUNBUFFERED=1 = disable Python output buffering 
 
# Why PYTHONUNBUFFERED=1? 
# - Python normally buffers print() statements (waits to output) 
# - Buffering = you don't see logs immediately 
# - PYTHONUNBUFFERED=1 = see print() in real-time 
# - Critical for debugging in containers! 
 
# ============================================================ 
# STAGE 8: Expose Port 
# ============================================================ 
EXPOSE 8000 
 
# What is "EXPOSE"? 
# - Documents which port the app uses 
# - Doesn't actually open the port (that happens when running) 
# - Railway looks for this to know where to route traffic 
 
# Why port 8000? 
# - Industry standard for Python web apps 
# - Flask default is 5000, but we'll configure 8000 
# - Railway expects EXPOSE to be set 
 


# ============================================================ 
# STAGE 9: Define Default Command 
# ============================================================ 


#CMD python init_db.py && python app.py
CMD ["python", "app.py"]
 

 
# ============================================================ 
# SUMMARY: What this Dockerfile does 
# ============================================================ 
# 1. Starts with Python 3.11 on Linux 
# 2. Installs system tools (gcc, postgresql-client) 
# 3. Installs Python packages (pandas, flask, etc.) 
# 4. Copies your code 
# 5. Creates necessary folders 
# 6. Configures environment 
# 7. Documents port 8000 
# 8. Runs cli.py by default 
# 
# Result: Self-contained container with everything needed to run your app!