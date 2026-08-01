FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

# Install all deps EXCEPT sentence-transformers/torch (too heavy for free tier).
# Set USE_TFIDF=true on Render to use the lightweight TF-IDF fallback instead.
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn==0.30.0 \
    "langchain>=0.3.0" \
    "langchain-community>=0.3.0" \
    "langchain-openai>=0.2.0" \
    "langgraph>=0.2.0" \
    "faiss-cpu>=1.8.0" \
    "pdfplumber>=0.11.0" \
    "reportlab>=4.2.0" \
    "pandas>=2.2.0" \
    "numpy>=1.26.0" \
    "python-dotenv>=1.0.0" \
    "groq>=0.9.0" \
    "scikit-learn>=1.5.0"

# sentence-transformers (optional, requires torch ~2GB — skip on free tier)
# To enable: set USE_TFIDF=false and uncomment the line below
# RUN pip install --no-cache-dir "sentence-transformers>=3.0.0"

COPY . .

RUN python data/generate_sample_data.py

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
