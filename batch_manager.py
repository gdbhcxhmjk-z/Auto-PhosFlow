#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import csv
import glob
import requests  # <--- 需要安装
import traceback
from pathlib import Path
from datetime import datetime, timedelta

# 引入核心工作流类
from workflow_manager import MoleculeFlow

# ================= 配置区域 =================
SOURCE_DIR = Path("molecules")       # 分子源目录
RESULTS_DIR = Path("results")        # 结果目录
STATUS_FILE = Path("status_report.csv") # 进度记录文件

MAX_CONCURRENT = 10                  # 并行度
CHECK_INTERVAL = 300                 # 轮询间隔 (秒)

# --- 报警配置 (飞书) ---
ENABLE_ALERT = True
# 替换为你的飞书 Webhook 地址
WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/8295e851-d6ae-4eba-bb08-4ba2cd1579e3"
TIMEOUT_THRESHOLD_HOURS = 48         # 超时阈值 (小时)
# ===========================================

class BatchController:
    def __init__(self):
        self.db = {} 
        self._load_db()
        
        SOURCE_DIR.mkdir(exist_ok=True)
        RESULTS_DIR.mkdir(exist_ok=True)

    def _load_db(self):
        if not STATUS_FILE.exists():
            self._init_csv()
            return
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.db[row['Name']] = row

    def _init_csv(self):
        with open(STATUS_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Status', 'Current_Stage', 'Last_Updated', 'Remark'])

    def _save_db(self):
        with open(STATUS_FILE, 'w', encoding='utf-8', newline='') as f:
            headers = ['Name', 'Status', 'Current_Stage', 'Last_Updated', 'Remark']
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for name in sorted(self.db.keys()):
                writer.writerow(self.db[name])

    # === 核心：飞书报警函数 ===
    def send_feishu_alert(self, title, message):
        """
        发送飞书报警。
        注意：内容中必须包含关键词 'Alert' 才能通过安全校验。
        """
        if not ENABLE_ALERT: return
        
        print(f"  [ALERT] {title}: {message}")
        
        # 构造符合飞书要求的文本 (必须包含 Alert)
        full_text = f"🚨 [Auto-PhosFlow Alert]\n**{title}**\n----------------\n{message}\n\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        data = {
            "msg_type": "text",
            "content": {
                "text": full_text
            }
        }
        
        try:
            resp = requests.post(WEBHOOK_URL, json=data, timeout=10)
            if resp.status_code != 200:
                print(f"  [Error] Feishu API returned {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"  [Error] Failed to send Feishu webhook: {e}")

    def scan_new_molecules(self):
        xyz_files = glob.glob(str(SOURCE_DIR / "*.xyz"))
        new_count = 0
        for p in xyz_files:
            name = Path(p).stem
            if name not in self.db:
                self.db[name] = {
                    'Name': name,
                    'Status': 'PENDING',
                    'Current_Stage': 'Init',
                    'Last_Updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'Remark': 'Newly added'
                }
                new_count += 1
        
        if new_count > 0:
            print(f"  [Scanner] Found {new_count} new molecules.")
            self._save_db()

    def determine_stage(self, flow):
        if (flow.root / "REPORT_PLQY.txt").exists(): return "Analysis Done"
        if (flow.dirs['kic'] / "job.done").exists(): return "MOMAP Kic Done"
        if (flow.dirs['kisc'] / "job.done").exists(): return "MOMAP Kisc Done"
        if (flow.dirs['kr'] / "job.done").exists(): return "MOMAP Kr Done"
        if (flow.dirs['orca'] / "job.done").exists(): return "ORCA Done"
        if (flow.dirs['t1_opt'] / "job.done").exists(): return "Gaussian T1 Done"
        if (flow.dirs['s1_opt'] / "job.done").exists(): return "Gaussian S1 Done"
        if (flow.dirs['s0_freq'] / "job.done").exists(): return "Gaussian S0 Done"
        return "Starting / In Progress"

    def run_watchdog(self):
        """看门狗：检查超时任务"""
        print("  [Watchdog] Checking task health...")
        now = datetime.now()
        
        for name, data in self.db.items():
            if data['Status'] == 'RUNNING':
                try:
                    last_update = datetime.strptime(data['Last_Updated'], "%Y-%m-%d %H:%M:%S")
                    delta = now - last_update
                    hours_running = delta.total_seconds() / 3600
                    
                    # 如果运行时间超过阈值，且之前没有报过警（避免刷屏，这里简单用 Remark 判断）
                    if hours_running > TIMEOUT_THRESHOLD_HOURS:
                        if "Timeout Alert Sent" not in data['Remark']:
                            msg = f"分子 {name} 已卡住 {hours_running:.1f} 小时。\n当前阶段: {data['Current_Stage']}"
                            self.send_feishu_alert("任务超时警告 (Timeout)", msg)
                            
                            # 标记已报警，防止下次循环重复发
                            self.db[name]['Remark'] += " [Timeout Alert Sent]"
                except:
                    pass

    def run_cycle(self):
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === Starting Schedule Cycle ===")
        
        self.scan_new_molecules()
        
        running_jobs = [name for name, data in self.db.items() if data['Status'] == 'RUNNING']
        print(f"  [Status] Active: {len(running_jobs)} / Limit: {MAX_CONCURRENT}")

        # 填补空缺
        slots_available = MAX_CONCURRENT - len(running_jobs)
        if slots_available > 0:
            pending_mols = [name for name, data in self.db.items() if data['Status'] == 'PENDING']
            to_activate = pending_mols[:slots_available]
            for name in to_activate:
                self.db[name]['Status'] = 'RUNNING'
                self.db[name]['Remark'] = 'Activated'
                print(f"  [Activate] Molecule '{name}' moved to RUNNING queue.")
            running_jobs.extend(to_activate)

        if not running_jobs:
            print("  [Idle] No active tasks. Waiting for new files...")
            return

        for name in running_jobs:
            xyz_path = SOURCE_DIR / f"{name}.xyz"
            
            if not xyz_path.exists():
                msg = f"源文件丢失: {name}.xyz"
                print(f"  [Warn] {msg}")
                self.db[name]['Status'] = 'FAILED'
                self.db[name]['Remark'] = 'XYZ Missing'
                self.send_feishu_alert("文件丢失错误", msg) # <--- 报警
                continue

            try:
                flow = MoleculeFlow(name, xyz_path, RESULTS_DIR)
                
                # 检查致命错误
                if flow._is_failed():
                     self.db[name]['Status'] = 'FAILED'
                     # 读取具体错误原因
                     try:
                         with open(flow.error_file, 'r') as ef:
                             err_msg = ef.read().strip()
                     except:
                         err_msg = "Unknown Fatal Error"
                     
                     self.db[name]['Remark'] = 'Fatal Error'
                     # <--- 发送报警
                     self.send_feishu_alert(f"计算失败: {name}", f"原因: {err_msg[-200:]}") # 只发最后200字符
                
                # 检查完成
                elif (flow.root / "REPORT_PLQY.txt").exists():
                    self.db[name]['Status'] = 'COMPLETED'
                    self.db[name]['Current_Stage'] = 'Finished'
                    self.db[name]['Remark'] = 'PLQY Report Generated'
                    # 可选：完成后也发个喜报
                    # self.send_feishu_alert("任务完成", f"分子 {name} 计算结束。")
                
                else:
                    # 正常推进
                    flow.process()
                    current_stage = self.determine_stage(flow)
                    self.db[name]['Current_Stage'] = current_stage
                    self.db[name]['Remark'] = 'Processing'

            except Exception as e:
                err_msg = f"未捕获异常: {str(e)}"
                print(f"  [Error] {err_msg}")
                traceback.print_exc()
                
                self.db[name]['Status'] = 'ERROR'
                self.db[name]['Remark'] = str(e)[:50]
                self.send_feishu_alert(f"程序崩溃: {name}", err_msg) # <--- 报警

            self.db[name]['Last_Updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._save_db()
        
        # 执行超时检查
        self.run_watchdog()
        
        print(f"  [Cycle] Finished.")

if __name__ == "__main__":
    controller = BatchController()
    
    print(f"🚀 Auto-PhosFlow Batch Manager Started.")
    print(f"   Webhook: {WEBHOOK_URL[:30]}...")
    print("-" * 50)
    
    # 启动时先发一条测试消息，确认配置正确
    # controller.send_feishu_alert("系统启动", "Batch Manager 已上线，开始监控任务。")

    try:
        while True:
            controller.run_cycle()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n🛑 Manager stopped by user.")
        controller._save_db()
