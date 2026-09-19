# 🚀 SOP & PERINTAH MONITORING BENCHMARK V4 (ISOLASI TERMINAL & QOS MATCHING)
## Robot Humanoid BRONE — ROS 2 Humble (Ubuntu 22.04 LTS)

Dokumen ini berisi panduan alur kerja terpadu dari persiapan, eksekusi pengujian 4 skenario, hingga pembuatan laporan grafik visual untuk robot BRONE menggunakan **Prinsip Isolasi Terminal (Zero-Touch System)**.

---

## 📌 FASE 0: PRE-FLIGHT CHECKLIST & PRINSIP ISOLASI TERMINAL

> [!IMPORTANT]
> **PRINSIP ISOLASI TERMINAL (ZERO-TOUCH SYSTEM):**
> * File `~/.bashrc` di NUC dan JETSON **TETAP MENGGUNAKAN FASTRTPS (`rmw_fastrtps_cpp`)** bawaan standar agar seluruh program robot seperti `op3_manager`, `gaze_node`, dan servo Dynamixel di NUC aman 100%.
> * Perintah `export` di terminal pengujian **HANYA BERLAKU SEMENTARA DI TERMINAL TERSEBUT** dan tidak merusak/mengubah sistem global.

### 1. Verifikasi Environment Utama:
Di NUC (`192.168.100.1`) dan JETSON (`192.168.100.2`), pastikan environment default:
```bash
source ~/.bashrc
echo "RMW: $RMW_IMPLEMENTATION | DOMAIN_ID: $ROS_DOMAIN_ID"
```
👉 *Output standar:* **`RMW: rmw_fastrtps_cpp | DOMAIN_ID: 30`**

### 2. Reset Daemon (Jika CLI Tersangkut):
```bash
ros2 daemon stop
ros2 daemon start
```

---

## ⏰ FASE 1: SINKRONISASI WAKTU (MENCEGAH CLOCK SKEW LINTAS MESIN)

Wajib dijalankan sebelum pengujian lintas mesin (`nuc2jetson` / `jetson2nuc`):

### Metode Chrony (Presisi Tinggi):
* **Di Terminal NUC (Master Clock `192.168.100.1`):**
  ```bash
  sudo systemctl restart chrony
  ```
* **Di Terminal JETSON (Client Clock `192.168.100.2`):**
  ```bash
  sudo chronyd -q 'server 192.168.100.1 iburst'
  chronyc tracking
  ```
  *(Pastikan selisih `System time` < 0.1 ms).*

---

## 🚀 FASE 2: EKSEKUSI PENGUJIAN 4 TOPOLOGI

> ⏱️ **Fitur Web GUI Dashboard v2.0 (Port 8765):**
> * Visualisasi live di browser laptop (`http://<IP_MESIN>:8765`).
> * **State Machine Kontrol Sesi:** Status awal `STANDBY (IDLE)`. Indikator `🟢 Connected` otomatis menyala saat Publisher & Subscriber aktif.
> * Klik **`[ ▶️ Start Session ]`** untuk mulai merekam data bersih.

---

### 🟢 Skenario 1: Baseline NUC Internal (`nuc2nuc` — Shared Memory)

* **Terminal 1 NUC (Publisher):**
  ```bash
  source /opt/ros/jazzy/setup.bash
  cd ~/ros2_network_monitor
  python3 dummy_publisher.py --topology nuc2nuc --freq 125 --payload 128 --samples 0
  ```
* **Terminal 2 NUC (Web GUI Monitor):**
  ```bash
  source /opt/ros/jazzy/setup.bash
  cd ~/ros2_network_monitor
  python3 network_monitor_gui.py --ros-args -p topology:=nuc2nuc
  ```
👉 *Buka Browser Laptop: `http://10.101.143.111:8765/` (atau `http://localhost:8765`).*

---

### 🟢 Skenario 2: Baseline JETSON Internal (`jetson2jetson` — CycloneDDS Terminal Isolation)

> [!NOTE]
> Khusus skenario `jetson2jetson`, tambahkan `export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` **HANYA di Terminal 1 & 2 Jetson** untuk menghindari bug *multicast discovery lock* FastDDS di kernel ARM64 Jetson.

* **Terminal 1 JETSON (Publisher):**
  ```bash
  source /opt/ros/humble/setup.bash
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  cd ~/ros2_network_monitor
  python3 dummy_publisher.py --topology jetson2jetson --freq 125 --payload 128 --samples 0
  ```
* **Terminal 2 JETSON (Web GUI Monitor):**
  ```bash
  source /opt/ros/humble/setup.bash
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  cd ~/ros2_network_monitor
  python3 network_monitor_gui.py --ros-args -p topology:=jetson2jetson
  ```
👉 *Buka Browser Laptop: `http://10.101.143.169:8765` (atau `http://localhost:8765`).*

---

### 🟢 Skenario 3: Uji Lintas Mesin (NUC ➔ JETSON via LAN Direct)

* **Terminal 1 NUC (Publisher):**
  ```bash
  source /opt/ros/jazzy/setup.bash
  cd ~/ros2_network_monitor
  python3 dummy_publisher.py --topology nuc2jetson --freq 125 --payload 128 --samples 0
  ```
* **Terminal 2 JETSON (Web GUI Monitor):**
  ```bash
  source /opt/ros/humble/setup.bash
  cd ~/ros2_network_monitor
  python3 network_monitor_gui.py --ros-args -p topology:=nuc2jetson
  ```

---

### 🟢 Skenario 4: Uji Lintas Mesin (JETSON ➔ NUC via LAN Direct)

* **Terminal 1 JETSON (Publisher):**
  ```bash
  source /opt/ros/humble/setup.bash
  cd ~/ros2_network_monitor
  python3 dummy_publisher.py --topology jetson2nuc --freq 30 --payload 600000 --samples 0
  ```
* **Terminal 2 NUC (Web GUI Monitor):**
  ```bash
  source /opt/ros/jazzy/setup.bash
  cd ~/ros2_network_monitor
  python3 network_monitor_gui.py --ros-args -p topology:=jetson2nuc
  ```

---

## 🩺 FASE 2.5: MODE INSPEKTUR KESEHATAN SISTEM & JITTER DATA NYATA (PASSIVE MODE)

> [!TIP]
> **Kapan Menggunakan Passive Mode?**
> Gunakan mode ini saat robot BRONE sedang beroperasi aktif (menjalankan `op3_manager`, `brone_talk.py`, atau pelacakan wajah `gaze_node`). Node monitor akan mengendus (*sniffing*) topik nyata tanpa menyuntikkan paket buatan, menghitung interval kedatangan data antar-frame ($\Delta t$), mendeteksi *deadline overrun*, dan memantau suhu/beban CPU secara non-intrusif (100% bebas dari clock skew).

### 🟢 1. Menginspeksi Loop Sensor IMU OpenCR (125 Hz — Deadline Budget 8.0 ms)
* **Jalankan di NUC (atau Jetson):**
  ```bash
  source ~/.bashrc  # (Otomatis memuat ROS 2 Jazzy di NUC atau Humble di Jetson)
  cd ~/ros2_network_monitor
  python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/robotis/open_cr/imu -p target_hz:=125.0
  ```
👉 *Buka Browser: `http://192.168.100.1:8765` (atau via IP laptop penguji).*

### 🟢 2. Menginspeksi Feedback Sudut Sendi / Joint States (50 Hz — Deadline Budget 20.0 ms)
* **Jalankan di NUC (atau Jetson):**
  ```bash
  source ~/.bashrc
  cd ~/ros2_network_monitor
  python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/robotis/present_joint_states -p target_hz:=50.0
  ```

### 🟢 3. Menginspeksi Aliran Citra Visi / Kamera Jetson (30 Hz — Deadline Budget 33.3 ms)
* **Jalankan di NUC atau JETSON:**
  ```bash
  source ~/.bashrc
  cd ~/ros2_network_monitor
  python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/camera/image_raw -p target_hz:=30.0
  ```

### 📊 Indikator Traffic Light Kesehatan pada Dashboard:
| Status Badge | Kriteria Evaluasi Otomatis | Arti Operasional |
| :--- | :--- | :--- |
| <span style="color:#15803d; font-weight:bold;">🟢 SISTEM NORMAL & STABIL</span> | Overrun $\le 2\%$, CPU $< 75\%$, Suhu $< 78^\circ\text{C}$, Hz $\approx$ target | Loop kontrol stabil presisi, aman untuk manuver dinamis. |
| <span style="color:#b45309; font-weight:bold;">⚠️ WASPADA / TERDEGRADASI</span> | Overrun $2 - 10\%$, atau CPU $75 - 90\%$, atau Suhu $78 - 85^\circ\text{C}$ | Terjadi jitter akibat beban inferensi SLM/Visi; perhatikan lonjakan lag. |
| <span style="color:#b91c1c; font-weight:bold;">🔴 KRITIS / OVERRUN TINGGI</span> | Overrun $> 10\%$, atau CPU $> 90\%$, atau Suhu $> 85^\circ\text{C}$ | Risiko frame drop tinggi; motor servo berpotensi tersendat (*jerky*). |

---

### 1. Inkompatibilitas QoS saat Mengintip Topik CLI
Saat mengintip topik `/test_topic` via terminal CLI (`ros2 topic echo`), Publisher kita menggunakan QoS `best_effort`. Sertakan opsi `--qos-reliability best_effort`:
```bash
ros2 topic echo /test_topic --qos-reliability best_effort
```

### 2. Memeriksa Topik Langsung Tanpa Daemon
Jika CLI ROS 2 terasa lambat atau tersangkut:
```bash
ros2 topic list --no-daemon
```

---

## 💻 FASE 4: DIAGNOSTIK KEMAMPUAN HARDWARE & BEBAN MESIN

* **Di Intel NUC (Master):**
  ```bash
  htop
  watch -n 1 "sensors | grep -i core"
  ```
* **Di NVIDIA Jetson Orin Nano (Visi/Persepsi):**
  ```bash
  jtop
  tegrastats
  ```

---

## Skenario 5: Stress Test (Isolasi Variabel)

Gunakan metode ini untuk mencari titik batas maksimal latensi sistem. **Sangat disarankan menggunakan Metode B (CLI)** agar sistem tidak terbebani oleh rendering GUI saat stres tinggi. 

**ATURAN EMAS:** Ubah hanya SATU variabel dalam satu waktu. Kunci *payload* saat *sweeping* frekuensi, dan kunci frekuensi saat *sweeping payload*.

### A. Sweeping Frekuensi (Kunci Payload di 128 Bytes)
Bertujuan mencari batas maksimal Hz yang bisa ditangani jaringan sebelum *miss rate* muncul.
*(Contoh di bawah menggunakan NUC lokal. Sesuaikan `--topology` jika mencoba di Jetson).*

```bash
# Level 1: 100 Hz
python3 dummy_publisher.py --topology nuc2nuc --freq 100 --payload 128 --samples 0
python3 network_monitor.py --topology nuc2nuc --freq 100 --payload 128 --samples 0

# Level 2: 500 Hz
python3 dummy_publisher.py --topology nuc2nuc --freq 500 --payload 128 --samples 0
python3 network_monitor.py --topology nuc2nuc --freq 500 --payload 128 --samples 0

# Level 3: 1000 Hz (Extreme)
python3 dummy_publisher.py --topology nuc2nuc --freq 1000 --payload 128 --samples 0
python3 network_monitor.py --topology nuc2nuc --freq 1000 --payload 128 --samples 0
```

### B. Sweeping Payload (Kunci Frekuensi di 50 Hz)
Bertujuan menguji ketahanan bandwidth (simulasi pengiriman array data besar seperti Lidar/Vision).
*(Contoh di bawah menggunakan NUC lokal. Sesuaikan `--topology` jika mencoba di Jetson).*

```bash
# Level 1: 1024 Bytes (1 KB)
python3 dummy_publisher.py --topology nuc2nuc --freq 50 --payload 1024 --samples 1000
python3 network_monitor.py --topology nuc2nuc --freq 50 --payload 1024 --samples 1000

# Level 2: 16384 Bytes (16 KB)
python3 dummy_publisher.py --topology nuc2nuc --freq 50 --payload 16384 --samples 1000
python3 network_monitor.py --topology nuc2nuc --freq 50 --payload 16384 --samples 1000

# Level 3: 65536 Bytes (65 KB - Maksimum UDP/DDS normal)
python3 dummy_publisher.py --topology nuc2nuc --freq 50 --payload 65536 --samples 1000
python3 network_monitor.py --topology nuc2nuc --freq 50 --payload 65536 --samples 1000
```

### C. Pengujian RELIABLE QoS
Hanya lakukan ini untuk mensimulasikan trafik State/Command yang pantang hilang. Default QoS adalah best_effort. Pastikan parameter --qos reliable dipasang di kedua sisi.
*(Contoh di bawah menggunakan NUC lokal. Sesuaikan `--topology` jika mencoba di Jetson).*

```bash
python3 dummy_publisher.py --topology nuc2nuc --freq 100 --payload 256 --samples 2000 --qos reliable
python3 network_monitor.py --topology nuc2nuc --freq 100 --payload 256 --samples 2000 --qos reliable
```
---

## 📊 FASE 3: Pembuatan Grafik & Laporan Otomatis

Setelah pengujian menghasilkan file `brone_log_*.csv`, buat laporan visual time-series lengkap dengan tool `plot_report.py`.

### 1. Eksekusi Generator Laporan (di Laptop atau NUC/Jetson)
```bash
# Memproses file CSV log terbaru:
python3 plot_report.py

# Atau memproses file CSV tertentu:
python3 plot_report.py brone_log_jetson2nuc_50hz_128b_best_effort_20260826_201015.csv
```

### 2. Output yang Dihasilkan:
1. 📑 **`<nama_file_log>_report.html` (Laporan Interaktif Light Mode):**
   - Kartu Metrik Latensi (Avg, Min, Max, p95, p99), Throughput Hz, Total Sampel, & Miss Rate.
   - Daftar Event Marker yang ditandai selama pengujian.
   - Grafik Fluktuasi Latensi Kontinu (Avg, p95, p99, Min-Max Jitter Shading).
   - Grafik Kestabilan Throughput Frekuensi (Hz).
   - Tombol **"🖨️ Cetak / Simpan PDF"** siap untuk lampiran dokumen resmi skripsi.
2. 🖼️ **`<nama_file_log>_plot.png`:** Grafik resolusi tinggi (300 DPI Light Mode) dengan 3 subplot bertumpuk dan garis vertikal penanda event.

---

## 💡 Tips: Membuka File CSV di Excel Windows
Jika file CSV dibuka di Excel dan seluruh data berada dalam Kolom A:
1. Blok **Kolom A**.
2. Pilih tab menu **Data** ➔ klik **Text to Columns**.
3. Pilih **Delimited** ➔ Next ➔ Centang **Comma** ➔ Klik **Finish**.

---

## ⏰ Solusi & Mitigasi Lengkap Jika Terjadi Clock Skew (Latensi Minus)

### Kapan Perlu Sinkronisasi Jam?
- **Uji Lokal Standalone (`jetson2jetson` / `nuc2nuc`):** ❌ **TIDAK PERLU**. Menggunakan 1 hardware CPU yang sama (`perf_counter_ns`), clock homogen dan bebas dari clock skew.
- **Uji Lintas Mesin (`jetson2nuc` / `nuc2jetson`):** ✅ **DIBUTUHKAN** jika kristal jam hardware NUC dan Jetson memiliki selisih waktu (offset).

---

### 🛠️ METODE 1: Sinkronisasi Presisi Tinggi via `chrony` (Rekomendasi Utama)
Jika di monitor muncul nilai latensi negatif (misal `-3.2 ms`) atau banner kuning Clock Skew aktif:

1. **Di Terminal NUC (Master Clock):**
   ```bash
   sudo apt install -y chrony
   sudo systemctl restart chrony
   ```

2. **Di Terminal JETSON (Client Clock):**
   ```bash
   sudo apt install -y chrony
   # Sinkronkan langsung ke IP NUC (bisa lewat IP ZeroTier atau IP LAN Kabel):
   sudo chronyd -q 'server 10.101.143.111 iburst'
   # Atau via IP LAN: sudo chronyd -q 'server 192.168.100.1 iburst'
   ```

3. **Verifikasi Keberhasilan di Jetson:**
   ```bash
   chronyc tracking
   ```
   👉 *Lihat baris `System time`: Jika tertulis `0.0000xxxxx seconds slow/fast` (selisih < 0.1 ms), sinkronisasi berhasil 100% dan Clock Skew hilang!*

---

### ⚡ METODE 2: Quick-Fix 1 Detik (Jika Tanpa Koneksi Internet / Offline Lapangan)
Jika di lapangan lomba robot tidak ada koneksi internet untuk install paket baru, cukup ketik **1 baris perintah ini di terminal JETSON**:

```bash
sudo date -s "$(ssh brone-ub@10.101.143.111 'date -u -Iseconds')"
```
*(Perintah ini menyalin detik dan menit waktu sistem NUC secara instan ke Jetson via SSH).*

> 🛡️ **Mengapa Aman untuk ROS 2 & Robotis OP3?**  
> `chrony` menggunakan metode **Clock Slewing** (menyesuaikan kecepatan kristal mikrodetik secara halus tanpa lompatan waktu kasar), sehingga **Transform Tree (TF2), Odometri, dan State Machine Robotis OP3 tetap 100% stabil dan tidak akan mengalami error waktu.**

---

## 🔍 Catatan Teknis: Middleware & Kompatibilitas Lintas Distro (Jazzy ↔ Humble)

### 1. Pastikan Kedua Mesin Memakai CycloneDDS (`rmw_cyclonedds_cpp`)
Jika saat dicek dengan `echo $RMW_IMPLEMENTATION` masih bernilai `rmw_fastrtps_cpp`:
- **Penyebab Masalah:** FastDDS bawaan Humble (Jetson) dan Jazzy (NUC) memiliki bug pada deserialisasi array biner serta format internal yang berbeda, menyebabkan paket tidak masuk.
- **Solusi Sesi Terminal (Aman & Terisolasi):**
  ```bash
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  ```
  *(Perintah `export` ini hanya aktif di jendela terminal pengujian dan otomatis kembali ke kondisi awal saat terminal ditutup).*

### 2. Peringatan "Failed to parse type hash... from USER_DATA '(null)'"
Jika di terminal NUC (Jazzy) muncul serangkaian pesan:
`[WARN] [rmw_cyclonedds_cpp]: Failed to parse type hash for topic ... from USER_DATA '(null)'`
- **Penyebab:** ROS 2 Jazzy (Ubuntu 24.04) memiliki fitur *Type Hash* (sidik jari tipe pesan). ROS 2 Humble (Ubuntu 22.04) belum memiliki fitur tersebut, sehingga nilainya kosong (`null`).
- **Status:** **100% AMAN (*Benign Warning*)**. Peringatan ini murni informasi kompatibilitas versi. Seluruh isi data biner, nomor sequence, dan kalkulasi latensi tetap terkirim dan terbaca 100% sempurna tanpa *corruption*.

---

## 🛡️ Batasan Sistem & Disclaimer Ruang Lingkup Pengukuran

Pahami batasan ini agar tidak terjadi salah interpretasi terhadap angka yang tertera di dashboard:

| Jalur / Komponen | Apakah Diukur oleh Monitor? | Penjelasan Teknis |
|---|:---:|---|
| 🌐 **Kabel LAN RJ45 (NUC ↔ Jetson)** | ✅ **DIUKUR (In-Scope)** | Latensi murni $\sim 1.2\text{ ms}$ mencakup serialisasi struct biner, middleware CycloneDDS, UDP transport, dan perambatan sinyal kabel fisik LAN robot. |
| 💻 **Komunikasi Loopback (Intra-Host)** | ✅ **DIUKUR (In-Scope)** | Latensi internal $\sim 0.7\text{ -- }0.8\text{ ms}$ di dalam memori/loopback prosesor NUC atau Jetson. |
| 📶 **SSH / Wi-Fi / ZeroTier Laptop** | ❌ **TIDAK DIUKUR (Out-of-Scope)** | Sinyal Wi-Fi laptop ke robot memiliki latensi acak ($\sim 20\text{ -- }100\text{ ms}$). Ini adalah jalur *telemetri pengamat*, bukan kontrol on-board robot. |
| 🔌 **Serial Bus Dynamixel / OpenCR / U2D2** | ❌ **TIDAK DIUKUR (Out-of-Scope)** | Waktu transmisi fisik USB/UART ke mikrokontroler OpenCR/servo ($\sim 1\text{ -- }3\text{ ms}$) adalah *hardware serial bus*, bukan lapisan DDS. |
| 👁️ **Waktu Inferensi AI & Shutter Kamera** | ❌ **TIDAK DIUKUR (Out-of-Scope)** | Waktu eksposur sensor optik kamera ($\sim 20\text{ ms}$) dan kalkulasi tensor GPU YOLOv11 ($\sim 30\text{ ms}$) adalah *computation latency*, bukan *network transport latency*. |
