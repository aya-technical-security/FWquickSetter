from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QTextEdit,
    QHeaderView, QSizePolicy, QFrame,
    QMessageBox, QFileDialog, QInputDialog,
)
from PySide6.QtCore import Qt
from datetime import datetime
import json
import os

from core.powershell_runner import run_powershell_script
from core.firewall import get_enabled_firewall_rules


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FWquickSetter")
        self.resize(1600, 960)
        self.setMinimumSize(1200, 800)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("ここに操作ログが表示されます。")
        self.log_box.setFixedHeight(80)

        self.setup_ui()

    # ==================================================================
    # 危険ポート判定
    # ==================================================================
    def is_danger_port(self, port):
        return str(port) in ["21", "23", "135", "139", "445", "3389"]

    def confirm_danger_port(self, port, protocol):
        if not self.is_danger_port(port):
            return True
        result = QMessageBox.warning(
            self,
            "危険ポートの開放確認",
            f"{protocol}/{port} は危険ポートです。\n\n本当に開放しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return result == QMessageBox.Yes

    # ==================================================================
    # ポート開放
    # ==================================================================
    def open_port(self, port, protocol):
        if not self.confirm_danger_port(port, protocol):
            self.log_box.append(f"CANCELLED: {protocol}/{port} の開放を中止しました。")
            return
        stdout, stderr = run_powershell_script(
            "powershell/open_port.ps1",
            ["-Port", str(port), "-Protocol", protocol]
        )
        if stdout:
            self.log_box.append(stdout.strip())
        if stderr:
            self.log_box.append(stderr.strip())

    # ==================================================================
    # ルール一覧の読み込み
    # ==================================================================
    def load_firewall_rules(self):
        from PySide6.QtWidgets import QApplication
        self.log_box.append("INFO: ファイアウォールルールを読み込み中...")
        QApplication.processEvents()

        rules, error = get_enabled_firewall_rules()

        if error:
            self.log_box.append(f"ERROR: {error}")
            return

        if not rules:
            self.log_box.append("WARN: ルールが0件でした（管理者権限で起動しているか確認してください）")
            return

        self.rule_table.setRowCount(0)

        for row, rule in enumerate(rules):
            self.rule_table.insertRow(row)
            values = [
                str(rule.get("Enabled", "")),
                str(rule.get("DisplayName", "")),
                str(rule.get("LocalPort", "")),
                str(rule.get("Protocol", "")),
                str(rule.get("Direction", "")),
                str(rule.get("Profile", "")),
                str(rule.get("Action", "")),
                str(rule.get("Program", "")),
            ]
            for col, value in enumerate(values):
                if col == 0:
                    on_label = QLabel("ON")
                    on_label.setObjectName("OnBadge")
                    on_label.setFixedSize(34, 20)
                    on_label.setAlignment(Qt.AlignCenter)
                    cell_w = QWidget()
                    cell_l = QHBoxLayout(cell_w)
                    cell_l.setContentsMargins(4, 2, 4, 2)
                    cell_l.addWidget(on_label)
                    cell_l.setAlignment(Qt.AlignCenter)
                    self.rule_table.setCellWidget(row, col, cell_w)
                else:
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                    self.rule_table.setItem(row, col, item)
            self.rule_table.setRowHeight(row, 32)

        self.log_box.append(f"SUCCESS: Firewall rules loaded. Count={len(rules)}")
        self.update_port_button_status()

    # ==================================================================
    # リアルタイムステータス（開放済みポートをログ表示）
    # ==================================================================
    def update_port_button_status(self):
        open_ports = set()
        for row in range(self.rule_table.rowCount()):
            port_item = self.rule_table.item(row, 2)
            protocol_item = self.rule_table.item(row, 3)
            if port_item and protocol_item:
                open_ports.add((port_item.text(), protocol_item.text()))
        self.log_box.append(f"INFO: Open ports detected: {len(open_ports)}")

    # ==================================================================
    # 指定ポート 開放 / 閉鎖
    # ==================================================================
    def open_custom_port(self):
        port = self.port_input.text().strip()
        protocol = self.protocol_combo.currentText()
        if not port:
            self.log_box.append("ERROR: ポート番号を入力してください。")
            return
        self.open_port(port, protocol)
        self.load_firewall_rules()

    def close_custom_port(self):
        port = self.port_input.text().strip()
        protocol = self.protocol_combo.currentText()
        if not port:
            self.log_box.append("ERROR: ポート番号を入力してください。")
            return

        # ④ RDP閉鎖の追加確認
        if str(port) == "3389":
            result = QMessageBox.warning(
                self,
                "RDP閉鎖の確認",
                "3389/TCP を閉鎖すると、リモート接続できなくなる可能性があります。\n\n本当に閉鎖しますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if result != QMessageBox.Yes:
                self.log_box.append("CANCELLED: RDP閉鎖を中止しました。")
                return

        stdout, stderr = run_powershell_script(
            "powershell/close_port.ps1",
            ["-Port", str(port), "-Protocol", protocol]
        )
        if stdout:
            self.log_box.append(stdout.strip())
        if stderr:
            self.log_box.append(stderr.strip())
        self.load_firewall_rules()

    # ==================================================================
    # 証跡出力
    # ==================================================================
    def export_evidence(self):
        os.makedirs("output/evidence", exist_ok=True)
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"output/evidence/firewall_evidence_{now}.txt"

        with open(path, "w", encoding="utf-8") as f:
            f.write("FWquickSetter Evidence\n")
            f.write(f"Generated: {now}\n\n")
            f.write("=== Operation Log ===\n")
            f.write(self.log_box.toPlainText())
            f.write("\n\n=== Current Rules ===\n")
            for row in range(self.rule_table.rowCount()):
                values = []
                for col in range(self.rule_table.columnCount()):
                    header = self.rule_table.horizontalHeaderItem(col).text()
                    item = self.rule_table.item(row, col)
                    value = item.text() if item else ""
                    values.append(f"{header}: {value}")
                f.write(" | ".join(values) + "\n")

        self.log_box.append(f"SUCCESS: 証跡を出力しました。{path}")

    # ==================================================================
    # 使い方 / 更新情報
    # ==================================================================
    def show_help(self):
        QMessageBox.information(
            self,
            "使い方",
            "1. よく使うポートボタンで即時開放できます。\n"
            "2. 指定ポート操作で任意のポートを開放・閉鎖できます。\n"
            "3. ルール一覧で現在の有効ルールを確認できます。\n"
            "4. ルールをクリックすると右側に詳細が表示されます。\n"
            "5. 証跡出力でログとルール一覧を保存できます。"
        )

    def show_update_info(self):
        QMessageBox.information(
            self,
            "更新情報",
            "FWquickSetter Pro\n\n"
            "・Python / PySide6 版UIを実装\n"
            "・Firewallルール一覧取得に対応\n"
            "・ポート開放／閉鎖に対応\n"
            "・検索機能に対応\n"
            "・証跡出力機能を追加"
        )

    # ==================================================================
    # 選択ルール削除
    # ==================================================================
    def delete_selected_rule(self):
        row = self.rule_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "削除エラー", "削除するルールを選択してください。")
            return

        name_item = self.rule_table.item(row, 1)
        if not name_item:
            QMessageBox.warning(self, "削除エラー", "ルール名を取得できません。")
            return

        rule_name = name_item.text()

        # ④ 削除前の確認ダイアログ
        result = QMessageBox.warning(
            self,
            "ルール削除確認",
            f"次のルールを削除します。\n\n{rule_name}\n\nよろしいですか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if result != QMessageBox.Yes:
            self.log_box.append("CANCELLED: ルール削除を中止しました。")
            return

        stdout, stderr = run_powershell_script(
            "powershell/delete_rule.ps1",
            ["-RuleName", rule_name]
        )
        if stdout:
            self.log_box.append(stdout.strip())
        if stderr:
            self.log_box.append(stderr.strip())
        self.load_firewall_rules()

    # ==================================================================
    # ⑤ 新しいルール追加（フォーム化・簡易版）
    # ==================================================================
    def add_new_rule(self):
        port = self.port_input.text().strip()
        protocol = self.protocol_combo.currentText()

        if not port:
            QMessageBox.warning(self, "入力エラー", "ポート番号を入力してください。")
            return

        if not self.confirm_danger_port(port, protocol):
            return

        self.open_port(port, protocol)
        self.load_firewall_rules()

    # ==================================================================
    # エクスポート / インポート
    # ==================================================================
    def export_settings(self):
        os.makedirs("output/exports", exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "設定をエクスポート",
            "output/exports/fwq_settings.json",
            "JSON Files (*.json)"
        )
        if not path:
            return

        data = []
        for row in range(self.rule_table.rowCount()):
            data.append({
                "enabled":   self.rule_table.item(row, 0).text() if self.rule_table.item(row, 0) else "",
                "name":      self.rule_table.item(row, 1).text() if self.rule_table.item(row, 1) else "",
                "port":      self.rule_table.item(row, 2).text() if self.rule_table.item(row, 2) else "",
                "protocol":  self.rule_table.item(row, 3).text() if self.rule_table.item(row, 3) else "",
                "direction": self.rule_table.item(row, 4).text() if self.rule_table.item(row, 4) else "",
                "profile":   self.rule_table.item(row, 5).text() if self.rule_table.item(row, 5) else "",
                "action":    self.rule_table.item(row, 6).text() if self.rule_table.item(row, 6) else "",
                "program":   self.rule_table.item(row, 7).text() if self.rule_table.item(row, 7) else "",
            })

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.log_box.append(f"SUCCESS: 設定をエクスポートしました。{path}")

    def import_settings(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "設定をインポート",
            "output/exports",
            "JSON Files (*.json)"
        )
        if not path:
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.log_box.append(f"INFO: インポート対象 {len(data)} 件を読み込みました。")

    # ==================================================================
    # ルール詳細表示
    # ==================================================================
    def show_rule_detail(self, row, column):
        values = []
        for col in range(self.rule_table.columnCount()):
            header_item = self.rule_table.horizontalHeaderItem(col)
            cell_item = self.rule_table.item(row, col)
            header = header_item.text() if header_item else ""
            value = cell_item.text() if cell_item else ""
            values.append(f"{header}：{value}")
        self.detail_label.setText("\n".join(values))
        self.detail_label.setStyleSheet(
            "color: #d4d8e1; font-size: 11px; background: transparent;"
        )

    # ==================================================================
    # 検索フィルタ
    # ==================================================================
    def filter_rules(self):
        keyword = self.search_input.text().strip().lower()
        for row in range(self.rule_table.rowCount()):
            match = False
            for col in range(self.rule_table.columnCount()):
                item = self.rule_table.item(row, col)
                if item and keyword in item.text().lower():
                    match = True
                    break
            self.rule_table.setRowHidden(row, not match)

    # ==================================================================
    # UI 構築
    # ==================================================================
    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(14, 12, 14, 10)
        main_layout.setSpacing(8)

        # ===== Header =====
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_frame.setStyleSheet("""
            QFrame#HeaderFrame {
                background-color: #161921;
                border: 1px solid #2a2d38;
                border-radius: 8px;
            }
        """)
        header_inner = QHBoxLayout(header_frame)
        header_inner.setContentsMargins(12, 8, 12, 8)
        header_inner.setSpacing(10)

        logo = QLabel("🔥")
        logo.setObjectName("LogoLabel")
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignCenter)

        title_area = QVBoxLayout()
        title_area.setSpacing(2)
        title_area.setContentsMargins(0, 0, 0, 0)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.setContentsMargins(0, 0, 0, 0)

        title = QLabel("FWquickSetter")
        title.setObjectName("TitleLabel")
        title.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        pro_badge = QLabel("Pro")
        pro_badge.setObjectName("ProBadge")
        pro_badge.setFixedSize(44, 22)
        pro_badge.setAlignment(Qt.AlignCenter)

        title_row.addWidget(title)
        title_row.addWidget(pro_badge)
        title_row.addStretch()

        subtitle = QLabel("Windows Firewall を直感的に確認・変更・証跡出力できる GUI ツール")
        subtitle.setObjectName("SubtitleLabel")

        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        badge_row.setContentsMargins(0, 0, 0, 0)

        green_badge = QLabel("✓ 対応 OS")
        green_badge.setObjectName("GreenBadge")
        green_badge.setFixedHeight(20)
        green_badge.setAlignment(Qt.AlignCenter)
        badge_row.addWidget(green_badge)

        for text in ["Windows Server 2022", "Windows Server 2025", "対応済み"]:
            b = QLabel(text)
            b.setObjectName("InfoBadge")
            b.setFixedHeight(20)
            b.setAlignment(Qt.AlignCenter)
            badge_row.addWidget(b)

        badge_row.addStretch()

        title_area.addLayout(title_row)
        title_area.addWidget(subtitle)
        title_area.addLayout(badge_row)

        header_inner.addWidget(logo)
        header_inner.addSpacing(4)
        header_inner.addLayout(title_area)
        header_inner.addStretch()

        help_button = QPushButton("? 使い方")
        help_button.setObjectName("HeaderButton")
        help_button.setFixedHeight(30)
        help_button.clicked.connect(self.show_help)

        update_button = QPushButton("△ 更新情報")
        update_button.setObjectName("HeaderButton")
        update_button.setFixedHeight(30)
        update_button.clicked.connect(self.show_update_info)

        header_inner.addWidget(help_button)
        header_inner.addWidget(update_button)

        main_layout.addWidget(header_frame)

        # ===== Top Area =====
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        fw_group = QGroupBox("現在の FW 状態")
        fw_group.setFixedWidth(320)
        fw_layout = QGridLayout()
        fw_layout.setHorizontalSpacing(10)
        fw_layout.setVerticalSpacing(6)
        fw_layout.setContentsMargins(8, 4, 8, 8)

        for col, text in enumerate(["プロファイル", "有効", "既定の受信動作", "既定の送信動作"]):
            lbl = QLabel(text)
            lbl.setObjectName("SmallHeaderLabel")
            fw_layout.addWidget(lbl, 0, col)

        for row, profile in enumerate(["Domain", "Private", "Public"], start=1):
            fw_layout.addWidget(QLabel(profile), row, 0)
            on_badge = QLabel("ON")
            on_badge.setObjectName("OnBadge")
            on_badge.setFixedSize(34, 20)
            on_badge.setAlignment(Qt.AlignCenter)
            fw_layout.addWidget(on_badge, row, 1)
            fw_layout.addWidget(QLabel("NotConfigured"), row, 2)
            fw_layout.addWidget(QLabel("NotConfigured"), row, 3)

        refresh_fw_btn = QPushButton("更新")
        refresh_fw_btn.setObjectName("BlueButton")
        refresh_fw_btn.setFixedHeight(28)
        refresh_fw_btn.setCursor(Qt.PointingHandCursor)
        fw_layout.addWidget(refresh_fw_btn, 4, 0, 1, 4)
        fw_group.setLayout(fw_layout)

        port_group = QGroupBox("よく使うポートを開放")
        port_layout = QGridLayout()
        port_layout.setSpacing(8)
        port_layout.setContentsMargins(8, 4, 8, 8)

        ports = [
            ("HTTP",   "80 / TCP",    "PortBlue",   80,    "TCP"),
            ("HTTPS",  "443 / TCP",   "PortBlue",   443,   "TCP"),
            ("RDP",    "3389 / TCP",  "PortOrange", 3389,  "TCP"),
            ("WinRM",  "5985 / TCP",  "PortOrange", 5985,  "TCP"),
            ("SSH",    "22 / TCP",    "PortPurple", 22,    "TCP"),
            ("Zabbix", "10050 / TCP", "PortPurple", 10050, "TCP"),
            ("MySQL",  "3306 / TCP",  "PortPurple", 3306,  "TCP"),
            ("DNS",    "53 / TCP",    "PortPurple", 53,    "TCP"),
        ]

        for i, (name, detail, obj_name, port_num, proto) in enumerate(ports):
            btn = QPushButton(f"{name}\n{detail}")
            btn.setObjectName(obj_name)
            btn.setMinimumHeight(60)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setAttribute(Qt.WA_Hover, True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda checked=False, p=port_num, pr=proto: self.open_port(p, pr)
            )
            port_layout.addWidget(btn, i // 4, i % 4)

        port_group.setLayout(port_layout)

        top_layout.addWidget(fw_group)
        top_layout.addWidget(port_group, 1)
        main_layout.addLayout(top_layout)

        # ===== Middle Area =====
        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(10)

        op_group = QGroupBox("指定ポート操作")
        op_layout = QGridLayout()
        op_layout.setHorizontalSpacing(10)
        op_layout.setVerticalSpacing(6)
        op_layout.setContentsMargins(10, 4, 10, 10)

        op_layout.addWidget(QLabel("ポート番号"), 0, 0)
        op_layout.addWidget(QLabel("プロトコル"), 0, 1)

        self.port_input = QLineEdit()
        self.port_input.setFixedHeight(30)
        op_layout.addWidget(self.port_input, 1, 0)

        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["TCP", "UDP"])
        self.protocol_combo.setFixedHeight(30)
        op_layout.addWidget(self.protocol_combo, 1, 1)

        open_btn = QPushButton("＋ 開放する")
        open_btn.setObjectName("GreenButton")
        open_btn.setFixedHeight(30)
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(self.open_custom_port)

        close_btn = QPushButton("－ 閉鎖する")
        close_btn.setObjectName("RedButton")
        close_btn.setFixedHeight(30)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close_custom_port)

        evidence_button = QPushButton("証跡を出力")
        evidence_button.setObjectName("GrayButton")
        evidence_button.setFixedHeight(30)
        evidence_button.setCursor(Qt.PointingHandCursor)
        evidence_button.clicked.connect(self.export_evidence)

        op_layout.addWidget(open_btn, 2, 0)
        op_layout.addWidget(close_btn, 2, 1)
        op_layout.addWidget(evidence_button, 2, 2)
        op_group.setLayout(op_layout)

        warn_group = QGroupBox("危険ポート警告")
        warn_layout = QVBoxLayout()
        warn_layout.setSpacing(8)
        warn_layout.setContentsMargins(10, 4, 10, 10)

        danger_row = QHBoxLayout()
        danger_row.setSpacing(6)

        for port in ["21 / TCP", "23 / TCP", "135 / TCP", "139 / TCP", "445 / TCP", "3389 / TCP"]:
            d = QLabel(port)
            d.setObjectName("DangerBadge")
            d.setFixedHeight(22)
            d.setAlignment(Qt.AlignCenter)
            danger_row.addWidget(d)

        danger_row.addStretch()

        note = QLabel("上記のポートが開放されている場合、セキュリティリスクが高まります。開放時には確認ダイアログが表示されます。")
        note.setObjectName("NoteLabel")
        note.setWordWrap(True)

        warn_layout.addLayout(danger_row)
        warn_layout.addWidget(note)
        warn_layout.addStretch()
        warn_group.setLayout(warn_layout)

        ie_group = QGroupBox("設定のエクスポート / インポート")
        ie_layout = QVBoxLayout()
        ie_layout.setSpacing(8)
        ie_layout.setContentsMargins(10, 4, 10, 10)

        export_btn = QPushButton("エクスポート\n現在の設定をファイルに保存")
        export_btn.setObjectName("BlueButton")
        export_btn.setMinimumHeight(48)
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self.export_settings)

        import_btn = QPushButton("インポート\n保存した設定を適用")
        import_btn.setObjectName("GreenButton")
        import_btn.setMinimumHeight(48)
        import_btn.setCursor(Qt.PointingHandCursor)
        import_btn.clicked.connect(self.import_settings)

        ie_layout.addWidget(export_btn)
        ie_layout.addWidget(import_btn)
        ie_group.setLayout(ie_layout)

        mid_layout.addWidget(op_group, 2)
        mid_layout.addWidget(warn_group, 3)
        mid_layout.addWidget(ie_group, 1)
        main_layout.addLayout(mid_layout)

        # ===== Rule Area =====
        rule_group = QGroupBox("ルール一覧（有効なルール）")
        rule_layout = QVBoxLayout()
        rule_layout.setSpacing(8)
        rule_layout.setContentsMargins(10, 6, 10, 10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        add_rule_button = QPushButton("＋ 新しいルールを追加")
        add_rule_button.setObjectName("GrayButton")
        add_rule_button.setFixedHeight(30)
        add_rule_button.setCursor(Qt.PointingHandCursor)
        add_rule_button.clicked.connect(self.add_new_rule)

        delete_rule_button = QPushButton("－ 選択したルールを削除")
        delete_rule_button.setObjectName("RedButton")
        delete_rule_button.setFixedHeight(30)
        delete_rule_button.setCursor(Qt.PointingHandCursor)
        delete_rule_button.clicked.connect(self.delete_selected_rule)

        ref_btn = QPushButton("リフレッシュ")
        ref_btn.setObjectName("GrayButton")
        ref_btn.setFixedHeight(30)
        ref_btn.setCursor(Qt.PointingHandCursor)
        ref_btn.clicked.connect(self.load_firewall_rules)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ルール名・ポート番号で検索")
        self.search_input.setFixedHeight(30)
        self.search_input.textChanged.connect(self.filter_rules)

        self.profile_filter = QComboBox()
        self.profile_filter.addItems(["すべてのプロファイル", "Domain", "Private", "Public"])
        self.profile_filter.setFixedHeight(30)

        toolbar.addWidget(add_rule_button)
        toolbar.addWidget(delete_rule_button)
        toolbar.addWidget(ref_btn)
        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.profile_filter)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(10)

        self.rule_table = QTableWidget()
        self.rule_table.setColumnCount(8)
        self.rule_table.setHorizontalHeaderLabels([
            "有効", "ルール名", "ポート", "プロトコル", "方向", "プロファイル", "アクション", "作成元",
        ])
        self.rule_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.rule_table.horizontalHeader().setDefaultSectionSize(90)
        self.rule_table.horizontalHeader().setMinimumSectionSize(50)
        self.rule_table.verticalHeader().setVisible(False)
        self.rule_table.setShowGrid(False)
        self.rule_table.setAlternatingRowColors(True)
        self.rule_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rule_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rule_table.cellClicked.connect(self.show_rule_detail)

        # 右パネル
        right_panel = QVBoxLayout()
        right_panel.setSpacing(8)

        detail_group = QGroupBox("選択中のルール詳細")
        detail_group.setFixedWidth(300)
        detail_layout = QVBoxLayout()
        detail_layout.setContentsMargins(10, 6, 10, 10)

        self.detail_label = QLabel(
            "ルールをクリックすると\n"
            "詳細がここに表示されます。\n\n"
            "表示予定項目\n"
            "・ルール名\n"
            "・ポート番号\n"
            "・プロファイル\n"
            "・プログラム / サービス\n"
            "・作成元"
        )
        self.detail_label.setObjectName("DetailPlaceholder")
        self.detail_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.detail_label.setWordWrap(True)
        self.detail_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        detail_layout.addWidget(self.detail_label)
        detail_layout.addStretch()
        detail_group.setLayout(detail_layout)

        audit_group = QGroupBox("クイック監査サマリ")
        audit_group.setFixedWidth(300)
        audit_layout = QVBoxLayout()
        audit_layout.setSpacing(10)
        audit_layout.setContentsMargins(10, 6, 10, 10)

        for title_text, value_text in [
            ("有効ルール数",   "―"),
            ("危険ポート検出", "―"),
            ("Public 許可",    "―"),
            ("System 作成",    "―"),
        ]:
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(4)
            t = QLabel(title_text)
            t.setStyleSheet("color: #9aa0b0; font-size: 11px; background: transparent;")
            v = QLabel(value_text)
            v.setStyleSheet("color: #60a5fa; font-size: 11px; font-weight: bold; background: transparent;")
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row_h.addWidget(t)
            row_h.addStretch()
            row_h.addWidget(v)
            audit_layout.addWidget(row_w)

        audit_layout.addStretch()
        audit_group.setLayout(audit_layout)

        right_panel.addWidget(detail_group, 3)
        right_panel.addWidget(audit_group, 2)

        body_layout.addWidget(self.rule_table, 1)
        body_layout.addLayout(right_panel)

        rule_layout.addLayout(toolbar)
        rule_layout.addLayout(body_layout)
        rule_group.setLayout(rule_layout)
        main_layout.addWidget(rule_group, 1)

        # ===== Log Area =====
        log_group = QGroupBox("操作ログ")
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(10, 6, 10, 8)
        log_layout.addWidget(self.log_box)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # 起動時に自動読み込み
        self.load_firewall_rules()