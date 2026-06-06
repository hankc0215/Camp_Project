# 全台灣露營區風險監測 Demo

這是一個以靜態網頁呈現的全台灣露營區風險監測展示專案。網站整合露營場點位、中央氣象署雨量資料、土石流/崩塌潛勢、聯外道路、河川距離、斷層距離、坡度與法規治理資訊，並以 AHP/MCDA 權重計算各露營場的綜合風險分數。

目前主要展示版本為：

- `index_V1.html`

## 主要功能

- 互動式 Leaflet 地圖瀏覽全台露營場風險
- 依縣市、風險等級、法規狀態與排序條件篩選
- 顯示高風險露營場清單與詳細風險組成
- 疊加土石流、崩塌、道路、河川與斷層圖層
- 支援中央氣象署雨量資料更新
- 風險統計採動態計算，避免固定統計數字過期

## 風險評分架構

本版使用 AHP/MCDA 權重整合多項風險因子：

| 因子 | 權重 |
| --- | ---: |
| 雨量 | 28.8% |
| 土石流距離 | 14.7% |
| 事件型崩塌距離 | 14.7% |
| 法規/治理狀態 | 14.3% |
| 聯外道路距離 | 14.3% |
| 坡度 | 5.6% |
| 河川距離 | 5.6% |
| 斷層距離 | 2.0% |

風險等級大致分為：

- `critical`：立即/優先關注
- `high`：高風險
- `medium`：中風險
- `low`：低風險

## 專案檔案

| 檔案/資料夾 | 說明 |
| --- | --- |
| `index_V1.html` | 目前主要展示頁面 |
| `index.html` | GitHub Pages 入口頁，會導向 `index_V1.html` |
| `index_legacy.html` | 原始/前一版展示頁 |
| `offline_map.html` | 離線地圖展示版本 |
| `data/` | 露營場、雨量、道路、災害、河川與斷層資料 |
| `data/demo_data.js` | 露營場與風險主資料 |
| `data/real_rainfall.js` / `data/real_rainfall.json` | 雨量更新結果 |
| `data/road_access.js` / `data/road_access.json` | 聯外道路距離資料 |
| `data/hazard_layers.js` / `data/hazard_layers.json` | 土石流/崩塌圖層資料 |
| `data/road_fault_layers.js` | 道路線與斷層線圖層 |
| `data/river_layers.js` | 河川線與河川面圖層 |
| `legacy/` | 舊版或離線展示頁面 |
| `scripts/` | 資料更新、檢查與本機預覽工具 |
| `.env.example` | 環境變數範例，不包含真實金鑰 |
| `.gitignore` | 忽略 `.env` 與本機暫存檔 |

## 本機預覽

如果只要預覽靜態展示頁，可以使用內建的 Node.js 靜態伺服器：

```bash
node scripts/static_server.js
```

預設會開在：

```text
http://127.0.0.1:8000/index_V1.html
```

也可以使用 Python 版本的伺服器，這個版本包含 `/api/rainfall`，會在請求時嘗試更新雨量：

```bash
python scripts/serve.py
```

## 更新雨量資料

雨量資料來源為中央氣象署開放資料 API：

```text
CWA O-A0002-001
```

使用前請建立 `.env`，並填入中央氣象署 API key：

```bash
copy .env.example .env
```

`.env` 內容範例：

```env
CWA_API_KEY=你的中央氣象署API_KEY
```

更新雨量資料：

```bash
python scripts/update_rainfall.py
```

或使用 Node.js 版本：

```bash
node scripts/update_rainfall.js
```

成功後會更新：

- `data/real_rainfall.json`
- `data/real_rainfall.js`

## GitHub Pages 展示注意事項

這個專案可以放到 GitHub Pages 作為靜態展示網站。若只展示已產生好的資料檔，不需要把 `.env` 放上 GitHub。

請不要提交：

- `.env`
- API key
- 個人本機暫存檔
- 瀏覽器 profile 或 server log

GitHub Pages 是靜態網站，不能在使用者打開網頁時安全地讀取 `.env` 或直接使用私密 API key。因此線上版採用 GitHub Actions 定時更新雨量資料，再重新部署 Pages。

本專案的 `.github/workflows/deploy.yml` 已設定：

- 每 30 分鐘嘗試更新一次中央氣象署雨量資料
- 每次部署前嘗試更新 `data/real_rainfall.json` 與 `data/real_rainfall.js`
- 網頁開啟後每 10 分鐘重新讀取一次 `data/real_rainfall.json`

請在 GitHub repository 設定 Secret：

```text
CWA_API_KEY
```

設定完成後，GitHub Actions 會使用這個 Secret 執行 `scripts/update_rainfall.py`。

設定步驟：

1. 將 `CWA_API_KEY` 放到 GitHub Secrets
2. 由 GitHub Actions 定時執行 `scripts/update_rainfall.py`
3. 自動更新 `data/real_rainfall.json` 與 `data/real_rainfall.js`
4. GitHub Pages 讀取更新後的靜態資料檔

這樣可以保留靜態網站部署的簡單性，同時避免 API key 暴露在前端程式碼中。

## 檢查網站

可執行下列指令檢查 `index_V1.html` 的基本結構、外部資料檔與 inline script 語法：

```bash
node scripts/audit_site.js
```

目前檢查項目包含：

- 重複 `id`
- 本地 script 檔案是否存在
- 遠端 Leaflet CDN 是否被辨識
- inline JavaScript 語法是否正確

## 資料更新工具

| 指令 | 用途 |
| --- | --- |
| `python scripts/update_rainfall.py` | 更新中央氣象署雨量資料 |
| `python scripts/update_road_access.py` | 更新聯外道路距離資料 |
| `python scripts/update_hazard_layers.py` | 更新土石流/崩塌圖層資料 |
| `node scripts/audit_site.js` | 檢查展示頁基本結構 |

## 版本備註

`index_V1.html` 已將大型內嵌資料拆成獨立 JS 檔，讓 HTML 本身更乾淨，也比較適合 GitHub 展示與後續維護。
