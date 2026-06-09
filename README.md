# 全台灣露營區風險監測 Demo

以 GitHub Pages 發布的全台灣露營區風險監測展示網站。專案整合露營場點位、中央氣象署雨量、土石流與崩塌潛勢、聯外道路、河川距離、斷層距離、坡度與法規治理資訊，並以 AHP/MCDA 權重計算綜合風險分數。

## 線上展示

- GitHub Pages: <https://hankc0215.github.io/Camp_Project/>
- 主要展示頁: <https://hankc0215.github.io/Camp_Project/index_V1.html>
- 展示分支: `github-pages-v1`

## 目前狀態

- `index.html` 是 GitHub Pages 入口，會自動導向 `index_V1.html`
- 資料檔已集中整理到 `data/`
- 舊版頁面已移到 `legacy/`
- GitHub Actions 每 30 分鐘嘗試更新中央氣象署雨量並重新部署
- 網頁開啟後每 10 分鐘重新讀取一次 `data/real_rainfall.json`
- API key 使用 GitHub Secret `CWA_API_KEY`，不放在前端或 repo 內

## 主要功能

- Leaflet 互動式地圖瀏覽全台露營場風險
- 依縣市、風險等級、法規狀態與關鍵字篩選
- 顯示風險優先清單與單一露營場詳細風險組成
- 疊加道路、斷層、河川、土石流與崩塌圖層
- 套用中央氣象署實測雨量資料
- 動態計算風險統計，避免固定統計數字過期

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

重要分數定義：

- 法規：符合相關法規 = 0；違反/非法 = 50。若 `law_status` 已標示符合，`law_issue` 不再額外加分。
- 雨量：未達大雨 = 0；大雨 `>=80 mm/24h` 或 `>=40 mm/h` = 25；豪雨 `>=200 mm/24h` 或 `>=100 mm/3h` = 50；大豪雨 `>=350 mm/24h` 或 `>=200 mm/3h` = 75；超大豪雨 `>=500 mm/24h` = 100。
- 坡度：坡度百分比 `<10%` = 0；`10-29%` = 50；`>=30%` = 100。
- 土石流：位於潛勢/影響範圍內 = 100；範圍外 = 0。
- 事件型崩塌：`<100m` = 100；`101-250m` = 75；`251-499m` = 25；`>=500m` = 0。
- 河川距離：`<50m` = 100；`50-99m` = 50；`>=100m` = 0。
- 聯外道路：1 條 = 100；2 條 = 50；3 條以上 = 0。
- 斷層：`<250m` = 100；`251-500m` = 75；`500-999m` = 25；`>=1000m` = 0。

風險等級分為：

- `立即撤離`: 極端雨量、綜合分數極高，或豪雨疊加土石流/崩塌/河川/道路等高脆弱條件
- `預警撤離`: 豪雨、綜合分數偏高，或土石流範圍內且疊加近河川/道路替代性低等條件
- `加強監測`: 大雨、近災害範圍、近河川、坡度高或多項風險條件接近門檻
- `正常監測`: 未達上述條件，維持一般天候與撤離路線確認

分級不只看單一綜合分數，也加入關鍵條件觸發，避免 AHP 加權平均把高風險情境稀釋掉。

## 專案結構

| 路徑 | 說明 |
| --- | --- |
| `index.html` | GitHub Pages 入口頁，導向 `index_V1.html` |
| `index_V1.html` | 目前主要展示頁 |
| `data/` | 露營場、雨量、道路、災害、河川與斷層資料 |
| `data/demo_data.js` | 露營場與風險主資料 |
| `data/real_rainfall.js` / `data/real_rainfall.json` | 中央氣象署雨量更新結果 |
| `data/road_access.js` / `data/road_access.json` | 聯外道路距離資料 |
| `data/hazard_layers.js` / `data/hazard_layers.json` | 土石流與崩塌圖層資料 |
| `data/road_fault_layers.js` | 道路線與斷層線圖層 |
| `data/river_layers.js` | 河川線與河川面圖層 |
| `legacy/index_legacy.html` | 前一版展示頁 |
| `legacy/offline_map.html` | 離線地圖展示版本 |
| `scripts/` | 資料更新、檢查與本機預覽工具 |
| `.github/workflows/deploy.yml` | GitHub Pages 部署與雨量更新 workflow |
| `.env.example` | 環境變數範例，不包含真實金鑰 |

## 本機預覽

使用 Node.js 靜態伺服器：

```bash
node scripts/static_server.js
```

預設網址：

```text
http://127.0.0.1:8000/index_V1.html
```

也可以使用 Python 伺服器。這個版本包含 `/api/rainfall`，會在請求時嘗試更新雨量：

```bash
python scripts/serve.py
```

## 雨量更新

雨量資料來源：

```text
中央氣象署 CWA O-A0002-001
```

本機更新前請建立 `.env`：

```bash
copy .env.example .env
```

`.env` 範例：

```env
CWA_API_KEY=你的中央氣象署API_KEY
```

更新雨量資料：

```bash
python scripts/update_rainfall.py
```

成功後會更新：

- `data/real_rainfall.json`
- `data/real_rainfall.js`

## GitHub Pages 自動更新

GitHub Pages 是靜態網站，不能在使用者打開網頁時安全地讀取 `.env` 或直接使用私密 API key。因此線上版採用 GitHub Actions 定時更新雨量資料，再重新部署 Pages。

目前 workflow 設定：

- `push` 到 `master` 或 `github-pages-v1` 時部署
- 每 30 分鐘排程執行一次
- 部署前執行 `scripts/update_rainfall.py`
- 若未設定 `CWA_API_KEY` secret，會沿用既有雨量檔部署

Repository Secret:

```text
CWA_API_KEY
```

請勿提交：

- `.env`
- API key
- 個人本機暫存檔
- 瀏覽器 profile 或 server log

## 檢查網站

檢查 `index_V1.html` 的本地 script、重複 id 與 inline JavaScript 語法：

```bash
node scripts/audit_site.js
```

## 資料更新工具

| 指令 | 用途 |
| --- | --- |
| `python scripts/update_rainfall.py` | 更新中央氣象署雨量資料 |
| `node scripts/update_rainfall.js` | Node.js 版本雨量更新 |
| `python scripts/update_road_access.py` | 更新聯外道路距離資料 |
| `python scripts/update_hazard_layers.py` | 更新土石流/崩塌圖層資料 |
| `node scripts/audit_site.js` | 檢查展示頁基本結構 |

## 備註

`index_V1.html` 已將大型內嵌資料拆成獨立資料檔，讓 HTML 本身更乾淨，也更適合 GitHub Pages 展示與後續維護。
