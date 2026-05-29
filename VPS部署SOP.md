# 藥局營收管理工具 — VPS 部署 SOP

> 目的：把目前運行於 Streamlit Community Cloud 的應用，遷移到自有 VPS 上長期運作。
>
> 假設環境：
> - VPS 為 Ubuntu 22.04 / Debian 12（其他發行版指令略有不同）
> - 你已申請好一個網域名（例如 `pharmacy.example.com`）並把 A record 指向 VPS IP
> - 本機（Windows）已能用 SSH 連到 VPS

---

## 架構總覽

```
[使用者瀏覽器]
       │  HTTPS
       ▼
[VPS:443 nginx 反向代理]
       │  HTTP (僅 127.0.0.1)
       ▼
[VPS:8501 Streamlit (systemd 常駐)]
       │  Google Sheets API
       ▼
[Google Sheets 試算表（資料儲存）]
```

---

## ⚠️ 遷移前必須先處理

### Bug 1：`requirements.txt` 缺 `tenacity`
- `database.py:9` 有 `from tenacity import retry, ...`
- 但 `requirements.txt` 沒列 `tenacity`
- Streamlit Cloud 環境可能預裝過所以沒事，VPS 純淨環境會直接 ImportError

**處理方式**：在 `requirements.txt` 結尾加一行 `tenacity`，commit 推到 GitHub，再到 VPS 拉取。

### 機密資料不在 Git（這是對的）
`.gitignore` 已排除：
- `.streamlit/secrets.toml`（Google Sheets 連線設定）
- `金鑰/`（GCP service account JSON）

→ 必須另外用 `scp` 從本機上傳到 VPS。

---

## Step 0 — 本機準備

### 0-1. 修 `requirements.txt`
打開 `requirements.txt`，最後加一行：
```
tenacity
```
推到 GitHub：
```bash
git add requirements.txt
git commit -m "Add missing tenacity to requirements.txt"
git push
```

### 0-2. 確認本機有需要上傳的檔案
- `.streamlit/secrets.toml`
- `金鑰/` 整個資料夾

---

## Step 1 — VPS 基礎環境

SSH 進 VPS 後：
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git nginx ufw
```

---

## Step 2 — 建立專案目錄與 Clone

```bash
sudo mkdir -p /opt/pharmacy
sudo chown $USER:$USER /opt/pharmacy
cd /opt
git clone https://github.com/mark780825/pharmacy-revenue-tool.git pharmacy
cd pharmacy
```

---

## Step 3 — Python 虛擬環境與依賴

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> 若還沒修 `requirements.txt`，需手動補：`pip install tenacity toml`

---

## Step 4 — 從本機上傳憑證

在**本機 PowerShell**（Windows 端）執行（把 `VPS_USER` 和 `VPS_IP` 換成實際值）：

```powershell
# 切到專案資料夾
cd "C:\Users\mark7\Documents\My Work\Project\藥局營收管理工具"

# 上傳 Streamlit secrets
scp ".streamlit/secrets.toml" VPS_USER@VPS_IP:/opt/pharmacy/.streamlit/

# 上傳 GCP 金鑰資料夾
scp -r "金鑰" VPS_USER@VPS_IP:/opt/pharmacy/
```

回到 VPS，收緊權限（防止其他使用者讀取憑證）：
```bash
chmod 600 /opt/pharmacy/.streamlit/secrets.toml
chmod -R 700 /opt/pharmacy/金鑰
```

---

## Step 5 — 手動試跑驗證

```bash
cd /opt/pharmacy
source venv/bin/activate
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
```

打開瀏覽器訪問 `http://VPS_IP:8501`：
- 能登入並讀取 Google Sheets → ✅ 成功
- 出現連線錯誤 → 檢查 `.streamlit/secrets.toml` 是否上傳成功、Google Sheet 是否有授權給該 service account

Ctrl+C 結束。

---

## Step 6 — 包成 systemd Service

建立 `/etc/systemd/system/pharmacy.service`：
```bash
sudo nano /etc/systemd/system/pharmacy.service
```

貼入內容（把 `YOUR_USER` 換成實際 VPS 使用者名稱）：
```ini
[Unit]
Description=Pharmacy Revenue Tool (Streamlit)
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/opt/pharmacy
Environment="PATH=/opt/pharmacy/venv/bin"
ExecStart=/opt/pharmacy/venv/bin/streamlit run app.py \
  --server.port=8501 \
  --server.address=127.0.0.1 \
  --server.headless=true \
  --browser.gatherUsageStats=false
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

啟用：
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pharmacy
sudo systemctl status pharmacy    # 應顯示 active (running)
```

監看 log：
```bash
journalctl -u pharmacy -f
```

---

## Step 7 — nginx 反向代理

> ⚠️ Streamlit 依賴 WebSocket。若沒設定 `Upgrade` / `Connection "upgrade"`，網頁會無限轉圈、按鈕無反應。

建立 `/etc/nginx/sites-available/pharmacy`：
```bash
sudo nano /etc/nginx/sites-available/pharmacy
```

貼入（把 `pharmacy.example.com` 換成你的網域）：
```nginx
server {
    listen 80;
    server_name pharmacy.example.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket — 缺這三行 Streamlit 會壞
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

啟用站點：
```bash
sudo ln -s /etc/nginx/sites-available/pharmacy /etc/nginx/sites-enabled/
sudo nginx -t                    # 必須顯示 syntax is ok
sudo systemctl reload nginx
```

---

## Step 8 — HTTPS（Let's Encrypt 免費憑證）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d pharmacy.example.com
```

依提示輸入 email、同意條款。certbot 會自動修改 nginx 設定加入 SSL 並重啟。

驗證自動續期：
```bash
sudo systemctl status certbot.timer    # 應為 active
sudo certbot renew --dry-run           # 模擬續期，應成功
```

---

## Step 9 — 防火牆

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

## 部署完成驗證清單

- [ ] `https://pharmacy.example.com` 可開啟，瀏覽器顯示有效 HTTPS 鎖頭
- [ ] 用 admin 帳號登入正常
- [ ] 用 staff 帳號登入正常
- [ ] 新增一筆交易後，刷新頁面可看到
- [ ] 開 Google Sheet 後台確認新列已寫入
- [ ] `sudo reboot` 後，pharmacy 服務自動啟動
- [ ] `journalctl -u pharmacy --since "10 min ago"` 沒有 Error / Traceback

---

## 日後更新工作流

寫好新功能 → 推 GitHub → SSH 進 VPS：
```bash
cd /opt/pharmacy
git pull
source venv/bin/activate
pip install -r requirements.txt    # 若依賴有變
sudo systemctl restart pharmacy
journalctl -u pharmacy -n 50       # 看啟動 log 確認無誤
```

---

## 常見問題排查

| 症狀 | 可能原因 | 解法 |
|---|---|---|
| 網頁無限轉圈 | nginx 沒設 WebSocket | 檢查 Step 7 的 Upgrade header |
| 502 Bad Gateway | Streamlit 沒在跑 | `sudo systemctl status pharmacy` 看狀態與 log |
| 登入後讀不到資料 | secrets.toml 沒上傳或路徑錯 | 檢查 `/opt/pharmacy/.streamlit/secrets.toml` 存在且 chmod 600 |
| ImportError tenacity | 沒裝相依套件 | `source venv/bin/activate && pip install tenacity` |
| Google API 403 | service account 沒授權給該試算表 | 把 service account 的 email 加入 Google Sheet 的共用清單（編輯權限）|
| 改完程式碼 VPS 沒更新 | 沒重啟 service | `sudo systemctl restart pharmacy` |

---

## 額外建議（非必要但推薦）

1. **每日 Google Sheet 備份**：cron 排程用 `gspread` dump 整份試算表為 CSV，避免誤刪後無法救回。
2. **fail2ban**：保護 SSH 免受暴力破解。
3. **Swap 檔**：1GB RAM 的 VPS 建議開 2GB swap，避免 pandas 載入大檔時 OOM。
4. **Cloudflare 代理**：放在 VPS 前面隱藏真實 IP，並擋部分掃描攻擊。
5. **監控**：用 UptimeRobot 之類免費服務每 5 分鐘 ping 一次，掛掉時 email 通知。
