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
export CYCLONEDDS_URI=file://$(pwd)/cyclonedds_jetson.xml

python3 dummy_publisher.py --topology jetson2nuc --samples 0
```

**Terminal 2 NUC (Web GUI Monitor):**
```bash
ssh -L 8765:127.0.0.1:8765 brone-ub@10.101.143.111
source /opt/ros/jazzy/setup.bash
cd ~/ros2_network_monitor
export CYCLONEDDS_URI=file://$(pwd)/cyclonedds_nuc.xml

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
export CYCLONEDDS_URI=file://$(pwd)/cyclonedds_nuc.xml

python3 dummy_publisher.py --topology nuc2jetson --samples 0
```

**Terminal 2 JETSON (Web GUI Monitor):**
```bash
ssh -L 8765:127.0.0.1:8765 brone@10.101.143.169
source /opt/ros/humble/setup.bash
cd ~/ros2_network_monitor
export CYCLONEDDS_URI=file://$(pwd)/cyclonedds_jetson.xml

python3 network_monitor_gui.py --ros-args -p topology:=nuc2jetson
```
👉 *Buka Browser: `http://10.101.143.169:8765`.*

*(Atau Metode CLI Auto-CSV di Jetson: `python3 network_monitor.py --topology nuc2jetson --samples 1000`)*

---

## 📊 FASE 2: Pembuatan Grafik & Laporan Otomatis

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
