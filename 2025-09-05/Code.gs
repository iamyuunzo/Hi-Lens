// Potens.AI API 설정
const POTENS_API_URL = 'https://ai.potens.ai/api/chat';
const API_KEY = 

// 실제 모니터링할 웹사이트 목록
const WEBSITES = [
  {
    url: 'https://www.epa.gov/newsroom',
    name: '미국 환경보호청',
    country: '미국',
    language: 'en',
    category: '환경규제',
    selectors: ['.view-content .node-title a', '.field-name-title a', 'h3 a']
  },
  {
    url: 'https://www.cbp.gov/newsroom/national-media-release',
    name: '미국 관세청',
    country: '미국', 
    language: 'en',
    category: '무역정책',
    selectors: ['.view-content .node-title a', '.news-item h3 a']
  },
  {
    url: 'https://www.motie.go.kr/motie/ne/presse/press2/bbs/bbsList.do?bbs_seq_n=81',
    name: '한국 산업통상자원부',
    country: '한국',
    language: 'ko', 
    category: '산업정책',
    selectors: ['td.subject a', '.board_list .subject a']
  }
];

/**
 * 웹 앱 진입점
 */
function doGet() {
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('RegWatch - 실시간 규제 모니터링')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

/**
 * 스프레드시트 초기화
 */
function initializeSpreadsheet() {
  let spreadsheet;
  const SPREADSHEET_ID = '1hs3oUfT-9yXxlBEH6KC69NiymJabWnQMmc9br2QstUs';
  
  try {
    spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  } catch (e) {
    spreadsheet = SpreadsheetApp.create('RegWatch 실시간 규제 데이터');
    Logger.log('새 스프레드시트 생성: ' + spreadsheet.getId());
  }
  
  let sheet = spreadsheet.getActiveSheet();
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, 12).setValues([[
      'ID', '제목', '카테고리', '요약', '주요변경사항', '시행일자', 
      '원문URL', '업데이트일', '담당기관', '국가', '키워드', '상태'
    ]]);
    
    sheet.getRange(1, 1, 1, 12).setBackground('#0f2e69').setFontColor('white').setFontWeight('bold');
  }
  
  return spreadsheet;
}

/**
 * 실제 웹사이트에서 뉴스 크롤링
 */
function crawlWebsite(website) {
  try {
    Logger.log(`${website.name} 크롤링 시작...`);
    
    const response = UrlFetchApp.fetch(website.url, {
      'method': 'GET',
      'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      },
      'muteHttpExceptions': true
    });
    
    if (response.getResponseCode() !== 200) {
      Logger.log(`HTTP 오류 ${response.getResponseCode()}: ${website.url}`);
      return [];
    }
    
    const html = response.getContentText();
    const newsItems = [];
    
    // 규제 관련 키워드
    const regulationKeywords = {
      'ko': ['규제', '법률', '정책', '개정', '시행', '발표', '공고', '고시', '제정'],
      'en': ['regulation', 'policy', 'law', 'rule', 'compliance', 'standard', 'requirement', 'enforcement']
    };
    
    const keywords = regulationKeywords[website.language] || regulationKeywords['en'];
    
    // 링크 추출
    const linkPattern = /<a[^>]*href=["']([^"']*)["'][^>]*>(.*?)<\/a>/gi;
    let match;
    
    while ((match = linkPattern.exec(html)) !== null && newsItems.length < 10) {
      const link = match[1];
      const title = match[2].replace(/<[^>]*>/g, '').trim();
      
      // 규제 관련 키워드 필터링
      const hasKeyword = keywords.some(keyword => 
        title.toLowerCase().includes(keyword.toLowerCase())
      );
      
      if (title.length > 10 && title.length < 200 && hasKeyword) {
        const fullUrl = link.startsWith('http') ? link : 
                       link.startsWith('/') ? website.url.split('/').slice(0,3).join('/') + link : 
                       website.url + '/' + link;
        
        newsItems.push({
          title: title,
          url: fullUrl,
          website: website,
          extractedDate: new Date().toISOString().split('T')[0]
        });
      }
    }
    
    Logger.log(`${website.name}에서 ${newsItems.length}개 뉴스 발견`);
    return newsItems;
    
  } catch (error) {
    Logger.log(`크롤링 오류 (${website.name}): ${error.toString()}`);
    return [];
  }
}

/**
 * Potens.AI로 뉴스 분석 및 요약
 */
function analyzeNewsWithAI(newsItem) {
  try {
    const prompt = `다음은 ${newsItem.website.name}에서 발표된 규제 관련 뉴스입니다.

제목: ${newsItem.title}
출처: ${newsItem.url}
기관: ${newsItem.website.name}
국가: ${newsItem.website.country}

이 뉴스를 분석하여 다음 JSON 형식으로 정리해주세요:

{
  "title": "규제 제목을 간결하게 정리",
  "summary": "핵심 내용을 150자 이내로 요약",
  "mainChanges": "주요 변경사항이나 새로운 요구사항을 구체적으로 설명",
  "effectiveDate": "시행일 또는 발표일 (YYYY-MM-DD 형식)",
  "keywords": "관련 키워드를 쉼표로 구분",
  "status": "ANNOUNCED/DRAFT/EFFECTIVE 중 하나",
  "fullContent": "상세한 기사 내용을 HTML 형식으로 작성 (h3, ul, li, p 태그 사용)"
}

규제와 관련이 없다면 null을 반환하세요.`;

    const response = UrlFetchApp.fetch(POTENS_API_URL, {
      'method': 'POST',
      'headers': {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + API_KEY
      },
      'payload': JSON.stringify({
        'prompt': prompt
      })
    });
    
    if (response.getResponseCode() === 200) {
      const responseText = response.getContentText();
      Logger.log('AI 응답: ' + responseText);
      
      // JSON 추출
      const jsonMatch = responseText.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const analysisResult = JSON.parse(jsonMatch[0]);
        
        if (analysisResult && analysisResult.title && analysisResult.title !== 'null') {
          return {
            id: 'news_' + new Date().getTime() + '_' + Math.random().toString(36).substr(2, 9),
            title: analysisResult.title,
            category: newsItem.website.category,
            summary: analysisResult.summary,
            mainChanges: analysisResult.mainChanges,
            effectiveDate: analysisResult.effectiveDate,
            sourceUrl: newsItem.url,
            lastUpdated: new Date().toISOString().split('T')[0],
            sourceAgency: newsItem.website.name,
            country: newsItem.website.country,
            keywords: analysisResult.keywords,
            status: analysisResult.status,
            fullContent: analysisResult.fullContent,
            isNew: true
          };
        }
      }
    }
    
    return null;
    
  } catch (error) {
    Logger.log(`AI 분석 오류: ${error.toString()}`);
    return null;
  }
}

/**
 * 실시간 뉴스 수집 및 분석
 */
function collectRealTimeNews() {
  Logger.log('실시간 뉴스 수집 시작...');
  
  const spreadsheet = initializeSpreadsheet();
  const sheet = spreadsheet.getActiveSheet();
  let newCardsCount = 0;
  
  WEBSITES.forEach(website => {
    try {
      const newsItems = crawlWebsite(website);
      
      newsItems.forEach(newsItem => {
        try {
          // 중복 체크
          const existingData = sheet.getDataRange().getValues();
          const isDuplicate = existingData.some(row => row[6] === newsItem.url);
          
          if (!isDuplicate) {
            const analysisResult = analyzeNewsWithAI(newsItem);
            
            if (analysisResult) {
              // 스프레드시트에 추가
              const newRow = [
                analysisResult.id,
                analysisResult.title,
                analysisResult.category,
                analysisResult.summary,
                analysisResult.mainChanges,
                analysisResult.effectiveDate,
                analysisResult.sourceUrl,
                analysisResult.lastUpdated,
                analysisResult.sourceAgency,
                analysisResult.country,
                analysisResult.keywords,
                analysisResult.status
              ];
              
              sheet.appendRow(newRow);
              newCardsCount++;
              Logger.log(`새 규제 카드 추가: ${analysisResult.title}`);
            }
          }
          
          // API 제한을 위한 대기
          Utilities.sleep(3000);
          
        } catch (error) {
          Logger.log(`뉴스 처리 오류: ${error.toString()}`);
        }
      });
      
      // 웹사이트 간 대기
      Utilities.sleep(5000);
      
    } catch (error) {
      Logger.log(`웹사이트 처리 오류 (${website.name}): ${error.toString()}`);
    }
  });
  
  Logger.log(`실시간 수집 완료. 새 카드 ${newCardsCount}개 추가됨.`);
  return newCardsCount;
}

/**
 * 저장된 규제 카드 가져오기
 */
function getRegulationCards() {
  try {
    const spreadsheet = initializeSpreadsheet();
    const sheet = spreadsheet.getActiveSheet();
    const lastRow = sheet.getLastRow();
    
    if (lastRow <= 1) {
      // 데이터가 없으면 샘플 데이터 반환
      return getSampleCards();
    }
    
    const data = sheet.getRange(2, 1, lastRow - 1, 12).getValues();
    
    return data.map(row => ({
      id: row[0],
      title: row[1],
      category: row[2],
      summary: row[3],
      mainChanges: row[4],
      effectiveDate: row[5],
      sourceUrl: row[6],
      lastUpdated: row[7],
      sourceAgency: row[8],
      country: row[9],
      keywords: row[10],
      status: row[11],
      isNew: isRecentCard(row[7]),
      fullContent: row[12] || generateDefaultContent(row[1], row[3], row[4])
    })).filter(card => card.title)
      .sort((a, b) => new Date(b.lastUpdated) - new Date(a.lastUpdated));
    
  } catch (error) {
    Logger.log('카드 데이터 가져오기 오류: ' + error.toString());
    return getSampleCards();
  }
}

/**
 * 기본 콘텐츠 생성 (fullContent가 없는 경우)
 */
function generateDefaultContent(title, summary, mainChanges) {
  return `
    <h3>개요</h3>
    <p>${summary}</p>
    
    <h3>주요 변경사항</h3>
    <p>${mainChanges}</p>
    
    <h3>상세 내용</h3>
    <p>자세한 내용은 원문 링크를 통해 확인하시기 바랍니다.</p>
  `;
}

/**
 * 샘플 카드 (초기 데이터용)
 */
function getSampleCards() {
  const today = new Date().toISOString().split('T')[0];
  
  return [
    {
      id: 'sample_001',
      title: '미국 EPA 새로운 대기질 기준 발표',
      category: '환경규제',
      summary: '미국 환경보호청이 PM2.5 미세먼지 기준을 기존 15㎍/㎥에서 12㎍/㎥로 강화한다고 발표했습니다.',
      mainChanges: 'PM2.5 연평균 기준 강화, 모니터링 지점 확대, 위반 시 제재 강화',
      effectiveDate: '2024-12-31',
      sourceUrl: 'https://www.epa.gov/newsroom/epa-strengthens-air-quality-standards',
      lastUpdated: today,
      sourceAgency: '미국 환경보호청',
      country: '미국',
      keywords: '대기질, PM2.5, 미세먼지, 환경기준',
      status: 'ANNOUNCED',
      isNew: true,
      fullContent: `
        <h3>배경</h3>
        <p>미국 환경보호청(EPA)이 국민 건강 보호를 위해 PM2.5 미세먼지 기준을 대폭 강화한다고 발표했습니다.</p>
        
        <h3>주요 변경사항</h3>
        <ul>
          <li>PM2.5 연평균 기준: 15㎍/㎥ → 12㎍/㎥</li>
          <li>모니터링 지점 30% 확대</li>
          <li>위반 시 과징금 최대 2배 인상</li>
        </ul>
        
        <h3>시행 일정</h3>
        <p>2024년 12월 31일부터 새로운 기준이 적용되며, 기업들은 6개월의 준비 기간을 갖게 됩니다.</p>
      `
    }
  ];
}

/**
 * 최근 카드 확인
 */
function isRecentCard(dateString) {
  try {
    const cardDate = new Date(dateString);
    const now = new Date();
    const diffDays = Math.ceil((now - cardDate) / (1000 * 60 * 60 * 24));
    return diffDays <= 7;
  } catch (e) {
    return false;
  }
}

/**
 * 수동 업데이트
 */
function manualUpdate() {
  return collectRealTimeNews();
}

/**
 * 자동 업데이트 트리거 설정
 */
function setupAutoUpdate() {
  // 기존 트리거 삭제
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    if (trigger.getHandlerFunction() === 'collectRealTimeNews') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  
  // 새 트리거 생성 (하루 3회: 오전 9시, 오후 2시, 오후 6시)
  [9, 14, 18].forEach(hour => {
    ScriptApp.newTrigger('collectRealTimeNews')
      .timeBased()
      .everyDays(1)
      .atHour(hour)
      .create();
  });
  
  Logger.log('자동 업데이트 트리거 설정 완료 (하루 3회)');
}

/**
 * 필터링 함수들
 */
function filterByCategory(category) {
  const cards = getRegulationCards();
  if (!category || category === '전체') {
    return cards;
  }
  return cards.filter(card => card.category.includes(category));
}

function searchCards(query) {
  const cards = getRegulationCards();
  if (!query || query.trim() === '') {
    return cards;
  }
  
  const searchTerm = query.toLowerCase();
  return cards.filter(card => 
    card.title.toLowerCase().includes(searchTerm) ||
    card.summary.toLowerCase().includes(searchTerm) ||
    card.keywords.toLowerCase().includes(searchTerm)
  );
}

/**
 * 테스트 함수
 */
function testRealTimeCrawling() {
  const website = WEBSITES[0]; // EPA 테스트
  const newsItems = crawlWebsite(website);
  
  if (newsItems.length > 0) {
    const testItem = newsItems[0];
    Logger.log('테스트 뉴스:', testItem.title);
    
    const analysis = analyzeNewsWithAI(testItem);
    Logger.log('분석 결과:', JSON.stringify(analysis, null, 2));
    
    return analysis;
  }
  
  return null;
}
