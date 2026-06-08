import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
import urllib.parse

# 🔑 제공해주신 네이버 개발자 센터 인증 키
NAVER_CLIENT_ID = "WoaRobbnYpkvj36i98OR"
NAVER_CLIENT_SECRET = "TnlbM6lfPn"

# 1. 네이버 검색 API를 통해 기업의 공식 홈페이지 URL을 찾는 함수 (정확도 개선 버전)
def get_company_url_naver(company_name):
    try:
        # '공식 홈페이지' 텍스트를 제거하고 기업명만으로 웹문서와 일반 검색 유연하게 대처
        # 정확도를 위해 기업명 뒤에 사이트(site) 관련 키워드 조합
        encText = urllib.parse.quote(f"{company_name} 홈페이지")
        
        # 1차 시도: 웹문서 검색
        url = f"https://openapi.naver.com/v1/search/webkr.json?query={encText}&display=3"
        
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            items = result.get('items', [])
            
            if items:
                # 블로그나 카페 링크(blog.naver.com, cafe.naver.com)는 제외하고 기업 진짜 사이트 필터링
                for item in items:
                    link = item['link']
                    if "naver.com" not in link and "daum.net" not in link:
                        return link
                # 필터링 후 남은 게 없다면 첫 번째 링크 반환
                return items[0]['link']
                
        # 2차 시도: 웹문서 결과가 없을 경우 일반 블로그/문서 통합 필터링 시도
        # (간혹 네이버가 대기업 홈페이지를 웹문서 섹션에 안 넣어주는 경우가 있음)
        if response.status_code != 200:
            return f"API 오류 (코드: {response.status_code})"
            
        return None
    except Exception as e:
        return f"검색 중 에러: {str(e)}"

# 2. 이메일 추출 핵심 함수
def extract_emails_from_url(url):
    if not url or url.startswith("공식 홈페이지") or url.startswith("API 오류"):
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
st.set_page_config(page_title="기업명 이메일 크롤러 V2", layout="wide")
st.title("🏢 기업 이름 기반 이메일 추출기 (검색 엔진 튜닝 버전)")
st.caption("네이버 API 검색 쿼리 튜닝 및 필터링 로직이 업그레이드된 버전입니다.")

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
            
            # 개선된 검색 함수 호출
            url = get_company_url_naver(company)
            
            if url and not url.startswith("API 오류") and not url.startswith("검색 중 에러"):
                status_text.text(f"⏳ 진행 중 ({idx+1}/{len(companies)}): {company} 이메일 추출 중...")
                email_result = extract_emails_from_url(url)
            else:
                email_result = "N/A"
                if not url:
                    url = "공식 홈페이지 찾기 실패 (검색 결과 없음)"
                
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
            file_name="company_emails_fixed_v2.csv",
            mime="text/csv"
        )
