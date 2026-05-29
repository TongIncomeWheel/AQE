# Hugging Face Spaces -- Docker SDK runtime for AQE.
# Builds on python:3.11-slim. Installs requirements, copies the whole project,
# launches Streamlit pointing at streamlit_app.py (the cloud entrypoint).

FROM python:3.11-slim

WORKDIR /app

# System deps: build-essential for any wheel that compiles, curl for the
# healthcheck, git in case any runtime install pulls from a git ref.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# Cache pip layer
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of the project. `.dockerignore` keeps caches/secrets out.
COPY . ./

# HF runs the container as a non-root user; ensure the app dir is writable so
# panel/score parquets can be (re)built into AQE_DATA_DIR at runtime.
RUN mkdir -p /app/data /app/output && chmod -R 777 /app/data /app/output

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Use the project-root streamlit_app.py (it bridges st.secrets -> os.environ
# and then runs src/ui/1_Scanner.py via runpy).
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0", \
            "--server.headless=true", \
            "--browser.gatherUsageStats=false"]
