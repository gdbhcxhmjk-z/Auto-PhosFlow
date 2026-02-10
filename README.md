# Auto-PhosFlow: Automated Phosphorescence Analysis Workflow

**Auto-PhosFlow** is a robust, high-throughput automated workflow designed to calculate the Photoluminescence Quantum Yield (PLQY) and phosphorescence rates ($k_r, k_{isc}, k_{ic}$) for organometallic complexes (e.g., Ir, Pt complexes).

It integrates **Gaussian 16**, **ORCA**, and **MOMAP** into a unified pipeline, featuring smart error recovery, batch scheduling, and real-time alerts.

## 🌟 Key Features

* **Full Automation**: End-to-end pipeline from `.xyz` structure to PLQY report.
    * Protocol: S0 Opt → S1 Opt (TD-DFT) → T1 Opt (U-DFT) → SOC (ORCA) → Rates (MOMAP).
* **Smart Recovery**:
    * Automatically detects imaginary frequencies and retries with `opt=calcall`.
    * Intelligent decision-making based on job execution time.
* **Batch Management**:
    * **Concurrency Control**: Limits active jobs (e.g., max 10) to protect cluster resources.
    * **Incremental Scanning**: Automatically detects new `.xyz` files added to the source folder.
* **Real-time Monitoring**:
    * **Feishu/Lark Alerts**: Sends notifications for timeouts, fatal errors, or file missing events.
    * **Watchdog**: Monitors "zombie" tasks and execution timeouts.
* **Publication-Quality Output**:
    * Automatic PLQY calculation.
    * Generates spectrum plots with `Times New Roman` styling.

## 🛠️ Prerequisites

### Software
* **Python 3.8+**
* **Gaussian 16** (Rev. C.01 or later recommended)
* **ORCA** (5.0+)
* **MOMAP** (Molecular Materials Property Prediction Package)
* **OpenBabel** (for geometry extraction)

### Python Dependencies
```bash
pip install numpy matplotlib requests
```
## 🚀 Quick Start

### 1. Configuration
Edit `config.py` to set up environment paths and calculation parameters. Note the separate memory controls for optimization and frequency steps:

```python
# config.py
G16_PARAMS = {
    'nproc': 56,
    'mem_opt': "128GB",   # Memory for Optimization
    'mem_freq': "180GB",  # Memory for Frequency (Higher recommended)
    # ...
}

# Set your Feishu Webhook URL for alerts (Ensure the bot has "Alert" keyword enabled)
WEBHOOK_URL = "[https://open.feishu.cn/open-apis/bot/v2/hook/](https://open.feishu.cn/open-apis/bot/v2/hook/)..."
```
### 2. Prepare Molecules
Place your initial molecular structures (`.xyz` format) into the `molecules/` directory.

### 3. Run the Manager
Start the batch controller in the background (using `nohup` is recommended for long-running tasks):
```bash
nohup python batch_manager.py > manager.log 2>&1 &
```
## 📂 Project Structure
```Plaintext
.
├── batch_manager.py      # [Entry Point] Daemon for scheduling and monitoring
├── workflow_manager.py   # Core Logic: Steps execution (Gaussian -> ORCA -> MOMAP)
├── config.py             # Configuration: Paths, Keywords, Resources, Alerts
├── lib/                  # Library functions
│   ├── g16_handler.py    # Gaussian input generation & log parsing
│   ├── orca_handler.py   # ORCA SOC input generation
│   ├── momap_handler.py  # MOMAP input/output handling
│   ├── analysis_handler.py # PLQY calc & Plotting
│   └── slurm_utils.py    # Slurm script generation
├── molecules/            # [Input] Folder for .xyz files
└── results/              # [Output] Auto-generated results folder
```

## 🔧 Manager Operation Guide

Since `batch_manager.py` runs as a background daemon, here is how to manage it effectively.

### 1. Monitoring Progress
* **Real-time Logs**:
    To see what the script is doing right now (polling, submitting jobs, or errors):
    ```bash
    tail -f manager.log
    ```
* **Status Report (Excel/CSV)**:
    Check `status_report.csv` in the root directory. It lists the status (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`) of every molecule.

### 2. Adding New Tasks
* Simply upload new `.xyz` files to the `molecules/` folder.
* The manager scans for new files every 5 minutes (configurable via `CHECK_INTERVAL` in `batch_manager.py`) and adds them to the queue automatically.

### 3. Retrying Failed Tasks
If a molecule fails (e.g., due to a cluster error) and you want to retry it:
1.  Delete its corresponding folder in `results/`.
2.  Open `status_report.csv`.
3.  Delete the row for that molecule (or change status to `PENDING`).
4.  The manager will pick it up again in the next cycle.

### 4. Stopping the Manager
To gracefully stop the background process:

```bash
# Find the Process ID (PID)
ps -ef | grep batch_manager.py

# Kill the process
kill <PID>

