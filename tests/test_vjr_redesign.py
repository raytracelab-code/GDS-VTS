"""Presentation regressions, separate from the unchanged Excel acceptance tests."""
import pytest
from app.qt.QtCore import Qt, QDate
from app.qt.QtWidgets import QFrame
from app.ui.pages.vdr.date_picker import VdrDatePicker
from app.ui.pages.vjr_workspace import VjrPage
from app.ui.pages.vjr_widgets import FieldGrid, GroupedHeader
from app.vjr.store import VjrStore
from vjr_fixture import full_report


@pytest.fixture
def page(qtbot,tmp_path):
    store=VjrStore(tmp_path/'report.json'); store.report=full_report()
    widget=VjrPage(store,lambda:{})
    qtbot.addWidget(widget); widget.resize(1366,768); widget.show(); qtbot.wait(30)
    return widget


@pytest.mark.parametrize('width,height',[(1920,1080),(1600,900),(1366,768)])
def test_responsive_actions_and_field_grids(page,qtbot,width,height):
    page.resize(width,height); qtbot.wait(30)
    assert page.rect().contains(page.excel_button.mapTo(page,page.excel_button.rect().bottomRight()))
    assert page.excel_button.isVisible()
    for index in (0,4,5):
        page.tabs.setCurrentIndex(index); qtbot.wait(20)
        for grid in page.tabs.currentWidget().findChildren(FieldGrid):
            rectangles=[widget.geometry() for widget,_ in grid.fields]
            for i,rect in enumerate(rectangles):
                assert grid.rect().contains(rect)
                assert all(not rect.intersects(other) for other in rectangles[i+1:])


def test_uses_accepted_vdr_calendar(page):
    editor=page.editors[('departure','report_date')]
    assert isinstance(editor,VdrDatePicker)
    editor.setDate(QDate(2026,11,17))
    assert page.store.report['departure']['report_date']=='2026-11-17'
    editor.clear(); assert page.store.report['departure']['report_date']==''


def test_grouped_headers_actions_and_totals(page):
    for group in ('waypoints','progress'):
        table,schema=page.tables[(group,)]
        assert isinstance(table.horizontalHeader(),GroupedHeader)
        assert table.horizontalHeader().groups
        assert table.columnCount()==len(schema)+1
    deck,_=page.tables[('departure','deck')]
    assert deck.rowCount()==6 and deck.item(5,0).text()=='TOTAL'
    assert deck.item(5,5).text()=='300' and deck.item(5,6).text()=='30.00%'
    assert not deck.item(5,5).flags() & Qt.ItemFlag.ItemIsEditable
    crew,schema=page.tables[('crew',)]
    crew.cellWidget(1,len(schema)).click()
    assert len(page.store.report['crew'])==1
    assert page.store.report['crew'][0]['name']=='Captain Example'
    page.undo(); assert len(page.store.report['crew'])==2


def test_edit_reuses_widgets_and_inline_validation(page,qtbot):
    tables={path:id(table) for path,(table,_) in page.tables.items()}
    editor=page.editors[('meta','capacity')]
    editor.selectAll(); qtbot.keyClicks(editor,'-1')
    assert editor.property('invalid')
    assert page.field_errors[('meta','capacity')].isVisible()
    assert not page.excel_button.isEnabled()
    assert tables=={path:id(table) for path,(table,_) in page.tables.items()}
    editor.selectAll(); qtbot.keyClicks(editor,'1000')
    assert not editor.property('invalid')
    assert page.excel_button.isEnabled()


def test_section_navigator_and_reserved_cards(page):
    for i,button in enumerate(page.nav_buttons):
        button.click(); assert page.tabs.currentIndex()==i and button.isChecked()
    cards=[w for w in page.findChildren(QFrame) if w.objectName()=='photoCard']
    assert len(cards)==2
    assert all(not card.acceptDrops() for card in cards)


def test_arrival_departure_time_is_visible_and_linked(page,qtbot):
    page.tabs.setCurrentIndex(5)
    editor=page.editors[('arrival','departure_time')]
    page.tabs.currentWidget().ensureWidgetVisible(editor); qtbot.wait(20)
    assert editor.isVisible() and editor.height()>=32
    assert editor.isReadOnly() and editor.text()=='09:05'
    page.set_field(('departure','departure_time'),'12:45')
    assert editor.text()=='12:45'
    time_editor=page.editors[('arrival','arrival_time')]
    page.tabs.currentWidget().ensureWidgetVisible(time_editor); qtbot.wait(20)
    assert time_editor.text()=='11:45'
    assert time_editor.lineEdit().width()>60  # Text must remain visible with both Qt styles.
