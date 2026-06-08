import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
import urllib.parse

# 🔑 네이버 개발자 센터 인증 키 설정
NAVER_CLIENT_ID = "WoaRobbnYpkvj36i98OR"
NAVER_CLIENT_SECRET = "TnlbM6lfPn"

# 1. 네이버 검색 API를 통해 기업의 공식 홈페이지 URL을 찾는 함수
def get_company_url_naver(company_name):
    try:
        # 충돌을 방지하기 위해 검색어 변수명을 완전히 다르게 지정
        search_keyword = f"{company_name} 홈페이지"
        encoded_keyword = urllib.parse.quote(search_keyword)
        
        # 네이버 웹문서 검색 API 주소
        naver_api_url = f"https://openapi.naver.com/v1/search/webkr.json?query={encoded_keyword}&display=3"
        
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
        }
        
        response = requests.get(naver_api_url, headers=headers)
        
        if response.status_code == 200:
            result_json = response.json()
            items_list = result_json.get('items', [])
            
            if items_list:
                # 블로그나 카페 링크는 제외하고 실제 기업 사이트 우선 필터링
                for item in items_list:
                    link = item['link']
                    if "naver.com" not in link and "daum.net" not in link:
                        return link
                # 필터링 후 남은 게 없다면 첫 번째 링크 반환
                return items_list[0]['link']
                
        if response.status_code != 200:
            return f"API 오류 (코드: {response.status_code})"
            
        return None
    except Exception as e:
        return f"검색 중 에러: {str(e)}"

# 2. 이메일 추출 핵심 함수
def extract_emails_from_url(url):
    if not url or url.startswith("공식 홈페이지") or url.startswith("API 오류") or url.startswith("검색 중 에러"):
        return "N/A"
        
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=7)
        if response.status_code != 200:
            return "홈페이지 접속 실패"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        emails = set(re.findall(email_regex, soup.text))
        
        # 메인 페이지에 없으면 Contact/소개 페이지 추가 검색
        if not emails:
            contact_links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].lower()
                if 'contact' in href or 'about' in href or '소개' in href or '안내' in href:
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
        return "접속/파싱 오류"

# 3. Streamlit UI 대시보드
st.set_page_config(page_title="기업명 이메일 크롤러 V2.1", layout="wide")
st.title("🏢 기업 이름 기반 이메일 추출기 (오류 수정 버전)")
st.caption("코드 내부 명칭 충돌 문제를 해결한 안정화 버전입니다.")

st.markdown("---")

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
            status_text.text(f"⏳ 진행 중 ({idx+1}/{len(companies)}): {company} 홈페이지 검색 중...")
            
            url = get_company_url_naver(company)
            
            if url and not url.startswith("API 오류") and not url.startswith("검색 중 에러"):
                status_text.text(f"⏳ 진행 중 ({idx+1}/{len(companies)}): {company} 이메일 추출 중...")
                email_result = extract_emails_from_url(url)
            else:
                email_result = "N/A"
                if not url:
                    url = "공식 홈페이지 찾기 실패"
                
            results.append({
                "기업 이름": company, 
                "찾은 홈페이지": url, 
                "추출된 이메일": email_result
            })
            
            progress_bar.progress((idx + 1) / len(companies))
            time.sleep(0.5)
            
        status_text.text("✅ 크롤링 완료!")
        
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 결과 Excel(CSV) 다운로드",
            data=csv,
            file_name="company_emails_fixed_final.csv",
            mime="text/csv"
        )
