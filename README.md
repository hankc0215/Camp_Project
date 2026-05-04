# 全台灣露營區風險監測 Demo｜V5 DEM 坡度＋坡向版

本版本將原本的全台露營區風險監測 Demo 加入 **2025 全台 20m DEM** 地形因子：

- 高程 elevation
- 坡度 slope
- 坡向 aspect
- 坡向迎風暴露分數 aspect exposure score
- 地形分數 terrain score

## 風險分數公式

Demo MCDA = 30% rainfall + 14% DEM slope + 4% aspect exposure + 20% debris-flow distance + 24% landslide-warning/event distance + 8% legal status。

原本的 18% 坡度權重被拆成：

- 14% 坡度
- 4% 坡向迎風暴露

坡向分數是展示用假設：東到東南向坡面在颱風／地形雨情境下給予較高迎風暴露分數。正式系統應改用即時風向與降雨雷達資料。

## 使用方式

1. 解壓縮整個資料夾。
2. 開啟 `index.html`。
3. 若現場網路不穩，開啟 `offline_map.html` 作為備援展示。

## 本版統計

- 有效露營場點位：1,737
- 立即撤離：1
- 預警撤離：34
- 加強監測：376
- 正常監測：1,326

## 產出檔案

- `index.html`：互動地圖版
- `offline_map.html`：離線備援版
- `all_taiwan_camping_risk_demo.csv`：含 DEM 坡度與坡向欄位的風險分級表
- `demo_payload.json`：網頁展示資料
