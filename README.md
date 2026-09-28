# 🧠 NEO - Local Knowledge Assistant

Privacy-first, tamamen lokal çalışan RAG (Retrieval-Augmented Generation) tabanlı geliştirici asistanı.

## ✨ Özellikler

- **Hibrit Arama**: Keyword + Vector search ile yüksek doğruluk
- **Lokal LLM**: Ollama + Qwen2.5 ile buluta veri göndermez
- **Hızlı**: Kısa sorgularda anında yanıt (fan dostu)
- **Türkçe Desteği**: Karakter normalizasyonu ve stemming
- **Akıllı Özellikler**: Kod tekrarı tespiti, mülakat modu, proje özeti

## 🚀 Kurulum

```bash
# 1. Sanal ortam oluştur
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate

# 2. Bağımlılıkları kur
pip install -r requirements.txt

# 3. Ollama'yı kur ve model çek
ollama pull qwen2.5:3b
ollama pull nomic-embed-text

# 4. Demo verileri oluştur
python create_demo_data.py
python indexer.py

# 5. Çalıştır
python neo_app.py
