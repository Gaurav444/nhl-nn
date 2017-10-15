from __future__ import division
import math
import re
import os
import csv
import progressbar
from math import sqrt
import trueskill
from trueskill import BETA
from trueskill.backends import cdf
import database as db

MOMENTUM_DEGRADE = 2
MIN_GAMES_PLAYED = 5
HOME_ADV = 25

def elo(winner_elo, loser_elo):
    k = 20
    r1 = math.pow(10, float(winner_elo / 400))
    r2 = math.pow(10, float(loser_elo / 400))
    r1_coe = r1 / float(r1 + r2)
    r2_coe = 1 - r1_coe
    e1 = round(winner_elo + k * (1 - r1_coe))
    e2 = round(loser_elo + k * (0 - r2_coe))
    return e1, e2


def win_probability(player_rating, opponent_rating):
    delta_mu = player_rating.mu - opponent_rating.mu
    denom = sqrt(2 * (BETA * BETA) + pow(player_rating.sigma, 2) + pow(opponent_rating.sigma, 2))
    return cdf(delta_mu / denom)


#need to reverse ID's in table so new games added arent backwards

def process_totals():
    db.clear_table('processed')
    for season in range(1990,2019):
        print(season)
        teams = setup_teams()
        games = db.get_all('raw','id','DESC',season)
        match = {}
        ts = trueskill.TrueSkill(draw_probability=0)

        for g in games:
            try:
                if g['a_score'] != g['b_score']:
                    if teams[g['team_a']]['stats']['games'] > MIN_GAMES_PLAYED and teams[g['team_b']]['stats']['games'] > MIN_GAMES_PLAYED:
                        match = {
                            'team_a': g['team_a'],
                            'team_b': g['team_b'],
                            'a_score': teams[g['team_a']]['stats']['score'],
                            'b_score': teams[g['team_b']]['stats']['score'],
                            'a_score_against': teams[g['team_a']]['stats']['score_against'],
                            'b_score_against': teams[g['team_b']]['stats']['score_against'],
                            'a_elo': teams[g['team_a']]['stats']['elo']+HOME_ADV,
                            'b_elo': teams[g['team_b']]['stats']['elo'],
                            'a_games': teams[g['team_a']]['stats']['games'],
                            'b_games': teams[g['team_b']]['stats']['games'],
                            'a_win': teams[g['team_a']]['stats']['wins'],
                            'b_win': teams[g['team_b']]['stats']['wins'],
                            'a_vs_record': teams[g['team_a']]['teams'][g['team_b']],
                            'b_vs_record': teams[g['team_b']]['teams'][g['team_a']],
                            'a_momentum': teams[g['team_a']]['stats']['momentum'],
                            'b_momentum': teams[g['team_b']]['stats']['momentum'],
                            'a_trueskill': win_probability(teams[g['team_a']]['stats']['ts'], teams[g['team_b']]['stats']['ts']),
                            'b_trueskill': win_probability(teams[g['team_b']]['stats']['ts'], teams[g['team_a']]['stats']['ts']),
                            'outcome': g['outcome'],
                            'season': season,
                        }

                        db.insert_game('processed', match)

                    teams[g['team_a']]['stats']['games'] += 1
                    teams[g['team_b']]['stats']['games'] += 1

                    teams[g['team_a']]['stats']['score'] += g['a_score']
                    teams[g['team_b']]['stats']['score'] += g['b_score']

                    teams[g['team_a']]['stats']['score_against'] += g['b_score']
                    teams[g['team_b']]['stats']['score_against'] += g['a_score']


                    if g['outcome'] == 1:
                        winner = 'team_a'
                        loser = 'team_b'
                        win_score = g['a_score']
                        lose_score = g['b_score']
                    else:
                        winner = 'team_b'
                        loser = 'team_a'
                        win_score = g['b_score']
                        lose_score = g['a_score']

                    teams[g[winner]]['stats']['ts'], teams[g[loser]]['stats']['ts'] = trueskill.rate_1vs1(teams[g[winner]]['stats']['ts'],teams[g[loser]]['stats']['ts'])
                    teams[g[winner]]['stats']['elo'], teams[g[loser]]['stats']['elo'] = elo(teams[g[winner]]['stats']['elo'], teams[g[loser]]['stats']['elo'])
                    teams[g[winner]]['stats']['wins'] +=(win_score-lose_score)
                    teams[g[winner]]['teams'][g[loser]] += 1
                    teams[g[loser]]['stats']['momentum'] = round(teams[g[loser]]['stats']['momentum']/MOMENTUM_DEGRADE,4)
                    teams[g[winner]]['stats']['momentum'] += (1+ math.log(win_score-lose_score)) 

            except Exception as e:
                print(g)
                print(e)
 
    return teams


def make_training_set():
    print("\n\nCreating Training Set") 
    db.clear_table('games')
    games = db.get_all('processed', 'id')
    bar = progressbar.ProgressBar(max_value=len(games))
    cnt=0
    for g in games:
        bar.update(cnt)
        cnt+=1
        vs_games = g['a_vs_record'] + g['b_vs_record']
        match = {
            'wins': stat_avg_diff(g['a_win'], g['a_games'] ,g['b_win'], g['b_games']),
            'elo': round(g['a_elo'] - g['b_elo'],2),
            'vs': stat_avg_diff(g['a_vs_record'], vs_games ,g['b_vs_record'], vs_games), 
            'score': stat_avg_diff(g['a_score'], g['a_games'] ,g['b_score'], g['b_games']),
            'score_against': stat_avg_diff(g['a_score_against'], g['a_games'] ,g['b_score_against'], g['b_games']),
            'momentum': g['a_momentum'] - g['b_momentum'],
            'ts': g['a_trueskill'],
            'outcome':g['outcome'],
        }

        db.insert_game('games',match)


def stat_avg_diff(a_stat, a_games ,b_stat, b_games):
    if a_games == 0:
        a_avg = 0
    else:
        a_avg = a_stat/a_games

    if b_games == 0:
        b_avg = 0
    else:
        b_avg = b_stat/b_games

    diff = a_avg - b_avg
    return round(diff,4)


def setup_teams():
    teams = {}
    vs_teams = {}
    games = db.get_all_teams()
    for g in games:
        teams[g['team']] = 0
        vs_teams[g['team']] = {'teams': 0, 'stats': 0}

    for t in teams:
        vs_teams[t]['teams'] = teams
        vs_teams[t]['stats'] = {'elo': 1000, 'games': 0, 'wins': 0, 'score': 0, 'score_against': 0,'momentum':0,'ts':trueskill.Rating()}

    return vs_teams


def export_training_set():
    os.unlink('data/training.csv')
    csv_columns = ['wins','elo','score','score_against','momentum','vs','ts','outcome']
    games = db.get_all('games','id','desc')
    with open('data/training.csv', 'a', newline='') as c:
        full_write = csv.DictWriter(c, fieldnames=csv_columns)
        for g in games:
            del g['Id']
            full_write.writerow(g)


def main():
    process_totals()
    make_training_set()
    export_training_set()


if __name__ == "__main__":
    main()