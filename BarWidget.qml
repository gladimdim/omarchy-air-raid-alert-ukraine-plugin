import QtQuick
import qs.Commons
import qs.Ui

Item {
  id: root
  implicitWidth: panelLoader.item ? panelLoader.item.implicitWidth : Style.bar.statusSlot
  implicitHeight: panelLoader.item ? panelLoader.item.implicitHeight : Style.bar.statusSlot

  property var bar: null
  property var settings: ({})

  function refresh() {
    if (panelLoader.item && panelLoader.item.refresh) panelLoader.item.refresh()
  }

  function toggle() {
    if (panelLoader.item && panelLoader.item.toggle) panelLoader.item.toggle()
  }

  Loader {
    id: panelLoader
    anchors.fill: parent
    source: Qt.resolvedUrl("Panel.qml")
    onLoaded: {
      if (item && "bar" in item) item.bar = root.bar
      if (item && "settings" in item) item.settings = root.settings
    }
  }
}
