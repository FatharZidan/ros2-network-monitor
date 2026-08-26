# SOP Lengkap Prosedur Pengujian & Pelaporan ROS 2 — BRONE v2

Dokumen ini berisi alur kerja terpadu dari persiapan, eksekusi pengujian 4 skenario, hingga pembuatan laporan grafik visual otomatis untuk robot BRONE.

---

## 🛠️ FASE 0: Persiapan & Sinkronisasi File

### 1. Sinkronkan File Terbaru ke NUC & JETSON
Jalankan dari Windows CMD:
```cmd
cd "C:\Users\Patarajah\Documents\IDE Antigravity\ros2_network_monitor"

REM Kirim ke NUC
scp dummy_publisher.py network_monitor.py network_monitor_gui.py dashboard.html plot_report.py brone-ub@10.101.143.111:~/ros2_network_monitor/

REM Kirim ke JETSON
scp dummy_publisher.py network_monitor.py network_monitor_gui.py dashboard.html plot_report.py brone@10.101.143.169:~/ros2_network_monitor/
```

### 2. Setup Environment Sekali Jalan (Wajib)
Jalankan di terminal **NUC** dan **JETSON**:
```bash
echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> ~/.bashrc
echo "export ROS_DOMAIN_ID=30" >> ~/.bashrc
source ~/.bashrc
```

*(Khusus di Jetson, pastikan paket CycloneDDS terpasang: `sudo apt install -y ros-humble-rmw-cyclonedds-cpp`)*

---

## 🚀 FASE 1: Eksekusi Pengujian (Pilih Skenario)

Tersedia **2 Metode Pengujian**:
- **Metode A (Web GUI Dashboard):** Visualisasi live di browser + Tombol **Download CSV**.
- **Metode B (CLI Batch Runner):** Otomatis berjalan N sampel, berhenti sendiri, dan otomatis membuat file CSV.

---

### Skenario 1: Uji Baseline NUC Internal (`nuc2nuc`)

**Terminal 1 NUC (Publisher):**
```bash
ssh brone-ub@10.101.143.111
source /opt/ros/jazzy/setup.bash
unset CYCLONEDDS_URI
cd ~/ros2_network_monitor

python3 dummy_publisher.py --topology nuc2nuc --samples 0
```

**Terminal 2 NUC (Web GUI Monitor):**
```bash
ssh -L 8765:127.0.0.1:8765 brone-ub@10.101.143.111
source /opt/ros/jazzy/setup.bash
unset CYCLONEDDS_URI
cd ~/ros2_network_monitor

python3 network_monitor_gui.py --ros-args -p topology:=nuc2nuc
```
👉 *Buka Browser: `http://10.101.143.111:8765` (atau `http://localhost:8765`). Klik **"Download CSV"** kapan saja untuk menyimpan data.*

*(Atau Metode CLI Auto-CSV: `python3 network_monitor.py --topology nuc2nuc --samples 1000`)*

---

### Skenario 2: Uji Baseline JETSON Internal (`jetson2jetson`)

**Terminal 1 JETSON (Publisher):**
```bash
ssh brone@10.101.143.169
source /opt/ros/humble/setup.bash
unset CYCLONEDDS_URI
cd ~/ros2_network_monitor

python3 dummy_publisher.py --topology jetson2jetson --samples 0
```

**Terminal 2 JETSON (Web GUI Monitor):**
```bash
ssh -L 8765:127.0.0.1:8765 brone@10.101.143.169
source /opt/ros/humble/setup.bash
unset CYCLONEDDS_URI
cd ~/ros2_network_monitor

python3 network_monitor_gui.py --ros-args -p topology:=jetson2jetson
```
👉 *Buka Browser: `http://10.101.143.169:8765` (atau `http://localhost:8765`).*

*(Atau Metode CLI Auto-CSV: `python3 network_monitor.py --topology jetson2jetson --samples 1000`)*

---

### Skenario 3: Uji Lintas Mesin (JETSON ➔ NUC)

**Terminal 1 JETSON (Publisher):**
```bash
ssh brone@10.101.143.169
source /opt/ros/humble/setup.bash
cd ~/ros2_network_monitor
export CYCLONEDDS_URI=file:///home/brone/ros2_network_monitor/cyclonedds_jetson.xml

python3 dummy_publisher.py --topology jetson2nuc --samples 0
```

**Terminal 2 NUC (Web GUI Monitor):**
```bash
ssh -L 8765:127.0.0.1:8765 brone-ub@10.101.143.111
source /opt/ros/jazzy/setup.bash
cd ~/ros2_network_monitor
export CYCLONEDDS_URI=file:///home/brone-ub/ros2_network_monitor/cyclonedds_nuc.xml

python3 network_monitor_gui.py --ros-args -p topology:=jetson2nuc
```
👉 *Buka Browser: `http://10.101.143.111:8765`.*

*(Atau Metode CLI Auto-CSV di NUC: `python3 network_monitor.py --topology jetson2nuc --samples 1000`)*

---

### Skenario 4: Uji Lintas Mesin (NUC ➔ JETSON)

**Terminal 1 NUC (Publisher):**
```bash
ssh brone-ub@10.101.143.111
source /opt/ros/jazzy/setup.bash
cd ~/ros2_network_monitor
export CYCLONEDDS_URI=file:///home/brone-ub/ros2_network_monitor/cyclonedds_nuc.xml

python3 dummy_publisher.py --topology nuc2jetson --samples 0
```

**Terminal 2 JETSON (Web GUI Monitor):**
```bash
ssh -L 8765:127.0.0.1:8765 brone@10.101.143.169
source /opt/ros/humble/setup.bash
cd ~/ros2_network_monitor
export CYCLONEDDS_URI=file:///home/brone/ros2_network_monitor/cyclonedds_jetson.xml

python3 network_monitor_gui.py --ros-args -p topology:=nuc2jetson
```
👉 *Buka Browser: `http://10.101.143.169:8765`.*

*(Atau Metode CLI Auto-CSV di Jetson: `python3 network_monitor.py --topology nuc2jetson --samples 1000`)*

---

## Skenario 5: Stress Test (Isolasi Variabel)

Gunakan metode ini untuk mencari titik batas maksimal latensi sistem. **Sangat disarankan menggunakan Metode B (CLI)** agar sistem tidak terbebani oleh rendering GUI saat stres tinggi. 

**ATURAN EMAS:** Ubah hanya SATU variabel dalam satu waktu. Kunci *payload* saat *sweeping* frekuensi, dan kunci frekuensi saat *sweeping payload*.

### A. Sweeping Frekuensi (Kunci Payload di 128 Bytes)
Bertujuan mencari batas maksimal Hz yang bisa ditangani jaringan sebelum *miss rate* muncul.
*(Contoh di bawah menggunakan NUC lokal. Sesuaikan `--topology` jika mencoba di Jetson).*

```bash
# Level 1: 100 Hz
python3 dummy_publisher.py --topology nuc2nuc --freq 100 --payload 128 --samples 2000
python3 network_monitor.py --topology nuc2nuc --freq 100 --payload 128 --samples 2000

# Level 2: 500 Hz
python3 dummy_publisher.py --topology nuc2nuc --freq 500 --payload 128 --samples 5000
python3 network_monitor.py --topology nuc2nuc --freq 500 --payload 128 --samples 5000

# Level 3: 1000 Hz (Extreme)
python3 dummy_publisher.py --topology nuc2nuc --freq 1000 --payload 128 --samples 10000
python3 network_monitor.py --topology nuc2nuc --freq 1000 --payload 128 --samples 10000
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

Setelah pengujian menghasilkan satu atau beberapa file `brone_log_*.csv`, buat laporan visual lengkap dengan tool `plot_report.py`.

### 1. Eksekusi Generator Laporan (di NUC atau JETSON)
```bash
cd ~/ros2_network_monitor

# Memproses semua file CSV yang ada di folder:
python3 plot_report.py
```

### 2. Output yang Dihasilkan:
1. 📑 **`brone_report_YYYYMMDD_HHMMSS.html` (Laporan Interaktif):**
   - Kartu Metrik Latensi (Avg, Min, Max, p95, p99) & Miss Rate per skenario.
   - Tabel ringkasan komparasi.
   - Grafik batang perbandingan latensi & kestabilan Hz.
   - Grafik riwayat *time-series* latensi per detik.
   - Tombol **"🖨️ Cetak / Simpan PDF"** siap lampiran dokumen resmi riset.
2. 🖼️ **`brone_report_YYYYMMDD_HHMMSS.png`:** Grafik resolusi tinggi (300 DPI).

---

## 💡 Tips: Membuka File CSV di Excel Windows
Jika file CSV dibuka di Excel dan seluruh data berada dalam Kolom A:
1. Blok **Kolom A**.
2. Pilih tab menu **Data** ➔ klik **Text to Columns**.
3. Pilih **Delimited** ➔ Next ➔ Centang **Comma** ➔ Klik **Finish**.

---

## ⏰ Solusi Jika Muncul Latensi Minus (Clock Skew)

### Kapan Perlu Sinkronisasi Jam?
- **Uji Lokal Standalone (`jetson2jetson` / `nuc2nuc` / Omniwheel):** ❌ **TIDAK PERLU**. Menggunakan 1 hardware CPU yang sama (`perf_counter_ns`), clock homogen dan bebas dari clock skew.
- **Uji Lintas Mesin (`jetson2nuc` / `nuc2jetson`):** ✅ **DIBUTUHKAN** jika jam sistem NUC dan Jetson memiliki selisih waktu (offset).

### 🛠️ Cara Sinkronisasi Presisi Tinggi (Aman untuk ROS 2 / TF2)
Jika di monitor muncul nilai latensi negatif (misal `-3.2 ms`):

1. **Di Terminal NUC (Master Clock):**
   ```bash
   sudo apt install -y chrony
   # Sinkronkan NUC ke NTP internet (jika ada) atau jadikan master lokal:
   sudo chronyd -q 'server pool.ntp.org iburst'
   ```

2. **Di Terminal JETSON (Client Clock):**
   ```bash
   sudo apt install -y chrony
   # Sinkronkan langsung ke IP NUC:
   sudo chronyd -q 'server 10.101.143.111 iburst'
   ```

> 🛡️ **Mengapa Aman untuk ROS 2?**
> `chrony` menggunakan metode **Clock Slewing** (menyesuaikan kecepatan kristal mikrodetik secara halus tanpa lompatan waktu kasar seperti `ntpdate`), sehingga **Transform Tree (TF2), Odometri, dan State Machine Robotis OP3 tetap 100% stabil dan tidak akan mengalami error waktu.**

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
