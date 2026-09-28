"""
NEO Demo Veri Oluşturucu
Mercedes staj başvurusu için profesyonel demo veriler
"""

from pathlib import Path

# Demo klasörünü oluştur
demo_dir = Path.home() / "NeoProjects" / "Mercedes_Demo_Projesi"
demo_dir.mkdir(parents=True, exist_ok=True)

# 1. CV Özeti
cv_content = """# Steud - Bilgisayar Mühendisliği Öğrencisi

## Kişisel Bilgiler
- **Hedef:** Mercedes-Benz'te Yazılım/Gömülü Sistemler Stajyeri
- **Eğitim:** Ostim Teknik Üniversitesi, Bilgisayar Mühendisliği (4. Sınıf)
- **Diller:** 
  - Python (İleri seviye)
  - C/C++ (Orta seviye, STM32 projeleri)
  - JavaScript/TypeScript (Temel)
  - Almanca (A2/B1)
  - İngilizce (B2)

## Teknik Yetenekler
- Gömülü Sistemler (STM32, ARM Cortex-M)
- Local-first AI uygulamaları
- Vector veritabanları (ChromaDB)
- LLM entegrasyonu (Ollama, Qwen)
- Privacy-focused sistem tasarımı

## Projeler
1. **NEO** - Local Knowledge Assistant (Python, ChromaDB, Ollama)
2. **STM32 Sıcaklık Sensörü** - Gömülü sistem projesi (C)
3. **Akıllı Ev Otomasyonu** - IoT projesi (Python, C++)

## İlgi Alanları
- Otonom sürüş sistemleri
- Yerel yapay zeka modelleri
- Gizlilik odaklı yazılım geliştirme
- MB.OS ve araç içi sistemler
"""
(demo_dir / "cv_ozet.md").write_text(cv_content, encoding="utf-8")

# 2. Python Proje Kodu
python_content = '''import ollama
import chromadb
from pathlib import Path

# NEO: Privacy-First Local Knowledge Assistant
# Bu modül, geliştiricinin kod tabanını yerel olarak indeksler.
# Mercedes MB.OS projeleri için yerel ve güvenli AI çözümleri araştırılmaktadır.

# Özellikler:
# - Tamamen lokal çalışır (buluta veri gitmez)
# - Semantic search (anlamsal arama)
# - Hibrit arama (keyword + vector)
# - Türkçe ve İngilizce destekli

def search_local_knowledge(query: str, top_k: int = 5):
    """Yerel bilgi tabanında arama yapar."""
    # Nomic-embed-text ile vektörleştirme
    response = ollama.embeddings(model="nomic-embed-text", prompt=query)
    query_embedding = response['embedding']
    
    # ChromaDB'de benzer dokümanları bul
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    
    return results

def generate_response(query: str, context: str):
    """Bağlam kullanarak yanıt üretir."""
    system_prompt = "Sen NEO'sun, yardımcı bir yerel yapay zeka asistanısın."
    system_prompt += f"Aşağıdaki bağlamı kullanarak soruyu cevapla: {context}"
    system_prompt += f"Soru: {query}"

    response = ollama.chat(
        model="qwen2.5:3b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
    )
    
    return response['message']['content']

# Veritabanı bağlantısı
DB_PATH = str(Path.home() / "NeoProjects" / "neo_db")
chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection = chroma_client.get_or_create_collection(name="developer_knowledge")

print("NEO Motoru Başlatılıyor... Gizlilik öncelikli.")
print("Local AI ile güvenli bilgi yönetimi.")
'''
(demo_dir / "neo_motor.py").write_text(python_content, encoding="utf-8")

# 3. STM32 C Kodu
c_content = '''/*
 * STM32F4 Discovery - Sıcaklık Sensörü Okuma
 * NEO Projesi donanım entegrasyon testi
 * Yazan: Steud
 * Hedef: Mercedes staj başvurusu için gömülü sistemler deneyimi
 */

#include "stm32f4xx.h"
#include "main.h"
#include <stdio.h>

// Sıcaklık sensörü pin tanımlamaları
#define TEMP_SENSOR_GPIO GPIOA
#define TEMP_SENSOR_PIN GPIO_PIN_0

// Sıcaklık eşik değerleri
#define CRITICAL_TEMP 80.0f
#define WARNING_TEMP 70.0f
#define NORMAL_TEMP 60.0f

void SystemClock_Config(void);
void MX_GPIO_Init(void);
float Read_Temperature_Sensor(void);
void Trigger_Cooling_System(void);
void Send_Alert(float temperature);

int main(void) {
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    
    float temperature = 0.0f;
    
    printf("STM32 Sıcaklık İzleme Sistemi Başlatıldı\\n");
    printf("Kritik Sıcaklık: %.1f°C\\n", CRITICAL_TEMP);
    
    while (1) {
        // Sensör verisini oku
        temperature = Read_Temperature_Sensor();
        
        printf("Mevcut Sıcaklık: %.1f°C\\n", temperature);
        
        // Sıcaklık kontrolü
        if (temperature > CRITICAL_TEMP) {
            // Kritik sıcaklık - soğutma sistemini tetikle
            Trigger_Cooling_System();
            Send_Alert(temperature);
            printf("UYARI: Kritik sıcaklık! Soğutma sistemi aktif.\\n");
        } else if (temperature > WARNING_TEMP) {
            // Uyarı seviyesi
            printf("DİKKAT: Sıcaklık yükseliyor.\\n");
        } else {
            // Normal seviye
            printf("Durum: Normal\\n");
        }
        
        // 1 saniye bekle
        HAL_Delay(1000);
    }
}

float Read_Temperature_Sensor(void) {
    // ADC okuması (simülasyon)
    // Gerçek uygulamada ADC dönüşümü yapılacak
    return 25.0f + (rand() % 100) / 10.0f;
}

void Trigger_Cooling_System(void) {
    // Soğutma sistemini aktif et
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_1, GPIO_PIN_SET);
}

void Send_Alert(float temperature) {
    // Alert gönderme (UART, SPI, vb.)
    printf("ALERT: Sıcaklık %.1f°C - Kritik seviye!\\n", temperature);
}
'''
(demo_dir / "stm32_sicaklik_sensoru.c").write_text(c_content, encoding="utf-8")

print("✅ Demo verileri başarıyla oluşturuldu!")
print(f" Konum: {demo_dir}")
print(f"📄 Oluşturulan dosyalar:")
print(f"   - cv_ozet.md")
print(f"   - neo_motor.py")
print(f"   - stm32_sicaklik_sensoru.c")