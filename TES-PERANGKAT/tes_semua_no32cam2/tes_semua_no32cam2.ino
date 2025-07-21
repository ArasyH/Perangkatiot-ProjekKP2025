#include <SPI.h>
#include <MFRC522.h>
#include <TFT_eSPI.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// WiFi credentials
const char* ssid     = "Aci2997";
const char* password = "arasyhemas";

// Flask endpoint
const char* serverUrl = "http://192.168.58.217:10000/ambiluid";

// RFID pin
#define RST_PIN    0
#define SS_PIN     5
MFRC522 rfid(SS_PIN, RST_PIN);

// LCD ST7789
TFT_eSPI tft = TFT_eSPI();

// Relay
#define RELAY1_PIN 25
#define RELAY2_PIN 26

void setup() {
  Serial.begin(115200);

  // Inisialisasi LCD awal
  tft.init();
  tft.setRotation(1);
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.drawString("Menghubungkan WiFi", 120, 120, 2);

  // Koneksi WiFi
  Serial.println("Menghubungkan ke WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  // Setelah berhasil konek
  String ip = WiFi.localIP().toString();
  Serial.println("\nWiFi Terhubung!");
  Serial.println("IP ESP32: " + ip);

  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_GREEN, TFT_BLACK);
  tft.drawString("WiFi Terhubung", 120, 100, 2);
  tft.drawString(ip, 120, 140, 2);
  delay(2000); // Tampilkan IP selama 2 detik

  // Inisialisasi Relay
  pinMode(RELAY1_PIN, OUTPUT);
  pinMode(RELAY2_PIN, OUTPUT);
  digitalWrite(RELAY1_PIN, LOW);
  digitalWrite(RELAY2_PIN, LOW);

  // Tampilkan pesan siap tempel kartu
  tft.fillScreen(TFT_NAVY);
  tft.setTextColor(TFT_WHITE);
  tft.drawString("Tempelkan Kartu", 120, 120, 4);

  delay(500);

  // Inisialisasi RFID
  SPI.begin();
  rfid.PCD_Init();
  Serial.println("RFID Reader siap.");
}

void loop() {
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    String uid = "";
    for (byte i = 0; i < rfid.uid.size; i++) {
      uid += (rfid.uid.uidByte[i] < 0x10 ? "0" : "");
      uid += String(rfid.uid.uidByte[i], HEX);
    }
    uid.toUpperCase();
    Serial.println("UID: " + uid);

    // Tampilkan UID di LCD
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_YELLOW, TFT_BLACK);
    tft.setTextDatum(MC_DATUM);
    tft.drawString("UID Terdeteksi:", 120, 100, 2);
    tft.drawString(uid, 120, 140, 4);

    // Kirim UID ke server Flask
    if (WiFi.status() == WL_CONNECTED) {
      // Menggunakan ArduinoJson untuk membuat JSON
      JsonDocument doc;
      doc["uid"] = uid;
      String jsonData;
      serializeJson(doc, jsonData);

      // Kirim request ke server
      WiFiClient client;
      HTTPClient http;
      http.begin(client, serverUrl);
      http.addHeader("Content-Type", "application/json");

      int httpResponseCode = http.POST(jsonData);

      // Cek respons dari server
      if (httpResponseCode == 200) { // Kode 200 berarti sukses
        String responsePayload = http.getString();
        Serial.println("Response dari server: " + responsePayload);

        // Parse respons JSON dari server
        JsonDocument responseDoc;
        DeserializationError error = deserializeJson(responseDoc, responsePayload);

        if (error) {
          Serial.print(F("deserializeJson() gagal: "));
          Serial.println(error.f_str());
          tft.drawString("Error Parsing", 120, 180, 2);
          delay(2000);
        } else {
          // Cek apakah status dari server adalah "success"
          if (String(responseDoc["status"]) == "success") {
            Serial.println("✅ Akses Diberikan!");
            tft.setTextColor(TFT_GREEN);
            tft.drawString("Akses Diberikan", 120, 180, 2);

            // Aktifkan relay karena akses diberikan
            digitalWrite(RELAY1_PIN, HIGH);
            digitalWrite(RELAY2_PIN, HIGH);
            delay(2000); // Relay aktif selama 2 detik
            digitalWrite(RELAY1_PIN, LOW);
            digitalWrite(RELAY2_PIN, LOW);

          } else {
            Serial.println("❌ Akses Ditolak oleh server.");
            tft.setTextColor(TFT_RED);
            tft.drawString("Akses Ditolak", 120, 180, 2);
            delay(2000);
          }
        }
      } else {
        Serial.println("Gagal terhubung ke server. Kode: " + String(httpResponseCode));
        tft.setTextColor(TFT_RED);
        tft.drawString("Error Koneksi", 120, 180, 2);
        delay(2000);
      }
      http.end();
    } else {
      Serial.println("WiFi tidak tersambung saat kirim UID.");
    }

    // Kembali ke layar awal setelah semua proses selesai
    tft.fillScreen(TFT_NAVY);
    tft.setTextColor(TFT_WHITE);
    tft.drawString("Tempelkan Kartu", 120, 120, 4);

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
  }
}