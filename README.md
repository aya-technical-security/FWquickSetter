# FWquickSetter

Windows Firewall を GUI で確認・変更・証跡出力するためのツール。

## 主な機能

- Firewall ルール一覧表示
- ポート開放・閉鎖
- 危険ポート警告・確認ダイアログ
- ルール検索
- 証跡出力（テキスト）
- 設定エクスポート / インポート（JSON）

## 動作環境

- Windows Server 2022 / 2025
- Python 3.10 以上
- PySide6

## インストール

```powershell
pip install -r requirements.txt
```

## 起動方法

管理者権限で PowerShell を開き、以下を実行。

```powershell
cd C:\FWQ
python app.py
```

管理者権限がない場合はエラーダイアログが表示されて終了します。

## EXE 化

```powershell
cd C:\FWQ
pip install pyinstaller
pyinstaller --onefile --windowed app.py
```

アイコン付き EXE 化（`assets\icons\fw.ico` を用意した場合）：

```powershell
pyinstaller --onefile --windowed --icon=assets\icons\fw.ico app.py
```

完成場所：`C:\FWQ\dist\app.exe`

## ディレクトリ構成

```
C:\FWQ\
├── app.py                  # エントリポイント
├── requirements.txt
├── README.md
├── assets\
│   └── icons\
│       └── fw.ico
├── config\
│   └── app_settings.json   # 設定ファイル
├── core\
│   ├── firewall.py         # ルール取得
│   ├── powershell_runner.py
│   ├── evidence.py
│   └── logger.py
├── ui\
│   ├── main_window.py      # メインウィンドウ
│   ├── style.qss           # スタイルシート
│   └── widgets.py
├── powershell\
│   ├── open_port.ps1
│   ├── close_port.ps1
│   ├── delete_rule.ps1
│   ├── get_fw_status.ps1
│   ├── get_rules.ps1
│   ├── export_rules.ps1
│   └── import_rules.ps1
└── output\
    ├── evidence\           # 証跡ファイル出力先
    └── exports\            # 設定エクスポート先
```