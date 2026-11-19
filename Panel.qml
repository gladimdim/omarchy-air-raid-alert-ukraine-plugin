import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "gladimdim.air-raid-alert"
  ipcTarget: "gladimdim.air-raid-alert"
  manageIpc: false

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  // Color and Theme Tokens
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color accent: Color.accent
  readonly property color urgent: Color.urgent
  readonly property color muted: Color.muted
  readonly property color dim: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.65)
  readonly property color cardBg: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.05)
  readonly property color cardBorder: Qt.rgba(foreground.r, foreground.g, foreground.b, 0.12)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  // Plugin Engine State
  readonly property string enginePath: String(Qt.resolvedUrl("alert_engine.py")).replace(/^file:\/\//, "")
  property var alertsData: null
  property bool loading: false
  property string selectedOblast: "м. Київ"
  property bool alertActive: false
  property string alertChanged: ""
  property int activeCount: 0
  property int totalCount: 27
  property string currentProvider: "ubilling"
  property string sourceName: "Ubilling / Mørk Skogen"
  property bool notificationsEnabled: true
  property bool soundEnabled: true
  property int refreshIntervalSec: 20
  property var allRegions: []
  property string errorMessage: ""
  property bool isInitialized: false
  property bool lastAlertState: false
  property int activeTab: 0 // 0: My Region, 1: All Ukraine, 2: Settings
  property string regionSearchQuery: ""
  property string statusNotice: ""

  // Dock Button Tooltip
  readonly property string selectedOblastCode: {
    if (!allRegions) return "kyiv-city"
    for (var i = 0; i < allRegions.length; i++) {
      if (allRegions[i].name === root.selectedOblast) {
        return allRegions[i].code || "kyiv-city"
      }
    }
    return "kyiv-city"
  }

  readonly property string tooltipMessage: alertActive
    ? "🚨 ПОВІТРЯНА ТРИВОГА: " + selectedOblast + (alertChanged ? " (з " + alertChanged + ")" : "")
    : "🟢 Відбій: " + selectedOblast + " (Небезпеки немає)"

  function refresh() {
    if (!fetchProc.running) {
      root.loading = true
      fetchProc.running = true
    }
  }

  function setOblast(oblastName) {
    if (!oblastName) return
    root.selectedOblast = oblastName
    actionProc.command = ["python3", root.enginePath, "--set-oblast", oblastName]
    actionProc.running = true
    root.showNotice("Обрано регіон: " + oblastName)
  }

  function toggleNotifications() {
    var nextVal = !root.notificationsEnabled
    root.notificationsEnabled = nextVal
    actionProc.command = ["python3", root.enginePath, "--set-notifications", nextVal ? "true" : "false"]
    actionProc.running = true
    root.showNotice(nextVal ? "Сповіщення увімкнено" : "Сповіщення вимкнено")
  }

  function toggleSound() {
    var nextVal = !root.soundEnabled
    root.soundEnabled = nextVal
    actionProc.command = ["python3", root.enginePath, "--set-sound", nextVal ? "true" : "false"]
    actionProc.running = true
    root.showNotice(nextVal ? "Звук увімкнено" : "Звук вимкнено")
  }

  function setIntervalSec(sec) {
    root.refreshIntervalSec = sec
    actionProc.command = ["python3", root.enginePath, "--set-interval", String(sec)]
    actionProc.running = true
    root.showNotice("Інтервал оновлення: " + sec + " сек.")
  }

  function playSiren() {
    soundProc.command = ["python3", root.enginePath, "--play-siren"]
    soundProc.running = true
  }

  function playClear() {
    soundProc.command = ["python3", root.enginePath, "--play-clear"]
    soundProc.running = true
  }

  function triggerTest() {
    soundProc.command = ["python3", root.enginePath, "--test-notification"]
    soundProc.running = true
    root.showNotice("Тестове сповіщення надіслано!")
  }

  function showNotice(msg) {
    root.statusNotice = msg
    noticeTimer.restart()
  }

  function parseAlerts(raw) {
    if (!raw || !raw.trim()) return
    try {
      var data = JSON.parse(raw)
      root.alertsData = data
      root.selectedOblast = data.selectedOblast || root.selectedOblast
      root.currentProvider = data.provider || root.currentProvider
      root.sourceName = data.sourceName || root.sourceName
      root.activeCount = data.activeCount || 0
      root.totalCount = data.totalCount || 27
      root.allRegions = data.regions || []
      root.errorMessage = data.errorMessage || ""
      root.notificationsEnabled = data.notificationsEnabled !== undefined ? data.notificationsEnabled : true
      root.soundEnabled = data.soundEnabled !== undefined ? data.soundEnabled : true
      root.refreshIntervalSec = data.refreshIntervalSec || 20

      var nextAlert = Boolean(data.alertActive)
      var nextChanged = data.alertChanged || ""

      // Check for state transitions to fire notifications
      if (root.isInitialized) {
        if (nextAlert !== root.lastAlertState) {
          if (nextAlert) {
            root.onAlertStarted(root.selectedOblast, nextChanged)
          } else {
            root.onAlertEnded(root.selectedOblast, nextChanged)
          }
        }
      } else {
        root.isInitialized = true
      }

      root.alertActive = nextAlert
      root.alertChanged = nextChanged
      root.lastAlertState = nextAlert
    } catch (e) {
      console.log("Error parsing alert data:", e)
    }
  }

  function onAlertStarted(oblast, time) {
    if (root.notificationsEnabled) {
      var title = "🚨 ПОВІТРЯНА ТРИВОГА: " + oblast
      var body = "Увага! В " + oblast + " оголошено тривогу. Загроза ударів! Перейдіть в укриття!"
      Util.execArgv([
        "omarchy-notification-send",
        "-g", "󰚌",
        "-u", "critical",
        "-t", "15000",
        title,
        body
      ])
    }
    if (root.soundEnabled) {
      root.playSiren()
    }
  }

  function onAlertEnded(oblast, time) {
    if (root.notificationsEnabled) {
      var title = "🟢 ВІДБІЙ ТРИВОГИ: " + oblast
      var body = "Відбій повітряної тривоги в " + oblast + ". Небезпека минула."
      Util.execArgv([
        "omarchy-notification-send",
        "-g", "󰄬",
        "-u", "normal",
        "-t", "10000",
        title,
        body
      ])
    }
    if (root.soundEnabled) {
      root.playClear()
    }
  }

  // Load config on startup
  Component.onCompleted: {
    refresh()
  }

  onOpenedChanged: {
    if (opened) refresh()
  }

  // Polling Timer
  Timer {
    id: pollTimer
    interval: Math.max(10000, root.refreshIntervalSec * 1000)
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  Timer {
    id: noticeTimer
    interval: 3000
    onTriggered: root.statusNotice = ""
  }

  // Background processes
  Process {
    id: fetchProc
    command: ["python3", root.enginePath, "--fetch"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.loading = false
        root.parseAlerts(text)
      }
    }
    onExited: function(code) {
      root.loading = false
    }
  }

  Process {
    id: actionProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.refresh()
      }
    }
  }

  Process {
    id: soundProc
  }

  // IPC interface
  IpcHandler {
    target: "gladimdim.air-raid-alert"
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): void { root.refresh() }
    function test(): void { root.triggerTest() }
  }

  // =========================================================================
  // DOCK / STATUS BAR BUTTON WITH UKRAINIAN TRIDENT ICON
  // =========================================================================
  // BarIconContent gives this item its size. anchors.fill ties that size to a
  // loader that is still 0×0, so the trident never paints and the slot looks empty.
  Component {
    id: tryzubComp
    Item {
      implicitWidth: mark.width
      implicitHeight: mark.height

      Image {
        id: mark
        width: Style.bar.iconSize
        height: Style.bar.iconSize
        source: root.alertActive
          ? Qt.resolvedUrl("assets/tryzub-red.svg")
          : Qt.resolvedUrl("assets/tryzub-green.svg")
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
        sourceSize.width: 64
        sourceSize.height: 64

        SequentialAnimation on opacity {
          running: root.alertActive
          loops: Animation.Infinite
          NumberAnimation { to: 0.15; duration: 400; easing.type: Easing.InOutQuad }
          NumberAnimation { to: 1.0; duration: 400; easing.type: Easing.InOutQuad }
        }
      }
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    iconComponent: tryzubComp
    tooltipText: root.tooltipMessage
    active: root.alertActive

    onPressed: function(b) {
      if (b === Qt.RightButton) {
        root.refresh()
      } else {
        root.toggle()
      }
    }
  }

  // Small blinking alert badge dot on bar icon when alarm is active
  Rectangle {
    visible: root.alertActive
    width: 8
    height: 8
    radius: 4
    color: Color.urgent
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.rightMargin: 1
    anchors.topMargin: 2

    SequentialAnimation on opacity {
      running: root.alertActive
      loops: Animation.Infinite
      NumberAnimation { to: 0.2; duration: 400; easing.type: Easing.InOutQuad }
      NumberAnimation { to: 1.0; duration: 400; easing.type: Easing.InOutQuad }
    }
  }

  // =========================================================================
  // POPUP WINDOW (KeyboardPanel)
  // =========================================================================
  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(460))
    contentHeight: panel.fittedContentHeight(Style.space(580))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTextKey: function(t) {
        if (t === "1") root.activeTab = 0
        else if (t === "2") root.activeTab = 1
        else if (t === "3") root.activeTab = 2
        else if (t === "r" || t === "R") root.refresh()
      }

      Column {
        anchors.fill: parent
        spacing: Style.space(12)

        // -------------------------------------------------------------------
        // 1. POPUP HEADER
        // -------------------------------------------------------------------
        RowLayout {
          width: parent.width
          spacing: Style.space(8)

          Text {
            text: "🇺🇦 Повітряна тривога"
            font.family: root.fontFamily
            font.pixelSize: Style.font.title
            font.bold: true
            color: root.foreground
            Layout.fillWidth: true
          }

          // Refresh Button
          Button {
            text: ""
            iconText: root.loading ? "󰑮" : "󰑐"
            tooltipText: "Оновити дані"
            onClicked: root.refresh()
            implicitWidth: Style.space(32)
            implicitHeight: Style.space(32)

            RotationAnimation on rotation {
              running: root.loading
              loops: Animation.Infinite
              from: 0
              to: 360
              duration: 800
            }
          }

          // Close Button
          Button {
            text: ""
            iconText: "󰅖"
            tooltipText: "Закрити"
            onClicked: root.close()
            implicitWidth: Style.space(32)
            implicitHeight: Style.space(32)
          }
        }

        // -------------------------------------------------------------------
        // 2. HERO STATUS BANNER (ACTIVE ALARM vs ALL-CLEAR)
        // -------------------------------------------------------------------
        Rectangle {
          width: parent.width
          implicitHeight: Style.space(96)
          radius: Style.cornerRadius
          color: root.alertActive
            ? Qt.rgba(0.9, 0.15, 0.15, 0.18)
            : Qt.rgba(0.15, 0.75, 0.35, 0.14)
          border.color: root.alertActive
            ? Qt.rgba(0.9, 0.2, 0.2, 0.5)
            : Qt.rgba(0.2, 0.8, 0.4, 0.4)
          border.width: 1.5

          RowLayout {
            anchors.fill: parent
            anchors.margins: Style.space(14)
            spacing: Style.space(14)

            // Ukrainian Trident & Selected Oblast Coat of Arms
            RowLayout {
              spacing: Style.space(10)
              Layout.alignment: Qt.AlignVCenter

              // Ukrainian Trident
              Image {
                source: root.alertActive
                  ? Qt.resolvedUrl("assets/tryzub-red.svg")
                  : Qt.resolvedUrl("assets/tryzub-green.svg")
                fillMode: Image.PreserveAspectFit
                smooth: true
                sourceSize.width: 128
                sourceSize.height: 128
                Layout.preferredWidth: Style.space(38)
                Layout.preferredHeight: Style.space(38)

                SequentialAnimation on opacity {
                  running: root.alertActive
                  loops: Animation.Infinite
                  NumberAnimation { to: 0.25; duration: 400; easing.type: Easing.InOutQuad }
                  NumberAnimation { to: 1.0; duration: 400; easing.type: Easing.InOutQuad }
                }
              }

              // Selected Oblast Official Coat of Arms
              Image {
                source: Qt.resolvedUrl("assets/emblems/" + root.selectedOblastCode + ".svg")
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
                sourceSize.width: 128
                sourceSize.height: 128
                Layout.preferredWidth: Style.space(40)
                Layout.preferredHeight: Style.space(40)
              }
            }

            ColumnLayout {
              Layout.fillWidth: true
              spacing: Style.space(2)

              Text {
                text: root.alertActive ? "ПОВІТРЯНА ТРИВОГА!" : "ВІДБІЙ ТРИВОГИ"
                font.family: root.fontFamily
                font.pixelSize: Style.font.subtitle
                font.bold: true
                color: root.alertActive ? Color.urgent : Qt.rgba(0.2, 0.85, 0.4, 1.0)
              }

              Text {
                text: root.selectedOblast
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                font.bold: true
                color: root.foreground
              }

              Text {
                text: root.alertActive
                  ? ("Початок: " + (root.alertChanged ? root.alertChanged : "нещодавно") + " • Перейдіть в укриття!")
                  : "Небезпеки немає • У вашому регіоні спокійно"
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                color: root.dim
              }
            }
          }
        }

        // Status Notice Feedback Bar
        Rectangle {
          visible: root.statusNotice !== ""
          width: parent.width
          implicitHeight: Style.space(26)
          radius: Style.cornerRadius
          color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.2)
          border.color: root.accent
          border.width: 1

          Text {
            anchors.centerIn: parent
            text: root.statusNotice
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
            color: root.foreground
          }
        }

        // -------------------------------------------------------------------
        // 3. TAB NAVIGATION BAR
        // -------------------------------------------------------------------
        RowLayout {
          width: parent.width
          spacing: Style.space(6)

          Button {
            Layout.fillWidth: true
            text: "Мій регіон"
            iconText: "󰍹"
            active: root.activeTab === 0
            onClicked: root.activeTab = 0
          }

          Button {
            Layout.fillWidth: true
            text: "Україна (" + root.activeCount + ")"
            iconText: "󰙔"
            active: root.activeTab === 1
            onClicked: root.activeTab = 1
          }

          Button {
            Layout.fillWidth: true
            text: "Налаштування"
            iconText: "󰒓"
            active: root.activeTab === 2
            onClicked: root.activeTab = 2
          }
        }

        PanelSeparator { width: parent.width }

        // -------------------------------------------------------------------
        // 4. TAB CONTENTS
        // -------------------------------------------------------------------
        Item {
          width: parent.width
          height: panel.height - y - Style.space(16)
          clip: true

          // =================================================================
          // TAB 0: MY REGION & OBLAST PICKER
          // =================================================================
          Column {
            anchors.fill: parent
            visible: root.activeTab === 0
            spacing: Style.space(10)

            // Search Filter
            TextField {
              width: parent.width
              placeholderText: "🔍 Пошук області (наприклад: Київ, Львів, Харків...)"
              text: root.regionSearchQuery
              foreground: root.foreground
              font.family: root.fontFamily
              onTextChanged: root.regionSearchQuery = text
            }

            // Oblasts Scroll List
            Flickable {
              width: parent.width
              height: Style.space(220)
              contentWidth: width
              contentHeight: oblastColumn.implicitHeight
              clip: true
              boundsBehavior: Flickable.StopAtBounds

              Column {
                id: oblastColumn
                width: parent.width
                spacing: Style.space(4)

                Repeater {
                  model: {
                    if (!root.allRegions) return []
                    var q = root.regionSearchQuery.trim().toLowerCase()
                    if (!q) return root.allRegions
                    var res = []
                    for (var i = 0; i < root.allRegions.length; i++) {
                      var r = root.allRegions[i]
                      if (r.name.toLowerCase().indexOf(q) !== -1 || (r.nameEn && r.nameEn.toLowerCase().indexOf(q) !== -1)) {
                        res.push(r)
                      }
                    }
                    return res
                  }

                  Rectangle {
                    required property var modelData
                    width: oblastColumn.width
                    implicitHeight: Style.space(36)
                    radius: Style.cornerRadius
                    readonly property bool isSelected: modelData.name === root.selectedOblast
                    color: isSelected
                      ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.22)
                      : (rowHover.hovered ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.08) : "transparent")
                    border.color: isSelected ? root.accent : "transparent"
                    border.width: 1

                    HoverHandler { id: rowHover }

                    MouseArea {
                      anchors.fill: parent
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.setOblast(modelData.name)
                    }

                    RowLayout {
                      anchors.fill: parent
                      anchors.leftMargin: Style.space(10)
                      anchors.rightMargin: Style.space(10)
                      spacing: Style.space(8)

                      // Official Oblast Coat of Arms from Wikimedia
                      Image {
                        source: Qt.resolvedUrl("assets/emblems/" + (modelData.code || "kyiv-city") + ".svg")
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        mipmap: true
                        sourceSize.width: 64
                        sourceSize.height: 64
                        Layout.preferredWidth: Style.space(22)
                        Layout.preferredHeight: Style.space(22)
                      }

                      Text {
                        text: modelData.name
                        color: isSelected ? root.accent : root.foreground
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.body
                        font.bold: isSelected
                        Layout.fillWidth: true
                      }

                      Rectangle {
                        radius: 4
                        color: modelData.alert ? Qt.rgba(0.9, 0.2, 0.2, 0.2) : Qt.rgba(0.2, 0.8, 0.4, 0.15)
                        implicitWidth: tagText.implicitWidth + Style.space(8)
                        implicitHeight: Style.space(20)

                        Text {
                          id: tagText
                          anchors.centerIn: parent
                          text: modelData.alert ? "ТРИВОГА" : "Відбій"
                          font.family: root.fontFamily
                          font.pixelSize: Style.font.caption
                          font.bold: true
                          color: modelData.alert ? Color.urgent : Qt.rgba(0.2, 0.8, 0.4, 1.0)
                        }
                      }

                      Text {
                        visible: isSelected
                        text: "󰄬 Обрано"
                        color: root.accent
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.caption
                        font.bold: true
                      }
                    }
                  }
                }
              }
            }

            PanelSeparator { width: parent.width }

            // Toggles Row
            RowLayout {
              width: parent.width
              spacing: Style.space(8)

              Button {
                Layout.fillWidth: true
                text: root.notificationsEnabled ? "Сповіщення: Увімкнено" : "Сповіщення: Вимкнено"
                iconText: root.notificationsEnabled ? "󰂚" : "󰂛"
                active: root.notificationsEnabled
                onClicked: root.toggleNotifications()
              }

              Button {
                Layout.fillWidth: true
                text: root.soundEnabled ? "Звук: Увімкнено" : "Звук: Вимкнено"
                iconText: root.soundEnabled ? "󰓃" : "󰓄"
                active: root.soundEnabled
                onClicked: root.toggleSound()
              }
            }

            // Test Notification Button
            Button {
              width: parent.width
              text: "󰞏 Надіслати тестове сповіщення та звук"
              onClicked: root.triggerTest()
            }
          }

          // =================================================================
          // TAB 1: ALL UKRAINE OVERVIEW
          // =================================================================
          Column {
            anchors.fill: parent
            visible: root.activeTab === 1
            spacing: Style.space(10)

            // National Summary Card
            Rectangle {
              width: parent.width
              implicitHeight: Style.space(42)
              radius: Style.cornerRadius
              color: root.activeCount > 0 ? Qt.rgba(0.9, 0.2, 0.2, 0.12) : Qt.rgba(0.2, 0.8, 0.4, 0.12)
              border.color: root.activeCount > 0 ? Qt.rgba(0.9, 0.2, 0.2, 0.3) : Qt.rgba(0.2, 0.8, 0.4, 0.3)
              border.width: 1

              RowLayout {
                anchors.fill: parent
                anchors.margins: Style.space(10)
                spacing: Style.space(8)

                Text {
                  text: root.activeCount > 0 ? "󰚌" : "󰄬"
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.subtitle
                  color: root.activeCount > 0 ? Color.urgent : Qt.rgba(0.2, 0.8, 0.4, 1.0)
                }

                Text {
                  text: "Зараз тривога у " + root.activeCount + " з " + root.totalCount + " регіонів України"
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.bold: true
                  color: root.foreground
                  Layout.fillWidth: true
                }
              }
            }

            // All Oblasts List
            Flickable {
              width: parent.width
              height: Style.space(310)
              contentWidth: width
              contentHeight: allOblastsCol.implicitHeight
              clip: true
              boundsBehavior: Flickable.StopAtBounds

              Column {
                id: allOblastsCol
                width: parent.width
                spacing: Style.space(4)

                Repeater {
                  model: {
                    if (!root.allRegions) return []
                    // Sort: active alarms first, then peaceful regions
                    var list = root.allRegions.slice()
                    list.sort(function(a, b) {
                      if (a.alert && !b.alert) return -1
                      if (!a.alert && b.alert) return 1
                      return a.name.localeCompare(b.name)
                    })
                    return list
                  }

                  Rectangle {
                    required property var modelData
                    width: allOblastsCol.width
                    implicitHeight: Style.space(34)
                    radius: Style.cornerRadius
                    color: modelData.alert
                      ? Qt.rgba(0.9, 0.2, 0.2, 0.1)
                      : (hoverItem.hovered ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.05) : "transparent")
                    border.color: modelData.name === root.selectedOblast ? root.accent : "transparent"
                    border.width: 1

                    HoverHandler { id: hoverItem }

                    MouseArea {
                      anchors.fill: parent
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.setOblast(modelData.name)
                    }

                    RowLayout {
                      anchors.fill: parent
                      anchors.leftMargin: Style.space(10)
                      anchors.rightMargin: Style.space(10)
                      spacing: Style.space(8)

                      // Official Oblast Coat of Arms from Wikimedia
                      Image {
                        source: Qt.resolvedUrl("assets/emblems/" + (modelData.code || "kyiv-city") + ".svg")
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        mipmap: true
                        sourceSize.width: 64
                        sourceSize.height: 64
                        Layout.preferredWidth: Style.space(22)
                        Layout.preferredHeight: Style.space(22)
                      }

                      Text {
                        text: modelData.name
                        color: modelData.name === root.selectedOblast ? root.accent : root.foreground
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.body
                        font.bold: modelData.name === root.selectedOblast || modelData.alert
                        Layout.fillWidth: true
                      }

                      Text {
                        visible: modelData.changed !== ""
                        text: modelData.changed
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.caption
                        color: root.dim
                      }

                      Rectangle {
                        radius: 4
                        color: modelData.alert ? Color.urgent : Qt.rgba(0.2, 0.8, 0.4, 0.2)
                        implicitWidth: Style.space(60)
                        implicitHeight: Style.space(20)

                        Text {
                          anchors.centerIn: parent
                          text: modelData.alert ? "ТРИВОГА" : "ВІДБІЙ"
                          font.family: root.fontFamily
                          font.pixelSize: Style.font.caption
                          font.bold: true
                          color: modelData.alert ? "#ffffff" : Qt.rgba(0.2, 0.8, 0.4, 1.0)
                        }
                      }
                    }
                  }
                }
              }
            }
          }

          // =================================================================
          // TAB 2: SETTINGS
          // =================================================================
          Column {
            anchors.fill: parent
            visible: root.activeTab === 2
            spacing: Style.space(12)

            PanelSectionHeader {
              text: "СПОДІЛЕННЯ ТА ЗВУК"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            RowLayout {
              width: parent.width
              spacing: Style.space(8)

              Button {
                Layout.fillWidth: true
                text: root.notificationsEnabled ? "󰂚 Сповіщення: Увімкнено" : "󰂛 Сповіщення: Вимкнено"
                active: root.notificationsEnabled
                onClicked: root.toggleNotifications()
              }

              Button {
                Layout.fillWidth: true
                text: root.soundEnabled ? "󰕾 Звук: Увімкнено" : "󰝟 Звук: Вимкнено"
                active: root.soundEnabled
                onClicked: root.toggleSound()
              }
            }

            PanelSeparator { width: parent.width }

            PanelSectionHeader {
              text: "ЧАСТОТА ОНОВЛЕННЯ ДАНИХ"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            RowLayout {
              width: parent.width
              spacing: Style.space(6)

              Button {
                Layout.fillWidth: true
                text: "15 сек"
                active: root.refreshIntervalSec === 15
                onClicked: root.setIntervalSec(15)
              }

              Button {
                Layout.fillWidth: true
                text: "20 сек"
                active: root.refreshIntervalSec === 20
                onClicked: root.setIntervalSec(20)
              }

              Button {
                Layout.fillWidth: true
                text: "30 сек"
                active: root.refreshIntervalSec === 30
                onClicked: root.setIntervalSec(30)
              }

              Button {
                Layout.fillWidth: true
                text: "60 сек"
                active: root.refreshIntervalSec === 60
                onClicked: root.setIntervalSec(60)
              }
            }

            PanelSeparator { width: parent.width }

            PanelSectionHeader {
              text: "ПЕРЕВІРКА СИГНАЛІВ ТА ЗВУКУ"
              foreground: root.foreground
              fontFamily: root.fontFamily
            }

            RowLayout {
              width: parent.width
              spacing: Style.space(6)

              Button {
                Layout.fillWidth: true
                text: "󰚌 Сирена тривоги"
                onClicked: root.playSiren()
              }

              Button {
                Layout.fillWidth: true
                text: "󰄬 Сигнал відбою"
                onClicked: root.playClear()
              }
            }

            Button {
              width: parent.width
              text: "󰂚 Надіслати тестове сповіщення на екран"
              onClicked: root.triggerTest()
            }
          }
        }
      }
    }
  }
}
