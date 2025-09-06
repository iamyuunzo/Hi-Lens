function doGet() {
  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('Hi-PolicyLens - 정책/규제 모니터링')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function analyzeRegulation(prompt, conversationId = null) {
  try {
    const apiUrl = 'https://ai.potens.ai/api/chat';
    const apiKey = '6PC9V5gF5WrH3ZY6Z1wBpDa7Dqkxh81G'; // API 키 확인
    
    // 출처 포함한 전문적인 프롬프트
    const systemPrompt = `당신은 인프라 투자 규제 분석 전문가 Hi-PolicyLens AI입니다.

사용자의 질문: "${prompt}"

다음 형식으로 전문적이고 구체적인 답변을 제공해주세요:

## 📋 핵심 요약
- 질문의 핵심 내용을 3-4줄로 요약

## 📈 상세 분석
- 관련 법규 및 정책 상세 내용
- 최신 변화 동향 및 향후 전망  
- 투자 시 고려사항 및 리스크 분석
- 국내외 비교 분석 (해당시)

## 💡 실무 가이드
- 담당자가 확인해야 할 체크포인트
- 투자위원회 보고 시 핵심 사항

## 🔗 참고 자료 및 출처
- 관련 법령/규정 명칭 및 조항
- 주요 정부기관 발표자료
- 업계 가이드라인 문서
- 최신 업데이트 일자

**중요**: 모든 정보는 구체적인 출처와 함께 제공하고, 불확실한 내용은 명시해주세요.`;
    
    const payload = { 'prompt': systemPrompt };
    
    const options = {
      'method': 'POST',
      'headers': {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + apiKey
      },
      'payload': JSON.stringify(payload),
      'muteHttpExceptions': true, // HTTP 예외를 무시하고 응답 받기
      'timeout': 60000 // 타임아웃 60초로 설정
    };
    
    console.log('API 요청 시작: ' + new Date());
    const response = UrlFetchApp.fetch(apiUrl, options);
    console.log('API 응답 수신: ' + new Date());
    
    // 응답 상태 코드 확인
    if (response.getResponseCode() !== 200) {
      console.error('API 응답 오류:', response.getResponseCode(), response.getContentText());
      return {
        success: false,
        error: '서버 응답 오류: ' + response.getResponseCode()
      };
    }
    
    // 응답 내용 파싱 시도
    let responseData;
    try {
      responseData = JSON.parse(response.getContentText());
    } catch (e) {
      console.error('응답 파싱 오류:', e, response.getContentText());
      return {
        success: false,
        error: '응답 파싱 오류: ' + e.toString()
      };
    }
    
    // 응답 데이터 확인
    if (!responseData || (!responseData.response && !responseData.message)) {
      console.error('유효하지 않은 응답 데이터:', responseData);
      return {
        success: false,
        error: '유효하지 않은 응답 데이터'
      };
    }
    
    const conversation = {
      id: conversationId || generateConversationId(),
      timestamp: new Date().toISOString(),
      userMessage: prompt,
      aiResponse: responseData.response || responseData.message || JSON.stringify(responseData),
      title: generateConversationTitle(prompt)
    };
    
    saveConversation(conversation);
    
    return {
      success: true,
      data: responseData,
      conversation: conversation
    };
    
  } catch (error) {
    console.error('API 호출 에러:', error);
    return {
      success: false,
      error: error.toString()
    };
  }
}

function generateConversationId() {
  return 'conv_' + new Date().getTime() + '_' + Math.random().toString(36).substr(2, 9);
}

function generateConversationTitle(prompt) {
  return prompt.length > 25 ? prompt.substring(0, 25) + '...' : prompt;
}

function saveConversation(conversation) {
  try {
    const properties = PropertiesService.getScriptProperties();
    const conversations = getConversations();
    
    const existingIndex = conversations.findIndex(c => c.id === conversation.id);
    if (existingIndex !== -1) {
      conversations[existingIndex] = conversation;
    } else {
      conversations.unshift(conversation);
    }
    
    if (conversations.length > 50) {
      conversations.splice(50);
    }
    
    properties.setProperty('conversations', JSON.stringify(conversations));
    return true;
  } catch (error) {
    console.error('대화 저장 실패:', error);
    return false;
  }
}

function getConversations() {
  try {
    const properties = PropertiesService.getScriptProperties();
    const conversationsData = properties.getProperty('conversations');
    return conversationsData ? JSON.parse(conversationsData) : [];
  } catch (error) {
    console.error('대화 불러오기 실패:', error);
    return [];
  }
}

function getConversation(conversationId) {
  const conversations = getConversations();
  return conversations.find(c => c.id === conversationId) || null;
}

function deleteConversation(conversationId) {
  try {
    const conversations = getConversations();
    const filteredConversations = conversations.filter(c => c.id !== conversationId);
    
    const properties = PropertiesService.getScriptProperties();
    properties.setProperty('conversations', JSON.stringify(filteredConversations));
    
    return { success: true };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}

function continueConversation(conversationId, newMessage) {
  const conversation = getConversation(conversationId);
  if (!conversation) {
    return { success: false, error: '대화를 찾을 수 없습니다.' };
  }
  
  const contextPrompt = `이전 대화 맥락:
사용자: ${conversation.userMessage}
AI: ${conversation.aiResponse}

새로운 질문: ${newMessage}

위 맥락을 고려하여 새로운 질문에 대해 출처와 함께 구체적이고 전문적으로 답변해주세요.`;
  
  return analyzeRegulation(contextPrompt, conversationId);
}

// 데일리 업데이트 데이터 (실제로는 크롤링/API에서 가져올 예정)
function getTodayUpdates() {
  return [
    {
      title: "풍력 발전 정책 상세 내용: 2025년 적용 예정인 풍력 발전 관련 주요 법규",
      category: "풍력발전",
      impact: "높음",
      effectDate: "2025.01.01",
      summary: "최신 풍력 발전 및 풍력 정책: 규제 완화의 최근 변화와 2025년 이후 예상되는 정책 변경",
      source: "에너지부",
      link: "#"
    },
    {
      title: "투자 시 고려사항 및 리스크 분석: 규제 변화 규제와 비교 투자 사업 시장",
      category: "ESG투자",
      impact: "중간",
      effectDate: "2024.12.15",
      summary: "타 국가/지역과의 비교 분석: 주요국 풍력 발전 규제와 비교를 통한 시사점",
      source: "금융위원회",
      link: "#"
    },
    {
      title: "실무진을 위한 체크리스트: 2025년 규제 대응을 위한 주요 준비사항 및 절차",
      category: "탄소중립",
      impact: "높음",
      effectDate: "2025.03.01",
      summary: "정답지 확보 가능성: 투자 및 예상 등의 답변 정확성 및 절차 간소화 방향",
      source: "환경부",
      link: "#"
    }
  ];
}

function getWeeklyReports() {
  return [
    {
      title: "주간 ESG 투자 가이드라인 변경사항 종합",
      date: "2024.09.02",
      summary: "이번 주 발표된 ESG 관련 규제 변경사항과 투자 영향도 분석",
      category: "ESG",
      link: "#"
    },
    {
      title: "신재생 에너지 정책 주간 업데이트",
      date: "2024.09.01", 
      summary: "태양광, 풍력 발전 관련 정책 변화와 향후 전망",
      category: "신재생에너지",
      link: "#"
    }
  ];
}
