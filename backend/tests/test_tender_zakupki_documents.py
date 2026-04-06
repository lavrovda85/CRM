"""Unit tests for ЕИС documentation page link extraction."""

from app.services.tender.tender_zakupki_documents import extract_zakupki_filestore_links


def test_extract_filestore_links_from_documents_html_snippet() -> None:
    html = """
    <div class="blockFilesTabDocs">
      <span class="section__value">
        <a href="https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=19341E907AD145239688997B3BC0D840"
           title="ТЗ.docx">Описание объекта</a>
      </span>
    </div>
    """
    links = extract_zakupki_filestore_links(html)
    assert len(links) == 1
    assert "uid=19341E907AD145239688997B3BC0D840" in links[0]["url"]
    assert "filestore/public" in links[0]["url"]
    assert links[0].get("uid") == "19341E907AD145239688997B3BC0D840"


def test_extract_filestore_dedupes_by_uid() -> None:
    uid = "19341E907AD145239688997B3BC0D840"
    html = f"""
    <a href="https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid={uid}">A</a>
    <a href="https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid={uid}">B</a>
    """
    links = extract_zakupki_filestore_links(html)
    assert len(links) == 1
