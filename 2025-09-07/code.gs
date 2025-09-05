// ================================================================
//   [v6.1 FINAL] Code.gs (동적 URL 필터링 강화 및 모든 오류 해결)
// ================================================================

const SPREADSHEET_ID = "1XoIQLRou3NWf5_hPc_wwYF9CU3ZnecBATZ8F3v0gXNI";
const SHEET_NAME = "reports";
const SETTINGS_SHEET_NAME = "설정";
const MAX_LINKS_TO_PROCESS = 10;

function onOpen() {
  SpreadsheetApp.getUi()
      .createMenu('🤖 크롤러 설정')
      .addItem('🔑 Gemini API 키 설정', 'setGeminiApiKey')
      .addToUi();
}

function setGeminiApiKey() {
  const ui = SpreadsheetApp.getUi();
  const response = ui.prompt('Gemini API 키 설정', '새로운 Gemini API 키를 입력하세요.', ui.ButtonSet.OK_CANCEL);
  if (response.getSelectedButton() == ui.Button.OK) {
    const apiKey = response.getResponseText();
    if (apiKey && apiKey.trim() !== '') {
      PropertiesService.getScriptProperties().setProperty('GEMINI_API_KEY', apiKey);
      ui.alert('Gemini API 키가 성공적으로 저장되었습니다.');
    }
  }
}

function runCrawlingFromWebApp() {
  const settingsSheet = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SETTINGS_SHEET_NAME);
  if (!settingsSheet || settingsSheet.getLastRow() < 2) { return '실패: 설정 시트에 크롤링할 URL이 없습니다.'; }
  const listPageUrls = settingsSheet.getRange(2, 1, settingsSheet.getLastRow() - 1, 1).getValues().flat().filter(url => url && url.trim() !== "");
  if (listPageUrls.length === 0) { return '실패: 설정 시트에 유효한 URL이 없습니다.'; }
  let totalNewItems = 0;
  listPageUrls.forEach(listUrl => {
    Logger.log(`======= 목록 페이지 처리 시작: ${listUrl} =======`);
    const detailUrls = extractArticleLinks(listUrl);
    if (detailUrls && detailUrls.length > 0) {
      const uniqueUrls = [...new Set(detailUrls)];
      Logger.log(`${uniqueUrls.length}개의 유효한 게시물 링크를 찾았습니다.`);
      const linksToProcess = uniqueUrls.slice(0, MAX_LINKS_TO_PROCESS);
      Logger.log(`API 할당량 보호를 위해 최대 ${MAX_LINKS_TO_PROCESS}개만 처리합니다.`);
      linksToProcess.forEach(detailUrl => {
        const success = processDetailUrlWithGemini(detailUrl);
        if (success) { totalNewItems++; }
        Utilities.sleep(1500);
      });
    } else {
      Logger.log('새로운 게시물 링크를 찾지 못했습니다.');
    }
  });
  if (totalNewItems > 0) { return `성공! ${totalNewItems}개의 새로운 정보를 업데이트했습니다.`; }
  else { return '완료. 새로운 정보가 없습니다. (API 사용량 초과일 수 있습니다)'; }
}

function extractArticleLinks(pageUrl) {
    Logger.log(`[1단계] 링크 추출 시작: ${pageUrl}`);
    try {
        const options = {'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}, 'muteHttpExceptions': true};
        const htmlContent = UrlFetchApp.fetch(pageUrl, options).getContentText();
        const baseUrlMatch = pageUrl.match(/^(https?:\/\/[^\/]+)/);
        if (!baseUrlMatch) { return []; }
        const baseUrl = baseUrlMatch[0];
        const linkRegex = /href="([^"$`{}]*(?:article|view|post|news|board|document|press|nttView)[^"$`{}]*\d+[^"$`{}]*)"/gi;
        let match;
        const links = new Set();
        while ((match = linkRegex.exec(htmlContent)) !== null) {
            let link = match[1].trim().replace(/&amp;/g, '&');
            if (link.startsWith('//')) { link = 'https:' + link; }
            else if (link.startsWith('/')) { link = baseUrl + link; }
            else if (!link.startsWith('http')) { link = baseUrl + '/' + link; }
