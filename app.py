import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
import urllib.parse

# 🔑 사용자 네이버 인증 키 설정
NAVER_CLIENT_ID = "WoaRobbnYpkvj36i98OR".strip()
NAVER_CLIENT_SECRET = "TnlbM6lfPn".strip()

# 1. 네이버 공식 가이드(블로그 검색 기반)를 적용하여 기업 URL을 찾는 함수
def get_company_url_naver(company_name):
    try:
        # 네이버 검색어 인코딩 처리 (공식 문서 방식)
        search_keyword = f"{company_name} 공식 홈페이지"
        encoded_keyword = urllib.parse.quote(search_keyword)
        
        # [수정] 보내주신 공식 가이드 문서의 기본 호출 주소 적용
        naver_api_url = f"https://openapi.naver.com/v1/search/blog?query={encoded_keyword}&display=5"
        
        # 공식 문서 명시 헤더 구성
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
        }
        
        response = requests.get(naver_api_url, headers=headers)
        
        # HTTP 응답 코드 조건문 (공식 문서의 if rescode==200 대응)
        if response.status_code == 200:
            result_json = response.json()
            items_list = result_json.get('items', [])
            
            if items_list:
                for item in items_list:
                    link = item['link']
                    # 블로그 내부 본문 링크 내에서 기업 도메인 형태 유추 및 정제
                    # 일반 블로그 글 내에 섞인 주소들 중 진짜 홈페이지 필터링을 위한 필터
                    if "naver.com" not in link and "daum.net" not in link and "tistory.com" not in link:
                        return link
                # 적절한 외부 주소가 없으면 검색된 첫 주소 사용
                return items_list[0]['link']
            else:
                # 블로그 결과가 안 나올 경우를 대비한 2차 백업 서브 쿼리 (뉴스/통합 섹션 대응 구조)
                backup_url = f"https://openapi.naver.com/v1/search/webkr.json?query={encoded_keyword}&display=3"
                backup_resp = requests.get(backup_url, headers=headers)
                if backup_resp.status_code == 200:
                    bk_items = backup_resp.json().get('items', [])
                    if bk_items: return bk_items[0]['link']
                
        # 401 권한오류를 포함한 에러 핸들링 출력
        if response.status_code != 200:
            return f"API 오류 (코드: {response.status_code})"
            
        return None
    except Exception as e:
        return f"검색 중 에러: {str(e)}"

# 2. 이메일 주소 정규식 크롤링 함수
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
        
        # 메인 페이지 부재 시 서브 Contact 스캐닝 기법 적용
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

# 3. Streamlit 웹 인프라 UI 구성
st.set_page_config(page_title="기업명 이메일 크롤러 V3", layout="wide")
st.title("🏢 기업 이름 기반 이메일 추출기 (공식 API 가이드 반영)")
st.caption("네이버 개발자 가이드 라인 규격에 맞춰 URL 탐색 인터페이스를 패치한 최종 버전입니다.")

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
            file_name="company_emails_official_fixed.csv",
            mime="text/csv"
        )
