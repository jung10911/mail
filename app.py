import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time

# 1. 이메일 추출 핵심 함수
def extract_emails_from_url(url):
    # URL 형식 보정
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # 이메일 매칭 정규표현식
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        # 1차: 메인 페이지 탐색
        response = requests.get(url, headers=headers, timeout=7)
        if response.status_code != 200:
            return f"접속 실패 (Status Code: {response.status_code})"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        emails = set(re.findall(email_regex, soup.text))
        
        # 2차: 메인에 없다면 하부 'Contact' 이나 'About' 페이지 추가 탐색
        if not emails:
            contact_links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].lower()
                if 'contact' in href or 'about' in href or '소개' in href:
                    # 상대 경로일 경우 절대 경로로 변환
                    full_url = href if href.startswith('http') else f"{url.rstrip('/')}/{href.lstrip('/')}"
                    contact_links.append(full_url)
            
            # 중복 제거 후 탐색
            for link in list(set(contact_links))[:2]: # 최대 2개 서브페이지만 탐색
                try:
                    sub_resp = requests.get(link, headers=headers, timeout=5)
                    sub_emails = re.findall(email_regex, sub_resp.text)
                    emails.update(sub_emails)
                except:
                    continue

        # 결과 반환
        if emails:
            return ", ".join(list(emails))
        else:
            return "이메일을 찾을 수 없음"
            
    except requests.exceptions.Timeout:
        return "시간 초과 (Timeout)"
    except Exception as e:
        return f"오류 발생: {str(e)}"

# 2. Streamlit UI 대시보드 구성
st.set_page_config(page_title="기업 이메일 크롤러", layout="wide")
st.title("🏢 기업 이메일 추출")
st.caption("기업 리스트(URL)를 입력하면 홈페이지 내 이메일 주소를 자동으로 수집합니다. (엑셀 복사/붙여넣기 가능)")

st.markdown("---")

# 텍스트 입력 창 (엑셀에서 드래그 후 붙여넣기 가능)
url_input = st.text_area(
    "기업 웹사이트 URL 리스트를 입력하세요 (엑셀에서 복사하여 붙여넣어도 됩니다)",
    height=250,
    placeholder="naver.com\ndaum.net\ngoogle.com"
)

if st.button("🚀 크롤링 시작", type="primary"):
    if not url_input.strip():
        st.warning("⚠️ URL을 최소 하나 이상 입력해 주세요.")
    else:
        # 💡 [핵심 수정] 엑셀 붙여넣기 시 발생하는 탭(\t), 캐리지 리턴(\r), 양끝 공백 전면 제거
        raw_urls = url_input.split('\n')
        urls = []
        for url in raw_urls:
            cleaned_url = url.strip().replace('\r', '').replace('\t', '')
            if cleaned_url:  # 빈 줄이 아닐 때만 리스트에 추가
                urls.append(cleaned_url)
        
        if not urls:
            st.error("❌ 유효한 URL 주소를 찾을 수 없습니다.")
        else:
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 반복문 돌며 크롤링 진행
            for idx, url in enumerate(urls):
                status_text.text(f"⏳ 진행 중 ({idx+1}/{len(urls)}): {url}")
                
                # 크롤링 함수 호출
                email_result = extract_emails_from_url(url)
                results.append({"기업 URL": url, "추출된 이메일": email_result})
                
                # 진행바 업데이트
                progress_bar.progress((idx + 1) / len(urls))
                
                # 디도스 방지 및 IP 차단 예방을 위한 타임 딜레이 (1초)
                time.sleep(1.0)
                
            status_text.text("✅ 크롤링 완료!")
            
            # 결과 데이터프레임 변환 및 출력
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
            
            # 엑셀/CSV 다운로드 버튼 제공
            csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="📥 결과 Excel(CSV) 다운로드",
                data=csv,
                file_name="company_emails.csv",
                mime="text/csv"
            )
