# 🚀 PANDUAN OPERASIONAL LENGKAP & SOP MONITORING DUAL-MODE (v5.0)
## Robot Humanoid BRONE — ROS 2 Jazzy (NUC) & Humble (Jetson Orin Nano)
### Universitas Brawijaya • Lab Robotika Humanoid

Dokumen ini adalah **Standard Operating Procedure (SOP)** terpadu untuk pengujian, monitoring, dan analisis performa jaringan komunikasi DDS serta kesehatan sistem robot humanoid BRONE. Sistem monitoring mendukung **Dual-Mode**:
1. **Mode 1 — Synthetic Benchmark**: Injeksi paket dummy terkalibrasi untuk mengukur latensi end-to-end transmisi kabel/internal pada 4 topologi komunikasi.
2. **Mode 2 — Passive Real-World Health & Jitter Inspector**: Sniffer pasif non-intrusif untuk topik robot nyata (`/robotis/open_cr/imu`, `/robotis/present_joint_states`, `/camera/image_raw`, `/cmd_vel`) dengan evaluasi *inter-arrival jitter* ($\Delta t$), *deadline overrun budget*, dan visual *Traffic Light*.

---

## 📑 DAFTAR ISI SISTEMATIS
1. [FASE 0: Pre-Flight Checklist, Git Sync, & Isolasi Sistem](#-fase-0-pre-flight-checklist-git-sync--isolasi-sistem)
2. [FASE 1: Sinkronisasi Waktu Antar-Mesin (Mitigasi Clock Skew)](#-fase-1-sinkronisasi-waktu-antar-mesin-mitigasi-clock-skew)
3. [FASE 2: Mode 1 — Synthetic Benchmark (4 Topologi Komunikasi)](#-fase-2-mode-1--synthetic-benchmark-4-topologi-komunikasi)
4. [FASE 3: Mode 2 — Passive Health & Jitter Inspector (Topik Robot Nyata)](#-fase-3-mode-2--passive-health--jitter-inspector-topik-robot-nyata)
5. [FASE 4: Panduan Interaktif Web Dashboard v2.0 (Port 8765)](#-fase-4-panduan-interaktif-web-dashboard-v20-port-8765)
6. [FASE 5: Skenario Stres & Pengujian Batas Ekstrem (Stress Test)](#-fase-5-skenario-stres--pengujian-batas-ekstrem-stress-test)
7. [FASE 6: Diagnostik Telemetri Hardware & Beban Komputasi](#-fase-6-diagnostik-telemetri-hardware--beban-komputasi)
8. [FASE 7: Generator Grafik & Laporan Analisis Otomatis (`plot_report.py`)](#-fase-7-generator-grafik--laporan-analisis-otomatis-plot_reportpy)
9. [FASE 8: Manajemen Log, Pengambilan Data ke Laptop, & Format Excel](#-fase-8-manajemen-log-pengambilan-data-ke-laptop--format-excel)
10. [FASE 9: Troubleshooting, Manajemen Port, & FAQ Lapangan](#-fase-9-troubleshooting-manajemen-port--faq-lapangan)
11. [FASE 10: Rangkuman Cepat Perintah Lapangan (1-Page Cheat Sheet)](#-fase-10-rangkuman-cepat-perintah-lapangan-1-page-cheat-sheet)
12. [FASE 11: Batasan Ruang Lingkup Pengukuran (*System Boundaries*)](#-fase-11-batasan-ruang-lingkup-pengukuran-system-boundaries)

---

## 📌 FASE 0: PRE-FLIGHT CHECKLIST, GIT SYNC, & ISOLASI SISTEM

> [!IMPORTANT]
> **PRINSIP ZERO-TOUCH SYSTEM (ISOLASI TERMINAL):**
> * Konfigurasi bawaan `~/.bashrc` di Intel NUC dan NVIDIA Jetson **TETAP MENGGUNAKAN FASTRTPS (`rmw_fastrtps_cpp`)** dengan `ROS_DOMAIN_ID=30`.
> * Perangkat lunak inti robot BRONE (seperti `op3_manager`, `gaze_node`, `brone-talk`, dan driver Dynamixel) **TIDAK DIUBAH SAMA SEKALI**.
> * Perintah `export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` **HANYA DIKETIK DI TERMINAL PENGUJIAN SEMENTARA** (otomatis kembali normal saat jendela terminal ditutup).

### 1. Verifikasi Environment Default
Jalankan di terminal Intel NUC (`192.168.100.1`) dan Jetson Orin Nano (`192.168.100.2`):
```bash
source ~/.bashrc
echo "RMW: $RMW_IMPLEMENTATION | DOMAIN_ID: $ROS_DOMAIN_ID"
```
👉 *Output standar:* **`RMW: rmw_fastrtps_cpp | DOMAIN_ID: 30`**

### 2. Prosedur Pembaruan Kode dari Git (Mencegah Pathspec Mismatch):
Lakukan di NUC maupun Jetson setiap kali ada pembaruan di repository GitHub:
```bash
cd ~/ros2_network_monitor
git fetch origin
git checkout feature/live-data-monitor
git pull origin feature/live-data-monitor
```
👉 *Verifikasi status:*
```bash
git status
# Output yang benar: On branch feature/live-data-monitor
# Your branch is up to date with 'origin/feature/live-data-monitor'.
```

> [!TIP]
> **Menangani Untracked Files Saat Git Status:**
> Jika saat mengetik `git status` muncul file hasil run sebelumnya (misal: `brone_log_*.csv`, `brone_report_*.html`), file-file tersebut aman dibiarkan (sudah masuk dalam `.gitignore`). Jika ingin membersihkan workspace tanpa menghapus log penting, cukup pindahkan file `.csv` ke folder arsip khusus atau laptop penguji.

### 3. Reset ROS 2 Daemon (Jika Perintah CLI Lambat/Stuck):
```bash
ros2 daemon stop
ros2 daemon start
```

---

## ⏰ FASE 1: SINKRONISASI WAKTU ANTAR-MESIN (MITIGASI CLOCK SKEW)

> [!NOTE]
> **Kapan Sinkronisasi Waktu Diperlukan?**
> * **Uji Intra-Host (`nuc2nuc` atau `jetson2jetson`):** ❌ **TIDAK PERLU**. Menggunakan 1 kristal jam CPU yang sama (`perf_counter_ns`), dijamin 100% bebas clock skew.
> * **Passive Inspector Mode (`mode:=passive`):** ❌ **TIDAK PERLU**. Menggunakan waktu kedatangan frame lokal di sisi subscriber ($\Delta t$), dijamin 100% bebas clock skew.
> * **Uji Sintetik Lintas Mesin (`nuc2jetson` atau `jetson2nuc`):** ✅ **WAJIB DIJALANKAN** sebelum sesi benchmarking dimulai.

### 🛠️ Rekomendasi Utama: Sinkronisasi Presisi via `chrony`
Jika terjadi latensi negatif di dashboard (banner kuning *Clock Skew Warning*):

1. **Di Terminal Intel NUC (`192.168.100.1` — Master Clock):**
   ```bash
   sudo systemctl restart chrony
   ```
2. **Di Terminal Jetson Orin Nano (`192.168.100.2` — Client Clock):**
   ```bash
   sudo chronyd -q 'server 192.168.100.1 iburst'
   chronyc tracking
   ```
   👉 *Periksa baris `System time`: jika selisih waktu `< 0.000100 s` (< 0.1 ms), sinkronisasi sukses sempurna.*

### ⚡ Alternatif Lapangan: Quick-Fix 1-Detik via SSH (Tanpa Internet)
Jika di venue kompetisi tidak tersedia akses internet untuk install package, jalankan satu baris perintah ini di terminal **Jetson**:
```bash
sudo date -s "$(ssh brone-ub@192.168.100.1 'date -u -Iseconds')"
```

---

## 🚀 FASE 2: MODE 1 — SYNTHETIC BENCHMARK (4 TOPOLOGI KOMUNIKASI)

Digunakan untuk mengevaluasi batas kapabilitas jaringan internal dan kabel LAN fisik point-to-point BRONE.

### 🟢 Skenario 1: Baseline NUC Internal (`nuc2nuc` — Shared Memory FastRTPS)
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
👉 *Akses Web Monitor via Browser Laptop:* `http://10.101.143.111:8765/` (ZeroTier) atau `http://192.168.100.1:8765/` (LAN).

---

### 🟢 Skenario 2: Baseline JETSON Internal (`jetson2jetson` — CycloneDDS Terisolasi)

> [!NOTE]
> Khusus `jetson2jetson`, tambahkan `export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` **HANYA di Terminal 1 & 2 Jetson** untuk mencegah kendala multicast internal FastDDS pada kernel ARM64 Jetpack.

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
👉 *Akses Web Monitor:* `http://10.101.143.169:8765/` (ZeroTier) atau `http://192.168.100.2:8765/` (LAN).

---

### 🟢 Skenario 3: Uji Lintas Mesin NUC ➔ JETSON (Kabel LAN Direct)
Simulasi aliran instruksi kontrol frekuensi tinggi dari NUC ke Jetson.

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

### 🟢 Skenario 4: Uji Lintas Mesin JETSON ➔ NUC (Kabel LAN Direct)
Simulasi streaming frame citra kamera berukuran besar (600 KB @ 30 Hz).

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

## 🩺 FASE 3: MODE 2 — PASSIVE HEALTH & JITTER INSPECTOR (TOPIK ROBOT NYATA)

> [!TIP]
> **Karakteristik & Keunggulan Mode Pasif:**
> * **Zero Overhead / Non-Intrusif:** Tidak menyuntikkan paket buatan yang membebani CPU robot.
> * **100% Imun Terhadap Clock Skew:** Menghitung interval waktu kedatangan lokal ($\Delta t_i = t_{\text{recv}, i} - t_{\text{recv}, i-1}$) menggunakan clock tunggal receiver.
> * **Evaluasi Real-Time Deadline Budget:** Batas waktu pengiriman dihitung otomatis:
>   $$T_{\text{budget}} = \frac{1000}{\text{target\_hz}}\text{ ms}$$
> * **Traffic Light Status:** Memantau jitter, deadline overrun, temperatur, dan pemakaian RAM/CPU.

### 🟢 1. Menginspeksi Loop Sensor IMU OpenCR (125 Hz — Budget 8.0 ms)
Loop stabilitas posisi tegak tubuh robot BRONE:
```bash
source ~/.bashrc
cd ~/ros2_network_monitor
python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/robotis/open_cr/imu -p target_hz:=125.0
```

### 🟢 2. Menginspeksi Feedback Sudut Sendi / Joint States (50 Hz — Budget 20.0 ms)
Loop trajectory position aktual dari 20 servo Dynamixel:
```bash
source ~/.bashrc
cd ~/ros2_network_monitor
python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/robotis/present_joint_states -p target_hz:=50.0
```

### 🟢 3. Menginspeksi Aliran Citra Kamera / Visi Jetson (30 Hz — Budget 33.3 ms)
Uji bandwidth transmisi frame kamera web/RGB:
```bash
source ~/.bashrc
cd ~/ros2_network_monitor
python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/camera/image_raw -p target_hz:=30.0
```

### 🟢 4. Menginspeksi Perintah Gerak & Navigasi (`/cmd_vel` — 10 Hz — Budget 100.0 ms)
Loop instruksi velocity navigasi autonomous:
```bash
source ~/.bashrc
cd ~/ros2_network_monitor
python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/cmd_vel -p target_hz:=10.0
```

### 🟢 5. Menginspeksi Modul Berjalan Robotis (`/robotis/walking/command`)
```bash
source ~/.bashrc
cd ~/ros2_network_monitor
python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/robotis/walking/command -p target_hz:=10.0
```

---

### 🛠️ Toolkit Probing Topik Robot Nyata:
Gunakan baris perintah diagnostik berikut sebelum menyalakan monitor untuk memvalidasi topik yang sedang aktif:
```bash
# A. Melihat semua topik yang sedang aktif di jaringan BRONE:
ros2 topic list

# B. Mengukur frekuensi publikasi aktual topik target:
ros2 topic hz /robotis/open_cr/imu

# C. Mengetahui tipe pesan (Message Type):
ros2 topic type /robotis/open_cr/imu

# D. Memeriksa detail QoS Publisher aktif (Reliability & History):
ros2 topic info -v /robotis/open_cr/imu

# E. Mengintip isi data topik dengan QoS best_effort:
ros2 topic echo /robotis/open_cr/imu --qos-reliability best_effort
```

---

### 📊 Evaluasi Traffic Light Kesehatan Sistem:
| Status Badge | Kriteria Evaluasi Otomatis | Arti Operasional & Dampak Robot |
| :--- | :--- | :--- |
| <span style="color:#15803d; font-weight:bold;">🟢 SISTEM NORMAL & STABIL</span> | Overrun $\le 2\%$, CPU $< 75\%$, Suhu $< 78^\circ\text{C}$, Hz stabil | Loop kontrol sangat presisi, aman untuk manuver dinamis dan jalan cepat. |
| <span style="color:#b45309; font-weight:bold;">⚠️ WASPADA / TERDEGRADASI</span> | Overrun $2 - 10\%$, atau CPU $75 - 90\%$, atau Suhu $78 - 85^\circ\text{C}$ | Mulai timbul jitter akibat beban inferensi SLM/Visi; perhatikan lonjakan lag. |
| <span style="color:#b91c1c; font-weight:bold;">🔴 KRITIS / OVERRUN TINGGI</span> | Overrun $> 10\%$, atau CPU $> 90\%$, atau Suhu $> 85^\circ\text{C}$ | Risiko paket drop tinggi; kendali servo berpotensi tersendat (*jerky* / hilang kendali). |

---

## 🖥️ FASE 4: PANDUAN INTERAKTIF WEB DASHBOARD v2.0 (PORT 8765)

Dashboard web dapat diakses dari browser komputer/laptop mana saja yang terhubung ke jaringan robot melalui IP NUC (`192.168.100.1:8765`) atau IP Jetson (`192.168.100.2:8765`).

```
+-----------------------------------------------------------------------------------+
|  [Logo UB]      BRONE ROS 2 NETWORK MONITOR & HEALTH INSPECTOR     [Logo Global]  |
|                                                                                   |
|  Status: [ 🟢 HEALTHY - SISTEM NORMAL & STABIL ]   Mode: PASSIVE   Port: 8765     |
+-----------------------------------------------------------------------------------+
|  Topic: /robotis/open_cr/imu  |  Rate: 124.8 Hz  |  Jitter: 0.21 ms  | Overrun: 0.1%|
+-----------------------------------------------------------------------------------+
|  [ ▶️ Start Session ]  [ ⏹️ Stop Session ]   Session Status: STANDBY (IDLE)        |
+-----------------------------------------------------------------------------------+
|  GRAFIK 1: Inter-Arrival Δt vs Deadline Budget Line (Merah Putus-putus)           |
|  GRAFIK 2: Jitter Time-Series (ms)                                                |
|  GRAFIK 3: Throughput Aktual (Hz)                                                 |
|  GRAFIK 4: Telemetri Hardware (Suhu °C & CPU % NUC/Jetson)                        |
+-----------------------------------------------------------------------------------+
|  Hasil Sesi Selesai: [ 📥 Unduh File CSV ]   [ 📑 Buka Laporan Interaktif HTML ]  |
+-----------------------------------------------------------------------------------+
```

### 📋 Alur Kerja Operator Saat Pengujian:
1. **Buka Web GUI:** Buka Google Chrome / Firefox di laptop: `http://192.168.100.1:8765` (atau IP Jetson).
2. **Periksa Indikator Koneksi:** Pastikan lampu status di pojok kiri bertuliskan `🟢 Connected` dan nama topik yang diinspeksi sudah benar.
3. **Mulai Perekaman Data Bersih:** Klik tombol **`[ ▶️ Start Session ]`**.
   - Badge sesi akan berubah menjadi kuning: `⏺️ RECORDING`.
   - Counter durasi dan jumlah sampel mulai bertambah.
   - Perekaman awal ini mengabaikan lonjakan inisialisasi (*warmup*).
4. **Biarkan Pengujian Berjalan:** Biarkan robot beraktivitas (misal: 60 detik atau 1000 sampel).
5. **Hentikan Sesi:** Klik tombol **`[ ⏹️ Stop Session ]`**.
   - Node monitor secara instan menyimpan log CSV (`brone_health_*.csv` atau `brone_log_*.csv`).
   - Node monitor otomatis membuat laporan interaktif HTML (`brone_report_*.html`).
6. **Akses Hasil Pengujian:**
   - Klik langsung tombol **`[ 📥 Unduh CSV ]`** di dashboard untuk mendownload file CSV ke laptop.
   - Klik tombol **`[ 📑 Buka Laporan HTML ]`** untuk melihat analisis statistik lengkap (p95, p99, grafik).

---

## ⚡ FASE 5: SKENARIO STRES & PENGUJIAN BATAS EKSTREM (STRESS TEST)

Gunakan skenario ini untuk mencari *breaking point* kapasitas transfer DDS sebelum terjadi packet drop.

> [!IMPORTANT]
> **ATURAN ISOLASI VARIABEL:**
> Ubah hanya **SATU variabel** dalam satu waktu:
> * Kunci *payload* saat menguji variasi frekuensi (Hz).
> * Kunci *frekuensi* saat menguji variasi payload (Bytes).

### A. Sweeping Frekuensi (Kunci Ukuran Payload di 128 Bytes)
* **Level 1 (100 Hz):**
  ```bash
  python3 dummy_publisher.py --topology nuc2nuc --freq 100 --payload 128 --samples 0
  python3 network_monitor_gui.py --ros-args -p topology:=nuc2nuc
  ```
* **Level 2 (500 Hz):**
  ```bash
  python3 dummy_publisher.py --topology nuc2nuc --freq 500 --payload 128 --samples 0
  python3 network_monitor_gui.py --ros-args -p topology:=nuc2nuc
  ```
* **Level 3 (1000 Hz — Stres Ekstrem):**
  ```bash
  python3 dummy_publisher.py --topology nuc2nuc --freq 1000 --payload 128 --samples 0
  python3 network_monitor_gui.py --ros-args -p topology:=nuc2nuc
  ```

### B. Sweeping Payload (Kunci Frekuensi di 50 Hz)
* **Level 1 (1024 Bytes / 1 KB):**
  ```bash
  python3 dummy_publisher.py --topology nuc2nuc --freq 50 --payload 1024 --samples 1000
  ```
* **Level 2 (16384 Bytes / 16 KB):**
  ```bash
  python3 dummy_publisher.py --topology nuc2nuc --freq 50 --payload 16384 --samples 1000
  ```
* **Level 3 (65536 Bytes / 64 KB — Batas Maksimum Fragmentasi UDP Normal):**
  ```bash
  python3 dummy_publisher.py --topology nuc2nuc --freq 50 --payload 65536 --samples 1000
  ```

### C. Pengujian RELIABLE QoS (Lossless State & Command)
Khusus menguji transmisi data kritis yang tidak boleh hilang:
```bash
python3 dummy_publisher.py --topology nuc2nuc --freq 100 --payload 256 --samples 2000 --qos reliable
python3 network_monitor_gui.py --ros-args -p topology:=nuc2nuc -p qos:=reliable
```

---

## 💻 FASE 6: DIAGNOSTIK TELEMETRI HARDWARE & BEBAN KOMPUTASI

Periksa beban fisik komputasi on-board robot:

* **Di Intel NUC (Master Controller):**
  ```bash
  htop                                 # Pemakaian per-core CPU & RAM
  watch -n 1 "sensors | grep -i core"  # Suhu thermal core processor x86
  ```
* **Di NVIDIA Jetson Orin Nano (Visi & Persepsi AI):**
  ```bash
  jtop                                 # Monitor GPU, DLA, CPU, Suhu, & Daya Watt
  tegrastats                           # Output teks telemetri SoC real-time
  ```

---

## 📊 FASE 7: GENERATOR GRAFIK & LAPORAN ANALISIS OTOMATIS (`plot_report.py`)

Skrip `plot_report.py` secara otomatis mendeteksi format data log:
* **Log Sintetik (`brone_log_*.csv`):** Menampilkan metrik Round-Trip / One-Way Latency (ms), Throughput (Hz), Jitter, & Packet Loss (%).
* **Log Pasif (`brone_health_*.csv`):** Menampilkan metrik Inter-Arrival $\Delta t$ (ms), Target Period, Jitter, & Deadline Overrun Rate (%).

### 1. Perintah Eksekusi Laporan:
```bash
cd ~/ros2_network_monitor

# A. Menghasilkan laporan dari file log terbaru atau seluruh file di folder:
python3 plot_report.py

# B. Menghasilkan laporan khusus untuk pengujian topik IMU:
python3 plot_report.py brone_health_robotis_open_cr_imu_125hz_*.csv

# C. Multi-Run Comparison (Membandingkan performa beberapa skenario sekaligus):
python3 plot_report.py brone_health_*.csv brone_log_*.csv
```

### 2. Berkas Hasil Output yang Terbentuk:
1. 📑 **`brone_report_<timestamp>.html`:**
   - Laporan web mandiri (*standalone*, tanpa butuh server).
   - Tabel perbandingan multi-run dengan penanda otomatis `[PASSIVE]` vs `[SYNTHETIC]`.
   - Grafik batang komparasi metrik statistik (Mean, p95, p99, Throughput Hz).
   - Grafik runtun waktu (*time series history*) per detik.
   - Tombol **"🖨️ Cetak / Simpan PDF"** dengan CSS cetak yang rapi untuk lampiran laporan teknis/jurnal.
2. 🖼️ **`brone_report_<timestamp>.png`:** Grafik resolusi tinggi (300 DPI) jika library `matplotlib` terpasang.

---

## 📦 FASE 8: MANAJEMEN LOG, PENGAMBILAN DATA KE LAPTOP, & FORMAT EXCEL

### 1. Mengunduh Log Melalui Browser
Setelah sesi pengujian selesai di Web Dashboard, cukup klik link:
* **`[ 📥 Unduh File CSV ]`**
* **`[ 📑 Buka Laporan HTML ]`** (lalu tekan `Ctrl+S` untuk menyimpan).

### 2. Mengambil Seluruh Log ke Laptop Penguji via SCP / Rsync:
Buka terminal di **laptop penguji** (Linux/macOS/Windows PowerShell):
```bash
# Mengunduh seluruh file CSV dan HTML dari Jetson:
scp brone@192.168.100.2:~/ros2_network_monitor/brone_* ./hasil_pengujian/

# Atau via ZeroTier IP Jetson:
scp brone@10.101.143.169:~/ros2_network_monitor/brone_* ./hasil_pengujian/

# Mengunduh dari Intel NUC:
scp brone-ub@192.168.100.1:~/ros2_network_monitor/brone_* ./hasil_pengujian/
```

### 3. Membuka File CSV di Microsoft Excel Windows:
File CSV kami sudah disematkan **UTF-8 BOM (`\ufeff`)** sehingga karakter dan angka terbaca akurat. Jika data masih terkumpul dalam satu kolom:
1. Blok **Kolom A**.
2. Klik tab menu **Data** ➔ pilih **Text to Columns**.
3. Pilih **Delimited** ➔ Klik **Next**.
4. Centang kotak **Comma** ➔ Klik **Finish**.

---

## 🔧 FASE 9: TROUBLESHOOTING, MANAJEMEN PORT, & FAQ LAPANGAN

### 1. Error `[Errno 98] Address already in use` (Port 8765 Bentrok)
Terjadi jika node sebelumnya dimatikan paksa (`Ctrl+Z` bukan `Ctrl+C`) sehingga port masih terkunci.
```bash
# Solusi A: Matikan proses yang masih memegang port 8765
fuser -k 8765/tcp

# Solusi B: Gunakan port alternatif langsung saat menjalankan node:
python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/robotis/open_cr/imu -p http_port:=8766
```

### 2. Data Kosong saat Menjalankan `ros2 topic echo` di Terminal
Jika `ros2 topic echo /test_topic` tidak memunculkan data apa pun:
* **Penyebab:** Perbedaan QoS Reliability. Publisher kami menggunakan `best_effort`.
* **Solusi:** Tambahkan flag `--qos-reliability best_effort`:
  ```bash
  ros2 topic echo /test_topic --qos-reliability best_effort
  ```

### 3. Peringatan Harmless Jazzy ↔ Humble:
Pesan seperti: `[WARN] [rmw_cyclonedds_cpp]: Failed to parse type hash... from USER_DATA '(null)'`
* **Status:** **100% AMAN (*Benign Compatibility Notice*)**. ROS 2 Jazzy (Ubuntu 24.04) memiliki Type Hash, sedangkan Humble (Ubuntu 22.04) belum memiliki. Semua transmisi payload dan kalkulasi latensi tetap 100% valid tanpa cacat.

### 4. Uji Konektivitas Fisik Kabel LAN & Broker MQTT Jetson:
```bash
# Uji kabel fisik point-to-point NUC <-> Jetson:
ping -c 3 192.168.100.1
ping -c 3 192.168.100.2

# Verifikasi port broker MQTT Mosquitto di Jetson (Port 1883):
nc -zv 192.168.100.2 1883

# Periksa daemon service bawaan robot di Jetson:
systemctl status brone_jetson_manager.service expression-display.service
```

---

## ⚡ FASE 10: RANGKUMAN CEPAT PERINTAH LAPANGAN (1-PAGE CHEAT SHEET)

Tabel referensi cepat perintah terminal untuk operator robot saat pengujian di lab/lomba:

| Skenario Pengujian | Mesin | Perintah Terminal Cepat |
| :--- | :---: | :--- |
| **Pre-Flight Env Check** | NUC & Jetson | `source ~/.bashrc && echo "RMW: $RMW_IMPLEMENTATION \| DOMAIN: $ROS_DOMAIN_ID"` |
| **Sinkronisasi Jam Chrony** | Jetson | `sudo chronyd -q 'server 192.168.100.1 iburst' && chronyc tracking` |
| **Synthetic `nuc2nuc`** | NUC | Pub: `python3 dummy_publisher.py --topology nuc2nuc --freq 125 --payload 128 --samples 0`<br>GUI: `python3 network_monitor_gui.py --ros-args -p topology:=nuc2nuc` |
| **Synthetic `jetson2jetson`** | Jetson | Pub: `export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp && python3 dummy_publisher.py --topology jetson2jetson --freq 125 --payload 128 --samples 0`<br>GUI: `export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp && python3 network_monitor_gui.py --ros-args -p topology:=jetson2jetson` |
| **Synthetic `nuc2jetson`** | NUC & Jetson | NUC (Pub): `python3 dummy_publisher.py --topology nuc2jetson --freq 125 --payload 128 --samples 0`<br>Jetson (GUI): `python3 network_monitor_gui.py --ros-args -p topology:=nuc2jetson` |
| **Synthetic `jetson2nuc`** | Jetson & NUC | Jetson (Pub): `python3 dummy_publisher.py --topology jetson2nuc --freq 30 --payload 600000 --samples 0`<br>NUC (GUI): `python3 network_monitor_gui.py --ros-args -p topology:=jetson2nuc` |
| **Passive IMU OpenCR** | NUC / Jetson | `python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/robotis/open_cr/imu -p target_hz:=125.0` |
| **Passive Joint States** | NUC / Jetson | `python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/robotis/present_joint_states -p target_hz:=50.0` |
| **Passive Camera Stream**| NUC / Jetson | `python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/camera/image_raw -p target_hz:=30.0` |
| **Passive Cmd Vel** | NUC / Jetson | `python3 network_monitor_gui.py --ros-args -p mode:=passive -p topic_name:=/cmd_vel -p target_hz:=10.0` |
| **Generate Report** | NUC / Jetson | `python3 plot_report.py` |
| **Bebaskan Port 8765** | NUC / Jetson | `fuser -k 8765/tcp` |

---

## 🛡️ FASE 11: BATASAN RUANG LINGKUP PENGUKURAN (*SYSTEM BOUNDARIES*)

Pahami batasan ini agar tidak terjadi kekeliruan analisis data ilmiah:

| Jalur / Komponen | Diukur oleh Monitor? | Penjelasan Teknis & Ruang Lingkup |
| :--- | :---: | :--- |
| 🌐 **Kabel Fisik LAN (NUC ↔ Jetson)** | ✅ **DIUKUR (In-Scope)** | Latensi transmisi paket ($\sim 1.2\text{ ms}$) mencakup serialisasi struct DDS, transport UDP, dan perambatan kabel fisik LAN Cat6. |
| 💻 **Komunikasi Internal (Intra-Host)** | ✅ **DIUKUR (In-Scope)** | Latensi shared-memory / loopback ($\sim 0.7 - 0.8\text{ ms}$) di dalam memori prosesor NUC atau Jetson. |
| ⏱️ **Inter-Arrival Jitter & Overrun ($\Delta t$)** | ✅ **DIUKUR (In-Scope)** | Interval kedatangan frame aktual vs deadline period topik aktif robot. |
| 📶 **SSH / Wi-Fi / ZeroTier Laptop Penguji** | ❌ **TIDAK DIUKUR (Out-of-Scope)** | Jaringan laptop penguji adalah saluran *pengamat telemetri* ($\sim 20 - 100\text{ ms}$), bukan jalur kontrol real-time robot. |
| 🔌 **Serial Bus Dynamixel / OpenCR (U2D2)** | ❌ **TIDAK DIUKUR (Out-of-Scope)** | Transmisi paket UART serial USB ke mikrokontroler OpenCR ($\sim 1 - 3\text{ ms}$) adalah lapisan *hardware bus*, bukan lapisan middleware ROS 2 DDS. |
| 👁️ **Waktu Inferensi AI & Shutter Kamera** | ❌ **TIDAK DIUKUR (Out-of-Scope)** | Eksposur optik sensor ($\sim 20\text{ ms}$) dan beban inferensi YOLO / LLM GPU ($\sim 30\text{ ms}$) adalah *computation time*, bukan *network DDS transmission latency*. |

---
*Dokumen ini diterbitkan untuk standardisasi pengujian tim robotika BRONE Universitas Brawijaya.*
