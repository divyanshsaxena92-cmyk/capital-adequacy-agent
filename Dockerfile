# Capital Adequacy Agent - server image (offline app; outbound access only to *.rbi.org.in for RBI downloads)
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Shared RBI knowledge base and imported data live here - mount a persistent volume so they survive restarts
ENV CAPITAL_AGENT_STORE=/data/store
VOLUME ["/data"]
EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
