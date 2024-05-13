import requests
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup as bs
import pandas as pd
import argparse

import json, math, datetime


url = "https://judgment.judicial.gov.tw/FJUD/default.aspx"

headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

session = requests.Session()
session.headers.update(headers)
session.encoding = 'utf-8'

def get_page_state_data():
    html = session.get(url)
    soup = bs(html.content, "lxml")

    page_state_data = {
        "__VIEWSTATE": soup.find("input", {"id": "__VIEWSTATE"}).attrs["value"],
        "__VIEWSTATEGENERATOR": soup.find("input", {"id": "__VIEWSTATEGENERATOR"}).attrs["value"],
        "__VIEWSTATEENCRYPTED": soup.find("input", {"id": "__VIEWSTATEENCRYPTED"}).attrs["value"],
        "__EVENTVALIDATION": soup.find("input", {"id": "__EVENTVALIDATION"}).attrs["value"]
    }

    return page_state_data

def get_query(keyword):
    payload = {
        **get_page_state_data(),
        "txtKW": keyword,
        "judtype": "JUDBOOK",
        "whosub": "0",
        "ctl00$cp_content$btnSimpleQry": "送出查詢"
    }

    #session.cookies.update({"JUDBOOK_onekw": keyword})
    content = session.post(url, data=payload).content
    soup = bs(content, "lxml")

    query = soup.find("input", {"id": "hidQID"})["value"]

    return query

def get_pkid(url):
    content = session.get(url).text

    index = content.find("pkid")
    pkid = content[index:index + 100].split('"')[0]

    soup = bs(content, "lxml")
    text = soup.find("td", class_='tab_content').text.strip()

    return pkid, text

def get_page_data(query, page, limit):
    url = "https://judgment.judicial.gov.tw/FJUD/qryresultlst.aspx"
    params = {
        "ty": "JUDBOOK",
        "q": query,
        "sort": "DS",
        "page": page
    }

    page = session.get(url, params=params).content
    soup = bs(page, "lxml")

    links_list = []
    links = soup.find_all("a", {"id": "hlTitle"}, limit=limit)

    for link in links:
        url = "https://judgment.judicial.gov.tw/FJUD/" + link["href"]
        links_list.append(url)

    return links_list

def fetch_data(link):
    info = get_pkid(link)
    text = info[1]
    reference = ""

    url = "https://judgment.judicial.gov.tw/controls/GetJudRelatedLaw.ashx?" + info[0]

    try:
        data = session.get(url)
    except:
        data = session.get(url)


    default = {'count': 0, 'list': []}

    if data.text:
        try:
            data_json = json.loads(data.text.encode("utf-8"))
        except:
            data_json = json.loads(data.text[:-2])
    else:
        data_json = default


    for desc in data_json["list"]:
        reference += desc["desc"]

    return (text, reference)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("-N", "--num", type=int, help="Count iteration")
    parser.add_argument("-k", "--keyword", type=str, help="Keyword for parsing")

    args = parser.parse_args()


    keyword = args.keyword.encode("UTF-8")

    total_count = args.num

    data_text = []
    data_reference = []

    limit = 20
    remaining_count = total_count
    page_count = math.ceil(total_count / 20)

    query = get_query(keyword)

    with ThreadPoolExecutor() as executor:
        for number_page in range(1, page_count + 1):
            if remaining_count < 20:
                limit = remaining_count

            links = get_page_data(query, number_page, limit)
            futures = []

            for link in links:
                futures.append(executor.submit(fetch_data, link))


            for future in futures:
                text, reference = future.result()
                data_text.append(text)
                data_reference.append(reference)

            remaining_count -= 20


    # Write data to CSV
    data_csv = {
        "text": data_text,
        "reference": data_reference
    }

    data_df = pd.DataFrame(data_csv)

    file_name = datetime.datetime.now().strftime("%m%d%H%M%S%f") + ".csv"
    data_df.to_csv(file_name)



