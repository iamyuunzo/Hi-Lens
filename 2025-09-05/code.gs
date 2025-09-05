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
            links.add(link);
        }
        return Array.from(links);
    } catch (e) {
        Logger.log(`링크 추출 실패: ${pageUrl}, 오류: ${e.message}`);
        return [];
    }
}

function processDetailUrlWithGemini(detailUrl) {
  const sheet = SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME);
  const urlsInSheet = sheet.getLastRow() > 1 ? sheet.getRange(2, 7, sheet.getLastRow() - 1, 1).getValues().flat() : [];
  if (urlsInSheet.includes(detailUrl)) { return false; }

  Logger.log(`[2단계] Gemini 분석 시작: ${detailUrl}`);
  let textContent;
  try {
    const options = {'headers': {'User-Agent': 'Mozilla/5.0'}, 'muteHttpExceptions': true};
    const response = UrlFetchApp.fetch(detailUrl, options);
    if (response.getResponseCode() !== 200) {
      Logger.log(`상세 페이지 fetch 실패: 응답코드 ${response.getResponseCode()} | URL: ${detailUrl}`);
      return false;
    }
    const htmlContent = response.getContentText();
    textContent = htmlContent.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '').replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    if (textContent.length < 100) { return false; }
  } catch (e) {
    Logger.log(`상세 페이지 fetch 중 오류: ${detailUrl}, 오류: ${e.message}`);
    return false;
  }
  const apiKey = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  if (!apiKey) { Logger.log('오류: Gemini API 키가 설정되지 않았습니다.'); return false; }
  const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key=${apiKey}`;
  const prompt = `당신은 인프라 투자 전문 애널리스트입니다. 다음 텍스트 내용에서 투자 리서치에 필요한 핵심 정보를 추출하여 JSON 형식으로만 반환해주세요. 다른 설명, 서론, 결론, 코드 블록 마크(\`\`\`)는 절대 추가하지 마세요.
  추출 정보: {"title": "기사 전체 제목", "summary": "기사 내용 전체를 한 문장으로 요약", "publishedDate": "기사 발행일(YYYY-MM-DD 형식, 날짜 없으면 오늘 날짜 '${Utilities.formatDate(new Date(), "GMT+9", "yyyy-MM-dd")}' 사용)", "category": "내용 기반으로 [환경규제, 투자정책, 시장개방, 에너지, 정부정책, 기술동향] 중 하나만 선택", "impactLevel": "인프라 투자자 영향 중요도를 [높음, 중간, 낮음] 중 하나로 평가"}
  텍스트 내용: ${textContent.substring(0, 15000)}`;
  const payload = { contents: [{ parts: [{ text: prompt }] }] };
  const fetchOptions = { method: 'post', contentType: 'application/json', payload: JSON.stringify(payload), muteHttpExceptions: true };
  try {
    const apiResponse = UrlFetchApp.fetch(geminiUrl, fetchOptions);
    if (apiResponse.getResponseCode() !== 200) {
      Logger.log(`🔴 [API 요청 실패] URL: ${detailUrl} | 응답: ${apiResponse.getContentText()}`);
      return false;
    }
    let content = JSON.parse(apiResponse.getContentText()).candidates[0].content.parts[0].text;
    if (content.startsWith("```json")) { content = content.substring(7, content.length - 3).trim(); }
    const data = JSON.parse(content);
    if (data.title) {
      sheet.appendRow([ `GEMINI-${new Date().getTime()}`, data.title, data.summary, data.impactLevel, data.category, data.publishedDate, detailUrl ]);
      Logger.log(`✅ [추가 성공] ${data.title}`);
      return true;
    }
  } catch (e) {
    Logger.log(`🔴 [스크립트 오류] URL: ${detailUrl} | 오류: ${e.toString()}`);
  }
  return false;
}

function doGet(e) { return HtmlService.createTemplateFromFile('index').evaluate().setTitle('인프라 투자 동향 대시보드').addMetaTag('viewport', 'width=device-width, initial-scale=1.0'); }
function getDashboardData() { const sheet=SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME); if(sheet.getLastRow()<2){return{todayReports:[],recentReports:[],stats:{total:0,today:0,highImpact:0,categories:0}}} const data=sheet.getRange(2,1,sheet.getLastRow()-1,7).getValues(); const todayString=Utilities.formatDate(new Date(),"GMT+9","yyyy-MM-dd"); const allReports=data.map(row=>({id:row[0],title:row[1],summary:row[2],impactLevel:row[3],category:row[4],publishedDate:Utilities.formatDate(new Date(row[5]),"GMT+9","yyyy-MM-dd"),sourceURL:row[6]})).reverse(); const todayReports=allReports.filter(report=>report.publishedDate===todayString); const highImpactCount=allReports.filter(report=>report.impactLevel==='높음').length; const categories=[...new Set(allReports.map(report=>report.category))].length; return{todayReports:todayReports,recentReports:allReports.slice(0,6),stats:{total:allReports.length,today:todayReports.length,highImpact:highImpactCount,categories:categories}} }
function searchReports(searchTerm){if(!searchTerm||searchTerm.trim()==="")return[]; const sheet=SpreadsheetApp.openById(SPREADSHEET_ID).getSheetByName(SHEET_NAME); if(sheet.getLastRow()<2)return[]; const data=sheet.getRange(2,1,sheet.getLastRow()-1,7).getValues(); const lowerCaseSearchTerm=searchTerm.toLowerCase(); const allReports=data.map(row=>({id:row[0],title:row[1],summary:row[2],impactLevel:row[3],category:row[4],publishedDate:Utilities.formatDate(new Date(row[5]),"GMT+9","yyyy-MM-dd"),sourceURL:row[6]})); return allReports.filter(report=>(report.title.toLowerCase().includes(lowerCaseSearchTerm)||report.summary.toLowerCase().includes(lowerCaseSearchTerm)||report.category.toLowerCase().includes(lowerCaseSearchTerm))).reverse()}
