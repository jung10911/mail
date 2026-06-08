import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
# 구글 검색을 위한 라이브러리 추가
from googlesearch import search

# 1. 기업명으로 공식 홈페이지 URL을 찾는 함수
def get_company_url(company_name):
    try:
        # 구글에 "기업명"으로 검색하여 가장 상단의 결과 1개를 가져옴
        query = f"{company_name}"
        for url in search(query, num_results=1, lang="ko"):
            return url
    except Exception as e:
        return None
    return None

# 2. 이메일 추출 핵심 함수 (이전과 동일)
def extract_emails_from_url(url):
    if not url:
        return "홈페이지 주소를 찾을 수 없음"
        
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
        return f"오류 발생"

# 3. Streamlit UI 대시보드
st.set_page_config(page_title="기업명 이메일 크롤러", layout="wide")
st.title("🏢 기업 이름 기반 이메일 추출기")
st.caption("기업 이름만 입력하면 구글 검색을 통해 홈페이지를 찾고 이메일을 수집합니다.")

st.markdown("---")

# 텍스트 입력 창 (기업 이름 입력)
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
            status_text.text(f"⏳ 진행 중 ({idx+1}/{len(companies)}): {company} 검색 중...")
            
            # 1단계: 구글 검색으로 홈페이지 URL 찾기
            url = get_company_url(company)
            
            if url:
                status_text.text(f"⏳ 진행 중 ({idx+1}/{len(companies)}): {company} 이메일 추출 중...")
                # 2단계: 해당 URL에서 이메일 추출
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
            
            # 구글 차단 방지 및 서버 부하 감소를 위해 조금 더 긴 딜레이 설정 (2초)
            time.sleep(2.0)
            
        status_text.text("✅ 크롤링 완료!")
        
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 결과 Excel(CSV) 다운로드",
            data=csv,
            file_name="company_emails_by_name.csv",
            mime="text/csv"
        )
