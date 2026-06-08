import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
import urllib.parse

# 🔑 보내주신 네이버 개발자 센터 인증 키 자동 주입 완료
NAVER_CLIENT_ID = "WoaRobbnYpkvj36i98OR"
NAVER_CLIENT_SECRET = "TnlbM6lfPn"

# 1. 네이버 검색 API를 통해 기업의 공식 홈페이지 URL을 찾는 함수
def get_company_url_naver(company_name):
    try:
        # 네이버 웹문서 검색 활용 (기업명 공식 홈페이지 조건 검색)
        encText = urllib.parse.quote(f"{company_name} 공식 홈페이지")
        url = f"https://openapi.naver.com/v1/search/webkr.json?query={encText}&display=1"
        
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('items'):
                # 검색 결과 중 가장 첫 번째 링크 반환
                return result['items'][0]['link']
        return None
    except Exception as e:
        return None

# 2. 이메일 추출 핵심 함수
def extract_emails_from_url(url):
    if not url:
        return "홈페이지 주소를 찾을 수 없음"
        
    # 이메일 추출 전용 정규표현식
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=7)
        if response.status_code != 200:
            return "접속 실패"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        emails = set(re.findall(email_regex, soup.text))
        
        # 메인 페이지에 메일이 없을 경우 하부 Contact 페이지 탐색 
        if not emails:
            contact_links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].lower()
                if 'contact' in href or 'about' in href or '소개' in href:
                    full_url = href if href.startswith('http') else f"{url.rstrip('/')}/{href.lstrip('/')}"
                    contact_links.append(full_url)
            
            for link in list(set(contact_links))[:2]:
                try:
                    sub_resp = requests.get(link, headers=headers, timeout=5)
                    sub_emails = re.findall(email_regex, sub_resp.text)
                    emails.update(sub_emails)
                except:
                    continue

        return ", ".join(list(emails)) if emails else "이메일을 찾을 수 없음"
            
    except Exception as e:
        return "오류 발생"

# 3. Streamlit UI 대시보드
st.set_page_config(page_title="기업명 이메일 크롤러", layout="wide")
st.title("🏢 기업 이름 기반 이메일 추출기")
st.caption("네이버 검색 API 연동 완료 - 차단 우회 및 공식 홈페이지 이메일 매칭 대시보드")

st.markdown("---")

# 기업명 리스트 대량 입력창
company_input = st.text_area(
    "기업 이름을 입력하세요 (한 줄에 하나씩)",
    height=200,
    placeholder="삼성전자\n네이버\n카카오"
)

if st.button("🚀 크롤링 시작", type="primary"):
    if not company_input.strip():
        st.warning("⚠️ 기업 이름을 최소 하나 이상 입력해 주세요.")
    else:
        companies = [name.strip() for name in company_input.split('\n') if name.strip()]
        
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, company in enumerate(companies):
            status_text.text(f"⏳ 진행 중 ({idx+1}/{len(companies)}): {company} 홈페이지 찾는 중...")
            
            # 네이버 API 기반 홈페이지 URL 탐색
            url = get_company_url_naver(company)
            
            if url:
                status_text.text(f"⏳ 진행 중 ({idx+1}/{len(companies)}): {company} 이메일 스캐닝 중...")
                email_result = extract_emails_from_url(url)
            else:
                url = "공식 홈페이지 찾기 실패"
                email_result = "N/A"
                
            results.append({
                "기업 이름": company, 
                "찾은 홈페이지": url, 
                "추출된 이메일": email_result
            })
            
            progress_bar.progress((idx + 1) / len(companies))
            time.sleep(0.5)  # API 기반 안정적인 조회를 위한 최소 딜레이 설정
            
        status_text.text("✅ 크롤링 완료!")
        
        # 대시보드 표 출력
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        
        # 다운로드 버튼 구현
        csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 결과 Excel(CSV) 다운로드",
            data=csv,
            file_name="company_emails_final.csv",
            mime="text/csv"
        )
