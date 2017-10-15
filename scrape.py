from __future__ import division
import re
import urllib.request
from bs4 import BeautifulSoup as bs
import database as db


def load_page(page_url):
    try:
        req = urllib.request.Request(
            page_url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req).read()
        soup = bs(html, 'html.parser')
        return soup
    except Exception as e:
        print("/n/n#######   Error Loading URL   ####### /n/n")
        print(page_url)
        print(e)
        return 0


def match_details():
    games = db.get_missing_matches()
    for g in games:
        team = 'a'
        players = {'stats':1}
        try:
            soup = load_page('https://www.hltv.org'+g['stats_url'])
        except Exception as e:
            print(e)
            continue


def scrape_matches():
    offset = 0
    for season in range(2017,2019):
        print(season)
        soup = load_page('https://www.hockey-reference.com/leagues/NHL_'+str(season)+'_games.html')

        match_table = soup.find("table", { "class" : 'stats_table'})
        tbody = match_table.find('tbody')
        for tr in tbody.find_all('tr'):
            th = tr.find('th',{"class":'left'})
            tds = tr.find_all('td')

            a_score = tds[3].text
            b_score = tds[1].text

            if int(a_score) > int(b_score):
                outcome = 1
            else:
                outcome = 0

            game = {
                'team_a': clean_name(re.sub('(.*?)', '', tds[2].text)),
                'team_b': clean_name(re.sub('(.*?)', '', tds[0].text)),
                'a_score':a_score,
                'b_score':b_score,
                'outcome': outcome,
                'date': th.text,
                'season': season,
                'stats_url': th.find('a', href=True)['href'],
            }
            
            if db.check_game(game) == 0:
                db.insert_game('raw', game)

                

def upcoming_matches():
    matches = []
    soup = load_page('https://www.hltv.org/')
    column = soup.find("div", { "class" : 'top-border-hide' })
    upcoming = column.find_all("div", { "class" : 'teamrows' })
    
    print("\nScraping Upcoming Matches:")
    for teams in upcoming:
        t = teams.find_all("div",{'class':'teamrow'})
        team_a = clean_name(t[0].text)
        team_b = clean_name(t[1].text)
        matches.append([team_a,team_b])
 
    return matches     


def new_team_check(team_name):
    if db.check_team_slug(team_name) < 1:
        team = {'team': team_name}
        db.insert_game('teams', team)


def clean_name(team_name):
    clean_name = re.sub('[^A-Za-z0-9]+', '', team_name)
    slug = re.sub(r'\W+', '', str(clean_name).lower().strip())
    return slug


def main():
    scrape_matches()


if __name__ == "__main__":
    main()

