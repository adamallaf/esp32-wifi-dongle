#include <WiFi.h>

volatile byte msg_id;

struct __attribute__((packed)) APInfo {
  const byte bssid[6];
  const int rssi;
  const int channel;
  const short encType;
  const char ssid[32];
};

int n = 0;

void setup() {
  msg_id = 0;
  byte msg[8] = { 2, msg_id, 0xBB, 1, 0xAA, 0, 0, 0 };
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  delay(10);
  digitalWrite(LED_BUILTIN, LOW);
  delay(10);
  digitalWrite(LED_BUILTIN, HIGH);
  delay(10);
  digitalWrite(LED_BUILTIN, LOW);
  delay(10);
  digitalWrite(LED_BUILTIN, HIGH);
  delay(10);
  digitalWrite(LED_BUILTIN, LOW);

  Serial.begin(115200 << 2);
  while (Serial.available() < 1)
    ;
  unsigned short crc = crc16(*(&msg) + 1, 4);
  msg[5] = crc;
  msg[6] = crc >> 8;
  digitalWrite(LED_BUILTIN, HIGH);
  Serial.write(msg, 7);
  // Serial.flush();
  digitalWrite(LED_BUILTIN, LOW);
}

void loop() {
  String ssid;
  String password;
  while (Serial.available() > 0) {
    unsigned int length = 0;
    char in_byte = Serial.read();
    if (in_byte == 0x02) {
      byte id = Serial.read();
      in_byte = Serial.read();
      if (in_byte != 0xA0) break;
      length = Serial.read();  // length
      if (length == 0x82) {
        length = ((unsigned int)(Serial.read()) << 8) + Serial.read();
      }
      byte ack[8] = { 6, id, in_byte, 0, 0, 0, 0, 0 };
      unsigned short crcs = crc16(*(&ack) + 1, 2);
      ack[3] = crcs;
      ack[4] = crcs >> 8;
      for (int i = 0; i < length; i++) {
        byte d = Serial.read();
        switch (d) {
          case 1:
            n = 1 - Serial.read();
            // unsigned short xx = Serial.read() + ((unsigned short)(Serial.read()) << 8);
            digitalWrite(LED_BUILTIN, n);
            Serial.write(ack, 5);
            break;
          case 0xF0:
            Serial.write(ack, 5);
            scan_networks();
            break;
          case 0xF2: /* connect wifi */
            Serial.write(ack, 5);
            ssid = Serial.readStringUntil(0);
            password = Serial.readStringUntil(0);
            i += ssid.length() + password.length() + 10;
            wifi_connect(ssid.c_str(), password.c_str());
            break;
          case 0xF4: /* disconnect wifi */
            Serial.write(ack, 5);
            wifi_disconnect();
            break;
          case 'A':
            ack[0] = 2;
            ack[1] = msg_id++;
            ack[2] = 0xBB;
            ack[3] = 1;
            ack[4] = 0xAA;
            crcs = crc16(*(&ack) + 1, 4);
            ack[5] = crcs;
            ack[6] = crcs >> 8;
            Serial.write(ack, 7);
            break;
          default:
            break;
        }
      }
      /* CRC16 */
      Serial.read();
      Serial.read();
      Serial.flush();
    }
    in_byte = 0;
  }
}

unsigned short crc16(const byte *msg, unsigned int msg_size) {
  return crc16(msg, msg_size, 0x5725);
}

unsigned short crc16(const byte *msg, unsigned int msg_size, unsigned short icrc) {
  unsigned short crc = icrc;
  for (int i = 0; i < msg_size; i += 2) {
    crc ^= (unsigned short)(msg[i] << 8) + msg[i + 1];
  }
  return crc;
}

void scan_networks() {
  // WiFi.scanNetworks will return the number of networks found.
  int n = WiFi.scanNetworks(false, true);
  if (n == 0) {
    /* no networks */
    byte msg[10] = { 2, 0, 0xA1, 2, 0xF0, 0, 0, 0, 0, 0 };
    unsigned short crc = crc16(*(&msg) + 1, 5);
    msg[6] = crc;
    msg[7] = crc >> 8;
    Serial.write(msg, 8);
  } else {
    byte msg[10] = { 2, 0, 0xA1, 2, 0xF0, n & 0xFF, 0, 0, 0, 0 };
    unsigned short crc = crc16(*(&msg) + 1, 5);
    msg[6] = crc;
    msg[7] = crc >> 8;
    Serial.write(msg, 8);
    for (int i = 0; i < n; ++i) {
      APInfo ap = {
        { 0, 0, 0, 0, 0, 0 },
        WiFi.RSSI(i),
        WiFi.channel(i),
        (unsigned short)WiFi.encryptionType(i),
        { 0 },
      };
      const char *ssid = WiFi.SSID(i).c_str();
      memcpy((void *)ap.bssid, WiFi.BSSID(i), 6);
      memcpy((void *)ap.ssid, ssid, strlen(ssid));

      const byte *ptr = (const byte *)(&ap);
      int msg_len = 16 + strlen(ssid);
      /* id, type, length, cmd*/
      byte frame[4] = { 0, 0xA1, msg_len + 2, 0xF1 };
      unsigned short msg_crc = crc16(ptr, msg_len, crc16(frame, 4));
      Serial.write(0x02);
      Serial.write(frame, 4);
      for (int j = 0; j < msg_len; j++) {
        Serial.write(*ptr++);
      }
      Serial.write('\0');
      Serial.write(msg_crc & 0xFF);
      Serial.write(msg_crc >> 8);
    }
  }

  WiFi.scanDelete();
}

void wifi_connect(const char *ssid, const char *password) {
  if (WiFi.status() == WL_CONNECTED) {
    WiFi.disconnect(false, true);
  }
  WiFi.begin(ssid, password);
  int i = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    if (i++ > 55) {
      WiFi.disconnect(false, true);
      byte msg[10] = { 2, 0, 0xA1, 2, 0xF3, WiFi.status(), 0, 0, 0, 0 };
      unsigned short crc = crc16(*(&msg) + 1, 5);
      msg[6] = crc;
      msg[7] = crc >> 8;
      Serial.write(msg, 8);
      return;
    }
  }

  String local_ip = "\x11" + WiFi.localIP().toString();
  const char *ip = local_ip.c_str();
  int msg_len = local_ip.length();
  byte frame[8] = { 0, 0xA1, msg_len + 1, 0xF3, 0, 0, 0, 0 };
  unsigned short msg_crc = crc16((const byte *)ip, msg_len, crc16(frame, 4));
  Serial.write(0x02);
  Serial.write(frame, 4);
  for (int j = 0; j < msg_len; j++) {
    Serial.write(*ip++);
  }
  // Serial.write('\0');
  Serial.write(msg_crc & 0xFF);
  Serial.write(msg_crc >> 8);
}

void wifi_disconnect() {
  WiFi.disconnect(false, true);
  byte msg[10] = { 2, 0, 0xA1, 2, 0xF5, 0x11, 0, 0, 0, 0 };
  unsigned short crc = crc16(*(&msg) + 1, 5);
  msg[6] = crc;
  msg[7] = crc >> 8;
  Serial.write(msg, 8);
}
